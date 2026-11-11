import { useEffect, useState } from 'react'
import { getJSON, useIdempotentSave } from './api.js'
import { Badge, when } from './ui.jsx'

// Lessons from human review (dashboard/lessons.py): short guidance for later Agent 1 / Agent 2 runs, written by the
// team lead when rejecting an interpretation or a grouping. No model writes or rewrites them.
export const AGENT_LABELS = { AGENT_1: 'Agent 1 (interpretation)', AGENT_2: 'Agent 2 (grouping)' }
export const CATEGORY_OPTIONS = {
  AGENT_1: ['SUMMARY', 'RESOLUTION', 'AUTHORITY', 'RELEVANCE', 'GENERAL'],
  AGENT_2: ['GROUPING', 'NAMING', 'GENERAL'],
}
export const MAX_LESSON = 400
const STATE_TONES = { ACTIVE: 'emerald', INACTIVE: 'neutral', SUPERSEDED: 'neutral' }
const GUIDANCE_NOTE = 'Sent as reviewer guidance to later runs of that agent, for new threads in the chosen scope. It is not project policy or evidence, never overrides source material, and clears no review obligation.'

/** The optional lesson fields under a review item (sent with Reject only). */
export function LessonFields({ agent, value, onChange, project }) {
  const v = { text: '', applies_to: 'PROJECT', category: 'GENERAL', target_agent: agent || 'AGENT_1', ...value }
  const set = patch => onChange({ ...v, ...patch })
  return (
    <details className="group mt-3 rounded-lg border border-white/[0.08] bg-white/[0.03]" data-testid="lesson-fields" open={!!v.text}>
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-300 hover:text-white">Save a lesson for future runs (optional, with Reject)</summary>
      <div className="space-y-2 border-t border-white/[0.06] p-3">
        <textarea className="field min-h-[3.5rem] w-full" maxLength={MAX_LESSON} placeholder="A short lesson the agent should apply to new threads, e.g. what it got wrong here in general terms."
          value={v.text} onChange={e => set({ text: e.target.value })} data-testid="lesson-text" />
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <label>For <select className="field ml-1" value={v.target_agent} onChange={e => set({ target_agent: e.target.value, category: 'GENERAL' })} data-testid="lesson-agent">
            {Object.entries(AGENT_LABELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
          <label>Category <select className="field ml-1" value={v.category} onChange={e => set({ category: e.target.value })} data-testid="lesson-category">
            {CATEGORY_OPTIONS[v.target_agent].map(c => <option key={c} value={c}>{c.toLowerCase()}</option>)}</select></label>
          <label>Applies to <select className="field ml-1" value={v.applies_to} onChange={e => set({ applies_to: e.target.value })} data-testid="lesson-scope">
            <option value="PROJECT">this project ({project})</option><option value="ALL_PROJECTS">all projects</option></select></label>
          <span className="text-slate-400">{v.text.trim().length}/{MAX_LESSON}</span>
        </div>
        <div className="text-xs leading-relaxed text-slate-400">{GUIDANCE_NOTE}</div>
      </div>
    </details>
  )
}

/** One lesson with its history and the team lead's controls: deactivate / reactivate, or save an edited version. */
export function LessonEntry({ view, actor, onChanged }) {
  const l = view.lesson
  const act = useIdempotentSave(`/api/lessons/${view.lesson_id}/actions`)
  const edit = useIdempotentSave(`/api/lessons/${view.lesson_id}/supersede`)
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(l.text)
  const [scope, setScope] = useState(l.applies_to)
  const run = async action => { if (await act.save({ action, actor_id: actor, expected_head: view.head.entry_id, note: null })) onChanged() }
  const saveEdit = async () => {
    if (await edit.save({ actor_id: actor, expected_head: view.head.entry_id, lesson: { text: text.trim(), applies_to: scope, category: l.category } })) { setEditing(false); onChanged() }
  }
  const error = [act.state, edit.state].find(s => s.phase === 'rejected' || s.phase === 'conflict')
  return (
    <li className="rounded-lg border border-white/[0.07] bg-ink-950/40 p-3" data-testid="lesson-entry" data-lesson-id={view.lesson_id} data-state={view.state}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={STATE_TONES[view.state]} data-testid="lesson-state">{view.state.toLowerCase()}</Badge>
        <Badge tone="cyan">{AGENT_LABELS[l.target_agent]}</Badge>
        <Badge>{l.category.toLowerCase()}</Badge>
        <span className="text-xs text-slate-400">{l.applies_to === 'ALL_PROJECTS' ? 'all projects' : l.project_id}</span>
      </div>
      <div className="mt-1.5 text-sm text-slate-100" data-testid="lesson-body">{l.text}</div>
      <div className="mt-1 text-xs text-slate-400">From a rejected {l.origin.item_kind.replaceAll('_', ' ')} in {l.origin.run_key}{l.supersedes_lesson_id ? ' · edited version of an earlier lesson' : ''}</div>
      <ol className="mt-1 space-y-0.5 text-xs text-slate-400">
        {view.events.map(e => <li key={e.entry_id}>{when(e.recorded_at)} · {e.actor_id}: <b className="text-slate-200">{e.event_type.toLowerCase()}</b></li>)}
      </ol>
      {view.state !== 'SUPERSEDED' && !editing && (
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" className="btn btn-sm" disabled={!actor} onClick={() => run(view.state === 'ACTIVE' ? 'DEACTIVATE' : 'REACTIVATE')} data-testid="lesson-toggle">
            {view.state === 'ACTIVE' ? 'Deactivate' : 'Reactivate'}</button>
          <button type="button" className="btn btn-sm" disabled={!actor} onClick={() => setEditing(true)} data-testid="lesson-edit">Edit</button>
        </div>
      )}
      {editing && (
        <div className="mt-2 space-y-2">
          <textarea className="field min-h-[3.5rem] w-full" maxLength={MAX_LESSON} value={text} onChange={e => { setText(e.target.value); edit.reset() }} data-testid="lesson-edit-text" />
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
            <select className="field" value={scope} onChange={e => setScope(e.target.value)}><option value="PROJECT">this project ({l.project_id})</option><option value="ALL_PROJECTS">all projects</option></select>
            <button type="button" className="btn btn-sm" onClick={saveEdit} disabled={!text.trim()} data-testid="lesson-edit-save">Save edited version</button>
            <button type="button" className="btn btn-sm" onClick={() => setEditing(false)}>Cancel</button>
            <span className="text-slate-400">The current version is kept in history as superseded.</span>
          </div>
        </div>
      )}
      {error && <div className="mt-1 text-xs text-red-300">Not saved: {error.phase === 'conflict' ? 'this lesson changed meanwhile; refresh.' : error.detail}</div>}
    </li>
  )
}

/** Every lesson (all runs) for inspection in the review tab. */
export function LessonsOverview({ actor, version }) {
  const [data, setData] = useState(null)
  const [tick, setTick] = useState(0)
  useEffect(() => { getJSON('/api/lessons').then(setData).catch(() => setData(null)) }, [tick, version])
  if (!data) return null
  const c = data.counts
  return (
    <details className="panel-inset" data-testid="lessons-overview">
      <summary className="cursor-pointer select-none px-3.5 py-2.5 text-sm text-slate-200">
        Lessons from human review: <b>{c.ACTIVE}</b> active · {c.INACTIVE} inactive · {c.SUPERSEDED} superseded
      </summary>
      <div className="border-t border-white/[0.06] p-3">
        <p className="mb-2 text-xs text-slate-400">{GUIDANCE_NOTE} Later runs use them through a lesson snapshot (scripts/build_lesson_snapshot.py).</p>
        {data.lessons.length ? <ul className="space-y-2">{data.lessons.map(v => <LessonEntry key={v.lesson_id} view={v} actor={actor} onChanged={() => setTick(t => t + 1)} />)}</ul>
          : <div className="text-xs text-slate-400">No lessons yet. Reject an Agent 1 or Agent 2 item and fill in "Save a lesson for future runs".</div>}
      </div>
    </details>
  )
}
