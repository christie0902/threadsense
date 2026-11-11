import { useCallback, useEffect, useMemo, useState } from 'react'
import { getJSON, useIdempotentSave } from './api.js'
import { Badge, Icon, when } from './ui.jsx'

// AI-quality feedback (dashboard/feedback.py). Kept apart from the operational decision: Accept/Reject/Defer and the
// card decisions never create feedback, and feedback never changes a decision, a review item or a card.
const STATE_TONES = { SUBMITTED: 'amber', CONFIRMED: 'emerald', WITHDRAWN: 'neutral', SUPERSEDED: 'neutral' }
const STATE_LABELS = { SUBMITTED: 'Submitted, not confirmed', CONFIRMED: 'Confirmed', WITHDRAWN: 'Withdrawn', SUPERSEDED: 'Superseded' }
const PROBLEM_LABELS = { MISSING: 'Missing', IRRELEVANT: 'Irrelevant', OUTDATED: 'Outdated', UNSUPPORTED: 'Unsupported', IMPRACTICAL: 'Impractical' }
const WITHHELD = {
  CITED_SOURCE_NOT_CURRENT: 'its cited source is no longer current',
  CONFLICTING_CORRECTIONS: 'it conflicts with another confirmed correction',
  PER_TOPIC_LIMIT: 'more corrections matched than one topic may receive',
}
const FUTURE_NOTE = 'Advisory context only: a later run on the same threads receives it as a labelled reviewer note. It does not edit source documents, prompts, rules or this card, and it executes nothing. A team lead must confirm it first.'
const short = (s, n = 90) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '')

function targetLabel(t) {
  if (t.kind === 'CARD') return 'The whole card'
  if (t.kind === 'STATEMENT') return `Statement ${t.id}${t.earlier_verdict ? ` (verifier: ${t.earlier_verdict.toLowerCase().replaceAll('_', ' ')})` : ''}`
  return `Review item ${t.id.slice(0, 15)}…`
}

function Saved({ state, reset, onChanged, what }) {
  if (state.phase === 'saving') return <div className="text-xs text-slate-400">Saving…</div>
  if (state.phase === 'uncertain') return <div className="text-xs text-amber-200" data-testid="feedback-uncertain">Not confirmed; the {what} may or may not be saved. Repeat the same action: it reuses the request key and cannot be saved twice.</div>
  if (state.phase === 'conflict') return <div className="text-xs text-red-300">Not saved: this report changed meanwhile. <button type="button" className="link" onClick={() => { reset(); onChanged() }}>Refresh</button></div>
  if (state.phase === 'rejected') return <div className="text-xs text-red-300" data-testid="feedback-rejected">Not saved: {state.detail}</div>
  return null
}

