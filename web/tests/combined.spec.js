// Combined briefing (49 reused cards + 14 refreshed consolidated issues) in the real dashboard, plus the separately
// labelled Observation demo fixture. No model calls. Screenshots of the affected cards go to TS_UI_TMP.
import { expect, test } from '@playwright/test'
import { startServer } from './server.js'

const COMBINED = 'threadsense_full_v1_combined_v1'
let server

test.afterEach(async () => { await server?.stop() })

const cardBox = (scope, name) => scope.locator(`[data-testid=card][data-topic-name=${JSON.stringify(name)}]`)

async function open(page, name) {
  const box = cardBox(page, name)
  await box.getByTestId('card-expand').click()
  return box
}

test('combined briefing: counts, lineage and the revalidated cards', async ({ page }) => {
  server = await startServer('combined', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=${COMBINED}`)
  await page.reload()
  await expect(page.getByTestId('tile-in-brief')).toContainText('63 in this brief (14 combined issues) · 3 kept in history')
  await expect(page.getByTestId('tile-needs-review')).toContainText('53')
  await expect(page.getByTestId('tile-recommended')).toContainText('7')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/combined-overview.png` })

  // The three live observations, each with its supported no-action reason.
  const observations = page.getByTestId('active-OBSERVATION').getByTestId('card')
  await expect(observations).toHaveCount(3)
  for (const box of await observations.all()) {
    await expect(box.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  await page.getByTestId('group-OBSERVATION').screenshot({ path: `${process.env.TS_UI_TMP}/combined-observations.png` })

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
  const observations = page.getByTestId('active-OBSERVATION').getByTestId('card')
  await expect(observations).toHaveCount(2)
  await expect(page.getByTestId('active-OBSERVATION')).toContainText('Unrequested markdown headers in plain-text answers')
  await expect(page.getByTestId('active-OBSERVATION')).toContainText('Slow waveform rendering on long clips (recovered)')
  for (const box of await observations.all()) {
    await expect(box.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  await page.getByTestId('group-OBSERVATION').screenshot({ path: `${process.env.TS_UI_TMP}/observation-demo.png` })
})

test('combined briefing v2 (demo baseline): targeted re-groundings, labels and the live observations', async ({ page }) => {
  server = await startServer('combined-v2', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=threadsense_full_v1_combined_v2`)
  await page.reload()
  await expect(page.getByTestId('tile-in-brief')).toContainText('63 in this brief (14 combined issues) · 3 kept in history')
  await expect(page.getByTestId('tile-needs-review')).toContainText('52')
  await expect(page.getByTestId('tile-recommended')).toContainText('8')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/v2-overview.png` })

  const observations = page.getByTestId('active-OBSERVATION').getByTestId('card')
  await expect(observations).toHaveCount(3)
  for (const name of ['Suggestive vs explicit content boundary', 'Queue coverage and closure reminders', 'Work environment and background noise']) {
    await expect(cardBox(page.getByTestId('active-OBSERVATION'), name).getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
  }
  await page.getByTestId('group-OBSERVATION').screenshot({ path: `${process.env.TS_UI_TMP}/v2-observations.png` })

  const overlap = await open(page, 'Overlapping speech in transcription')
  await expect(overlap.getByTestId('action-box')).toBeVisible()
  await expect(overlap.getByTestId('what-to-review')).toContainText(/flag/i)
  await expect(overlap.getByTestId('what-to-review')).not.toContainText('not been checked against the evidence yet')
  await overlap.screenshot({ path: `${process.env.TS_UI_TMP}/v2-overlapping-speech.png` })

  const format = cardBox(page.getByTestId('group-RECOMMENDED_ACTION'), 'Format compliance versus accuracy')
  await format.getByTestId('card-expand').click()
  await expect(format.getByTestId('action-box')).toBeVisible()
  await expect(format.getByTestId('human-edit')).toHaveCount(3)
  await expect(format.getByTestId('human-edits')).toContainText('verified by the live model')
  await expect(format.getByTestId('tl-suggestion')).toContainText('not judged')
  await format.screenshot({ path: `${process.env.TS_UI_TMP}/v2-format.png` })
})
