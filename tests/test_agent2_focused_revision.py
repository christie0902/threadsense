"""Focused v5.1 instruction and synthetic contract checks; no accuracy claims."""
from copy import deepcopy
import json

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.legacy.agent2.topic_consolidation_v6 import parse_response, export_result, PROMPT_VERSION
from threadsense.handoff_inputs import ROOT, read_json
from tests.agent2_inventory_fixtures import GIDS, payload, impact
from tests.agent2_structured_fixtures import reviewed_draft, wiring_draft, assert_only_versioned_rubric_changed, assert_only_question_uncertainty_schema_changed
from tests.test_agent2_structured import synthetic_source, item

ORDER=[GIDS[5],GIDS[1],GIDS[2],GIDS[0]]
BASE=ROOT/'data/experiments/agent2_comparison_v5'


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-5.4-2026-03-05')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-offline-key')
    def forbidden(*args,**kwargs): raise AssertionError('No model call in offline tests.')
    monkeypatch.setattr(transport,'send_once',forbidden)


def test_four_actual_wire_requests_carry_same_revised_rules_and_frozen_b_settings(monkeypatch,tmp_path):
    sent=[]
    def send(endpoint,body,key):
        request=json.loads(body); sent.append(request)
        gid=json.loads(request['messages'][1]['content'])['candidate_group_id']
        return 200,json.dumps({'model':request['model'],'choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps(reviewed_draft(gid))}}]}).encode(),None
    monkeypatch.setattr(transport,'send_once',send)
    result=pipeline.execute_batch([payload(g) for g in ORDER],tmp_path/'run',run=True,maximum_requests=4)
    assert result['new_request_attempts']==4 and result['processing_counts']=={'CONSOLIDATED':4}
    assert result['retained_input_identities']==12 and result['inherited_review_obligations']==2
    rows=read_json(tmp_path/'run/consolidations.json')
    assert rows[0]['morning_review_obligations'] and rows[-1]['processing_state']=='CONSOLIDATED'
    assert len({r['messages'][0]['content'] for r in sent})==1
    assert [json.loads(r['messages'][1]['content'])['candidate_group_id'] for r in sent]==ORDER
    for gid,r in zip(ORDER,sent):
        old=read_json(BASE/'runs/B/records'/gid/'request.json')
        assert r==read_json(tmp_path/'run/records'/gid/'request.json')
        assert_only_versioned_rubric_changed(r['messages'][1],old['messages'][1])
        assert_only_question_uncertainty_schema_changed(r['response_format'],old['response_format'])
        assert {k:v for k,v in r.items() if k not in {'messages','response_format'}}=={k:v for k,v in old.items() if k not in {'messages','response_format'}}
        system=r['messages'][0]['content']
        assert system.startswith(f'Prompt version: {PROMPT_VERSION}\n')
        for text in ('Before selecting a lower-impact criterion','Unknown root cause or',
            'isolated keywords do not establish HIGH','evidenced prospective risk',
            'reported document disagreement does not automatically',
            'never fill the gap with speculative harm','Select the controlling rubric level',
            'only\nsupported criteria consistent with that one level',
            'Never relabel an item ANSWER solely to','Diagnostics may coexist with a valid partial answer',
            'keep the question OPEN with no links'):
            assert text in system
        assert all(g not in system for g in GIDS)
        assert all(s not in json.dumps(r) for s in ('review_supplement_','expected_verdict','assisted_source_review','case_01'))


def test_diagnostic_and_valid_partial_answer_coexist_without_closing_the_question():
    p=synthetic_source(['How is the stale preview handled while approval is pending?',
        'For this item retain the original record for now. Which preview version is displayed? Final handling still needs approval.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[
        item('q','E001','QUESTION',{'status':'PARTIAL','answer_item_ids':['a']}),
        item('a','E002','ANSWER',answer_status='DIRECT'),item('d','E002','DIAGNOSTIC_REQUEST')]
    out=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')['topics'][0]
    assert out['open_questions'][0]['question']=={'status':'PARTIAL','answer_item_ids':['a'], 'resolution_confidence':None, 'uncertainty_note':None}
    assert len(out['supported_answers'])==len(out['guidance'])==1
    assert 'Final handling still needs approval' in out['supported_answers'][0]['scope']['text']


@pytest.mark.parametrize('kind',['FACT','CONTEXT','DIAGNOSTIC_REQUEST','INSTRUCTION'])
def test_same_message_non_answer_role_cannot_satisfy_link(kind):
    p=synthetic_source(['How should this item be handled?', 'Please provide the item version.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'PARTIAL','answer_item_ids':['x']}),item('x','E002',kind)]
    with pytest.raises(ValueError,match='scoped ANSWER'):
        parse_response(p,json.dumps(draft))


def test_reported_blockage_can_be_high_with_unknown_cause_and_extent():
    p=synthetic_source(['I cannot complete the assigned review because the required form will not open. Cause and other affected users are unknown.',
        'Please attach the form identifier; the underlying cause is not established.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('report','E001','FACT'),item('diagnostic','E002','DIAGNOSTIC_REQUEST')]
    draft['topics'][0]['impact']=impact('E001','substantial_blockage','OBSERVED_OUTCOME',
        'The member reports being unable to complete this assigned review; cause and wider extent are unknown.')
    draft['topics'][0]['impact']['affected_scope']=None
    out=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')
    severity=out['topics'][0]['preliminary_severity']
    assert severity['level']=='HIGH' and severity['affected_scope'] is None
    assert severity['quality_or_safety_consequences'] is None and out['morning_review_obligations']


@pytest.mark.parametrize('text',[
    'The older checklist and latest note differ. Which wording applies?',
    'Which category fits this unusual example? No effect on completed work is reported.',
])
def test_clarification_without_impact_evidence_can_remain_unknown(text):
    p=synthetic_source([text,'Please attach the exact wording for review.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('q','E001','QUESTION',{'status':'OPEN','answer_item_ids':[]}),item('d','E002','DIAGNOSTIC_REQUEST')]
    draft['topics'][0]['impact']=impact('E001','insufficient_impact_evidence','INSUFFICIENT_EVIDENCE',
        'The exchange requests clarification without evidence establishing operational impact.')
    out=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')
    assert out['severity_validity']=='VALID' and out['topics'][0]['preliminary_severity']['level']=='UNKNOWN'
    assert not out['morning_review_obligations']


def test_lower_observation_can_remain_without_conflicting_with_controlling_high():
    p=synthetic_source(['The required form cannot save the assigned review. The confirmation wording is also unclear.',
        'Please retain the form reference while the problem is investigated.'])
    draft=wiring_draft(p)
    draft['topics'][0]['inventory']=[item('report','E001','FACT'),item('i','E002','INSTRUCTION')]
    draft['topics'][0]['relevant_differences']=[{'text':'The report also mentions unclear confirmation wording.','evidence_ids':['E001']}]
    draft['topics'][0]['impact']=impact('E001','substantial_blockage','OBSERVED_OUTCOME','The member reports the required form cannot save their assigned review.')
    out=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')
    assert out['severity_validity']=='VALID' and out['topics'][0]['preliminary_severity']['level']=='HIGH'
    assert out['topics'][0]['relevant_differences']
    draft['topics'][0]['impact']['criteria']+=impact('E001','bounded_operational_issue','OBSERVED_OUTCOME')['criteria']
    rejected=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')
    assert rejected['factual_validity']=='VALID' and rejected['severity_validity']=='INVALID'
