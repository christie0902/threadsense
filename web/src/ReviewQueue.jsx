import { useEffect, useRef, useState } from 'react'
import { useIdempotentSave } from './api.js'
import { RunFeedback } from './Feedback.jsx'
import { LessonEntry, LessonFields, LessonsOverview } from './Lessons.jsx'
import { Gloss } from './Markdown.jsx'
import { plainReason, plural } from './text.js'
import { Badge, Details, Json, when } from './ui.jsx'

const STATE_TONES = { OPEN: 'amber', ACCEPTED: 'emerald', REJECTED: 'rose' }
const STATE_LABELS = { OPEN: 'Open', ACCEPTED: 'Accepted', REJECTED: 'Rejected' }
const EFFECTS = { ACCEPT: 'resolved for this run', REJECT: 'recorded as a negative example', DEFER: 'kept open' }
// What the flag is about, for a reader; which agent raised it stays in the tooltip.
const KIND_LABELS = {
  inherited_agent1_review: ['Thread summary not verified', 'Raised by Agent 1 (thread interpretation)'],
  inherited_agent1_review_announcement_route: ['Announcement summary not verified', 'Raised by Agent 1 (announcement route)'],
  assisted_content_review: ['Topic review finding', 'Raised by Agent 2 (topic taxonomy)'],
}
const kindLabel = item => (item.kind === 'assisted_content_review' && JSON.stringify(item.source_obligation).includes('TAXONOMY_NAMING_CAUTION')
  ? ['Topic name caution', 'Raised by Agent 2 (topic taxonomy)'] : KIND_LABELS[item.kind] || [item.kind.replaceAll('_', ' '), item.origin])
const REOPEN_NOTE = 'Reopened'

/** A related card by its title; a card replaced by a combined issue is named through the card that replaced it. */
function relatedCard(id, cardTopics, replacedBy) {
  if (cardTopics[id]) return cardTopics[id]
  if (replacedBy[id]) return `an earlier card now part of “${replacedBy[id]}”`
  return 'an earlier card that is not in this briefing'
}

