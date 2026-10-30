// End-to-end UI checks for the Milestone 6 dashboard: real FastAPI server, real browser, no model calls.
// Live smoke cards are used where the saved run has the state; the labelled test-fixture run covers the rest.
import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { hashes, REPO, startServer } from './server.js'

const SMOKE = 'agent3_overnight_smoke_v1', V1 = 'agent3_overnight_offline_v1', V2 = 'agent3_overnight_offline_v2'
const FIXTURE = 'dashboard_states_fixture_v1'
let server

test.afterEach(async () => { await server?.stop() })

const cardBox = (page, text) => page.locator('[data-testid=card]', { hasText: text })
async function open(page, run, extra = '') {
  await page.goto(`${server.url}/#run=${run}${extra}`)
  await page.reload() // hash-only navigation does not reload the app
  await expect(page.getByTestId('run-banner')).toBeVisible()
  await page.getByTestId('actor-select').selectOption('U006')
}
async function decisionsFor(run, cardId) {
  const all = (await server.api(`/api/runs/${run}/decisions`)).decisions
  return cardId ? all.filter(d => d.card_id === cardId) : all
}
async function cardId(run, predicate) {
  const brief = await server.api(`/api/runs/${run}/brief`)
  return brief.cards.find(c => predicate(c.card)).card
}

test('approve -> refresh -> restart keeps exactly one decision, never executed', async ({ page, context }) => {
  server = await startServer('approve')
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: server.url })
  const hosts = new Set(), posts = []
  page.on('request', r => { hosts.add(new URL(r.url()).host); if (r.method() === 'POST') posts.push(new URL(r.url()).pathname) })
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  await open(page, FIXTURE)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Copy draft' }).click()
  await expect(box.getByTestId('copy-note')).toHaveText('Copied to your clipboard. Nothing was posted.')
  expect(posts).toEqual([]) // copying is not posting
  await box.getByRole('button', { name: 'Approve…' }).click()
  await expect(box.getByTestId('form-text-origin')).toHaveText('Model-grounded text (unchanged)')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toContainText('Nothing is posted or executed')
  await expect(box.getByTestId('text-origin')).toHaveText('Model-grounded text (validated card text, unchanged)')
  await expect(box.getByTestId('decision-text')).toHaveText(card.recommended_action.draft_text)
  await expect(box.getByTestId('decision-states')).toHaveText('Execution: not executed · Outcome: not observed')
  await box.getByRole('button', { name: /Done/ }).click()
  await expect(page.getByTestId('active-RECOMMENDED_ACTION').getByTestId('card')).toHaveCount(0)
  await expect(page.getByTestId('resolved-RECOMMENDED_ACTION')).toContainText('Resolved (1)')

  for (const step of ['refresh', 'restart']) {
    if (step === 'restart') await server.restart()
    await page.reload()
    const resolved = page.getByTestId('resolved-RECOMMENDED_ACTION')
    await resolved.locator(':scope > summary').click()
    await expect(resolved.getByTestId('decision-current')).toHaveCount(1)
    await expect(resolved.getByTestId('card-summary')).toHaveText(card.summary) // original assessment intact
    const saved = await decisionsFor(FIXTURE)
    expect(saved).toHaveLength(1)
    expect(saved[0].decision.execution.state).toBe('NOT_EXECUTED')
    expect(saved[0].decision.outcome.state).toBe('NOT_OBSERVED')
    await expect(resolved.getByTestId('indexing-status')).toHaveText('Retrieval: saved, not yet in a retrieval snapshot')
  }
  expect([...hosts]).toEqual([`127.0.0.1:${server.port}`]) // nothing leaves localhost
  expect(posts.every(p => p.endsWith('/decisions'))).toBe(true)
})

