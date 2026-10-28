"""Synthetic source fixtures and real frozen accounting; no model or embeddings."""
from copy import deepcopy
import json
import runpy
import sys

import pytest

from threadsense.routing import partition, route_kind, select_activity, slack_time
from threadsense.source_ingestion import fixture_routes, interpretation_threads, extraction_report
from threadsense.handoff_inputs import ROOT, CANONICAL, load_handoff, identity, read_json
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents import topic_pipeline as pipeline, topic_taxonomy as taxonomy
from threadsense.agents.topic_effective import load_effective_output

CUTOFF = '1970-01-03T00:00:00Z'


def source(kind='ANNOUNCEMENTS', tid='86400.000001'):
    return {'channel_id':'C_SYNTHETIC', 'channel_type':kind, 'project_id':'synthetic',
        'batch_id':'synthetic_batch', 'thread_id':tid, 'channel_metadata':{},
        'users':{'u1':{'name':'Synthetic lead','role':'TEAM_LEAD'},
                 'u2':{'name':'Synthetic engineer','role':'ENGINEER'}},
        'messages':[{'ts':tid,'user':'u1','text':'Synthetic source only.',
                     'reactions':[{'name':'eyes','users':['u2'],'count':1}]}]}


def reply(ts, **kwargs):
    return {'ts':ts,'user':'u2','text':'Synthetic context question?',**kwargs}


@pytest.fixture(autouse=True)
def no_calls(monkeypatch):
    from threadsense.agents import verification_requests, thread_interpreter
    def forbidden(*a, **kw):raise AssertionError('No calls in source routing.')
    monkeypatch.setattr(verification_requests,'send_once',forbidden)
    monkeypatch.setattr(thread_interpreter,'create_llm',forbidden)


@pytest.mark.parametrize('kind', ['GENERAL','QA','TUTOR'])
def test_explicit_discussion_types_keep_tl_replies(kind):
    s=source(kind); s['channel_name']='announcements'; s['messages'][0]['text']='Official decision'
    assert route_kind(s)=='DISCUSSION'
    assert partition([s])[0]==[s]


def test_no_name_or_role_inference_and_conflicts_fail_closed():
    s=source(); s.pop('channel_type'); s['channel_name']='announcements'
    with pytest.raises(ValueError,match='explicit'):route_kind(s)
    s=source('GENERAL')
    with pytest.raises(ValueError,match='conflict'):
        route_kind(s,rules={'C_SYNTHETIC':{'channel_type':'ANNOUNCEMENTS'}})
    with pytest.raises(ValueError,match='Duplicate'):partition([s,s])


@pytest.mark.parametrize('ts,selected', [('86399.999999',False),('86400.000000',True),
                                       ('172799.999999',True),('172800.000000',False)])
def test_exact_half_open_window(ts,selected):
    rows,report=select_activity([source(tid=ts)],CUTOFF)
    assert bool(rows)==selected
    assert report['source_messages_in_window']==int(selected)
    if selected:assert rows[0]['thread_id']==ts


def test_timezone_and_slack_precision():
    assert select_activity([source()],CUTOFF)==select_activity([source()],'1970-01-02T19:00:00-05:00')
    with pytest.raises(ValueError,match='timezone'):select_activity([source()],'1970-01-03T00:00:00')
    with pytest.raises(ValueError):slack_time(86400.000001)


@pytest.mark.parametrize('activity', ['reply','edit'])
def test_old_parent_new_reply_or_exposed_edit(activity):
    s=source(tid='10000.000001')
    if activity=='reply':s['messages'].append(reply('90000.000001'))
    else:s['messages'][0]['edited']={'ts':'90000.000001','user':'u1'}
    rows,report=select_activity([s],CUTOFF)
    assert len(rows)==report['source_threads_in_window']==1
    assert rows[0]['messages']==s['messages']
    assert report['source_messages_in_window']==1
    assert report['context_messages']==(activity=='reply')


def test_future_edit_and_malformed_timestamp_are_visible_failures():
    changed=source();changed['messages'][0]['edited']={'ts':'172800.000001'}
    malformed=source(tid='10000.000001');malformed['messages'].append(reply('invalid'))
    rows,report=select_activity([changed,malformed],CUTOFF)
    assert not rows and report['source_threads_in_window']==1
    assert report['window_selection_failed_threads']==report['unclassified_source_threads']==1
    assert report['source_messages_in_window']==1
    assert len(report['selection_failures'])==2
    assert report['selection_failures'][0]['source']==changed


def test_empty_window_and_independent_extraction_failure(tmp_path):
    assert fixture_routes(ROOT/'data/fixtures/slack_generated',cutoff='2030-01-01T00:00:00Z')[2]['input_threads']==0
    good=source();bad=source(tid='86401.000001');bad['messages']=[]
    d,a,r=partition([bad,good]);r.update(source_threads_in_window=2)
    report=extraction_report(d,a,r,destination=tmp_path)
    assert report['stored_new_records']==1 and len(report['extraction_failures'])==1
    assert report['extraction_failures'][0]['source']==bad and report['state']=='complete_with_failures'
    assert report['model_calls']==0


