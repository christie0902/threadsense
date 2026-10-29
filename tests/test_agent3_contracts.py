"""Agent 3 v1 contracts: structural guardrails only, no semantic assessment."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from threadsense.agents.advice_contracts import (
    AdviceCard, AnnouncementRecord, CardChecks, CountEvidence, DecisionRecord, ModelReviewItem, OccurrenceEvidence,
    SeverityAssessment, confidence_band, record_review_action, stable_id, unassessed_severity,
)
from threadsense.knowledge_markdown import markdown_source
from threadsense.severity_rubric import compatibility_issues, load_rubric, signal_reference_issues

KNOWLEDGE = Path(__file__).resolve().parents[1]/'data/knowledge'
SOURCE = {'kind': 'knowledge_source', 'project_id': 'audio_multimodal', 'scope': 'project',
          'document_id': 'knowledge_x', 'version_id': 'version_x'}
SLACK = {'kind': 'slack_message', 'channel_id': 'C_AUDIO_QA', 'thread_id': '1790000000.000100',
         'message_id': '1790000000.000100'}


def lineage(**overrides):
    return {'agent3_run_id': 'run-1', 'handoff_contract': 'agent2-taxonomy-handoff-v2', 'agent2_export_sha256': 'a'*64,
            'agent2_schema_version': 8, 'candidate_group_id': 'g1', 'topic_id': 'g1/topic_1',
            'member_ids': ['m1', 'm2'], 'project_id': 'audio_multimodal', **overrides}


def assessed(level='MEDIUM', signals=None):
    rubric = load_rubric('audio_multimodal')
    if signals is None:
        signals = [] if level not in {'MEDIUM', 'HIGH'} else [
            {'level': level, 'signal_index': 0, 'signal_text': rubric['levels'][level]['required_signals'][0],
             'support': 'Described behaviour supports this signal.', 'evidence': [SLACK]}]
    return {'level': level, 'assessment_status': 'ASSESSED', 'rubric_version': rubric['version'],
            'rubric_content_sha256': rubric['content_sha256'], 'rubric_scope': rubric['rubric_scope'],
            'rationale': 'Rubric applied to cited evidence.',
            'matched_signals': signals}


def card(**overrides):
    value = {'card_id': stable_id('card', {'topic': 'g1/topic_1'}), 'project_id': 'audio_multimodal',
             'topic_name': 'Playback stalls', 'card_line': 'RECOMMENDED_ACTION', 'summary': 'Playback stalls.',
             'severity': assessed(), 'severity_is_provisional': False, 'resolution_status': 'UNRESOLVED',
             'recommended_action': {'action_type': 'POST_ALIGNMENT', 'draft_text': 'Draft.'},
             'reasoning': 'Grounded in cited sources.', 'supporting_sources': [SOURCE], 'confidence': 0.9,
             'checks': {'grounding': 'PASSED'}, 'lineage': lineage()}
    value.update(overrides)
    return AdviceCard.model_validate(value)


def test_confidence_bands_include_exact_boundaries():
    assert [confidence_band(v) for v in (0.0, 0.5999, 0.60, 0.8499, 0.85, 1.0)] == [
        'LOW', 'LOW', 'MODERATE', 'MODERATE', 'HIGH', 'HIGH']
    assert card(confidence=0.60).confidence_band == 'MODERATE'
    assert card(confidence=0.85).confidence_band == 'HIGH'
    with pytest.raises(ValidationError, match='LOW_CONFIDENCE'):
        card(confidence=0.5999)
    low = card(confidence=0.59, card_line='NEEDS_REVIEW',
               needs_review_reasons=[{'code': 'LOW_CONFIDENCE', 'detail': 'Below 0.60.'}])
    assert low.confidence_band == 'LOW'
    with pytest.raises(ValidationError, match='band'):
        card(confidence=0.9, confidence_band='MODERATE')


def test_high_severity_and_inherited_flags_cannot_be_recommended_actions():
    with pytest.raises(ValidationError, match='HIGH_SEVERITY'):
        card(severity=assessed('HIGH'), confidence=0.99)
    flag = {'origin': 'agent1', 'kind': 'inherited_agent1_review', 'candidate_group_id': 'g1', 'member_ids': ['m1']}
    with pytest.raises(ValidationError, match='INHERITED_FLAG'):
        card(inherited_flags=[flag])
    with pytest.raises(ValidationError, match='NEEDS_REVIEW line'):
        card(inherited_flags=[flag], needs_review_reasons=[{'code': 'INHERITED_FLAG', 'detail': 'Agent 1 flag.'}])
    review = card(card_line='NEEDS_REVIEW', severity=assessed('HIGH'), inherited_flags=[flag], needs_review_reasons=[
        {'code': 'HIGH_SEVERITY', 'detail': 'HIGH always needs TL review.'},
        {'code': 'INHERITED_FLAG', 'detail': 'Agent 1 flag.'},
        {'code': 'OTHER', 'detail': 'First extra reason.'}, {'code': 'OTHER', 'detail': 'Second extra reason.'}])
    assert [r.code for r in review.needs_review_reasons] == ['HIGH_SEVERITY', 'INHERITED_FLAG', 'OTHER', 'OTHER']


@pytest.mark.parametrize('check,value,code', [('temporal_conflict', 'DETECTED', 'TEMPORAL_CONFLICT'),
                                              ('grounding', 'FAILED', 'GROUNDING_FAILURE'),
                                              ('open_confirmation', 'OPEN', 'OPEN_CONFIRMATION')])
def test_recorded_check_failures_force_needs_review(check, value, code):
    with pytest.raises(ValidationError, match=code):
        card(checks={check: value})
    assert card(checks={check: value}, card_line='NEEDS_REVIEW',
                needs_review_reasons=[{'code': code, 'detail': 'Recorded by checker.'}]).card_line == 'NEEDS_REVIEW'


def test_recommended_action_requires_grounding_passed():
    with pytest.raises(ValidationError, match='grounding PASSED; it is NOT_RUN'):
        card(checks={'grounding': 'NOT_RUN'}, confidence=0.99)
    with pytest.raises(ValidationError, match='GROUNDING_FAILURE'):
        card(checks={'grounding': 'FAILED'}, confidence=0.99)
    assert card(checks={'grounding': 'PASSED'}, confidence=0.85).card_line == 'RECOMMENDED_ACTION'


def test_grounding_not_run_is_an_unready_state_not_a_failure():
    waiting = card(checks={'grounding': 'NOT_RUN'}, card_line='NEEDS_REVIEW',
                   needs_review_reasons=[{'code': 'GROUNDING_NOT_RUN', 'detail': 'Grounding check not yet run.'}])
    assert waiting.checks.grounding == 'NOT_RUN' and waiting.recommended_action.action_type == 'POST_ALIGNMENT'
    for checked in ('PASSED', 'FAILED'):
        with pytest.raises(ValidationError, match='GROUNDING_NOT_RUN'):
            card(checks={'grounding': checked}, card_line='NEEDS_REVIEW', needs_review_reasons=[
                {'code': 'GROUNDING_NOT_RUN', 'detail': 'x'}, {'code': 'GROUNDING_FAILURE', 'detail': 'x'}])
    # An unrun check cannot be reported as a grounding failure.
    with pytest.raises(ValidationError, match='GROUNDING_FAILURE'):
        card(checks={'grounding': 'NOT_RUN'}, card_line='NEEDS_REVIEW',
             needs_review_reasons=[{'code': 'GROUNDING_FAILURE', 'detail': 'Not actually checked.'}])


def test_reasons_cannot_contradict_checks_and_grounding_defaults_to_not_run():
    assert CardChecks().grounding == 'NOT_RUN'
    with pytest.raises(ValidationError, match='contradict'):
        card(checks={'grounding': 'PASSED'}, card_line='NEEDS_REVIEW',
             needs_review_reasons=[{'code': 'GROUNDING_FAILURE', 'detail': 'x'}])


def test_card_lines_and_scope():
    with pytest.raises(ValidationError, match='operational recommended action'):
        card(recommended_action={'action_type': 'NO_ACTION'})
    with pytest.raises(ValidationError, match='supporting sources'):
        card(supporting_sources=[])
    assert card(card_line='OBSERVATION', recommended_action={'action_type': 'NO_ACTION'}).card_line == 'OBSERVATION'
    with pytest.raises(ValidationError, match='another project'):
        card(supporting_sources=[{**SOURCE, 'project_id': 'safety_classification'}])
    with pytest.raises(ValidationError, match='lineage'):
        card(lineage=lineage(project_id='safety_classification'))


def test_unknown_counts_are_never_zero():
    assert CountEvidence().count is None and OccurrenceEvidence().affected_tasks.status == 'UNKNOWN'
    with pytest.raises(ValidationError, match='unknown count'):
        CountEvidence(status='UNKNOWN', count=0)
    with pytest.raises(ValidationError, match='basis'):
        CountEvidence(status='KNOWN', count=2)
    with pytest.raises(ValidationError, match='distinct'):
        CountEvidence(status='KNOWN', count=2, ids=['U1', 'U1'], basis='quoted reports')
    with pytest.raises(ValidationError, match='semantic identification'):
        OccurrenceEvidence(affected_reporters={'status': 'KNOWN', 'count': 2, 'ids': ['U1', 'U2'], 'basis': 'x'})
    assessed_counts = OccurrenceEvidence(
        semantic_identification='ASSESSED', affected_reporters={'status': 'LOWER_BOUND', 'count': 2, 'ids': ['U1', 'U2'], 'basis': 'x'},
        known_denominator={'count': 12, 'unit': 'reporters', 'basis': 'Active batch roster.'})
    assert assessed_counts.affected_tasks.count is None
    with pytest.raises(ValidationError, match='denominator'):
        OccurrenceEvidence(semantic_identification='ASSESSED', known_denominator={'count': 1, 'unit': 'tasks', 'basis': 'x'},
                           affected_tasks={'status': 'KNOWN', 'count': 2, 'ids': ['T1', 'T2'], 'basis': 'x'})


def test_severity_is_bound_to_the_existing_rubric_and_separate_from_confidence():
    rubric = load_rubric()
    assert rubric['version'] == 'severity-rubric-v3-semantic-signals' and compatibility_issues(rubric) == []
    assert rubric['rubric_scope'] == 'SHARED_DEFAULT' and load_rubric('safety_classification')['rubric_scope'] == 'SHARED_DEFAULT'
    severity = SeverityAssessment.model_validate(assessed('HIGH'))
    assert signal_reference_issues(severity, rubric) == []
    wrong = SeverityAssessment.model_validate(assessed('HIGH', [{**assessed('HIGH')['matched_signals'][0], 'signal_text': 'Paraphrase.'}]))
    assert signal_reference_issues(wrong, rubric) == ['Signal HIGH[0] does not match the rubric text.']
    with pytest.raises(ValidationError, match='MEDIUM needs'):
        SeverityAssessment.model_validate(assessed('MEDIUM', []))
    with pytest.raises(ValidationError, match='rubric version'):
        SeverityAssessment(level='LOW', assessment_status='ASSESSED', rationale='x')
    deferred = unassessed_severity({'level': 'UNKNOWN', 'assessment_status': 'UNASSESSED'})
    assert deferred.level == 'UNKNOWN' and deferred.inherited_from['assessment_status'] == 'UNASSESSED'
    with pytest.raises(ValidationError, match='provisional'):
        card(severity=deferred.model_dump())
    assert card(severity=deferred.model_dump(), severity_is_provisional=True, confidence=0.95).confidence == 0.95


def test_rubric_hash_ignores_line_endings(tmp_path):
    text = (KNOWLEDGE/'severity_rubric.py').read_text(encoding='utf-8')
    crlf, lf = tmp_path/'crlf.py', tmp_path/'lf.py'
    crlf.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('utf-8'))
    lf.write_bytes(text.replace('\r\n', '\n').encode('utf-8'))
    assert load_rubric(path=crlf)['content_sha256'] == load_rubric(path=lf)['content_sha256'] == load_rubric()['content_sha256']


def test_review_actions_never_modify_cards_or_silently_clear():
    flag = {'origin': 'agent1', 'kind': 'inherited_agent1_review', 'candidate_group_id': 'g1', 'member_ids': ['m1']}
    operational = card(card_line='NEEDS_REVIEW', inherited_flags=[flag],
                       needs_review_reasons=[{'code': 'INHERITED_FLAG', 'detail': 'Agent 1 flag.'}])
    before = operational.model_dump()
    item = ModelReviewItem(item_id=stable_id('review', {'m': 'm1'}), origin='agent1', kind='inherited_agent1_review',
                           project_id='audio_multimodal', candidate_group_id='g1', member_ids=['m1'], reason='Flagged.',
                           related_card_ids=[operational.card_id])
    deferred = record_review_action(item, {'action': 'DEFER', 'actor_id': 'U006', 'acted_at': '2026-10-01T12:00:00Z'})
    accepted = record_review_action(deferred, {'action': 'ACCEPT', 'actor_id': 'U006', 'acted_at': '2026-10-01T13:00:00Z'})
    assert item.review_state == deferred.review_state == 'OPEN' and accepted.review_state == 'ACCEPTED'
    assert [a.action for a in accepted.actions] == ['DEFER', 'ACCEPT'] and item.actions == []
    assert operational.model_dump() == before and operational.inherited_flags
    with pytest.raises(ValidationError):
        operational.card_line = 'RECOMMENDED_ACTION'
    with pytest.raises(ValidationError, match='pattern'):
        ModelReviewItem(item_id=operational.card_id, origin='agent1', kind='k', project_id='p', candidate_group_id='g',
                        member_ids=['m1'], reason='r')


def decision(**overrides):
    value = {'decision_id': 'D1', 'project_id': 'audio_multimodal',
             'tl_response': {'outcome': 'APPROVED', 'actor_id': 'U006', 'approved_actions': ['POST_ALIGNMENT']},
             'execution': {'state': 'NOT_EXECUTED'}, 'outcome': {'state': 'NOT_OBSERVED'}}
    value.update(overrides)
    return DecisionRecord.model_validate(value)


def test_decision_stages_stay_distinct():
    approved = decision()
    assert approved.execution.state == 'NOT_EXECUTED' and approved.outcome.state == 'NOT_OBSERVED'
    with pytest.raises(ValidationError, match='execution'):
        DecisionRecord(decision_id='D', project_id='p', tl_response={'outcome': 'APPROVED', 'actor_id': 'U'},
                       outcome={'state': 'NOT_OBSERVED'})
    with pytest.raises(ValidationError, match='not approved'):
        decision(tl_response={'outcome': 'REJECTED', 'actor_id': 'U006'}, execution={'state': 'COMPLETED'})
    assert decision(tl_response={'outcome': 'REJECTED', 'actor_id': 'U006'},
                    outcome={'state': 'RESOLVED', 'source_status': 'resolved_in_checked_tasks'}).outcome.state == 'RESOLVED'
    with pytest.raises(ValidationError, match='edited'):
        decision(tl_response={'outcome': 'APPROVED_WITH_EDITS', 'actor_id': 'U006'})
    with pytest.raises(ValidationError, match='change the proposed'):
        decision(tl_response={'outcome': 'OVERRIDDEN', 'actor_id': 'U006',
                              'severity_override': {'proposed': 'HIGH', 'tl_selected': 'HIGH', 'reason': 'x'}})
    with pytest.raises(ValidationError, match='approves no operational'):
        decision(tl_response={'outcome': 'DEFERRED', 'actor_id': 'U006', 'approved_actions': ['POST_ALIGNMENT']})


def test_announcement_record_reuses_source_record():
    source = markdown_source(KNOWLEDGE/'decisions/safety_classification/2026-09-11_fictional_pii_clarification_posted.md')
    record = AnnouncementRecord(source=source)
    assert record.document_id == source.record_id and record.source.source.message_id == '1789135200.700004'
    guideline = markdown_source(KNOWLEDGE/'instructions/safety_classification_instructions.md')
    with pytest.raises(ValidationError, match='announcement'):
        AnnouncementRecord(source=guideline)