test('double click and duplicate requests create one decision; key reuse with new content is refused', async ({ page }) => {
  server = await startServer('duplicates')
  const card = await cardId(FIXTURE, c => c.card_line === 'NEEDS_REVIEW')
  await open(page, FIXTURE)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Confirm announcement').check()
  await box.getByTestId('save-decision').dblclick()
  await expect(box.getByTestId('save-success')).toBeVisible()
  expect(await decisionsFor(FIXTURE, card.card_id)).toHaveLength(1)

  const audio = await cardId(SMOKE, c => c.project_id === 'audio_multimodal')
  const result = await page.evaluate(async ({ url }) => {
    const send = body => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'ui-test-duplicate-1' }, body: JSON.stringify(body) })
      .then(async r => ({ status: r.status, body: await r.json() }))
    const body = { kind: 'ROUTE_TO_EXPERT', actor_id: 'U006', expert: 'ENGINEERING' }
    const pair = await Promise.all([send(body), send(body)])
    const changed = await send({ ...body, note: 'different content' })
    return { pair, changed }
  }, { url: `${server.url}/api/runs/${SMOKE}/cards/${audio.card_id}/decisions` })
  expect(result.pair.map(r => r.status).sort()).toEqual([200, 201])
  expect(result.pair[0].body.entry.entry_id).toBe(result.pair[1].body.entry.entry_id)
  expect(result.changed.status).toBe(422)
  expect(result.changed.body.code).toBe('IDEMPOTENCY_KEY_REUSED')
  const saved = await decisionsFor(SMOKE, audio.card_id)
  expect(saved).toHaveLength(1)
  expect(saved[0].note).toBeNull()
})

test('a lost response is recovered by a safe retry, without a duplicate', async ({ page }) => {
  server = await startServer('lost-response')
  const submit = await cardId(SMOKE, c => c.project_id === 'response_preference')
  let dropped = false
  await page.route('**/decisions', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue()
    dropped = true
    await route.fetch() // reaches the server, which commits the decision
    await route.abort('connectionreset') // ...but the browser never sees the answer
  })
  await open(page, SMOKE)
  const box = cardBox(page, submit.topic_name)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Override severity').check()
  await box.locator('select[name=severity]').selectOption('MEDIUM')
  await box.locator('textarea[name=note]').fill('Known workaround limits the impact for this batch.')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-uncertain')).toBeVisible()
  await expect(box.getByTestId('save-success')).toHaveCount(0)
  expect(await decisionsFor(SMOKE, submit.card_id)).toHaveLength(1) // the server did save it
  await box.getByRole('button', { name: 'Retry safely' }).click()
  await expect(box.getByTestId('save-success')).toContainText('no duplicate was created')
  const saved = await decisionsFor(SMOKE, submit.card_id)
  expect(saved).toHaveLength(1)
  expect(saved[0].decision.tl_response.severity_override).toEqual({ proposed: 'HIGH', tl_selected: 'MEDIUM', reason: 'Known workaround limits the impact for this batch.' })
  await expect(box.getByText('the rubric is unchanged')).toBeVisible()
  await expect(box.locator('header')).toContainText('Severity high') // the card's assessment is not rewritten
})

