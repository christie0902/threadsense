"""Close-call routing after the final grounding and the grounding's own source-consistency check (PREPARED judgments:
the Fake client returns scripted draft, comparison and grounding responses; routing is DETERMINISTIC). Upstream
obligations are removed from a copy of the record, so no inherited flag, HIGH severity or other review reason can hide
a routing defect. Evidence comes from each payload; no topic is named in the logic under test."""
from types import SimpleNamespace

import pytest

from threadsense.agents.advisor_contracts import AdvisorDraft
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    SCEN, Fake, codes, draft_for, retriever, run, supported, view,
)
from tests.test_agent3_tot_v3 import candidate, choice_draft, comparison, guide_of, members

CLOSE_SCENARIO = 'korean_register'  # Current guidance in its evidence; reaches RECOMMENDED_ACTION once unflagged.
SOURCES_SCENARIO = 'audio_playback'  # Two current guidance documents (instructions and FAQ) in its evidence.


def unflagged(view, scenario):
    record = next(r for r in view['records'] if r['candidate_group_id'] == SCEN[scenario]['candidate_group_id'])
    return {**view, 'records': [{**record, 'inherited_review_obligations': [], 'agent2_review_obligations': [],
                                 'content_review_obligations': []}]}


def reasons(result):
    return [(r['code'], r['detail']) for r in result['card']['needs_review_reasons']]


def close_call(payload, *others):
    return comparison(payload, None, [o(payload) for o in others], close=True)


def no_action(payload):
    return candidate('NO', 'NO_ACTION', [guide_of(payload)], 'Keep observing; the threads were answered in place.')


def escalation(payload):
    return candidate('ESC', 'ESCALATE_ENGINEERING', [guide_of(payload)], 'Please look into the reported problem with these '
                     'tasks.', need_ids=members(payload)[:1])


def same_type(payload):
    return candidate('ALT', 'POST_ALIGNMENT', [guide_of(payload)], 'Reminder: please follow the current guidance for these '
                     'tasks.', need_ids=members(payload)[:1])


# --- Close calls ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('other, types', [
    (no_action, {'POST_ALIGNMENT', 'NO_ACTION'}),               # intervening versus observing
    (escalation, {'POST_ALIGNMENT', 'ESCALATE_ENGINEERING'}),   # two materially different interventions
])
def test_close_call_that_survives_grounding_goes_to_needs_review_with_both_options(retriever, view, other, types):
    """A close call whose materially different options both pass the final grounding stays a choice for the team lead:
    Needs Review with an unresolved-choice reason (the only reason here), the incumbent kept but not preferred, and the
    other option kept for display. NO_ACTION needs no intervention need to be eligible."""
    client = Fake(draft=choice_draft, tot=lambda p: close_call(p, other), grounding=supported)
    result = run(CLOSE_SCENARIO, client, retriever, unflagged(view, CLOSE_SCENARIO))
    tot = result['tot']
    assert tot['triggers'] == ['ACTION_CHOICE'] and tot['status'] == 'COMPARED'
    choice = tot['choice_after_grounding']
    assert choice['status'] == 'UNRESOLVED' and {v['action_type'] for v in choice['viable']} == types
    assert choice['viable'][0]['source'] == 'CARD_ACTION' and tot['preferred_candidate_id'] is None
    assert all(c['issues'] == [] for c in tot['candidates'] if c['candidate_id'] != 'INC')
    card = result['card']
    assert card['card_line'] == 'NEEDS_REVIEW' and codes(result) == ['OTHER']
    assert reasons(result)[0][1].startswith('Unresolved action choice')
    assert any('none is clearly better' in n for n in card['review_notes'])
    assert card['recommended_action']['action_type'] == 'POST_ALIGNMENT'  # retained, not dropped


def test_close_call_resolved_by_grounding_is_not_a_review_reason(retriever, view):
    """The ACTION_CHOICE trigger and the comparison's close call are not review reasons by themselves: when the final
    grounding rejects the other option, one option survives and the card is an ordinary recommended action."""
    client = Fake(draft=choice_draft, tot=lambda p: close_call(p, no_action),
                  grounding=lambda p: supported(p, **{'alternative:NO': 'UNSUPPORTED'}))
    result = run(CLOSE_SCENARIO, client, retriever, unflagged(view, CLOSE_SCENARIO))
    assert result['tot']['choice_after_grounding']['status'] == 'RESOLVED_BY_GROUNDING'
    assert result['card']['card_line'] == 'RECOMMENDED_ACTION' and result['card']['needs_review_reasons'] == []


