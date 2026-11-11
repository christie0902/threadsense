// The compiled static demo (dist-demo) over plain files: no FastAPI server, no rewrites, no request to /api or to
// another origin. Counts are checked against the saved run's own files.
import { expect, test } from '@playwright/test'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIST = path.join(WEB, 'dist-demo')
const RUN = 'threadsense_full_v1_combined_v2'
const runFile = f => JSON.parse(readFileSync(path.join(WEB, '..', 'data/experiments', RUN, f), 'utf8'))
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp' }
let server, origin, served

test.beforeAll(async () => {
  if (!existsSync(path.join(DIST, 'index.html'))) throw new Error('Run npm run build:demo first.')
  served = []
  server = createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    served.push(url.pathname)
    const file = path.join(DIST, url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname))
    if (!file.startsWith(DIST) || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404); res.end('Not found'); return }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' })
    res.end(readFileSync(file))
  })
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  origin = `http://127.0.0.1:${server.address().port}`
})
test.afterAll(async () => { await new Promise(r => server.close(r)) })

/** Every request the page makes; the test fails on any API call or other origin. */
function watch(page) {
  const seen = []
  page.on('request', r => seen.push(r.url()))
  return () => {
    const outside = seen.filter(u => !u.startsWith(origin) && !u.startsWith('data:'))
    const api = seen.filter(u => new URL(u).pathname.startsWith('/api'))
    expect(outside, 'requests to another origin').toEqual([])
    expect(api, 'API requests').toEqual([])
    return seen
  }
}

const feedCards = page => page.getByTestId('feed').getByTestId('card')

test('fresh visit: briefing, filters, sorting, card details and evidence from bundled data', async ({ page }) => {
  const check = watch(page)
  const brief = runFile('morning_brief.json'), queue = runFile('review_queue.json')
  await page.goto(`${origin}/`)
  await expect(page.getByTestId('demo-notice')).toContainText('Demo data · Changes saved in this browser.')
  await expect(page.getByTestId('run-select')).toHaveValue(RUN)
  await expect(page.getByTestId('stat-in-brief')).toContainText('63')
  await expect(page.getByTestId('stat-in-brief')).toContainText('52 needs review · 8 recommended · 3 observation')
  await expect(page.getByTestId('header-queue')).toContainText(String(queue.length))
  expect(brief.run_id).toBeTruthy()
  await expect(page.getByTestId('demo-reset')).toHaveCount(0) // nothing saved yet
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/demo-overview.png` })

  const all = await feedCards(page).count()
  expect(all).toBeGreaterThan(10)
  await page.getByTestId('project-select').selectOption('audio_multimodal')
  const audio = await feedCards(page).count()
  expect(audio).toBeGreaterThan(0)
  expect(audio).toBeLessThan(all)
  await page.getByTestId('project-select').selectOption('')
  await expect(feedCards(page)).toHaveCount(all)
  const order = async () => feedCards(page).evaluateAll(cards => cards.map(c => c.dataset.cardId).join())
  const bySeverity = await order()
  await page.getByTestId('sort-select').selectOption('activity')
  await expect.poll(order).not.toBe(bySeverity)
  await expect(feedCards(page)).toHaveCount(all)
  await page.getByTestId('sort-select').selectOption('severity')

  let card
  for (let i = 0; ; i++) { // the first card that cites a source in its opened view
    card = feedCards(page).nth(i)
    await card.getByTestId('card-expand').click()
    await expect(card.getByTestId('ai-feedback')).toBeVisible()
    if (await card.getByTestId('source-link').count()) break
    await card.getByTestId('card-expand').click()
  }
  const source = card.getByTestId('source-link').first()
  await source.scrollIntoViewIfNeeded()
  await source.click()
  await expect(page.getByTestId('evidence-detail')).toBeVisible()
  await expect(page.getByTestId('evidence-text')).not.toBeEmpty()
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/demo-evidence.png` })
  expect(page.url()).toContain('panel=evidence')
  await page.reload() // the open panel is in the URL hash and comes back on refresh
  await expect(page.getByTestId('evidence-detail')).toBeVisible()
  check()
})

