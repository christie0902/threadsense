// Regression checks for the QA pass on the static demo (2026-11-19): each test names the finding it guards. Runs on the
// compiled demo (npm run build:demo) over plain files, like demo.spec.js.
import { expect, test } from '@playwright/test'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIST = path.join(WEB, 'dist-demo')
const RUN = 'threadsense_full_v1_combined_v2'
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp', '.svg': 'image/svg+xml' }
// Cards in the saved briefing used below.
const ENGINEERING_CARD = 'card_23e1af47284c5a9e742c51401c1d6bd1' // Needs review, proposes an engineering report
const ARCHIVED_ANNOUNCEMENT_CARD = 'card_6f0643a3c9edc5ff136705387a4615b1' // cites an announcement posted before the window
let server, origin

test.beforeAll(async () => {
  if (!existsSync(path.join(DIST, 'index.html'))) throw new Error('Run npm run build:demo first.')
  server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    const file = path.join(DIST, url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname))
    if (!file.startsWith(DIST) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404); res.end('Not found'); return }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' })
    res.end(readFileSync(file))
  })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  origin = `http://127.0.0.1:${server.address().port}`
})
test.afterAll(async () => { await new Promise(r => server.close(r)) })

async function go(page, hash = '') {
  await page.goto(`${origin}/#run=${RUN}${hash}`)
  await expect(page.getByTestId('briefing-header')).toBeVisible()
}
const card = (page, id) => page.locator(`[data-testid=card][data-card-id="${id}"]`)

test('High 1-2: the review queue shows plain reasons and card titles, no exception text or card IDs', async ({ page }) => {
  await go(page, '&tab=queue')
  const queue = page.getByTestId('review-queue')
  await expect(page.getByTestId('review-item').first()).toBeVisible()
  const items = await page.getByTestId('review-item').count()
  await expect(page.getByTestId('review-reason-title')).toHaveCount(items)
  const text = await queue.innerText() // closed "Technical record" disclosures are not rendered text
  for (const raw of ['ValueError', 'Prose unit', 'Candidate:', 'TEAM_LEAD', 'card_', 'member(s)', "['"]) expect(text, raw).not.toContain(raw)
  expect(text).toContain('Check who answered this thread')
  // The original stays one click away.
  await page.getByTestId('review-technical').first().locator('summary').click()
  await expect(page.getByTestId('review-reason-raw').first()).toBeVisible()
})

test('High 3: an announcement posted before the window opens as a source, never as a broken thread link', async ({ page }) => {
  await go(page, '&project=audio_multimodal')
  const box = card(page, ARCHIVED_ANNOUNCEMENT_CARD)
  await box.getByTestId('card-expand').click()
  await box.getByRole('tab', { name: 'Sources & threads' }).click()
  await box.getByTestId('source-link').filter({ hasText: 'Playback trial posted' }).click()
  const panel = page.getByTestId('evidence-detail')
  await expect(panel.getByTestId('evidence-thread-unavailable')).toBeVisible()
  await expect(panel.getByTestId('evidence-thread-link')).toHaveCount(0)
  await expect(page.getByTestId('side-panel')).not.toContainText('is not in channel')
  // Medium 9: Escape closes the source viewer.
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('side-panel')).toHaveCount(0)
})

test('Medium 4, 6: no pipeline notes, raw JSON tab or unrendered markdown in the reader view', async ({ page }) => {
  await go(page, '&project=audio_multimodal')
  const box = card(page, ARCHIVED_ANNOUNCEMENT_CARD)
  await box.getByTestId('card-expand').click()
  await expect(box.getByRole('tab', { name: 'Technical' })).toHaveCount(0) // developer view only
  const more = box.getByTestId('supported-findings')
  if (await more.count()) await more.locator('summary').click()
  const text = await box.innerText()
  for (const raw of ["Agent 1's earlier labels", 'advisor statement', 'an input, not evidence', '×']) expect(text, raw).not.toContain(raw)
  await box.getByRole('tab', { name: 'Sources & threads' }).click()
  await box.getByTestId('source-link').first().click()
  const evidence = await page.getByTestId('evidence-text').innerText()
  for (const raw of ['## ', '| --- |', '[RELATED RECORD', '[PRIOR RECORD', '[HISTORICAL']) expect(evidence, raw).not.toContain(raw)
})

