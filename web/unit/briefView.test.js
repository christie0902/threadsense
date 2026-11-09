// Unit checks for the shared brief view model (src/briefView.js): node --test, no browser, no server.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  briefStats, buildRows, decisionStatus, decisionsByCard, filterRows, quickCounts, runKind, severityState, sortRows,
} from '../src/briefView.js'

const KINDS = { RECOMMENDED_ACTION: ['APPROVE_ACTION'], OBSERVATION: [],
  NEEDS_REVIEW: ['CONFIRM_FAQ_UPDATE', 'CONFIRM_ANNOUNCEMENT', 'OVERRIDE_SEVERITY', 'DISMISS', 'ROUTE_TO_EXPERT'] }

let n = 0
/** One /brief card entry with only the fields the view model reads. */
function item({ id, line = 'NEEDS_REVIEW', level = 'MEDIUM', status = 'ASSESSED', at = '2026-10-02T08:00:00.000000Z',
  action = line === 'RECOMMENDED_ACTION' ? 'POST_ALIGNMENT' : null, inventory, briefing, project = 'audio_multimodal',
  resolution = 'UNRESOLVED', unsupported = false } = {}) {
  const card_id = id || `card_${String(++n).padStart(32, '0')}`
  return {
    card: { card_id, card_line: line, project_id: project, resolution_status: resolution,
      severity: { level, assessment_status: status },
      recommended_action: action ? { action_type: action, label: action, draft_text: 'Draft.' } : null },
    allowed_decisions: KINDS[line], activity: { latest_at: at },
    presentation: { inventory, briefing: briefing ? { status: briefing } : undefined, unsupported_observation: unsupported },
  }
}
const decision = (card_id, kind, sequence = 1, extra = {}) => ({
  entry_id: `decision_${card_id}_${sequence}`, card_id, kind, sequence,
  decision: { execution: { state: 'NOT_EXECUTED' }, outcome: { state: 'NOT_OBSERVED' }, tl_response: {}, ...extra },
})
const rowsOf = (cards, decisions = [], queue = []) => buildRows(cards, decisionsByCard({ decisions, indexing: {} }), queue)
const ids = rows => rows.map(r => r.card.card_id)

test('default order: HIGH, MEDIUM, LOW, unassessed; review first; newest activity; card ID breaks ties', () => {
  const unassessed = item({ id: 'card_u', level: 'UNKNOWN', status: 'UNASSESSED', at: '2026-10-02T11:00:00.000000Z' })
  const low = item({ id: 'card_l', level: 'LOW', line: 'RECOMMENDED_ACTION' })
  const na = item({ id: 'card_na', level: 'N/A', line: 'OBSERVATION' })
  const medAction = item({ id: 'card_ma', line: 'RECOMMENDED_ACTION', at: '2026-10-02T11:59:00.000000Z' })
  const medOld = item({ id: 'card_mo', at: '2026-10-01T13:00:00.000000Z' })
  const medNew = item({ id: 'card_mn', at: '2026-10-02T09:00:00.000000Z' })
  const tieB = item({ id: 'card_tb', level: 'HIGH' })
  const tieA = item({ id: 'card_ta', level: 'HIGH' })
  const rows = rowsOf([unassessed, low, na, medAction, medOld, medNew, tieB, tieA])
  // Needs review before a recommended action at the same severity even though the action is newer.
  assert.deepEqual(ids(sortRows(rows)), ['card_ta', 'card_tb', 'card_mn', 'card_mo', 'card_ma', 'card_l', 'card_na', 'card_u'])
  // Deterministic: the input order does not matter.
  assert.deepEqual(ids(sortRows([...rows].reverse())), ids(sortRows(rows)))
})

test('unassessed severity is distinct from LOW and missing timestamps never sort as now', () => {
  const unassessed = severityState({ severity: { level: 'UNKNOWN', assessment_status: 'UNASSESSED' } }, null)
  const low = severityState({ severity: { level: 'LOW', assessment_status: 'ASSESSED' } }, null)
  assert.equal(unassessed.unassessed, true)
  assert.equal(low.unassessed, false)
  assert.ok(unassessed.rank > low.rank)
  const dated = item({ id: 'card_d', at: '2026-10-01T12:00:01.000000Z' })
  const undated = item({ id: 'card_x', at: null })
  const rows = rowsOf([undated, dated])
  assert.deepEqual(ids(sortRows(rows, 'activity')), ['card_d', 'card_x'])
  assert.deepEqual(ids(sortRows(rows, 'severity')), ['card_d', 'card_x'])
  assert.equal(rows.find(r => r.card.card_id === 'card_x').activity, null) // not replaced by a clock value
})