def test_canonical_partition_preserves_all_49_obligations_and_all_lineage():
    members=load_handoff();d,a,r=partition(members)
    assert (len(members),len(d),len(a))==(200,178,22)
    assert sum(m['agent1_record']['review_required'] for m in d)==41
    assert sum(m['agent1_record']['review_required'] for m in a)==8
    assert r['announcement_sources']==a
    assert {identity(m):m for m in d+a}=={identity(m):m for m in members}
    payloads=load_candidate_payloads()
    assert len(payloads)==81 and sum(len(p['members']) for p in payloads)==178
    assert {identity(m) for p in payloads for m in p['members']}=={identity(m) for m in d}
    for p in payloads:assert p['routing_manifest']['announcement_threads']==22


def test_all_supported_boundaries_exclude_announcements_before_calls():
    from threadsense.agents.thread_interpreter import interpret_thread
    from threadsense.models import Thread
    from threadsense.topic_grouping import group_members
    historical=load_candidate_payloads(historical=True)
    p=next(p for p in historical if any(route_kind(m)=='ANNOUNCEMENT' for m in p['members']))
    m=next(m for m in p['members'] if route_kind(m)=='ANNOUNCEMENT')
    with pytest.raises(ValueError,match='Announcement'):interpret_thread(Thread.model_validate(m['original_thread']))
    with pytest.raises(ValueError,match='Announcement'):taxonomy.build_request(p,{},'openai/gpt-4o-mini')
    with pytest.raises(ValueError,match='Announcement'):taxonomy.export_result(p)
    with pytest.raises(ValueError,match='Announcement'):group_members([m],None,None,.50)
    batch=runpy.run_path(str(ROOT/'scripts/run_agent1_batch.py'))
    threads=batch['load_threads'](ROOT/'data/fixtures/slack_generated',None)
    assert len(threads)==178 and all(route_kind(t)=='DISCUSSION' for t in threads)
    grouping=runpy.run_path(str(ROOT/'scripts/run_thread_grouping.py'))
    assert len(grouping['load_records'](CANONICAL))==178


def test_stale_reply_count_and_tutor_channel_preserve_selected_context(tmp_path):
    s=source('TUTOR',tid='10000.000001');s['messages'].append(reply('90000.000001'))
    fixture=tmp_path/'fixtures';(fixture/'channels').mkdir(parents=True)
    (fixture/'users.json').write_text(json.dumps([{'id':k,**v} for k,v in s['users'].items()]))
    (fixture/'channels/C_SYNTHETIC.json').write_text(json.dumps({'channel':{
        'id':s['channel_id'],'name':'synthetic','channel_type':'TUTOR','project_id':'synthetic'},
        'history':[s['messages'][0]],'replies':{s['thread_id']:s['messages']}}))
    threads,a,r=interpretation_threads(fixture,cutoff=CUTOFF)
    assert not a and len(threads)==1
    assert [m.message_id for m in threads[0].messages]==[m['ts'] for m in s['messages']]
    assert r['context_messages']==1


def test_active_export_unassessed_without_assessor_and_effective_routing(tmp_path,monkeypatch):
    from threadsense.legacy import taxonomy_severity_v7
    def forbidden(*a,**kw):raise AssertionError('Historical assessment cannot run for active exports.')
    monkeypatch.setattr(taxonomy_severity_v7,'assess_canonical_impact',forbidden)
    p=next(p for p in load_candidate_payloads() if any(m['agent1_record']['review_required'] for m in p['members']))
    d={'topics':[{'topic_name':'Synthetic grouping','rationale':'Synthetic wiring only.',
                 'member_ids':[m['member_id'] for m in p['members']]}],'rejected_member_ids':[]}
    row=taxonomy.export_result(p,taxonomy.parse_response(p,json.dumps(d)),state='CONSOLIDATED')
    assert row['schema_version']==8 and row['response_schema_version']==7
    assert row['topics'][0]['preliminary_severity']=={'level':'UNKNOWN','assessment_status':'UNASSESSED',
        'assessment_deferred_to':'AGENT3','reason':'Agent 2 performs taxonomy only.'}
    assert not row['morning_review_obligations'] and row['review_required']
    pipeline.write_json(tmp_path/'consolidations.json',[row])
    view=load_effective_output(tmp_path);handoff=view['records'][0]['taxonomy_handoff']
    assert handoff['contract_version']=='agent2-taxonomy-handoff-v2'
    assert handoff['routing_manifest']==p['routing_manifest']
    assert handoff['members']==p['members'] and view['member_review_queue']==row['inherited_review_obligations']


