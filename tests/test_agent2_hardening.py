"""Actual saved-response replay and explicit synthetic v3 regressions are separate."""
from copy import deepcopy
import json
from pathlib import Path
import runpy

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.handoff_inputs import ROOT, read_json, digest, file_hash
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import verification_requests as transport
from threadsense.legacy.agent2.topic_consolidation_v3 import build_request, parse_response, export_result
from threadsense.legacy.agent2.topic_consolidation_v2 import parse_response as parse_v2
from threadsense.agents.topic_diagnostics import describe_exception, ConsolidationValidationError, legacy_diagnostics
from threadsense.legacy.agent2.topic_evidence import evidence_catalog
from threadsense.terminology import get_terms
from tests.agent2_fixtures import membership_only_draft, guidance, severity

HISTORICAL = ROOT / 'data/processed/agent2_full_v1_continued'
REPLAY = runpy.run_path(str(ROOT / 'scripts/replay_agent2_responses.py'))['replay']


@pytest.fixture(scope='module')
def payloads():
    return {p['candidate_group_id']: p for p in load_candidate_payloads(historical=True)}


@pytest.fixture(scope='module')
def cases():
    fixture = read_json(ROOT / 'tests/fixtures/agent2_hardening_v3.json')
    assert fixture['origin'] == 'synthetic_offline_regressions'
    return {c['candidate_group_id']: c for c in fixture['cases']}


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL', 'openai/gpt-4o-mini')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('No paid calls in offline hardening tests.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


def test_original_replay_preserves_34_55_1_and_counts_only_combined_records(tmp_path):
    before = file_hash(HISTORICAL / 'consolidations.json')
    summary = REPLAY(HISTORICAL, tmp_path / 'replay')
    assert summary['response_replay_counts'] == {
        'accepted': 34, 'quotation_mismatch': 29, 'invalid_message_reference': 1,
        'custom_consistency': 15, 'schema': 4, 'malformed_json': 2,
        'membership': 3, 'cross_topic_evidence': 1, 'no_saved_response': 1}
    assert summary['historical_status_counts'] == {'CONSOLIDATED': 34, 'FAILED': 55, 'INTERRUPTED': 1}
    assert summary['historically_consolidated_threads'] == 55
    assert summary['request_attempts'] == summary['combined_groups'] == 90
    assert summary['saved_http_responses'] == 89 and summary['http_status_counts'] == {'200': 89}
    assert summary['retained_threads'] == 200 and summary['inherited_review_obligations'] == 49
    assert summary['unknown_completion_requests'] == ['cluster_128dab46288ce554']
    details = read_json(tmp_path / 'replay/diagnostics.json')
    for row in details:
        for error in row['diagnostics']:
            assert error['message'] and error['exception_type'] and error['group_member_identities']
            assert error['candidate_group_id'] == row['candidate_group_id']
            if error['category'] in {'quotation_mismatch', 'invalid_message_reference', 'cross_topic_evidence'}:
                assert error['field_path'] and error['offending_evidence_reference']
    assert file_hash(HISTORICAL / 'consolidations.json') == before


def test_catalog_contains_only_exact_original_messages_and_request_excludes_labels(payloads, cases):
    p = payloads['cluster_6b59d13144282285']
    aliases, catalog = evidence_catalog(p)
    request = build_request(p, get_terms(), 'openai/gpt-4o-mini')
    data = json.loads(request['messages'][1]['content'])
    assert len(request['messages']) == 2 and data['schema_version'] == 3
    assert len(catalog) == sum(len(m['original_thread']['messages']) for m in p['members'])
    for entry in data['evidence_catalog']:
        original = aliases[entry['member_id']]
        message = next(m for m in original['original_thread']['messages'] if m['message_id'] == entry['message_id'])
        assert entry['quote'] == message['text'] and entry['reactions'] == message['reactions']
        assert all(entry[k] == original[k] for k in ('project_id', 'batch_id', 'channel_id', 'thread_id'))
    serialized = json.dumps(data)
    assert all(label not in serialized for label in ('purpose_not_model_input', 'expected_verdict', 'review_note', 'source_review_outcome', 'candidate_interpretation'))
    reordered = deepcopy(p); reordered['members'].reverse()
    assert evidence_catalog(reordered) == (aliases, catalog)


