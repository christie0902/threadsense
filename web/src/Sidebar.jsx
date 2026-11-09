import { useEffect, useRef } from 'react'
import { QUICK_FILTERS, briefingDate, runKind } from './briefView.js'
import { CopilotFigure, Icon, Orb } from './ui.jsx'

// Each quick filter as a selectable box: accent, and what it selects (structured fields, see briefView.QUICK).
const QUICK_STYLES = {
  ALL: ['bg-slate-300', 'every card in this tab'],
  PENDING_ACTIONS: ['bg-emerald-300', 'approvable recommendations'],
  NEEDS_REVIEW: ['bg-amber-300', 'review required'],
  OBSERVATIONS: ['bg-violet-300', 'no decision needed'],
  HIGH: ['bg-rose-400', 'team rubric'],
  UNASSESSED: ['bg-slate-400', 'not yet assessed'],
}

/** Runs grouped by the UTC day of their cutoff; several runs can share a day, so each option names its run. */
export function RunSelect({ runs, runKey, onSelect, className = 'field w-full text-sm' }) {
  const days = {}
  for (const r of runs || []) (days[briefingDate(r) || 'No cutoff recorded'] ||= []).push(r)
  return (
    <select id="run-select" className={className} value={runKey || ''} data-testid="run-select" onChange={e => onSelect(e.target.value)} aria-label="Briefing">
      {Object.entries(days).map(([day, list]) => (
        <optgroup key={day} label={`Source date ${day}`}>
          {list.map(r => <option key={r.run_key} value={r.run_key}>{r.run_key} · {runKind(r).label.toLowerCase()}</option>)}
        </optgroup>
      ))}
    </select>
  )
}

const TONES = {
  white: 'border-white/10 bg-white/[0.04] text-white',
  amber: 'border-amber-300/30 bg-amber-300/[0.08] text-amber-200',
  emerald: 'border-emerald-300/30 bg-emerald-300/[0.08] text-emerald-200',
  cyan: 'border-cyan-300/35 bg-cyan-300/[0.09] text-cyan-200',
  violet: 'border-violet-300/30 bg-violet-300/[0.08] text-violet-200',
}

/** One statistic in its own tile, so the number stands out. */
function Stat({ label, value, caption, testid, tone = 'white', icon, onClick, wide = false }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick} data-testid={testid}
      className={`rounded-xl border p-4 text-left ${TONES[tone]} ${wide ? 'col-span-2' : ''} ${onClick ? 'transition hover:-translate-y-px hover:border-white/25' : ''}`}>
      <span className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium leading-4 text-slate-200">{label}</span>
        {icon && <Icon name={icon} className="h-4 w-4 shrink-0 opacity-90" />}
      </span>
      <span className={`mt-2 block font-display text-3xl font-semibold leading-none tabular-nums ${value ? '' : 'text-slate-400'}`}>{value}</span>
      {caption && <span className="mt-2 block text-xs leading-4 text-slate-300">{caption}</span>}
    </Tag>
  )
}

/**
 * Processing status from the run's own accounting (developer details). COMPLETE covers the members handed to advice;
 * threads that never reached that handoff (for example an Agent 1 rejection) are outside it, so a gap is shown.
 */
export function Health({ run, counts, accounting, incomplete }) {
  const members = counts?.discussion_members
  const inWindow = run.handoff_activity?.discussion_threads_in_window
  const gap = inWindow != null && members != null ? inWindow - members : 0
  const status = accounting?.status
  const tone = run.failed || status !== 'COMPLETE' ? 'bg-rose-400' : gap > 0 || run.unprocessed || incomplete ? 'bg-amber-300' : 'bg-emerald-300'
  return (
    <section className="space-y-1 text-xs leading-5 text-slate-300" data-testid="processing-health">
      <div className="flex items-center gap-2 font-semibold text-slate-100"><span className={`h-2 w-2 rounded-full ${tone}`} />Processing</div>
      <p data-testid="health-accounting">Accounting {String(status || 'not recorded').toLowerCase()}
        {members != null ? ` for the ${members} discussion members handed to advice` : ''}.</p>
      {gap > 0 && <p className="text-amber-200" data-testid="health-gap">{inWindow} discussion threads were in the window; {gap} {gap === 1 ? 'is' : 'are'} outside this accounting (not handed to advice).</p>}
      {(run.failed > 0 || run.unprocessed > 0) && <p className="text-rose-200">{run.failed} failed · {run.unprocessed} unprocessed work items.</p>}
    </section>
  )
}

