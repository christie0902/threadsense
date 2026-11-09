// End-to-end UI checks for the Milestone 6 dashboard: real FastAPI server, real browser, no model calls.
// Live smoke cards are used where the saved run has the state; the labelled test-fixture run covers the rest.
import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { hashes, REPO, startServer } from './server.js'

const SMOKE = 'agent3_overnight_smoke_v1', V1 = 'agent3_overnight_offline_v1', V2 = 'agent3_overnight_offline_v2'
const FIXTURE = 'dashboard_states_fixture_v1'
const ROUTING = 'agent3_recipient_routing_v1'
let server

test.afterEach(async () => { await server?.stop() })

// Cards are found by their saved topic name (a projection-gap card displays a fallback title instead).
const cardBox = (page, name) => page.locator(`[data-testid=card][data-topic-name=${JSON.stringify(name)}]`)
async function open(page, run, extra = '') {
  await page.goto(`${server.url}/#run=${run}${extra}`)
  await page.reload() // hash-only navigation does not reload the app
  await expect(page.getByTestId('run-banner')).toBeVisible()
  await expect(page.getByTestId('session-user')).toContainText('Priya')
}
// Card details sit behind the card's expander, one tab at a time.
async function details(box, tab) {
  if (await box.getByTestId('card-detail').count() === 0) await box.getByTestId('card-expand').click()
  if (tab) await box.getByRole('tab', { name: tab }).click()
}
// Reviewed cards are listed under the Reviewed tab (a saved decision; execution not recorded).
async function reviewedTab(page) {
  await page.getByTestId('tab-reviewed').click()
  return page.getByTestId('feed')
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
  await details(box, 'Action & draft')
  const copyButton = box.getByTestId('card-detail').getByRole('button', { name: 'Copy draft' })
  await copyButton.scrollIntoViewIfNeeded() // positions are viewport-relative: measure without a scroll in between
  const draftBefore = await box.getByTestId('action-draft').boundingBox()
  await copyButton.click()
  await expect(box.getByTestId('copy-note')).toHaveText('Copied to your clipboard. Nothing was posted.')
  // The note sits below its button and does not move the draft.
  const [note, button] = [await box.getByTestId('copy-note').boundingBox(), await copyButton.boundingBox()]
  expect(note.y).toBeGreaterThanOrEqual(button.y + button.height)
  expect(await box.getByTestId('action-draft').boundingBox()).toEqual(draftBefore)
  expect(posts).toEqual([]) // copying is not posting
  await box.getByTestId('card-collapse').click()
  await expect(box.getByTestId('card-detail')).toHaveCount(0)
  await box.getByRole('button', { name: 'Approve…' }).click()
  await expect(box.getByTestId('form-text-origin')).toHaveText('Model-grounded text (unchanged)')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toContainText('Nothing is posted or executed')
  await expect(box.getByTestId('text-origin')).toHaveText('Model-grounded text (validated card text, unchanged)')
  await expect(box.getByTestId('decision-text')).toHaveText(card.recommended_action.draft_text)
  await expect(box.getByTestId('decision-states')).toHaveText('Execution: not executed · Outcome: not observed')
  await box.getByRole('button', { name: /Done/ }).click()
  await expect(page.getByTestId('feed').locator('[data-card-line=RECOMMENDED_ACTION]')).toHaveCount(0)
  await expect(page.getByTestId('tab-reviewed')).toHaveText('Reviewed (1)')

  for (const step of ['refresh', 'restart']) {
    if (step === 'restart') await server.restart()
    await page.reload()
    const resolved = await reviewedTab(page)
    await expect(resolved.getByTestId('lifecycle-status')).toHaveText('Approved — execution not recorded')
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
  await expect(box.locator('header')).toContainText('High severity') // the card's assessment is not rewritten
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
  await details(box, 'Action & draft')
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
  const [a, b] = [await browser.newPage(), await browser.newPage()] // two tabs of the same team lead's session
  for (const p of [a, b]) {
    await p.goto(`${server.url}/#run=${FIXTURE}`)
    await expect(p.getByTestId('session-user')).toContainText('Priya')
    await cardBox(p, card.topic_name).getByRole('button', { name: 'Approve…' }).click()
  }
  await cardBox(a, card.topic_name).getByTestId('save-decision').click()
  await expect(cardBox(a, card.topic_name).getByTestId('save-success')).toBeVisible()
  const boxB = cardBox(b, card.topic_name)
  await boxB.getByTestId('save-decision').click()
  await expect(boxB.getByTestId('save-conflict')).toContainText('by U006')
  await boxB.getByRole('button', { name: 'Show the latest decision' }).click()
  const resolved = await reviewedTab(b)
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
  await details(box, 'All evidence')
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
  await details(audio, 'Sources & threads')
  await audio.getByTestId('thread-link').first().click()
  const thread = page.getByTestId('thread-detail')
  await expect(thread.getByTestId('permalink-note')).toContainText('No Slack permalink is stored')
  // The smoke run predates the fixture fingerprint: the thread is labelled current fixture content, apart from saved evidence.
  await expect(thread.getByTestId('fixture-status')).toHaveAttribute('data-status', 'NOT_RECORDED')
  await expect(thread.getByTestId('fixture-status')).toContainText('separate from the run\'s saved evidence')
  await expect(thread.getByTestId('thread-message').first()).toContainText('matches saved evidence')
  expect(page.url()).toContain('panel=thread')
  await page.reload() // deep link reopens the same view
  await expect(page.getByTestId('thread-detail')).toBeVisible()
  await page.getByRole('button', { name: 'Close' }).click()
  await details(audio, 'Sources & threads') // the reload collapsed the card
  await audio.getByTestId('source-link').first().click()
  await expect(page.getByTestId('evidence-detail')).toContainText('saved evidence')
})