def test_evidence_resolution_restores_full_identity_and_verbatim_quotation(payloads, cases):
    gid = 'cluster_a6dfe8374217a497'; p = payloads[gid]
    out = export_result(p, parse_response(p, json.dumps(cases[gid]['draft'])), state='CONSOLIDATED')
    answer = out['topics'][0]['provisional_answers'][0]
    ref = answer['evidence'][0]
    member = next(m for m in p['members'] if m['member_id'] == ref['member_id'])
    message = next(m for m in member['original_thread']['messages'] if m['message_id'] == ref['message_id'])
    assert ref['quote'] == message['text']
    assert 'on its own' in answer['text'] and 'school-context' in answer['scope']['text']
    assert 'independent flags' in answer['limitations'][0]['text']
    assert ref['tl_endorsements'] == [{'reaction': 'agree', 'user_id': 'U006', 'target_message_id': '1790893058.000113'}]
    assert not any('No definitive guidance' in c['text'] for c in out['topics'][0]['uncertainties'])
    assert out['review_required']  # Source uncertainty is distinct from inherited Agent 1 disputes.
    assert len(out['inherited_review_obligations']) == sum(m['agent1_record']['review_required'] for m in p['members'])
    assert out['topics'][0]['preliminary_severity']['level'] == 'UNKNOWN'


@pytest.mark.parametrize('gid', ['cluster_1ba596334ad5cde7', 'cluster_6b59d13144282285', 'cluster_a6dfe8374217a497'])
def test_reviewed_completeness_cases_use_real_parser_and_retain_original_questions(payloads, cases, gid):
    p = payloads[gid]; draft = deepcopy(cases[gid]['draft'])
    result = parse_response(p, json.dumps(draft))
    exported = export_result(p, result, state='CONSOLIDATED')
    assert exported['members'] == p['members']
    assert any(t.open_questions for t in result.topics)
    if gid == 'cluster_1ba596334ad5cde7':
        assert any('later announcement replaces' in q.text for q in result.topics[0].open_questions)
        assert 'declaring either document superseded' in result.topics[0].guidance[0].text
    if gid == 'cluster_6b59d13144282285':
        assert len(result.topics) == 2
        assert {r['message_id'] for a in exported['topics'][0]['provisional_answers'] for r in a['evidence']} == {'1790920220.000113', '1790934431.000339'}
        assert 'does not establish a current attempt or failure' in result.topics[0].uncertainties[0].text
    draft['topics'][0]['open_questions'] = []
    with pytest.raises(ConsolidationValidationError, match='OPEN/PARTIAL') as caught:
        parse_response(p, json.dumps(draft))
    detail = describe_exception(p, caught.value)[0]
    assert detail['category'] == 'question_coverage' and detail['member_identity']
    assert detail['offending_evidence_reference']['quote']


def test_available_guidance_cannot_disappear_and_scope_is_required(payloads, cases):
    gid = 'cluster_a6dfe8374217a497'; p = payloads[gid]
    draft = deepcopy(cases[gid]['draft']); draft['topics'][0]['supported_answers'] = []
    with pytest.raises(ConsolidationValidationError, match='Available source guidance'):
        parse_response(p, json.dumps(draft))
    draft = deepcopy(cases[gid]['draft']); del draft['topics'][0]['supported_answers'][0]['scope']
    with pytest.raises(ValueError) as caught:
        parse_response(p, json.dumps(draft))
    assert describe_exception(p, caught.value)[0]['field_path'] == ['topics', 0, 'supported_answers', 0, 'scope']


def test_eyes_or_wrong_reaction_user_cannot_support_tl_endorsement(payloads, cases):
    gid = 'cluster_a6dfe8374217a497'; original = payloads[gid]
    for alteration in ('eyes', 'thumbsup', 'wrong_user'):
        p = deepcopy(original)
        member = next(m for m in p['members'] if m['thread_id'] == '1790893012.001800')
        reaction = member['original_thread']['messages'][1]['reactions'][0]
        if alteration in {'eyes', 'thumbsup'}: reaction['name'] = alteration
        else: reaction['users'] = ['U_DIFFERENT']
        member['agent1_record']['input_sha256'] = digest(member['original_thread'])
        with pytest.raises(ConsolidationValidationError, match='TL endorsement'):
            parse_response(p, json.dumps(cases[gid]['draft']))