export default function Sidebar({ run, session, stats, quick, onQuick, quickCounts, tab, onOpenQueue, open, onClose }) {
  const closeRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    closeRef.current?.focus()
    const onKey = e => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  const name = session?.name || session?.actor_id

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside id="sidebar" aria-label="Briefing navigation" data-testid="sidebar"
        className={`${open ? 'fixed inset-y-0 left-0 z-40 flex w-[min(22rem,90vw)] shadow-2xl shadow-black' : 'hidden'} sidebar-scroll flex-col gap-6 overflow-y-auto border-r border-white/[0.08] bg-gradient-to-b from-ink-800 via-ink-850 to-ink-900 px-6 lg:sticky lg:top-0 lg:z-auto lg:flex lg:h-screen lg:w-auto lg:shadow-none`}
        style={{ paddingTop: 'calc(1.5rem + env(safe-area-inset-top, 0px))', paddingBottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))' }}>
        <div className="flex items-center gap-3">
          <Orb className="h-9 w-9" />
          <span className="font-display text-xl font-semibold tracking-tight text-white">Thread<span className="text-cyan-300">Sense</span></span>
          <button ref={closeRef} type="button" className="btn btn-sm ml-auto lg:hidden" onClick={onClose} aria-label="Close the briefing menu"><Icon name="close" className="h-3.5 w-3.5" /></button>
        </div>

        <div data-testid="copilot">
          <div className="relative flex justify-center">
            <div className="pointer-events-none absolute inset-x-6 top-6 h-32 rounded-full bg-cyan-300/15 blur-3xl" aria-hidden="true" />
            <CopilotFigure className="h-44" />
          </div>
          <div className="panel mt-4 px-4 py-4 text-center">
            <div className="font-display text-lg font-semibold text-white">AI Co-pilot</div>
            <p className="mt-1 text-sm leading-6 text-slate-200" data-testid="greeting">
              Good morning{name ? `, ${name}` : ''}.{run && <span className="block text-slate-300">Your briefing for {briefingDate(run) || 'this run'} is ready.</span>}
            </p>
          </div>
        </div>

        {stats && (
          <section className="panel p-4" aria-labelledby="stats-heading" data-testid="briefing-stats">
            <h2 id="stats-heading" className="text-base font-semibold text-slate-100">Selected briefing</h2>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <Stat testid="stat-in-brief" wide icon="layers" label="Cards in this briefing" value={stats.inBrief}
                caption={`${stats.byLine.NEEDS_REVIEW} needs review · ${stats.byLine.RECOMMENDED_ACTION} recommended · ${stats.byLine.OBSERVATION} observation`} />
              {stats.consolidatedIssues > 0 && (
                <Stat testid="stat-consolidated" wide tone="violet" label="Consolidated issues" value={stats.consolidatedIssues}
                  caption={`fresh advice pending · ${stats.consolidatedPending} original cards kept inside`} />
              )}
              <Stat testid="stat-awaiting" tone="amber" icon="alert" label="Awaiting decision" value={stats.awaitingDecision}
                caption={`incl. ${stats.pendingActions} pending ${stats.pendingActions === 1 ? 'action' : 'actions'} to approve`} />
              <Stat testid="stat-reviewed" tone="emerald" icon="check" label="Reviewed" value={stats.reviewed} caption="decision saved; execution not recorded" />
              <Stat testid="stat-model-review" wide tone="cyan" icon="queue" label="Model-review items open" value={stats.modelReviewOpen}
                caption={`of ${stats.modelReviewTotal} · separate from card decisions · open the queue`} onClick={onOpenQueue} />
            </div>
            {Boolean(stats.notInBrief + stats.processingHistory + (stats.replacedRecords || 0)) && (
              <div className="mt-3 text-xs leading-5 text-slate-300" data-testid="stat-history">
                History, not counted above: {[stats.notInBrief && `${stats.notInBrief} not in this brief`, stats.processingHistory && `${stats.processingHistory} processing history`,
                  stats.replacedRecords && `${stats.replacedRecords} replaced records (lineage only)`].filter(Boolean).join(' · ')}.
              </div>
            )}
            {run?.presentation?.totals && run.presentation.totals.active_cards !== stats.inBrief && (
              <div className="mt-3 text-xs text-amber-200" data-testid="stat-mismatch">The saved presentation layer lists {run.presentation.totals.active_cards} active cards; the dashboard counts {stats.inBrief}.</div>
            )}
          </section>
        )}

        {quickCounts && (
          <nav className="panel p-4" aria-labelledby="quick-heading" data-testid="quick-filters">
            <h2 id="quick-heading" className="text-base font-semibold text-slate-100">Quick filters <span className="text-sm font-normal text-slate-300">({tab === 'REVIEWED' ? 'reviewed' : 'active'})</span></h2>
            <ul className="mt-4 space-y-2">
              {Object.entries(QUICK_FILTERS).map(([key, label]) => {
                const [dot, caption] = QUICK_STYLES[key]
                const on = quick === key
                return (
                  <li key={key}>
                    <button type="button" aria-pressed={on} data-testid={`quick-${key}`} onClick={() => onQuick(key)}
                      className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition ${on ? 'border-cyan-300/60 bg-cyan-300/[0.12] text-white' : 'border-white/10 bg-white/[0.03] text-slate-200 hover:border-white/20 hover:bg-white/[0.06]'}`}>
                      <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border ${on ? 'border-cyan-200' : 'border-slate-400'}`} aria-hidden="true">
                        {on && <span className="h-2 w-2 rounded-full bg-cyan-200" />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2 text-sm font-medium leading-5"><span className={`h-1.5 w-1.5 rounded-full ${dot}`} />{label}</span>
                        <span className="block text-xs leading-5 text-slate-300">{caption}</span>
                      </span>
                      <span className={`font-display text-lg font-semibold leading-5 tabular-nums ${quickCounts[key] ? (on ? 'text-cyan-100' : 'text-white') : 'text-slate-400'}`}>{quickCounts[key]}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </nav>
        )}

        <div className="mt-auto">
          {session !== undefined && (
            <div className={`flex items-center gap-3 rounded-full border py-1.5 pl-1.5 pr-4 ${session ? 'border-white/10 bg-white/[0.05]' : 'border-rose-400/40 bg-rose-500/10'}`}
              data-testid="session-user" title={session ? 'Signed in for this local session. The identity is fixed by the server.' : undefined}>
              <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-semibold ${session ? 'bg-gradient-to-br from-cyan-200 to-indigo-300 text-ink-950' : 'bg-rose-400/20 text-rose-200'}`}>
                {session ? (session.name || session.actor_id).slice(0, 1) : '!'}
              </span>
              <span className="leading-tight">
                <span className="block text-sm font-medium text-white">{session ? `${session.name || session.actor_id}` : 'No team-lead session'}</span>
                <span className="flex items-center gap-1 text-xs text-slate-300">{session ? <><Icon name="lock" className="h-3 w-3" />Team lead · {session.actor_id}</> : 'Decisions disabled'}</span>
              </span>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