test('failed, incomplete, scripted and fixture runs are labelled and never merged', async ({ page }) => {
  server = await startServer('runs')
  await open(page, SMOKE, '&debug=1') // run identity and accounting are developer details
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'LIVE')
  await expect(page.getByTestId('saved-counts')).toContainText('out of scope 85')
  await expect(page.getByTestId('semantic-source').first()).toHaveText('Live model')

  await page.getByTestId('run-select').selectOption(V1)
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'SCRIPTED')
  await expect(page.getByTestId('run-banner')).toContainText('Scripted run, not model output')
  await expect(page.getByTestId('run-status')).toHaveText('complete with failures')
  await expect(page.getByTestId('shared-run-id')).toContainText(`Another directory (${V2}) has the same run ID`)
  await expect(page.getByTestId('saved-counts')).toContainText('Failed topics 1')
  await expect(page.getByTestId('processing-health')).toContainText('1 failed')
  await expect(page.getByTestId('incomplete-work')).toContainText('topic failed')
  await page.getByTestId('topics-details').locator('summary').click()
  await expect(page.locator('[data-testid=topic-row][data-outcome=TOPIC_FAILED]')).toHaveCount(1)
  await expect(page.getByText('Scripted placeholder (nothing judged)').first()).toBeVisible()
  await expect(page.getByText('Scripted (prepared judgments)').first()).toBeVisible()

  await page.getByTestId('run-select').selectOption(FIXTURE)
  await expect(page.getByTestId('run-banner')).toHaveAttribute('data-mode', 'TEST_FIXTURE')
  await expect(page.getByTestId('run-status')).toHaveText('incomplete')
  await expect(page.getByTestId('saved-counts')).toContainText('unprocessed 1')
  await expect(page.getByTestId('incomplete-work')).toContainText('unprocessed budget')
  await expect(page.getByTestId('semantic-source').first()).toHaveText('Test fixture (hand-written)')
  // Project filter narrows this run only; other runs' cards never appear.
  await page.getByTestId('project-select').selectOption('audio_multimodal')
  await expect(page.getByTestId('card')).toHaveCount(1)
  await expect(page.getByTestId('feed').locator('[data-card-line=OBSERVATION]')).toContainText('No action needed now')
  await expect(page.getByTestId('visible-count')).toHaveText('Showing 1 of 3 active cards · audio_multimodal')
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
  const snapshotArgs = ['scripts/build_decision_snapshot.py', '--cutoff', cutoff, '--index-dir', `${server.dir}/snapshot`,
    '--export-dir', `${server.dir}/exports`, '--decision-db', server.db]
  // A decision on the hand-written fixture run is UI test data: excluded from default (operational) snapshots.
  const plan = JSON.parse(run(snapshotArgs))
  expect([plan.would_include, plan.excluded_by_namespace]).toEqual([0, 1])
  const built = JSON.parse(run([...snapshotArgs, '--namespace', 'test', '--build']))
  expect(built.decisions_indexed).toBe(1)
  expect(built.decisions_after_cutoff).toEqual([])
  await page.reload()
  const resolved = await reviewedTab(page)
  await expect(resolved.getByTestId('indexing-status')).toContainText('in snapshot')
  const found = JSON.parse(run(['-c', `
import json, sys
from threadsense.retrieval.search import Retriever
r = Retriever(sys.argv[1]).search('team lead approved reminder made-up phone number fictional story', 'safety_classification', top_k=10)
print(json.dumps([{k: x['metadata'][k] for k in ('origin', 'decision_status', 'execution_status', 'outcome_status')} for x in r['results']]))
`, `${server.dir}/snapshot`]).trim().split('\n').at(-1))
  expect(found).toContainEqual({ origin: 'tl_decision_store', decision_status: 'tl_approved', execution_status: 'not_executed', outcome_status: 'not_observed' })
})

