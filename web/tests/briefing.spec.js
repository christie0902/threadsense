// briefing-routing-v2 in the real dashboard: the derived run of the full live run, and the original run beside it.
// No model calls. Screenshots of the corrected examples go to TS_UI_TMP.
import { expect, test } from '@playwright/test'
import { startServer } from './server.js'

const DERIVED = 'threadsense_full_v1_briefing_v2', ORIGINAL = 'overnight_run'
const ROOTS = ['--runs', 'data/experiments', '--runs', 'data/experiments/threadsense_full_v1/stages/agent3']
let server

test.afterEach(async () => { await server?.stop() })

const cardBox = (page, name) => page.locator(`[data-testid=card][data-topic-name=${JSON.stringify(name)}]`)
async function open(page, run) {
  await page.goto(`${server.url}/#run=${run}`)
  await page.reload()
  await expect(page.getByTestId('run-banner')).toBeVisible()
}
const shot = (page, name) => page.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-${name}.png`, fullPage: false })

test('derived brief: counts, outstanding steps and no contradictory observations', async ({ page }) => {
  server = await startServer('briefing', ROOTS)
  await open(page, DERIVED)
  await expect(page.getByTestId('run-derivation')).toContainText('briefing-routing-v2')
  const relevanceNote = page.getByTestId('run-derivation').getByText(/not from an automatic classifier/)
  await expect(relevanceNote).toBeHidden()  // processing detail stays folded
  await page.getByTestId('run-derivation').locator('summary').click()
  await expect(relevanceNote).toBeVisible()
  await expect(page.getByTestId('tile-needs-review')).toContainText('66')
  await expect(page.getByTestId('tile-recommended')).toContainText('8')
  await expect(page.getByTestId('tile-in-brief')).toContainText('77 in this brief · 4 kept in history')
  await expect(page.getByTestId('headline')).toContainText('3 observations to keep in view')
  await shot(page, 'overview')

  // Every observation in the brief has a supported no-action reason; none says withheld or no intervention.
  const observations = page.getByTestId('active-OBSERVATION').getByTestId('card')
  await expect(observations).toHaveCount(3)
  for (const box of await observations.all()) {
    await expect(box.getByTestId('next-step-status')).toHaveAttribute('data-status', 'NO_ACTION_NEEDED')
    await expect(box.getByTestId('no-decision')).toHaveText('Observations need no decision.')
  }
  await expect(page.getByTestId('group-OBSERVATION')).not.toContainText('Recommendation withheld')
  await expect(page.getByTestId('group-OBSERVATION')).not.toContainText('No intervention proposed')

  // The screenshot cases are back in review with their outstanding step.
  const korean = cardBox(page, 'Korean language QA edge cases')
  await expect(korean).toHaveAttribute('data-card-line', 'NEEDS_REVIEW')
  await expect(korean.getByTestId('next-step-status')).toHaveAttribute('data-status', 'RECOMMENDATION_WITHHELD')
  await expect(korean.getByTestId('outstanding-label')).toHaveText('Pending follow-up')
  await korean.scrollIntoViewIfNeeded()
  await korean.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-korean.png` })
  const vietnamese = cardBox(page, 'Regional vocabulary fit for target audience')
  await expect(vietnamese).toHaveAttribute('data-card-line', 'NEEDS_REVIEW')
  await expect(vietnamese.getByTestId('outstanding-step')).toContainText('does not confirm the audience')
  await expect(vietnamese.getByTestId('outstanding-step')).not.toContainText('judged supported')
  await vietnamese.getByTestId('card-expand').click()
  await expect(vietnamese.getByTestId('outstanding-detail')).toContainText('judged supported')
  await expect(vietnamese.getByTestId('outstanding-detail')).toContainText('team-lead request')
  // The pending follow-up text appears once, in the box, even with the card open.
  await expect(vietnamese.getByText(/does not confirm the audience/)).toHaveCount(1)
  await expect(vietnamese.getByTestId('next-step-explanation')).toBeVisible()
  await vietnamese.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-vietnamese-expanded.png` })
  const repeat = cardBox(page, 'Repeated ending phrase in generated answer')
  await expect(repeat.getByTestId('outstanding-label')).toHaveText('Pending follow-up')
  await expect(page.getByTestId('active-OBSERVATION')).toContainText('Queue coverage and closure reminders')
  await expect(page.getByTestId('active-OBSERVATION')).toContainText('Suggestive vs explicit content boundary')

  // Greetings are out of the brief's lists but kept, with their card, in history.
  await expect(page.getByTestId('active-OBSERVATION')).not.toContainText('Language-day greetings')
  const history = page.getByTestId('not-in-brief')
  await history.locator('summary').click()
  await expect(history.getByTestId('card')).toHaveCount(4)
  await expect(cardBox(page, 'Language-day greetings').getByTestId('history-badge')).toContainText('Not in this brief')
  await expect(page.getByTestId('active-OBSERVATION')).not.toContainText('Team avatar asset location')
  await expect(page.getByTestId('active-OBSERVATION')).not.toContainText('Tie threshold for near-identical responses')
  const avatar = cardBox(page, 'Team avatar asset location')
  await expect(avatar.getByTestId('history-badge')).toContainText('routine admin')
  await expect(avatar).toContainText(/partially resolved/i)
  await expect(avatar.getByTestId('outstanding-label')).toHaveText('Still open (no action needed now)')
  await avatar.getByTestId('card-expand').click()
  await expect(avatar.getByTestId('history-basis')).toContainText('Nothing was resolved or deleted')
  await avatar.scrollIntoViewIfNeeded()
  await avatar.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-avatar-history.png` })
  await avatar.getByTestId('card-collapse').click()
  await expect(cardBox(page, 'Language-day greetings').getByTestId('no-decision')).toContainText('kept in history')
  await history.scrollIntoViewIfNeeded()
  await history.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-history.png` })
})

test('original run stays available and flags its unsupported observations', async ({ page }) => {
  server = await startServer('briefing-original', ROOTS)
  await open(page, ORIGINAL)
  const korean = cardBox(page, 'Korean language QA edge cases')
  await expect(korean).toHaveAttribute('data-card-line', 'OBSERVATION')
  await expect(korean.getByTestId('unsupported-observation')).toBeVisible()
  await expect(korean.getByTestId('no-decision')).toContainText('No decision options on this card')
  await expect(korean).not.toContainText('Observations need no decision.')
  await korean.scrollIntoViewIfNeeded()
  await korean.screenshot({ path: `${process.env.TS_UI_TMP}/briefing-original-korean.png` })
  await expect(cardBox(page, 'Language-day greetings').getByTestId('no-decision')).toHaveText('Observations need no decision.')
})
