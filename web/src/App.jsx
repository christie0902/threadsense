import { AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { getJSON } from './api.js'
import CardView from './CardView.jsx'
import SidePanel from './Panels.jsx'
import ReviewQueue from './ReviewQueue.jsx'
import { Badge, Details, when } from './ui.jsx'

const GROUPS = [
  ['RECOMMENDED_ACTION', 'Recommended actions'],
  ['OBSERVATION', 'Observations'],
  ['NEEDS_REVIEW', 'Needs review'],
]
const MODE_BANNERS = {
  LIVE: ['Live run', 'Card text comes from live model judgments that passed the final grounding check.', 'border-emerald-300 bg-emerald-50 text-emerald-900'],
  SCRIPTED: ['Scripted run, not model output', 'Prepared judgments for the pilot topics and a placeholder that judges nothing elsewhere. It shows the workflow, not model quality.', 'border-amber-400 bg-amber-50 text-amber-900'],
  TEST_FIXTURE: ['Test fixture, not model output', 'Hand-written cards for dashboard states that no saved run has. Decisions here are for testing.', 'border-fuchsia-400 bg-fuchsia-50 text-fuchsia-900'],
}
const OUTCOME_STYLES = { TOPIC_FAILED: 'text-red-800 bg-red-50', UNPROCESSED_BUDGET: 'text-amber-900 bg-amber-50',
  UNPROCESSED_RUN_STOPPED: 'text-amber-900 bg-amber-50', INTERRUPTED_UNCERTAIN: 'text-amber-900 bg-amber-50', OUT_OF_SCOPE: 'text-slate-500' }

function readHash() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  const raw = p.get('panel')
  let panel = null
  if (raw?.startsWith('evidence:')) panel = { type: 'evidence', id: raw.slice(9) }
  else if (raw?.startsWith('thread:')) { const [, channel, thread] = raw.split(':'); panel = { type: 'thread', channel, thread } }
  return { run: p.get('run'), project: p.get('project') || '', tab: p.get('tab') || 'brief', panel }
}

function writeHash(s) {
  const p = new URLSearchParams()
  if (s.run) p.set('run', s.run)
  if (s.project) p.set('project', s.project)
  if (s.tab !== 'brief') p.set('tab', s.tab)
  if (s.panel) p.set('panel', s.panel.type === 'evidence' ? `evidence:${s.panel.id}` : `thread:${s.panel.channel}:${s.panel.thread}`)
  const next = `#${p.toString()}`
  if (window.location.hash !== next) window.history.replaceState(null, '', next)
}

function Tile({ label, value, tone = '', testid }) {
  return (
    <div className={`rounded border border-slate-200 bg-white px-3 py-2 ${tone}`} data-testid={testid}>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-slate-600">{label}</div>
    </div>
  )
}

function Briefing({ markdown }) {
  if (!markdown) return null
  const blocks = markdown.split(/\n\s*\n/).filter(b => !b.startsWith('# '))
  const inline = t => t.split(/(\*\*[^*]+\*\*)/).map((part, i) => part.startsWith('**') ? <b key={i}>{part.slice(2, -2)}</b> : part)
  return (
    <div className="space-y-2 text-sm text-slate-800" data-testid="briefing">
      {blocks.map((b, i) => b.startsWith('## ') ? <div key={i} className="font-semibold">{b.slice(3)}</div>
        : b.split('\n').every(l => l.startsWith('- ')) ? <ul key={i} className="list-disc pl-5">{b.split('\n').map((l, j) => <li key={j}>{inline(l.slice(2))}</li>)}</ul>
          : <p key={i}>{inline(b)}</p>)}
    </div>
  )
}

