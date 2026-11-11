import { defineConfig } from '@playwright/test'

// Static demo build (npm run build:demo -> dist-demo), served as plain files with no FastAPI server and no rewrites.
// Output goes outside the repository (TS_UI_TMP, default D:/tsb/ui-demo-<time>).
const tmp = process.env.TS_UI_TMP || `D:/tsb/ui-demo-${Date.now()}`
process.env.TS_UI_TMP = tmp

export default defineConfig({
  testDir: './demo-tests',
  outputDir: `${tmp}/playwright-output`,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: { channel: 'chrome', headless: true, viewport: { width: 1280, height: 900 }, trace: 'retain-on-failure' },
})
