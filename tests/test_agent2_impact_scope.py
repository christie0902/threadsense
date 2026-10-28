"""Focused v5.2 synthetic contracts and wire checks, not semantic accuracy tests."""
from copy import deepcopy
import json

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.legacy.agent2.operational_severity import RUBRIC, RUBRIC_V2, CRITERIA, CRITERIA_V2
from threadsense.legacy.agent2.topic_consolidation_v6 import parse_response, export_result, PROMPT_VERSION
from threadsense.legacy.agent2.topic_evidence import evidence_catalog
from threadsense.handoff_inputs import ROOT, read_json, digest
from tests.agent2_inventory_fixtures import GIDS, payload, impact
from tests.agent2_structured_fixtures import wiring_draft, reviewed_draft, assert_only_versioned_rubric_changed, assert_only_question_uncertainty_schema_changed
from tests.test_agent2_structured import synthetic_source, item


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-5.4-2026-03-05')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-offline-key')
    def forbidden(*args,**kwargs): raise AssertionError('No model call in offline tests.')
    monkeypatch.setattr(transport,'send_once',forbidden)


def exported(p,draft):
    return export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')


def test_v2_rubric_only_clarifies_medium_and_keeps_v1_available():
    old=read_json(ROOT/'data/processed/agent2_focused_v5_1/records'/GIDS[0]/'request.json')
    assert json.loads(old['messages'][1]['content'])['provisional_operational_severity_rubric']==RUBRIC
    assert RUBRIC_V2['version']=='provisional-operational-severity-v2'
    assert RUBRIC_V2['rules']==RUBRIC['rules']
    assert {k:v for k,v in CRITERIA_V2.items() if k!='bounded_operational_issue'}=={
        k:v for k,v in CRITERIA.items() if k!='bounded_operational_issue'}
    medium=CRITERIA_V2['bounded_operational_issue']
    assert medium['level']=='MEDIUM'
    assert 'source-supported mechanism' in medium['definition']
    assert 'alone does not establish delay, rework, incorrect labeling or blocked work' in medium['definition']
    assert 'does not require harm to have already occurred' in medium['definition']


