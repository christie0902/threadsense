import { useMemo, useState } from 'react'
import { useIdempotentSave } from './api.js'
import { Badge, CopyButton, textOriginLabel, when } from './ui.jsx'

export const KIND_LABELS = {
  APPROVE_ACTION: 'Approved the recommended action', CONFIRM_FAQ_UPDATE: 'Confirmed an FAQ update',
  CONFIRM_ANNOUNCEMENT: 'Confirmed an announcement', OVERRIDE_SEVERITY: 'Overrode the severity', DISMISS: 'Dismissed',
  ROUTE_TO_EXPERT: 'Routed to an expert',
}
const RESOLUTIONS = {
  CONFIRM_FAQ_UPDATE: { label: 'Confirm FAQ update', action: 'UPDATE_FAQ' },
  CONFIRM_ANNOUNCEMENT: { label: 'Confirm announcement', action: 'POST_ALIGNMENT' },
  OVERRIDE_SEVERITY: { label: 'Override severity' },
  DISMISS: { label: 'Dismiss' },
  ROUTE_TO_EXPERT: { label: 'Route to an expert' },
}
const EXPERT_ACTIONS = { ENGINEERING: 'ESCALATE_ENGINEERING', LANGUAGE_SPECIALIST: 'ROUTE_TO_LANGUAGE_SPECIALIST' }
const KIND_NOTES = {
  APPROVE_ACTION: 'Approval records your decision. Nothing is posted or executed; copy the draft and post it yourself.',
  CONFIRM_FAQ_UPDATE: 'Confirms the FAQ change. The FAQ itself is not edited, and the change does not become current guidance automatically.',
  CONFIRM_ANNOUNCEMENT: 'Confirms the announcement text. Nothing is posted; copy it and post it yourself.',
  OVERRIDE_SEVERITY: 'Recorded as your decision for this card only. The team rubric is unchanged.',
  DISMISS: 'A review disposition. It is not evidence that the underlying issue is resolved.',
  ROUTE_TO_EXPERT: 'Records that this should go to an expert. Nobody is contacted automatically.',
}

export function DecisionSummary({ entry, indexing, current = true }) {
  const d = entry.decision
  const text = entry.text.origin === 'MODEL_GROUNDED' ? entry.text.model_grounded_text : entry.text.tl_text
  const override = d.tl_response.severity_override
  const idx = indexing?.[entry.entry_id]
  return (
    <div className={`rounded border p-3 text-sm ${current ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white opacity-80'}`}
      data-testid={current ? 'decision-current' : 'decision-history-entry'}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold" data-testid="decision-kind">{KIND_LABELS[entry.kind]}</span>
        {entry.expert && <Badge className="border-slate-300 bg-white">{entry.expert.replace('_', ' ').toLowerCase()}</Badge>}
        {!current && <Badge className="border-slate-300 bg-slate-100">superseded by a later decision</Badge>}
      </div>
      <div className="mt-1 text-xs text-slate-600">
        Saved {when(entry.recorded_at)} by {entry.actor_id} (team lead) · decision #{entry.sequence}
      </div>
      <div className="mt-1 text-xs text-slate-700" data-testid="decision-states">
        Execution: <b>not executed</b> · Outcome: <b>not observed</b>
      </div>
      {override && <div className="mt-2 text-xs">Severity for this card: assessed <b>{override.proposed}</b>, team lead selected <b>{override.tl_selected}</b> (the rubric is unchanged).</div>}
      {entry.note && <div className="mt-2 text-xs"><span className="font-medium">Note:</span> {entry.note}</div>}
      {text && (
        <div className="mt-2">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
            <Badge className={entry.text.origin === 'MODEL_GROUNDED' ? 'border-emerald-400 bg-white text-emerald-800' : 'border-violet-400 bg-violet-50 text-violet-800'}
              data-testid="text-origin">{textOriginLabel(entry.text.origin)}</Badge>
            {entry.text.grounded_source === 'SUPPORTED_ALTERNATIVE' && <Badge className="border-slate-300 bg-white">from a supported alternative</Badge>}
            <CopyButton text={text} what="text" />
          </div>
          <div className="prose-pre rounded border border-slate-200 bg-white p-2 text-sm" data-testid="decision-text">{text}</div>
          {entry.text.origin === 'TL_EDITED' && (
            <details className="mt-1 text-xs"><summary className="cursor-pointer text-slate-600">Model-grounded draft before your edit</summary>
              <div className="prose-pre mt-1 rounded bg-slate-50 p-2">{entry.text.model_grounded_text}</div></details>
          )}
        </div>
      )}
      <div className="mt-2 text-xs text-slate-600">{KIND_NOTES[entry.kind]}</div>
      {idx && <div className="mt-1 text-[11px] text-slate-500" data-testid="indexing-status">
        Retrieval: {idx.status === 'PENDING' ? 'saved, not yet in a retrieval snapshot' : idx.status === 'INDEXED' ? `in snapshot ${idx.snapshot}` : `indexing failed (${idx.error}); the decision itself is saved`}
      </div>}
    </div>
  )
}

