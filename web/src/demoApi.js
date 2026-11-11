// Static demo backend (`npm run build:demo`): answers the dashboard's API paths from a bundled snapshot of one saved
// run (scripts/build_web_demo_data.py) and keeps the visitor's decisions, review actions, lessons and AI-feedback
// reports in this browser's localStorage, scoped to that briefing. It mirrors the FastAPI rules the UI relies on
// (idempotency keys, expected heads, state transitions) in simplified form. No network request leaves the page except
// the one for the bundled data file, and nothing runs an agent.
import bundleUrl from '../demo/briefing.json?url'

const EFFECTS = { ACCEPT: 'RESOLVED_FOR_RUN', REJECT: 'NEGATIVE_EXAMPLE', DEFER: 'KEPT_OPEN' }
const KIND_ACTIONS = { CONFIRM_FAQ_UPDATE: 'UPDATE_FAQ', CONFIRM_ANNOUNCEMENT: 'POST_ALIGNMENT' }
const EXPERTS = { ENGINEERING: 'ESCALATE_ENGINEERING', LANGUAGE_SPECIALIST: 'ROUTE_TO_LANGUAGE_SPECIALIST' }
const ORIGIN_AGENT = { agent1: 'AGENT_1', agent2: 'AGENT_2', assisted_content_review: 'AGENT_2' }
const LESSON_CATEGORIES = { AGENT_1: ['SUMMARY', 'RESOLUTION', 'AUTHORITY', 'RELEVANCE', 'GENERAL'], AGENT_2: ['GROUPING', 'NAMING', 'GENERAL'] }
const FEEDBACK_TRANSITIONS = { SUBMITTED: ['CONFIRM', 'WITHDRAW'], CONFIRMED: ['WITHDRAW'] }

let bundle = null
let memory = null // used when localStorage is unavailable (private window, blocked site data)

export const DEMO_NOTE = 'Demo data · Changes saved in this browser.'

export async function load() {
  if (!bundle) {
    bundle = fetch(bundleUrl).then(r => { if (!r.ok) throw new Error(`Demo data not found (${r.status}).`); return r.json() })
      .then(b => ({ ...b, decoded: new Map(Object.keys(b.responses).map(k => [decoded(k), k])) }))
  }
  return bundle
}

// Python's quote() and encodeURIComponent() escape a few characters differently; paths are compared decoded.
function decoded(path) {
  try { return decodeURIComponent(path) } catch { return path }
}

const storageKey = b => `threadsense-demo/v1/${b.run_key}#${b.run_instance.slice(0, 16)}`
const empty = () => ({ decisions: [], reviews: [], lessons: [], feedback: [], keys: {} })

function readState(b) {
  try {
    const raw = window.localStorage.getItem(storageKey(b))
    if (raw) return { ...empty(), ...JSON.parse(raw) }
  } catch { /* fall through to memory */ }
  return memory || empty()
}

function writeState(b, state) {
  memory = state
  try { window.localStorage.setItem(storageKey(b), JSON.stringify(state)) } catch { /* kept in memory for this tab */ }
}

export async function resetDemo() {
  const b = await load()
  memory = null
  try { window.localStorage.removeItem(storageKey(b)) } catch { /* nothing stored */ }
}

export async function demoChangeCount() {
  const s = readState(await load())
  return s.decisions.length + s.reviews.length + s.lessons.length + s.feedback.length
}

const clone = v => (v === undefined ? v : JSON.parse(JSON.stringify(v)))
const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
const newId = prefix => `${prefix}_${crypto.randomUUID().replaceAll('-', '')}`
const byId = (list, key, id) => list.filter(e => e[key] === id).sort((a, b) => a.sequence - b.sequence)
const notFound = detail => { const e = new Error(detail); e.status = 404; throw e }

function saved(b, path) {
  const r = b.responses[path] || b.responses[b.decoded.get(decoded(path))]
  if (!r) notFound('Not part of the demo data.')
  if (r.status !== 200) { const e = new Error(r.body?.detail || `${r.status}`); e.status = r.status; throw e }
  return clone(r.body)
}

// ---- folds over the locally saved events (same views as dashboard/lessons.py and dashboard/feedback.py) ----