test('each structured resolution saves its own decision and leaves cards unchanged', async ({ page }) => {
  server = await startServer('resolutions')
  const before = hashes()
  const faq = await cardId(V2, c => c.recommended_action?.action_type === 'UPDATE_FAQ')
  const korean = await cardId(V2, c => c.recommended_action?.action_type === 'ROUTE_TO_LANGUAGE_SPECIALIST')
  const bare = await cardId(V2, c => c.recommended_action === null && c.project_id === 'multilingual_eval')
  const v1card = await cardId(V1, c => c.card_line === 'NEEDS_REVIEW' && c.project_id === 'safety_classification')
  const alt = await cardId(FIXTURE, c => c.card_line === 'NEEDS_REVIEW')

  await open(page, V2, `&project=${faq.project_id}`)
  let box = cardBox(page, faq.topic_name)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Confirm FAQ update').check()
  await expect(box.locator('textarea[name=text]')).toHaveValue(faq.recommended_action.draft_text)
  await box.locator('textarea[name=text]').fill(`${faq.recommended_action.draft_text} Checked by the team lead.`)
  await expect(box.getByTestId('form-text-origin')).toHaveText('TL-edited text (not model-grounded)')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('text-origin')).toHaveText('TL-edited text (not model-grounded)')

  await open(page, V2, `&project=${korean.project_id}`)
  box = cardBox(page, korean.topic_name)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Route to an expert').check()
  await box.locator('select[name=expert]').selectOption('LANGUAGE_SPECIALIST')
  await expect(box.locator('textarea[name=text]')).toHaveValue(korean.recommended_action.draft_text)
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('text-origin')).toHaveText('Model-grounded text (validated card text, unchanged)')

  box = cardBox(page, bare.topic_name).first()
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Confirm announcement').check()
  await expect(box.getByTestId('save-decision')).toBeDisabled() // no matching draft: the TL must write the text
  await box.locator('textarea[name=text]').fill('Please keep new examples in the batch thread.')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('text-origin')).toHaveText('TL-written text (not model-grounded)')

  await open(page, V1, `&project=${v1card.project_id}`)
  box = cardBox(page, v1card.topic_name).first()
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Dismiss').check()
  await expect(box.getByTestId('save-decision')).toBeDisabled()
  await box.locator('textarea[name=note]').fill('Duplicate of another card.')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toContainText('not evidence that the underlying issue is resolved')

  await open(page, FIXTURE)
  box = cardBox(page, alt.topic_name)
  await expect(box.getByTestId('alternatives')).toContainText('Update the FAQ')
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Confirm FAQ update').check()
  await expect(box.getByTestId('form-text-origin')).toHaveText('Model-grounded text (unchanged)')
  await box.getByTestId('save-decision').click()
  await expect(box.getByText('from a supported alternative')).toBeVisible()

  const all = [...await decisionsFor(V2), ...await decisionsFor(V1), ...await decisionsFor(FIXTURE)]
  expect(all.map(d => [d.kind, d.text.origin]).sort()).toEqual([
    ['CONFIRM_ANNOUNCEMENT', 'TL_WRITTEN'], ['CONFIRM_FAQ_UPDATE', 'MODEL_GROUNDED'], ['CONFIRM_FAQ_UPDATE', 'TL_EDITED'],
    ['DISMISS', 'NONE'], ['ROUTE_TO_EXPERT', 'MODEL_GROUNDED']])
  expect(hashes()).toEqual(before)
})

test('a stale edit is shown as a conflict, not saved over the newer decision', async ({ browser }) => {
  server = await startServer('stale')
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  const [a, b] = [await browser.newPage(), await browser.newPage()]
  for (const p of [a, b]) {
    await p.goto(`${server.url}/#run=${FIXTURE}`)
    await p.getByTestId('actor-select').selectOption(p === a ? 'U006' : 'U001')
    await cardBox(p, card.topic_name).getByRole('button', { name: 'Approve…' }).click()
  }
  await cardBox(a, card.topic_name).getByTestId('save-decision').click()
  await expect(cardBox(a, card.topic_name).getByTestId('save-success')).toBeVisible()
  const boxB = cardBox(b, card.topic_name)
  await boxB.getByTestId('save-decision').click()
  await expect(boxB.getByTestId('save-conflict')).toContainText('by U006')
  await boxB.getByRole('button', { name: 'Show the latest decision' }).click()
  const resolved = b.getByTestId('resolved-RECOMMENDED_ACTION')
  await resolved.locator(':scope > summary').click()
  await expect(resolved.getByTestId('decision-current')).toContainText('by U006')
  const saved = await decisionsFor(FIXTURE)
  expect(saved.map(d => d.actor_id)).toEqual(['U006'])
})

