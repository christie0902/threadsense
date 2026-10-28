"""Offline v4 contract/exports, source regressions and isolated severity validation.

Reviewed synthetic expectations test behavior, never live semantic accuracy.
"""
from copy import deepcopy
import json
from pathlib import Path
import runpy

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import verification_requests as transport
from threadsense.legacy.agent2.topic_consolidation_v4 import build_request, parse_response, export_result
from threadsense.legacy.agent2.topic_consolidation_v3 import parse_response as parse_v3
from threadsense.legacy.agent2.topic_contracts_v4 import TopicConsolidation
from threadsense.agents.topic_effective import load_effective_output, REGISTRY
from threadsense.legacy.agent2.topic_evidence import evidence_catalog
from threadsense.handoff_inputs import ROOT, read_json, digest, file_hash
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, FROZEN, payload, reviewed_draft, wiring_draft, impact


@pytest.fixture(autouse=True)
def no_paid_calls(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL', 'openai/gpt-4o-mini')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-offline-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('No real API calls in offline inventory tests.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


def result(gid, draft=None):
    p = payload(gid)
    return export_result(p, parse_response(p, json.dumps(draft or reviewed_draft(gid))), state='CONSOLIDATED')


@pytest.mark.parametrize('gid', GIDS)
def test_six_reviewed_synthetic_inventories_preserve_every_message_member_and_flag(gid):
    p = payload(gid)
    out = result(gid)
    assert out['factual_validity'] == out['severity_validity'] == 'VALID'
    assert out['members'] == p['members']
    assert out['inherited_review_obligations'] == read_json(FROZEN / 'records' / gid / 'result.json')['inherited_review_obligations']
    topic = out['topics'][0]
    aliases, catalog = evidence_catalog(p)
    assert {r['evidence_id'] for r in topic['source_coverage']} == set(catalog)
    assert {catalog[i['evidence_id']]['member_id'] for i in topic['inventory']} == set(aliases)
    for item in topic['inventory']:
        assert item['text'] in catalog[item['evidence_id']]['quote']
        assert item['evidence'][0]['quote'] == catalog[item['evidence_id']]['quote']
    # No synthetic expected content or source-review judgments enter actual requests.
    request = build_request(p, get_terms(), 'openai/gpt-4o-mini')
    assert len(request['messages']) == 2
    assert 'source_review' not in json.dumps(request)
    assert topic['topic_name'] not in json.dumps(request)


def test_request_has_compact_contract_and_no_independent_display_fields():
    request = build_request(payload(GIDS[0]), get_terms(), 'openai/gpt-4o-mini')
    schema = TopicConsolidation.model_json_schema()
    props = schema['$defs']['ResponseTopic']['properties']
    assert set(props) == {'topic_name', 'member_ids', 'shared_issue', 'relevant_differences', 'inventory', 'dispositions', 'impact'}
    for removed in ('open_questions', 'guidance', 'supported_answers', 'representative_question', 'source_assessments', 'preliminary_severity', 'conversation_kind'):
        assert removed not in props
    assert 'level' not in schema['$defs']['ImpactProposal']['properties']
    system = request['messages'][0]['content']
    assert 'Prompt version: agent2-inventory-v4.0' in system
    assert all(s in system for s in ('NON_OPERATIONAL', 'INSUFFICIENT_EVIDENCE', 'EXACT contiguous', 'same', 'eyes is not', 'OBSERVED_OUTCOME'))
    data = json.loads(request['messages'][1]['content'])
    assert data['schema_version'] == 4
    assert all('eligible_tl_endorsements' in e for e in data['evidence_catalog'])


def test_original_precedence_questions_and_withheld_supersession_survive_adapter():
    t = result(GIDS[0])['topics'][0]
    assert {q['evidence_id'] for q in t['open_questions']} == {'E001', 'E002'}
    assert any('not declaring either document superseded' in g['scope']['text'] for g in t['guidance'])
    assert t['representative_question']['item_id'] in {q['item_id'] for q in t['inventory'] if q['kind'] == 'QUESTION'}


def test_audio_silence_loading_and_scoped_playback_guidance_remain_distinct():
    t = result(GIDS[1])['topics'][0]
    assert t['flagged_member_ids'] and t['supported_answers'] == []
    assert {q['evidence_id'] for q in t['open_questions']} == {'E001', 'E004', 'E008', 'E011', 'E014', 'E016'}
    assert any('waveform' in d['text'] and 'never loads' in d['text'] for d in t['relevant_differences'])
    for eid in ('E007', 'E010', 'E015', 'E019'):
        assert any(g['evidence_id'] == eid for g in t['guidance'])
    assert any('do not mark the recording as a model-quality failure' in g['scope']['text'] for g in t['guidance'])
    assert len(t['provisional_answers']) == 2
    assert all(a['reliability'] == 'PROVISIONAL' for a in t['provisional_answers'])


def test_quarantine_scope_endorsement_and_broader_unanswered_question():
    t = result(GIDS[2])['topics'][0]
    answer = t['supported_answers'][0]
    assert answer['authority'] == 'TL_ENDORSED'
    assert answer['evidence'][0]['tl_endorsements'] == [{'reaction': 'agree', 'user_id': 'U006', 'target_message_id': '1790893058.000113'}]
    assert all(s in answer['scope']['text'] for s in ('school-context', 'on its own', 'independent flags'))
    assert {q['evidence_id'] for q in t['open_questions']} >= {'E001', 'E003', 'E005', 'E007'}
    assert t['preliminary_severity']['level'] == 'UNKNOWN'
    draft = reviewed_draft(GIDS[2])
    broad = next(i for i in draft['topics'][0]['inventory'] if i['evidence_id'] == 'E003')
    broad['question'] = {'status': 'ANSWERED', 'answer_item_ids': ['E002_ANSWER']}
    with pytest.raises(ValueError, match='same thread'):
        parse_response(payload(GIDS[2]), json.dumps(draft))


def test_tentative_avatar_advice_is_partial_and_na_has_criteria():
    t = result(GIDS[3])['topics'][0]
    assert t['open_questions'][0]['question']['status'] == 'PARTIAL'
    assert 'I think' in t['supported_answers'][0]['text']
    assert 'pinned files' in t['supported_answers'][0]['scope']['text']
    assert t['preliminary_severity']['level'] == 'N/A'
    assert t['preliminary_severity']['evidence_basis'] == 'NON_OPERATIONAL'


def test_submit_and_announcement_conditions_have_structured_exports():
    t = result(GIDS[4])['topics'][0]
    assert any('clicking Submit with no effect' in d['text'] for d in t['relevant_differences'])
    assert not t['open_questions']  # Diagnostic requests do not become invented causal questions.
    assert any('until LT confirms it' in g['scope']['text'] for g in t['guidance'])
    assert any('successful reload is not proof' in g['scope']['text'] for g in t['guidance'])
    announcement = result(GIDS[5])['topics'][0]
    assert announcement['conversation_kind'] == 'MIXED'
    assert announcement['representative_question'] is None
    assert announcement['open_questions'][0]['evidence_id'] == 'E002'
    assert len(announcement['guidance']) == 2
    assert any('no policy change' in g['text'] for g in announcement['guidance'])


@pytest.mark.parametrize('gid,eid,text', [
    (GIDS[2], 'E004', 'The child is in harmful content.'),
    (GIDS[4], 'E007', 'What causes all submission failures?'),
    (GIDS[1], 'E004', 'The old workaround was attempted and failed.'),
])
def test_invented_inventory_content_cannot_pass_as_an_exact_source_item(gid, eid, text):
    draft = reviewed_draft(gid)
    next(i for i in draft['topics'][0]['inventory'] if i['evidence_id'] == eid)['text'] = text
    with pytest.raises(ValueError, match='exact source excerpt'):
        parse_response(payload(gid), json.dumps(draft))


def test_real_ids_do_not_establish_synthesis_entailment():
    # Deliberately unsupported synthesis STILL passes traceability. This limitation
    # is explicit; the actual accepted historical error reaches the effective view.
    draft = reviewed_draft(GIDS[2])
    draft['topics'][0]['relevant_differences'][0]['text'] = 'Harmless stories versus harmful content.'
    parsed = parse_response(payload(GIDS[2]), json.dumps(draft))
    assert parsed.topics[0].relevant_differences[0].text == 'Harmless stories versus harmful content.'
    view = load_effective_output(FROZEN)
    row = next(r for r in view['records'] if r['candidate_group_id'] == GIDS[2])
    assert row['processing_state'] == 'CONSOLIDATED' and not row['automated_review_required']
    assert row['effective_review_required'] and row['content_review_obligations']


@pytest.mark.parametrize('mutation', ['missing', 'disposition_and_item', 'all_context', 'invalid_id', 'legacy_question'])
def test_missing_coverage_or_internal_contradictions_do_not_default_to_none(mutation):
    draft = reviewed_draft(GIDS[0]); t = draft['topics'][0]
    if mutation == 'missing': t['inventory'].pop()
    elif mutation == 'disposition_and_item': t['dispositions'] = [{'evidence_id': 'E001', 'disposition': 'NON_SUBSTANTIVE', 'reason': 'Contradiction'}]
    elif mutation == 'all_context':
        t['inventory'][0].update(kind='CONTEXT', question=None)
    elif mutation == 'invalid_id': t['inventory'][0]['evidence_id'] = 'E999'
    else: t['representative_question'] = {'text': 'Invented duplicate', 'evidence_ids': ['E001']}
    with pytest.raises(ValueError): parse_response(payload(GIDS[0]), json.dumps(draft))


def test_question_misclassified_as_fact_and_directive_omission_raise_nonblocking_review():
    draft = reviewed_draft(GIDS[0]); t = draft['topics'][0]
    t['inventory'][0].update(kind='FACT', question=None)
    t['inventory'][-1].update(kind='FACT', question=None)
    out = result(GIDS[0], draft)
    assert out['processing_state'] == 'CONSOLIDATED' and out['review_required']
    warnings = out['topics'][0]['coverage_diagnostics']
    assert {d['offending_evidence_reference']['evidence_id'] for d in warnings} >= {'E001', 'E004'}
    assert not any(q['evidence_id'] == 'E001' for q in out['topics'][0]['open_questions'])  # Cues do not establish meaning.


@pytest.mark.parametrize('bad', [None, {}, {'criteria': [], 'affected_scope': None},
    impact('E999'), impact('E001', 'limited_demonstrated_consequence', 'NON_OPERATIONAL'),
    impact('E001', 'non_operational', 'INSUFFICIENT_EVIDENCE')])
def test_severity_failure_preserves_valid_facts_and_rejected_proposal(bad):
    draft = reviewed_draft(GIDS[3]); draft['topics'][0]['impact'] = bad
    out = result(GIDS[3], draft)
    assert out['processing_state'] == 'CONSOLIDATED' and out['factual_validity'] == 'VALID'
    assert out['severity_validity'] == 'INVALID' and out['review_required']
    topic = out['topics'][0]
    assert topic['open_questions'] and topic['supported_answers']
    assert topic['preliminary_severity']['level'] == 'UNKNOWN'
    assert topic['preliminary_severity']['assessment_status'] == 'UNASSESSED'
    assert topic['rejected_severity_proposal'] == bad
    assert topic['severity_diagnostics'] and out['agent2_review_obligations']


def test_valid_high_cannot_accept_invalid_factual_content():
    draft = reviewed_draft(GIDS[5])
    draft['topics'][0]['inventory'][0]['text'] = 'No source says this.'
    with pytest.raises(ValueError, match='exact source'):
        parse_response(payload(GIDS[5]), json.dumps(draft))


@pytest.mark.parametrize('gid', GIDS)
def test_historical_responses_replay_only_under_original_contract(gid):
    directory = FROZEN / 'records' / gid
    raw = (directory / 'analysis.raw.txt').read_text(encoding='utf-8')
    historical = read_json(directory / 'result.json')
    if historical['processing_state'] == 'CONSOLIDATED':
        assert parse_v3(payload(gid), raw).schema_version == 3
    else:
        with pytest.raises(ValueError): parse_v3(payload(gid), raw)
    with pytest.raises(ValueError): parse_response(payload(gid), raw)


def synthetic_source(texts):
    """Separate source corpus; no synthetic edits touch pilot files."""
    p = deepcopy(payload(GIDS[3])); m = p['members'][0]
    m['original_thread']['messages'] = deepcopy(m['original_thread']['messages'][:len(texts)])
    for message, text in zip(m['original_thread']['messages'], texts):
        message['text'] = text
    m['agent1_record']['input_sha256'] = digest(m['original_thread'])
    return p


def test_multiple_items_diagnostic_and_condition_same_message_with_quoted_question():
    p = synthetic_source(['Please send the job ID. Do not submit until the preview completes.', 'The label reads "Ready?"; this is a quote, not a request.'])
    draft = wiring_draft(p); t = draft['topics'][0]
    t['inventory'] = [
        {'item_id': 'diagnostic', 'evidence_id': 'E001', 'kind': 'DIAGNOSTIC_REQUEST', 'text': 'Please send the job ID.', 'question': None},
        {'item_id': 'condition', 'evidence_id': 'E001', 'kind': 'INSTRUCTION', 'text': 'Do not submit until the preview completes.', 'question': None},
        {'item_id': 'quoted', 'evidence_id': 'E002', 'kind': 'CONTEXT', 'text': 'The label reads "Ready?"; this is a quote, not a request.', 'question': None}]
    out = export_result(p, parse_response(p, json.dumps(draft)), state='CONSOLIDATED')
    topic = out['topics'][0]
    assert len(topic['guidance']) == 2 and not topic['open_questions']
    assert topic['coverage_diagnostics']  # Review only; does not invent a quoted question.
    assert len(topic['source_coverage'][0]['item_ids']) == 2


@pytest.mark.parametrize('reaction,authority', [('eyes', 'SOURCE_REPLY'), ('agree', 'TL_ENDORSED')])
def test_synthetic_actual_tl_reaction_target_is_not_inferred_from_eyes(reaction, authority):
    p = synthetic_source(['Where is the worksheet?', 'It may be in the shared folder; check its date.'])
    reply = p['members'][0]['original_thread']['messages'][1]
    reply['reactions'] = [{'name': reaction, 'users': ['SYNTHETIC_TL'], 'count': 1, 'reactor_roles': {'SYNTHETIC_TL': 'TEAM_LEAD'}}]
    p['members'][0]['agent1_record']['input_sha256'] = digest(p['members'][0]['original_thread'])
    draft = wiring_draft(p); t = draft['topics'][0]
    t['inventory'][0].update(kind='QUESTION', question={'status': 'PARTIAL', 'answer_item_ids': ['E002']})
    t['inventory'][1]['kind'] = 'ANSWER'
    out = export_result(p, parse_response(p, json.dumps(draft)), state='CONSOLIDATED')
    answer = out['topics'][0]['supported_answers'][0]
    assert answer['authority'] == authority
    assert bool(answer['evidence'][0]['tl_endorsements']) == (reaction == 'agree')


def test_synthetic_split_topics_reject_real_but_cross_topic_citation():
    p = deepcopy(payload(GIDS[0])); _, catalog = evidence_catalog(p)
    draft = wiring_draft(p); first = draft['topics'][0]; second = deepcopy(first)
    for t, alias in ((first, 'M01'), (second, 'M02')):
        t['member_ids'] = [alias]
        t['inventory'] = [i for i in t['inventory'] if catalog[i['evidence_id']]['member_id'] == alias]
        eid = t['inventory'][0]['evidence_id']
        t['shared_issue']['evidence_ids'] = [eid]
        t['impact'] = impact(eid)
    draft['topics'].append(second)
    assert len(parse_response(p, json.dumps(draft)).topics) == 2
    first['shared_issue']['evidence_ids'] = [second['inventory'][0]['evidence_id']]
    with pytest.raises(ValueError, match='crosses topic'):
        parse_response(p, json.dumps(draft))


def test_mocked_batch_keeps_flags_and_continues_after_high_and_severity_failure(monkeypatch, tmp_path):
    gids = [GIDS[5], GIDS[3], GIDS[1], GIDS[4]]
    attempts = []
    def send(endpoint, body, key):
        gid = json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id']
        attempts.append(gid)
        from tests.agent2_structured_fixtures import reviewed_draft as current_draft
        draft = current_draft(gid)
        if gid == GIDS[3]: draft['topics'][0]['impact']['criteria'] = []
        return 200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(draft)}}]}).encode(), None
    monkeypatch.setattr(transport, 'send_once', send)
    out = tmp_path / 'mocked'
    manifest = pipeline.execute_batch([payload(g) for g in gids], out, run=True, maximum_requests=4)
    assert attempts == gids and manifest['processing_counts'] == {'CONSOLIDATED': 4}
    assert manifest['factual_validity_counts'] == {'VALID': 4}
    assert manifest['severity_validity_counts'] == {'VALID': 3, 'INVALID': 1}
    assert manifest['inherited_review_obligations'] == 5
    rows = read_json(out / 'consolidations.json')
    assert rows[0]['morning_review_obligations'] and rows[1]['topics'] and rows[2]['review_required']
    assert len(read_json(out / 'effective_output.json')['member_review_queue']) == 5


