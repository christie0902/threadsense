"""Historical v7 offline contract tests; synthetic assignments are not quality evidence."""
from collections import Counter
from copy import deepcopy
import json
import runpy

import pytest
from pydantic import ValidationError

from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.agents import topic_consolidation as contract, topic_consolidation_v6 as legacy
from threadsense.agents import topic_comparison
from threadsense.legacy import taxonomy_severity_v7 as severity
from tests.legacy_agent2 import bind_v7
from threadsense.agents.topic_contracts import TopicTaxonomy, TopicConsolidation
from threadsense.agents.topic_effective import load_effective_output
from threadsense.agents.topic_diagnostics import ConsolidationValidationError, describe_exception
from threadsense.handoff_inputs import ROOT, IDENTITY, read_json, file_hash, identity, digest
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.terminology import get_terms

MODEL = 'openai/gpt-5.4-2026-03-05'


@pytest.fixture(scope='module')
def payloads():
    return load_candidate_payloads(historical=True)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    bind_v7(monkeypatch)
    monkeypatch.setenv('THREADSENSE_MODEL', MODEL)
    monkeypatch.setenv('THREADSENSE_AGENT2_REASONING_EFFORT', 'low')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-offline-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('No real API call is permitted by these offline tests.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


def draft(p, *, partitions=None, rejected=()):
    """Clearly synthetic grouping only; never auto-label source meaning as correct."""
    if partitions is None:
        partitions = [[m['member_id'] for m in p['members']]]
    return {'topics': [{'topic_name': 'Synthetic grouping',
                        'rationale': 'Synthetic partition for structural testing only.',
                        'member_ids': ids} for ids in partitions],
            'rejected_member_ids': list(rejected)}


def exported(p, d):
    return contract.export_result(p, contract.parse_response(p, json.dumps(d)), state='CONSOLIDATED', export_adapter_version='taxonomy-to-canonical-v1')


def http_response(d):
    return 200, json.dumps({'model': MODEL.split('/')[1], 'choices': [
        {'finish_reason': 'stop', 'message': {'content': json.dumps(d)}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}).encode(), None


@pytest.mark.parametrize('kind', ['coherent', 'split', 'singleton', 'outlier', 'all_rejected', 'social'])
def test_valid_partitions_and_nonoperational_content(payloads, kind):
    p = next(p for p in payloads if len(p['members']) >= 3)
    if kind == 'singleton': p = next(p for p in payloads if len(p['members']) == 1)
    if kind == 'social': p = next(p for p in payloads if p['candidate_group_id'] == 'cluster_be4e3bac742eccb3')
    mids = [m['member_id'] for m in p['members']]
    d = draft(p)
    if kind == 'split': d = draft(p, partitions=[mids[:1], mids[1:]])
    if kind == 'outlier': d = draft(p, partitions=[mids[1:]], rejected=mids[:1])
    if kind == 'all_rejected': d = draft(p, partitions=[], rejected=mids)
    if kind == 'social':
        d['topics'][0].update(topic_name='Team appreciation', rationale='Members share team appreciation.')
    row = exported(p, d)
    assert row['taxonomy_validity'] == 'VALID' and row['processing_state'] == 'CONSOLIDATED'
    assert row['members'] == p['members']
    assert Counter(x['member_id'] for x in row['member_dispositions']) == Counter(mids)
    assert row['rejected_member_ids'] == d['rejected_member_ids']
    assert row['unassigned_member_ids'] == []
    assert all(t['preliminary_severity']['level'] == 'UNKNOWN' for t in row['topics'])
    assert not any(k in row for k in ('research_handoff', 'questions', 'severity_validity', 'factual_validity'))
    assert all(not set(t) & {'inventory','shared_issue','representative_question','supported_answers',
                            'resolution_confidence','uncertainties','impact_proposal'} for t in row['topics'])


@pytest.mark.parametrize('mutation', ['unknown','within','across','overlap','duplicate_rejected','missing',
                                      'empty_topic','blank_name','blank_rationale','empty_partition','whitespace_id','legacy_field'])
def test_invalid_schema_or_partition_is_not_repaired(payloads, mutation):
    p = next(p for p in payloads if len(p['members']) >= 2)
    d = draft(p); mids = d['topics'][0]['member_ids']
    if mutation == 'unknown': mids[0] = 'member_unknown'
    elif mutation == 'within': mids.append(mids[0])
    elif mutation == 'across': d['topics'].append(deepcopy(d['topics'][0]))
    elif mutation == 'overlap': d['rejected_member_ids'] = [mids[0]]
    elif mutation == 'duplicate_rejected': d = draft(p, partitions=[], rejected=mids + mids[:1])
    elif mutation == 'missing': mids.pop()
    elif mutation == 'empty_topic': d['topics'][0]['member_ids'] = []
    elif mutation == 'blank_name': d['topics'][0]['topic_name'] = ' \n '
    elif mutation == 'blank_rationale': d['topics'][0]['rationale'] = ' \t '
    elif mutation == 'empty_partition': d['topics'] = []
    elif mutation == 'whitespace_id': mids[0] += ' '
    else: d['topics'][0]['supported_answers'] = []
    saved = deepcopy(d)
    with pytest.raises((ValidationError, ConsolidationValidationError)) as caught:
        contract.parse_response(p, json.dumps(d))
    details = describe_exception(p, caught.value)
    assert details[0]['category'] in {'schema','membership'}
    assert details[0]['group_member_identities'] == [{k:m[k] for k in IDENTITY} for m in p['members']]
    assert d == saved


@pytest.mark.parametrize('mutation', ['project','batch','candidate_hash','source_hash','identity'])
def test_integrity_boundary_still_enforced(payloads, mutation):
    p = deepcopy(payloads[0]); m = p['members'][0]
    if mutation in {'project','batch'}: p[mutation+'_id'] = 'different'
    elif mutation == 'candidate_hash': m['agent1_record']['candidate_sha256'] = 'different'
    elif mutation == 'source_hash': m['agent1_record']['input_sha256'] = 'different'
    else: m['member_id'] = 'different'
    with pytest.raises(ValueError): contract.build_request(p, get_terms(), MODEL)


def test_all_200_members_49_obligations_survive_assignment_rejection_and_failure(payloads):
    expected = {identity(m):m for p in payloads for m in p['members']}
    assert len(payloads) == 90 and len(expected) == 200
    assert Counter(m['agent1_record']['verification_status'] for m in expected.values()) == {
        'VERIFIED':81, 'CORRECTED':70, 'NEEDS_REVIEW':49}
    flagged_groups = [p['candidate_group_id'] for p in payloads if any(m['agent1_record']['review_required'] for m in p['members'])]
    rows=[]
    for p in payloads:
        gid = p['candidate_group_id']
        if gid == flagged_groups[0]: row = contract.export_result(p, state='FAILED', error='Synthetic failure.', export_adapter_version='taxonomy-to-canonical-v1')
        elif gid == flagged_groups[1]: row = exported(p, draft(p, partitions=[], rejected=[m['member_id'] for m in p['members']]))
        else: row = exported(p, draft(p))
        rows.append(row)
        assert row['members'] == p['members'] and row['review_evidence'] == p['review_evidence']
        assert row['grouping_sha256'] == p['grouping_sha256']
        assert row['members'] is not p['members']
    actual = {identity(m):m for r in rows for m in r['members']}
    assert actual == expected
    obligations = [o for r in rows for o in r['inherited_review_obligations']]
    assert len(obligations) == 49
    assert {identity(o) for o in obligations} == {k for k,m in expected.items() if m['agent1_record']['review_required']}
    for o in obligations:
        m = expected[identity(o)]
        assert o['agent1_record'] == m['agent1_record']
        assert o['candidate_sha256'] == m['agent1_record']['candidate_sha256']
        assert o['source_sha256'] == m['agent1_record']['input_sha256']
        assert all(o[k] == m[k] for k in ('agent1_export_file','agent1_export_sha256','agent1_lineage_base'))
    assert all(r['review_required'] for r in rows if r['inherited_review_obligations'])
    assert any(d['disposition']=='REJECTED' for r in rows for d in r['member_dispositions'])
    assert any(d['disposition']=='UNASSIGNED' for r in rows for d in r['member_dispositions'])


def test_actual_wire_is_minimal_strict_taxonomy_and_no_legacy_semantic_calls(payloads, monkeypatch, tmp_path):
    p = next(p for p in payloads if len(p['members']) > 1); captured=[]
    def forbidden(*args, **kwargs): raise AssertionError('Legacy semantic processing must be inactive.')
    for name in ('parse_response','validate_output','derive_severity','evidence_catalog','tl_endorsements'):
        monkeypatch.setattr(legacy, name, forbidden)
    def send(endpoint, body, key):
        captured.append(json.loads(body))
        return http_response(draft(p))
    monkeypatch.setattr(transport, 'send_once', send)
    manifest = pipeline.execute_batch([p], tmp_path/'run', run=True, maximum_requests=1)
    assert manifest['processing_counts'] == {'CONSOLIDATED':1} and len(captured) == 1
    req = captured[0]
    assert req == read_json(tmp_path/'run/records'/p['candidate_group_id']/'request.json')
    assert req['model'] == MODEL.split('/')[1] and req['reasoning_effort'] == 'low'
    assert req['max_completion_tokens'] == 8192 and not set(req) & {'temperature','top_p','logprobs'}
    assert len(req['messages']) == 2
    data = json.loads(req['messages'][1]['content'])
    assert set(data) == {'schema_version','candidate_group_id','project_id','batch_id','approved_glossary','members'}
    assert data['members'] == [{'member_id':m['member_id'], 'summary':m['agent1_record']['interpretation']['summary'],
                               'central_question':m['agent1_record']['interpretation']['central_question']} for m in p['members']]
    system = req['messages'][0]['content']
    assert 'Do not reinterpret Slack' in system and 'assess severity' in system
    assert 'QUESTION UNCERTAINTY HANDOFF' not in system and 'provisional_operational_severity_rubric' not in data
    schema = req['response_format']['json_schema']
    assert schema['strict'] and schema['name'] == 'threadsense_agent2_taxonomy_v7'
    assert set(schema['schema']['properties']) == {'topics','rejected_member_ids'}
    assert set(schema['schema']['$defs']['TaxonomyTopic']['properties']) == {'topic_name','rationale','member_ids'}
    for node in [schema['schema'], *schema['schema']['$defs'].values()]:
        if node.get('type') == 'object':
            assert node['additionalProperties'] is False
            assert set(node['required']) == set(node['properties'])


@pytest.mark.parametrize('failure', ['membership','refusal','length','unknown'])
def test_one_attempt_and_recoverable_failure_continues_with_passive_handoff(payloads, monkeypatch, tmp_path, failure):
    selected = [p for p in payloads if any(m['agent1_record']['review_required'] for m in p['members'])][:2]
    calls=[]
    def send(endpoint, body, key):
        calls.append(json.loads(body))
        if len(calls) == 2: return http_response(draft(selected[1]))
        if failure == 'membership': return http_response({'topics':[],'rejected_member_ids':[]})
        if failure == 'unknown': raise TimeoutError('Synthetic unknown provider completion.')
        return 200, json.dumps({'choices':[{'finish_reason':'length' if failure == 'length' else 'stop',
            'message':{'content':None,'refusal':'Synthetic refusal' if failure == 'refusal' else None}}]}).encode(), None
    monkeypatch.setattr(transport, 'send_once', send)
    out = tmp_path/'run'
    manifest = pipeline.execute_batch(selected, out, run=True, maximum_requests=2)
    assert len(calls) == manifest['new_request_attempts'] == 2
    assert manifest['processing_counts'] == {'FAILED':1,'CONSOLIDATED':1}
    assert manifest['unprocessed_groups'] == 0
    assert len(manifest['unknown_completion_requests']) == (1 if failure == 'unknown' else 0)
    view = load_effective_output(out)
    assert view['records'][0]['unassigned_member_ids'] == [m['member_id'] for m in selected[0]['members']]
    for p,row in zip(selected, view['records']):
        assert row['members'] == p['members'] and row['taxonomy_handoff']['members'] == p['members']
        assert row['effective_review_required'] and row['taxonomy_handoff']['nonblocking']
        assert 'research_handoff' not in row and 'questions' not in row['taxonomy_handoff']
    assert len(view['member_review_queue']) == sum(m['agent1_record']['review_required'] for p in selected for m in p['members'])
    with pytest.raises(FileExistsError): pipeline.execute_batch(selected, out, run=True, maximum_requests=2)
    assert len(calls) == 2


def test_severity_does_not_infer_impact_from_names_or_flags(payloads):
    p = next(p for p in payloads if any(m['agent1_record']['review_required'] for m in p['members']))
    for name in ('Label Tool bugs', 'Catastrophic system outage', 'Social appreciation'):
        d = draft(p); d['topics'][0]['topic_name'] = name
        r = exported(p, d); s = r['topics'][0]['preliminary_severity']
        assert s['level'] == 'UNKNOWN' and s['assessment_status'] == 'UNASSESSED'
        assert s['basis'] == 'INSUFFICIENT_EVIDENCE' and s['rubric_version'] == 'provisional-operational-severity-v2'
        assert s['rule_version'] == severity.DETERMINISTIC_RULE_VERSION
        assert r['taxonomy_validity'] == 'VALID' and r['review_required']
        assert {v['member_id'] for v in s['input_provenance']} == {m['member_id'] for m in p['members']}


@pytest.mark.parametrize('level', ['HIGH','LOW','UNKNOWN','N/A'])
def test_post_export_routing_does_not_gate_taxonomy_or_clear_flags(payloads, monkeypatch, level):
    p = next(p for p in payloads if any(m['agent1_record']['review_required'] for m in p['members']))
    # Synthetic already-assessed signal tests routing only. No invented Agent 1 impact field.
    monkeypatch.setattr(severity, 'assess_canonical_impact', lambda members: {
        'level':level, 'origin':'SYNTHETIC_OFFLINE_ROUTING_TEST_NOT_REAL_IMPACT', 'severity_is_provisional':True})
    r = exported(p, draft(p))
    assert r['taxonomy_validity'] == 'VALID' and r['processing_state'] == 'CONSOLIDATED'
    assert r['review_required'] and r['inherited_review_obligations']
    assert bool(r['morning_review_obligations']) == (level == 'HIGH')
    assert r['topics'][0]['morning_review_required'] == (level == 'HIGH')


def test_historical_reviews_cannot_transfer_to_new_taxonomy_output(payloads, tmp_path):
    old = ROOT/'data/processed/agent2_final_v6'
    supplement = old/'combined_review_supplement.json'
    gid = read_json(supplement)['entries'][0]['candidate_group_id']
    p = next(p for p in payloads if p['candidate_group_id'] == gid)
    out = tmp_path/'taxonomy'; directory=out/'records'/gid
    d=draft(p); r=exported(p,d)
    pipeline.write_json(directory/'input.json',p)
    pipeline.write_json(directory/'analysis.raw.txt',d)
    pipeline.write_json(directory/'result.json',r)
    pipeline.write_json(out/'consolidations.json',[r])
    before = file_hash(directory/'result.json')
    view = load_effective_output(out, additional_supplements=(supplement,))
    assert view['unapplied_findings'] and not view['applied_content_obligations']
    assert all('run_mismatch' in f['reasons'] for f in view['unapplied_findings'])
    assert file_hash(directory/'result.json') == before
    assert view['records'][0]['inherited_review_obligations'] == r['inherited_review_obligations']
    # A separately bound taxonomy finding routes review without touching canonical records.
    fresh = tmp_path/'review.json'
    binding = {k:file_hash(directory/name) for k,name in [('input_file_sha256','input.json'),
        ('raw_draft_sha256','analysis.raw.txt'),('export_result_sha256','result.json')]}
    pipeline.write_json(fresh, {'run':out.as_posix(),'origin':'synthetic taxonomy test review','entries':[
        {'candidate_group_id':gid,'binding':binding,'assisted_content_review_required':True,
         'findings':[{'summary':'Synthetic membership concern.'}]}]})
    new=load_effective_output(out, additional_supplements=(fresh,))
    assert len(new['applied_content_obligations']) == 1 and new['records'][0]['review_required']
    assert new['records'][0]['topics'][0]['assignment_reliability'] == 'PROVISIONAL'
    assert new['records'][0]['members'] == p['members']
    assert not {'supported_answers','provisional_answers','inventory'} & set(new['records'][0]['topics'][0])


def test_legacy_contract_imports_and_all_accepted_v6_replay_unchanged():
    assert TopicConsolidation is not TopicTaxonomy
    old = ROOT/'data/processed/agent2_final_v6'
    rows=read_json(old/'consolidations.json'); count=0
    for row in rows:
        if row['processing_state'] != 'CONSOLIDATED': continue
        directory=old/'records'/row['candidate_group_id']
        p=read_json(directory/'input.json'); raw=(directory/'analysis.raw.txt').read_text(encoding='utf-8')
        parsed=contract.parse_response(p,raw,response_schema_version=6)
        assert contract.export_result(p,parsed,state='CONSOLIDATED',response_schema_version=6) == row
        with pytest.raises(ValidationError): contract.parse_response(p,raw)
        count+=1
    assert count == 88
    view=load_effective_output(old)
    assert len(view['applied_content_obligations']) == 10 and not view['unapplied_findings']
    assert all('research_handoff' in row and 'taxonomy_handoff' not in row for row in view['records'])


def test_historical_comparison_cannot_launch_taxonomy_experiment(tmp_path):
    with pytest.raises(ValueError, match='inactive under taxonomy v7'):
        topic_comparison.prepare_comparison(tmp_path/'experiment')
    assert not (tmp_path/'experiment').exists()


def test_compatibility_task_requires_and_minimizes_canonical_payload(payloads, monkeypatch):
    from threadsense.agents import topic_analyst
    monkeypatch.setattr(topic_analyst, 'Task', lambda **kwargs: kwargs)
    p=next(p for p in payloads if all(m['original_thread']['channel_type']=='GENERAL' for m in p['members']))
    with pytest.raises(TypeError): topic_analyst.create_topic_task(object())
    task=topic_analyst.create_topic_task(object(),payload=p)
    data=json.loads(task['description'].split('\nCandidate:\n')[1].replace('{{','{').replace('}}','}'))
    assert task['output_pydantic'] is TopicTaxonomy
    assert all(set(m)=={'member_id','summary','central_question'} for m in data['members'])
    assert 'original_thread' not in data and 'evidence_catalog' not in data


def test_explicit_v6_to_v7_pilot_refresh_preserves_selection_and_originals(payloads, tmp_path, monkeypatch):
    from tests.legacy_agent2 import bind_v6
    from threadsense.handoff_inputs import CANONICAL, GROUPING
    p=payloads[0]; source=tmp_path/'source.json'; old_dir=tmp_path/'old'
    with pytest.MonkeyPatch.context() as patch:
        bind_v6(patch)
        old=pipeline.execute_batch([p],old_dir,run=False,maximum_requests=1)
    pipeline.write_json(source,{'schema_version':2,'response_schema_version':6,'model':MODEL,
        'canonical_sha256':file_hash(CANONICAL),'grouping_sha256':file_hash(GROUPING),
        'configuration_sha256':old['config_sha256'],'maximum_request_attempts':1,
        'requests_per_group':1,'automatic_retries':0,'repairs':0,'additional_verifier_calls':0,
        'cases':[{'candidate_group_id':p['candidate_group_id'],'anchor_thread_id':p['members'][0]['thread_id'],
            'member_identities':[{k:m[k] for k in IDENTITY} for m in p['members']],
            'inherited_review_count':sum(m['agent1_record']['review_required'] for m in p['members'])}]})
    before={path:file_hash(path) for path in old_dir.rglob('*') if path.is_file()}
    prepare=runpy.run_path(str(ROOT/'scripts/prepare_agent2_pilot.py'))['prepare_pilot']
    monkeypatch.setitem(prepare.__globals__, 'load_candidate_payloads', lambda: payloads)
    args=(source,old_dir,tmp_path/'new.json',tmp_path/'new','Synthetic explicit scope review.')
    with pytest.raises(ValueError,match='Non-code configuration changed'): prepare(*args)
    pilot,manifest=prepare(*args,allow_contract_upgrade=True)
    assert pilot['response_schema_version']==7 and pilot['cases']==read_json(source)['cases']
    assert manifest['new_request_attempts']==0 and manifest['processing_counts']=={'NOT_RUN':1}
    assert pilot['preparation_review']['model_requests_changed']==[p['candidate_group_id']]
    assert all(file_hash(path)==h for path,h in before.items())
    assert not list((tmp_path/'new').rglob('call.json'))


def test_all_group_dry_run_builds_requests_without_keys_calls_or_evaluation_data(payloads, monkeypatch, capsys):
    from pathlib import Path
    original=Path.open
    def checked(path, *args, **kwargs):
        assert '/data/evaluation/' not in path.as_posix()
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',checked)
    def forbidden(*args,**kwargs): raise AssertionError('Dry run cannot access credentials.')
    monkeypatch.setattr(pipeline.config,'get_api_key',forbidden)
    cli=runpy.run_path(str(ROOT/'scripts/run_agent2_batch.py'))['main']
    monkeypatch.setitem(cli.__globals__, 'load_candidate_payloads', lambda: payloads)
    monkeypatch.setitem(cli.__globals__, 'build_request', pipeline.build_request)
    assert cli(['--dry-run','--limit','0']) == 0
    output=capsys.readouterr().out
    assert '200 inputs in 90 groups' in output and '49 inherited review obligations' in output