function lessonViews(state) {
  const ids = [...new Set(state.lessons.map(e => e.lesson_id))]
  return ids.map(id => {
    const events = byId(state.lessons, 'lesson_id', id)
    const head = events.at(-1)
    return { lesson_id: id, state: head.state_after, lesson: events[0].lesson, head, events, superseded_by: head.superseded_by_lesson_id || null }
  }).sort((a, b) => b.lesson.saved_at.localeCompare(a.lesson.saved_at))
}

function feedbackView(state, id) {
  const events = byId(state.feedback, 'feedback_id', id)
  const head = events.at(-1), report = events[0].report
  const confirm = [...events].reverse().find(e => e.event_type === 'CONFIRMED')
  const st = head.state_after
  const eligible = st === 'CONFIRMED' && report.future_use.requested && !report.future_use.blockers.length
  const why = eligible ? 'Eligible: confirmed, opted in, with a correction and a thread scope.'
    : !report.future_use.requested ? 'Not offered for future runs by the reviewer.'
      : st === 'SUBMITTED' ? 'Awaiting confirmation by a team lead.' : `${st[0]}${st.slice(1).toLowerCase()}: no longer used in new snapshots.`
  return { feedback_id: id, state: st, report, head, events, confirmed_at: confirm?.recorded_at || null, confirmed_by: confirm?.actor_id || null,
    self_confirmed: !!confirm && confirm.actor_id === report.submitted_by, superseded_by: head.superseded_by_feedback_id || null,
    eligible_for_future_runs: eligible, eligibility: why }
}

function feedbackViews(state, cardId = null) {
  return [...new Set(state.feedback.map(e => e.feedback_id))].map(id => feedbackView(state, id))
    .filter(v => cardId === null || v.report.card_id === cardId)
    .sort((a, b) => b.report.submitted_at.localeCompare(a.report.submitted_at))
}

function feedbackCounts(views, used) {
  return { submitted: views.length, confirmed: views.filter(v => v.state === 'CONFIRMED').length,
    eligible_for_future_runs: views.filter(v => v.eligible_for_future_runs).length,
    withdrawn: views.filter(v => v.state === 'WITHDRAWN').length, superseded: views.filter(v => v.state === 'SUPERSEDED').length,
    corrections_used_by_this_run: used }
}

const indexing = decisions => Object.fromEntries(decisions.map(e => [e.entry_id, { entry_id: e.entry_id, status: 'PENDING', snapshot: null,
  snapshot_fingerprint: null, error: null, updated_at: e.recorded_at }]))

function cardState(state, cardId) {
  const decisions = byId(state.decisions, 'card_id', cardId)
  return { decisions, head: decisions.at(-1) || null, indexing: indexing(decisions) }
}

function queueRow(b, state, row) {
  const id = row.item.item_id
  const entries = byId(state.reviews, 'item_id', id)
  const actions = [...(row.item.actions || []), ...entries.map(e => e.action)]
  const last = actions.at(-1)?.action
  const lessons = lessonViews(state).filter(v => v.lesson.origin.item_id === id && v.lesson.origin.run_key === b.run_key)
  return { ...row, item: { ...row.item, actions }, review_state: !last || last === 'DEFER' ? 'OPEN' : last === 'ACCEPT' ? 'ACCEPTED' : 'REJECTED',
    entries: [...row.entries, ...entries], head: entries.at(-1) || row.head, lessons: [...row.lessons, ...lessons] }
}

// ---- GET ----