test('latest-activity and needs-review-first orders', () => {
  const highOld = item({ id: 'card_h', level: 'HIGH', at: '2026-10-01T12:00:00.000000Z' })
  const lowNew = item({ id: 'card_n', level: 'LOW', line: 'RECOMMENDED_ACTION', at: '2026-10-02T11:00:00.000000Z' })
  const lowReview = item({ id: 'card_r', level: 'LOW', at: '2026-10-02T10:00:00.000000Z' })
  const rows = rowsOf([highOld, lowNew, lowReview])
  assert.deepEqual(ids(sortRows(rows, 'activity')), ['card_n', 'card_r', 'card_h'])
  assert.deepEqual(ids(sortRows(rows, 'review')), ['card_h', 'card_r', 'card_n'])
})

test('pending actions are authorized recommendations awaiting a decision, not every unresolved discussion', () => {
  const action = item({ id: 'card_a', line: 'RECOMMENDED_ACTION' })
  const noAction = item({ id: 'card_na', line: 'RECOMMENDED_ACTION', action: 'NO_ACTION' })
  const reviewWithDraft = item({ id: 'card_rd', line: 'NEEDS_REVIEW', action: 'UPDATE_FAQ', resolution: 'UNRESOLVED' })
  const observation = item({ id: 'card_o', line: 'OBSERVATION', resolution: 'UNRESOLVED' })
  const approved = item({ id: 'card_ap', line: 'RECOMMENDED_ACTION' })
  const rows = rowsOf([action, noAction, reviewWithDraft, observation, approved], [decision('card_ap', 'APPROVE_ACTION')])
  assert.deepEqual(ids(filterRows(rows, { quick: 'PENDING_ACTIONS' })), ['card_a'])
  const stats = briefStats(rows)
  assert.equal(stats.pendingActions, 1)
  // Awaiting any TL decision: the action, the no-action recommendation and the review card; never the observation.
  assert.equal(stats.awaitingDecision, 3)
  assert.equal(stats.observations, 1)
  assert.deepEqual(ids(filterRows(rows, { quick: 'OBSERVATIONS' })), ['card_o'])
})

test('tab membership: closing decisions move to Reviewed; a severity override stays active', () => {
  const cards = ['APPROVE_ACTION', 'DISMISS', 'ROUTE_TO_EXPERT', 'CONFIRM_FAQ_UPDATE', 'OVERRIDE_SEVERITY']
    .map((k, i) => item({ id: `card_${i}`, line: k === 'APPROVE_ACTION' ? 'RECOMMENDED_ACTION' : 'NEEDS_REVIEW' }))
  const override = { tl_response: { severity_override: { proposed: 'MEDIUM', tl_selected: 'HIGH', reason: 'r' } } }
  const decisions = [decision('card_0', 'APPROVE_ACTION'), decision('card_1', 'DISMISS'), decision('card_2', 'ROUTE_TO_EXPERT'),
    decision('card_3', 'CONFIRM_FAQ_UPDATE'), decision('card_4', 'OVERRIDE_SEVERITY', 1, override)]
  const rows = rowsOf(cards, decisions)
  assert.deepEqual(ids(filterRows(rows, { tab: 'REVIEWED' })), ['card_0', 'card_1', 'card_2', 'card_3'])
  const active = filterRows(rows, { tab: 'ACTIVE' })
  assert.deepEqual(ids(active), ['card_4'])
  assert.equal(active[0].severity.level, 'HIGH') // the TL override orders the card; the card itself is unchanged
  assert.equal(active[0].card.severity.level, 'MEDIUM')
  assert.equal(active[0].awaitingDecision, true)
  const labels = Object.fromEntries(rows.map(r => [r.card.card_id, r.decision.label]))
  assert.equal(labels.card_0, 'Approved — execution not recorded')
  assert.equal(labels.card_1, 'Dismissed — not evidence the issue is resolved')
  // Approval is never labelled resolution; only the dismissal says the issue is NOT shown resolved.
  assert.ok(Object.values(labels).every(l => !/resolved/i.test(l.replace('not evidence the issue is resolved', ''))))
})

