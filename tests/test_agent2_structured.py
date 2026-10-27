"""Strict wire requests and v5 behavior; synthetic examples are not model-accuracy evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline, topic_requests as requests, verification_requests as transport
from threadsense.agents.topic_consolidation_v6 import build_request, parse_response, export_result
from threadsense.agents.topic_consolidation_v4 import parse_response as parse_v4
from threadsense.agents.topic_diagnostics import describe_exception
from threadsense.agents.topic_effective import load_effective_output
from threadsense.agents.topic_evidence import evidence_catalog
from threadsense.agents.topic_comparison import prepare_comparison, preflight_comparison, run_arm
from threadsense.handoff_inputs import ROOT, read_json, file_hash, digest
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, payload, impact
from tests.agent2_structured_fixtures import reviewed_draft, wiring_draft

V4 = ROOT/'data/processed/agent2_inventory_pilot_v4'


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-4o-mini')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-offline-key')
    def forbidden(*args,**kwargs):
        raise AssertionError('No paid API calls authorized.')
    monkeypatch.setattr(transport,'send_once',forbidden)


def response(draft):
    return 200,json.dumps({'model':'synthetic-test-model','choices':[{'finish_reason':'stop',
        'message':{'content':json.dumps(draft)}}],'usage':{'prompt_tokens':100,'completion_tokens':200}}).encode(),None


def exported(p,draft):
    return export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')


@pytest.mark.parametrize('model',[requests.BASELINE_MODEL,requests.COMPARISON_MODEL])
def test_actual_http_body_has_strict_provider_schema_and_supported_parameters(monkeypatch,tmp_path,model):
    p=payload(GIDS[0]); captured=[]
    def send(endpoint,body,key):
        captured.append(json.loads(body))
        return response(reviewed_draft(GIDS[0]))
    monkeypatch.setattr(transport,'send_once',send)
    pipeline.execute_batch([p],tmp_path/'run',run=True,maximum_requests=1,model_override=model)
    assert len(captured)==1
    req=captured[0]
    assert req==read_json(tmp_path/'run/records'/GIDS[0]/'request.json')
    assert req['response_format']['type']=='json_schema'
    structured=req['response_format']['json_schema']
    assert structured['strict'] is True and structured['name']=='threadsense_agent2_inventory_v6'
    schema=structured['schema']
    assert schema['type']=='object' and 'anyOf' not in schema
    assert schema['required']==['topics'] and 'schema_version' not in schema['properties']
    for node in [schema,*schema['$defs'].values()]:
        if node.get('type')=='object':
            assert node['additionalProperties'] is False
            assert set(node['properties'])==set(node['required'])
    assert 'text' not in schema['$defs']['SourceItem']['properties']
    assert 'minLength' not in json.dumps(schema)
    assert req['temperature']==0 and req['max_completion_tokens']==8192 and 'max_tokens' not in req
    assert req.get('reasoning_effort')==('none' if model==requests.COMPARISON_MODEL else None)
    status=read_json(tmp_path/'run/records'/GIDS[0]/'completion_status.json')
    assert status['status']=='COMPLETED' and status['usage']['completion_tokens']==200 and status['latency_seconds']>=0


@pytest.mark.parametrize('case,category,status',[
    ('refusal','refusal','REFUSED'),('length','incomplete_output','INCOMPLETE_OUTPUT'),
    ('filter','incomplete_output','INCOMPLETE_OUTPUT'),('partial_http','incomplete_response','INCOMPLETE_HTTP')])
def test_refusal_and_incompletion_are_preserved_and_later_group_continues(monkeypatch,tmp_path,case,category,status):
    selected=[payload(GIDS[0]),payload(GIDS[3])]; calls=[]
    def send(endpoint,body,key):
        calls.append(json.loads(body))
        if len(calls)==2: return response(reviewed_draft(GIDS[3]))
        message={'content':'{"topics":'}
        if case=='refusal': message={'content':None,'refusal':'Synthetic refusal.'}
        reason={'length':'length','filter':'content_filter'}.get(case,'stop')
        body=json.dumps({'choices':[{'finish_reason':reason,'message':message}]}).encode()
        return 200,body,'Incomplete HTTP response; no retry.' if case=='partial_http' else None
    monkeypatch.setattr(transport,'send_once',send)
    manifest=pipeline.execute_batch(selected,tmp_path/'run',run=True,maximum_requests=2)
    rows=read_json(tmp_path/'run/consolidations.json')
    assert len(calls)==2 and manifest['processing_counts']=={'FAILED':1,'CONSOLIDATED':1}
    assert rows[0]['validation_diagnostics'][0]['category']==category
    assert rows[0]['factual_validity']=='UNASSESSED' and rows[0]['severity_validity']=='UNASSESSED'
    d=tmp_path/'run/records'/GIDS[0]
    assert (d/'response.raw.bin').exists() and read_json(d/'completion_status.json')['status']==status
    assert manifest['unknown_completion_requests']==([GIDS[0]] if case=='partial_http' else [])


def test_unsupported_schema_is_fatal_without_fallback_or_later_requests(monkeypatch,tmp_path):
    calls=[]
    def send(*args):
        calls.append(1)
        return 400,b'{"error":{"code":"invalid_json_schema","param":"response_format","message":"Synthetic unsupported schema"}}',None
    monkeypatch.setattr(transport,'send_once',send)
    with pytest.raises(requests.UnsupportedStructuredSchema):
        pipeline.execute_batch([payload(GIDS[0]),payload(GIDS[1])],tmp_path/'run',run=True,maximum_requests=2)
    manifest=read_json(tmp_path/'run/manifest.json')
    assert calls==[1] and manifest['state']=='failed' and manifest['unprocessed_groups']==1
    d=tmp_path/'run/records'/GIDS[0]
    assert read_json(d/'completion_status.json')['status']=='UNSUPPORTED_SCHEMA'
    assert read_json(d/'diagnostics.json')[0]['category']=='unsupported_schema'
    assert read_json(d/'result.json')['factual_validity']=='UNASSESSED'


@pytest.mark.parametrize('body,failure,expected,unknown',[
    ({'choices':None},None,'FAILED',False),
    ({'choices':[{'finish_reason':'stop','message':{'content':None,'refusal':'Partial refusal'}}]},
     'Incomplete HTTP response; no retry.','INCOMPLETE_HTTP',True),
])
def test_malformed_envelope_retains_telemetry_and_partial_refusal_stays_unknown(monkeypatch,tmp_path,body,failure,expected,unknown):
    raw=json.dumps(body).encode()
    monkeypatch.setattr(transport,'send_once',lambda *args:(200,raw,failure))
    manifest=pipeline.execute_batch([payload(GIDS[0])],tmp_path/'run',run=True,maximum_requests=1)
    d=tmp_path/'run/records'/GIDS[0]
    status=read_json(d/'completion_status.json')
    assert status['status']==expected and status['provider_completion_unknown'] is unknown
    assert manifest['new_request_attempts']==1 and (d/'response.raw.bin').read_bytes()==raw
    assert manifest['unknown_completion_requests']==([GIDS[0]] if unknown else [])


@pytest.mark.parametrize('gid',GIDS)
def test_observed_v4_responses_are_replayed_only_under_v4(gid):
    d=V4/'records'/gid; raw=(d/'analysis.raw.txt').read_text(encoding='utf-8'); p=read_json(d/'input.json')
    if read_json(d/'result.json')['processing_state']=='CONSOLIDATED':
        assert parse_v4(p,raw).topics
    else:
        with pytest.raises(ValueError): parse_v4(p,raw)
    with pytest.raises(ValueError): parse_response(p,raw)


@pytest.mark.parametrize('gid,count,missing_members',[(GIDS[1],15,{'M04','M05'}),(GIDS[4],13,{'M03','M04'})])
def test_observed_missing_source_patterns_report_exact_ids_without_inventing_dispositions(gid,count,missing_members):
    # Reproduce only the observed omission pattern on a synthetic v5 example;
    # do not upgrade or repair the historical response.
    p=payload(gid); d=read_json(V4/'records'/gid/'analysis.raw.txt')
    ids={i['evidence_id'] for i in d['topics'][0]['inventory']}
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[i for i in draft['topics'][0]['inventory'] if i['evidence_id'] in ids]
    with pytest.raises(ValueError) as caught: parse_response(p,json.dumps(draft))
    details=describe_exception(p,caught.value)[0]['offending_evidence_reference']
    assert len(details['missing_evidence_ids'])==count
    assert set(details['missing_member_aliases'])==missing_members
    assert len(details['missing_member_ids'])==2
    assert all(e['quote'] and e['thread_id'] and e['message_id'] for e in details['missing_sources'])
    assert draft['topics'][0]['dispositions']==[]


@pytest.mark.parametrize('gid',GIDS)
def test_python_restores_full_exact_sources_and_lineage_for_new_v5_outputs(gid):
    p=payload(gid); draft=reviewed_draft(gid); out=exported(p,draft)
    assert out['schema_version']==6 and out['members']==p['members']
    assert out['factual_validity']==out['severity_validity']=='VALID'
    assert out['inherited_review_obligations']==read_json(V4/'records'/gid/'result.json')['inherited_review_obligations']
    _,catalog=evidence_catalog(p)
    for t in out['topics']:
        for item in t['inventory']:
            assert item['text']==catalog[item['evidence_id']]['quote']
            assert item['text_origin']=='python_original_message'
            assert item['evidence'][0]['quote']==item['text']
    # Historical bad quotes cannot be accepted as new responses and silently normalized.
    draft['topics'][0]['inventory'][0]['text']='Incorrect historical quote.'
    with pytest.raises(ValueError): parse_response(p,json.dumps(draft))


def synthetic_source(texts):
    p=deepcopy(payload(GIDS[3])); m=p['members'][0]
    for message,text in zip(m['original_thread']['messages'],texts):
        message['text']=text
    m['agent1_record']['input_sha256']=digest(m['original_thread'])
    return p


def item(i,eid,kind,question=None,answer_status=None):
    if question is not None:
        question = dict(resolution_confidence=None, uncertainty_note=None, **question)
    return {'item_id':i,'evidence_id':eid,'kind':kind,'question':question,'answer_status':answer_status}


def test_synthetic_handling_question_context_and_diagnostics_are_distinct():
    p=synthetic_source(['How should we handle this harmless example?', 'The example describes a school story.'])
    draft=wiring_draft(p); t=draft['topics'][0]
    t['inventory']=[item('q','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}),item('context','E002','CONTEXT')]
    out=exported(p,draft)['topics'][0]
    assert len(out['open_questions'])==1 and not out['supported_answers']
    for wrong in ('FACT','DIAGNOSTIC_REQUEST'):
        bad=deepcopy(draft); bad['topics'][0]['inventory'][0].update(kind=wrong,question=None)
        retained=exported(p,bad)
        assert retained['review_required'] and retained['topics'][0]['coverage_diagnostics']
    bad=deepcopy(draft); bad['topics'][0]['inventory'][1].update(kind='ANSWER',answer_status='DIRECT')
    retained=exported(p,bad)
    assert retained['review_required'] and not retained['topics'][0]['supported_answers']
    assert retained['topics'][0]['provisional_answers']  # Unlinked context-like answer stays provisional.


def test_synthetic_diagnostic_reply_cannot_replace_or_resolve_handling_question():
    p=synthetic_source(['How should this task be handled?', 'Does another task show the same behavior?'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}),item('diag','E002','DIAGNOSTIC_REQUEST')]
    t=exported(p,draft)['topics'][0]
    assert [q['evidence_id'] for q in t['open_questions']]==['E001'] and len(t['guidance'])==1
    draft['topics'][0]['inventory'][0]['question'].update(status='ANSWERED',answer_item_ids=['diag'])
    with pytest.raises(ValueError,match='ANSWER items'): parse_response(p,json.dumps(draft))


def test_synthetic_tentative_location_advice_cannot_confirm_resolution():
    p=synthetic_source(['Where is the onboarding checklist?', 'I think it is in the shared folder; please check its date.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'PARTIAL','answer_item_ids':['a']}),
                                   item('a','E002','ANSWER',answer_status='TENTATIVE')]
    t=exported(p,draft)['topics'][0]
    assert t['open_questions'][0]['question']['status']=='PARTIAL'
    assert t['supported_answers'][0]['answer_status']=='TENTATIVE'
    assert t['supported_answers'][0]['scope']['text'].startswith('I think')
    draft['topics'][0]['inventory'][0]['question']['status']='ANSWERED'
    with pytest.raises(ValueError,match='Tentative advice'): parse_response(p,json.dumps(draft))


def test_synthetic_report_instruction_condition_and_announcement_use_content_not_channel():
    p=synthetic_source(['Service notice: the queue is stalled. Save affected IDs. Do not resubmit until status is confirmed.',
                        'Does the log show the previous attempt?'])
    # Keep the unrelated channel metadata; the model's semantic items determine kind.
    draft=wiring_draft(p); t=draft['topics'][0]
    t['inventory']=[item('notice','E001','ANNOUNCEMENT'),item('report','E001','FACT'),
        item('instruction','E001','INSTRUCTION'),item('q','E002','QUESTION',{'status':'OPEN','answer_item_ids':[]})]
    out=exported(p,draft)['topics'][0]
    assert out['conversation_kind']=='MIXED' and out['representative_question'] is None
    assert out['guidance'][0]['scope']['text']=='Service notice: the queue is stalled. Save affected IDs. Do not resubmit until status is confirmed.'
    assert len(out['source_coverage'][0]['item_ids'])==3 and out['open_questions'][0]['evidence_id']=='E002'


def test_alignment_questions_and_scoped_tl_guidance_remain_working():
    t=exported(payload(GIDS[0]),reviewed_draft(GIDS[0]))['topics'][0]
    assert {q['evidence_id'] for q in t['open_questions']}=={'E001','E002'}
    assert any(g['authority']=='TEAM_LEAD' and 'not declaring either document superseded' in g['scope']['text'] for g in t['guidance'])
    q=exported(payload(GIDS[2]),reviewed_draft(GIDS[2]))['topics'][0]
    answer=q['supported_answers'][0]
    assert answer['authority']=='TL_ENDORSED'
    assert 'on its own' in answer['scope']['text'] and 'independent flags' in answer['scope']['text']
    assert answer['evidence'][0]['tl_endorsements'][0]['user_id']=='U006'


@pytest.mark.parametrize('proposal,validity',[(None,'UNASSESSED'),({'criteria':[],'affected_scope':None},'INVALID')])
def test_valid_facts_survive_invalid_or_explicitly_unassessed_severity(proposal,validity):
    p=payload(GIDS[3]); draft=reviewed_draft(GIDS[3]); draft['topics'][0]['impact']=proposal
    out=exported(p,draft)
    assert out['processing_state']=='CONSOLIDATED' and out['factual_validity']=='VALID'
    assert out['severity_validity']==validity and out['review_required']
    assert out['topics'][0]['preliminary_severity']['level']=='UNKNOWN'
    assert out['topics'][0]['severity_proposal']==proposal
    assert out['topics'][0]['open_questions'] and out['topics'][0]['supported_answers']


def test_synthetic_guideline_conflict_is_reported_not_observed_operational_outcome():
    p=synthetic_source(['The current note and the older guide seem to disagree. Which applies?', 'Please attach the document dates.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}),item('i','E002','INSTRUCTION')]
    draft['topics'][0]['impact']=impact('E001','insufficient_impact_evidence','INSUFFICIENT_EVIDENCE',
        'Reported disagreement does not establish an operational consequence.')
    t=exported(p,draft)['topics'][0]
    assert t['preliminary_severity']['level']=='UNKNOWN'
    assert t['preliminary_severity']['evidence_basis']=='INSUFFICIENT_EVIDENCE'
    # Choosing an unsupported criterion/observation remains a semantic-review task;
    # strict JSON alone must never be represented as evidence of support.


def test_high_and_inherited_review_are_nonblocking_with_actual_v5_wire_requests(monkeypatch,tmp_path):
    gids=[GIDS[5],GIDS[1],GIDS[3]]; calls=[]
    def send(endpoint,body,key):
        req=json.loads(body); assert req['response_format']['json_schema']['strict']
        gid=json.loads(req['messages'][1]['content'])['candidate_group_id']; calls.append(gid)
        return response(reviewed_draft(gid))
    monkeypatch.setattr(transport,'send_once',send)
    m=pipeline.execute_batch([payload(g) for g in gids],tmp_path/'run',run=True,maximum_requests=3)
    assert calls==gids and m['processing_counts']=={'CONSOLIDATED':3}
    rows=read_json(tmp_path/'run/consolidations.json')
    assert rows[0]['morning_review_obligations'] and len(rows[1]['inherited_review_obligations'])==2
    assert rows[1]['topics'][0]['supported_answers']==[] and rows[2]['factual_validity']=='VALID'


def test_v4_review_is_bound_to_actual_new_outputs_not_previous_v3_candidates(tmp_path):
    before=file_hash(V4/'consolidations.json')
    view=load_effective_output(V4)
    assert len(view['records'])==len(view['review_queue'])==6 and len(view['member_review_queue'])==5
    assert not view['unapplied_findings']
    assert next(r for r in view['records'] if r['candidate_group_id']==GIDS[5])['content_review_obligations']
    assert file_hash(V4/'consolidations.json')==before
    old=ROOT/'data/experiments/agent2_revalidation_v3_2/review_supplement.json'
    stale=load_effective_output(V4,additional_supplements=[old])
    assert stale['unapplied_findings'] and all(not f['applied'] for f in stale['unapplied_findings'])


def test_prepare_both_arms_freezes_identical_content_schema_and_budget_without_credentials(monkeypatch,tmp_path):
    def forbidden(*args): raise AssertionError('Offline comparison must not read credentials.')
    monkeypatch.setattr(pipeline.config,'get_api_key',forbidden)
    target=tmp_path/'comparison'
    freeze=prepare_comparison(target)
    checked,selected=preflight_comparison(target)
    assert checked==freeze and len(selected)==6 and freeze['maximum_new_requests_total']==12
    assert freeze['arms']['A']['model']==requests.BASELINE_MODEL
    assert freeze['arms']['B']['model']==requests.COMPARISON_MODEL
    for gid in GIDS:
        a=read_json(target/'prepared/A/records'/gid/'request.json')
        b=read_json(target/'prepared/B/records'/gid/'request.json')
        assert a['messages']==b['messages'] and a['response_format']==b['response_format']
        assert all(s not in json.dumps(a) for s in ('source_review_findings','expected_verdict','synthetic_offline','assisted_source_review'))
    assert not list(target.rglob('call.json')) and not (target/'runs').exists()
    with pytest.raises(ValueError): run_arm(target,'A',12)
    freeze['maximum_new_requests_total']=13
    pipeline.write_json(target/'freeze.json',freeze)
    with pytest.raises(ValueError,match='freeze changed'): preflight_comparison(target)


def test_frozen_arm_cannot_be_repeated_or_override_model_via_environment(monkeypatch,tmp_path):
    target=tmp_path/'comparison'; freeze=prepare_comparison(target); calls=[]
    def send(endpoint,body,key):
        req=json.loads(body); calls.append(req['model'])
        return response(reviewed_draft(json.loads(req['messages'][1]['content'])['candidate_group_id']))
    monkeypatch.setattr(transport,'send_once',send)
    monkeypatch.setenv('THREADSENSE_MODEL','openai/some-other-model')
    result=run_arm(target,'A',6)
    assert result['new_request_attempts']==6 and set(calls)=={requests.BASELINE_MODEL.split('/')[1]}
    with pytest.raises(FileExistsError): run_arm(target,'A',6)
    assert len(calls)==6 and not (target/'runs/B').exists()