export async function getJSON(path) {
  const b = await load()
  const state = readState(b)
  const url = new URL(path, 'http://demo.invalid')
  const p = url.pathname
  const base = `/api/runs/${encodeURIComponent(b.run_key)}`
  const run = p.startsWith('/api/runs/') ? decodeURIComponent(p.split('/')[3]) : null
  if (run !== null && run !== b.run_key) notFound(`No run ${run}.`)
  const rest = run === null ? p : p.slice(`/api/runs/${p.split('/')[3]}`.length)
  const used = saved(b, `${base}/feedback`).counts.corrections_used_by_this_run

  if (p === '/api/lessons') {
    const views = lessonViews(state)
    return { ...saved(b, p), lessons: views, counts: Object.fromEntries(['ACTIVE', 'INACTIVE', 'SUPERSEDED'].map(s => [s, views.filter(v => v.state === s).length])) }
  }
  if (rest === '/brief') {
    const brief = saved(b, `${base}/brief`)
    const views = feedbackViews(state)
    for (const item of brief.cards) {
      const id = item.card.card_id
      item.resolved = item.resolved || state.decisions.some(e => e.card_id === id)
      item.feedback_reports += views.filter(v => v.report.card_id === id).length
    }
    brief.feedback_counts = feedbackCounts(views, used)
    return brief
  }
  if (rest === '/decisions') {
    const d = saved(b, `${base}/decisions`)
    const decisions = [...d.decisions, ...state.decisions]
    return { ...d, decisions, indexing: { ...d.indexing, ...indexing(state.decisions) } }
  }
  if (rest === '/review-queue') return { items: saved(b, `${base}/review-queue`).items.map(r => queueRow(b, state, r)) }
  if (rest === '/negative-examples') {
    const items = saved(b, `${base}/review-queue`).items.map(r => queueRow(b, state, r))
    return { items: items.filter(i => i.review_state === 'REJECTED').map(i => ({ item: i.item, rejected_by: i.head.action })) }
  }
  if (rest === '/feedback') {
    const views = feedbackViews(state)
    return { items: views, counts: feedbackCounts(views, used) }
  }
  const m = rest.match(/^\/cards\/([^/]+)(\/feedback)?$/)
  if (m) {
    const body = saved(b, `${base}${rest}`)
    if (m[2]) return { ...body, history: [...body.history, ...feedbackViews(state, m[1])] }
    return { ...body, decision_state: cardState(state, m[1]) }
  }
  return saved(b, run === null ? p : `${base}${rest}`) // evidence, threads, flags and the run list: as saved
}

// ---- POST (one idempotent save) ----

class Refused extends Error {
  constructor(status, code, detail, extra = {}) { super(detail); Object.assign(this, { status, code, extra }) }
}
const invalid = (detail, code = 'INVALID_DECISION') => new Refused(422, code, detail)

function checkHead(head, expected, label) {
  if ((head?.entry_id || null) !== (expected || null)) throw new Refused(409, 'STALE', `Another ${label} was saved since this one was prepared.`, { current_head: head || null })
}

function sessionCheck(b, body) {
  if (body.actor_id !== b.team_lead) throw new Refused(403, 'NOT_SESSION_USER', `This dashboard records decisions for ${b.team_lead} only.`)
}

function cardItem(b, cardId) {
  const item = saved(b, `/api/runs/${encodeURIComponent(b.run_key)}/brief`).cards.find(c => c.card.card_id === cardId)
  if (!item) notFound(`No card ${cardId} in run ${b.run_key}.`)
  return item
}