test('Medium 5: the AI-issue form names threads and statements, not IDs', async ({ page }) => {
  await go(page, '&project=audio_multimodal')
  const box = card(page, ARCHIVED_ANNOUNCEMENT_CARD)
  await box.getByTestId('card-expand').click()
  await box.getByTestId('report-ai-issue').locator('summary').click()
  const form = box.getByTestId('feedback-form')
  expect(await form.getByTestId('feedback-threads').innerText()).not.toMatch(/C_[A-Z_]+\/\d/)
  const options = await form.getByTestId('feedback-target').locator('option').allTextContents()
  for (const o of options) expect(o).not.toMatch(/^(claim|summary|detail):/)
  expect(await form.innerText()).not.toContain('m:C_')
  const categories = await form.getByTestId('feedback-category').locator('option').allTextContents()
  expect(categories.at(-1)).toBe('Other') // Low: "Other" last
})

test('Medium 8: double-clicking Accept accepts one flag, and Reopen undoes it', async ({ page }) => {
  await go(page, '&tab=queue')
  const items = page.getByTestId('review-item')
  const [first, second] = [await items.nth(0).getAttribute('data-item-id'), await items.nth(1).getAttribute('data-item-id')]
  const item = id => page.locator(`[data-testid=review-item][data-item-id="${id}"]`)
  await item(first).getByTestId('review-accept').dblclick()
  await expect(item(first).getByTestId('review-state')).toHaveText('Accepted')
  await expect(item(second).getByTestId('review-state')).toHaveText('Open')
  await expect(item(first).getByTestId('review-history').locator('li')).toHaveCount(1)
  await item(first).getByTestId('review-reopen').click()
  await expect(item(first).getByTestId('review-state')).toHaveText('Open')
})

test('Medium 10: arrow keys keep working at the last slide', async ({ page }) => {
  await go(page, '&view=slides')
  const position = page.getByTestId('slide-position')
  const total = Number((await position.innerText()).match(/of (\d+)/)[1])
  for (let i = 1; i < total - 1; i++) await page.keyboard.press('ArrowRight')
  await expect(position).toHaveText(`Card ${total - 1} of ${total}`)
  await page.getByTestId('slide-next').click() // the button disables itself at the last card
  await expect(position).toHaveText(`Card ${total} of ${total}`)
  await page.keyboard.press('ArrowLeft')
  await expect(position).toHaveText(`Card ${total - 1} of ${total}`)
})

test('Medium 11: Resolve offers only resolutions that fit the card', async ({ page }) => {
  await go(page, '&project=response_preference')
  const box = card(page, ENGINEERING_CARD)
  await box.getByRole('button', { name: 'Resolve…' }).click()
  await expect(box.getByLabel('Confirm FAQ update')).toHaveCount(0)
  await expect(box.getByLabel('Confirm announcement')).toHaveCount(0)
  await expect(box.getByLabel('Route to an expert')).toBeVisible()
  await expect(box.getByLabel('Dismiss')).toBeVisible()
})