def test_effective_loader_applies_mandatory_review_without_changing_historical_outcomes():
    before = file_hash(FROZEN / 'consolidations.json')
    view = load_effective_output(FROZEN)
    assert len(view['records']) == len(view['review_queue']) == 6
    assert len(view['member_review_queue']) == 5 and not view['unapplied_findings']
    row = next(r for r in view['records'] if r['candidate_group_id'] == GIDS[2])
    assert row['automated_review_required'] is False and row['effective_review_required'] is True
    assert row['processing_state'] == 'CONSOLIDATED'
    # The historical answer was exported in guidance, not supported_answers.
    assert row['topics'][0]['guidance']
    assert all(g['reliability'] == 'PROVISIONAL' for g in row['topics'][0]['guidance'])
    assert not row['topics'][0]['supported_answers']
    assert file_hash(FROZEN / 'consolidations.json') == before


def test_supplement_demotes_answer_without_rewriting_canonical_or_transferring_to_changed_source(tmp_path):
    gid = GIDS[3]; canonical = result(gid)
    run = tmp_path / 'synthetic-run'; directory = run / 'records' / gid
    pipeline.write_json(directory / 'input.json', payload(gid))
    pipeline.write_json(directory / 'result.json', canonical)
    pipeline.write_json(directory / 'analysis.raw.txt', reviewed_draft(gid))
    pipeline.write_json(run / 'consolidations.json', [canonical])
    binding = {field: file_hash(directory / name) for field, name in (
        ('input_file_sha256', 'input.json'), ('raw_draft_sha256', 'analysis.raw.txt'), ('export_result_sha256', 'result.json'))}
    supplement = tmp_path / 'review.json'
    pipeline.write_json(supplement, {'origin': 'synthetic_test_review', 'run': run.as_posix(), 'entries': [{
        'candidate_group_id': gid, 'binding': binding, 'assisted_content_review_required': True,
        'findings': [{'finding_id': 'synthetic-finding', 'explanation': 'Synthetic downstream flag test.'}]}]})
    view = load_effective_output(run, additional_supplements=[supplement])
    t = view['records'][0]['topics'][0]
    assert t['provisional_answers'] and not t['supported_answers']
    assert t['provisional_answers'][0]['reliability'] == 'PROVISIONAL'
    assert read_json(directory / 'result.json') == canonical
    pipeline.write_json(directory / 'input.json', {'different': 'source'})
    stale = load_effective_output(run, additional_supplements=[supplement])
    assert not stale['applied_content_obligations'] and len(stale['unapplied_findings']) == 1
    assert stale['records'][0]['topics'][0]['supported_answers']