function decide(b, state, cardId, body) {
  const item = cardItem(b, cardId), card = item.card
  if (!item.allowed_decisions.includes(body.kind)) throw invalid(`${body.kind} is not offered on this card.`)
  const { head, decisions } = cardState(state, cardId)
  checkHead(head, body.expected_head, 'decision')
  let action = card.recommended_action || {}, source = 'CARD_DRAFT'
  if (body.alternative_id) {
    action = item.alternatives.find(a => a.candidate_id === body.alternative_id)
    if (!action) throw invalid(`${body.alternative_id} is not a supported alternative on this card.`)
    source = 'SUPPORTED_ALTERNATIVE'
  }
  const edited = body.text?.trim() ? body.text : null
  const note = body.note?.trim() || null
  let approved = null, override = null, reuse = null
  if (body.kind === 'APPROVE_ACTION') { approved = [action.action_type]; reuse = action.draft_text || null }
  else if (KIND_ACTIONS[body.kind] || body.kind === 'ROUTE_TO_EXPERT') {
    approved = [KIND_ACTIONS[body.kind] || EXPERTS[body.expert]]
    reuse = action.action_type === approved[0] ? action.draft_text || null : null
    if (KIND_ACTIONS[body.kind] && !reuse && !edited) throw invalid('This card has no matching draft; write the text to confirm.')
  } else {
    if (edited) throw invalid(`${body.kind} carries no draft text; use the note for the reason.`)
    if (!note) throw invalid('Give the reason for this decision.')
    if (body.kind === 'OVERRIDE_SEVERITY') {
      if (!body.severity || body.severity === card.severity.level) throw invalid(`Choose a severity different from the assessed ${card.severity.level}.`)
      override = { proposed: card.severity.level, tl_selected: body.severity, reason: note }
    }
  }
  const grounded = reuse ? { grounded_source: source, alternative_id: body.alternative_id || null } : {}
  const text = !edited || edited === reuse ? (reuse ? { origin: 'MODEL_GROUNDED', model_grounded_text: reuse, ...grounded } : { origin: 'NONE' })
    : { origin: reuse ? 'TL_EDITED' : 'TL_WRITTEN', model_grounded_text: reuse, tl_text: edited, ...grounded }
  const at = now()
  const outcome = { DISMISS: 'REJECTED', OVERRIDE_SEVERITY: 'OVERRIDDEN' }[body.kind] || (['TL_EDITED', 'TL_WRITTEN'].includes(text.origin) ? 'APPROVED_WITH_EDITS' : 'APPROVED')
  const entry = {
    contract_version: 'dashboard-tl-decision-v3', decision_origin: 'DEMO_SCRIPT', namespace: 'demo', demo_browser_only: true,
    entry_id: newId('decision'), sequence: decisions.length + 1, supersedes_entry_id: head?.entry_id || null,
    run_key: b.run_key, run_instance: b.run_instance, card_id: cardId, card_line: card.card_line, topic_name: card.topic_name,
    project_id: card.project_id, kind: body.kind, recorded_at: at, actor_id: body.actor_id, actor_role: 'TEAM_LEAD',
    text, note, expert: body.expert || null, approval_is_not_execution: true,
    decision: { tl_response: { outcome, actor_id: body.actor_id, actor_role: 'TEAM_LEAD', reviewed_at: at, text: edited,
      approved_actions: approved || [], severity_override: override },
    execution: { state: 'NOT_EXECUTED' }, outcome: { state: 'NOT_OBSERVED' } },
  }
  state.decisions.push(entry)
  return { entry }
}

function reviewAction(b, state, itemId, body) {
  const row = saved(b, `/api/runs/${encodeURIComponent(b.run_key)}/review-queue`).items.find(r => r.item.item_id === itemId)
  if (!row) notFound(`Review item ${itemId} is not in run ${b.run_key}.`)
  if (!['ACCEPT', 'REJECT', 'DEFER'].includes(body.action)) throw invalid('Unknown review action.')
  const current = queueRow(b, state, row)
  checkHead(current.head, body.expected_head, 'action')
  let lesson = null
  if (body.lesson != null) {
    if (body.action !== 'REJECT') throw invalid('A lesson is saved only with a rejection.')
    lesson = lessonInput(body.lesson, ORIGIN_AGENT[row.item.origin])
  }
  const at = now()
  const entry = {
    contract_version: 'dashboard-model-review-action-v2', namespace: 'demo', demo_browser_only: true, entry_id: newId('reviewaction'),
    sequence: current.entries.length + 1, supersedes_entry_id: current.head?.entry_id || null, run_key: b.run_key, run_instance: b.run_instance,
    item_id: itemId, project_id: row.item.project_id,
    action: { action: body.action, actor_id: body.actor_id, actor_role: 'TEAM_LEAD', acted_at: at, note: body.note?.trim() || null },
    effect: EFFECTS[body.action], related_card_ids: row.item.related_card_ids, cards_untouched: true,
  }
  state.reviews.push(entry)
  if (!lesson) return { entry }
  const lessonId = newId('lesson')
  const event = lessonEvent(lessonId, 1, null, 'SAVED', 'ACTIVE', at, body.actor_id, {
    contract_version: 'dashboard-review-lesson-v1', lesson_id: lessonId, namespace: 'demo', ...lesson,
    project_id: row.item.project_id,
    origin: { run_key: b.run_key, run_instance: b.run_instance, item_id: itemId, item_kind: row.item.kind, item_origin: row.item.origin,
      item_reason: row.item.reason, review_entry_id: entry.entry_id },
    supersedes_lesson_id: null, saved_at: at, saved_by: body.actor_id, saved_by_role: 'TEAM_LEAD',
    lesson_is_guidance_not_policy: true, lesson_is_not_evidence: true, lesson_clears_no_review_obligation: true,
  })
  state.lessons.push(event)
  return { entry, lesson: event }
}