def test_same_type_options_and_clear_comparisons_are_not_unresolved_choices(retriever, view):
    """Two wordings of the same action type are not materially different; a comparison that kept the incumbent
    clearly is not a close call, even with a supported NO_ACTION alternative."""
    same = run(CLOSE_SCENARIO, Fake(draft=choice_draft, tot=lambda p: close_call(p, same_type), grounding=supported),
               retriever, unflagged(view, CLOSE_SCENARIO))
    assert same['tot']['choice_after_grounding']['status'] == 'RESOLVED_BY_GROUNDING'
    assert same['card']['card_line'] == 'RECOMMENDED_ACTION'
    kept = run(CLOSE_SCENARIO, Fake(draft=choice_draft, tot=lambda p: comparison(p, 'INC', [no_action(p)]), grounding=supported),
               retriever, unflagged(view, CLOSE_SCENARIO))
    assert kept['tot']['choice_after_grounding']['status'] == 'NOT_A_CLOSE_CALL'
    assert kept['card']['card_line'] == 'RECOMMENDED_ACTION' and kept['card']['needs_review_reasons'] == []


def test_dashboard_marks_closely_matched_options_and_prefers_none():
    """The dashboard lists a viable NO_ACTION option of an unresolved choice (it has no sufficiency entry) and marks
    every listed option closely matched, none preferred."""
    from threadsense.dashboard.runs import Run
    tot = {'candidates': [{'candidate_id': 'NO', 'action_type': 'NO_ACTION', 'draft_text': 'Keep observing.', 'issues': []}],
           'preferred_candidate_id': 'NO',
           'choice_after_grounding': {'status': 'UNRESOLVED', 'viable': [
               {'candidate_id': None, 'action_type': 'POST_ALIGNMENT', 'source': 'CARD_ACTION'},
               {'candidate_id': 'NO', 'action_type': 'NO_ACTION', 'source': 'TOT_CANDIDATE'}]}}
    stub = SimpleNamespace(topics={'c': {'result': {'tot': tot, 'grounding': {'statements': []}}}},
                           cards={'c': {'recommended_action': {'draft_text': 'Post it.'}}})
    [shown] = Run.alternatives(stub, 'c')
    assert shown['closely_matched'] and not shown['preferred_by_comparison'] and shown['action_type'] == 'NO_ACTION'


# --- Source consistency in the final grounding ----------------------------------------------------------------------

def two_guides(payload):
    """Two current guidance items from different documents, from whatever the payload shows."""
    items = payload.get('retrieved_evidence') or payload['retrieved_sources']
    seen, out = set(), []
    for i in items:
        document = i['use'] == 'CURRENT_GUIDANCE' and i['citation']['authoring'].rsplit('@', 1)[0]
        if document and document not in seen:
            seen.add(document)
            out.append(i['evidence_id'])
    return out[:2]


def with_relations(payload, relations=(), checks=()):
    value = supported(payload)
    value['source_consistency'] = {**value['source_consistency'], 'relations': list(relations),
                                   'declared_conflict_checks': list(checks)}
    return value


def test_grounding_finds_a_current_source_conflict_the_draft_did_not_declare(retriever, view):
    """Paired case 1: the draft declares no conflict, but the final grounding finds that two current guidance sources
    state different rules. The conflict reaches final routing (TEMPORAL_CONFLICT, origin FINAL_GROUNDING) without a late
    comparison call, and the record says the comparison did not consider it."""
    def grounding(p):
        a, b = two_guides(p)
        assert {a, b} <= set(p['governing_sources']) and p['declared_conflicts'] == []
        return with_relations(p, [{'evidence_ids': [a, b], 'relation': 'CONFLICT', 'point': 'How to handle a player that never starts',
                                   'disagreement_scope': 'whether a visible waveform with no sound counts', 'rationale': 'Prepared.'}])
    result = run(SOURCES_SCENARIO, Fake(draft=draft_for, grounding=grounding), retriever, unflagged(view, SOURCES_SCENARIO))
    assert [c['stage'] for c in result['model_calls']] == ['draft', 'grounding'] and result['tot']['status'] == 'NOT_TRIGGERED'
    assert result['temporal_before_grounding']['status'] == 'NONE_FOUND'
    found = [f for f in result['temporal']['findings'] if f.get('origin') == 'FINAL_GROUNDING']
    assert [(f['code'], f['status'], f['considered_by_tot']) for f in found] == [('SOURCE_CONFLICT_FOUND_IN_GROUNDING', 'DETECTED', False)]
    assert 'TEMPORAL_CONFLICT' in codes(result) and result['card']['card_line'] == 'NEEDS_REVIEW'
    assert any('did not consider it' in n for n in result['card']['review_notes'])


