// Two saved runs in one static demo: the recorded briefing keeps its link and its counts; the revised briefing has its
// own link and bundle; switching runs, and saving in one, leaves the other as it was. No API request, no other origin.
import { expect, test } from '@playwright/test'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DIST = path.join(WEB, 'dist-demo')
const ORIGINAL = 'threadsense_full_v1_combined_v2'
const REVISED = 'threadsense_full_v1_combined_v3'
const runFile = (run, f) => JSON.parse(readFileSync(path.join(WEB, '..', 'data/experiments', run, f), 'utf8'))
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

function watch(page) {
  const seen = []
  page.on('request', r => seen.push(r.url()))
  return () => {
    expect(seen.filter(u => !u.startsWith(origin) && !u.startsWith('data:')), 'requests to another origin').toEqual([])
    expect(seen.filter(u => new URL(u).pathname.startsWith('/api')), 'API requests').toEqual([])
    return seen.map(u => new URL(u).pathname)
  }
}

const card = (page, name) => page.locator(`[data-testid=feed] [data-testid=card][data-topic-name^="${name}"]`)
const lines = by => `${by.NEEDS_REVIEW} needs review · ${by.RECOMMENDED_ACTION} recommended · ${by.OBSERVATION} observation`

test('the recorded briefing keeps its link and counts; the revised briefing opens at its own link from its own bundle', async ({ page }) => {
  const check = watch(page)
  const before = runFile(ORIGINAL, 'presentation.json').totals, after = runFile(REVISED, 'presentation.json').totals
  expect(lines(before.by_line)).toBe('52 needs review · 8 recommended · 3 observation')
  expect(lines(after.by_line)).toBe('53 needs review · 7 recommended · 3 observation')
  await page.goto(`${origin}/#run=${ORIGINAL}`)
  await expect(page.getByTestId('run-select')).toHaveValue(ORIGINAL)
  await expect(page.getByTestId('stat-in-brief')).toContainText(lines(before.by_line))
  const shipped = runFile(REVISED, 'derivation.json').card_id_map
  await expect(card(page, 'Waveform loads')).toHaveAttribute('data-card-id', 'card_4d391a71696447c5a06eba316582b985')
  let paths = check()
  expect(paths.filter(p => p.includes(REVISED)), 'the revised bundle is fetched only when that run is opened').toEqual([])

  await page.goto(`${origin}/#run=${REVISED}`)
  await page.reload()
  await expect(page.getByTestId('run-select')).toHaveValue(REVISED)
  await expect(page.getByTestId('stat-in-brief')).toContainText(String(after.active_cards))
  await expect(page.getByTestId('stat-in-brief')).toContainText(lines(after.by_line))
  await expect(card(page, 'Waveform loads')).toHaveAttribute('data-card-id', shipped.card_4d391a71696447c5a06eba316582b985)
  await expect(card(page, 'Waveform loads')).toContainText('playback failures across three threads')
  await expect(card(page, 'Spanish tú/usted')).toHaveAttribute('data-card-id', shipped.card_4ac440fb06af174ba3aa52a7727c2b44)
  await expect(card(page, 'Which QN rule applies')).toHaveAttribute('data-card-id', shipped.card_7664fdc93f494e9d0180f776a6b1f78e)
  paths = check()
  expect(paths.some(p => p.includes(REVISED) && p.endsWith('.json'))).toBe(true)
  await page.screenshot({ path: `${process.env.TS_UI_TMP}/demo-revised.png` })
})

test('a visit without a run opens the recorded briefing, and the briefing menu switches between the two', async ({ page }) => {
  const check = watch(page)
  await page.goto(`${origin}/`)
  await expect(page.getByTestId('run-select')).toHaveValue(ORIGINAL)
  await expect(page.getByTestId('run-select').locator('option')).toHaveCount(2)
  await page.getByTestId('run-select').selectOption(REVISED)
  await expect(page).toHaveURL(new RegExp(`#run=${REVISED}`))
  await expect(page.getByTestId('stat-in-brief')).toContainText('53 needs review · 7 recommended · 3 observation')
  await page.getByTestId('run-select').selectOption(ORIGINAL)
  await expect(page.getByTestId('stat-in-brief')).toContainText('52 needs review · 8 recommended · 3 observation')
  check()
})

test('a review action saved on the revised briefing stays with it; the recorded briefing starts clean', async ({ page }) => {
  const check = watch(page)
  await page.goto(`${origin}/#run=${REVISED}&tab=queue`)
  await expect(page.getByTestId('review-queue')).toBeVisible()
  const first = page.getByTestId('review-item').first()
  await first.getByTestId('review-accept').click()
  await expect(first.getByTestId('review-state')).toHaveText('Accepted')
  await expect(page.getByTestId('demo-reset')).toContainText('(1)')
  await page.goto(`${origin}/#run=${ORIGINAL}&tab=queue`)
  await page.reload()
  await expect(page.getByTestId('run-select')).toHaveValue(ORIGINAL)
  await expect(page.getByTestId('demo-reset')).toHaveCount(0)
  await page.goto(`${origin}/#run=${REVISED}&tab=queue`)
  await page.reload()
  await expect(page.getByTestId('demo-reset')).toContainText('(1)')
  check()
})