test('model review Accept/Reject/Defer change only review records', async ({ page }) => {
  server = await startServer('review')
  const before = hashes()
  const cardsBefore = (await server.api(`/api/runs/${SMOKE}/brief`)).cards
  await open(page, SMOKE)
  await page.getByTestId('tab-queue').click()
  const items = page.getByTestId('review-item')
  await expect(items).toHaveCount(52)
  const ids = await items.evaluateAll(els => els.slice(0, 3).map(e => e.dataset.itemId))
  const item = id => page.locator(`[data-item-id="${id}"]`)
  await item(ids[0]).getByTestId('review-accept').click()
  await expect(items).toHaveCount(51) // accepted: out of the open list
  await item(ids[1]).getByTestId('review-reject').click()
  await expect(items).toHaveCount(50)
  await item(ids[2]).getByTestId('review-defer').click()
  await expect(item(ids[2]).getByTestId('review-history')).toContainText('defer (kept open)')
  await expect(items).toHaveCount(50) // deferred stays open
  await page.getByRole('button', { name: /^accepted/ }).click()
  await expect(item(ids[0]).getByTestId('review-state')).toHaveText('accepted')
  await page.getByRole('button', { name: /^rejected/ }).click()
  await expect(item(ids[1]).getByTestId('review-history')).toContainText('negative example')
  const negatives = await server.api(`/api/runs/${SMOKE}/negative-examples`)
  expect(negatives.items.map(i => i.item.item_id)).toEqual([ids[1]])
  expect((await server.api(`/api/runs/${SMOKE}/brief`)).cards).toEqual(cardsBefore)
  expect(await decisionsFor(SMOKE)).toEqual([])
  expect(hashes()).toEqual(before)
})

test('source and thread views come from saved evidence and keep superseded labels', async ({ page }) => {
  server = await startServer('evidence')
  const runs = await server.api(`/api/runs/${V2}/brief`)
  let target = null
  for (const c of runs.cards) {
    const detail = await server.api(`/api/runs/${V2}/cards/${c.card.card_id}`)
    const e = detail.evidence.find(x => x.superseded_label?.startsWith('Superseded section'))
    if (e) { target = { card: c.card, evidence: e }; break }
  }
  expect(target).not.toBeNull()
  await open(page, V2, `&project=${target.card.project_id}`)
  const box = page.locator(`[data-card-id="${target.card.card_id}"]`)
  await box.getByTestId('all-evidence').locator('summary').click()
  const row = box.getByTestId('all-evidence').locator('li', { hasText: target.evidence.title }).filter({ has: page.getByTestId('superseded-label') }).first()
  await expect(row.getByTestId('superseded-label')).toContainText('Superseded section')
  await row.getByRole('button').click()
  const panel = page.getByTestId('evidence-detail')
  await expect(panel.getByTestId('superseded-banner')).toContainText('Not current: Superseded section')
  await expect(panel.getByTestId('superseded-label')).toBeVisible()
  await expect(panel.getByTestId('evidence-text')).toContainText('[HISTORICAL - NOT CURRENT GUIDANCE')
  await expect(panel).toContainText('Source date')
  await expect(panel).toContainText('Scope')
  await expect(panel).toContainText('No Slack permalink stored')
  await page.getByRole('button', { name: 'Close' }).click()

  await open(page, SMOKE)
  const audio = cardBox(page, 'LT audio player playback failure')
  await audio.getByTestId('thread-link').first().click()
  const thread = page.getByTestId('thread-detail')
  await expect(thread.getByTestId('permalink-note')).toContainText('No Slack permalink is stored')
  await expect(thread.getByTestId('thread-message').first()).toContainText('matches saved evidence')
  expect(page.url()).toContain('panel=thread')
  await page.reload() // deep link reopens the same view
  await expect(page.getByTestId('thread-detail')).toBeVisible()
  await page.getByRole('button', { name: 'Close' }).click()
  await audio.getByTestId('source-link').first().click()
  await expect(page.getByTestId('evidence-detail')).toContainText('saved evidence')
})