test('a later decision supersedes the earlier one', () => {
  const card = item({ id: 'card_s' })
  const override = { tl_response: { severity_override: { proposed: 'MEDIUM', tl_selected: 'LOW', reason: 'r' } } }
  const rows = rowsOf([card], [decision('card_s', 'DISMISS', 1), decision('card_s', 'OVERRIDE_SEVERITY', 2, override)])
  assert.equal(rows[0].tab, 'ACTIVE')
  assert.equal(rows[0].decision.status, 'SEVERITY_OVERRIDDEN')
  assert.equal(rows[0].state.decisions.length, 2) // history kept
})

test('approval moves a card to Reviewed and leaves its model-review obligations open', () => {
  const card = item({ id: 'card_q', line: 'RECOMMENDED_ACTION' })
  const queue = [{ review_state: 'OPEN', item: { item_id: 'review_1', related_card_ids: ['card_q'] } },
    { review_state: 'ACCEPTED', item: { item_id: 'review_2', related_card_ids: ['card_q'] } }]
  const before = rowsOf([card], [], queue)
  const after = rowsOf([card], [decision('card_q', 'APPROVE_ACTION')], queue)
  assert.equal(before[0].tab, 'ACTIVE')
  assert.equal(after[0].tab, 'REVIEWED')
  assert.deepEqual(after[0].openObligations, ['review_1'])
  assert.equal(briefStats(after, queue).modelReviewOpen, 1)
  assert.equal(briefStats(after, queue).pendingActions, 0)
  assert.equal(decisionStatus(card, null).status, 'PENDING')
})

test('counts use the brief only: history, processing history and replaced records are never active', () => {
  const cards = [item({ line: 'NEEDS_REVIEW' }), item({ line: 'RECOMMENDED_ACTION' }), item({ line: 'OBSERVATION' }),
    item({ line: 'OBSERVATION', briefing: 'EXCLUDED_SOCIAL' }), item({ line: 'OBSERVATION', inventory: 'PROCESSING_HISTORY' }),
    item({ line: 'NEEDS_REVIEW', inventory: 'CONSOLIDATED_PENDING' })]
  const rows = rowsOf(cards)
  const totals = { card_records: { total: 35, replaced_history: 29 } }
  const stats = briefStats(rows, [], totals)
  assert.equal(stats.inBrief, 3)
  assert.equal(stats.active, 3)
  assert.deepEqual(stats.byLine, { NEEDS_REVIEW: 1, RECOMMENDED_ACTION: 1, OBSERVATION: 1 })
  assert.equal(stats.notInBrief, 1)
  assert.equal(stats.processingHistory, 1)
  assert.equal(stats.consolidatedPending, 1)
  assert.equal(stats.consolidatedIssues, 0) // this synthetic pending card names no consolidated issue
  assert.equal(stats.replacedRecords, 29)
  // History cards are in no lifecycle tab and in no quick-filter count.
  assert.equal(filterRows(rows, { tab: 'ACTIVE' }).length + filterRows(rows, { tab: 'REVIEWED' }).length, 3)
  assert.equal(quickCounts(rows).OBSERVATIONS, 1)
})

test('decisions bound to another run instance do not change this run', () => {
  const card = item({ id: 'card_iso', line: 'RECOMMENDED_ACTION' })
  // The decisions endpoint returns only this instance's rows; a run with none keeps the card active.
  const thisRun = rowsOf([card], [])
  const otherRun = rowsOf([card], [decision('card_iso', 'APPROVE_ACTION')])
  assert.equal(thisRun[0].tab, 'ACTIVE')
  assert.equal(otherRun[0].tab, 'REVIEWED')
})

test('project filter and quick counts agree with the feed', () => {
  const rows = rowsOf([item({ project: 'a', level: 'HIGH' }), item({ project: 'b', level: 'HIGH' }),
    item({ project: 'b', level: 'UNKNOWN', status: 'UNASSESSED' })])
  assert.equal(filterRows(rows, { project: 'b' }).length, 2)
  assert.deepEqual(quickCounts(rows, { project: 'b' }), { ALL: 2, PENDING_ACTIONS: 0, NEEDS_REVIEW: 2, OBSERVATIONS: 0, HIGH: 1, UNASSESSED: 1 })
})

test('run kinds keep derived and combined briefings apart from live runs', () => {
  assert.equal(runKind({ mode: 'LIVE' }).label, 'Live overnight run')
  assert.equal(runKind({ mode: 'LIVE', derivation: { provenance: 'OFFLINE_COMBINATION', parents: ['a', 'b'] } }).label, 'Offline combination')
  assert.equal(runKind({ mode: 'LIVE', derivation: { parent_run_key: 'x' } }).label, 'Offline derivation')
  assert.equal(runKind({ mode: 'TEST_FIXTURE' }).label, 'Test fixture')
})