def test_full_routing_receipt_published_with_prepared_groups(tmp_path,monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-4o-mini')
    p=load_candidate_payloads()[:1]
    out=tmp_path/'prepared';manifest=pipeline.execute_batch(p,out,run=False)
    route=read_json(out/'routing_manifest.json')
    assert route['input_threads']==200 and len(route['announcement_sources'])==22
    assert manifest['new_request_attempts']==0
    assert 'announcement_sources' not in (out/'records'/p[0]['candidate_group_id']/'request.json').read_text()


def test_all_frozen_v7_rows_replay_without_reinterpretation():
    from threadsense.agents.topic_consolidation import parse_response,export_result
    run=ROOT/'data/processed/agent2_taxonomy_final_v7'
    rows=read_json(run/'consolidations.json')
    for row in rows:
        directory=run/'records'/row['candidate_group_id']
        payload=read_json(directory/'input.json')
        analysis=parse_response(payload,(directory/'analysis.raw.txt').read_text(encoding='utf-8'))
        assert export_result(payload,analysis,state='CONSOLIDATED',export_adapter_version='taxonomy-to-canonical-v1')==row
    view=load_effective_output(run)
    assert len(rows)==90 and len(view['member_review_queue'])==49
    assert len(view['applied_content_obligations'])==3


def test_active_model_prompt_and_schema_match_historical_taxonomy():
    from threadsense.legacy import topic_taxonomy_v7
    from threadsense.terminology import get_terms
    p=load_candidate_payloads()[0]
    assert taxonomy.build_request(p,get_terms(),'openai/gpt-4o-mini')==topic_taxonomy_v7.build_request(p,get_terms(),'openai/gpt-4o-mini')


def test_sample_routes_announcement_before_thread_conversion_and_keeps_flags(tmp_path,monkeypatch):
    from threadsense.adapters.mock_slack import MockSlackAdapter
    from threadsense import source_ingestion
    main=runpy.run_path(str(ROOT/'scripts/run_agent1_demo.py'))['main']
    fixture=tmp_path/'data/fixtures/slack_generated';fixture.mkdir(parents=True)
    (fixture/'users.json').write_text('[]')
    s=source();s['users']={}  # Unknown author must remain unknown, not require a Thread role.
    d,a,r=partition([s])
    member={k:s[k] for k in ('project_id','batch_id','channel_id','thread_id')}
    member['agent1_record']={'review_required':True,'lineage':{'source':'synthetic'}}
    monkeypatch.setattr(source_ingestion,'fixture_routes',lambda *a,**kw:(d,[s],r))
    monkeypatch.setattr(source_ingestion,'existing_canonical_members',lambda:[member])
    def forbidden(*a,**kw):raise AssertionError('Announcement must not enter interpretation conversion.')
    monkeypatch.setattr(MockSlackAdapter,'get_threads',forbidden)
    monkeypatch.setitem(main.__globals__,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['sample','--channel',s['channel_id'],'--thread-id',s['thread_id'],'--cutoff',CUTOFF])
    main()
    files=list((tmp_path/'data/knowledge/decisions').rglob('source.json'))
    assert len(files)==1
    assert read_json(files[0])['inherited_agent1']==member
    assert read_json(files[0])['author']['recorded_role'] is None


def test_prospective_assembly_preserves_full_routing_and_rejects_tampering(tmp_path,monkeypatch):
    from threadsense.agents import verification_requests
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-4o-mini')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-key')
    payloads=load_candidate_payloads()[:2]
    def send(endpoint,body,key):
        candidate=json.loads(json.loads(body)['messages'][1]['content'])
        draft={'topics':[{'topic_name':'Synthetic topic','rationale':'Structural test only.',
            'member_ids':[m['member_id'] for m in candidate['members']]}],'rejected_member_ids':[]}
        return 200,json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(draft)}}]}).encode(),None
    monkeypatch.setattr(verification_requests,'send_once',send)
    a,b=tmp_path/'a',tmp_path/'b'
    pipeline.execute_batch(payloads[:1],a,run=True,maximum_requests=1)
    pipeline.execute_batch(payloads[1:],b,run=True,maximum_requests=1)
    assemble=runpy.run_path(str(ROOT/'scripts/assemble_agent2_dataset.py'))['assemble_dataset']
    registry=tmp_path/'registry.json';pipeline.write_json(registry,{'supplements':[]})
    original=read_json(a/'routing_manifest.json')
    pipeline.write_json(a/'routing_manifest.json',{**original,'announcement_sources':[]})
    with pytest.raises(ValueError,match='routing manifest'):
        assemble([(a,'reused'),(b,'new')],tmp_path/'refused',payloads,registry=registry)
    assert not (tmp_path/'refused').exists()
    pipeline.write_json(a/'routing_manifest.json',original)
    result=assemble([(a,'reused'),(b,'new')],tmp_path/'final',payloads,registry=registry)
    assert result['schema_version']==8 and result['groups']==2 and result['assembly_model_calls']==0
    assert read_json(tmp_path/'final/routing_manifest.json')==original


def test_prospective_offline_continuation_carries_announcement_obligations(tmp_path,monkeypatch):
    from threadsense.agents.topic_continuation import continue_batch
    monkeypatch.setenv('THREADSENSE_MODEL','openai/gpt-4o-mini')
    payloads=load_candidate_payloads()[:1]
    pipeline.execute_batch(payloads,tmp_path/'before',run=False)
    result=continue_batch(payloads,tmp_path/'before',tmp_path/'after',run=False)
    assert read_json(tmp_path/'after/routing_manifest.json')==read_json(tmp_path/'before/routing_manifest.json')
    assert result['new_request_attempts']==0
