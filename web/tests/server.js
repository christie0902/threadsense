import { spawn, execSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
let port = 8800 + Math.floor(Math.random() * 100)

/** A dashboard server on a fresh decision store outside the repository. restart() keeps the same store. */
export async function startServer(name) {
  const dir = `${process.env.TS_UI_TMP}/${name}-${Date.now()}`
  mkdirSync(dir, { recursive: true })
  const server = { dir, db: `${dir}/store.sqlite3`, port: port++, proc: null }
  server.url = `http://127.0.0.1:${server.port}`
  server.start = async () => {
    server.proc = spawn('uv', ['run', '--locked', 'python', 'scripts/run_dashboard.py', '--port', String(server.port),
      '--include-test-fixtures', '--decision-db', server.db], { cwd: REPO, stdio: 'ignore', windowsHide: true })
    for (let i = 0; i < 120; i++) {
      try { if ((await fetch(`${server.url}/api/health`)).ok) return } catch { /* not up yet */ }
      await new Promise(r => setTimeout(r, 500))
    }
    throw new Error('dashboard server did not start')
  }
  server.stop = async () => {
    if (!server.proc) return
    try { execSync(`taskkill /pid ${server.proc.pid} /T /F`, { stdio: 'ignore' }) } catch { server.proc.kill() }
    server.proc = null
    await new Promise(r => setTimeout(r, 500))
  }
  server.restart = async () => { await server.stop(); await server.start() }
  server.api = async (p, init) => (await fetch(`${server.url}${p}`, init)).json()
  await server.start()
  return server
}

export function sha256(rel) {
  return createHash('sha256').update(readFileSync(path.join(REPO, rel))).digest('hex')
}

export const RUN_FILES = ['data/experiments/agent3_overnight_smoke_v1', 'data/experiments/agent3_overnight_offline_v1',
  'data/experiments/agent3_overnight_offline_v2', 'tests/fixtures/dashboard_runs/dashboard_states_fixture_v1']
  .flatMap(d => ['cards.json', 'review_queue.json', 'morning_brief.json'].map(f => `${d}/${f}`))

export const hashes = () => Object.fromEntries(RUN_FILES.map(f => [f, sha256(f)]))