@pytest.mark.parametrize('criterion,basis', [('non_operational', 'NON_OPERATIONAL'),
    ('limited_demonstrated_consequence', 'OBSERVED_OUTCOME')])
def test_low_and_na_do_not_clear_inherited_flags_in_v4(criterion, basis):
    # Synthetic mechanics only: these levels are not judgments of the pilot source.
    draft = reviewed_draft(GIDS[1])
    draft['topics'][0]['impact'] = impact('E001', criterion, basis)
    out = result(GIDS[1], draft)
    assert out['topics'][0]['preliminary_severity']['level'] in {'LOW', 'N/A'}
    assert len(out['inherited_review_obligations']) == 2 and out['review_required']
    assert not out['topics'][0]['supported_answers']


def test_rhetorical_question_cue_does_not_establish_actual_question_or_resolution():
    p = synthetic_source(['What a day! Who would have guessed?', 'Thanks.'])
    draft = wiring_draft(p)
    draft['topics'][0]['inventory'][1]['kind'] = 'CONTEXT'
    out = export_result(p, parse_response(p, json.dumps(draft)), state='CONSOLIDATED')
    assert out['review_required'] and not out['topics'][0]['open_questions']
    assert out['topics'][0]['representative_question'] is None


def test_uncertain_disposition_remains_visible_without_defaulting_missing_messages():
    draft = reviewed_draft(GIDS[0]); t = draft['topics'][0]
    t['inventory'] = [i for i in t['inventory'] if i['evidence_id'] != 'E004']
    t['dispositions'] = [{'evidence_id': 'E004', 'disposition': 'UNCERTAIN', 'reason': 'Synthetic uncertainty, inspect original instruction.'}]
    out = result(GIDS[0], draft)
    assert out['review_required'] and out['topics'][0]['uncertainties']
    assert out['topics'][0]['source_coverage'][-1]['disposition']['disposition'] == 'UNCERTAIN'