function lessonInput(raw, defaultAgent) {
  const text = (raw?.text || '').trim()
  const target = raw?.target_agent || defaultAgent
  if (text.length < 12 || text.length > 400) throw invalid('A lesson has 12 to 400 characters.', 'INVALID_LESSON')
  if (/[{}]/.test(text)) throw invalid('A lesson may not contain curly braces.', 'INVALID_LESSON')
  if (!LESSON_CATEGORIES[target]) throw invalid('Choose Agent 1 or Agent 2.', 'INVALID_LESSON')
  const category = raw.category || 'GENERAL'
  if (!LESSON_CATEGORIES[target].includes(category)) throw invalid(`${category} is not a category for ${target}.`, 'INVALID_LESSON')
  return { target_agent: target, applies_to: raw.applies_to === 'ALL_PROJECTS' ? 'ALL_PROJECTS' : 'PROJECT', category, text }
}

function lessonEvent(lessonId, sequence, previous, type, after, at, actor, lesson = null, extra = {}) {
  return { contract_version: 'dashboard-review-lesson-event-v1', entry_id: newId('lessonevent'), lesson_id: lessonId, sequence,
    supersedes_entry_id: previous, namespace: 'demo', demo_browser_only: true, event_type: type, state_after: after, recorded_at: at,
    actor_id: actor, actor_role: actor ? 'TEAM_LEAD' : null, note: null, lesson, superseded_by_lesson_id: null, ...extra }
}

function lessonAction(state, lessonId, body) {
  const events = byId(state.lessons, 'lesson_id', lessonId)
  if (!events.length) notFound(`No lesson ${lessonId}.`)
  const head = events.at(-1)
  checkHead(head, body.expected_head, 'lesson change')
  const next = { DEACTIVATE: ['ACTIVE', 'DEACTIVATED', 'INACTIVE'], REACTIVATE: ['INACTIVE', 'REACTIVATED', 'ACTIVE'] }[body.action]
  if (!next || head.state_after !== next[0]) throw invalid(`A ${head.state_after.toLowerCase()} lesson cannot be changed that way.`, 'INVALID_LESSON')
  const entry = lessonEvent(lessonId, head.sequence + 1, head.entry_id, next[1], next[2], now(), body.actor_id, null, { note: body.note || null })
  state.lessons.push(entry)
  return { entry }
}

function lessonSupersede(state, lessonId, body) {
  const events = byId(state.lessons, 'lesson_id', lessonId)
  if (!events.length) notFound(`No lesson ${lessonId}.`)
  const head = events.at(-1), old = events[0].lesson
  checkHead(head, body.expected_head, 'lesson change')
  if (head.state_after === 'SUPERSEDED') throw invalid('This lesson was already replaced.', 'INVALID_LESSON')
  const input = lessonInput({ ...body.lesson, target_agent: old.target_agent }, old.target_agent)
  const at = now(), newIdValue = newId('lesson')
  const entry = lessonEvent(newIdValue, 1, null, 'SAVED', 'ACTIVE', at, body.actor_id,
    { ...old, ...input, lesson_id: newIdValue, supersedes_lesson_id: lessonId, saved_at: at, saved_by: body.actor_id })
  const superseded = lessonEvent(lessonId, head.sequence + 1, head.entry_id, 'SUPERSEDED', 'SUPERSEDED', at, body.actor_id, null,
    { note: `Replaced by an edited version (${newIdValue}).`, superseded_by_lesson_id: newIdValue })
  state.lessons.push(entry, superseded)
  return { entry, superseded }
}

