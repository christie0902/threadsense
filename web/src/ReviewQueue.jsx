import { useState } from 'react'
import { useIdempotentSave } from './api.js'
import { Badge, Details, Json, when } from './ui.jsx'

const STATE_STYLES = { OPEN: 'border-amber-300 bg-amber-50 text-amber-900', ACCEPTED: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  REJECTED: 'border-rose-300 bg-rose-50 text-rose-900' }
const EFFECTS = { ACCEPT: 'resolved for this run', REJECT: 'recorded as a negative example', DEFER: 'kept open' }

function ReviewItem({ runKey, row, actor, onChanged, cardTopics }) {
  const { item, review_state: state, entries, head } = row
  const { state: save, save: submit, reset } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/review-items/${item.item_id}/actions`)
  const [note, setNote] = useState('')
  const act = async action => {
    const entry = await submit({ action, actor_id: actor, expected_head: head?.entry_id || null, note: note.trim() || null })
    if (entry) { setNote(''); onChanged(); }
  }
  return (
    <li className="rounded border border-slate-200 bg-white p-3" data-testid="review-item" data-item-id={item.item_id}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={STATE_STYLES[state]} data-testid="review-state">{state.toLowerCase()}</Badge>
        <Badge className="border-slate-300 bg-white">{item.origin}</Badge>
        <Badge className="border-slate-300 bg-white">{item.kind.replaceAll('_', ' ')}</Badge>
        <Badge className="border-slate-300 bg-white">{item.project_id}</Badge>
        <span className="text-xs text-slate-500">{item.member_ids.length} member(s)</span>
      </div>
      <div className="prose-pre mt-2 text-sm">{item.reason}</div>
      {item.related_card_ids.length > 0 && <div className="mt-1 text-xs text-slate-600">Related card: {item.related_card_ids.map(id => cardTopics[id] || id).join('; ')} (not changed by these actions)</div>}
      {entries.length > 0 && (
        <ol className="mt-2 space-y-0.5 text-xs text-slate-700" data-testid="review-history">
          {entries.map(e => <li key={e.entry_id}>{when(e.action.acted_at)} · {e.action.actor_id}: <b>{e.action.action.toLowerCase()}</b> ({EFFECTS[e.action.action]}){e.action.note ? ` - ${e.action.note}` : ''}</li>)}
        </ol>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input className="min-w-[12rem] flex-1 rounded border border-slate-300 px-2 py-0.5 text-sm" placeholder="Note (optional)" value={note} onChange={e => { setNote(e.target.value); reset() }} />
        {['ACCEPT', 'REJECT', 'DEFER'].map(a => (
          <button key={a} type="button" disabled={!actor || save.phase === 'saving'} onClick={() => act(a)} data-testid={`review-${a.toLowerCase()}`}
            className="rounded border border-slate-300 bg-white px-2 py-0.5 text-sm hover:bg-slate-100 disabled:opacity-50">
            {a === 'ACCEPT' ? 'Accept' : a === 'REJECT' ? 'Reject (negative example)' : 'Defer'}
          </button>
        ))}
      </div>
      {save.phase === 'uncertain' && <div className="mt-1 text-xs text-amber-800" data-testid="save-uncertain">Not confirmed; the action may or may not be saved. Click the same action again: it reuses the request key and cannot be saved twice.</div>}
      {save.phase === 'conflict' && <div className="mt-1 text-xs text-red-800" data-testid="save-conflict">Not saved: another action was recorded on this item meanwhile. <button className="underline" onClick={() => { reset(); onChanged() }}>Refresh</button></div>}
      {save.phase === 'rejected' && <div className="mt-1 text-xs text-red-800">Not saved: {save.detail}</div>}
      {save.phase === 'saved' && <div className="mt-1 text-xs text-emerald-800" data-testid="review-saved">Saved: {save.entry.action.action.toLowerCase()} ({EFFECTS[save.entry.action.action]}). AdviceCards are unchanged.</div>}
      <div className="mt-2"><Details summary="Upstream record (verbatim)"><Json value={item.source_obligation} /></Details></div>
    </li>
  )
}

export default function ReviewQueue({ runKey, rows, actor, onChanged, cardTopics }) {
  const [show, setShow] = useState('OPEN')
  const shown = rows.filter(r => show === 'ALL' || r.review_state === show)
  const counts = rows.reduce((acc, r) => ({ ...acc, [r.review_state]: (acc[r.review_state] || 0) + 1 }), {})
  return (
    <section data-testid="review-queue">
      <p className="mb-2 text-sm text-slate-600">
        Upstream model-output flags (Agent 1/2 and assisted review), kept separate from the operational cards.
        Accept resolves the flag for this run, Reject records a negative example, Defer keeps it open. None of these change an AdviceCard.
      </p>
      <div className="mb-3 flex gap-2 text-sm">
        {['OPEN', 'ACCEPTED', 'REJECTED', 'ALL'].map(s => (
          <button key={s} type="button" onClick={() => setShow(s)} className={`rounded px-2 py-0.5 ${show === s ? 'bg-slate-800 text-white' : 'bg-white border border-slate-300'}`}>
            {s.toLowerCase()} ({s === 'ALL' ? rows.length : counts[s] || 0})
          </button>
        ))}
      </div>
      <ul className="space-y-2">{shown.map(r => <ReviewItem key={r.item.item_id} runKey={runKey} row={r} actor={actor} onChanged={onChanged} cardTopics={cardTopics} />)}</ul>
      {shown.length === 0 && <div className="text-sm text-slate-500">No items.</div>}
    </section>
  )
}
