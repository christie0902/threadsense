"""Offline validation of the actual v7 release; no mocked/model calls or mutations.

Writes new accounting receipts only after all assertions pass. This is a one-off
milestone audit, not a producer change or an additional model verifier.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics

from threadsense.handoff_inputs import ROOT, CANONICAL, GROUPING, read_json, file_hash, digest, identity
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_consolidation import build_request, parse_response, export_result
from threadsense.agents.topic_pipeline import write_json
from threadsense.agents.topic_effective import REGISTRY, load_effective_output, taxonomy_handoff
from threadsense.terminology import get_terms

HERE = Path(__file__).resolve().parent
RUN = ROOT/'data/processed/agent2_taxonomy_final_v7'


def main():
    f = read_json(HERE/'freeze.json')
    os.environ['THREADSENSE_MODEL'] = f['model']
    os.environ['THREADSENSE_AGENT2_REASONING_EFFORT'] = 'low'
    checks = []
    assert file_hash(HERE/'freeze.json') == read_json(HERE/'freeze_receipt.json')['freeze_sha256']
    for path, value in f['config']['code_sha256'].items():
        if path != 'docs/agent2-review-supplements.json':
            assert file_hash(ROOT/path) == value, path
    assert file_hash(ROOT/'scripts/assemble_agent2_dataset.py') == f['assembly_script_sha256']
    assert file_hash(CANONICAL) == f['canonical_sha256'] and file_hash(GROUPING) == f['grouping_sha256']
    registry = read_json(REGISTRY)
    original_registry = dict(registry, supplements=registry['supplements'][:-2])
    encoded = (json.dumps(original_registry, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
    assert hashlib.sha256(encoded).hexdigest() == f['config']['code_sha256']['docs/agent2-review-supplements.json']
    assert len(original_registry['supplements']) == 11
    for entry in original_registry['supplements']:
        assert file_hash(ROOT/entry['path']) == entry['sha256']
    checks.append('Frozen producer/assembler, model parameters, inputs, glossary and eleven historical review registrations unchanged; two post-run registrations appended explicitly.')
    payloads = load_candidate_payloads()
    by = {p['candidate_group_id']:p for p in payloads}
    rows = read_json(RUN/'consolidations.json'); manifest = read_json(RUN/'manifest.json')
    assert len(by) == len(rows) == 90 and {r['candidate_group_id'] for r in rows} == set(by)
    mids = [identity(m) for r in rows for m in r['members']]
    canonical = read_json(CANONICAL)
    assert len(mids) == len(set(mids)) == 200
    assert Counter(mids) == Counter(identity(r) for r in canonical)
    assert {identity(m):m['agent1_record'] for r in rows for m in r['members']} == {identity(r):r for r in canonical}
    assert dict(Counter(r['verification_status'] for r in canonical)) == {'VERIFIED':81,'CORRECTED':70,'NEEDS_REVIEW':49}
    checks.append('Exactly 90 canonical groups and 200 unique full project/batch/channel/thread identities; entire Agent 1 records deep-equal, including statuses, evidence, hashes and lineage.')
    ledger = []; dispositions = Counter(); projects = {}
    frozen_requests = {r['candidate_group_id']:r for r in f['requests']}
    for row in rows:
        gid = row['candidate_group_id']; p = by[gid]; d = RUN/'records'/gid
        origin = manifest['record_provenance'][gid]; source = Path(origin['source_run'])
        assert source == (ROOT/f['reused_run']).resolve() if origin['origin']=='reused' else source == (ROOT/f['new_run']).resolve()
        assert file_hash(source/'manifest.json') == origin['source_manifest_sha256']
        files = {q.name:file_hash(q) for q in d.iterdir() if q.is_file()}
        assert files == origin['files'] == {q.name:file_hash(q) for q in (source/'records'/gid).iterdir() if q.is_file()}
        assert read_json(d/'input.json') == p and row['members'] == p['members']
        assert read_json(d/'result.json') == row
        request = read_json(d/'request.json')
        assert request == build_request(p, get_terms(), f['model'])
        assert set(request) == {'model','messages','max_completion_tokens','reasoning_effort','response_format'}
        assert request['reasoning_effort']=='low' and request['max_completion_tokens']==8192
        assert request['model']=='gpt-5.4-2026-03-05'
        projection = json.loads(request['messages'][1]['content'])
        assert all(set(m)=={'member_id','summary','central_question'} for m in projection['members'])
        if origin['origin']=='new':
            assert file_hash(d/'input.json') == frozen_requests[gid]['input_sha256']
            assert file_hash(d/'request.json') == frozen_requests[gid]['request_sha256']
        else:
            assert files == f['reused_records_sha256'][gid]
        raw = (d/'analysis.raw.txt').read_text(encoding='utf-8')
        assert export_result(p, parse_response(p, raw), state='CONSOLIDATED') == row
        assert row['inherited_review_obligations'] == export_result(p)['inherited_review_obligations']
        assert row['processing_state']=='CONSOLIDATED' and not row['validation_diagnostics']
        member_ids = [m['member_id'] for m in p['members']]
        partition = [x for t in row['topics'] for x in t['member_ids']] + row['rejected_member_ids'] + row['unassigned_member_ids']
        assert len(partition)==len(set(partition)) and Counter(partition)==Counter(member_ids)
        assert Counter(x['member_id'] for x in row['member_dispositions'])==Counter(member_ids)
        for item in row['member_dispositions']:
            assert item['disposition']=='ASSIGNED'
            assert any(item['topic_id']==t['topic_id'] and item['member_id'] in t['member_ids'] for t in row['topics'])
        dispositions.update(x['disposition'] for x in row['member_dispositions'])
        for topic in row['topics']:
            severity = topic['preliminary_severity']
            assert severity['level']=='UNKNOWN' and severity['assessment_status']=='UNASSESSED'
            assert severity['assessor']=='deterministic_post_export' and severity['rule_version']=='canonical-impact-availability-v1'
            assert severity['rubric_version']=='provisional-operational-severity-v2'
            assert not set(topic)&{'inventory','supported_answers','shared_issue','open_questions','guidance'}
        call = read_json(d/'call.json'); response = read_json(d/'response.json')
        completion = read_json(d/'completion_status.json'); body = read_json(d/'response.raw.bin')
        assert call['attempt']==1 and (d/'started.json').is_file()
        assert response['http_status']==200 and response['failure'] is None
        assert completion['status']=='COMPLETED' and not completion['provider_completion_unknown']
        assert completion['requested_model']==completion['response_model']==request['model']==body['model']
        assert body['choices'][0]['finish_reason']==completion['finish_reason']=='stop'
        assert body['choices'][0]['message']['content']==raw
        assert completion['usage']==body['usage']
        u = completion['usage']
        assert u['total_tokens']==u['prompt_tokens']+u['completion_tokens'] and u['completion_tokens']<=8192
        ledger.append({'candidate_group_id':gid, 'origin':origin['origin'], 'source_run':source.as_posix(),
            'attempt':1, 'outcome':'COMPLETED', 'saved_response':True, 'provider_completion_unknown':False,
            'requested_model':completion['requested_model'],'returned_model':completion['response_model'],
            'finish_reason':completion['finish_reason'], 'latency_seconds':completion['latency_seconds'],
            'usage':u, 'request_sha256':files['request.json'], 'response_sha256':files['response.raw.bin'],
            'completion_sha256':files['completion_status.json'], 'call_sha256':files['call.json']})
        q=projects.setdefault(row['project_id'],dict(groups=0,identities=0,topics=0,inherited_obligations=0))
        q['groups']+=1; q['identities']+=len(row['members']);q['topics']+=len(row['topics']);q['inherited_obligations']+=len(row['inherited_review_obligations'])
    checks.extend([
        'All 90 individual records/aggregates/evidence files match original v7 run bytes; four accepted pilot results reused, no v6 results.',
        'All 86 new inputs and serialized requests exactly match the frozen prepared files; minimal schema 7 projection excludes reviews, raw transcripts and severity.',
        'All 90 raw responses replay to the exact saved export under the accepted parser/validator, without modifying any response.',
        'All 200 assigned dispositions form exact disjoint membership partitions; zero rejected/unassigned/missing/duplicate members.',
        'All 97 topic severities are deterministic UNKNOWN/UNASSESSED with original input provenance; no model severity or regenerated semantic inventory.',
        'Every attempt has one call marker, completed HTTP 200 response, matching raw content/model/usage, finish stop; zero unknown completions or unprocessed groups.',
    ])
    obligations = [o for r in rows for o in r['inherited_review_obligations']]
    assert len(obligations)==len({identity(o) for o in obligations})==49
    assert {identity(o) for o in obligations}=={identity(r) for r in canonical if r['review_required']}
    assert read_json(RUN/'member_review_queue.json') == obligations
    assert read_json(RUN/'review_queue.json') == [r for r in rows if r['review_required']]
    view = load_effective_output(RUN)
    assert view == read_json(RUN/'effective_output_reviewed.json')
    assert not view['unapplied_findings'] and len(view['applied_content_obligations'])==3
    assert view['member_review_queue']==obligations
    assert view['review_queue']==[r for r in view['records'] if r['effective_review_required']]
    assert len(view['review_queue'])==41 and sum(r['review_required'] for r in rows)==40
    for effective, row in zip(view['records'],rows):
        assert effective['members']==row['members'] and effective['inherited_review_obligations']==row['inherited_review_obligations']
        assert effective['processing_state']==row['processing_state']
        assert 'research_handoff' not in effective and effective['taxonomy_handoff']==taxonomy_handoff(effective)
        assert effective['taxonomy_handoff']['nonblocking']
        assert all(o in effective['review_obligations'] for o in row['inherited_review_obligations'])
    review=read_json(HERE/'taxonomy_review.json')
    assert {e['candidate_group_id'] for e in review['entries']}==set(by)
    assert sum(e['fixed_sample'] for e in review['entries'])==8
    assert sum(e['split'] for e in review['entries'])==7
    assert {o['candidate_group_id'] for o in view['applied_content_obligations']}=={e['candidate_group_id'] for e in review['entries'] if e['assisted_content_review_required']}
    checks.append('Both queues and effective taxonomy handoffs agree: 49 unchanged inherited obligations plus three new exact-output naming cautions; no historical v6 findings transplanted.')
    for source in (ROOT/f['reused_run'],ROOT/f['new_run']):
        m=read_json(source/'manifest.json'); saved=read_json(source/'consolidations.json')
        assert digest(m['config'])==m['config_sha256']
        assert len(list((source/'records').glob('*/call.json')))==len(saved)==m['new_request_attempts']
        assert not m['unknown_completion_requests'] and not m['started_without_call_markers'] and m['unprocessed_groups']==0
        assert read_json(source/'review_queue.json')==[r for r in saved if r['review_required']]
        assert read_json(source/'member_review_queue.json')==[o for r in saved for o in r['inherited_review_obligations']]
        # Historical view captures the registry hash at execution; refresh only in memory.
        fresh=load_effective_output(source); previous=read_json(source/'effective_output.json')
        assert {k:v for k,v in fresh.items() if k!='review_registry_sha256'}=={k:v for k,v in previous.items() if k!='review_registry_sha256'}
    assert read_json(ROOT/f['new_run']/'manifest.json')['config']==f['config']
    assert Counter(x['origin'] for x in ledger)=={'new':86,'reused':4}
    assert file_hash(ROOT/f['reused_run']/'manifest.json')==f['reused_manifest_sha256']
    assert manifest['new_request_attempts']==86 and manifest['assembly_model_calls']==0
    checks.append('Independent source-run ledgers/queues/configurations agree; authorized new-request maximum of 86 respected, reused pilot never re-called.')
    summaries = {}
    for kind in ('new','reused','combined'):
        selected=[x for x in ledger if kind=='combined' or x['origin']==kind]
        prompt=sum(x['usage']['prompt_tokens'] for x in selected)
        cached=sum(x['usage']['prompt_tokens_details']['cached_tokens'] for x in selected)
        output=sum(x['usage']['completion_tokens'] for x in selected)
        reasoning=sum(x['usage']['completion_tokens_details']['reasoning_tokens'] for x in selected)
        latency=[x['latency_seconds'] for x in selected]
        summaries[kind]={'attempts':len(selected),'completed_responses':len(selected),'unknown_completions':0,
            'input_tokens':prompt,'cached_input_tokens':cached,'output_tokens_including_reasoning':output,
            'reasoning_tokens_included_in_output':reasoning,'total_tokens':prompt+output,
            'latency_seconds_sum':sum(latency),'latency_seconds_median':statistics.median(latency),
            'latency_seconds_min':min(latency),'latency_seconds_max':max(latency),
            'standard_rate_cost_usd_estimate':round(((prompt-cached)*2.5+cached*0.25+output*15)/1_000_000,8)}
    receipt={'status':'PASS','checked_at':datetime.now(timezone.utc).isoformat(),
        'command':'.venv\\Scripts\\python.exe -X utf8 data/experiments/agent2_taxonomy_final_v7/validate_release.py',
        'method':'Actual saved-artifact audit and deterministic replay; not an additional pytest run or model quality benchmark.',
        'checks':checks,'groups':90,'identities':200,'source_messages':sum(len(m['original_thread']['messages']) for r in rows for m in r['members']),
        'inherited_obligations':49,'inherited_pilot_obligations':3,'inherited_remaining_obligations':46,
        'processing_counts':dict(Counter(r['processing_state'] for r in rows)), 'unprocessed_groups':0,
        'topics':sum(len(r['topics']) for r in rows),'split_groups':7,'dispositions':dict(dispositions),
        'automated_review_groups':40,'effective_review_groups':41,'new_naming_cautions':3,
        'preliminary_severity_counts':dict(Counter(t['preliminary_severity']['level'] for r in rows for t in r['topics'])),
        'by_project':projects,'usage':summaries,
        'pricing_source':f['cost_estimate']['source'],'cost_is_provider_usage_at_published_standard_rates_not_invoice':True,
        'producer_tests_reused':{'receipt':'data/experiments/agent2_taxonomy_v7/validation.json','sha256':f['previous_test_receipt_sha256'],
            'agent2_related_passed':294,'agent2_related_failed':0,'single_green_full_suite':False},
        'producer_code_changed':False,'assembly_export_code_changed':False,'new_test_runs':0,
        'additional_model_calls_for_review_assembly_validation':0}
    write_json(HERE/'request_ledger.json',{'entries':ledger,'totals':summaries},exclusive=True)
    write_json(HERE/'validation.json',receipt,exclusive=True)
    write_json(RUN/'effective_review_queue.json',view['review_queue'],exclusive=True)
    release={'release_version':1,'state':'complete_with_review','agent2_milestone':'closed_taxonomy_only',
        'decision':'Full accounting passes; no obvious consequential membership defect found; three naming cautions remain nonblocking and all inherited flags persist.',
        'canonical_file':'consolidations.json','canonical_sha256':file_hash(RUN/'consolidations.json'),
        'assembly_manifest':'manifest.json','assembly_manifest_sha256':file_hash(RUN/'manifest.json'),
        'current_effective_file':'effective_output_reviewed.json','current_effective_sha256':file_hash(RUN/'effective_output_reviewed.json'),
        'effective_review_queue_file':'effective_review_queue.json','effective_review_queue_sha256':file_hash(RUN/'effective_review_queue.json'),
        'member_review_queue_file':'member_review_queue.json','member_review_queue_sha256':file_hash(RUN/'member_review_queue.json'),
        'automated_review_queue_file':'review_queue.json','automated_review_queue_sha256':file_hash(RUN/'review_queue.json'),
        'review_registry':REGISTRY.relative_to(ROOT).as_posix(),'review_registry_sha256':file_hash(REGISTRY),
        'taxonomy_review':(HERE/'taxonomy_review.json').relative_to(ROOT).as_posix(),'taxonomy_review_sha256':file_hash(HERE/'taxonomy_review.json'),
        'validation':(HERE/'validation.json').relative_to(ROOT).as_posix(),'validation_sha256':file_hash(HERE/'validation.json'),
        'request_ledger':(HERE/'request_ledger.json').relative_to(ROOT).as_posix(),'request_ledger_sha256':file_hash(HERE/'request_ledger.json'),
        'handoff_contract':'agent2-taxonomy-handoff-v1','nonblocking':True,
        'groups':90,'identities':200,'topics':97,'inherited_obligations':49,'naming_cautions':3,
        'automated_review_groups':40,'effective_review_groups':41,
        'snapshot_note':'effective_output.json and manifest.json preserve the assembly-time view (40 review groups). The current reviewed view adds three bound naming cautions (41 review groups), without rewriting automated records.'}
    write_json(RUN/'release_manifest.json',release,exclusive=True)
    print(json.dumps({k:receipt[k] for k in ('status','groups','identities','source_messages','topics','dispositions','effective_review_groups','usage','by_project')},indent=2))


if __name__=='__main__':main()