test('Medium 12: a reviewed card can be reopened and returns to Active', async ({ page }) => {
  await go(page, '&filter=PENDING_ACTIONS')
  const box = page.getByTestId('feed').locator('[data-testid=card]').first()
  const id = await box.getAttribute('data-card-id')
  await box.getByRole('button', { name: 'Approve…' }).click()
  await box.getByTestId('save-decision').click()
  // The card moves at once, with no extra click (QA follow-up: moves felt delayed).
  await expect(page.getByTestId('feed').locator(`[data-card-id="${id}"]`)).toHaveCount(0, { timeout: 1500 })
  await page.getByTestId('move-notice-show').click()
  const reviewed = card(page, id)
  await reviewed.getByTestId('reopen-card').click()
  await reviewed.locator('textarea[name=note]').fill('Approved by mistake.')
  await reviewed.getByTestId('save-reopen').click()
  await expect(page.getByTestId('feed').locator(`[data-card-id="${id}"]`)).toHaveCount(0, { timeout: 1500 })
  await expect(page.getByTestId('move-notice')).toContainText('Moved back to Active')
  await page.getByTestId('move-notice-show').click()
  await expect(card(page, id).getByTestId('reopened-note')).toContainText('Approved by mistake.')
  await expect(card(page, id).getByTestId('lifecycle-status')).toContainText('Reopened')
})

test('Low: counts agree with a project picked, plurals read right, and the line updates', async ({ page }) => {
  await go(page, '&project=audio_multimodal')
  const all = Number(await page.getByTestId('quick-ALL').locator('span').last().innerText())
  await expect(page.getByTestId('visible-count')).toHaveText(new RegExp(`^Showing ${all} of ${all} active cards? in audio_multimodal$`))
  await expect(page.getByTestId('stats-project')).toHaveText('audio_multimodal only')
  const text = await page.locator('main').innerText()
  expect(text).not.toMatch(/\b1 threads\b|\b1 cited sources\b|member\(s\)/)
  const caption = page.getByTestId('stat-in-brief')
  const before = await caption.innerText()
  const box = page.getByTestId('feed').locator('[data-testid=card][data-card-line=RECOMMENDED_ACTION]').first()
  if (await box.count()) {
    await box.getByRole('button', { name: 'Approve…' }).click()
    await box.getByTestId('save-decision').click()
    await expect(caption).not.toHaveText(before) // "Still active: …" follows the decision
  }
})

test('Low: Back returns to the previous tab inside the site', async ({ page }) => {
  await go(page)
  await page.getByTestId('tab-reviewed').click()
  await page.getByTestId('tab-queue').click()
  await page.goBack()
  await expect(page.getByTestId('tab-reviewed')).toHaveAttribute('aria-current', 'page')
  await page.goBack()
  await expect(page.getByTestId('tab-active')).toHaveAttribute('aria-current', 'page')
  expect(page.url().startsWith(origin)).toBe(true)
})

test('Low: Reset demo also clears the project filter and Slides view', async ({ page }) => {
  await go(page, '&tab=queue')
  await page.getByTestId('review-item').first().getByTestId('review-defer').click()
  await go(page, '&project=audio_multimodal&view=slides')
  await expect(page.getByTestId('demo-reset')).toBeVisible({ timeout: 10_000 })
  await page.getByTestId('demo-reset').click()
  await page.getByTestId('demo-reset-confirm').click()
  await page.waitForURL(`${origin}/`)
  await expect(page.getByTestId('briefing-header')).toBeVisible()
  await expect(page.getByTestId('feed')).toHaveAttribute('data-view', 'grid')
  await expect(page.getByTestId('project-select')).toHaveValue('')
})

test('Low: draft buttons toggle, copy once, and confirm; abbreviations explain themselves; favicon and description', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin })
  await go(page, '&filter=PENDING_ACTIONS')
  const box = page.getByTestId('feed').locator('[data-testid=card]').first()
  await box.getByTestId('show-draft').click()
  await expect(box.getByTestId('show-draft')).toHaveText('Hide draft')
  await expect(box.getByTestId('inline-draft')).toBeVisible()
  await box.getByTestId('action-box').getByRole('button', { name: 'Copy draft' }).click()
  await expect(box.getByTestId('action-box').getByRole('button', { name: 'Copied' })).toBeVisible()
  await box.getByTestId('card-expand').click()
  await expect(box.getByRole('button', { name: /^Copy draft$|^Copied$/ })).toHaveCount(1) // one copy button when opened
  await expect(page.locator('abbr[title^="Label Tool"]').first()).toBeAttached()
  await expect(page.getByTestId('glossary')).toContainText('Quarantine')
  await expect(page.locator('link[rel=icon]')).toHaveAttribute('href', /favicon\.svg$/)
  await expect(page.locator('meta[name=description]')).toHaveAttribute('content', /morning brief/i)
})

