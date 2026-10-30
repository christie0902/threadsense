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
