import { AnimatePresence, MotionConfig } from 'framer-motion'
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getJSON } from './api.js'
import { QUICK_FILTERS, SORTS, briefStats, briefingDate, buildRows, decisionsByCard, filterRows, quickCounts, runKind, sortRows } from './briefView.js'
import CardView from './CardView.jsx'
import SidePanel from './Panels.jsx'
import ReviewQueue from './ReviewQueue.jsx'
import Sidebar, { Health, RunSelect } from './Sidebar.jsx'
import CardSlider from './Slider.jsx'
import { Badge, CopilotAvatar, Details, Icon, Orb, when, words } from './ui.jsx'

const MODE_BANNERS = {
  LIVE: ['Live run', 'Card text comes from live model judgments that passed the final grounding check.', 'border-emerald-400/25 bg-emerald-400/[0.06]', 'bg-emerald-400'],
  SCRIPTED: ['Scripted run, not model output', 'Prepared judgments for the pilot topics and a placeholder that judges nothing elsewhere. It shows the workflow, not model quality.', 'border-amber-400/30 bg-amber-400/[0.07]', 'bg-amber-400'],
  TEST_FIXTURE: ['Test fixture, not model output', 'Hand-written cards for dashboard states that no saved run has. Decisions here are for testing.', 'border-fuchsia-400/30 bg-fuchsia-400/[0.07]', 'bg-fuchsia-400'],
}
const OUTCOME_STYLES = { TOPIC_FAILED: 'text-red-300', UNPROCESSED_BUDGET: 'text-amber-200', UNPROCESSED_RUN_STOPPED: 'text-amber-200',
  INTERRUPTED_UNCERTAIN: 'text-amber-200', OUT_OF_SCOPE: 'text-slate-400' }
const TABS = { active: 'ACTIVE', reviewed: 'REVIEWED' }
// Static demo build only (npm run build:demo); other builds drop it.
const DemoNotice = import.meta.env.MODE === 'demo' ? lazy(() => import('./DemoNotice.jsx')) : null

function readHash() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  const raw = p.get('panel')
  let panel = null
  if (raw?.startsWith('evidence:')) panel = { type: 'evidence', id: raw.slice(9) }
  else if (raw?.startsWith('thread:')) { const [, channel, thread] = raw.split(':'); panel = { type: 'thread', channel, thread } }
  const tab = p.get('tab')
  return { run: p.get('run'), project: p.get('project') || '', tab: tab === 'queue' || tab === 'reviewed' ? tab : 'active', panel,
    item: p.get('item'), sort: SORTS[p.get('sort')] ? p.get('sort') : 'severity', quick: QUICK_FILTERS[p.get('filter')] ? p.get('filter') : 'ALL', debug: p.get('debug') === '1', view: p.get('view') === 'slides' ? 'slides' : 'grid' }
}

