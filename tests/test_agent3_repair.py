"""Repair pass: intervention need in the final grounding (MOCKED SEMANTIC verdicts; DETERMINISTIC routing), contract
compatibility for recorded drafts, and summary-writing rules. Evidence comes from each payload; no topic is named in
the logic under test."""
import json

import pytest
from pydantic import ValidationError

from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.advisor_pilot import DRAFT_RULES, GROUNDING_RULES, LEGACY_LABELS, REVISION_RULES
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, supported, view,
)


def questions_draft(payload, kind='UNRESOLVED_HANDLING_QUESTION'):
    """A reminder whose stated need is the members' handling questions (their own messages, cited)."""
    asked = [i['evidence_id'] for i in payload['member_evidence'] if i['author_role'] in ('TUTOR', 'QA_TUTOR')][:2]
    base = draft_for(payload)
    return {**base, 'proposed_action': {**base['proposed_action'], 'intervention_need': {
        'kind': kind, 'statement': 'Several members ask how to handle this and their threads do not settle it.',
        'evidence_ids': asked}}}


def scenario_with_action(view):
    from tests.test_agent3_advisor import SCEN
    return next(iter(k for k in SCEN if not SCEN[k].get('control')))


def test_need_is_judged_in_the_same_final_grounding_call(retriever, view):
    sent = []
    result = run(scenario_with_action(view), Fake(draft=questions_draft, grounding=lambda p: sent.append(p) or supported(p)),
                 retriever, view)
    assert len(sent) == 1 and 'intervention' not in [s for s, _ in result.get('stages', [])]  # One grounding call only.
    assert sorted({c['stage'] for c in result['model_calls']}) <= ['draft', 'grounding', 'revision', 'tot']
    need = next(s for s in sent[0]['statements'] if s['statement_id'] == 'action:need')
    assert need['kind'] == 'INTERVENTION_NEED' and need['text'].startswith('Why intervening now is needed (an unresolved handling question)')
    assert need['evidence_ids'] and all(e.startswith('m:') for e in need['evidence_ids'])


def test_observation_without_an_intervention_need_carries_no_action(retriever, view):
    """The judge finds the questions already answered (need UNSUPPORTED): the action is withheld, but that alone is not
    a grounding failure and the card line still comes from the review reasons only."""
    scenario = scenario_with_action(view)
    result = run(scenario, Fake(draft=questions_draft, grounding=lambda p: supported(p, **{'action:need': 'UNSUPPORTED'})),
                 retriever, view)
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['action'] == 'NO_INTERVENTION_NEED' and verdicts['action:need'] == 'UNSUPPORTED'
    assert result['grounding']['status'] == 'PASSED' and 'GROUNDING_FAILURE' not in codes(result)
    card = result['card']
    assert card['recommended_action'] is None
    assert any('did not show a need to intervene now' in n for n in card['review_notes'])
    # Inherited flags still route to Needs Review; nothing else changes the line.
    assert card['card_line'] == ('NEEDS_REVIEW' if card['inherited_flags'] or codes(result) else 'OBSERVATION')
    assert set(codes(result)) <= {'INHERITED_FLAG', 'HIGH_SEVERITY', 'OPEN_CONFIRMATION', 'TEMPORAL_CONFLICT', 'OTHER'}


def test_repeated_unanswered_handling_questions_justify_a_reminder(retriever, view):
    """The paired case: the same reminder, with the need judged SUPPORTED (questions that their threads leave open),
    reaches the card. Existing guidance does not by itself rule the reminder out."""
    result = run(scenario_with_action(view), Fake(draft=questions_draft, grounding=supported), retriever, view)
    assert {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}['action'] == 'SUPPORTED'
    assert result['card']['recommended_action']['action_type'] == 'POST_ALIGNMENT'
    assert not any('did not show a need' in n for n in result['card']['review_notes'])


def test_pending_need_is_never_counted_as_supported(retriever, view):
    result = run(scenario_with_action(view), Fake(draft=questions_draft, grounding=lambda p: {
        **supported(p), 'verdicts': [v for v in supported(p)['verdicts'] if v['statement_id'] != 'action:need']}), retriever, view)
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['action'] == 'NOT_JUDGED' and result['card']['recommended_action'] is None