def test_supplements_deduplicate_and_stale_candidate_is_exposed_without_application(tmp_path):
    supplement = ROOT / read_json(REGISTRY)['supplements'][0]['path']
    baseline = load_effective_output(FROZEN)
    copy = tmp_path / 'duplicate.json'; pipeline.write_json(copy, read_json(supplement))
    merged = load_effective_output(FROZEN, additional_supplements=[copy])
    assert len(merged['applied_content_obligations']) == len(baseline['applied_content_obligations'])
    assert len(merged['applied_content_obligations'][0]['provenance']) == 2
    bad = read_json(supplement)
    bad['entries'] = [deepcopy(bad['entries'][2])]
    bad['entries'][0]['binding']['raw_draft_sha256'] = 'stale'
    stale = tmp_path / 'stale.json'; pipeline.write_json(stale, bad)
    view = load_effective_output(FROZEN, additional_supplements=[stale])
    assert len(view['applied_content_obligations']) == len(baseline['applied_content_obligations'])
    assert view['unapplied_findings'][0]['applied'] is False
    assert 'raw_draft_sha256_mismatch' in view['unapplied_findings'][0]['reasons']


def test_explicit_contract_upgrade_requires_same_inputs_model_and_bound(tmp_path, monkeypatch):
    prepare = runpy.run_path(str(ROOT / 'scripts/prepare_agent2_pilot.py'))['prepare_pilot']
    from threadsense.topic_inputs import load_candidate_payloads
    monkeypatch.setitem(prepare.__globals__, 'load_candidate_payloads', lambda: load_candidate_payloads(historical=True))
    source = ROOT / 'docs/agent2-revalidation-v3-2.json'
    prepared = ROOT / 'data/processed/agent2_revalidation_v3_2_prepared'
    with pytest.raises(ValueError, match='Non-code configuration'):
        prepare(source, prepared, tmp_path / 'refused.json', tmp_path / 'refused', 'Synthetic review')
    p, m = prepare(source, prepared, tmp_path / 'new.json', tmp_path / 'prepared',
                   'Synthetic reviewed v4 contract migration, no calls.', allow_contract_upgrade=True)
    assert p['response_schema_version'] == 6 and p['cases'] == read_json(source)['cases']
    assert m['selected_groups'] == 6 and m['retained_input_identities'] == 18
    assert m['inherited_review_obligations'] == 5 and m['new_request_attempts'] == 0
    assert p['maximum_request_attempts'] == 6
    assert p['preparation_review']['version_changes']['rubric_version'] == {
        'previous': None, 'current': 'provisional-operational-severity-v2'}
    assert p['preparation_review']['version_changes']['export_adapter_version'] == {
        'previous': None, 'current': 'inventory-to-display-v3'}