test('two runs with the same run_id and card_id keep separate decisions, also after restart', async ({ page }) => {
  server = await startServer('isolation')
  const runs = (await server.api('/api/runs')).runs
  const [v1, v2] = [runs.find(r => r.run_key === V1), runs.find(r => r.run_key === V2)]
  expect(v1.run_id).toBe(v2.run_id)
  expect(v1.run_instance).not.toBe(v2.run_instance)
  const card = await cardId(V1, c => c.topic_name === 'LT response-fetch failure on safety tasks')
  expect((await server.api(`/api/runs/${V2}/brief`)).cards.some(c => c.card.card_id === card.card_id)).toBe(true)
  await open(page, V1, `&project=${card.project_id}`)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await box.getByLabel('Dismiss').check()
  await box.locator('textarea[name=note]').fill('Handled in the engineering thread.')
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toBeVisible()
  for (const step of ['now', 'restart']) {
    if (step === 'restart') await server.restart()
    await open(page, V2, `&project=${card.project_id}`)
    await expect(page.getByTestId('feed').locator(`[data-card-id="${card.card_id}"]`)).toHaveAttribute('data-card-line', 'NEEDS_REVIEW')
    await expect(page.getByTestId('tab-reviewed')).toHaveText('Reviewed (0)')
    expect(await decisionsFor(V2, card.card_id)).toEqual([])
    expect((await decisionsFor(V1, card.card_id)).map(d => [d.kind, d.run_instance])).toEqual([['DISMISS', v1.run_instance]])
  }
})

test('the session is locked to one team lead: no identity switch, other IDs refused', async ({ page }) => {
  server = await startServer('session')
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  await open(page, FIXTURE)
  await expect(page.getByTestId('actor-select')).toHaveCount(0)
  await expect(page.getByTestId('session-user')).toContainText('U006')
  const listing = await server.api('/api/runs')
  expect(listing.actors.map(a => a.actor_id)).toEqual(['U006'])
  const status = await page.evaluate(async url => (await fetch(url, { method: 'POST', body: JSON.stringify({ kind: 'APPROVE_ACTION', actor_id: 'U001' }),
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'ui-test-session-1' } })).status, `${server.url}/api/runs/${FIXTURE}/cards/${card.card_id}/decisions`)
  expect(status).toBe(403)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Approve…' }).click()
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toBeVisible()
  expect((await decisionsFor(FIXTURE)).map(d => d.actor_id)).toEqual(['U006'])
})