def test_declared_conflict_between_agreeing_current_sources_is_resolved_by_the_grounding(retriever, view):
    """Paired case 2: the draft declares a conflict between two current sources, the final grounding finds they say the
    same thing, so no temporal conflict reaches routing (the comparison it triggered still ran before grounding)."""
    def draft(p):
        return {**draft_for(p), 'source_conflicts': [{'evidence_ids': two_guides(p), 'description': 'They seem to differ.'}]}

    def grounding(p):
        assert p['declared_conflicts'][0]['conflict_index'] == 0
        return with_relations(p, [{'evidence_ids': p['declared_conflicts'][0]['evidence_ids'], 'relation': 'AGREE',
                                   'point': 'Player failures', 'rationale': 'Both say report it as a tool incident.'}],
                              [{'conflict_index': 0, 'verdict': 'SOURCES_AGREE', 'rationale': 'Same rule; wording differs.'}])
    client = Fake(draft=draft, tot=lambda p: comparison(p, 'INC', [no_action(p)]), grounding=grounding)
    result = run(SOURCES_SCENARIO, client, retriever, unflagged(view, SOURCES_SCENARIO))
    assert result['temporal_before_grounding']['status'] == 'DETECTED' and result['tot']['triggers'] == ['TEMPORAL_CONFLICT']
    assert [(f['code'], f['status']) for f in result['temporal']['findings']] == [
        ('DECLARED_CONFLICT_SOURCES_AGREE', 'RESOLVED_BY_SOURCE_AGREEMENT')]
    assert 'TEMPORAL_CONFLICT' not in codes(result)
    # The same draft with the judge confirming the conflict stays reviewable.
    confirmed = run(SOURCES_SCENARIO, Fake(draft=draft, tot=lambda p: comparison(p, 'INC', [no_action(p)]), grounding=supported),
                    retriever, unflagged(view, SOURCES_SCENARIO))
    assert 'TEMPORAL_CONFLICT' in codes(confirmed)


def _item(eid, use, applicability=None, **extra):
    return {'evidence_id': eid, 'origin': 'retrieved_source', 'use': use, 'citation': {'authoring': f'{eid}@1.0'},
            'applicability': {'state': 'CURRENT', 'unverified_supersession': [], 'replaced_by': [], 'supersedes': [],
                              **(applicability or {})}, 'dates': {}, 'scope': {}, 'recorded_states': {}, **extra}


def _draft(conflicts=()):
    return AdvisorDraft.model_validate({
        'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
        'severity': {'level': 'LOW', 'rationale': 'x'},
        'claims': [{'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Sources on the rule.', 'evidence_ids': ['k:a']}],
        'source_conflicts': [{'evidence_ids': list(c), 'description': 'Declared.'} for c in conflicts]})


def _relation(*ids):
    return {'relations': [{'evidence_ids': list(ids), 'relation': 'CONFLICT', 'point': 'The rule',
                           'disagreement_scope': 'which cases', 'rationale': 'Prepared.'}], 'declared_conflict_checks': []}


ENACTED = {'status': 'ENACTED', 'basis': 'RECORDED_ENACTMENT', 'governing_sources': ['k:dec@1.0'], 'missing': []}
UNENACTED = {'status': 'NOT_ENACTED', 'basis': None, 'governing_sources': [], 'missing': ['NO_ENACTMENT_EVIDENCE']}


