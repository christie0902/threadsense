import { useEffect, useRef, useState } from 'react'
import { useIdempotentSave } from './api.js'
import { RunFeedback } from './Feedback.jsx'
import { LessonEntry, LessonFields, LessonsOverview } from './Lessons.jsx'
import { Badge, Details, Json, when } from './ui.jsx'

const STATE_TONES = { OPEN: 'amber', ACCEPTED: 'emerald', REJECTED: 'rose' }
const EFFECTS = { ACCEPT: 'resolved for this run', REJECT: 'recorded as a negative example', DEFER: 'kept open' }
const KIND_LABELS = {
  inherited_agent1_review: 'Agent 1 obligation (discussion)',
  inherited_agent1_review_announcement_route: 'Agent 1 obligation (announcement route)',
  assisted_content_review: 'Agent 2 assisted review',
}
const kindLabel = item => (item.kind === 'assisted_content_review' && JSON.stringify(item.source_obligation).includes('TAXONOMY_NAMING_CAUTION')
  ? 'Agent 2 naming caution' : KIND_LABELS[item.kind] || item.kind.replaceAll('_', ' '))

function ReviewItem({ runKey, row, actor, onChanged, cardTopics, focused }) {
  const ref = useRef(null)
  useEffect(() => { if (focused) ref.current?.scrollIntoView({ block: 'center' }) }, [focused])
  const { item, review_state: state, entries, head, lessons = [], lesson_agent: lessonAgent } = row
  const { state: save, save: submit, reset } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/review-items/${item.item_id}/actions`)
  const [note, setNote] = useState('')
  const [lesson, setLesson] = useState(null)
  const lessonText = lesson?.text?.trim()
  const act = async action => {
    // A lesson goes with Reject only; without one, every action is sent exactly as before.
    const body = { action, actor_id: actor, expected_head: head?.entry_id || null, note: note.trim() || null }
    if (action === 'REJECT' && lessonText) body.lesson = { ...lesson, text: lessonText }
    const entry = await submit(body)
    if (entry) { setNote(''); setLesson(null); onChanged(); }
  }
  return (
    <li ref={ref} className={`panel p-4 ${focused ? 'ring-2 ring-cyan-300/60' : ''}`} data-testid="review-item" data-item-id={item.item_id} data-focused={focused || undefined}>
      {focused && <div className="mb-2 text-xs font-medium text-cyan-200">Opened from a card's "What to review" panel</div>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={STATE_TONES[state]} data-testid="review-state">{state.toLowerCase()}</Badge>
        <Badge tone="cyan" title={`${item.origin} · ${item.kind}`}>{kindLabel(item)}</Badge>
        <Badge>{item.project_id}</Badge>
        <span className="text-xs text-slate-400">{item.member_ids.length} member(s)</span>
      </div>
      <div className="prose-pre mt-2 line-clamp-3 text-sm leading-relaxed text-slate-200 hover:line-clamp-none">{item.reason}</div>
      {item.related_card_ids.length > 0 && <div className="mt-1 text-xs text-slate-400">Related card: {item.related_card_ids.map(id => cardTopics[id] || id).join('; ')} (not changed by these actions)</div>}
      {entries.length > 0 && (
        <ol className="mt-2 space-y-0.5 text-xs text-slate-400" data-testid="review-history">
          {entries.map(e => <li key={e.entry_id}>{when(e.action.acted_at)} · {e.action.actor_id}: <b className="text-slate-200">{e.action.action.toLowerCase()}</b> ({EFFECTS[e.action.action]}){e.action.note ? ` - ${e.action.note}` : ''}</li>)}
        </ol>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input className="field min-w-[12rem] flex-1" placeholder="Note (optional)" value={note} onChange={e => { setNote(e.target.value); reset() }} />
        {['ACCEPT', 'REJECT', 'DEFER'].map(a => (
          <button key={a} type="button" disabled={!actor || save.phase === 'saving'} onClick={() => act(a)} data-testid={`review-${a.toLowerCase()}`}
            className="btn btn-sm">
            {a === 'ACCEPT' ? 'Accept' : a === 'REJECT' ? 'Reject (negative example)' : 'Defer'}
          </button>
        ))}
      </div>
      {(lessonAgent || lessons.length > 0) && state !== 'REJECTED' && (
        <LessonFields agent={lessonAgent} value={lesson} project={item.project_id} onChange={v => { setLesson(v); reset() }} />
      )}
      {lessonText && <div className="mt-1 text-xs text-cyan-200" data-testid="lesson-pending">The lesson is saved when you click Reject; Accept and Defer ignore it.</div>}
      {lessons.length > 0 && (
        <div className="mt-3"><div className="text-xs text-slate-400">Lessons saved from this item</div>
          <ul className="mt-1 space-y-2">{lessons.map(v => <LessonEntry key={v.lesson_id} view={v} actor={actor} onChanged={onChanged} />)}</ul></div>
      )}
      {save.phase === 'uncertain' && <div className="mt-2 text-xs text-amber-200" data-testid="save-uncertain">Not confirmed; the action may or may not be saved. Click the same action again: it reuses the request key and cannot be saved twice.</div>}
      {save.phase === 'conflict' && <div className="mt-2 text-xs text-red-300" data-testid="save-conflict">Not saved: another action was recorded on this item meanwhile. <button className="link" onClick={() => { reset(); onChanged() }}>Refresh</button></div>}
      {save.phase === 'rejected' && <div className="mt-2 text-xs text-red-300">Not saved: {save.detail}</div>}
      {save.phase === 'saved' && <div className="mt-2 text-xs text-emerald-200" data-testid="review-saved">Saved: {save.entry.action.action.toLowerCase()} ({EFFECTS[save.entry.action.action]}). AdviceCards are unchanged.</div>}
      <div className="mt-3"><Details summary="Upstream record (verbatim)"><Json value={item.source_obligation} /></Details></div>
    </li>
  )
}

export default function ReviewQueue({ runKey, rows, actor, onChanged, cardTopics, focus }) {
  // A linked item is shown whatever its state.
  const [show, setShow] = useState(focus ? 'ALL' : 'OPEN')
  const shown = rows.filter(r => show === 'ALL' || r.review_state === show)
  const counts = rows.reduce((acc, r) => ({ ...acc, [r.review_state]: (acc[r.review_state] || 0) + 1 }), {})
  return (
    <section data-testid="review-queue" className="space-y-4">
      <p className="max-w-3xl text-sm text-slate-400">
        Flags on upstream model output (Agent 1 obligations and Agent 2 naming cautions), kept apart from the cards.
        Accept resolves a flag for this run, Reject records a negative example, Defer keeps it open. None of these change a card,
        and none of them records AI feedback.
      </p>
      <RunFeedback runKey={runKey} cardTopics={cardTopics} />
      <LessonsOverview actor={actor} version={rows} />
      <div className="inline-flex flex-wrap gap-1 rounded-xl border border-white/[0.06] bg-ink-950/50 p-1 text-sm">
        {['OPEN', 'ACCEPTED', 'REJECTED', 'ALL'].map(s => (
          <button key={s} type="button" onClick={() => setShow(s)}
            className={`rounded-lg px-3 py-1 first-letter:uppercase transition ${show === s ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            {s.toLowerCase()} ({s === 'ALL' ? rows.length : counts[s] || 0})
          </button>
        ))}
      </div>
      <ul className="space-y-3">{shown.map(r => <ReviewItem key={r.item.item_id} runKey={runKey} row={r} actor={actor} onChanged={onChanged} cardTopics={cardTopics} focused={r.item.item_id === focus} />)}</ul>
      {shown.length === 0 && <div className="text-sm text-slate-400">No items.</div>}
    </section>
  )
}