function TopicTable({ rows }) {
  const [all, setAll] = useState(false)
  const order = { TOPIC_FAILED: 0, UNPROCESSED_BUDGET: 1, UNPROCESSED_RUN_STOPPED: 1, INTERRUPTED_UNCERTAIN: 1, CARD: 2, OUT_OF_SCOPE: 3 }
  const sorted = [...rows].sort((a, b) => (order[a.outcome] ?? 2) - (order[b.outcome] ?? 2))
  const shown = all ? sorted : sorted.slice(0, 12)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm" data-testid="topic-table">
        <thead className="text-xs text-slate-500"><tr><th className="py-1 pr-2">Topic</th><th className="pr-2">Project</th><th className="pr-2">Outcome</th><th className="pr-2">Card</th><th>Members</th></tr></thead>
        <tbody>
          {shown.map(r => (
            <tr key={r.work_id || r.card_id} className={`border-t border-slate-100 ${OUTCOME_STYLES[r.outcome] || ''}`} data-testid="topic-row" data-outcome={r.outcome}>
              <td className="py-1 pr-2">{r.topic_name || <span className="font-mono text-xs">{r.work_id}</span>}
                {r.detail && <div className="text-xs">{r.failure_class ? `${r.failure_class}: ` : ''}{r.detail}</div>}</td>
              <td className="pr-2 text-xs">{r.project_id}</td>
              <td className="pr-2 text-xs">{r.outcome.replaceAll('_', ' ').toLowerCase()}</td>
              <td className="pr-2 text-xs">{r.card_line ? r.card_line.replaceAll('_', ' ').toLowerCase() : '-'}</td>
              <td className="text-xs tabular-nums">{r.members}{r.review_items_kept ? ` (+${r.review_items_kept} review items kept)` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > 12 && <button type="button" className="mt-1 text-xs underline" onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${sorted.length} work items`}</button>}
    </div>
  )
}

export default function App() {
  const initial = readHash()
  const [runs, setRuns] = useState(null)
  const [actors, setActors] = useState([])
  const [runKey, setRunKey] = useState(initial.run)
  const [project, setProject] = useState(initial.project)
  const [tab, setTab] = useState(initial.tab)
  const [panel, setPanel] = useState(initial.panel)
  const [actor, setActor] = useState(() => { try { return localStorage.getItem('threadsense.actor') || '' } catch { return '' } })
  const [brief, setBrief] = useState(null)
  const [decisions, setDecisions] = useState({ decisions: [], indexing: {} })
  const [queue, setQueue] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => { getJSON('/api/runs').then(d => { setRuns(d.runs); setActors(d.actors); if (!runKey && d.runs.length) setRunKey(d.runs[0].run_key) }).catch(e => setError(String(e.message))) }, [])
  useEffect(() => { writeHash({ run: runKey, project, tab, panel }) }, [runKey, project, tab, panel])
  useEffect(() => { try { localStorage.setItem('threadsense.actor', actor) } catch { /* per-viewer convenience only */ } }, [actor])

  const loadDecisions = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/decisions`).then(setDecisions), [runKey])
  const loadQueue = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/review-queue`).then(d => setQueue(d.items)), [runKey])
  useEffect(() => {
    if (!runKey) return
    setBrief(null); setError(null)
    getJSON(`/api/runs/${encodeURIComponent(runKey)}/brief`).then(setBrief).catch(e => setError(String(e.message)))
    loadDecisions(); loadQueue()
  }, [runKey])

  const byCard = useMemo(() => {
    const out = {}
    for (const e of decisions.decisions) (out[e.card_id] ||= { decisions: [], indexing: decisions.indexing }).decisions.push(e)
    for (const s of Object.values(out)) { s.decisions.sort((a, b) => a.sequence - b.sequence); s.head = s.decisions.at(-1) }
    return out
  }, [decisions])

  const run = brief?.run
  const inProject = x => !project || x.project_id === project
  const cards = (brief?.cards || []).filter(c => inProject(c.card))
  const queueRows = queue.filter(r => inProject(r.item))
  const topics = (brief?.topics || []).filter(t => !project || t.project_id === project)
  const cardTopics = Object.fromEntries((brief?.cards || []).map(c => [c.card.card_id, c.card.topic_name]))
  const projects = runs?.find(r => r.run_key === runKey)?.projects || []
  const openQueue = queueRows.filter(r => r.review_state === 'OPEN').length
  const [banner, bannerText, bannerStyle] = MODE_BANNERS[run?.mode] || ['Unknown run mode', '', 'border-slate-300 bg-white']
  const counts = brief?.counts || {}

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 py-2 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3">
          <h1 className="mr-auto text-lg font-semibold">ThreadSense morning brief</h1>
          <label className="text-xs">Run
            <select className="ml-1 max-w-[22rem] rounded border border-slate-300 px-1 py-0.5 text-sm" value={runKey || ''} data-testid="run-select"
              onChange={e => { setRunKey(e.target.value); setPanel(null); setProject('') }}>
              {(runs || []).map(r => <option key={r.run_key} value={r.run_key}>{r.run_key} · {r.mode.toLowerCase()} · {r.status.toLowerCase()}</option>)}
            </select>
          </label>
          <label className="text-xs">Project
            <select className="ml-1 rounded border border-slate-300 px-1 py-0.5 text-sm" value={project} onChange={e => setProject(e.target.value)} data-testid="project-select">
              <option value="">All projects</option>
              {projects.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label className="text-xs">Acting as
            <select className="ml-1 rounded border border-slate-300 px-1 py-0.5 text-sm" value={actor} onChange={e => setActor(e.target.value)} data-testid="actor-select">
              <option value="">Choose…</option>
              {actors.map(a => <option key={a.actor_id} value={a.actor_id}>{a.name} ({a.actor_id}, team lead)</option>)}
            </select>
          </label>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-4 px-4 py-4">
        {error && <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900">{error}</div>}
        {!brief && !error && <div className="text-sm text-slate-600">Loading…</div>}
        {brief && (
          <>
            <section className={`rounded border p-3 ${bannerStyle}`} data-testid="run-banner" data-mode={run.mode}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{banner}</span>
                <Badge className="border-current bg-white/60" data-testid="run-status">{run.status.replaceAll('_', ' ').toLowerCase()}</Badge>
                <span className="text-xs">Cutoff {when(run.cutoff)} · window {when(run.window.start)} to {when(run.window.cutoff)}</span>
              </div>
              <div className="mt-1 text-xs">{bannerText} {run.mode !== 'LIVE' && run.semantic_note}</div>
              <div className="mt-1 text-xs">Run <code>{run.run_key}</code> ({run.run_id}){run.scope_only ? ` · scoped to ${run.scope_only.join(', ')}` : ''}.
                {run.shares_run_id_with.length > 0 && <> Another directory ({run.shares_run_id_with.join(', ')}) has the same run ID; it is a separate run and is never combined with this one.</>}</div>
            </section>

            <nav className="flex gap-2 border-b border-slate-200">
              {[['brief', 'Morning brief'], ['queue', `Model Review Queue (${openQueue} open)`]].map(([t, label]) => (
                <button key={t} type="button" onClick={() => setTab(t)} data-testid={`tab-${t}`}
                  className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${tab === t ? 'border-sky-700 font-semibold text-sky-800' : 'border-transparent text-slate-600'}`}>{label}</button>
              ))}
            </nav>

            {tab === 'brief' && (
              <>
                <section className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8" data-testid="overview">
                  <Tile label="Cards" value={counts.cards ?? 0} testid="tile-cards" />
                  {GROUPS.map(([line, label]) => <Tile key={line} label={label} value={(counts.cards_by_line || {})[line] || 0} />)}
                  <Tile label="Failed topics" value={run.failed} tone={run.failed ? 'bg-red-50' : ''} testid="tile-failed" />
                  <Tile label="Unprocessed" value={run.unprocessed} tone={run.unprocessed ? 'bg-amber-50' : ''} testid="tile-unprocessed" />
                  <Tile label="Out of scope" value={run.out_of_scope} testid="tile-out-of-scope" />
                  <Tile label="Model review items" value={counts.review_queue_items ?? 0} />
                </section>
                <div className="text-xs text-slate-600">
                  {counts.discussion_members} discussion members ({counts.members_on_cards} on cards) · {counts.announcement_route_members} announcement-route members ·
                  {' '}{counts.window_announcements} announcements in the window ({counts.window_announcements_in_snapshot} in the retrieval snapshot) · accounting {brief.accounting?.status?.toLowerCase()}
                </div>

                <Details summary="Saved briefing (from the run's morning_brief.md)" testid="briefing-details"><Briefing markdown={brief.briefing_markdown} /></Details>
                <Details summary={`Topic summary (${topics.length} work items${project ? ` in ${project}` : ''})`} testid="topics-details"><TopicTable rows={topics} /></Details>

                {brief.incomplete_work.length > 0 && (
                  <section className="rounded border border-red-200 bg-red-50 p-3" data-testid="incomplete-work">
                    <div className="text-sm font-semibold text-red-900">Incomplete work ({brief.incomplete_work.length}): members and review items are kept, but these topics have no card</div>
                    <ul className="mt-1 list-disc pl-5 text-sm">
                      {brief.incomplete_work.map(w => <li key={w.work_id}><b>{w.outcome.replaceAll('_', ' ').toLowerCase()}</b>: {w.topic_name || w.work_id}{w.failure_class ? ` (${w.failure_class})` : ''} - {w.detail || w.error}</li>)}
                    </ul>
                  </section>
                )}

                {GROUPS.map(([line, label]) => {
                  const group = cards.filter(c => c.card.card_line === line)
                  const active = group.filter(c => !byCard[c.card.card_id])
                  const resolved = group.filter(c => byCard[c.card.card_id])
                  return (
                    <section key={line} data-testid={`group-${line}`}>
                      <h2 className="mb-2 text-base font-semibold">{label} <span className="text-sm font-normal text-slate-500">({active.length} active{line !== 'OBSERVATION' ? `, ${resolved.length} resolved` : ''})</span></h2>
                      <div className="space-y-3" data-testid={`active-${line}`}>
                        <AnimatePresence initial={false}>
                          {active.map(c => <CardView key={c.card.card_id} runKey={runKey} item={c} actor={actor} decisionState={byCard[c.card.card_id]}
                            onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                        </AnimatePresence>
                        {active.length === 0 && <div className="text-sm text-slate-500">None active.</div>}
                      </div>
                      {resolved.length > 0 && (
                        <details className="mt-3 rounded border border-slate-200 bg-white p-2" data-testid={`resolved-${line}`}>
                          <summary className="cursor-pointer text-sm font-medium text-slate-700">Resolved ({resolved.length}): out of the active worklist; original card, review reasons and evidence unchanged</summary>
                          <div className="mt-2 space-y-3">
                            {resolved.map(c => <CardView key={c.card.card_id} runKey={runKey} item={c} actor={actor} decisionState={byCard[c.card.card_id]}
                              onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                          </div>
                        </details>
                      )}
                    </section>
                  )
                })}
              </>
            )}
            {tab === 'queue' && <ReviewQueue runKey={runKey} rows={queueRows} actor={actor} onChanged={loadQueue} cardTopics={cardTopics} />}
          </>
        )}
      </main>
      {runKey && <SidePanel runKey={runKey} panel={panel} openPanel={setPanel} onClose={() => setPanel(null)} />}
    </div>
  )
}