function writeHash(s) {
  const p = new URLSearchParams()
  if (s.run) p.set('run', s.run)
  if (s.project) p.set('project', s.project)
  if (s.tab !== 'active') p.set('tab', s.tab)
  if (s.sort !== 'severity') p.set('sort', s.sort)
  if (s.quick !== 'ALL') p.set('filter', s.quick)
  if (s.debug) p.set('debug', '1')
  if (s.view === 'slides') p.set('view', 'slides')
  if (s.tab === 'queue' && s.item) p.set('item', s.item)
  if (s.panel) p.set('panel', s.panel.type === 'evidence' ? `evidence:${s.panel.id}` : `thread:${s.panel.channel}:${s.panel.thread}`)
  const next = `#${p.toString()}`
  if (window.location.hash !== next) window.history.replaceState(null, '', next)
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

function Briefing({ markdown }) {
  if (!markdown) return <div className="text-slate-400">This run saved no readable brief.</div>
  const blocks = markdown.split(/\n\s*\n/).filter(b => !b.startsWith('# '))
  const inline = t => t.split(/(\*\*[^*]+\*\*)/).map((part, i) => part.startsWith('**') ? <b key={i} className="text-slate-100">{part.slice(2, -2)}</b> : part)
  return (
    <div className="space-y-2 text-sm leading-relaxed text-slate-300" data-testid="briefing">
      {blocks.map((b, i) => b.startsWith('## ') ? <div key={i} className="font-semibold text-slate-100">{b.slice(3)}</div>
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
        <thead className="text-xs uppercase tracking-wider text-slate-400"><tr><th className="py-1.5 pr-3 font-medium">Topic</th><th className="pr-3 font-medium">Project</th><th className="pr-3 font-medium">Outcome</th><th className="pr-3 font-medium">Card</th><th className="font-medium">Members</th></tr></thead>
        <tbody>
          {shown.map(r => (
            <tr key={r.work_id || r.card_id} className={`border-t border-white/[0.05] ${OUTCOME_STYLES[r.outcome] || 'text-slate-200'}`} data-testid="topic-row" data-outcome={r.outcome}>
              <td className="py-1.5 pr-3">{r.topic_name || <span className="font-mono text-xs">{r.work_id}</span>}
                {r.detail && <div className="text-xs opacity-80">{r.failure_class ? `${r.failure_class}: ` : ''}{r.detail}</div>}</td>
              <td className="pr-3 text-xs">{r.project_id}</td>
              <td className="pr-3 text-xs">{words(r.outcome)}</td>
              <td className="pr-3 text-xs">{r.card_line ? words(r.card_line) : '-'}</td>
              <td className="text-xs tabular-nums">{r.members}{r.review_items_kept ? ` (+${r.review_items_kept} review items kept)` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length > 12 && <button type="button" className="link mt-2 text-xs" onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${sorted.length} work items`}</button>}
    </div>
  )
}

function RunBanner({ run }) {
  const [mode, text, style, dot] = MODE_BANNERS[run.mode] || ['Unknown run mode', '', 'border-white/10 bg-white/[0.03]', 'bg-slate-400']
  // A derived or combined briefing carries live judgments but is not itself a live run.
  const label = run.mode === 'LIVE' && run.derivation ? `Live model judgments, ${runKind(run).label.toLowerCase()}` : mode
  return (
    <section className={`rounded-xl border px-4 py-3 ${style}`} data-testid="run-banner" data-mode={run.mode}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-white"><span className={`h-2 w-2 rounded-full ${dot} animate-breathe`} />{label}</span>
        <Badge data-testid="run-status">{words(run.status)}</Badge>
      </div>
      <div className="mt-1.5 text-sm leading-6 text-slate-200">{text} {run.mode !== 'LIVE' && run.semantic_note}</div>
      {run.derivation?.parents?.length > 1 && (
        <details className="mt-1 text-xs leading-relaxed text-cyan-100/90" data-testid="run-derivation">
          <summary className="cursor-pointer">Combined offline ({run.derivation.version}) from {run.derivation.parents.length} saved runs; no model call in this step.</summary>
          <div className="mt-1 text-slate-300">Sources: {run.derivation.parents.map(p => <code key={p} className="mr-2 font-mono">{p}</code>)} Card text is the saved live judgments; cards changed by a targeted live check say so on the card.</div>
        </details>
      )}
      {run.derivation && !(run.derivation.parents?.length > 1) && (
        <details className="mt-1 text-xs leading-relaxed text-cyan-100/90" data-testid="run-derivation">
          <summary className="cursor-pointer">Derived offline from <code className="font-mono">{run.derivation.parent_run_key}</code> ({run.derivation.policy_version}); card text and verdicts unchanged.</summary>
          <div className="mt-1 text-slate-300">No model call. Card lines, review reasons, briefing eligibility and pending follow-ups were recomputed from that run's saved judgments. Briefing relevance comes from audited labels bound to each thread's saved messages, not from an automatic classifier; a card without a matching label stays in the brief. Card IDs are new, so decisions on the original cards do not carry over.</div>
        </details>
      )}
    </section>
  )
}

/** Briefing date and source window, prominent. Controls sit on the right of the same bar. */
function BriefingHeader({ run, children }) {
  const kind = runKind(run)
  return (
    <header className="space-y-2 border-b border-white/[0.08] pb-6" data-testid="briefing-header">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <div className="eyebrow inline-flex items-center gap-1.5 text-cyan-300"><Icon name="spark" className="h-3.5 w-3.5" />Morning briefing · <span data-testid="run-kind">{kind.label}</span></div>
          <h2 className="mt-2 bg-gradient-to-r from-white via-cyan-100 to-cyan-300 bg-clip-text pb-1 font-display text-4xl font-bold leading-tight tracking-tight text-transparent sm:text-5xl" data-testid="briefing-date">{briefingDate(run) || 'Briefing date not recorded'}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2" data-testid="feed-controls">{children}</div>
      </div>
      <div className="flex items-center gap-1.5 text-sm leading-6 text-slate-300" data-testid="source-window">
        <Icon name="clock" className="h-4 w-4 text-slate-400" />Source window {when(run.window.start)} to {when(run.window.cutoff)} (cutoff excluded)
      </div>
    </header>
  )
}

/**
 * Developer details, off by default (footer toggle or #debug=1): run identity, provenance strings, generation time,
 * processing accounting and the saved run files. Kept out of the team lead's view, never removed.
 */
function DevPanel({ run, brief, topics, project, counts }) {
  return (
    <section className="panel space-y-4 p-6" data-testid="dev-panel">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100"><Icon name="layers" className="h-4 w-4 text-slate-400" />Developer details</h3>
      <div className="grid gap-4 text-xs leading-5 text-slate-300 lg:grid-cols-2">
        <div className="space-y-1" data-testid="run-identity">
          <div>Run <code className="font-mono text-slate-200">{run.run_key}</code> ({run.run_id}){run.scope_only ? ` · scoped to ${run.scope_only.join(', ')}` : ''}</div>
          <div className="break-all">Instance <code className="font-mono text-slate-200">{run.run_instance}</code></div>
          <div data-testid="run-provenance">Prompts {run.provenance?.prompt_version || 'not recorded'}{run.provenance?.model ? ` · model ${run.provenance.model}` : ''}</div>
          <div data-testid="run-scope">{run.projects.length} projects{run.batches?.length ? ` · ${run.batches.length} batches` : ''}</div>
          <div data-testid="generated-at">Generated: {run.generated_at ? when(run.generated_at) : 'not recorded in this run'}</div>
          {run.shares_run_id_with.length > 0 && <div className="text-amber-200" data-testid="shared-run-id">Another directory ({run.shares_run_id_with.join(', ')}) has the same run ID; it is a separate run and is never combined with this one.</div>}
        </div>
        <Health run={run} counts={brief.counts} accounting={brief.accounting} incomplete={brief.incomplete_work.length} />
      </div>
      <div className="space-y-2">
        <Details summary="Saved briefing (from the run's morning_brief.md)" testid="briefing-details"><Briefing markdown={brief.briefing_markdown} /></Details>
        {run.presentation?.stage_costs && (
          <Details summary="Usage by stage (saved ledgers)" testid="stage-costs">
            <table className="w-full text-left text-xs text-slate-300">
              <thead><tr className="text-slate-400"><th className="py-1">Stage</th><th>Requests</th><th>Cost for this stage</th></tr></thead>
              <tbody>{run.presentation.stage_costs.map(r => (
                <tr key={r.stage} data-testid="stage-cost"><td className="py-1 pr-3">{r.stage}</td><td className="tabular-nums">{r.requests}</td>
                  <td className="tabular-nums">${r.charged_usd_exact != null ? `${r.charged_usd.toFixed(3)} (as reported)` : r.charged_usd.toFixed(4)}</td></tr>))}</tbody>
            </table>
            <p className="mt-2 text-xs text-slate-400">The full-pipeline total is from the campaign ledger; the other rows are later, separate stages.</p>
          </Details>
        )}
        <Details summary={`Topic summary (${topics.length} work items${project ? ` in ${project}` : ''})`} testid="topics-details"><TopicTable rows={topics} /></Details>
        <Details summary="Run counts as saved (includes history; not active totals)" testid="saved-counts">
          <div className="space-y-1" data-testid="saved-counts-body">
            <div>Card records saved: {counts.cards ?? 0}{run.presentation?.totals ? ` (${run.presentation.totals.card_records.replaced_history} replaced, ${run.presentation.totals.card_records.processing_history} processing history)` : ''}</div>
            <div>Failed topics {run.failed} · unprocessed {run.unprocessed} · out of scope {run.out_of_scope}</div>
            <div>{counts.discussion_members} discussion members ({counts.members_on_cards} on cards) · {counts.announcement_route_members} announcement-route members · {counts.window_announcements} announcements in the window</div>
          </div>
        </Details>
      </div>
    </section>
  )
}

const EMPTY = {
  ACTIVE: 'Every card in this briefing has a saved decision. They are listed under Reviewed.',
  REVIEWED: 'No card in this briefing has a closing decision yet.',
}

export default function App() {
  const initial = readHash()
  const [runs, setRuns] = useState(null)
  const [session, setSession] = useState(undefined)
  const [runKey, setRunKey] = useState(initial.run)
  const [project, setProject] = useState(initial.project)
  const [tab, setTab] = useState(initial.tab)
  const [sort, setSort] = useState(initial.sort)
  const [quick, setQuick] = useState(initial.quick)
  const [focusItem, setFocusItem] = useState(initial.item)
  const [drawer, setDrawer] = useState(false)
  const [debug, setDebug] = useState(initial.debug)
  const [view, setView] = useState(initial.view)
  const menuRef = useRef(null)
  const openQueueItem = useCallback(id => { setFocusItem(id); setTab('queue'); window.scrollTo({ top: 0 }) }, [])
  const [panel, setPanel] = useState(initial.panel)
  const [brief, setBrief] = useState(null)
  const [decisions, setDecisions] = useState({ decisions: [], indexing: {} })
  const [queue, setQueue] = useState([])
  const [error, setError] = useState(null)
  const [syncErrors, setSyncErrors] = useState({})
  const syncError = Object.entries(syncErrors).filter(([, m]) => m).map(([source, m]) => `${source}: ${m}`).join('; ')
  const actor = session?.actor_id || ''

  useEffect(() => { getJSON('/api/runs').then(d => { setRuns(d.runs); setSession(d.session || null); if (!runKey && d.runs.length) setRunKey((d.runs.find(r => r.presentation) || d.runs[0]).run_key) }).catch(e => setError(String(e.message))) }, [])
  useEffect(() => { writeHash({ run: runKey, project, tab, panel, item: focusItem, sort, quick, debug, view }) }, [runKey, project, tab, panel, focusItem, sort, quick, debug, view])

  // Decisions and queue state always come back from the server, so lists and counts follow the saved records. A
  // failed refresh keeps the last confirmed state on screen (no card disappears) and says so.
  const failed = (source, message) => setSyncErrors(s => ({ ...s, [source]: message }))
  const loadDecisions = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/decisions`)
    .then(d => { setDecisions(d); failed('decisions', null) }).catch(e => failed('decisions', String(e.message))), [runKey])
  const loadQueue = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/review-queue`)
    .then(d => { setQueue(d.items); failed('queue', null) }).catch(e => failed('queue', String(e.message))), [runKey])
  const refresh = useCallback(() => { loadDecisions(); loadQueue() }, [loadDecisions, loadQueue])
  useEffect(() => {
    if (!runKey) return
    setBrief(null); setError(null); setDecisions({ decisions: [], indexing: {} }); setQueue([])
    getJSON(`/api/runs/${encodeURIComponent(runKey)}/brief`).then(setBrief).catch(e => setError(String(e.message)))
    loadDecisions(); loadQueue()
  }, [runKey])
  const closePanel = useCallback(() => setPanel(null), [])
  const closeDrawer = useCallback(() => { setDrawer(false); menuRef.current?.focus() }, [])

  const byCard = useMemo(() => decisionsByCard(decisions), [decisions])
  const run = brief?.run
  const inProject = x => !project || x.project_id === project
  const rows = useMemo(() => buildRows(brief?.cards || [], byCard, queue), [brief, byCard, queue])
  const stats = useMemo(() => brief && briefStats(rows, queue, run?.presentation?.totals), [rows, queue, brief])
  const lifecycle = TABS[tab] || 'ACTIVE'
  const counts = useMemo(() => quickCounts(rows, { tab: lifecycle, project }), [rows, lifecycle, project])
  const tabTotal = useMemo(() => filterRows(rows, { tab: lifecycle }).length, [rows, lifecycle])
  const visible = useMemo(() => sortRows(filterRows(rows, { tab: lifecycle, quick, project }), sort), [rows, lifecycle, quick, project, sort])
  const historyRows = scope => sortRows(rows.filter(r => r.scope === scope && inProject(r.card)), sort)
  const consolidated = (run?.consolidation?.pending || []).map(m => ({ ...m, rows: rows.filter(r => r.item.presentation?.consolidated?.consolidated_topic_id === m.consolidated_topic_id && inProject(r.card)) }))
    .filter(m => m.rows.length)
  const shared = run?.coordinated_actions || []
  const queueRows = queue.filter(r => inProject(r.item))
  const topics = (brief?.topics || []).filter(t => !project || t.project_id === project)
  const cardTopics = Object.fromEntries((brief?.cards || []).map(c => [c.card.card_id, c.display_title || c.card.topic_name]))
  const projects = runs?.find(r => r.run_key === runKey)?.projects || []
  const openQueue = queueRows.filter(r => r.review_state === 'OPEN').length
  const selectRun = k => { setRunKey(k); setPanel(null); setProject(''); setQuick('ALL'); setDrawer(false) }
  const card = r => (
    <CardView key={r.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={r.item} row={r} actor={actor}
      decisionState={r.state} onDecisionChanged={refresh} openPanel={setPanel} />
  )

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen lg:grid lg:grid-cols-[clamp(20rem,22vw,26rem)_minmax(0,1fr)]">
        <Sidebar run={run} session={session} stats={stats} quick={quick}
          onQuick={k => { setQuick(k); if (tab === 'queue') setTab('active'); setDrawer(false) }}
          quickCounts={brief ? counts : null} tab={lifecycle} onOpenQueue={() => { setTab('queue'); setDrawer(false) }}
          open={drawer} onClose={closeDrawer} />

        <div className="min-w-0">
          <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-white/[0.06] bg-ink-950/85 px-4 py-2.5 backdrop-blur-xl lg:hidden"
            style={{ top: 'env(safe-area-inset-top, 0px)' }} data-testid="mobile-bar">
            <button ref={menuRef} type="button" className="btn btn-sm" onClick={() => setDrawer(true)} aria-expanded={drawer} aria-controls="sidebar" data-testid="menu-button">
              <Icon name="queue" className="h-3.5 w-3.5" />Menu
            </button>
            <CopilotAvatar className="h-7 w-7" />
            <div className="min-w-0 leading-tight">
              <div className="font-display text-sm font-semibold text-white">Thread<span className="text-cyan-300">Sense</span></div>
              {run && <div className="truncate text-xs text-slate-300">{briefingDate(run)} · {stats ? `${stats.awaitingDecision} awaiting decision` : ''}</div>}
            </div>
          </div>

          <main className="max-w-[132rem] space-y-6 px-4 pb-16 pt-6 sm:px-6 lg:px-8 lg:pt-8 2xl:px-12">
            {DemoNotice && <Suspense fallback={null}><DemoNotice /></Suspense>}
            {error && <div className="rounded-xl border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}
            {!brief && !error && <div className="flex items-center gap-3 py-16 text-sm text-slate-400"><Orb busy className="h-6 w-6" />Loading the brief…</div>}
            {brief && (
              <>
                <BriefingHeader run={run}>
                  <label className="control" title="Briefing">
                    <Icon name="doc" className="h-4 w-4 text-slate-400" /><span className="sr-only">Briefing</span>
                    <RunSelect runs={runs} runKey={runKey} onSelect={selectRun} className="control-select max-w-[16rem]" />
                  </label>
                  <label className="control">Sort
                    <select className="control-select" value={sort} onChange={e => setSort(e.target.value)} data-testid="sort-select">
                      {Object.entries(SORTS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                    </select>
                  </label>
                  <label className="control">Project
                    <select className="control-select" value={project} onChange={e => setProject(e.target.value)} data-testid="project-select">
                      <option value="">All projects</option>
                      {projects.map(p => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </label>
                  <div className="control gap-1 p-1" role="group" aria-label="Card layout" data-testid="view-toggle">
                    {[['grid', 'Grid', 'layers'], ['slides', 'Slides', 'doc']].map(([v, label, icon]) => (
                      <button key={v} type="button" onClick={() => setView(v)} aria-pressed={view === v} data-testid={`view-${v}`}
                        className={`inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition ${view === v ? 'bg-cyan-300 text-ink-950' : 'text-slate-200 hover:bg-white/[0.08]'}`}>
                        <Icon name={icon} className="h-4 w-4" />{label}
                      </button>
                    ))}
                  </div>
                  <button type="button" onClick={() => setTab('queue')} data-testid="header-queue"
                    className="control px-4 text-slate-200 hover:border-cyan-300/40" title="Model Review Queue">
                    <Icon name="queue" className="h-4 w-4" />Review queue
                    {openQueue > 0 && <span className="rounded-full bg-cyan-400/20 px-2 text-xs font-semibold tabular-nums text-cyan-200">{openQueue}</span>}
                  </button>
                </BriefingHeader>
                {(debug || run.mode !== 'LIVE') && <RunBanner run={run} />}

                {brief.incomplete_work.length > 0 && (
                  <section className="rounded-xl border border-red-400/30 bg-red-500/[0.07] p-4" data-testid="incomplete-work">
                    <div className="flex items-center gap-2 text-sm font-semibold text-red-200"><Icon name="alert" />Incomplete work ({brief.incomplete_work.length}): members and review items are kept, but these topics have no card</div>
                    <ul className="mt-2 list-disc space-y-0.5 pl-6 text-sm text-red-100/90">
                      {brief.incomplete_work.map(w => <li key={w.work_id}><b>{words(w.outcome)}</b>: {w.topic_name || w.work_id}{w.failure_class ? ` (${w.failure_class})` : ''} - {w.detail || w.error}</li>)}
                    </ul>
                  </section>
                )}
                {syncError && (
                  <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-400/40 bg-amber-400/10 p-3 text-sm text-amber-100" data-testid="sync-error" role="alert">
                    Could not refresh decisions from the server ({syncError}). The list shows the last confirmed state.
                    <button type="button" className="btn btn-sm" onClick={refresh}>Retry</button>
                  </div>
                )}

                <nav className="flex gap-1 overflow-x-auto whitespace-nowrap border-b border-white/[0.06]" aria-label="Lifecycle">
                  {[['active', `Active (${stats.active})`], ['reviewed', `Reviewed (${stats.reviewed})`], ['queue', `Model Review Queue (${openQueue} open)`]].map(([t, label]) => (
                    <button key={t} type="button" onClick={() => setTab(t)} data-testid={`tab-${t}`} aria-current={tab === t ? 'page' : undefined}
                      className={`-mb-px border-b-2 px-3 py-2 text-sm transition ${tab === t ? 'border-cyan-300 font-semibold text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>{label}</button>
                  ))}
                </nav>

                {tab !== 'queue' && (
                  <>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                      {quick !== 'ALL' && (
                        <button type="button" className="inline-flex items-center gap-1 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-0.5 text-xs text-cyan-100"
                          onClick={() => setQuick('ALL')} data-testid="active-filter" aria-label={`Clear the ${QUICK_FILTERS[quick]} filter`}>
                          {QUICK_FILTERS[quick]}<Icon name="close" className="h-3 w-3" />
                        </button>
                      )}
                      <span className="ml-auto text-xs text-slate-400" data-testid="visible-count" aria-live="polite">
                        Showing {visible.length} of {plural(tabTotal, `${tab} card`)}{project ? ` · ${project}` : ''}
                      </span>
                    </div>

                    {tab === 'reviewed' && (
                      <p className="text-xs leading-relaxed text-slate-400" data-testid="reviewed-note">
                        Reviewed means a team-lead decision is saved for the card. The dashboard records no execution and no outcome, so nothing here is marked done or resolved. Model-review items stay open in their own queue.
                      </p>
                    )}

                    {/* Keyed by view: switching tab or filter shows the new list at once; only a card leaving after a
                        decision animates out. */}
                    <section key={`${lifecycle}|${quick}|${project}|${view}`} data-testid="feed" data-tab={lifecycle} data-view={view}
                      className={view === 'slides' ? '' : 'grid items-start gap-6 xl:grid-cols-2 min-[2200px]:grid-cols-3'}>
                      {view === 'slides'
                        ? <CardSlider key={sort} rows={visible} renderCard={card} />
                        : <AnimatePresence initial={false}>{visible.map(card)}</AnimatePresence>}
                      {visible.length === 0 && (
                        <div className="panel-inset px-4 py-3 text-sm text-slate-400 col-span-full" data-testid="feed-empty">
                          {!stats.inBrief ? `No cards${project ? ` in ${project}` : ''} in this briefing.`
                            : tabTotal && (quick !== 'ALL' || project) ? 'No card matches these filters.' : EMPTY[lifecycle]}
                        </div>
                      )}
                    </section>
                  </>
                )}

                {tab === 'active' && (
                  <>
                    {consolidated.length > 0 && (
                      <section className="space-y-3" data-testid="consolidated-issues">
                        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100"><span className="h-2 w-2 rounded-full bg-violet-300" />Consolidated issues
                          <span className="font-normal text-slate-400">({consolidated.length}, fresh advice pending)</span></h3>
                        {consolidated.map(m => (
                          <details key={m.consolidated_topic_id} className="group panel-inset p-3" data-testid="consolidated-issue" data-consolidated-id={m.consolidated_topic_id}>
                            <summary className="cursor-pointer text-sm font-medium text-slate-200">{m.topic_name}
                              <span className="ml-2 text-xs font-normal text-slate-400">{m.rows.length} original topics · fresh advice pending{m.review_codes_carried.length ? ' · review reasons kept' : ''}</span></summary>
                            <div className="mt-2 text-xs leading-relaxed text-slate-400" data-testid="consolidated-basis">Same issue ({words(m.judgment_provenance)}): {m.rationale} The advice below belongs to each original topic.</div>
                            <div className="mt-3 grid items-start gap-6 xl:grid-cols-2 min-[2200px]:grid-cols-3">{m.rows.map(card)}</div>
                          </details>
                        ))}
                      </section>
                    )}

                    {shared.length > 0 && (
                      <section className="panel p-4" data-testid="shared-actions">
                        <h3 className="text-sm font-semibold text-slate-100">Shared actions ({shared.length})</h3>
                        <p className="mt-1 text-xs text-slate-400">Distinct topics support the same edit. A shared action does not mean the topics share a cause.</p>
                        {shared.map(a => (
                          <div key={a.action_id} className="mt-3 rounded-lg border border-cyan-400/15 bg-cyan-400/[0.04] px-3 py-2 text-sm" data-testid="shared-action">
                            <div className="font-medium text-white">{a.label}: {a.targets.map(t => `${t.document} · ${t.section}`).join('; ')}</div>
                            <ul className="mt-1 list-disc pl-5 text-xs text-slate-300">
                              {a.cards.map(c => <li key={c.card_id} data-testid="shared-action-card">{c.topic_name}{c.review_codes.length ? ` (still needs review: ${c.review_codes.map(words).join(', ')})` : ''}</li>)}
                            </ul>
                            {a.related_withheld.length > 0 && <div className="mt-1 text-xs text-slate-400">Not coordinated (proposal withheld): {a.related_withheld.map(w => w.topic_name).join('; ')}</div>}
                          </div>
                        ))}
                      </section>
                    )}

                    {historyRows('NOT_IN_BRIEF').length > 0 && (
                      <details className="group panel-inset p-3" data-testid="not-in-brief">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Not in this brief ({historyRows('NOT_IN_BRIEF').length}): social or routine exchanges kept in history</summary>
                        <div className="mt-3 grid items-start gap-6 xl:grid-cols-2 min-[2200px]:grid-cols-3">{historyRows('NOT_IN_BRIEF').map(card)}</div>
                      </details>
                    )}

                    {historyRows('PROCESSING_HISTORY').length > 0 && (
                      <details className="group panel-inset p-3" data-testid="processing-history">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300">Processing history ({historyRows('PROCESSING_HISTORY').length}): kept out of issue clustering by Agent 1 relevance</summary>
                        <div className="mt-3 grid items-start gap-6 xl:grid-cols-2 min-[2200px]:grid-cols-3">{historyRows('PROCESSING_HISTORY').map(card)}</div>
                      </details>
                    )}

                  </>
                )}
                {tab === 'queue' && <ReviewQueue runKey={runKey} rows={queueRows} actor={actor} onChanged={loadQueue} cardTopics={cardTopics} focus={focusItem} />}
                {debug && <DevPanel run={run} brief={brief} topics={topics} project={project} counts={brief.counts} />}
              </>
            )}
          </main>
          <footer className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-t border-white/[0.06] px-4 py-4 text-xs text-slate-400" style={{ paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))' }}>
            <span>ThreadSense · local dashboard without authentication · decisions are saved, never posted or executed</span>
            <button type="button" className="link text-xs text-slate-400" onClick={() => setDebug(!debug)} aria-pressed={debug} data-testid="debug-toggle">
              {debug ? 'Hide developer details' : 'Developer details'}
            </button>
          </footer>
        </div>
        {runKey && <SidePanel runKey={runKey} panel={panel} openPanel={setPanel} onClose={closePanel} />}
      </div>
    </MotionConfig>
  )
}