function SaveStatus({ state, onRetry, onShowLatest }) {
  if (state.phase === 'saving') return <div className="text-xs text-slate-600" data-testid="save-status">Saving…</div>
  if (state.phase === 'uncertain') return (
    <div className="rounded border border-amber-400 bg-amber-50 p-2 text-xs text-amber-900" data-testid="save-uncertain">
      Not confirmed: the connection failed before the server answered, so this decision may or may not be saved.
      Retrying is safe: it reuses the same request key, so it cannot be saved twice.
      <button type="button" className="ml-2 rounded bg-amber-600 px-2 py-0.5 text-white" onClick={onRetry}>Retry safely</button>
    </div>
  )
  if (state.phase === 'conflict') return (
    <div className="rounded border border-red-300 bg-red-50 p-2 text-xs text-red-900" data-testid="save-conflict">
      Not saved: another decision was recorded on this card since you opened it
      {state.current ? ` (${KIND_LABELS[state.current.kind]} by ${state.current.actor_id}, ${when(state.current.recorded_at)})` : ''}.
      Review it before deciding again.
      <button type="button" className="ml-2 rounded bg-red-700 px-2 py-0.5 text-white" onClick={onShowLatest}>Show the latest decision</button>
    </div>
  )
  if (state.phase === 'rejected') return <div className="rounded border border-red-300 bg-red-50 p-2 text-xs text-red-900" data-testid="save-rejected">Not saved: {state.detail}</div>
  return null
}

/** Text source choices for a resolution: the card's own draft and supported alternatives with the same action. */
function textSources(card, alternatives, actionType) {
  const out = []
  const own = card.recommended_action
  if (own?.draft_text && own.action_type === actionType) out.push({ id: '', label: 'Card draft', text: own.draft_text })
  for (const a of alternatives) if (a.action_type === actionType && a.draft_text) out.push({ id: a.candidate_id, label: `Supported alternative: ${a.label}`, text: a.draft_text })
  return out
}

export default function DecisionPanel({ runKey, card, alternatives, allowed, actor, state, onChanged }) {
  const head = state?.head || null
  const [revising, setRevising] = useState(false)
  if (!allowed.length) return <div className="text-xs text-slate-500">Observations need no decision.</div>
  if (head && !revising) {
    const older = state.decisions.slice(0, -1).reverse()
    return (
      <div className="space-y-2" data-testid="decision-area">
        <DecisionSummary entry={head} indexing={state.indexing} />
        {older.length > 0 && <details className="text-xs"><summary className="cursor-pointer text-slate-600">Earlier decisions ({older.length})</summary>
          <div className="mt-2 space-y-2">{older.map(e => <DecisionSummary key={e.entry_id} entry={e} indexing={state.indexing} current={false} />)}</div></details>}
        <button type="button" className="text-xs text-sky-700 underline" onClick={() => setRevising(true)}>Record a new decision (supersedes this one)</button>
      </div>
    )
  }
  return <DecisionForm key={head?.entry_id || 'first'} runKey={runKey} card={card} alternatives={alternatives} allowed={allowed}
    actor={actor} head={head} onCancel={head ? () => setRevising(false) : null}
    onDone={() => { setRevising(false); onChanged() }} />
}