@pytest.mark.parametrize('other, code, status', [
    (_item('k:b', 'CURRENT_GUIDANCE'), 'SOURCE_CONFLICT_FOUND_IN_GROUNDING', 'DETECTED'),
    (_item('k:b', 'ENACTED_DECISION', {'enactment': ENACTED}), 'SOURCE_CONFLICT_FOUND_IN_GROUNDING', 'DETECTED'),
    # Approved, in scope, effective, but no enactment evidence: not current, still reviewable against current guidance.
    (_item('k:b', 'PRIOR_DECISION', {'enactment': UNENACTED}), 'SOURCE_CONFLICT_FOUND_IN_GROUNDING', 'DETECTED'),
    (_item('k:b', 'PRIOR_DECISION', recorded_states={'execution_status': 'not_executed'}), 'OTHER_SOURCES_DO_NOT_COMPETE',
     'NOT_A_CURRENT_CONFLICT'),
    (_item('k:b', 'HISTORY_ONLY', {'state': 'SECTION_SUPERSEDED', 'replaced_by': [{'replaced_by': 'k:a@1.0'}]}),
     'HISTORICAL_DIFFERENCE', 'NOT_A_CURRENT_CONFLICT'),
    (_item('k:b', 'HISTORY_ONLY', {'state': 'WITHDRAWN'}), 'OTHER_SOURCES_DO_NOT_COMPETE', 'NOT_A_CURRENT_CONFLICT'),
    (_item('k:b', 'ANNOUNCEMENT'), 'ANNOUNCEMENT_NOT_ESTABLISHED', 'NOT_A_SOURCE_CONFLICT'),
    ({'evidence_id': 'k:b', 'origin': 'member_message', 'use': 'MEMBER_REPORT'}, 'MEMBER_DISAGREEMENT', 'NOT_A_SOURCE_CONFLICT'),
])
def test_grounding_conflicts_follow_temporal_eligibility(other, code, status):
    """A conflict the judge reports is routed only between current sources (or with uncertain applicability);
    historical differences, records out of the running, unverified announcements and member messages are not
    current-source conflicts."""
    from threadsense.agents.advisor_checks import temporal_check
    ledger = {'k:a': _item('k:a', 'CURRENT_GUIDANCE'), 'k:b': other}
    temporal = temporal_check(_draft(), ledger, set(), {}, _relation('k:a', 'k:b'))
    [finding] = temporal['findings']
    assert (finding['code'], finding['status'], finding['origin']) == (code, status, 'FINAL_GROUNDING')
    assert temporal['status'] == ('DETECTED' if status == 'DETECTED' else 'NONE_FOUND')


def test_recorded_supersession_explains_a_declared_conflict_whatever_the_judge_says():
    """Paired with the agreement case: documented supersession settles a declared conflict by record; a judge's
    CONFIRMED does not reopen it. Without an assessment (recorded v4 judgments) the result says NOT_ASSESSED."""
    from threadsense.agents.advisor_checks import temporal_check
    ledger = {'k:a': _item('k:a', 'CURRENT_GUIDANCE'),
              'k:b': _item('k:b', 'HISTORY_ONLY', {'state': 'SECTION_SUPERSEDED', 'replaced_by': [{'replaced_by': 'k:a@1.0'}]})}
    checks = {'relations': [], 'declared_conflict_checks': [{'conflict_index': 0, 'verdict': 'CONFIRMED', 'rationale': 'x'}]}
    temporal = temporal_check(_draft([('k:a', 'k:b')]), ledger, set(), {}, checks)
    assert [f['status'] for f in temporal['findings']] == ['RESOLVED_BY_RECORDED_SUPERSESSION']
    assert temporal['status'] == 'NONE_FOUND' and temporal['source_consistency'] == 'ASSESSED'
    assert temporal_check(_draft(), ledger, set())['source_consistency'] == 'NOT_ASSESSED'


def test_grounding_v5_requires_the_assessment_and_v4_replays_without_it():
    from pydantic import ValidationError
    from threadsense.agents.advisor_contracts import GroundingJudgment
    with pytest.raises(ValidationError):
        GroundingJudgment.model_validate({'verdicts': []})
    with pytest.raises(ValidationError):  # A conflict states what differs.
        GroundingJudgment.model_validate({'verdicts': [], 'source_consistency': {'relations': [
            {'evidence_ids': ['a', 'b'], 'relation': 'CONFLICT', 'point': 'p', 'rationale': 'r'}]}})
    assert GroundingJudgment.model_validate({'contract_version': 'agent3-grounding-judgment-v4', 'verdicts': []}).source_consistency is None