// ---- Second QA pass (2026-11-19) ----
const ADVISOR_CARD = 'card_2b05a096d172c66727f5a27fb50d5a18' // "Evidence the advisor needed is missing", ISO-titled sources
const QN_CARD = 'card_a03615c8bc678a84c906d5831a4ba1b0' // editorial note with three sources

test('Round 2: no "advisor", "not shown" or raw timestamps on an opened card and its source list', async ({ page }) => {
  await go(page, '&project=response_preference')
  const box = card(page, ADVISOR_CARD)
  await box.getByTestId('card-expand').click()
  await box.getByTestId('all-reasons').locator(':scope > summary').click()
  await box.getByRole('tab', { name: 'Sources & threads' }).click()
  const text = await box.innerText()
  expect(text).not.toMatch(/\badvisor\b/i)
  expect(text).not.toMatch(/(is|are|was|were) not shown\b(?! in the thread)|: not shown,/)
  expect(text).not.toMatch(/\d{4}-\d\d-\d\dT\d\d:\d\d/)
  expect(text).not.toMatch(/\b\d{4}-\d\d-\d\d\b/)
  // Collapse is the one way to close an opened card.
  await expect(box.getByTestId('card-collapse')).toBeVisible()
  await expect(box.getByRole('button', { name: 'Hide details' })).toHaveCount(0)
})

test('Round 2: links to other knowledge files show their label, not markdown', async ({ page }) => {
  await go(page, `&project=safety_classification&panel=evidence:${encodeURIComponent('k:safety-classification-faq@1.1:6025b955')}`)
  const textBox = page.getByTestId('evidence-text')
  await expect(textBox).toBeVisible()
  expect(await textBox.innerText()).not.toMatch(/\]\(\.\.\/|\.md\)/)
  await expect(page.getByTestId('doc-reference').first()).toBeVisible()
})

test('Round 2: Escape closes an open Approve form', async ({ page }) => {
  await go(page, '&filter=PENDING_ACTIONS')
  const box = page.getByTestId('feed').locator('[data-testid=card]').first()
  await box.getByRole('button', { name: 'Approve…' }).click()
  await expect(box.getByTestId('decision-form')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(box.getByTestId('decision-form')).toHaveCount(0)
  await expect(box.getByRole('button', { name: 'Approve…' })).toBeVisible()
})

test('Round 2: a thread opened by URL that the data does not contain gets a plain message', async ({ page }) => {
  await go(page, '&panel=thread:C_AUDIO_ANNOUNCEMENTS:1787581200.700001')
  await expect(page.getByTestId('panel-not-found')).toContainText("not in this briefing's saved Slack data")
  await expect(page.getByTestId('side-panel')).not.toContainText('is not in channel')
})

test('Round 2: editorial note sources are separate, numbered links', async ({ page }) => {
  await go(page, '&project=safety_classification')
  const note = card(page, QN_CARD).getByTestId('editorial-note').first()
  const text = await note.innerText()
  expect(text).not.toContain('sourcesource')
  expect(text).toMatch(/Sources: 1, 2, 3/)
})

test('Round 2: favicon.ico exists, and Back undoes a filter change', async ({ page }) => {
  expect((await page.request.get(`${origin}/favicon.ico`)).status()).toBe(200)
  await go(page)
  await page.getByTestId('tab-reviewed').click()
  await page.getByTestId('tab-active').click()
  await page.getByTestId('quick-NEEDS_REVIEW').click()
  await expect(page.getByTestId('active-filter')).toBeVisible()
  await page.goBack()
  await expect(page.getByTestId('active-filter')).toHaveCount(0)
  await expect(page.getByTestId('tab-active')).toHaveAttribute('aria-current', 'page')
})