@pytest.mark.parametrize('emoji', ['this', 'agree', 'white_check_mark'])
def test_endorsements_reuse_existing_policy_and_actual_tl_target(payloads, cases, emoji):
    gid = 'cluster_a6dfe8374217a497'; p = deepcopy(payloads[gid])
    member = next(m for m in p['members'] if m['thread_id'] == '1790893012.001800')
    member['original_thread']['messages'][1]['reactions'][0]['name'] = emoji
    member['agent1_record']['input_sha256'] = digest(member['original_thread'])
    result = parse_response(p, json.dumps(cases[gid]['draft']))
    assert result.topics[0].supported_answers[0].authority == 'TL_ENDORSED'


@pytest.mark.parametrize('mutation, category', [
    ('malformed', 'malformed_json'), ('schema', 'schema'), ('consistency', 'custom_consistency'),
    ('membership', 'membership'), ('unknown', 'invalid_evidence_reference'),
    ('duplicate', 'duplicate_evidence'), ('source_coverage', 'source_coverage'), ('answer', 'answer_evidence'),
])
def test_diagnostic_categories_and_actionable_paths(payloads, mutation, category):
    p = payloads['cluster_6b59d13144282285']; draft = membership_only_draft(p); t = draft['topics'][0]
    if mutation == 'schema': del t['shared_issue']
    elif mutation == 'consistency': draft['is_coherent'] = False
    elif mutation == 'membership': t['member_ids'].pop()
    elif mutation == 'unknown': t['shared_issue']['evidence_ids'][0] = 'E999'
    elif mutation == 'duplicate': t['shared_issue']['evidence_ids'].append(t['shared_issue']['evidence_ids'][0])
    elif mutation == 'source_coverage': t['source_assessments'].pop()
    elif mutation == 'answer':
        t['supported_answers'] = [guidance('Synthetic unsupported root-only answer.', [t['shared_issue']['evidence_ids'][0]], scope='Synthetic test.')]
    raw = '{' if mutation == 'malformed' else json.dumps(draft)
    with pytest.raises(ValueError) as caught:
        parse_response(p, raw)
    detail = describe_exception(p, caught.value)[0]
    assert detail['category'] == category and detail['message'] and detail['group_member_identities']
    if category not in {'malformed_json', 'custom_consistency'}: assert detail['field_path']


@pytest.mark.parametrize('gid, level', [
    ('cluster_024655fb52cc3352', 'N/A'), ('cluster_1ba596334ad5cde7', 'UNKNOWN'),
    ('cluster_14c5fc257d90b58f', 'HIGH'), ('cluster_06c08cf4143f2022', 'HIGH'),
])
def test_reviewed_severity_examples_use_operational_impact(payloads, cases, gid, level):
    p = payloads[gid]
    output = export_result(p, parse_response(p, json.dumps(cases[gid]['draft'])), state='CONSOLIDATED')
    assessment = output['topics'][0]['preliminary_severity']
    assert assessment['level'] == level and assessment['assessor'] == 'agent2'
    assert assessment['rubric_version'] == 'provisional-operational-severity-v1'
    assert assessment['severity_is_provisional'] and assessment['rationale']['evidence']
    if level == 'HIGH':
        assert output['morning_review_obligations'] and output['review_required']
        assert assessment['evidence_basis'] == 'REPORTED_RISK'
    if gid == 'cluster_06c08cf4143f2022':
        assert p['members'][0]['original_thread']['channel_type'] == 'ANNOUNCEMENTS'
        assert output['topics'][0]['representative_question'] is None
        assert not output['topics'][0]['supported_answers']


@pytest.mark.parametrize('level, criterion', [('LOW', 'limited_demonstrated_consequence'), ('N/A', 'non_operational')])
def test_low_na_never_clear_inherited_flags_and_flags_do_not_set_severity(payloads, level, criterion):
    p = payloads['cluster_6b59d13144282285']; draft = membership_only_draft(p)
    # Structural test of flag independence, not a factual assessment of this source.
    refs = draft['topics'][0]['shared_issue']['evidence_ids'][:1]
    draft['topics'][0]['preliminary_severity'] = severity(refs, level, criterion)
    out = export_result(p, parse_response(p, json.dumps(draft)), state='CONSOLIDATED')
    assert out['topics'][0]['preliminary_severity']['level'] == level
    assert len(out['inherited_review_obligations']) == 2 and out['review_required']