test('failed, incomplete, scripted and fixture runs are labelled and never merged', async ({ page }) => {
  server = await startServer('runs')
  await open(page, SMOKE)
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'LIVE')
  await expect(page.getByTestId('tile-out-of-scope')).toContainText('85')
  await expect(page.getByTestId('semantic-source').first()).toHaveText('Live model')

  await page.getByTestId('run-select').selectOption(V1)
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'SCRIPTED')
  await expect(page.getByTestId('run-banner')).toContainText('Scripted run, not model output')
  await expect(page.getByTestId('run-status')).toHaveText('complete with failures')
  await expect(page.getByTestId('run-banner')).toContainText(`Another directory (${V2}) has the same run ID`)
  await expect(page.getByTestId('tile-failed')).toContainText('1')
  await expect(page.getByTestId('incomplete-work')).toContainText('topic failed')
  await page.getByTestId('topics-details').locator('summary').click()
  await expect(page.locator('[data-testid=topic-row][data-outcome=TOPIC_FAILED]')).toHaveCount(1)
  await expect(page.getByText('Scripted placeholder (nothing judged)').first()).toBeVisible()
  await expect(page.getByText('Scripted (prepared judgments)').first()).toBeVisible()

  await page.getByTestId('run-select').selectOption(FIXTURE)
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'TEST_FIXTURE')
  await expect(page.getByTestId('run-status')).toHaveText('incomplete')
  await expect(page.getByTestId('tile-unprocessed')).toContainText('1')
  await expect(page.getByTestId('incomplete-work')).toContainText('unprocessed budget')
  await expect(page.getByTestId('semantic-source').first()).toHaveText('Test fixture (hand-written)')
  // Project filter narrows this run only; other runs' cards never appear.
  await page.getByTestId('project-select').selectOption('audio_multimodal')
  await expect(page.getByTestId('card')).toHaveCount(1)
  await expect(page.getByTestId('group-OBSERVATION')).toContainText('No action needed now')
})

test('a saved decision reaches a later retrieval snapshot with its exact states', async ({ page }) => {
  server = await startServer('retrieval')
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  await open(page, FIXTURE)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Approve…' }).click()
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('indexing-status')).toHaveCount(0) // a fresh save shows success first
  await box.getByRole('button', { name: /Done/ }).click()
  const cutoff = new Date().toISOString() // after the decision was saved: a coherent later cutoff
  const run = args => execFileSync('uv', ['run', '--locked', 'python', ...args], { cwd: REPO, encoding: 'utf-8' })
  const built = JSON.parse(run(['scripts/build_decision_snapshot.py', '--cutoff', cutoff, '--index-dir', `${server.dir}/snapshot`,
    '--export-dir', `${server.dir}/exports`, '--decision-db', server.db, '--build']))
  expect(built.decisions_indexed).toBe(1)
  expect(built.decisions_after_cutoff).toEqual([])
  await page.reload()
  const resolved = page.getByTestId('resolved-RECOMMENDED_ACTION')
  await resolved.locator(':scope > summary').click()
  await expect(resolved.getByTestId('indexing-status')).toContainText('in snapshot')
  const found = JSON.parse(run(['-c', `
import json, sys
from threadsense.retrieval.search import Retriever
r = Retriever(sys.argv[1]).search('team lead approved reminder made-up phone number fictional story', 'safety_classification', top_k=10)
print(json.dumps([{k: x['metadata'][k] for k in ('origin', 'decision_status', 'execution_status', 'outcome_status')} for x in r['results']]))
`, `${server.dir}/snapshot`]).trim().split('\n').at(-1))
  expect(found).toContainEqual({ origin: 'tl_decision_store', decision_status: 'tl_approved', execution_status: 'not_executed', outcome_status: 'not_observed' })
})
