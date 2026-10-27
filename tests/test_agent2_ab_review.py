"""Executed v5 A/B regressions, not synthetic evidence of model accuracy.

Original responses remain immutable. Negative synthetic link cases exercise each
scope/type rule independently; no saved response is repaired or promoted.
"""
from copy import deepcopy
import json

from jsonschema import Draft202012Validator
import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_consolidation_v6 import build_request, parse_response, export_result
from threadsense.agents.topic_contracts_v5 import InventoryTopic
from threadsense.agents.topic_diagnostics import describe_exception
from threadsense.agents.topic_effective import load_effective_output
from threadsense.agents.topic_evidence import evidence_catalog
from threadsense.agents.topic_consolidation_v6 import derive_severity, RUBRIC_VERSION, EXPORT_ADAPTER_VERSION
from threadsense.handoff_inputs import ROOT, read_json, file_hash, identity, digest
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, payload, impact
from tests.agent2_structured_fixtures import wiring_draft, reviewed_draft, assert_only_versioned_rubric_changed, assert_only_question_uncertainty_schema_changed

BASE=ROOT/'data/experiments/agent2_comparison_v5'
REVIEW=ROOT/'data/experiments/agent2_comparison_v5_review'
FREEZE=read_json(BASE/'freeze.json')


@pytest.fixture(autouse=True)
def forbid_model_calls(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Saved-response review must never call a model.')
    monkeypatch.setattr(transport,'send_once',forbidden)


@pytest.mark.parametrize('arm',['A','B'])
@pytest.mark.parametrize('gid',GIDS)
def test_saved_responses_keep_application_verdict_under_current_code_replay(arm,gid):
    d=BASE/FREEZE['arms'][arm]['run_dir']/'records'/gid
    request=read_json(d/'request.json'); http=read_json(d/'response.raw.bin')
    raw=(d/'analysis.raw.txt').read_text(encoding='utf-8')
    before=file_hash(d/'analysis.raw.txt')
    assert read_json(d/'response.json')=={'http_status':200,'failure':None}
    assert http['model']==request['model']==FREEZE['arms'][arm]['model'].split('/',1)[1]
    assert http['choices'][0]['finish_reason']=='stop' and not http['choices'][0]['message'].get('refusal')
    assert http['choices'][0]['message']['content']==raw
    # Provider shape acceptance and local semantic/cross-field acceptance differ.
    assert not list(Draft202012Validator(request['response_format']['json_schema']['schema']).iter_errors(json.loads(raw)))
    p=read_json(d/'input.json'); historical=read_json(d/'result.json')
    if arm=='A' or gid==GIDS[1]:
        assert historical['processing_state']=='FAILED'
        with pytest.raises(ValueError) as caught: parse_response(p,raw,response_schema_version=5)
        assert describe_exception(p,caught.value)==read_json(d/'diagnostics.json')
    else:
        assert historical['processing_state']=='CONSOLIDATED'
        parsed=parse_response(p,raw,response_schema_version=5)
        replay=export_result(p,parsed,state='CONSOLIDATED')
        # This is a current-code replay, not a newly generated or rewritten result.
        # V5.2 adds distinct-member counts and records rubric v2 / export v3.
        # Every other field must still match the original saved result exactly.
        projection=deepcopy(replay)
        assert projection['schema_version'] == 6
        projection['schema_version'] = 5
        for t in projection['topics']:
            assert t['export_adapter_version']==EXPORT_ADAPTER_VERSION
            counts=t.pop('inventory_counts')
            _,catalog=evidence_catalog(p)
            for name,kinds in [('answers',{'ANSWER'}),('guidance',{'ANSWER','INSTRUCTION','DIAGNOSTIC_REQUEST'})]:
                source_ids={i['evidence_id'] for i in t['inventory'] if i['kind'] in kinds}
                mids={catalog[e]['canonical_member_id'] for e in source_ids}
                assert counts[name]['member_count']==len(mids)
                assert set(counts[name]['member_ids'])==mids
                assert set(counts[name]['evidence_ids'])==source_ids
            t['export_adapter_version']='inventory-to-display-v2'
        seen_nodes=set()
        def historical_version(value):
            if isinstance(value,(list,dict)):
                if id(value) in seen_nodes: return
                seen_nodes.add(id(value))
            if isinstance(value,list):
                for child in value: historical_version(child)
            elif isinstance(value,dict):
                if 'rubric_version' in value:
                    assert value['rubric_version']==RUBRIC_VERSION
                    value['rubric_version']='provisional-operational-severity-v1'
                for child in value.values(): historical_version(child)
        historical_version(projection)
        assert projection==historical
    assert file_hash(d/'analysis.raw.txt')==before


@pytest.mark.parametrize('root,target,kind',[
    ('E004','E015','ANSWER'),  # Correct kind still cannot transfer another member's answer.
    ('E014','E015','FACT'),
    ('E016','E019','INSTRUCTION'),
])
def test_synthetic_multi_role_links_cannot_be_resolved_by_source_id_alone(root,target,kind):
    p=payload(GIDS[1]); draft=wiring_draft(p); items=draft['topics'][0]['inventory']
    question=next(i for i in items if i['evidence_id']==root)
    answer=next(i for i in items if i['evidence_id']==target)
    answer.update(kind=kind,answer_status='DIRECT' if kind=='ANSWER' else None)
    question.update(kind='QUESTION',question={'status':'PARTIAL','answer_item_ids':[answer['item_id']], 'resolution_confidence':None, 'uncertainty_note':None})
    with pytest.raises(ValueError,match='scoped ANSWER items in the same thread') as caught:
        parse_response(p,json.dumps(draft))
    assert describe_exception(p,caught.value)[0]['category']=='answer_evidence'


def test_real_audio_failure_has_three_bad_links_and_two_independent_impact_failures():
    d=BASE/'runs/B/records'/GIDS[1]; p=read_json(d/'input.json'); raw=read_json(d/'analysis.raw.txt')
    _,catalog=evidence_catalog(p)
    topic=raw['topics'][1]; items={i['item_id']:i for i in topic['inventory']}
    problems=[]
    for i in topic['inventory']:
        for link in (i['question'] or {}).get('answer_item_ids',[]):
            target=items[link]
            if target['kind']!='ANSWER' or catalog[target['evidence_id']]['member_id']!=catalog[i['evidence_id']]['member_id']:
                problems.append((i['item_id'],link,target['kind']))
    assert problems==[('T2_I1','T2_I11','FACT'),('T2_I8','T2_I11','FACT'),('T2_I12','T2_I17','INSTRUCTION')]
    for ti,t in enumerate(raw['topics']):
        section=InventoryTopic.model_validate({k:v for k,v in t.items() if k!='impact'})
        with pytest.raises(ValueError,match='unambiguous rubric level'):
            derive_severity(t['impact'],section,catalog,ti)
    assert read_json(d/'result.json')['processing_state']=='FAILED'


@pytest.mark.parametrize('criteria',[
    [('bounded_operational_issue','OBSERVED_OUTCOME'),('insufficient_impact_evidence','INSUFFICIENT_EVIDENCE')],
    [('substantial_blockage','OBSERVED_OUTCOME'),('bounded_operational_issue','OBSERVED_OUTCOME')],
])
def test_synthetic_mixed_levels_preserve_valid_facts_with_invalid_severity(criteria):
    p=payload(GIDS[3]); draft=reviewed_draft(GIDS[3])
    draft['topics'][0]['impact']={'criteria':[impact('E001',c,b)['criteria'][0] for c,b in criteria],'affected_scope':None}
    out=export_result(p,parse_response(p,json.dumps(draft)),state='CONSOLIDATED')
    assert out['factual_validity']=='VALID' and out['severity_validity']=='INVALID'
    assert out['review_required'] and out['topics'][0]['preliminary_severity']['level']=='UNKNOWN'


@pytest.mark.parametrize('arm',['A','B'])
def test_new_reviews_are_source_bound_preserve_every_identity_and_flag_and_do_not_rewrite(arm):
    run=BASE/'runs'/arm; canonical=read_json(run/'consolidations.json')
    before=file_hash(run/'consolidations.json'); view=load_effective_output(run)
    assert len(view['records'])==6 and len(view['review_queue'])==(6 if arm=='A' else 5)
    assert len({identity(m) for r in view['records'] for m in r['members']})==18
    assert view['member_review_queue']==read_json(run/'member_review_queue.json')
    assert len(view['member_review_queue'])==5 and not view['unapplied_findings']
    assert view['applied_content_obligations']
    for obligation in view['applied_content_obligations']:
        d=run/'records'/obligation['candidate_group_id']
        assert obligation['binding']=={'input_file_sha256':file_hash(d/'input.json'),
            'raw_draft_sha256':file_hash(d/'analysis.raw.txt'),'export_result_sha256':file_hash(d/'result.json')}
        assert obligation['finding']['source_evidence']
    assert [r['processing_state'] for r in view['records']]==[r['processing_state'] for r in canonical]
    assert file_hash(run/'consolidations.json')==before


def test_material_severity_finding_routes_original_medium_to_review_without_rewriting_high():
    run=BASE/'runs/B'; view=load_effective_output(run)
    original=read_json(run/'records'/GIDS[5]/'result.json')
    effective=next(r for r in view['records'] if r['candidate_group_id']==GIDS[5])
    assert original['processing_state']=='CONSOLIDATED' and not original['review_required']
    assert original['topics'][0]['preliminary_severity']['level']=='MEDIUM'
    assert not original['morning_review_obligations']
    assert effective['review_required'] and effective['content_review_obligations']
    assert effective['topics'][0]['preliminary_severity']==original['topics'][0]['preliminary_severity']
    # This is an assisted dispute, not a silent severity correction or human approval.
    assert effective['effective_content_review_status']=='DISPUTED'


def test_accepted_b_improvements_retain_conditions_endorsements_tentative_advice_and_announcements():
    rows={r['candidate_group_id']:r for r in read_json(BASE/'runs/B/consolidations.json')}
    quarantine=rows[GIDS[2]]['topics'][0]
    assert [q['question']['status'] for q in quarantine['open_questions']]==['PARTIAL','OPEN','OPEN']
    answer=quarantine['supported_answers'][0]
    assert answer['authority']=='TL_ENDORSED' and 'on its own' in answer['scope']['text'] and 'independent flags' in answer['scope']['text']
    assert answer['evidence'][0]['tl_endorsements']==[{'reaction':'agree','user_id':'U006','target_message_id':answer['evidence'][0]['message_id']}]
    avatar=rows[GIDS[3]]['topics'][0]
    assert avatar['supported_answers'][0]['answer_status']=='TENTATIVE'
    assert avatar['open_questions'][0]['question']['status']=='PARTIAL'
    submission=rows[GIDS[4]]['topics'][0]
    assert submission['representative_question'] is None and submission['conversation_kind']=='ANNOUNCEMENT'
    assert submission['preliminary_severity']['level']=='HIGH' and submission['morning_review_required']
    assert len(submission['flagged_member_ids'])==3
    assert any('successful reload is not proof' in g['scope']['text'] for g in submission['guidance'])


def test_review_labels_never_reach_requests_and_historical_freeze_remains_unchanged():
    assert read_json(BASE/'freeze_receipt.json')['freeze_sha256']==file_hash(BASE/'freeze.json')
    for arm in ('A','B'):
        spec=FREEZE['arms'][arm]
        for saved in spec['requests']:
            d=BASE/spec['run_dir']/'records'/saved['candidate_group_id']
            assert file_hash(d/'request.json')==saved['request_sha256']
            current=build_request(read_json(d/'input.json'),get_terms(),spec['model'])
            historical=read_json(d/'request.json')
            # A later authorized instruction revision does not rewrite the original
            # freeze. Source inputs, schema and model settings remain independent of
            # assisted findings; system instructions and explicitly versioned
            # rubric are the only semantic-input revisions.
            assert_only_versioned_rubric_changed(current['messages'][1],historical['messages'][1])
            assert_only_question_uncertainty_schema_changed(current['response_format'],historical['response_format'])
            assert {k:v for k,v in current.items() if k not in {'messages','response_format'}}=={k:v for k,v in historical.items() if k not in {'messages','response_format'}}
            assert all(label not in json.dumps(current) for label in (
                'understated_blockage_missing_high_review','review_supplement_',
                'codex_assisted_source_review','expected_verdict'))
    for arm in ('A','B'):
        manifest=read_json(BASE/FREEZE['arms'][arm]['run_dir']/'manifest.json')
        assert manifest['config']==FREEZE['arms'][arm]['config']