@pytest.mark.parametrize('state', ['NOT_RUN', 'FAILED', 'INTERRUPTED'])
def test_unsuccessful_processing_is_unknown_unassessed(payloads, state):
    out = export_result(next(iter(payloads.values())), state=state)
    assert out['severity_assessment_status'] == 'UNASSESSED'
    assert out['unassessed_severity']['level'] == 'UNKNOWN' and not out['topics']


def test_old_saved_response_cannot_pass_v3_parser(payloads):
    gid = 'cluster_6b59d13144282285'
    raw = (HISTORICAL / 'records' / gid / 'analysis.raw.txt').read_text(encoding='utf-8')
    assert parse_v2(payloads[gid], raw).schema_version == 2
    with pytest.raises(ValueError): parse_response(payloads[gid], raw)


@pytest.mark.parametrize('mutation', ['wrong_criterion', 'high_without_impact'])
def test_rubric_requires_matching_criteria_and_cited_impact(payloads, mutation):
    p = next(iter(payloads.values())); draft = membership_only_draft(p)
    assessment = draft['topics'][0]['preliminary_severity']
    if mutation == 'wrong_criterion':
        assessment['matched_criteria'] = ['material_safety_risk']
    else:
        assessment.update(level='HIGH', matched_criteria=['substantial_blockage'], evidence_basis='REPORTED_RISK')
    with pytest.raises(ValueError) as caught:
        parse_response(p, json.dumps(draft))
    detail = describe_exception(p, caught.value)[0]
    assert detail['category'] == 'custom_consistency'
    assert detail['field_path'] == ['topics', 0, 'preliminary_severity']


def test_pipeline_saves_actionable_errors_and_keeps_later_high_review_nonblocking(monkeypatch, tmp_path, payloads, cases):
    gids = ['cluster_6b59d13144282285', 'cluster_06c08cf4143f2022', 'cluster_024655fb52cc3352']
    selected = [payloads[gid] for gid in gids]; calls = []
    def send(endpoint, body, key):
        gid = json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id']; calls.append(gid)
        from tests.agent2_structured_fixtures import reviewed_draft
        draft = reviewed_draft(gid)
        if len(calls) == 1: draft['topics'][0]['shared_issue']['evidence_ids'][0] = 'E999'
        return 200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(draft)}}]}).encode(), None
    monkeypatch.setattr(transport, 'send_once', send)
    out = tmp_path / 'batch'; result = pipeline.execute_batch(selected, out, run=True, maximum_requests=3)
    assert calls == gids and result['processing_counts'] == {'FAILED': 1, 'CONSOLIDATED': 2}
    diagnostics = read_json(out / 'records' / gids[0] / 'diagnostics.json')
    assert diagnostics[0]['category'] == 'invalid_evidence_reference'
    assert diagnostics[0]['offending_evidence_reference'] == {'evidence_id': 'E999'}
    rows = read_json(out / 'consolidations.json')
    assert rows[0]['validation_diagnostics'] == diagnostics
    assert rows[1]['morning_review_obligations'] and rows[2]['processing_state'] == 'CONSOLIDATED'


@pytest.mark.parametrize('filename', ['diagnostics.json', 'result.json'])
def test_diagnostic_or_result_persistence_failure_is_fatal(monkeypatch, tmp_path, payloads, filename):
    selected = list(payloads.values())[:2]; calls = []
    def send(*args):
        calls.append(1)
        return 200, b'{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}', None
    monkeypatch.setattr(transport, 'send_once', send)
    original = pipeline.write_json
    def fail(path, body, **kwargs):
        if Path(path).name == filename: raise OSError('Synthetic disk failure')
        return original(path, body, **kwargs)
    monkeypatch.setattr(pipeline, 'write_json', fail)
    out = tmp_path / 'fatal'
    with pytest.raises(transport.EvidencePersistenceError):
        pipeline.execute_batch(selected, out, run=True, maximum_requests=2)
    manifest = read_json(out / 'manifest.json')
    assert calls == [1] and manifest['state'] == 'failed' and manifest['unprocessed_groups'] == 1