function HistoryEntry({ runKey, view, actor, onChanged }) {
  const r = view.report
  const { state, save, reset } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/feedback/${view.feedback_id}/actions`)
  const act = async action => { if (await save({ action, actor_id: actor, expected_head: view.head.entry_id, note: null })) onChanged() }
  return (
    <li className="rounded-xl border border-white/[0.07] bg-ink-950/40 p-3.5" data-testid="feedback-entry" data-feedback-id={view.feedback_id} data-state={view.state}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={STATE_TONES[view.state]} data-testid="feedback-state">{STATE_LABELS[view.state]}</Badge>
        <Badge tone="cyan">{r.category_label}</Badge>
        {r.problem && <Badge>{PROBLEM_LABELS[r.problem] || r.problem}</Badge>}
        <span className="text-xs text-slate-400">{targetLabel(r.target)}</span>
      </div>
      {r.target.kind === 'STATEMENT' && <div className="quote mt-2 text-xs">{r.target.earlier_text}</div>}
      <div className="mt-2 text-sm text-slate-200"><span className="text-slate-400">What is wrong: </span>{r.what_is_wrong}</div>
      {r.suggested_correction && <div className="mt-1 text-sm text-slate-200"><span className="text-slate-400">Correction: </span>{r.suggested_correction}</div>}
      {r.source_refs.length > 0 && <div className="mt-1 text-xs text-slate-400">Sources: {r.source_refs.map(x => x.ref).join(', ')}</div>}
      <div className={`mt-2 text-xs ${view.eligible_for_future_runs ? 'text-emerald-200' : 'text-slate-400'}`} data-testid="feedback-eligibility">
        {view.eligible_for_future_runs ? <><Icon name="check" className="mr-1 inline h-3.5 w-3.5" />Eligible for future runs (advisory context, scoped to {r.scope.threads.length} thread{r.scope.threads.length === 1 ? '' : 's'} in {r.scope.project_id})</> : view.eligibility}
      </div>
      <ol className="mt-2 space-y-0.5 text-xs text-slate-400" data-testid="feedback-events">
        {view.events.map(e => <li key={e.entry_id}>{when(e.recorded_at)} · {e.actor_id || 'system'}: <b className="text-slate-200">{e.event_type.toLowerCase()}</b>{e.note ? ` - ${e.note}` : ''}</li>)}
      </ol>
      {(view.state === 'SUBMITTED' || view.state === 'CONFIRMED') && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {view.state === 'SUBMITTED' && (
            <button type="button" className="btn btn-sm" disabled={!actor || state.phase === 'saving'} onClick={() => act('CONFIRM')} data-testid="feedback-confirm"
              title="Confirm that this report is correct. An opted-in correction then becomes eligible for later reviewer-feedback snapshots.">Confirm report</button>
          )}
          <button type="button" className="btn btn-sm" disabled={!actor || state.phase === 'saving'} onClick={() => act('WITHDRAW')} data-testid="feedback-withdraw">Withdraw</button>
          <Saved state={state} reset={reset} onChanged={onChanged} what="action" />
        </div>
      )}
    </li>
  )
}

function ReportForm({ runKey, cardId, data, actor, onSaved }) {
  const { targets, categories, problems, limits } = data
  const [category, setCategory] = useState('')
  const [problem, setProblem] = useState('')
  const [target, setTarget] = useState('CARD:')
  const [wrong, setWrong] = useState('')
  const [correction, setCorrection] = useState('')
  const [refs, setRefs] = useState('')
  const [threads, setThreads] = useState(() => targets.threads.length <= limits.max_scope_threads ? targets.threads.map(t => t.key) : [])
  const [future, setFuture] = useState(false)
  const [supersedes, setSupersedes] = useState('')
  const { state, save, reset } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/cards/${cardId}/feedback`)
  const [kind, id] = [target.split(':')[0], target.slice(target.indexOf(':') + 1)]
  const cardLevel = kind === 'CARD'
  const blockers = [
    correction.trim().length < limits.min_correction && `write the correction (at least ${limits.min_correction} characters)`,
    cardLevel && threads.length === 0 && 'choose the threads it applies to',
    cardLevel && threads.length > limits.max_scope_threads && `choose at most ${limits.max_scope_threads} threads`,
  ].filter(Boolean)
  useEffect(() => { if (blockers.length && future) setFuture(false) }, [blockers.length, future])
  const replaceable = data.history.filter(v => v.state === 'SUBMITTED' || v.state === 'CONFIRMED')
  const change = setter => e => { setter(e.target.value); reset() }
  const submit = async e => {
    e.preventDefault()
    const entry = await save({
      actor_id: actor, category, problem: problems[category] && problem ? problem : null, target_kind: kind, target_id: cardLevel ? null : id,
      what_is_wrong: wrong.trim(), suggested_correction: correction.trim() || null,
      source_refs: refs.split(/[\s,]+/).map(s => s.trim()).filter(Boolean),
      scope_threads: cardLevel ? threads : null, use_in_future_runs: future, supersedes_feedback_id: supersedes || null,
    })
    if (entry) { setWrong(''); setCorrection(''); setRefs(''); setFuture(false); setSupersedes(''); onSaved() }
  }
  return (
    <form onSubmit={submit} className="space-y-3" data-testid="feedback-form">
      <p className="text-xs leading-relaxed text-slate-400">
        Tell us which AI output is wrong. This is separate from your decision on the card: agreeing, rejecting or deferring never
        records AI feedback, and a report here changes no decision.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-slate-300">Category
          <select className="field mt-1 w-full" value={category} onChange={change(setCategory)} required data-testid="feedback-category">
            <option value="" disabled>Choose…</option>
            {Object.entries(categories).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </label>
        {problems[category] ? (
          <label className="block text-xs text-slate-300">Kind of problem (optional)
            <select className="field mt-1 w-full" value={problem} onChange={change(setProblem)} data-testid="feedback-problem">
              <option value="">Not specified</option>
              {problems[category].map(p => <option key={p} value={p}>{PROBLEM_LABELS[p]}</option>)}
            </select>
          </label>
        ) : <div className="hidden sm:block" />}
      </div>
      <label className="block text-xs text-slate-300">Affected output
        <select className="field mt-1 w-full" value={target} onChange={change(setTarget)} data-testid="feedback-target">
          <option value="CARD:">The whole card</option>
          {targets.statements.length > 0 && (
            <optgroup label="Statements on this card">
              {targets.statements.map(s => <option key={s.id} value={`STATEMENT:${s.id}`}>{s.id} · {short(s.text, 70)}{s.verdict ? ` · ${s.verdict.toLowerCase().replaceAll('_', ' ')}` : ''}</option>)}
            </optgroup>
          )}
          {targets.review_items.length > 0 && (
            <optgroup label="Review findings about this card">
              {targets.review_items.map(i => <option key={i.id} value={`REVIEW_ITEM:${i.id}`}>{short(i.reason, 80)}</option>)}
            </optgroup>
          )}
        </select>
      </label>
      {cardLevel ? (
        <fieldset className="text-xs text-slate-300" data-testid="feedback-threads">
          <legend>Threads it applies to (at most {limits.max_scope_threads} for future use)</legend>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
            {targets.threads.map(t => (
              <label key={t.key} className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={threads.includes(t.key)} onChange={e => { setThreads(e.target.checked ? [...threads, t.key] : threads.filter(k => k !== t.key)); reset() }} />
                <span className="font-mono text-[11px] text-slate-300">{t.key}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : <div className="text-xs text-slate-400">Scope: the threads this {kind === 'STATEMENT' ? 'statement cites' : 'finding is about'}.</div>}
      <label className="block text-xs text-slate-300">What is wrong
        <textarea className="field mt-1 min-h-[4.5rem] w-full" maxLength={limits.max_text} value={wrong} onChange={change(setWrong)} required data-testid="feedback-wrong" />
      </label>
      <label className="block text-xs text-slate-300">Suggested correction (optional)
        <textarea className="field mt-1 min-h-[4.5rem] w-full" maxLength={limits.max_text} value={correction} onChange={change(setCorrection)} data-testid="feedback-correction" />
      </label>
      <label className="block text-xs text-slate-300">Supporting source references (optional; evidence IDs such as m:C_AUDIO_QA:1790864427.000131)
        <input className="field mt-1 w-full" value={refs} onChange={change(setRefs)} data-testid="feedback-refs" />
      </label>
      {replaceable.length > 0 && (
        <label className="block text-xs text-slate-300">Replaces an earlier report (optional; it is superseded once this one is confirmed)
          <select className="field mt-1 w-full" value={supersedes} onChange={change(setSupersedes)} data-testid="feedback-supersedes">
            <option value="">None</option>
            {replaceable.map(v => <option key={v.feedback_id} value={v.feedback_id}>{v.report.category_label}: {short(v.report.what_is_wrong, 60)}</option>)}
          </select>
        </label>
      )}
      <div className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-3">
        <label className={`inline-flex items-start gap-2 text-sm ${blockers.length ? 'text-slate-400' : 'text-slate-100'}`}>
          <input type="checkbox" className="mt-0.5" checked={future} disabled={blockers.length > 0} onChange={e => { setFuture(e.target.checked); reset() }} data-testid="feedback-future" />
          Use this correction in future runs
        </label>
        <div className="mt-1 text-xs leading-relaxed text-slate-400">{blockers.length ? `To enable: ${blockers.join('; ')}.` : FUTURE_NOTE}</div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn-primary" disabled={!actor || !category || !wrong.trim() || state.phase === 'saving'} data-testid="feedback-submit">Submit report</button>
        {state.phase === 'saved' && <span className="text-xs text-emerald-200" data-testid="feedback-saved">Report saved. It is not used anywhere until a team lead confirms it.</span>}
        <Saved state={state} reset={reset} onChanged={onSaved} what="report" />
      </div>
    </form>
  )
}

function ReviewerContext({ context }) {
  if (!context || !(context.sent.length || context.withheld.length)) return null
  return (
    <div className="rounded-xl border border-cyan-400/25 bg-cyan-400/[0.05] p-3.5" data-testid="reviewer-context">
      <div className="text-xs font-semibold uppercase tracking-wide text-cyan-200">Reviewer corrections this card's model input included</div>
      <p className="mt-1 text-xs text-slate-400">Given to the model as labelled advisory context (not evidence, not policy), from snapshot {context.snapshot_sha256.slice(0, 12)}. This shows what was sent, not that it changed the card.</p>
      <ul className="mt-2 space-y-2">
        {context.sent.map(x => (
          <li key={x.feedback_id} className="text-sm text-slate-200" data-testid="reviewer-context-sent">
            <Badge tone="cyan">{x.category.toLowerCase().replaceAll('_', ' ')}</Badge>
            <span className="ml-2">{x.correction || x.feedback_id}</span>
            <div className="mt-0.5 text-xs text-slate-400">Confirmed {when(x.confirmed_at)} by {x.confirmed_by} · threads {x.applies_to_threads.join(', ')} · from {x.origin.run_key}{x.state_now && x.state_now !== 'CONFIRMED' ? ` · now ${x.state_now.toLowerCase()}` : ''}</div>
          </li>
        ))}
      </ul>
      {context.withheld.length > 0 && (
        <div className="mt-2 text-xs text-amber-200" data-testid="reviewer-context-withheld">
          Not sent, needs review: {context.withheld.map(w => `${w.feedback_id.slice(0, 17)}… (${WITHHELD[w.reason] || w.reason})`).join('; ')}
        </div>
      )}
    </div>
  )
}

/** "Report an AI issue" on an opened card, with this card's feedback history and any reviewer context it received. */
export default function FeedbackPanel({ runKey, cardId, actor }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    getJSON(`/api/runs/${encodeURIComponent(runKey)}/cards/${cardId}/feedback`)
      .then(d => setData({ ...d, history: d.history.map(v => ({ ...v, report: { ...v.report, category_label: d.categories[v.report.category] } })) }))
      .catch(e => setError(String(e.message)))
  }, [runKey, cardId])
  useEffect(load, [load])
  if (error) return <div className="text-xs text-red-300">AI feedback could not be loaded: {error}</div>
  if (!data) return null
  return (
    <section className="space-y-3" data-testid="ai-feedback">
      <ReviewerContext context={data.reviewer_context} />
      {data.history.length > 0 && (
        <div>
          <div className="eyebrow">AI feedback on this card ({data.history.length})</div>
          <ul className="mt-2 space-y-2">{data.history.map(v => <HistoryEntry key={v.feedback_id} runKey={runKey} view={v} actor={actor} onChanged={load} />)}</ul>
        </div>
      )}
      <details className="group panel-inset" data-testid="report-ai-issue">
        <summary className="flex cursor-pointer select-none list-none items-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white [&::-webkit-details-marker]:hidden">
          <Icon name="chevron" className="h-3.5 w-3.5 text-slate-400 transition group-open:rotate-90" />Report an AI issue
        </summary>
        <div className="border-t border-white/[0.06] p-3"><ReportForm runKey={runKey} cardId={cardId} data={data} actor={actor} onSaved={load} /></div>
      </details>
    </section>
  )
}

/** Workflow counts and the run's feedback list for the review tab. Counts are not accuracy. */
export function RunFeedback({ runKey, cardTopics }) {
  const [data, setData] = useState(null)
  useEffect(() => { getJSON(`/api/runs/${encodeURIComponent(runKey)}/feedback`).then(setData).catch(() => setData(null)) }, [runKey])
  const c = data?.counts
  const items = useMemo(() => data?.items || [], [data])
  if (!c) return null
  return (
    <div className="panel-inset p-3.5" data-testid="run-feedback">
      <div className="text-sm text-slate-200" data-testid="feedback-counts">
        AI feedback on this run: <b>{c.submitted}</b> report{c.submitted === 1 ? '' : 's'} · <b>{c.confirmed}</b> confirmed ·{' '}
        <b>{c.eligible_for_future_runs}</b> eligible for future runs · <b>{c.corrections_used_by_this_run}</b> reviewer correction{c.corrections_used_by_this_run === 1 ? '' : 's'} used by this run
      </div>
      <div className="mt-0.5 text-xs text-slate-400">Workflow counts, not accuracy. Report issues from an opened card's "Report an AI issue" section.</div>
      {items.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-300">
          {items.map(v => (
            <li key={v.feedback_id} data-testid="run-feedback-item">
              <Badge tone={STATE_TONES[v.state]}>{STATE_LABELS[v.state]}</Badge> <span className="ml-1">{v.report.category.toLowerCase().replaceAll('_', ' ')}</span>
              <span className="text-slate-400"> · {cardTopics[v.report.card_id] || v.report.topic_name} · {v.eligible_for_future_runs ? 'eligible for future runs' : v.eligibility}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