test('closed cards are easy to scan; an opened card leads with what to check, without opening Technical', async ({ page }) => {
  server = await startServer('what-to-check')
  const SMOKE_PLAYBACK = 'card_bd0a25b5720e9f5c55945f96f92f4783'

  // Closed: topic, severity, status, the whole saved summary and instruction; no reasons, notes or prompt metadata.
  const submit = await cardId(ROUTING, c => c.topic_name.startsWith('Unassigned members'))
  await open(page, ROUTING)
  let box = cardBox(page, submit.topic_name)
  await expect(box.getByTestId('card-summary')).toHaveText(submit.summary)
  const instruction = box.getByTestId('action-instruction')
  await expect(instruction).toHaveText(submit.recommended_action.instruction)
  expect(await instruction.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true)
  await expect(box.getByTestId('action-box').getByRole('button', { name: 'Copy draft' })).toBeVisible()
  for (const id of ['what-to-check', 'what-to-review', 'advisor-review-note', 'card-provenance']) await expect(box.getByTestId(id)).toHaveCount(0)
  await expect(box).not.toContainText('reasons from the final checks')
  await expect(page.getByTestId('run-provenance')).toHaveCount(0) // prompt metadata only under developer details
  await expect(box.getByTestId('card-topic')).toHaveText('Threads awaiting a topic') // projection gap: fallback title

  // Opened Submit: the escalation stays at the top; flags lead the checks; no boilerplate.
  await box.getByTestId('card-expand').click()
  const checks = box.getByTestId('what-to-check')
  await expect(box.getByTestId('action-box')).toBeVisible()
  await expect(checks.getByTestId('check').first()).toHaveAttribute('data-kind', 'FLAG')
  await expect(checks).toContainText('passed the evidence check')
  for (const boilerplate of ['Concerns:', 'from the final checks', 'severity-rubric', 'final evidence check supported', 'review this card'])
    await expect(checks).not.toContainText(boilerplate)
  await expect(box.getByTestId('all-reasons')).not.toHaveAttribute('open', '')
  // Flag provenance: the upstream dispute is shown, not the failed revision; the projection gap is described apart.
  await expect(checks.locator('[data-kind=FLAG]').filter({ hasText: 'Topic grouping needs review' })).toHaveCount(1)
  await box.getByTestId('all-reasons').locator(':scope > summary').click()
  const review = box.getByTestId('what-to-review')
  await expect(review).toContainText('2 earlier review flags are still open; topic grouping needs review')
  await expect(review.getByTestId('upstream-finding').first()).toContainText('What the upstream check disputed')
  await box.getByTestId('all-reasons').locator(':scope > summary').click()
  await box.getByRole('tab', { name: 'Technical' }).click()
  await expect(box.getByTestId('saved-title')).toContainText(submit.topic_name) // the saved label is kept here
  await box.getByRole('tab', { name: 'Action & draft' }).click()
  await checks.getByTestId('check-link').filter({ hasText: 'Open its Model Review Queue item' }).first().click()
  await expect(page.locator('[data-testid=review-item][data-focused]')).toHaveCount(1)

  // Opened smoke playback (the reload-workaround card): the saved question leads, once; withheld named, not shown.
  await open(page, SMOKE)
  box = page.locator(`[data-testid=card][data-card-id=${SMOKE_PLAYBACK}]`)
  await box.getByTestId('card-expand').click()
  const first = box.getByTestId('check').first()
  await expect(first).toHaveAttribute('data-kind', 'QUESTION')
  await expect(first.getByTestId('check-text')).toHaveAttribute('data-origin', 'SAVED')
  await expect(first.getByTestId('check-text')).toHaveText('Does the earlier reload trial apply to the current symptoms, and what observed outcome or later decision supports using it now?')
  await expect(first.getByTestId('check-related')).toContainText('did not find a recorded answer on earlier decisions')
  await expect(first.getByTestId('check-note')).toContainText('do not establish that a current reporter attempted a workaround')
  await expect(box.getByTestId('what-to-check').getByText('Does the earlier reload trial apply', { exact: false })).toHaveCount(1)
  await expect(box.getByTestId('what-to-check').locator('[data-kind=GAP]')).toHaveCount(0) // folded into the question
  const withheld = box.getByTestId('what-to-check').locator('[data-testid=check][data-kind=WITHHELD]')
  await expect(withheld).toContainText('How an announcement applies to this topic: not shown')
  await withheld.getByTestId('check-link').click()
  await expect(page.getByTestId('evidence-detail')).toBeVisible()
  await page.keyboard.press('Escape')
  await first.getByTestId('check-link').filter({ hasText: 'View the record' }).click()
  await expect(page.getByTestId('evidence-detail')).toContainText('Approve a limited playback trial')
  await page.keyboard.press('Escape')
  // Every original reason is still one click away; Technical was never opened.
  await box.getByTestId('all-reasons').locator(':scope > summary').click()
  await expect(box.getByTestId('what-to-review').getByTestId('review-item-reason')).toHaveCount(5)
  await expect(box.getByRole('tab', { name: 'Technical', selected: true })).toHaveCount(0)
})