def test_unsupported_need_blocks_the_tot_fallback_too():
    from threadsense.agents.advisor_tot import fallback
    draft = AdvisorDraft.model_validate({
        'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
        'severity': {'level': 'LOW', 'rationale': 'x'},
        'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A tutor reports it.', 'evidence_ids': ['m:C:1.1']}],
        'proposed_action': {'action_type': 'POST_ALIGNMENT', 'draft_text': 'd', 'support_claim_ids': ['c1'],
                            'intervention_need': {'kind': 'GUIDANCE_GAP', 'statement': 's', 'evidence_ids': ['m:C:1.1']}}})
    action, _, note = fallback({'status': 'COMPARED'}, draft, 'NO_INTERVENTION_NEED')
    assert action is None and 'did not show a need to intervene' in note


def test_v7_requires_a_need_for_operational_actions_but_recorded_v6_drafts_keep_their_rules():
    base = {'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
            'severity': {'level': 'LOW', 'rationale': 'x'},
            'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A tutor reports it.', 'evidence_ids': ['m:C:1.1']}],
            'proposed_action': {'action_type': 'POST_ALIGNMENT', 'draft_text': 'd', 'support_claim_ids': ['c1']}}
    with pytest.raises(ValidationError, match='intervention_need'):
        AdvisorDraft.model_validate(base)
    assert AdvisorDraft.model_validate({**base, 'contract_version': LEGACY_LABELS['AdvisorDraft']}).proposed_action
    no_action = {**base, 'proposed_action': {'action_type': 'NO_ACTION', 'support_claim_ids': ['c1']}}
    assert AdvisorDraft.model_validate(no_action).proposed_action.intervention_need is None


def test_prompts_teach_need_and_summary_distinctions_without_relaxing_the_judge():
    for rules in (DRAFT_RULES, REVISION_RULES):
        assert 'intervention_need' in rules and '"a reminder might help" is not a need' in rules
        assert 'already answered in the thread are not unresolved' in rules and 'not from keywords' in rules
        assert 'a symptom only some of them report' in rules and 'a reported symptom versus a confirmed finding' in rules
        assert 'asking a question versus a member reporting being affected' in rules
    assert 'INTERVENTION_NEED says why intervening now is needed' in GROUNDING_RULES
    # The judge's standard for displayed text is unchanged: it still judges the exact text shown.
    assert 'judge that exact text' in GROUNDING_RULES and 'must not overstate the evidence' in GROUNDING_RULES


def test_open_confirmation_is_a_team_lead_question_not_pending_diagnosis():
    """ToT trigger audit: inherited flags are not a trigger, and the open-confirmation trigger is defined as a handling
    or policy question for the team lead; the final judge applies the same (stricter) criterion. Legitimate triggers
    (temporal conflict, low confidence, a real open question) are unchanged."""
    from threadsense.agents.advisor_tot import triggers
    for rules in (DRAFT_RULES, REVISION_RULES):
        assert 'A technical cause not yet diagnosed, diagnostic results not yet collected' in rules
        assert 'earlier review flags (already carried with the card) are not open confirmations' in rules
    assert 'a not-yet-diagnosed cause, pending diagnostic results or a pending expert assessment is not one' in GROUNDING_RULES
    class D:  # The trigger reads only these fields; inherited flags are not among them.
        confidence, open_confirmation = 0.9, 'NONE'
    assert triggers(D(), {'status': 'NONE_FOUND'}) == []
    D.open_confirmation = 'OPEN'
    assert triggers(D(), {'status': 'DETECTED'}) == ['TEMPORAL_CONFLICT', 'OPEN_CONFIRMATION']


@pytest.mark.parametrize('text, flagged', [
    ('One of the tutors also reports a visible waveform with no sound.', False),  # Observed live (repair run, audio).
    ('Each of the tutors reports the same symptom.', False),
    ('Tutors also report a visible waveform with no sound.', True),
    ('Two tutors report a visible waveform with no sound.', True),
])
def test_singular_partitive_is_not_a_plural_claim(text, flagged):
    """The rule was wrong for "one of the tutors ... reports" (one author cited); real plurals are still checked."""
    from threadsense.agents.advisor_checks import prose_issues
    item = {'evidence_id': 'm:C:1.1', 'origin': 'member_message', 'author_id': 'U018', 'author_role': 'TUTOR',
            'thread_starter_id': 'U018'}
    codes = [c for c, _ in prose_issues(text, [item], {'m:C:1.1': item})]
    assert ('PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS' in codes) == flagged


