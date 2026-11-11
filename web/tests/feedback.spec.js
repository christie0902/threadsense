// Human-feedback loop in the real dashboard: report a verifier false rejection on a saved card, confirm it, reload,
// and see the workflow counts. No model calls; the store is a fresh file outside the repository.
import { expect, test } from '@playwright/test'
import { sha256, startServer } from './server.js'

const RUN = 'threadsense_full_v1_briefing_v2', CARD = 'card_4e2b000dc32802a991cfcb24432507a6'
const FILES = ['cards.json', 'morning_brief.json', 'review_queue.json'].map(f => `data/experiments/${RUN}/${f}`)
let server

test.afterEach(async () => { await server?.stop() })

async function openCard(page) {
  await page.goto(`${server.url}/#run=${RUN}`)
  await page.reload()
  const card = page.locator(`[data-testid=card][data-card-id=${CARD}]`)
  await card.scrollIntoViewIfNeeded()
  await card.getByTestId('card-expand').click()
  await expect(card.getByTestId('ai-feedback')).toBeVisible()
  return card
}

test('report an AI issue, confirm it, and keep it across a reload', async ({ page }) => {
  const before = FILES.map(sha256)
  server = await startServer('feedback', ['--runs', 'data/experiments'])
  let card = await openCard(page)
  await card.getByTestId('report-ai-issue').locator('summary').click()
  await card.getByTestId('feedback-category').selectOption('VERIFIER_FALSE_REJECTION')
  await card.getByTestId('feedback-target').selectOption('STATEMENT:claim:c1')
  await card.getByTestId('feedback-wrong').fill('The author-count check rejected this, but the "two people" are the speakers in the audio, not Slack reporters.')
  const future = card.getByTestId('feedback-future')
  await expect(future).toBeDisabled() // No correction yet: future use cannot be chosen.
  await card.getByTestId('feedback-correction').fill('One QA tutor asked about two speakers talking at once; do not count speakers in the audio as reporters.')
  await expect(future).toBeEnabled()
  await future.check()
  await card.getByTestId('feedback-submit').click()
  await expect(card.getByTestId('feedback-saved')).toBeVisible()
  const entry = card.getByTestId('feedback-entry')
  await expect(entry).toHaveAttribute('data-state', 'SUBMITTED')
  await expect(entry.getByTestId('feedback-eligibility')).toHaveText('Awaiting confirmation by a team lead.')
  await entry.getByTestId('feedback-confirm').click()
  await expect(entry).toHaveAttribute('data-state', 'CONFIRMED')
  await expect(entry.getByTestId('feedback-eligibility')).toContainText('Eligible for future runs')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/feedback-card.png` })

  await server.restart() // Persisted: a new server process over the same store shows the same history.
  card = await openCard(page)
  await expect(card.getByTestId('feedback-entry')).toHaveAttribute('data-state', 'CONFIRMED')
  await expect(card.getByTestId('feedback-events')).toContainText('confirmed')
  await page.getByTestId('header-queue').click()
  await expect(page.getByTestId('feedback-counts')).toContainText('1 report · 1 confirmed · 1 eligible for future runs · 0 reviewer corrections used by this run')
  // Agree / Reject / Defer stay as they were and record no AI feedback.
  await page.getByTestId('review-item').first().getByTestId('review-defer').click()
  await expect(page.getByTestId('review-saved')).toBeVisible()
  expect((await server.api(`/api/runs/${RUN}/feedback`)).counts.submitted).toBe(1)
  expect(FILES.map(sha256)).toEqual(before) // Run artifacts unchanged.
})

test('reject with a lesson for future runs, then deactivate and edit it', async ({ page }) => {
  server = await startServer('lessons', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=${RUN}&tab=queue`)
  await page.reload()
  await page.getByTestId('header-queue').click()
  const item = page.getByTestId('review-item').first()
  await item.getByTestId('lesson-fields').locator('summary').click()
  await item.getByTestId('lesson-text').fill('People heard speaking in an audio clip are not the people reporting in Slack.')
  await item.getByTestId('lesson-category').selectOption('SUMMARY')
  await expect(item.getByTestId('lesson-scope')).toHaveValue('PROJECT') // project-specific unless chosen otherwise
  await expect(item.getByTestId('lesson-pending')).toBeVisible()
  const itemId = await item.getAttribute('data-item-id')
  await item.getByTestId('review-reject').click()
  const saved = page.locator(`[data-testid=review-item][data-item-id="${itemId}"]`)
  await page.getByTestId('review-queue').getByRole('button', { name: /^all/i }).click()
  await expect(saved.getByTestId('review-state')).toHaveText('rejected')
  await expect(saved.getByTestId('lesson-entry')).toHaveAttribute('data-state', 'ACTIVE')
  await saved.getByTestId('lesson-toggle').click()
  await expect(saved.getByTestId('lesson-entry')).toHaveAttribute('data-state', 'INACTIVE')
  await saved.getByTestId('lesson-toggle').click()
  await expect(saved.getByTestId('lesson-entry')).toHaveAttribute('data-state', 'ACTIVE')
  await saved.getByTestId('lesson-edit').click()
  await saved.getByTestId('lesson-edit-text').fill('Speakers in a clip are not Slack reporters; count message authors only.')
  await saved.getByTestId('lesson-edit-save').click()
  await expect(saved.locator('[data-testid=lesson-entry][data-state=SUPERSEDED]')).toHaveCount(1)
  await expect(saved.locator('[data-testid=lesson-entry][data-state=ACTIVE]')).toContainText('count message authors only')
  const lessons = await server.api('/api/lessons')
  expect(lessons.counts).toEqual({ ACTIVE: 1, INACTIVE: 0, SUPERSEDED: 1 })
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/lessons-queue.png` })
})
