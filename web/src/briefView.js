// One view model for the brief: lifecycle membership, counts, filters and sorting. Pure functions over the saved
// /brief, /decisions and /review-queue payloads, so tabs, statistics and the feed share one definition.
//
// Four separate things, never merged:
// - source-thread resolution: card.resolution_status, read from the threads (unchanged here);
// - advice classification: card.card_line (Recommended action / Needs review / Observation);
// - TL decision status: the latest saved decision on the card (the head; a later decision supersedes it);
// - execution or resolution: decision.execution / decision.outcome. Dashboard decisions always record NOT_EXECUTED
//   and NOT_OBSERVED, so nothing here is ever shown as executed or resolved.

// Decisions that answer the card and take it out of the active queue. OVERRIDE_SEVERITY is not one: it changes the
// severity for this card and leaves the decision on what to do open.
const CLOSING = {
  APPROVE_ACTION: 'Approved',
  CONFIRM_FAQ_UPDATE: 'FAQ update confirmed',
  CONFIRM_ANNOUNCEMENT: 'Announcement confirmed',
  ROUTE_TO_EXPERT: 'Routed to an expert',
  DISMISS: 'Dismissed',
}
// Ranks for ordering: assessed levels first, a "not applicable" assessment next, unassessed or unknown last.
const SEVERITY_RANK = { HIGH: 0, MEDIUM: 1, LOW: 2, 'N/A': 3 }
const UNASSESSED_RANK = 4

export const SORTS = {
  severity: 'Severity: High to Low',
  activity: 'Latest activity',
  review: 'Needs review first',
}
export const QUICK_FILTERS = {
  ALL: 'All cards',
  PENDING_ACTIONS: 'Pending actions',
  NEEDS_REVIEW: 'Needs review',
  OBSERVATIONS: 'Observations',
  HIGH: 'High severity',
  UNASSESSED: 'Severity unassessed',
}

/** Where a served card belongs in the run: the brief itself or one of its history lists. */
export function scopeOf(item) {
  const inventory = item.presentation?.inventory || 'BRIEF'
  if (inventory !== 'BRIEF') return inventory // PROCESSING_HISTORY, CONSOLIDATED_PENDING, REPLACED (never served)
  return (item.presentation?.briefing?.status || 'IN_BRIEFING') === 'IN_BRIEFING' ? 'BRIEF' : 'NOT_IN_BRIEF'
}

/** Latest decision per card, with its full history in sequence order. */
export function decisionsByCard(decisions) {
  const out = {}
  for (const e of decisions?.decisions || []) (out[e.card_id] ||= { decisions: [], indexing: decisions.indexing }).decisions.push(e)
  for (const s of Object.values(out)) { s.decisions.sort((a, b) => a.sequence - b.sequence); s.head = s.decisions.at(-1) }
  return out
}

/** The severity used for ordering: a current TL override wins over the assessment; unassessed stays distinct. */
export function severityState(card, head) {
  const override = head?.kind === 'OVERRIDE_SEVERITY' ? head.decision?.tl_response?.severity_override || null : null
  const level = override ? override.tl_selected : card.severity.level
  const unassessed = !override && (card.severity.assessment_status === 'UNASSESSED' || card.severity.level === 'UNKNOWN')
  return { level, unassessed, override, rank: unassessed ? UNASSESSED_RANK : SEVERITY_RANK[level] ?? UNASSESSED_RANK }
}

function executionText(head) {
  const state = head.decision?.execution?.state
  return !state || state === 'NOT_EXECUTED' ? 'execution not recorded' : `execution ${state.replaceAll('_', ' ').toLowerCase()}`
}