def test_member_disagreement_is_not_a_temporal_source_conflict():
    """QA misalignment (baseline): two QA tutors' opposing replies were declared as source conflicts and became
    UNEXPLAINED_SOURCE_CONFLICT (a temporal review reason and a ToT trigger). Members disagreeing is reported evidence."""
    from threadsense.agents.advisor_checks import temporal_check
    msg = lambda i, role: {'evidence_id': f'm:C:{i}', 'origin': 'member_message', 'author_role': role, 'use': 'MEMBER_REPORT'}
    ledger = {e['evidence_id']: e for e in (msg('1.1', 'QA_TUTOR'), msg('1.2', 'QA_TUTOR'))}
    draft = AdvisorDraft.model_validate({
        'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
        'severity': {'level': 'LOW', 'rationale': 'x'},
        'source_conflicts': [{'evidence_ids': ['m:C:1.1', 'm:C:1.2'], 'description': 'One QA tutor rejects the tie, another accepts it.'}]})
    result = temporal_check(draft, ledger)
    assert result['status'] == 'NONE_FOUND' and result['findings'][0]['code'] == 'MEMBER_DISAGREEMENT'


def test_intervention_need_text_gets_the_prose_checks():
    """The need statement is judged, though not displayed: role and count wording are checked like other statements."""
    from threadsense.agents.advisor_checks import presentation_issues
    item = {'evidence_id': 'm:C:1.1', 'origin': 'member_message', 'author_id': 'U018', 'author_role': 'TUTOR',
            'thread_starter_id': 'U018'}
    draft = AdvisorDraft.model_validate({
        'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
        'severity': {'level': 'LOW', 'rationale': 'x'},
        'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A tutor reports it.', 'evidence_ids': ['m:C:1.1']}],
        'proposed_action': {'action_type': 'POST_ALIGNMENT', 'draft_text': 'd', 'support_claim_ids': ['c1'],
                            'intervention_need': {'kind': 'UNRESOLVED_HANDLING_QUESTION', 'evidence_ids': ['m:C:1.1'],
                                                  'statement': 'Three tutors ask how to handle this.'}}})
    issues = [i for i in presentation_issues(draft, {'m:C:1.1': item}) if i['statement_id'] == 'action:need']
    assert [i['code'] for i in issues] == ['PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']


def test_replay_reads_overnight_runs_with_their_recorded_retrieval(tmp_path):
    from threadsense.agents.advisor_pilot import ReplayClient
    import json as _json
    (tmp_path/'topics').mkdir()
    for name, ledger in (('a', {'k:x': {'retrieved_as': {'role': 'TYPE_COVERAGE'}}}), ('b', {})):
        (tmp_path/'topics'/f'{name}.json').write_text(_json.dumps({'work_item': {'work_id': name}, 'result': {
            'scenario': {'id': name}, 'model_calls': [], 'grounding': {'statements': []}, 'evidence_ledger': ledger}}), encoding='utf-8')
    client = ReplayClient(tmp_path)
    assert set(client.recorded) == {'a', 'b'} and client.retrieval_expansion is True
    (tmp_path/'topics'/'a.json').unlink()
    assert ReplayClient(tmp_path).retrieval_expansion is False  # A run recorded without the expansion replays without it.


def _conflict_draft(ids):
    return AdvisorDraft.model_validate({
        'summary': 's', 'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'confidence': 0.9, 'open_confirmation': 'NONE',
        'severity': {'level': 'LOW', 'rationale': 'x'},
        'claims': [{'claim_id': 'c1', 'kind': 'GUIDANCE', 'text': 'Sources on the rule.', 'evidence_ids': ids}],
        'source_conflicts': [{'evidence_ids': ids, 'description': 'They state different rules.'}]})


def _item(eid, use, applicability=None, **extra):
    """A ledger item shaped like advisor_evidence.evidence_item (only the fields the temporal checks read)."""
    return {'evidence_id': eid, 'origin': 'retrieved_source', 'use': use, 'citation': {'authoring': f'{eid}@1.0'},
            'applicability': {'state': 'CURRENT', 'unverified_supersession': [], 'replaced_by': [], 'supersedes': [],
                              **(applicability or {})}, 'dates': {}, 'scope': {}, 'recorded_states': {}, **extra}


