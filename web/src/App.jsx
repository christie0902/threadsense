import { AnimatePresence } from 'framer-motion'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { getJSON } from './api.js'
import CardView from './CardView.jsx'
import SidePanel from './Panels.jsx'
import ReviewQueue from './ReviewQueue.jsx'
import { Badge, CopilotAvatar, CopilotFigure, Details, Icon, Orb, when, words } from './ui.jsx'

// Needs review first: it is what the team lead has to look at.
const GROUPS = [
  ['NEEDS_REVIEW', 'Needs review', 'bg-amber-400'],
  ['RECOMMENDED_ACTION', 'Recommended actions', 'bg-emerald-400'],
  ['OBSERVATION', 'Observations', 'bg-violet-400'],
]
const MODE_BANNERS = {
  LIVE: ['Live run', 'Card text comes from live model judgments that passed the final grounding check.', 'border-emerald-400/25 bg-emerald-400/[0.06]', 'bg-emerald-400'],
  SCRIPTED: ['Scripted run, not model output', 'Prepared judgments for the pilot topics and a placeholder that judges nothing elsewhere. It shows the workflow, not model quality.', 'border-amber-400/30 bg-amber-400/[0.07]', 'bg-amber-400'],
  TEST_FIXTURE: ['Test fixture, not model output', 'Hand-written cards for dashboard states that no saved run has. Decisions here are for testing.', 'border-fuchsia-400/30 bg-fuchsia-400/[0.07]', 'bg-fuchsia-400'],
}
const OUTCOME_STYLES = { TOPIC_FAILED: 'text-red-300', UNPROCESSED_BUDGET: 'text-amber-200', UNPROCESSED_RUN_STOPPED: 'text-amber-200',
  INTERRUPTED_UNCERTAIN: 'text-amber-200', OUT_OF_SCOPE: 'text-slate-500' }

function readHash() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  const raw = p.get('panel')
  let panel = null
  if (raw?.startsWith('evidence:')) panel = { type: 'evidence', id: raw.slice(9) }
  else if (raw?.startsWith('thread:')) { const [, channel, thread] = raw.split(':'); panel = { type: 'thread', channel, thread } }
  return { run: p.get('run'), project: p.get('project') || '', tab: p.get('tab') || 'brief', panel, item: p.get('item') }
}

function writeHash(s) {
  const p = new URLSearchParams()
  if (s.run) p.set('run', s.run)
  if (s.project) p.set('project', s.project)
  if (s.tab !== 'brief') p.set('tab', s.tab)
  if (s.tab === 'queue' && s.item) p.set('item', s.item)
  if (s.panel) p.set('panel', s.panel.type === 'evidence' ? `evidence:${s.panel.id}` : `thread:${s.panel.channel}:${s.panel.thread}`)
  const next = `#${p.toString()}`
  if (window.location.hash !== next) window.history.replaceState(null, '', next)
}

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

function Metric({ icon, label, value, caption, tone, onClick, testid }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick} data-testid={testid}
      className={`panel flex items-center gap-3 p-3 text-left sm:gap-4 sm:p-4 ${onClick ? 'transition hover:border-white/15' : ''}`}>
      <span className={`hidden h-11 w-11 shrink-0 sm:grid place-items-center rounded-full border ${tone.ring}`}><Icon name={icon} className={`h-5 w-5 ${tone.text}`} /></span>
      <span className="min-w-0">
        <span className="block text-xs font-medium text-slate-400">{label}</span>
        <span className={`block font-display text-2xl font-semibold sm:text-3xl tabular-nums leading-tight ${value ? tone.text : 'text-slate-500'}`}>{value}</span>
        {caption && <span className="block truncate text-[11px] text-slate-500">{caption}</span>}
      </span>
    </Tag>
  )
}
const TONES = {
  amber: { ring: 'border-amber-400/30 bg-amber-400/10', text: 'text-amber-300' },
  emerald: { ring: 'border-emerald-400/30 bg-emerald-400/10', text: 'text-emerald-300' },
  red: { ring: 'border-red-400/30 bg-red-500/10', text: 'text-red-300' },
  cyan: { ring: 'border-cyan-400/30 bg-cyan-400/10', text: 'text-cyan-300' },
}