/** Decision status of one card from its head decision. reviewed: out of the active queue (never "resolved"). */
export function decisionStatus(item, head) {
  const allowed = item.allowed_decisions || []
  if (!head) return { status: allowed.length ? 'PENDING' : 'NO_DECISION', reviewed: false, label: allowed.length ? 'Decision pending' : null }
  if (head.kind === 'OVERRIDE_SEVERITY') {
    const o = head.decision?.tl_response?.severity_override
    return { status: 'SEVERITY_OVERRIDDEN', reviewed: false, kind: head.kind,
      label: `Severity set to ${o?.tl_selected} by the team lead; decision still pending` }
  }
  if (CLOSING[head.kind]) {
    const label = head.kind === 'DISMISS' ? 'Dismissed — not evidence the issue is resolved' : `${CLOSING[head.kind]} — ${executionText(head)}`
    return { status: head.kind, reviewed: true, kind: head.kind, label }
  }
  return { status: head.kind, reviewed: false, kind: head.kind, label: head.kind }
}

const operational = card => !!card.recommended_action && card.recommended_action.action_type !== 'NO_ACTION'

/**
 * Rows for every served card, with lifecycle, severity, activity and open model-review obligations.
 * pendingAction: an authorized operational recommendation (the card offers approval and states an action) that has
 * no closing decision. It never includes a discussion that is merely unresolved in its source threads.
 */
export function buildRows(cards, byCard, queueRows = []) {
  const openByCard = {}
  for (const r of queueRows) {
    if (r.review_state !== 'OPEN') continue
    for (const id of r.item.related_card_ids || []) (openByCard[id] ||= []).push(r.item.item_id)
  }
  return cards.map(item => {
    const card = item.card
    const state = byCard[card.card_id]
    const head = state?.head || null
    const decision = decisionStatus(item, head)
    const scope = scopeOf(item)
    const awaiting = scope === 'BRIEF' && !decision.reviewed && (item.allowed_decisions || []).length > 0
    return {
      item, card, state, head, decision, scope,
      tab: scope === 'BRIEF' ? (decision.reviewed ? 'REVIEWED' : 'ACTIVE') : null,
      severity: severityState(card, head),
      activity: item.activity?.latest_at || null,
      needsReview: card.card_line === 'NEEDS_REVIEW' || !!item.presentation?.unsupported_observation,
      observation: card.card_line === 'OBSERVATION',
      awaitingDecision: awaiting,
      pendingAction: awaiting && (item.allowed_decisions || []).includes('APPROVE_ACTION') && operational(card),
      openObligations: openByCard[card.card_id] || [],
    }
  })
}

/**
 * Statistics for the selected briefing, from the brief's own active records only. Replaced cards are never served;
 * history and processing-history cards are counted separately, never as active.
 */
export function briefStats(rows, queueRows = [], totals = null) {
  const brief = rows.filter(r => r.scope === 'BRIEF')
  const active = brief.filter(r => r.tab === 'ACTIVE')
  const byLine = line => brief.filter(r => r.card.card_line === line).length
  return {
    inBrief: brief.length,
    byLine: { NEEDS_REVIEW: byLine('NEEDS_REVIEW'), RECOMMENDED_ACTION: byLine('RECOMMENDED_ACTION'), OBSERVATION: byLine('OBSERVATION') },
    active: active.length,
    reviewed: brief.length - active.length,
    awaitingDecision: active.filter(r => r.awaitingDecision).length,
    pendingActions: active.filter(r => r.pendingAction).length,
    observations: active.filter(r => r.observation).length,
    modelReviewOpen: queueRows.filter(r => r.review_state === 'OPEN').length,
    modelReviewTotal: queueRows.length,
    notInBrief: rows.filter(r => r.scope === 'NOT_IN_BRIEF').length,
    processingHistory: rows.filter(r => r.scope === 'PROCESSING_HISTORY').length,
    consolidatedPending: rows.filter(r => r.scope === 'CONSOLIDATED_PENDING').length,
    // Same-issue groups awaiting fresh advice: briefing items without a card of their own (their original cards above).
    consolidatedIssues: new Set(rows.filter(r => r.scope === 'CONSOLIDATED_PENDING')
      .map(r => r.item.presentation?.consolidated?.consolidated_topic_id).filter(Boolean)).size,
    replacedRecords: totals?.card_records?.replaced_history ?? null, // reachable only through the card that replaced them
  }
}

