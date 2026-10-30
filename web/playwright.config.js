import { defineConfig } from '@playwright/test'

// UI tests drive the real FastAPI server (started per test by tests/server.js) in the system Chrome.
// Stores, snapshots and Playwright output go outside the repository (TS_UI_TMP, default D:/tsb/ui-<time>).
const tmp = process.env.TS_UI_TMP || `D:/tsb/ui-${Date.now()}`
process.env.TS_UI_TMP = tmp
process.env.TS_UI_ORIGIN ||= 'TEST' // Decisions made by UI tests are test data, never operational.

export default defineConfig({
  testDir: './tests',
  outputDir: `${tmp}/playwright-output`,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: { channel: 'chrome', headless: true, viewport: { width: 1280, height: 900 }, trace: 'retain-on-failure' },
})