function submitFeedback(b, state, cardId, body) {
  const item = cardItem(b, cardId), card = item.card
  const context = saved(b, `/api/runs/${encodeURIComponent(b.run_key)}/cards/${cardId}/feedback`)
  const { targets, categories, limits } = context
  if (!categories[body.category]) throw invalid('Choose a category.', 'INVALID_FEEDBACK')
  const wrong = (body.what_is_wrong || '').trim()
  if (!wrong) throw invalid('Say what is wrong.', 'INVALID_FEEDBACK')
  if (wrong.length > limits.max_text || (body.suggested_correction || '').length > limits.max_text) throw invalid(`At most ${limits.max_text} characters.`, 'INVALID_FEEDBACK')
  for (const ref of body.source_refs || []) {
    if (!/^(m:[^:]+:\S+|k:\S+)$/.test(ref)) throw invalid(`'${ref}' is not an evidence ID (m:<channel>:<message> or k:<source>).`, 'INVALID_FEEDBACK')
  }
  let target, threads, basis
  if (body.target_kind === 'CARD') {
    target = { kind: 'CARD', id: cardId, statement_kind: null, earlier_text: card.summary, earlier_verdict: null, earlier_rationale: null, evidence_ids: [], review_item_kind: null }
    const keys = new Set(body.scope_threads || [])
    threads = targets.threads.filter(t => keys.has(t.key)).map(t => ({ channel_id: t.channel_id, thread_id: t.thread_id }))
    basis = 'REVIEWER_SELECTED'
  } else if (body.target_kind === 'STATEMENT') {
    const s = targets.statements.find(x => x.id === body.target_id)
    if (!s) throw invalid(`${body.target_id} is not a statement on this card.`, 'INVALID_FEEDBACK')
    target = { kind: 'STATEMENT', id: s.id, statement_kind: s.kind, earlier_text: s.text, earlier_verdict: s.verdict, earlier_rationale: s.rationale, evidence_ids: s.evidence_ids, review_item_kind: null }
    // Simplified scope: the card's threads whose root message is cited, else the threads in the cited channels.
    const cited = s.evidence_ids.filter(e => e.startsWith('m:')).map(e => e.split(':'))
    const exact = targets.threads.filter(t => cited.some(([, c, ts]) => c === t.channel_id && ts === t.thread_id))
    threads = (exact.length ? exact : targets.threads.filter(t => cited.some(([, c]) => c === t.channel_id)))
      .map(t => ({ channel_id: t.channel_id, thread_id: t.thread_id }))
    basis = 'STATEMENT_EVIDENCE'
  } else if (body.target_kind === 'REVIEW_ITEM') {
    const r = targets.review_items.find(x => x.id === body.target_id)
    if (!r) throw invalid(`${body.target_id} is not a review finding about this card.`, 'INVALID_FEEDBACK')
    target = { kind: 'REVIEW_ITEM', id: r.id, statement_kind: null, earlier_text: r.reason, earlier_verdict: null, earlier_rationale: null, evidence_ids: [], review_item_kind: r.kind || null }
    threads = targets.threads.map(t => ({ channel_id: t.channel_id, thread_id: t.thread_id }))
    basis = 'REVIEW_ITEM_MEMBERS'
  } else throw invalid('Choose the affected output.', 'INVALID_FEEDBACK')
  const correction = (body.suggested_correction || '').trim() || null
  const blockers = [
    (correction || '').length < limits.min_correction && `write the correction itself (at least ${limits.min_correction} characters)`,
    !threads.length && 'the card has no Slack thread to scope the correction to',
    threads.length > limits.max_scope_threads && `the scope has ${threads.length} threads; choose at most ${limits.max_scope_threads} it applies to`,
  ].filter(Boolean)
  if (body.use_in_future_runs && blockers.length) throw invalid(`Cannot offer this for future runs: ${blockers.join('; ')}.`, 'INVALID_FEEDBACK')
  if (body.supersedes_feedback_id && !state.feedback.some(e => e.feedback_id === body.supersedes_feedback_id)) throw invalid('The report it replaces is not recorded on this card.', 'INVALID_FEEDBACK')
  const at = now(), id = newId('feedback')
  const report = {
    contract_version: 'dashboard-ai-feedback-v1', feedback_id: id, namespace: 'demo', run_key: b.run_key, run_instance: b.run_instance,
    card_id: cardId, card_line: card.card_line, topic_name: card.topic_name, category: body.category, problem: body.problem || null, target,
    what_is_wrong: wrong, suggested_correction: correction, source_refs: [...new Set(body.source_refs || [])].map(ref => ({ ref })),
    scope: { project_id: card.project_id, threads, basis },
    future_use: { requested: !!body.use_in_future_runs, blockers },
    supersedes_feedback_id: body.supersedes_feedback_id || null, submitted_at: at, submitted_by: body.actor_id, submitted_by_role: 'TEAM_LEAD',
    feedback_is_not_policy: true, feedback_is_not_ground_truth: true,
  }
  const entry = feedbackEvent(id, 1, null, 'SUBMITTED', 'SUBMITTED', at, body.actor_id, { report })
  state.feedback.push(entry)
  return { entry }
}