def test_actual_two_wire_requests_include_scope_impact_and_count_instructions(monkeypatch,tmp_path):
    sent=[]
    def send(endpoint,body,key):
        request=json.loads(body); sent.append(request)
        gid=json.loads(request['messages'][1]['content'])['candidate_group_id']
        return 200,json.dumps({'model':request['model'],'choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps(reviewed_draft(gid))}}]}).encode(),None
    monkeypatch.setattr(transport,'send_once',send)
    result=pipeline.execute_batch([payload(GIDS[0]),payload(GIDS[1])],tmp_path/'run',run=True,maximum_requests=2)
    assert result['new_request_attempts']==2 and result['unprocessed_groups']==0
    assert result['retained_input_identities']==8 and result['inherited_review_obligations']==2
    assert result['config']['rubric_version']==RUBRIC_V2['version']
    assert len({r['messages'][0]['content'] for r in sent})==1
    for gid,request in zip((GIDS[0],GIDS[1]),sent):
        assert request==read_json(tmp_path/'run/records'/gid/'request.json')
        old=read_json(ROOT/'data/processed/agent2_focused_v5_1/records'/gid/'request.json')
        assert_only_versioned_rubric_changed(request['messages'][1],old['messages'][1])
        assert_only_question_uncertainty_schema_changed(request['response_format'],old['response_format'])
        assert {k:v for k,v in request.items() if k not in {'messages','response_format'}}=={k:v for k,v in old.items() if k not in {'messages','response_format'}}
        system=request['messages'][0]['content']
        assert system.startswith(f'Prompt version: {PROMPT_VERSION}\n')
        for text in ('complete question','PARTIAL requires a substantive component',
                     'statement withholding a decision is procedural guidance',
                     'identify the operational consequence','source-supported mechanism',
                     'observed harm is not required','Preserve HIGH for explicit substantial blockage',
                     'Omit exact counts of threads','distinct original member identities'):
            assert text in system
        assert all(g not in system for g in GIDS)
        assert all(s not in json.dumps(request) for s in ('review_supplement','expected_verdict','source_review_findings','case_01'))


@pytest.mark.parametrize('source,criterion,basis,observation,level',[
    ('The checklist and later note disagree. Which applies?', 'insufficient_impact_evidence','INSUFFICIENT_EVIDENCE',
     'Only disagreement is reported; no operational consequence or risk mechanism is established.','UNKNOWN'),
    ('The conflicting checklist required me to redo two completed forms; other work continues.', 'bounded_operational_issue','OBSERVED_OUTCOME',
     'The member reports rework of two forms, a concrete limited operational consequence; other work continues.','MEDIUM'),
    ('This import maps two fields to the same destination. If used on the queue it will overwrite one field; no import has run yet.',
     'material_quality_risk','REPORTED_RISK','The described duplicate destination mapping would overwrite a field on import, a source-supported prospective data-quality risk, not observed data loss.','HIGH'),
    ('I cannot submit the required review. The cause and number of affected reviewers are unknown.',
     'substantial_blockage','OBSERVED_OUTCOME','The source reports inability to submit assigned work; unknown cause and wider scope do not negate this blockage.','HIGH'),
])
def test_synthetic_evidenced_impact_choices_preserve_rationale_and_independent_validation(source,criterion,basis,observation,level):
    p=synthetic_source([source,'Please retain the relevant record for investigation.'])
    d=wiring_draft(p); t=d['topics'][0]
    root=item('root','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}) if '?' in source else item('root','E001','FACT')
    t['inventory']=[root,item('instruction','E002','INSTRUCTION')]
    t['impact']=impact('E001',criterion,basis,observation)
    out=exported(p,d)
    s=out['topics'][0]['preliminary_severity']
    assert out['factual_validity']==out['severity_validity']=='VALID'
    assert s['level']==level and s['evidence_basis']==basis
    assert s['rationale']['text']==observation and s['rationale']['evidence'][0]['quote']==source
    assert bool(out['morning_review_obligations'])==(level=='HIGH')
    # Invalid references still reject only impact; a source-supported interpretation
    # is reviewed by the test author/model, not proved by this deterministic check.
    t['impact']['criteria'][0]['observation']['evidence_ids']=['E999']
    bad=exported(p,d)
    assert bad['factual_validity']=='VALID' and bad['severity_validity']=='INVALID'


def test_reporting_guidance_leaves_handling_decision_open_without_answer_relabeling():
    p=synthetic_source(['Is this item eligible for release?', 'Report its identifier to the review queue. Release eligibility has not been decided.'])
    d=wiring_draft(p)
    d['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}),item('i','E002','INSTRUCTION')]
    out=exported(p,d)['topics'][0]
    assert out['open_questions'][0]['question']['status']=='OPEN'
    assert not out['supported_answers'] and not out['provisional_answers']
    assert out['guidance'][0]['text']==p['members'][0]['original_thread']['messages'][1]['text']
    assert out['inventory_counts']['answers']['member_count']==0
    assert out['inventory_counts']['guidance']['member_count']==1


@pytest.mark.parametrize('question,reply,status',[
    ('Can I release this form, and is external distribution approved?',
     'Release this form internally after removing the draft banner. External distribution is not yet decided.','PARTIAL'),
    ('Can I release this form internally after removing the draft banner?',
     'Yes, release this form internally after removing the draft banner.','ANSWERED'),
])
def test_substantive_partial_and_complete_answers_preserve_conditions_and_endorsement(question,reply,status):
    p=synthetic_source([question,reply]); m=p['members'][0]
    message=m['original_thread']['messages'][1]
    message['reactions']=[{'name':'agree','count':1,'users':['synthetic-lead'],'reactor_roles':{'synthetic-lead':'TEAM_LEAD'}}]
    m['agent1_record']['input_sha256']=digest(m['original_thread'])
    d=wiring_draft(p)
    d['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':status,'answer_item_ids':['a']}),item('a','E002','ANSWER',answer_status='DIRECT')]
    out=exported(p,d)['topics'][0]
    assert bool(out['open_questions'])==(status=='PARTIAL')
    answer=out['supported_answers'][0]
    assert answer['scope']['text']==reply and answer['authority']=='TL_ENDORSED'
    assert answer['evidence'][0]['tl_endorsements'][0]['target_message_id']==message['message_id']
    assert out['inventory'][0]['question']['status']==status


def test_inventory_counts_use_distinct_members_across_messages_and_overlapping_guidance_roles():
    # Synthetic role assignments for counting only, not a semantic review of audio.
    p=payload(GIDS[1]); d=wiring_draft(p); t=d['topics'][0]
    _,cat=evidence_catalog(p)
    t['inventory']=[i for i in t['inventory'] if i['evidence_id'] not in {'E002','E003','E005'}]
    t['inventory'] += [item('a1','E002','ANSWER',answer_status='DIRECT'),item('i1','E002','INSTRUCTION'),
        item('d1','E002','DIAGNOSTIC_REQUEST'),item('i2','E003','INSTRUCTION'),
        item('a2','E003','ANSWER',answer_status='DIRECT'),item('i3','E005','INSTRUCTION')]
    raw_before=deepcopy(d); out=exported(p,d)
    counts=out['topics'][0]['inventory_counts']
    assert counts['answers']['member_count']==1
    assert counts['answers']['member_ids']==[cat['E002']['canonical_member_id']]
    assert counts['answers']['evidence_ids']==['E002','E003']
    assert counts['guidance']['member_count']==2
    assert set(counts['guidance']['member_ids'])=={cat['E002']['canonical_member_id'],cat['E005']['canonical_member_id']}
    assert counts['guidance']['evidence_ids']==['E002','E003','E005']
    assert d==raw_before  # No prose repair or mutation of response items.
    assert out['members']==p['members'] and len(out['inherited_review_obligations'])==2
    assert out['topics'][0]['claim_reliability']=='PROVISIONAL'
