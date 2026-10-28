"""Offline contract tests; mocked prose is never evidence of live semantic accuracy."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")
from pydantic import ValidationError

from threadsense import handoff_inputs as inputs
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.topic_grouping import approved_grouping, group_members
from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_consolidation_v3 import build_request, parse_response, export_result
from threadsense.agents.topic_contracts_v3 import TopicConsolidation
from threadsense.terminology import get_terms
from threadsense.agents.topic_evidence import evidence_catalog
from tests.agent2_fixtures import membership_only_draft, guidance

@pytest.fixture(scope='module')
def payloads():
    return load_candidate_payloads(historical=True)

def _find(payloads, thread_id):
    return deepcopy(next(p for p in payloads if any(m['thread_id']==thread_id for m in p['members'])))

def _membership_only_draft(payload):
    """Synthetic stub for wiring tests, explicitly not a reviewed factual summary."""
    return membership_only_draft(payload)

def _http(draft):
    return 200, json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(draft)}}]}).encode(), None

def _copy_handoff(tmp_path):
    """Small portable copy; exact source/result bytes remain intact."""
    import shutil
    target = tmp_path/'handoff'
    target.mkdir()
    original = inputs.CANONICAL.parent
    for name in ('interpretations.json','manifest.json','review_queue.json'):
        shutil.copyfile(original/name, target/name)
    # The source/result directory copies support corruption tests without touching originals.
    rows = inputs.read_json(inputs.CANONICAL)
    for row in rows:
        for field in ('source_file','verification_file'):
            relative = row['lineage'][field]
            (target/relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original/relative, target/relative)
    return target/'interpretations.json'

def test_all_200_canonical_members_and_49_flags_survive_grouping(payloads):
    canonical = {inputs.identity(r):r for r in inputs.read_json(inputs.CANONICAL)}
    members = [m for p in payloads for m in p['members']]
    assert len(members) == len({inputs.identity(m) for m in members}) == 200
    assert {inputs.identity(m) for m in members} == set(canonical)
    assert Counter(m['agent1_record']['verification_status'] for m in members) == {'VERIFIED':81,'CORRECTED':70,'NEEDS_REVIEW':49}
    for m in members:
        assert m['agent1_record'] == canonical[inputs.identity(m)]
        assert inputs.digest(m['original_thread']) == m['agent1_record']['input_sha256']
        assert inputs.identity(m['original_thread']) == inputs.identity(m)
    assert len(payloads) == 90  # Actual refreshed result, not the obsolete 91-group assumption.

@pytest.mark.parametrize('mutation', ['duplicate','missing_flag','candidate','source','lineage'])
def test_canonical_loader_rejects_corruption(tmp_path, mutation):
    path = _copy_handoff(tmp_path)
    rows = inputs.read_json(path)
    if mutation == 'duplicate': rows[-1] = deepcopy(rows[0])
    elif mutation == 'missing_flag': next(r for r in rows if r['review_required'])['review_required'] = False
    elif mutation == 'candidate': rows[0]['interpretation']['summary'] = 'Changed candidate'
    elif mutation == 'source':
        source_path = path.parent/rows[0]['lineage']['source_file']
        source = inputs.read_json(source_path)
        source['messages'][0]['text'] = 'Invented source'
        source_path.write_text(json.dumps(source),encoding='utf-8')
    else: rows[0]['lineage']['verification_file'] = '../../elsewhere.json'
    path.write_text(json.dumps(rows),encoding='utf-8')
    with pytest.raises(ValueError): inputs.load_handoff(path)

@pytest.mark.parametrize('mutation', ['missing','duplicate','metadata','old_input'])
def test_candidate_loader_rejects_missing_duplicate_stale_members(tmp_path, mutation):
    grouping = inputs.read_json(inputs.GROUPING)
    if mutation=='missing': grouping['clusters'][0]['threads'].pop()
    elif mutation=='duplicate': grouping['clusters'][0]['threads'].append(deepcopy(grouping['clusters'][0]['threads'][0]))
    elif mutation=='metadata': grouping['clusters'][0]['threads'][0]['automated_verification_status'] = 'INVALID'
    else: grouping['input_sha256'] = 'old baseline'
    path=tmp_path/'clusters.json'; path.write_text(json.dumps(grouping),encoding='utf-8')
    with pytest.raises(ValueError): load_candidate_payloads(path)

def test_grouping_keeps_approved_parameters_and_full_scope_identity(payloads):
    implementation, baseline = approved_grouping()
    current = inputs.read_json(inputs.GROUPING)
    assert current['config'] == baseline['config']
    assert current['config']['distance_threshold'] == .50
    assert current['config']['embedding']['device'] == 'cpu'
    # Same channel/thread IDs in different projects must not collide.
    member = deepcopy(payloads[0]['members'][0])
    other = deepcopy(member)
    other['project_id'] = other['agent1_record']['project_id'] = 'other_project'
    groups = group_members([member,other],np.asarray([[1,0],[1,0]],dtype=np.float32),implementation,.50,historical=True)
    assert len(groups)==2
    assert len({inputs.identity(r) for g in groups for r in g['threads']})==2

def test_request_is_factual_has_flags_and_no_review_labels_or_agent3_fields(payloads):
    payload = _find(payloads,'1790882197.000111')
    request = build_request(payload,get_terms(),'openai/gpt-4o-mini')
    assert len(request['messages'])==2
    data=json.loads(request['messages'][1]['content'])
    flagged=next(m for m in data['members'] if m['thread_id']=='1790882197.000111')
    assert flagged['review_required'] and 'summary' in flagged['disputed_fields']
    assert any(e['member_id']==flagged['member_id'] and e['quote'] for e in data['evidence_catalog'])
    assert data['approved_glossary']['QN']=='Quarantine'
    assert not any(word in request['messages'][1]['content'] for word in ('source_review_outcome','human_approval','expected_verdict','ground_truth'))
    schema=TopicConsolidation.model_json_schema()
    assert 'preliminary_severity' in json.dumps(schema)
    for forbidden in ('actionable','research_needs','recommendations','actionability_rationale'):
        assert forbidden not in json.dumps(schema)

@pytest.mark.parametrize('mutation', ['missing','duplicate','unknown','quote','message','candidate','member_evidence','legacy_field'])
def test_real_parser_rejects_bad_assignments_evidence_and_legacy_schema(payloads,mutation):
    payload=_find(payloads,'1790882197.000111'); draft=_membership_only_draft(payload)
    topic=draft['topics'][0]
    if mutation=='missing': topic['member_ids'].pop()
    elif mutation=='duplicate': topic['member_ids'].append(topic['member_ids'][0])
    elif mutation=='unknown': topic['member_ids'][0]='invented'
    elif mutation=='quote': topic['shared_issue']['quote']='Fabricated quote.'
    elif mutation=='message': topic['shared_issue']['evidence_ids'][0]='invented'
    elif mutation=='candidate': draft['candidate_group_id']='wrong'
    elif mutation=='member_evidence': topic['shared_issue']['evidence_ids'].pop()
    else: topic['severity']='HIGH'
    with pytest.raises(ValueError): parse_response(payload,json.dumps(draft))

def test_citations_cannot_cross_topic_boundaries(payloads):
    payload=_find(payloads,'1790882197.000111'); draft=_membership_only_draft(payload)
    first=draft['topics'][0]; second=deepcopy(first)
    second['member_ids']=[first['member_ids'].pop()]
    # Leave the removed member's citation in topic one: source quote is real but misplaced.
    second['shared_issue']['evidence_ids']=[first['shared_issue']['evidence_ids'][-1]]
    draft['topics'].append(second); draft['is_coherent']=False
    with pytest.raises(ValueError,match='crosses topic'): parse_response(payload,json.dumps(draft))

def test_full_identity_not_thread_id_is_assignment_key(payloads):
    payload=deepcopy(payloads[0]); m=deepcopy(payload['members'][0])
    payload['members']=[m]
    other=deepcopy(m)
    for holder in (other,other['agent1_record'],other['original_thread']): holder['channel_id']='ANOTHER_CHANNEL'
    other['member_id']=inputs.member_id(other)
    other['agent1_record']['input_sha256']=inputs.digest(other['original_thread'])
    payload['members'].append(other)
    result=parse_response(payload,json.dumps(_membership_only_draft(payload)))
    assert len(result.topics[0].member_ids)==2

def test_announcements_keep_null_question_and_no_invented_answer(payloads):
    payload=_find(payloads,'1790857839.000141'); draft=_membership_only_draft(payload)
    topic=draft['topics'][0]; topic['conversation_kind']='ANNOUNCEMENT'
    topic['shared_issue']['text']='Calibration scheduling announcements and acknowledgments.'
    result=parse_response(payload,json.dumps(draft))
    exported=export_result(payload,result,state='CONSOLIDATED')
    assert exported['topics'][0]['representative_question'] is None
    assert not exported['topics'][0]['supported_answers']
    assert exported['review_required']  # The inherited announcement dispute is not cleared.
    topic['representative_question']=deepcopy(topic['shared_issue'])
    topic['representative_question']['text']='When will calibration be scheduled?'
    with pytest.raises(ValueError,match='announcements'): parse_response(payload,json.dumps(draft))

def test_reviewed_synthetic_example_preserves_flags_and_qualified_answers(payloads):
    fixture=inputs.read_json(Path(__file__).parent/'fixtures/agent2_hardening_v3.json')
    assert fixture['origin']=='synthetic_offline_regressions'
    payload=_find(payloads,'1790882197.000111')
    draft=next(c['draft'] for c in fixture['cases'] if c['candidate_group_id']==payload['candidate_group_id'])
    analysis=parse_response(payload,json.dumps(draft))
    result=export_result(payload,analysis,state='CONSOLIDATED')
    assert len(result['members'])==6 and len(result['topics'])==2
    assert {o['thread_id'] for o in result['inherited_review_obligations']}=={'1790882197.000111','1790920171.000109'}
    topic=result['topics'][0]
    assert topic['shared_issue']['reliability']=='PROVISIONAL'
    assert topic['supported_answers']==[] and len(topic['provisional_answers'])==2
    assert {a['evidence'][0]['message_id'] for a in topic['provisional_answers']}=={'1790920220.000113','1790934431.000339'}
    assert topic['provisional_answers'][0]['evidence']
    for member in result['members']:
        original=next(m for m in payload['members'] if m['member_id']==member['member_id'])
        assert member==original  # All statuses/reasons/evidence/hashes/lineage preserved verbatim.
    assert 'severity' not in topic and 'actionable' not in topic

def test_model_cannot_clear_flags_by_merging_or_claiming_supported_answer(payloads):
    payload=_find(payloads,'1790882197.000111'); draft=_membership_only_draft(payload)
    member=next(m for m in payload['members'] if m['thread_id']=='1790882197.000111')
    reply=member['original_thread']['messages'][-1]
    # Intentionally incorrect model prose with real quotes must never enter an accepted-answer slot.
    _, catalog=evidence_catalog(payload)
    eid=next(k for k,e in catalog.items() if e['message_id']==reply['message_id'] and e['canonical_member_id']==member['member_id'])
    draft['topics'][0]['supported_answers']=[guidance('The old workaround was attempted and failed.', [eid],
        scope='Deliberately incorrect model prose for a flag-preservation test.')]
    result=export_result(payload,parse_response(payload,json.dumps(draft)),state='CONSOLIDATED')
    assert result['review_required'] and len(result['inherited_review_obligations'])==2
    assert result['topics'][0]['supported_answers']==[]
    assert result['topics'][0]['provisional_answers'][0]['reliability']=='PROVISIONAL'

def test_all_200_continue_after_timeout_and_invalid_response(monkeypatch,tmp_path,payloads):
    monkeypatch.setenv('OPENAI_API_KEY','mock-test-key')
    attempts=[]; by_group={p['candidate_group_id']:p for p in payloads}
    def send(endpoint,body,key):
        request=json.loads(body); data=json.loads(request['messages'][1]['content'])
        attempts.append(data['candidate_group_id'])
        if len(attempts)==2: raise TimeoutError('synthetic timeout')
        if len(attempts)==3: return _http({'bad':'schema'})
        from tests.agent2_structured_fixtures import wiring_draft
        return _http(wiring_draft(by_group[data['candidate_group_id']]))
    monkeypatch.setattr(transport,'send_once',send)
    out=tmp_path/'mock_full'
    manifest=pipeline.execute_batch(payloads,out,run=True,maximum_requests=90)
    assert len(attempts)==len(set(attempts))==90
    assert manifest['retained_input_identities']==200 and manifest['inherited_review_obligations']==49
    assert manifest['processing_counts']=={'CONSOLIDATED':88,'FAILED':2}
    assert manifest['state']=='complete_with_review' and manifest['unprocessed_groups']==0
    assert manifest['new_request_attempts']==90 and manifest['available_response_records']==89
    assert manifest['unknown_completion_requests']==[attempts[1]]
    records=inputs.read_json(out/'consolidations.json')
    assert records[-1]['processing_state']=='CONSOLIDATED'
    queue=inputs.read_json(out/'member_review_queue.json')
    assert {inputs.identity(o) for o in queue}=={inputs.identity(m) for p in payloads for m in p['members'] if m['agent1_record']['review_required']}
    assert inputs.read_json(out/'review_queue.json')==[r for r in records if r['review_required']]
    assert (out/'records'/attempts[1]/'call.json').exists()
    assert not (out/'records'/attempts[1]/'response.raw.bin').exists()
    assert (out/'records'/attempts[2]/'analysis.raw.txt').read_text()=='{"bad": "schema"}'
    with pytest.raises(FileExistsError): pipeline.execute_batch(payloads,out,run=True,maximum_requests=90)
    assert len(attempts)==90

@pytest.mark.parametrize('kind',['configuration','persistence','interruption'])
def test_fatal_and_interrupted_runs_keep_unprocessed_visible(monkeypatch,tmp_path,payloads,kind):
    monkeypatch.setenv('OPENAI_API_KEY','mock-test-key')
    calls=[]
    def send(endpoint,body,key):
        calls.append(1)
        if kind=='configuration': return 401,b'{}',None
        if kind=='interruption': raise KeyboardInterrupt()
        from tests.agent2_structured_fixtures import wiring_draft
        return _http(wiring_draft(payloads[0]))
    monkeypatch.setattr(transport,'send_once',send)
    if kind=='persistence':
        original=pipeline.write_bytes
        def fail(path,body,**kwargs):
            if Path(path).name=='response.raw.bin': raise OSError('synthetic disk failure')
            return original(path,body,**kwargs)
        monkeypatch.setattr(pipeline,'write_bytes',fail)
    out=tmp_path/kind
    if kind=='interruption':
        result=pipeline.execute_batch(payloads[:3],out,run=True,maximum_requests=3)
        assert result['state']=='interrupted'
    else:
        with pytest.raises((transport.EvidencePersistenceError,transport.VerificationConfigurationError)):
            pipeline.execute_batch(payloads[:3],out,run=True,maximum_requests=3)
    assert len(calls)==1
    manifest=inputs.read_json(out/'manifest.json')
    assert manifest['unprocessed_groups']==2
    assert len(inputs.read_json(out/'consolidations.json'))==3

def test_prepare_never_reads_credentials_or_calls_model(monkeypatch,tmp_path,payloads):
    def forbidden(*args,**kwargs): raise AssertionError('Offline preparation cannot call a model or read credentials')
    monkeypatch.setattr(pipeline.config,'get_api_key',forbidden)
    monkeypatch.setattr(transport,'send_once',forbidden)
    result=pipeline.execute_batch(payloads[:2],tmp_path/'prepared')
    assert result['new_request_attempts']==0 and result['state']=='prepared_no_calls'
    assert result['unprocessed_groups']==2
    assert not list((tmp_path/'prepared').rglob('call.json'))

def test_requested_budget_is_checked_before_output(monkeypatch,tmp_path,payloads):
    monkeypatch.setenv('OPENAI_API_KEY','mock-test-key')
    out=tmp_path/'overbudget'
    with pytest.raises(ValueError,match='bound'): pipeline.execute_batch(payloads[:2],out,run=True,maximum_requests=1)
    assert not out.exists()