function feedbackEvent(id, sequence, previous, type, after, at, actor, extra = {}) {
  return { contract_version: 'dashboard-ai-feedback-event-v1', entry_id: newId('feedbackevent'), feedback_id: id, sequence,
    supersedes_entry_id: previous, namespace: 'demo', demo_browser_only: true, event_type: type, state_after: after, recorded_at: at,
    actor_id: actor, actor_role: actor ? 'TEAM_LEAD' : null, note: null, report: null, superseded_by_feedback_id: null, ...extra }
}

function feedbackAction(state, id, body) {
  const events = byId(state.feedback, 'feedback_id', id)
  if (!events.length) notFound(`Feedback ${id} is not recorded on this run.`)
  const head = events.at(-1)
  checkHead(head, body.expected_head, 'change to this report')
  if (!(FEEDBACK_TRANSITIONS[head.state_after] || []).includes(body.action)) throw invalid(`A ${head.state_after.toLowerCase()} report cannot be ${body.action.toLowerCase()}ed.`, 'INVALID_FEEDBACK')
  const after = body.action === 'CONFIRM' ? 'CONFIRMED' : 'WITHDRAWN'
  const at = now()
  const entry = feedbackEvent(id, head.sequence + 1, head.entry_id, after, after, at, body.actor_id, { note: body.note || null })
  state.feedback.push(entry)
  const earlierId = events[0].report.supersedes_feedback_id
  if (after === 'CONFIRMED' && earlierId) { // A confirmed replacement supersedes the report it names (if still open).
    const earlier = byId(state.feedback, 'feedback_id', earlierId).at(-1)
    if (earlier && FEEDBACK_TRANSITIONS[earlier.state_after]) {
      state.feedback.push(feedbackEvent(earlierId, earlier.sequence + 1, earlier.entry_id, 'SUPERSEDED', 'SUPERSEDED', at, null,
        { superseded_by_feedback_id: id, note: `Superseded by ${id}, confirmed by ${body.actor_id}.` }))
    }
  }
  return { entry }
}

/** One POST, answered like the API: { ok, status, data }. Same key + same body replays; same key + other body is refused. */
export async function post(path, key, serialized) {
  const b = await load()
  const state = readState(b)
  const prior = state.keys[key]
  if (prior) {
    if (prior.body === serialized) return { ok: true, status: 200, data: { ...prior.response, replayed: true, persisted: true } }
    return { ok: false, status: 422, data: { code: 'IDEMPOTENCY_KEY_REUSED', detail: 'This request key was already used for a different request.' } }
  }
  const body = JSON.parse(serialized)
  const p = new URL(path, 'http://demo.invalid').pathname
  const run = p.startsWith('/api/runs/') ? decodeURIComponent(p.split('/')[3]) : null
  const rest = run === null ? p : p.slice(`/api/runs/${p.split('/')[3]}`.length)
  let m
  try {
    if (run !== null && run !== b.run_key) notFound(`No run ${run}.`)
    sessionCheck(b, body)
    let response
    if ((m = rest.match(/^\/cards\/([^/]+)\/decisions$/))) response = decide(b, state, m[1], body)
    else if ((m = rest.match(/^\/review-items\/([^/]+)\/actions$/))) response = reviewAction(b, state, m[1], body)
    else if ((m = rest.match(/^\/cards\/([^/]+)\/feedback$/))) response = submitFeedback(b, state, m[1], body)
    else if ((m = rest.match(/^\/feedback\/([^/]+)\/actions$/))) response = feedbackAction(state, m[1], body)
    else if ((m = p.match(/^\/api\/lessons\/([^/]+)\/actions$/))) response = lessonAction(state, m[1], body)
    else if ((m = p.match(/^\/api\/lessons\/([^/]+)\/supersede$/))) response = lessonSupersede(state, m[1], body)
    else notFound('This action is not available in the demo.')
    state.keys[key] = { body: serialized, response }
    writeState(b, state)
    return { ok: true, status: 201, data: { ...response, replayed: false, persisted: true } }
  } catch (error) {
    if (error instanceof Refused) return { ok: false, status: error.status, data: { code: error.code, detail: error.message, ...error.extra } }
    return { ok: false, status: error.status || 500, data: { code: error.status === 404 ? 'NOT_FOUND' : 'ERROR', detail: error.message } }
  }
}