test('review changes persist in this browser across a refresh, and a fresh browser starts clean', async ({ page, browser }) => {
  const check = watch(page)
  await page.goto(`${origin}/#run=${RUN}&tab=queue`)
  await expect(page.getByTestId('review-queue')).toBeVisible()
  const items = page.getByTestId('review-item')
  const first = items.first()
  const itemId = await first.getAttribute('data-item-id')
  await first.getByTestId('lesson-fields').locator('summary').click()
  await first.getByTestId('lesson-text').fill('Speakers heard in an audio clip are not the Slack reporters; count message authors only.')
  await first.getByTestId('review-reject').click()
  const secondId = await items.nth(1).getAttribute('data-item-id')
  await items.nth(1).getByTestId('review-accept').click()
  await expect(page.locator(`[data-testid=review-item][data-item-id="${secondId}"]`)).toHaveCount(0) // left the open list

  // A card decision (approve a recommended action) and an AI-issue report.
  await page.goto(`${origin}/#run=${RUN}`)
  await page.getByTestId('quick-PENDING_ACTIONS').click()
  const rec = page.getByTestId('feed').locator('[data-testid=card][data-card-line=RECOMMENDED_ACTION]').first()
  const recId = await rec.getAttribute('data-card-id')
  await rec.getByTestId('card-expand').click()
  await rec.getByRole('button', { name: 'Approve…' }).click()
  await rec.getByTestId('save-decision').click()
  await expect(rec.getByTestId('save-success')).toBeVisible()
  await rec.getByTestId('report-ai-issue').locator('summary').click()
  await rec.getByTestId('feedback-category').selectOption('RECOMMENDATION')
  await rec.getByTestId('feedback-wrong').fill('The reminder repeats guidance the thread already quoted.')
  await rec.getByTestId('feedback-submit').click()
  await expect(rec.getByTestId('feedback-entry')).toHaveAttribute('data-state', 'SUBMITTED')
  await rec.getByTestId('feedback-confirm').click()
  await expect(rec.getByTestId('feedback-entry')).toHaveAttribute('data-state', 'CONFIRMED')

  await page.reload()
  await expect(page.getByTestId('demo-reset')).toContainText('(6)') // saved events: decision, 2 review actions, lesson, report submitted + confirmed
  await page.getByTestId('header-queue').click()
  await page.getByTestId('review-queue').getByRole('button', { name: /^all/i }).click()
  const rejected = page.locator(`[data-testid=review-item][data-item-id="${itemId}"]`)
  await expect(rejected.getByTestId('review-state')).toHaveText('rejected')
  await expect(rejected.getByTestId('lesson-entry')).toHaveAttribute('data-state', 'ACTIVE')
  await expect(page.locator(`[data-testid=review-item][data-item-id="${secondId}"]`).getByTestId('review-state')).toHaveText('accepted')
  await rejected.getByTestId('lesson-toggle').click()
  await expect(rejected.getByTestId('lesson-entry')).toHaveAttribute('data-state', 'INACTIVE')
  await expect(page.getByTestId('feedback-counts')).toContainText('1 report · 1 confirmed')
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/demo-queue-after-reload.png` })

  await page.goto(`${origin}/#run=${RUN}&tab=reviewed`)
  await page.reload()
  await expect(page.locator(`[data-testid=card][data-card-id=${recId}]`)).toBeVisible()
  check()

  const fresh = await browser.newContext() // another browser profile: no saved changes
  const other = await fresh.newPage()
  await other.goto(`${origin}/#run=${RUN}&tab=queue`)
  await expect(other.getByTestId('review-item')).toHaveCount(37)
  await expect(other.getByTestId('demo-reset')).toHaveCount(0)
  await fresh.close()

  await page.getByTestId('demo-reset').click()
  await page.getByTestId('demo-reset-confirm').click()
  await expect(page.getByTestId('demo-reset')).toHaveCount(0) // cleared and reloaded
  await page.goto(`${origin}/#run=${RUN}&tab=queue`)
  await page.reload()
  await expect(page.getByTestId('review-item')).toHaveCount(37)
})

test('direct navigation: root, hash routes and refresh need no rewrite', async ({ page }) => {
  const check = watch(page)
  for (const hash of ['', `#run=${RUN}`, `#run=${RUN}&tab=queue`, `#run=${RUN}&tab=reviewed`]) {
    await page.goto(`${origin}/${hash}`)
    await page.reload()
    await expect(page.getByTestId('demo-notice')).toBeVisible()
    await expect(page.getByTestId('briefing-header')).toBeVisible()
  }
  // Only index.html and hashed assets (plus the browser's own favicon probe); no other path is needed.
  expect(served.filter(p => p !== '/' && p !== '/favicon.ico' && !p.startsWith('/assets/'))).toEqual([])
  check()
})