// AdviceCard v4 (prepared fixture run, not model output) and a v3 card whose state is derived from its saved result.
const PREPARED = 'agent3_presentation_prepared_v1'
test('closed cards state the next step; opened cards explain what happened and why, and v3 cards stay as saved', async ({ page }) => {
  server = await startServer('presentation')
  await open(page, PREPARED)
  const ties = cardBox(page, 'Tie judgments when differences are only cosmetic')
  await expect(ties).toHaveAttribute('data-card-line', 'NEEDS_REVIEW')
  await expect(ties.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  await expect(ties.getByTestId('action-box')).toHaveCount(0)
  await expect(ties.getByTestId('what-happened')).toHaveCount(0) // closed
  await details(ties)
  await expect(ties.getByTestId('detail-sentence')).toHaveCount(3)
  await expect(ties.getByTestId('why-next-step')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  await expect(ties.getByTestId('next-step-rationale')).toContainText('do not establish a remaining handling question')
  await expect(ties.getByTestId('what-to-check')).toBeVisible() // the failed severity assessment still needs review
  const submit = page.locator('[data-testid=card][data-topic-name^="Unassigned members of routed_440e64c7fbdcc49f"]')
  await expect(submit.getByTestId('action-box')).toBeVisible()
  await details(submit)
  await expect(submit.getByTestId('detail-sentence')).toHaveCount(4) // sentence 4 unsupported, 5 withheld with it
  await expect(submit.getByTestId('detail-sentence').filter({ hasText: 'validation fault' })).toHaveCount(0)
  await expect(submit.getByTestId('why-next-step')).toContainText('Why this next step')
  await expect(submit.getByTestId('action-scope')).toContainText('Applies only as stated')
  const greet = cardBox(page, 'Language-day social greetings')
  await expect(greet.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  await details(greet)
  await expect(greet.getByTestId('no-details')).toBeVisible()

  const before = await server.api(`/api/runs/${ROUTING}/brief`)
  await open(page, ROUTING)
  const legacy = page.getByTestId('card').first()
  const id = await legacy.getAttribute('data-card-id')
  const saved = before.cards.find(c => c.card.card_id === id)
  expect(saved.card.contract_version).toBe('agent3-advice-card-v3')
  await expect(legacy.getByTestId('card-summary')).toHaveText(saved.card.summary)
  await details(legacy)
  await expect(legacy.getByTestId('what-happened')).toHaveAttribute('data-source', 'SAVED_REASONING')
  await expect(legacy.getByTestId('next-step-derived')).toBeVisible()
})

test('approval moves the card to Reviewed; its model-review item stays open; counts follow the saved records', async ({ page }) => {
  server = await startServer('lifecycle')
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  await open(page, FIXTURE)
  await expect(page.getByTestId('stat-awaiting')).toContainText('2')
  await expect(page.getByTestId('quick-PENDING_ACTIONS')).toContainText('1')
  await expect(page.getByTestId('stat-model-review')).toContainText('4')
  const box = cardBox(page, card.topic_name)
  await expect(box.getByTestId('open-obligations')).toHaveText('1 model-review item open')
  await box.getByRole('button', { name: 'Approve…' }).click()
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toBeVisible()
  await expect(page.getByTestId('feed').locator(`[data-card-id="${card.card_id}"]`)).toHaveCount(1) // stays until Done
  await box.getByRole('button', { name: 'Done (move to Reviewed)' }).click()
  await expect(page.getByTestId('feed').locator(`[data-card-id="${card.card_id}"]`)).toHaveCount(0)
  await expect(page.getByTestId('stat-awaiting')).toContainText('1')
  await expect(page.getByTestId('stat-awaiting')).toContainText('incl. 0 pending actions')
  await expect(page.getByTestId('stat-reviewed')).toContainText('1')
  await expect(page.getByTestId('tab-active')).toHaveText('Active (2)')
  await expect(page.getByTestId('stat-model-review')).toContainText('4') // approval clears no model-review obligation
  const reviewed = await reviewedTab(page)
  const done = cardBox(reviewed, card.topic_name)
  await expect(done.getByTestId('lifecycle-status')).toHaveText('Approved — execution not recorded')
  await expect(done.getByTestId('lifecycle-status')).not.toContainText(/resolved/i)
  await expect(done.getByTestId('open-obligations')).toHaveText('1 model-review item open')
  await expect(page.getByTestId('reviewed-note')).toContainText('nothing here is marked done or resolved')
  await done.getByTestId('open-obligations').click()
  await expect(page.getByTestId('tab-queue')).toHaveAttribute('aria-current', 'page')
  const states = (await server.api(`/api/runs/${FIXTURE}/review-queue`)).items
  expect(states.filter(i => i.item.related_card_ids.includes(card.card_id)).map(i => i.review_state)).toEqual(['OPEN'])
})

test('a failed refresh after saving keeps the card on screen and says so', async ({ page }) => {
  server = await startServer('refresh-failure')
  const card = await cardId(FIXTURE, c => c.card_line === 'RECOMMENDED_ACTION')
  await open(page, FIXTURE)
  const box = cardBox(page, card.topic_name)
  await box.getByRole('button', { name: 'Approve…' }).click()
  await box.getByTestId('save-decision').click()
  await expect(box.getByTestId('save-success')).toBeVisible()
  await page.route('**/decisions', route => (route.request().method() === 'GET' ? route.abort('connectionreset') : route.continue()))
  await box.getByRole('button', { name: 'Done (move to Reviewed)' }).click()
  await expect(page.getByTestId('sync-error')).toContainText('last confirmed state')
  await expect(page.getByTestId('feed').locator(`[data-card-id="${card.card_id}"]`)).toHaveCount(1)
  await page.unroute('**/decisions')
  await page.getByTestId('sync-error').getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByTestId('sync-error')).toHaveCount(0)
  await expect(page.getByTestId('tab-reviewed')).toHaveText('Reviewed (1)')
})

test('sort and filter controls use structured fields; narrow screens get a drawer', async ({ page }) => {
  server = await startServer('layout')
  await open(page, FIXTURE)
  // Presentation view: no run identity or accounting dump until developer details are switched on.
  for (const id of ['dev-panel', 'run-identity', 'processing-health', 'run-provenance']) await expect(page.getByTestId(id)).toHaveCount(0)
  await page.getByTestId('debug-toggle').click()
  await expect(page.getByTestId('dev-panel')).toContainText('fixture_dashboard_states_v1')
  await expect(page).toHaveURL(/debug=1/)
  await page.getByTestId('debug-toggle').click()
  await expect(page.getByTestId('dev-panel')).toHaveCount(0)
  // Dropdown options use the dark theme with light text.
  const [bg, fg] = await page.getByTestId('sort-select').locator('option').first().evaluate(o => [getComputedStyle(o).backgroundColor, getComputedStyle(o).color])
  expect([bg, fg]).toEqual(['rgb(26, 42, 56)', 'rgb(226, 232, 240)'])
  const order = () => page.getByTestId('feed').getByTestId('card').evaluateAll(els => els.map(e => e.dataset.cardLine))
  // Default: MEDIUM review card, then the two LOW cards (newest source activity first).
  expect(await order()).toEqual(['NEEDS_REVIEW', 'RECOMMENDED_ACTION', 'OBSERVATION'])
  await page.getByTestId('sort-select').selectOption('activity')
  const stamps = await page.getByTestId('feed').getByTestId('card-activity').allTextContents()
  expect(stamps.every(t => t.startsWith('Latest source message'))).toBe(true)
  expect([...stamps].sort().reverse()).toEqual(stamps)
  await page.getByTestId('quick-OBSERVATIONS').click()
  await expect(page.getByTestId('feed').getByTestId('card')).toHaveCount(1)
  expect(await order()).toEqual(['OBSERVATION'])
  await expect(page).toHaveURL(/filter=OBSERVATIONS/)
  await expect(page).toHaveURL(/sort=activity/)

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByTestId('sidebar')).toBeHidden()
  await page.getByTestId('menu-button').click()
  await expect(page.getByTestId('sidebar')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Close the briefing menu' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('sidebar')).toBeHidden()
  await expect(page.getByTestId('menu-button')).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
})