@pytest.mark.parametrize('other, reason, status', [
    (_item('k:old', 'HISTORY_ONLY', dates={'expired_as_of': True}), 'EXPIRED', 'RESOLVED_BY_RECORD'),
    (_item('k:old', 'PRIOR_DECISION', scope={'batch_relation': 'other_batch'}), 'OTHER_BATCH_DECISION', 'NO_CONFLICT'),
    (_item('k:old', 'PRIOR_DECISION', recorded_states={'execution_status': 'not_executed'}), 'DECISION_NOT_EXECUTED', 'NO_CONFLICT'),
    (_item('k:old', 'HISTORY_ONLY', applicability={'state': 'NOT_APPROVED'}), 'NOT_APPROVED', 'NO_CONFLICT'),
])
def test_records_out_of_the_running_do_not_make_a_temporal_conflict(other, reason, status):
    """Temporal golden set T10/T11/T13: expired, other-batch, unexecuted or unapproved records never competed with
    current guidance; recorded state settles it without a date comparison, and the guidance stays the baseline."""
    from threadsense.agents.advisor_checks import temporal_check, temporal_decision
    ledger = {e['evidence_id']: e for e in (_item('k:guide', 'CURRENT_GUIDANCE'), other)}
    draft = _conflict_draft(['k:guide', 'k:old'])
    temporal = temporal_check(draft, ledger)
    assert temporal['status'] == 'NONE_FOUND' and temporal['findings'][0]['not_competing'] == {'k:old': reason}
    decision = temporal_decision(draft, ledger, temporal)
    assert (decision['decision'], decision['baseline'], decision['temporal_status']) == ('DECIDED', ['k:guide'], status)


def test_an_executed_in_scope_decision_still_needs_review():
    """No new override: an executed, in-scope, unexpired decision that conflicts with guidance stays reviewable."""
    from threadsense.agents.advisor_checks import temporal_check, temporal_decision
    executed = _item('k:dec', 'PRIOR_DECISION', recorded_states={'execution_status': 'posted'}, scope={'batch_relation': 'same_batch'})
    ledger = {e['evidence_id']: e for e in (_item('k:guide', 'CURRENT_GUIDANCE'), executed)}
    draft = _conflict_draft(['k:guide', 'k:dec'])
    temporal = temporal_check(draft, ledger)
    assert temporal['status'] == 'DETECTED'
    assert temporal_decision(draft, ledger, temporal)['decision'] == 'ABSTAIN'


def test_temporal_golden_subset_through_production(tmp_path):
    """Three golden cases end to end (throwaway snapshots in pytest's temp directory): tied timestamps abstain, an
    expired directive yields to the guide, a same-day later revision wins (timezone-aware)."""
    import importlib.util
    from threadsense.routing import ROOT
    spec = importlib.util.spec_from_file_location('evaluate_temporal', ROOT/'scripts/evaluate_temporal.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    golden = json.loads((ROOT/'data/evaluation/temporal_golden.json').read_text(encoding='utf-8'))
    cases = {c['id']: c for c in golden['cases']}
    for cid in ('T03_same_day_distinct_times', 'T04_tied_timestamps', 'T13_expired_temporary_directive'):
        forward = module.run_case(cases[cid], golden['defaults'], tmp_path, lambda xs: list(xs))
        backward = module.run_case(cases[cid], golden['defaults'], tmp_path, lambda xs: list(reversed(list(xs))))
        expected = cases[cid]['expected']
        assert (forward['decision'], forward['baseline']) == (expected['decision'], sorted(expected['baseline'])), cid
        assert forward['temporal_status'] == expected['temporal_status'] and forward['baseline'] == backward['baseline']


def test_two_current_sources_in_conflict_stay_a_temporal_conflict():
    """Regression for the non-competing rule: it settles only records out of the running, never current versus current."""
    from threadsense.agents.advisor_checks import temporal_check
    ledger = {e['evidence_id']: e for e in (_item('k:a', 'CURRENT_GUIDANCE'), _item('k:b', 'CURRENT_GUIDANCE'))}
    assert temporal_check(_conflict_draft(['k:a', 'k:b']), ledger)['status'] == 'DETECTED'
