// Relevance and consolidation repair in the real dashboard: the derived run of the full live run. No model calls.
// Screenshots of the reviewed sections go to TS_UI_TMP.
import { expect, test } from '@playwright/test'
import { startServer } from './server.js'

const DERIVED = 'threadsense_full_v1_consolidated_v1'
let server

test.afterEach(async () => { await server?.stop() })

const cardBox = (scope, name) => scope.locator(`[data-testid=card][data-topic-name=${JSON.stringify(name)}]`)

test('consolidated issues, shared action and processing history', async ({ page }) => {
  server = await startServer('consolidation', ['--runs', 'data/experiments'])
  await page.goto(`${server.url}/#run=${DERIVED}`)
  await page.reload()
  await expect(page.getByTestId('run-banner')).toBeVisible()
  // 49 cards plus 14 consolidated issues awaiting fresh advice (their 29 original cards sit inside each issue).
  await expect(page.getByTestId('stat-in-brief')).toContainText('49')
  await expect(page.getByTestId('stat-consolidated')).toContainText('14')
  await expect(page.getByTestId('stat-consolidated')).toContainText('29 original cards kept inside')
  await expect(page.getByTestId('stat-history')).toContainText('3 processing history')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/consolidation-overview.png` })

  // One shared action for the duplicate Contact details edit; each card keeps its review reasons.
  const shared = page.getByTestId('shared-actions')
  await expect(shared.getByTestId('shared-action')).toHaveCount(1)
  await expect(shared).toContainText('safety-qn-help-page@1.0 · Contact details')
  await expect(shared).toContainText('does not mean the topics share a cause')
  await expect(shared.getByTestId('shared-action-card')).toHaveCount(2)
  await expect(shared).toContainText('still needs review: grounding failure, inherited flag')
  await expect(shared).toContainText('Not coordinated (proposal withheld): Conflicting QN guidance sources')
  await shared.screenshot({ path: `${process.env.TS_UI_TMP}/consolidation-shared-action.png` })

  // Consolidated issues are listed once; the original cards sit inside, attributed and unchanged.
  const issues = page.getByTestId('consolidated-issue')
  await expect(issues).toHaveCount(14)
  const contact = issues.filter({ hasText: 'QN handling for fictional contact details' })
  await contact.locator('summary').click()
  await expect(contact.getByTestId('consolidated-basis')).toContainText('belongs to each original topic')
  await expect(contact.getByTestId('card')).toHaveCount(2)
  const phone = cardBox(contact, 'QN handling for fictional phone numbers')
  await expect(phone.getByTestId('consolidated-badge')).toContainText('combined issue pending')
  await expect(phone.getByTestId('shared-action-note')).toContainText('Fictional placeholder contact details and QN handling')
  await expect(phone.getByTestId('action-box')).toBeVisible()  // the original advice stays readable
  await contact.screenshot({ path: `${process.env.TS_UI_TMP}/consolidation-contact-details.png` })
  // Merged source cards are not repeated in the main lists.
  await expect(cardBox(page.getByTestId('feed'), 'QN handling for fictional phone numbers')).toHaveCount(0)

  // Processing history: greetings and the avatar exchange, kept with their cards.
  const history = page.getByTestId('processing-history')
  await history.locator('summary').click()
  await expect(history.getByTestId('card')).toHaveCount(3)
  await expect(cardBox(history, 'Team avatar asset location').getByTestId('processing-badge')).toBeVisible()
  await expect(cardBox(page.getByTestId('feed'), 'Language-day greetings')).toHaveCount(0)
  await history.screenshot({ path: `${process.env.TS_UI_TMP}/consolidation-processing-history.png` })
})