const QUICK = {
  ALL: () => true,
  PENDING_ACTIONS: r => r.pendingAction,
  NEEDS_REVIEW: r => r.needsReview,
  OBSERVATIONS: r => r.observation,
  HIGH: r => !r.severity.unassessed && r.severity.level === 'HIGH',
  UNASSESSED: r => r.severity.unassessed,
}

/** Rows of one lifecycle tab (ACTIVE / REVIEWED) after the quick filter and the project filter. */
export function filterRows(rows, { tab = 'ACTIVE', quick = 'ALL', project = '' } = {}) {
  const keep = QUICK[quick] || QUICK.ALL
  return rows.filter(r => r.tab === tab && keep(r) && (!project || r.card.project_id === project))
}

/** Count per quick filter in one tab, for the sidebar (project filter applied, so counts match the feed). */
export function quickCounts(rows, { tab = 'ACTIVE', project = '' } = {}) {
  return Object.fromEntries(Object.keys(QUICK_FILTERS).map(k => [k, filterRows(rows, { tab, quick: k, project }).length]))
}

// Newest first; a card without any timestamp sorts after every dated card, never as "now". latest_at strings are
// fixed-width UTC (runs.activity), so text order is time order.
const byActivity = (a, b) => (a.activity === b.activity ? 0 : a.activity === null ? 1 : b.activity === null ? -1 : a.activity < b.activity ? 1 : -1)
const bySeverity = (a, b) => a.severity.rank - b.severity.rank
const byReview = (a, b) => Number(b.needsReview) - Number(a.needsReview)
const byId = (a, b) => (a.card.card_id < b.card.card_id ? -1 : a.card.card_id > b.card.card_id ? 1 : 0)
const ORDERS = {
  severity: [bySeverity, byReview, byActivity, byId],
  activity: [byActivity, bySeverity, byReview, byId],
  review: [byReview, bySeverity, byActivity, byId],
}

/** A new array in the chosen order; the card ID is always the final tie-breaker, so the order is deterministic. */
export function sortRows(rows, sort = 'severity') {
  const keys = ORDERS[sort] || ORDERS.severity
  return [...rows].sort((a, b) => { for (const k of keys) { const d = k(a, b); if (d) return d } return 0 })
}

/** What kind of briefing a run is, from its recorded mode and derivation; never presented as fresher than it is. */
export function runKind(run) {
  if (run.mode === 'TEST_FIXTURE') return { label: 'Test fixture', tone: 'fuchsia', detail: 'Hand-written cards, not model output.' }
  if (run.mode === 'SCRIPTED') return { label: 'Scripted run', tone: 'amber', detail: 'Prepared judgments, not model output.' }
  const d = run.derivation
  if (d && (d.provenance === 'OFFLINE_COMBINATION' || (d.parents?.length || 0) > 1))
    return { label: 'Offline combination', tone: 'cyan', detail: `Assembled offline from ${d.parents?.length || 'several'} saved runs; not a fresh pipeline run.` }
  if (d) return { label: 'Offline derivation', tone: 'cyan', detail: `Recomputed offline from ${d.parent_run_key || 'a saved run'}; not a fresh pipeline run.` }
  if (run.mode === 'LIVE') return { label: 'Live overnight run', tone: 'emerald', detail: 'Card text from live model judgments.' }
  return { label: 'Unknown run mode', tone: 'neutral', detail: '' }
}

/** Source date of a briefing: the UTC day of its window cutoff (the morning the brief is for). */
export function briefingDate(run) {
  const iso = run?.window?.cutoff || run?.cutoff
  const d = iso ? new Date(iso) : null
  if (!d || Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString('en-GB', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}