function DecisionForm({ runKey, card, alternatives, allowed, actor, head, onCancel, onDone }) {
  const { state, save } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/cards/${card.card_id}/decisions`)
  const [kind, setKind] = useState(allowed.length === 1 ? allowed[0] : '')
  const [open, setOpen] = useState(false)
  const [expert, setExpert] = useState('ENGINEERING')
  const [severity, setSeverity] = useState('')
  const [note, setNote] = useState('')
  const actionType = kind === 'APPROVE_ACTION' ? card.recommended_action?.action_type
    : kind === 'ROUTE_TO_EXPERT' ? EXPERT_ACTIONS[expert] : RESOLUTIONS[kind]?.action
  const sources = useMemo(() => kind && !['OVERRIDE_SEVERITY', 'DISMISS'].includes(kind)
    ? textSources(card, alternatives, actionType) : [], [kind, actionType, card, alternatives])
  const [sourceId, setSourceId] = useState(null)
  const chosen = sources.find(s => s.id === sourceId) || sources[0] || null
  const [edits, setEdits] = useState({})
  const editKey = `${kind}|${chosen?.id ?? 'none'}`
  const text = edits[editKey] ?? (chosen?.text || '')
  const textRequired = ['CONFIRM_FAQ_UPDATE', 'CONFIRM_ANNOUNCEMENT'].includes(kind) && !chosen
  const changed = chosen ? text !== chosen.text : text.trim() !== ''
  const noteRequired = kind === 'OVERRIDE_SEVERITY' || kind === 'DISMISS'
  const ready = kind && actor && (!noteRequired || note.trim()) && (!textRequired || text.trim())
    && (kind !== 'OVERRIDE_SEVERITY' || severity) && !(chosen && !text.trim())

  if (state.phase === 'saved') {
    return (
      <div className="space-y-2" data-testid="decision-area">
        <div className="rounded border border-emerald-400 bg-emerald-100 p-2 text-xs text-emerald-900" data-testid="save-success">
          Saved{state.replayed ? ' (the server already had this exact request; no duplicate was created)' : ''}. {KIND_NOTES[state.entry.kind]}
        </div>
        <DecisionSummary entry={state.entry} />
        <button type="button" className="text-xs text-sky-700 underline" onClick={onDone}>Done (move to resolved)</button>
      </div>
    )
  }
  const body = () => ({
    kind, actor_id: actor, expected_head: head?.entry_id || null, note: note.trim() || null,
    text: kind === 'OVERRIDE_SEVERITY' || kind === 'DISMISS' ? null : (changed ? text : null),
    severity: kind === 'OVERRIDE_SEVERITY' ? severity : null, expert: kind === 'ROUTE_TO_EXPERT' ? expert : null,
    alternative_id: chosen?.id || null,
  })
  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-2" data-testid="decision-area">
        <button type="button" className="rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white hover:bg-sky-800" onClick={() => setOpen(true)}>
          {card.card_line === 'RECOMMENDED_ACTION' ? 'Approve…' : 'Resolve…'}
        </button>
        {onCancel && <button type="button" className="text-xs underline" onClick={onCancel}>Cancel</button>}
      </div>
    )
  }
  return (
    <form className="space-y-3 rounded border border-sky-200 bg-sky-50 p-3 text-sm" data-testid="decision-form"
      onSubmit={e => { e.preventDefault(); if (ready) save(body()) }}>
      {allowed.length > 1 && (
        <fieldset className="flex flex-wrap gap-3">
          <legend className="mb-1 text-xs font-medium text-slate-600">Resolution</legend>
          {allowed.map(k => (
            <label key={k} className="flex items-center gap-1 text-sm">
              <input type="radio" name={`kind-${card.card_id}`} value={k} checked={kind === k} onChange={() => { setKind(k); setSourceId(null) }} />
              {RESOLUTIONS[k].label}
            </label>
          ))}
        </fieldset>
      )}
      {kind === 'ROUTE_TO_EXPERT' && (
        <label className="block text-xs">Expert
          <select className="ml-2 rounded border px-1 py-0.5" value={expert} onChange={e => { setExpert(e.target.value); setSourceId(null) }} name="expert">
            <option value="ENGINEERING">Engineering</option><option value="LANGUAGE_SPECIALIST">Language specialist</option>
          </select>
        </label>
      )}
      {kind === 'OVERRIDE_SEVERITY' && (
        <label className="block text-xs">Severity for this card (assessed {card.severity.level})
          <select className="ml-2 rounded border px-1 py-0.5" value={severity} onChange={e => setSeverity(e.target.value)} name="severity">
            <option value="">Choose…</option>
            {['LOW', 'MEDIUM', 'HIGH', 'N/A'].filter(l => l !== card.severity.level).map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
      )}
      {kind && !['OVERRIDE_SEVERITY', 'DISMISS'].includes(kind) && (
        <div className="space-y-1">
          {sources.length > 1 && (
            <label className="block text-xs">Start from
              <select className="ml-2 rounded border px-1 py-0.5" value={chosen?.id ?? ''} onChange={e => setSourceId(e.target.value)} name="text-source">
                {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </label>
          )}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-medium">{chosen ? 'Draft' : textRequired ? 'Text (required; the card has no matching draft)' : 'Message to the expert (optional)'}</span>
            <Badge className={chosen && !changed ? 'border-emerald-400 bg-white text-emerald-800' : 'border-violet-400 bg-violet-50 text-violet-800'} data-testid="form-text-origin">
              {chosen ? (changed ? 'TL-edited text (not model-grounded)' : 'Model-grounded text (unchanged)') : 'TL-written text (not model-grounded)'}
            </Badge>
          </div>
          <textarea className="h-32 w-full rounded border border-slate-300 p-2 font-sans text-sm" value={text} name="text"
            onChange={e => setEdits({ ...edits, [editKey]: e.target.value })} />
        </div>
      )}
      {kind && (
        <label className="block text-xs">{noteRequired ? 'Reason (required)' : 'Note (optional)'}
          <textarea className="mt-1 h-16 w-full rounded border border-slate-300 p-2 text-sm" value={note} name="note" onChange={e => setNote(e.target.value)} />
        </label>
      )}
      {kind && <div className="text-xs text-slate-600">{KIND_NOTES[kind]}</div>}
      {!actor && <div className="text-xs text-red-700">Choose who you are acting as (top of the page).</div>}
      <SaveStatus state={state} onRetry={() => save(body())} onShowLatest={onDone} />
      <div className="flex items-center gap-3">
        <button type="submit" disabled={!ready || state.phase === 'saving'} data-testid="save-decision"
          className="rounded bg-sky-700 px-3 py-1 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400">
          {kind === 'APPROVE_ACTION' ? 'Save approval' : 'Save decision'}
        </button>
        <button type="button" className="text-xs underline" onClick={() => (onCancel ? onCancel() : setOpen(false))}>Cancel</button>
        {head && <span className="text-xs text-slate-600">This supersedes decision #{head.sequence}.</span>}
      </div>
    </form>
  )
}
