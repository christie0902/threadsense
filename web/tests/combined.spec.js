// Combined briefing (49 reused cards + 14 refreshed consolidated issues) in the real dashboard, plus the separately
// labelled Observation demo fixture. No model calls. Screenshots of the affected cards go to TS_UI_TMP.
import { expect, test } from '@playwright/test'
import { startServer } from './server.js'

const COMBINED = 'threadsense_full_v1_combined_v1'
let server

test.afterEach(async () => { await server?.stop() })

const cardBox = (scope, name) => scope.locator(`[data-testid=card][data-topic-name=${JSON.stringify(name)}]`)
// The active feed is one sorted list; a card's line is on the card itself.
const feedLine = (page, line) => page.getByTestId('feed').locator(`[data-testid=card][data-card-line=${line}]`)

async function open(page, name) {
  const box = cardBox(page, name)
  await box.getByTestId('card-expand').click()
  return box
}

test('combined briefing: counts, lineage and the revalidated cards', async ({ page }) => {
  server = await startServer('combined', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=${COMBINED}`)
  await page.reload()
  await expect(page.getByTestId('stat-in-brief')).toContainText('63')
  await expect(page.getByTestId('stat-in-brief')).toContainText('53 needs review · 7 recommended · 3 observation')
  await expect(page.getByTestId('stat-history')).toContainText('3 routine or social threads set aside')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/combined-overview.png` })

  // The three live observations, each with its supported no-action reason.
  const observations = feedLine(page, 'OBSERVATION')
  await expect(observations).toHaveCount(3)
  for (const box of await observations.all()) {
    await expect(box.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  await page.getByTestId('quick-OBSERVATIONS').click()
  await expect(page.getByTestId('feed').getByTestId('card')).toHaveCount(3)
  await page.getByTestId('feed').screenshot({ path: `${process.env.TS_UI_TMP}/combined-observations.png` })
  await page.getByTestId('quick-ALL').click()

  // Replaced cards appear only through the lineage of the issue that replaced them.
  await expect(cardBox(page, 'QN handling for fictional phone numbers')).toHaveCount(0)
  await expect(cardBox(page, 'Fictional placeholder contact details and QN handling')).toHaveCount(0)
  const fictional = await open(page, 'QN handling for fictional contact details')
  await expect(fictional.getByTestId('combined-badge')).toContainText('replaces 2 earlier cards')
  await fictional.getByTestId('combined-lineage').locator('summary').click()
  await expect(fictional.getByTestId('replaced-card')).toHaveCount(2)
  await expect(fictional.getByTestId('what-to-review')).toContainText('A documentation question is unresolved')
  await expect(fictional.getByTestId('what-to-review')).toContainText('October status note')
  await fictional.screenshot({ path: `${process.env.TS_UI_TMP}/combined-fictional-contact.png` })

  const business = await open(page, 'Public business contact details are not private PII')
  await expect(business.getByTestId('what-to-review')).not.toContainText('Sources disagree')
  await business.screenshot({ path: `${process.env.TS_UI_TMP}/combined-business-contact.png` })

  const overlap = await open(page, 'Overlapping speech in transcription')
  await expect(overlap.getByTestId('action-box')).toBeVisible()
  await expect(overlap.getByTestId('what-to-review')).toContainText('not been checked against the evidence yet')
  await overlap.screenshot({ path: `${process.env.TS_UI_TMP}/combined-overlapping-speech.png` })

  const format = await open(page, 'Format compliance versus accuracy')
  await expect(format.getByTestId('next-step-status')).toHaveAttribute('data-status', 'RECOMMENDATION_WITHHELD')
  await format.screenshot({ path: `${process.env.TS_UI_TMP}/combined-format.png` })

  const older = await open(page, 'Older scoring guide screenshot versus newer pinned note')
  await expect(older.getByTestId('outstanding-label')).toHaveText('Pending follow-up')
  await expect(older.getByTestId('outstanding-step')).toHaveAttribute('data-kind', 'WAITING_ON_REQUESTED_STEP')
  await older.screenshot({ path: `${process.env.TS_UI_TMP}/combined-older-scoring.png` })
})

test('observation demo fixture: labelled, separate, two observations', async ({ page }) => {
  server = await startServer('observation-demo', ['--runs', 'tests/fixtures/observation_demo_runs'])
  await page.goto(`${server.url}/#run=observation_demo_fixture_v1`)
  await page.reload()
  await expect(page.getByTestId('run-banner')).toContainText(/test fixture/i)
  const observations = feedLine(page, 'OBSERVATION')
  await expect(observations).toHaveCount(2)
  for (const name of ['Unrequested markdown headers in plain-text answers', 'Slow waveform rendering on long clips (recovered)'])
    await expect(cardBox(page.getByTestId('feed'), name)).toHaveAttribute('data-card-line', 'OBSERVATION')
  for (const box of await observations.all()) {
    await expect(box.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  // Observations are identified and listed, but never counted as decisions or actions waiting.
  await expect(page.getByTestId('stat-awaiting')).toContainText('0')
  await expect(page.getByTestId('quick-PENDING_ACTIONS')).toContainText('0')
  await page.getByTestId('feed').screenshot({ path: `${process.env.TS_UI_TMP}/observation-demo.png` })
})

test('combined briefing v2 (demo baseline): targeted re-groundings, labels and the live observations', async ({ page }) => {
  server = await startServer('combined-v2', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=threadsense_full_v1_combined_v2&debug=1`)
  await page.reload()
  await expect(page.getByTestId('run-derivation')).toContainText('Combined offline (combined-briefing-v2) from 4 saved runs')
  // Statistics come from the briefing's active records: history, the queue and replaced card records are separate.
  await expect(page.getByTestId('stat-in-brief')).toContainText('63')
  await expect(page.getByTestId('stat-in-brief')).toContainText('52 needs review · 8 recommended · 3 observation')
  await expect(page.getByTestId('stat-mismatch')).toHaveCount(0) // agrees with the saved presentation totals
  await expect(page.getByTestId('stat-history')).toContainText('3 routine or social threads set aside; 29 earlier cards merged into combined issues')
  await expect(page.getByTestId('stat-model-review')).toContainText('37')
  await expect(page.getByTestId('stat-awaiting')).toContainText('60')
  await expect(page.getByTestId('stat-awaiting')).toContainText('incl. 8 pending actions to approve')
  await expect(page.getByTestId('tab-active')).toHaveText('Active (63)')
  await expect(page.getByTestId('tab-reviewed')).toHaveText('Reviewed (0)')
  await expect(page.getByTestId('visible-count')).toHaveText('Showing 63 of 63 active cards')
  await expect(page.getByTestId('briefing-eyebrow')).toHaveText('Morning briefing') // run kind: briefing selector and developer details
  await expect(page.getByTestId('run-banner')).not.toContainText('Live run')
  await expect(page.getByTestId('briefing-date')).toHaveText('Fri, 2 Oct 2026')
  await expect(page.getByTestId('source-window')).toContainText('2026-10-01 12:00 UTC to 2026-10-02 12:00 UTC')
  await expect(page.getByTestId('generated-at')).toHaveText('Generated: not recorded in this run')
  // Accounting covers the 177 members handed to advice; the 178th discussion thread is shown as outside it.
  await expect(page.getByTestId('health-accounting')).toContainText('complete for the 177 discussion members handed to advice')
  await expect(page.getByTestId('health-gap')).toContainText('178 discussion threads were in the window; 1 is outside this accounting')
  await expect(page.locator('body')).not.toContainText(/auto-resolved/i)
  // Default order: severity ranks never go back up the list, and unassessed cards come after every assessed one.
  const levels = await page.getByTestId('feed').getByTestId('severity').evaluateAll(els => els.map(e => e.dataset.level))
  const rank = { HIGH: 0, MEDIUM: 1, LOW: 2, 'N/A': 3, UNASSESSED: 4 }
  expect(levels).toHaveLength(63)
  expect(levels.map(l => rank[l])).toEqual([...levels.map(l => rank[l])].sort((a, b) => a - b))
  expect(levels.filter(l => l === 'UNASSESSED')).toHaveLength(7)
  await expect(page.getByTestId('feed').getByTestId('severity').filter({ hasText: 'Severity unassessed' })).toHaveCount(7)
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/v2-overview.png` })
  // Pending actions: the 8 approvable recommendations only.
  await page.getByTestId('quick-PENDING_ACTIONS').click()
  await expect(page.getByTestId('feed').getByTestId('card')).toHaveCount(8)
  await expect(page.getByTestId('feed').locator('[data-testid=card]:not([data-card-line=RECOMMENDED_ACTION])')).toHaveCount(0)
  await expect(page.getByTestId('active-filter')).toHaveText('Pending actions')
  await page.getByTestId('active-filter').click()
  const costs = page.getByTestId('stage-costs')
  await costs.locator('summary').click()
  await expect(costs.getByTestId('stage-cost')).toHaveCount(4)
  await expect(costs).toContainText('$2.2280')
  await expect(costs).toContainText('$0.094 (as reported)')
  await expect(costs).toContainText('$0.0000')
  await costs.screenshot({ path: `${process.env.TS_UI_TMP}/v2-stage-costs.png` })
  const saved = page.getByTestId('briefing-details')
  await saved.locator('summary').click()
  await expect(saved).toContainText('63 active cards covering 174 threads')
  await expect(saved).not.toContainText('95 cards (')

  const observations = feedLine(page, 'OBSERVATION')
  await expect(observations).toHaveCount(3)
  for (const name of ['Suggestive vs explicit content boundary', 'Queue coverage and closure reminders', 'Work environment and background noise']) {
    await expect(cardBox(page.getByTestId('feed'), name)).toHaveAttribute('data-card-line', 'OBSERVATION')
    await expect(cardBox(page.getByTestId('feed'), name).getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  await page.getByTestId('quick-OBSERVATIONS').click()
  await page.getByTestId('feed').screenshot({ path: `${process.env.TS_UI_TMP}/v2-observations.png` })
  await page.getByTestId('quick-ALL').click()

  const overlap = await open(page, 'Overlapping speech in transcription')
  await expect(overlap.getByTestId('action-box')).toBeVisible()
  await expect(overlap.getByTestId('what-to-review')).toContainText(/flag/i)
  await expect(overlap.getByTestId('what-to-review')).not.toContainText('not been checked against the evidence yet')
  await overlap.screenshot({ path: `${process.env.TS_UI_TMP}/v2-overlapping-speech.png` })

  const format = cardBox(page.getByTestId('feed'), 'Format compliance versus accuracy')
  await expect(format).toHaveAttribute('data-card-line', 'RECOMMENDED_ACTION')
  await format.getByTestId('card-expand').click()
  await expect(format.getByTestId('action-box')).toBeVisible()
  await expect(format.getByTestId('human-edit')).toHaveCount(3)
  await expect(format.getByTestId('human-edits')).toContainText('verified by the live model')
  await expect(format.getByTestId('posting-suggestion')).toHaveCount(2)
  await expect(format.getByTestId('posting-suggestions')).toContainText('10:21 UTC batch status note')
  await expect(format.getByTestId('action-box')).not.toContainText('status note')  // suggestions stay out of the copyable draft
  await format.getByTestId('posting-source').click()
  await expect(page.getByTestId('side-panel')).toContainText('factuality versus instruction adherence')
  await page.keyboard.press('Escape')
  await format.screenshot({ path: `${process.env.TS_UI_TMP}/v2-format.png` })

  const nsfw = await open(page, 'NSFW suggestive-content threshold')
  await expect(nsfw.getByTestId('choice')).toContainText('Choose a next step (2 options)')
  await expect(nsfw.getByTestId('choice-option')).toHaveCount(2)
  await expect(nsfw.getByTestId('alternatives-heading')).toHaveText('Closely matched options (none preferred)')
  await nsfw.screenshot({ path: `${process.env.TS_UI_TMP}/v2-nsfw-choice.png` })

  const qn = await open(page, 'QN handling for fictional contact details')
  await expect(qn.getByTestId('editorial-note')).toContainText('Confirm before editing')
  await expect(qn.getByTestId('editorial-note')).toContainText('not established')
  await qn.screenshot({ path: `${process.env.TS_UI_TMP}/v2-fictional-contact.png` })

  const queue = cardBox(page.getByTestId('feed'), 'Queue coverage and closure reminders')
  await expect(queue.getByTestId('editorial-note')).toContainText('Timing unconfirmed')
  await queue.screenshot({ path: `${process.env.TS_UI_TMP}/v2-queue-coverage.png` })
})

test('presentation view: no developer banner, Triage, and the slides layout over the whole briefing', async ({ page }) => {
  server = await startServer('slides', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/`)
  await expect(page.getByTestId('run-select')).toHaveValue('threadsense_full_v1_combined_v2') // default: the presentation briefing
  await expect(page.getByTestId('agent-name')).toHaveText('Triage')
  await expect(page.getByTestId('run-banner')).toHaveCount(0)
  await expect(page.getByTestId('briefing-eyebrow')).toHaveText('Morning briefing') // no run-kind label in the presentation header
  await expect(page.getByTestId('stat-history')).not.toContainText(/lineage|processing history/)
  await page.getByTestId('view-slides').click()
  await expect(page).toHaveURL(/view=slides/)
  const feed = page.getByTestId('feed')
  await expect(feed.getByTestId('card')).toHaveCount(1)
  await expect(page.getByTestId('slide-position')).toHaveText('Card 1 of 63')
  await expect(page.getByTestId('slide-prev')).toBeDisabled()
  await expect(feed.locator('[data-testid=slide-preview][data-side=next]')).toBeVisible()
  const first = await feed.getByTestId('card').getAttribute('data-card-id')
  await page.getByTestId('slide-next').click()
  await expect(page.getByTestId('slide-position')).toHaveText('Card 2 of 63')
  await expect(feed.getByTestId('card')).not.toHaveAttribute('data-card-id', first)
  await page.getByTestId('card-slider').focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByTestId('slide-position')).toHaveText('Card 3 of 63')
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByTestId('slide-position')).toHaveText('Card 2 of 63')
  // Same order as the grid: the slides follow the sorted, filtered list.
  await page.getByTestId('quick-PENDING_ACTIONS').click()
  await expect(page.getByTestId('slide-position')).toHaveText('Card 1 of 8')
  await expect(feed.getByTestId('card')).toHaveAttribute('data-card-line', 'RECOMMENDED_ACTION')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/slides-desktop.png` })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByTestId('slide-next-compact')).toBeVisible()
  await page.getByTestId('slide-next-compact').click()
  await expect(page.getByTestId('slide-position')).toHaveText('Card 2 of 8')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
  await page.getByTestId('view-grid').click()
  await expect(feed.getByTestId('card')).toHaveCount(8)
})