function Briefing({ markdown }) {
  if (!markdown) return <div className="text-slate-500">This run saved no readable brief.</div>
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
        <thead className="text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="py-1.5 pr-3 font-medium">Topic</th><th className="pr-3 font-medium">Project</th><th className="pr-3 font-medium">Outcome</th><th className="pr-3 font-medium">Card</th><th className="font-medium">Members</th></tr></thead>
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

const EMPTY_TEXT = {
  NEEDS_REVIEW: 'No card in this run needs a team lead.',
  RECOMMENDED_ACTION: 'This run produced no recommended-action cards.',
  OBSERVATION: 'This run produced no observation cards.',
}
/** An honest empty line: the count is what the run saved, so explain the zero instead of filling it. */
function EmptyLine({ line, resolved, total, fixture, onOpen }) {
  const why = resolved ? `All ${resolved} resolved.`
    : line !== 'NEEDS_REVIEW' && total ? 'A card that has any review reason (for example an inherited Agent 1 flag or high severity) is listed under Needs review instead.' : ''
  return (
    <div className="panel-inset flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 text-sm text-slate-400 lg:col-span-2" data-testid={`empty-${line}`}>
      <span>{resolved ? 'Nothing active.' : EMPTY_TEXT[line]} <span className="text-slate-500">{why}</span></span>
      {!resolved && line !== 'NEEDS_REVIEW' && fixture && (
        <button type="button" className="link text-xs" onClick={() => onOpen(fixture.run_key)}>See how one looks in the labelled test fixture</button>
      )}
    </div>
  )
}

function RunBanner({ run }) {
  const [label, text, style, dot] = MODE_BANNERS[run.mode] || ['Unknown run mode', '', 'border-white/10 bg-white/[0.03]', 'bg-slate-400']
  return (
    <section className={`rounded-xl border px-4 py-3 ${style}`} data-testid="run-banner" data-mode={run.mode}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-white"><span className={`h-2 w-2 rounded-full ${dot} animate-breathe`} />{label}</span>
        <Badge data-testid="run-status">{words(run.status)}</Badge>
        <span className="text-xs text-slate-400"><Icon name="clock" className="mr-1 inline h-3.5 w-3.5 -translate-y-px" />Cutoff {when(run.cutoff)} · window {when(run.window.start)} to {when(run.window.cutoff)}</span>
      </div>
      <div className="mt-1.5 text-xs leading-relaxed text-slate-300">{text} {run.mode !== 'LIVE' && run.semantic_note}</div>
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
      <div className="mt-1 text-[11px] text-slate-500">Run <code className="font-mono text-slate-400">{run.run_key}</code> ({run.run_id}){run.scope_only ? ` · scoped to ${run.scope_only.join(', ')}` : ''}
        <span data-testid="run-provenance"> · prompts {run.provenance?.prompt_version || 'not recorded'}{run.provenance?.model ? ` · model ${run.provenance.model}` : ''}</span>.
        {run.shares_run_id_with.length > 0 && <span className="text-amber-200/90"> Another directory ({run.shares_run_id_with.join(', ')}) has the same run ID; it is a separate run and is never combined with this one.</span>}</div>
    </section>
  )
}

export default function App() {
  const initial = readHash()
  const [runs, setRuns] = useState(null)
  const [session, setSession] = useState(undefined)
  const [runKey, setRunKey] = useState(initial.run)
  const [project, setProject] = useState(initial.project)
  const [tab, setTab] = useState(initial.tab)
  const [focusItem, setFocusItem] = useState(initial.item)
  const openQueueItem = useCallback(id => { setFocusItem(id); setTab('queue'); window.scrollTo({ top: 0 }) }, [])
  const [panel, setPanel] = useState(initial.panel)
  const [lineFilter, setLineFilter] = useState('ALL')
  const [brief, setBrief] = useState(null)
  const [decisions, setDecisions] = useState({ decisions: [], indexing: {} })
  const [queue, setQueue] = useState([])
  const [error, setError] = useState(null)
  const actor = session?.actor_id || ''

  useEffect(() => { getJSON('/api/runs').then(d => { setRuns(d.runs); setSession(d.session || null); if (!runKey && d.runs.length) setRunKey(d.runs[0].run_key) }).catch(e => setError(String(e.message))) }, [])
  useEffect(() => { writeHash({ run: runKey, project, tab, panel, item: focusItem }) }, [runKey, project, tab, panel, focusItem])

  const loadDecisions = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/decisions`).then(setDecisions), [runKey])
  const loadQueue = useCallback(() => runKey && getJSON(`/api/runs/${encodeURIComponent(runKey)}/review-queue`).then(d => setQueue(d.items)), [runKey])
  useEffect(() => {
    if (!runKey) return
    setBrief(null); setError(null)
    getJSON(`/api/runs/${encodeURIComponent(runKey)}/brief`).then(setBrief).catch(e => setError(String(e.message)))
    loadDecisions(); loadQueue()
  }, [runKey])
  const closePanel = useCallback(() => setPanel(null), [])

  const byCard = useMemo(() => {
    const out = {}
    for (const e of decisions.decisions) (out[e.card_id] ||= { decisions: [], indexing: decisions.indexing }).decisions.push(e)
    for (const s of Object.values(out)) { s.decisions.sort((a, b) => a.sequence - b.sequence); s.head = s.decisions.at(-1) }
    return out
  }, [decisions])

  const run = brief?.run
  const inProject = x => !project || x.project_id === project
  const allCards = (brief?.cards || []).filter(c => inProject(c.card))
  // briefing_policy: social or routine cards are kept in history, outside the brief's lists and counts. A v2 run also
  // lists consolidated issues (original cards attached) and Agent 1 processing history separately.
  const inventory = c => c.presentation?.inventory || 'BRIEF'
  const inBrief = c => (c.presentation?.briefing?.status || 'IN_BRIEFING') === 'IN_BRIEFING' && inventory(c) === 'BRIEF'
  const cards = allCards.filter(inBrief)
  const history = allCards.filter(c => inventory(c) === 'BRIEF' && !inBrief(c))
  const processed = allCards.filter(c => inventory(c) === 'PROCESSING_HISTORY')
  const consolidated = (run?.consolidation?.pending || []).map(m => ({ ...m, cards: allCards.filter(c => c.presentation?.consolidated?.consolidated_topic_id === m.consolidated_topic_id) }))
    .filter(m => m.cards.length)
  const shared = run?.coordinated_actions || []
  const queueRows = queue.filter(r => inProject(r.item))
  const topics = (brief?.topics || []).filter(t => !project || t.project_id === project)
  const cardTopics = Object.fromEntries((brief?.cards || []).map(c => [c.card.card_id, c.display_title || c.card.topic_name]))
  const projects = runs?.find(r => r.run_key === runKey)?.projects || []
  const openQueue = queueRows.filter(r => r.review_state === 'OPEN').length
  const counts = brief?.counts || {}
  const active = cards.filter(c => !byCard[c.card.card_id])
  const activeIn = line => active.filter(c => c.card.card_line === line).length
  const highActive = active.filter(c => c.card.severity.level === 'HIGH').length
  const totalIn = line => cards.filter(c => c.card.card_line === line).length

  const headline = !cards.length ? `No cards${project ? ` in ${project}` : ''} in this run.`
    : !active.length ? 'Every card in this run has a saved decision.'
      : [activeIn('NEEDS_REVIEW') && `${plural(activeIn('NEEDS_REVIEW'), 'card needs', 'cards need')} your review`,
        activeIn('RECOMMENDED_ACTION') && `${plural(activeIn('RECOMMENDED_ACTION'), 'recommended action')} ready to approve`,
        activeIn('OBSERVATION') && `${plural(activeIn('OBSERVATION'), 'observation')} to keep in view`].filter(Boolean).join(', ') + '.'

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-white/[0.06] bg-ink-950/75 px-4 py-2.5 backdrop-blur-xl" style={{ top: 'env(safe-area-inset-top, 0px)' }}>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2">
          <div className="mr-auto flex items-center gap-3" data-testid="copilot">
            <CopilotAvatar />
            <div className="leading-tight">
              <h1 className="font-display text-lg font-semibold tracking-tight text-white">Thread<span className="text-cyan-300">Sense</span></h1>
              <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300/70">AI co-pilot · <span className="text-slate-400">{brief ? 'brief ready' : 'loading'}</span></div>
            </div>
          </div>
          <label className="flex items-center gap-2 text-[11px] text-slate-500">Run
            <select className="field max-w-[19rem] text-xs" value={runKey || ''} data-testid="run-select"
              onChange={e => { setRunKey(e.target.value); setPanel(null); setProject('') }}>
              {(runs || []).map(r => <option key={r.run_key} value={r.run_key}>{r.run_key} · {r.mode.toLowerCase()} · {r.status.toLowerCase()}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-[11px] text-slate-500">Project
            <select className="field text-xs" value={project} onChange={e => setProject(e.target.value)} data-testid="project-select">
              <option value="">All projects</option>
              {projects.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          {session !== undefined && (
            <div className={`flex items-center gap-2 rounded-full border py-1 pl-1 pr-3 ${session ? 'border-white/10 bg-white/[0.04]' : 'border-red-400/40 bg-red-500/10'}`}
              data-testid="session-user" title={session ? 'Signed in for this local session. The identity is fixed by the server.' : undefined}>
              <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${session ? 'bg-gradient-to-br from-cyan-300 to-indigo-400 text-ink-950' : 'bg-red-400/20 text-red-200'}`}>
                {session ? (session.name || session.actor_id).slice(0, 1) : '!'}
              </span>
              <span className="leading-tight">
                <span className="block text-xs font-medium text-white">{session ? `${session.name || session.actor_id}` : 'No team-lead session'}</span>
                <span className="flex items-center gap-1 text-[10px] text-slate-400">{session ? <><Icon name="lock" className="h-2.5 w-2.5" />Team lead · {session.actor_id}</> : 'Decisions disabled'}</span>
              </span>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-5 px-4 pb-16 pt-5">
        {error && <div className="rounded-xl border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-100">{error}</div>}
        {!brief && !error && <div className="flex items-center gap-3 py-16 text-sm text-slate-400"><Orb busy className="h-6 w-6" />Loading the brief…</div>}
        {brief && (
          <>
            <RunBanner run={run} />

            <nav className="flex gap-1 border-b border-white/[0.06]">
              {[['brief', 'Morning brief'], ['queue', `Model Review Queue (${openQueue} open)`]].map(([t, label]) => (
                <button key={t} type="button" onClick={() => setTab(t)} data-testid={`tab-${t}`}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm transition ${tab === t ? 'border-cyan-300 font-semibold text-white' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>{label}</button>
              ))}
            </nav>

            {tab === 'brief' && (
              <>
                <section className="panel relative overflow-hidden p-6 md:min-h-[13rem] md:pr-56" data-testid="hero">
                  <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" aria-hidden="true" />
                  <div className="absolute -bottom-2 right-6 hidden md:block"><CopilotFigure className="h-52" /></div>
                  <div className="relative max-w-2xl">
                    <div className="eyebrow inline-flex items-center gap-1.5 text-cyan-300/80"><Icon name="spark" className="h-3.5 w-3.5" />Your co-pilot prepared this overnight · cutoff {when(run.cutoff)}</div>
                    <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-white sm:text-[1.7rem]">
                      Good morning{session?.name ? `, ${session.name}` : ''}. <span className="text-cyan-300">Here's what needs you today.</span>
                    </h2>
                    <p className="mt-2 text-sm leading-relaxed text-slate-300" data-testid="headline">
                      {headline}{highActive > 0 && ` ${highActive} ${highActive === 1 ? 'is' : 'are'} high severity.`}
                      {openQueue > 0 && ` ${plural(openQueue, 'model-review flag')} open in the queue.`}
                    </p>
                  </div>
                </section>

                <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="overview">
                  <Metric icon="alert" label="Needs review" value={activeIn('NEEDS_REVIEW')} tone={TONES.amber} testid="tile-needs-review"
                    caption={totalIn('NEEDS_REVIEW') - activeIn('NEEDS_REVIEW') ? `${totalIn('NEEDS_REVIEW') - activeIn('NEEDS_REVIEW')} resolved` : 'awaiting your decision'} />
                  <Metric icon="spark" label="Recommended actions" value={activeIn('RECOMMENDED_ACTION')} tone={TONES.emerald} testid="tile-recommended"
                    caption={totalIn('RECOMMENDED_ACTION') - activeIn('RECOMMENDED_ACTION') ? `${totalIn('RECOMMENDED_ACTION') - activeIn('RECOMMENDED_ACTION')} resolved` : 'ready to approve'} />
                  <Metric icon="shield" label="High severity" value={highActive} tone={TONES.red} caption="active cards, team rubric" testid="tile-high" />
                  <Metric icon="queue" label="Model review flags" value={openQueue} tone={TONES.cyan} caption="open · view the queue" onClick={() => setTab('queue')} testid="tile-queue" />
                </section>

                {run.presentation && (() => {
                  const t = run.presentation.totals
                  return (
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-1 text-xs text-slate-500" data-testid="active-totals">
                      <span className="text-slate-300" data-testid="tile-active"><b className="tabular-nums text-white">{t.active_cards}</b> active cards covering <b className="tabular-nums text-white">{t.active_threads}</b> threads ({t.by_line.NEEDS_REVIEW} needs review, {t.by_line.RECOMMENDED_ACTION} recommended, {t.by_line.OBSERVATION} observation)</span>
                      <span data-testid="tile-history-threads">Processing history <b className="tabular-nums text-slate-300">{t.processing_history_threads}</b> threads</span>
                      <span data-testid="tile-queue-items">Review queue <b className="tabular-nums text-slate-300">{t.review_queue_items}</b> items</span>
                      <span data-testid="tile-records" title={t.card_records.note}>Card records in this run <b className="tabular-nums text-slate-300">{t.card_records.total}</b> (incl. {t.card_records.replaced_history} replaced, history; not active)</span>
                    </div>)
                })()}
                <div className={`${run.presentation ? 'hidden' : 'flex'} flex-wrap items-center gap-x-5 gap-y-1 px-1 text-xs text-slate-500`}>
                  <span data-testid="tile-cards">Cards <b className="tabular-nums text-slate-300">{counts.cards ?? 0}</b>
                    {run.briefing && <span data-testid="tile-in-brief"> · {run.briefing.in_briefing} in this brief{run.consolidation?.refreshed?.length ? ` (${run.consolidation.refreshed.length} combined issues)` : run.consolidation ? ` (${run.consolidation.pending.length} consolidated issues)` : ''} · {run.briefing.not_in_briefing.length + (run.processing_history?.length || 0)} kept in history</span>}</span>
                  <span data-testid="tile-failed" className={run.failed ? 'text-red-300' : ''}>Failed topics <b className="tabular-nums">{run.failed}</b></span>
                  <span data-testid="tile-unprocessed" className={run.unprocessed ? 'text-amber-200' : ''}>Unprocessed <b className="tabular-nums">{run.unprocessed}</b></span>
                  <span data-testid="tile-out-of-scope">Out of scope <b className="tabular-nums text-slate-300">{run.out_of_scope}</b></span>
                  <span title={`${counts.announcement_route_members} announcement-route members · ${counts.window_announcements} announcements in the window (${counts.window_announcements_in_snapshot} in the retrieval snapshot)`}>
                    {counts.discussion_members} discussion members ({counts.members_on_cards} on cards) · accounting {brief.accounting?.status?.toLowerCase()}
                  </span>
                </div>

                {brief.incomplete_work.length > 0 && (
                  <section className="rounded-xl border border-red-400/30 bg-red-500/[0.07] p-4" data-testid="incomplete-work">
                    <div className="flex items-center gap-2 text-sm font-semibold text-red-200"><Icon name="alert" />Incomplete work ({brief.incomplete_work.length}): members and review items are kept, but these topics have no card</div>
                    <ul className="mt-2 list-disc space-y-0.5 pl-6 text-sm text-red-100/90">
                      {brief.incomplete_work.map(w => <li key={w.work_id}><b>{words(w.outcome)}</b>: {w.topic_name || w.work_id}{w.failure_class ? ` (${w.failure_class})` : ''} - {w.detail || w.error}</li>)}
                    </ul>
                  </section>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                  <h2 className="eyebrow inline-flex items-center gap-2"><Icon name="layers" className="h-3.5 w-3.5" />Advice cards</h2>
                  <div className="inline-flex flex-wrap gap-1 rounded-xl border border-white/[0.06] bg-ink-950/50 p-1 text-xs" data-testid="line-filter">
                    {[['ALL', 'All', active.length], ...GROUPS.map(([line, label]) => [line, label, activeIn(line)])].map(([key, label, n]) => (
                      <button key={key} type="button" onClick={() => setLineFilter(key)} aria-pressed={lineFilter === key}
                        className={`rounded-lg px-3 py-1.5 font-medium transition ${lineFilter === key ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                        {label} <span className="ml-1 tabular-nums text-slate-500">{n}</span>
                      </button>
                    ))}
                  </div>
                </div>

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
                        {a.related_withheld.length > 0 && <div className="mt-1 text-[11px] text-slate-500">Not coordinated (proposal withheld): {a.related_withheld.map(w => w.topic_name).join('; ')}</div>}
                      </div>
                    ))}
                  </section>
                )}

                {consolidated.length > 0 && (
                  <section className="space-y-3" data-testid="consolidated-issues">
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100"><span className="h-2 w-2 rounded-full bg-violet-300" />Consolidated issues
                      <span className="font-normal text-slate-500">({consolidated.length}, fresh advice pending)</span></h3>
                    {consolidated.map(m => (
                      <details key={m.consolidated_topic_id} className="group panel-inset p-3" data-testid="consolidated-issue" data-consolidated-id={m.consolidated_topic_id}>
                        <summary className="cursor-pointer text-sm font-medium text-slate-200">{m.topic_name}
                          <span className="ml-2 text-xs font-normal text-slate-500">{m.cards.length} original topics · fresh advice pending{m.review_codes_carried.length ? ' · review reasons kept' : ''}</span></summary>
                        <div className="mt-2 text-xs leading-relaxed text-slate-400" data-testid="consolidated-basis">Same issue ({words(m.judgment_provenance)}): {m.rationale} The advice below belongs to each original topic.</div>
                        <div className="mt-3 grid gap-4 lg:grid-cols-2">
                          {m.cards.map(c => <CardView key={c.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={c} actor={actor} decisionState={byCard[c.card.card_id]} wide={m.cards.length === 1}
                            onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                        </div>
                      </details>
                    ))}
                  </section>
                )}

                {GROUPS.filter(([line]) => lineFilter === 'ALL' || lineFilter === line).map(([line, label, dot]) => {
                  const group = cards.filter(c => c.card.card_line === line)
                  const live = group.filter(c => !byCard[c.card.card_id])
                  const resolved = group.filter(c => byCard[c.card.card_id])
                  return (
                    <section key={line} data-testid={`group-${line}`} className="space-y-3">
                      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                        <span className={`h-2 w-2 rounded-full ${dot}`} />{label}
                        <span className="font-normal text-slate-500">({live.length} active{line !== 'OBSERVATION' ? `, ${resolved.length} resolved` : ''})</span>
                      </h3>
                      <div className="grid gap-4 lg:grid-cols-2" data-testid={`active-${line}`}>
                        <AnimatePresence initial={false}>
                          {live.map(c => <CardView key={c.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={c} actor={actor} decisionState={byCard[c.card.card_id]} wide={live.length === 1}
                            onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                        </AnimatePresence>
                        {live.length === 0 && <EmptyLine line={line} resolved={resolved.length} total={cards.length}
                          fixture={runs?.find(r => r.mode === 'TEST_FIXTURE' && r.run_key !== runKey)} onOpen={k => { setRunKey(k); setProject(''); setPanel(null) }} />}
                      </div>
                      {resolved.length > 0 && (
                        <details className="group panel-inset p-3" data-testid={`resolved-${line}`}>
                          <summary className="cursor-pointer text-sm font-medium text-slate-300">Resolved ({resolved.length}): out of the active worklist; original card, review reasons and evidence unchanged</summary>
                          <div className="mt-3 grid gap-4 lg:grid-cols-2">
                            {resolved.map(c => <CardView key={c.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={c} actor={actor} decisionState={byCard[c.card.card_id]} wide={resolved.length === 1}
                              onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                          </div>
                        </details>
                      )}
                    </section>
                  )
                })}

                {history.length > 0 && (
                  <details className="group panel-inset p-3" data-testid="not-in-brief">
                    <summary className="cursor-pointer text-sm font-medium text-slate-300">Not in this brief ({history.length}): social or routine exchanges kept in history</summary>
                    <div className="mt-3 grid gap-4 lg:grid-cols-2">
                      {history.map(c => <CardView key={c.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={c} actor={actor} decisionState={byCard[c.card.card_id]} wide={history.length === 1}
                        onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                    </div>
                  </details>
                )}

                {processed.length > 0 && (
                  <details className="group panel-inset p-3" data-testid="processing-history">
                    <summary className="cursor-pointer text-sm font-medium text-slate-300">Processing history ({processed.length}): kept out of issue clustering by Agent 1 relevance</summary>
                    <div className="mt-3 grid gap-4 lg:grid-cols-2">
                      {processed.map(c => <CardView key={c.card.card_id} runKey={runKey} run={run} openQueueItem={openQueueItem} item={c} actor={actor} decisionState={byCard[c.card.card_id]} wide={processed.length === 1}
                        onDecisionChanged={loadDecisions} openPanel={setPanel} />)}
                    </div>
                  </details>
                )}

                <div className="space-y-2 pt-2">
                  <Details summary="Saved briefing (from the run's morning_brief.md)" testid="briefing-details"><Briefing markdown={brief.briefing_markdown} /></Details>
                  {run.presentation?.stage_costs && (
                    <Details summary="Usage by stage (saved ledgers)" testid="stage-costs">
                      <table className="w-full text-left text-xs text-slate-300">
                        <thead><tr className="text-slate-500"><th className="py-1">Stage</th><th>Requests</th><th>Cost for this stage</th></tr></thead>
                        <tbody>{run.presentation.stage_costs.map(r => (
                          <tr key={r.stage} data-testid="stage-cost"><td className="py-1 pr-3">{r.stage}</td><td className="tabular-nums">{r.requests}</td>
                            <td className="tabular-nums">${r.charged_usd_exact != null ? `${r.charged_usd.toFixed(3)} (as reported)` : r.charged_usd.toFixed(4)}</td></tr>))}</tbody>
                      </table>
                      <p className="mt-2 text-xs text-slate-500">The full-pipeline total is from the campaign ledger; the other rows are later, separate stages.</p>
                    </Details>
                  )}
                  <Details summary={`Topic summary (${topics.length} work items${project ? ` in ${project}` : ''})`} testid="topics-details"><TopicTable rows={topics} /></Details>
                </div>
              </>
            )}
            {tab === 'queue' && <ReviewQueue runKey={runKey} rows={queueRows} actor={actor} onChanged={loadQueue} cardTopics={cardTopics} focus={focusItem} />}
          </>
        )}
      </main>
      <footer className="border-t border-white/[0.05] px-4 py-4 text-center text-[11px] text-slate-600" style={{ paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))' }}>
        ThreadSense · local dashboard without authentication · decisions are saved, never posted or executed
      </footer>
      {runKey && <SidePanel runKey={runKey} panel={panel} openPanel={setPanel} onClose={closePanel} />}
    </div>
  )
}