function ReviewItem({ runKey, row, actor, onChanged, onActed, cardTopics, replacedBy, focused }) {
  const ref = useRef(null)
  useEffect(() => { if (focused) ref.current?.scrollIntoView({ block: 'center' }) }, [focused])
  const { item, review_state: state, entries, head, lessons = [], lesson_agent: lessonAgent } = row
  const { state: save, save: submit, reset } = useIdempotentSave(`/api/runs/${encodeURIComponent(runKey)}/review-items/${item.item_id}/actions`)
  const [note, setNote] = useState('')
  const [lesson, setLesson] = useState(null)
  const lessonText = lesson?.text?.trim()
  const reason = plainReason(item.reason)
  const [kind, raisedBy] = kindLabel(item)
  const act = async (action, fixedNote = null) => {
    // A lesson goes with Reject only; without one, every action is sent exactly as before.
    const body = { action, actor_id: actor, expected_head: head?.entry_id || null, note: fixedNote || note.trim() || null }
    if (action === 'REJECT' && lessonText) body.lesson = { ...lesson, text: lessonText }
    onActed(item.item_id) // keeps the item in place, so a second click cannot land on the next item
    const entry = await submit(body)
    if (entry) { setNote(''); setLesson(null); onChanged() }
  }
  const decided = state === 'ACCEPTED' || state === 'REJECTED'
  return (
    <li ref={ref} className={`panel p-4 ${focused ? 'ring-2 ring-cyan-300/60' : ''}`} data-testid="review-item" data-item-id={item.item_id} data-focused={focused || undefined}>
      {focused && <div className="mb-2 text-xs font-medium text-cyan-200">Opened from a card</div>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={STATE_TONES[state]} data-testid="review-state">{STATE_LABELS[state] || state}</Badge>
        <Badge tone="cyan" title={raisedBy}>{kind}</Badge>
        <Badge>{item.project_id}</Badge>
        <span className="text-xs text-slate-400">{plural(item.member_ids.length, 'thread')}</span>
      </div>
      <div className="mt-2 text-sm font-medium text-white" data-testid="review-reason-title">{reason.title}</div>
      <div className="mt-0.5 text-sm leading-relaxed text-slate-300" data-testid="review-reason">{reason.explanation}</div>
      {reason.detail && <div className="mt-1 text-xs leading-relaxed text-slate-400" data-testid="review-reason-detail"><Gloss text={reason.detail} /></div>}
      {item.related_card_ids.length > 0 && (
        <div className="mt-1.5 text-xs text-slate-400" data-testid="review-related-card">
          Related card: {item.related_card_ids.map(id => relatedCard(id, cardTopics, replacedBy)).join('; ')} (these actions do not change it)
        </div>
      )}
      {entries.length > 0 && (
        <ol className="mt-2 space-y-0.5 text-xs text-slate-400" data-testid="review-history">
          {entries.map(e => {
            const reopened = e.action.action === 'DEFER' && e.action.note === REOPEN_NOTE
            return <li key={e.entry_id}>{when(e.action.acted_at)} · {e.action.actor_id}: <b className="text-slate-200">{reopened ? 'reopened' : e.action.action.toLowerCase()}</b>
              {reopened ? '' : ` (${EFFECTS[e.action.action]})`}{e.action.note && !reopened ? ` - ${e.action.note}` : ''}</li>
          })}
        </ol>
      )}
      {decided ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" className="btn btn-sm" disabled={!actor || save.phase === 'saving'} onClick={() => act('DEFER', REOPEN_NOTE)} data-testid="review-reopen">Reopen</button>
          <span className="text-xs text-slate-400">Moves it back to open. The earlier action stays in the history.</span>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input className="field min-w-[12rem] flex-1" placeholder="Note (optional)" value={note} onChange={e => { setNote(e.target.value); reset() }} />
          {['ACCEPT', 'REJECT', 'DEFER'].map(a => (
            <button key={a} type="button" disabled={!actor || save.phase === 'saving'} onClick={() => act(a)} data-testid={`review-${a.toLowerCase()}`}
              className="btn btn-sm">
              {a === 'ACCEPT' ? 'Accept' : a === 'REJECT' ? 'Reject (negative example)' : 'Defer'}
            </button>
          ))}
        </div>
      )}
      {!decided && (lessonAgent || lessons.length > 0) && (
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
      {save.phase === 'saved' && <div className="mt-2 text-xs text-emerald-200" data-testid="review-saved">
        Saved: {save.entry.action.note === REOPEN_NOTE ? 'reopened' : `${save.entry.action.action.toLowerCase()} (${EFFECTS[save.entry.action.action]})`}. Cards are unchanged.</div>}
      <div className="mt-3"><Details summary="Technical record" testid="review-technical">
        <div className="mb-2 text-slate-400">The automatic check's own words{reason.translated ? '' : ' (no plain-language version for this one)'}:</div>
        <div className="prose-pre mb-3 text-slate-300" data-testid="review-reason-raw">{reason.raw}</div>
        <Json value={item.source_obligation} />
      </Details></div>
    </li>
  )
}

export default function ReviewQueue({ runKey, rows, actor, onChanged, cardTopics, replacedBy = {}, focus }) {
  // A linked item is shown whatever its state.
  const [show, setShow] = useState(focus ? 'ALL' : 'OPEN')
  // Items acted on in this view stay where they are until the filter changes, with their new state and a Reopen button.
  const [acted, setActed] = useState(() => new Set())
  const choose = s => { setShow(s); setActed(new Set()) }
  const shown = rows.filter(r => show === 'ALL' || r.review_state === show || acted.has(r.item.item_id))
  const counts = rows.reduce((acc, r) => ({ ...acc, [r.review_state]: (acc[r.review_state] || 0) + 1 }), {})
  return (
    <section data-testid="review-queue" className="space-y-4">
      <p className="max-w-3xl text-sm text-slate-400">
        Flags on the automatic thread summaries and topic names that fed the cards, kept apart from the cards themselves.
        Accept resolves a flag for this run, Reject records it as a negative example, Defer keeps it open, and Reopen undoes
        an Accept or Reject. None of these change a card or record AI feedback.
      </p>
      <RunFeedback runKey={runKey} cardTopics={cardTopics} />
      <LessonsOverview actor={actor} version={rows} />
      <div className="inline-flex flex-wrap gap-1 rounded-xl border border-white/[0.06] bg-ink-950/50 p-1 text-sm">
        {['OPEN', 'ACCEPTED', 'REJECTED', 'ALL'].map(s => (
          <button key={s} type="button" onClick={() => choose(s)}
            className={`rounded-lg px-3 py-1 first-letter:uppercase transition ${show === s ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:text-slate-200'}`}>
            {s.toLowerCase()} ({s === 'ALL' ? rows.length : counts[s] || 0})
          </button>
        ))}
      </div>
      <ul className="space-y-3">{shown.map(r => (
        <ReviewItem key={r.item.item_id} runKey={runKey} row={r} actor={actor} onChanged={onChanged} cardTopics={cardTopics} replacedBy={replacedBy}
          onActed={id => setActed(a => new Set(a).add(id))} focused={r.item.item_id === focus} />
      ))}</ul>
      {shown.length === 0 && <div className="text-sm text-slate-400">No items.</div>}
    </section>
  )
}
