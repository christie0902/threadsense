"""Zero-call preflight for the authorized remaining 86 taxonomy groups.

One-off milestone receipt builder, using the unchanged loader/runner/selection.
Never dispatches a model request; fails on incompatible pilot or existing paths.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import runpy

from threadsense.handoff_inputs import ROOT, CANONICAL, GROUPING, IDENTITY, read_json, file_hash, digest, identity
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.agents.topic_consolidation import build_request, parse_response, export_result
from threadsense.agents.topic_effective import load_effective_output
from threadsense.terminology import get_terms

HERE=Path(__file__).resolve().parent
PILOT=ROOT/'data/processed/agent2_taxonomy_pilot_v7'
PREPARED=ROOT/'data/processed/agent2_taxonomy_remaining_v7_prepared'
NEW_RUN=ROOT/'data/processed/agent2_taxonomy_remaining_v7'
FINAL=ROOT/'data/processed/agent2_taxonomy_final_v7'
SELECTION=ROOT/'docs/agent2-taxonomy-remaining-v7.json'


def write(path, data):
    pipeline.write_json(path,data,exclusive=True)


def no_calls(*args, **kwargs):
    raise AssertionError('Preflight cannot make model calls.')


def main():
    for path in (HERE/'freeze.json', PREPARED, NEW_RUN, FINAL, SELECTION):
        if path.exists():raise FileExistsError(f'Preserve existing artifacts: {path}')
    transport.send_once=transport.complete_once=no_calls
    before={}
    for folder in ('src','scripts','tests','docs','data'):
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts or p.is_relative_to(HERE) or p.is_relative_to(ROOT/'data/evaluation'):
                continue
            before[p.relative_to(ROOT).as_posix()]=file_hash(p)
    for name in ('README.md','pyproject.toml','uv.lock','requirements.txt','.env'):
        before[name]=file_hash(ROOT/name)
    write(HERE/'before.json',before)
    old=read_json(PILOT/'manifest.json'); model=old['config']['model']
    os.environ['THREADSENSE_MODEL']=model
    os.environ['THREADSENSE_AGENT2_REASONING_EFFORT']=old['config']['request_parameters']['reasoning_effort']
    all_payloads=load_candidate_payloads(); by={p['candidate_group_id']:p for p in all_payloads}
    rows=read_json(PILOT/'consolidations.json')
    gids=[r['candidate_group_id'] for r in rows]
    assert len(gids)==len(set(gids))==4
    selected=[by[g] for g in gids]
    assert old['config']==pipeline.configuration(selected,model)
    assert old['config_sha256']==digest(old['config'])
    assert old['processing_counts']=={'CONSOLIDATED':4} and old['unprocessed_groups']==0
    assert (old['retained_input_identities'],old['inherited_review_obligations'])==(11,3)
    assert old['new_request_attempts']==old['available_response_records']==4
    assert not old['unknown_completion_requests'] and not old['started_without_call_markers']
    assert sum(len(r['topics']) for r in rows)==5
    assert sum(len(m['original_thread']['messages']) for r in rows for m in r['members'])==30
    pilot_files={}
    for p,r in zip(selected,rows):
        d=PILOT/'records'/p['candidate_group_id']
        assert read_json(d/'input.json')==p
        assert read_json(d/'request.json')==build_request(p,get_terms(),model)
        assert read_json(d/'result.json')==r
        raw=(d/'analysis.raw.txt').read_text(encoding='utf-8')
        assert export_result(p,parse_response(p,raw),state='CONSOLIDATED')==r
        http=read_json(d/'response.json'); response=read_json(d/'response.raw.bin')
        status=read_json(d/'completion_status.json'); call=read_json(d/'call.json')
        assert call['attempt']==1 and http['http_status']==200 and not http['failure']
        assert response['choices'][0]['message']['content']==raw
        assert response['choices'][0]['finish_reason']=='stop'
        assert status['status']=='COMPLETED' and not status['provider_completion_unknown']
        assert status['requested_model']==status['response_model']==model.split('/',1)[1]
        pilot_files[p['candidate_group_id']]={f.name:file_hash(f) for f in d.iterdir() if f.is_file()}
    pilot_view=load_effective_output(PILOT)
    assert pilot_view==read_json(PILOT/'effective_output.json')
    assert not pilot_view['unapplied_findings']
    assert read_json(PILOT/'review_queue.json')==[r for r in rows if r['review_required']]
    assert read_json(PILOT/'member_review_queue.json')==pilot_view['member_review_queue']
    assert len(pilot_view['member_review_queue'])==3
    remaining=[p for p in all_payloads if p['candidate_group_id'] not in gids]
    assert len(remaining)==86 and sum(len(p['members']) for p in remaining)==189
    assert sum(m['agent1_record']['review_required'] for p in remaining for m in p['members'])==46
    assert len({identity(m) for p in all_payloads for m in p['members']})==200
    # Fixed sample is selected BEFORE new results: largest remaining candidate and
    # a flagged remaining candidate in each project, stable ID tie-breaks; never labels.
    sample=[]
    for project in sorted({p['project_id'] for p in remaining}):
        candidates=sorted([p for p in remaining if p['project_id']==project],key=lambda p:(-len(p['members']),p['candidate_group_id']))
        largest=candidates[0]; sample.append(largest['candidate_group_id'])
        flagged=next((p for p in candidates if p['candidate_group_id']!=largest['candidate_group_id'] and any(m['agent1_record']['review_required'] for m in p['members'])),None)
        sample.append((flagged or candidates[1])['candidate_group_id'])
    write(HERE/'review_selection.json',{'origin':'FIXED_BEFORE_NEW_OUTPUTS_NOT_MODEL_INPUT',
        'scope':'Taxonomy against canonical summaries/questions only; rationales are grouping metadata, not guidance.',
        'selection_rule':'Largest and separate flagged candidate per project, stable group-ID ties. Review all splits/rejections/failures additionally.',
        'fixed_group_ids':sample,'project_by_group':{g:by[g]['project_id'] for g in sample},
        'input_hashes':{g:digest(by[g]) for g in sample},'pilot_groups':gids})
    prepared=pipeline.execute_batch(remaining,PREPARED,run=False,maximum_requests=86)
    assert {k:v for k,v in prepared['config'].items() if k!='payload_sha256'}=={k:v for k,v in old['config'].items() if k!='payload_sha256'}
    selection={'schema_version':2,'response_schema_version':7,'model':model,
        'origin':'USER_AUTHORIZED_REMAINING_86_GROUPS_AFTER_ACCEPTED_V7_PILOT',
        'canonical_sha256':file_hash(CANONICAL),'grouping_sha256':file_hash(GROUPING),
        'configuration_sha256':prepared['config_sha256'],'maximum_request_attempts':86,
        'requests_per_group':1,'automatic_retries':0,'repairs':0,'additional_verifier_calls':0,
        'cases':[{'candidate_group_id':p['candidate_group_id'],'anchor_thread_id':p['members'][0]['thread_id'],
            'member_identities':[{k:m[k] for k in IDENTITY} for m in p['members']],
            'inherited_review_count':sum(m['agent1_record']['review_required'] for m in p['members'])} for p in remaining]}
    write(SELECTION,selection)
    select=runpy.run_path(str(ROOT/'scripts/run_agent2_batch.py'))['select_pilot']
    chosen,bound=select(all_payloads,SELECTION,model)
    assert chosen==remaining and bound==86
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'.cache/tiktoken')
    assert (ROOT/'.cache/tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790').exists()
    import tiktoken
    encoding=tiktoken.get_encoding('o200k_base')
    requests=[]
    for p in remaining:
        d=PREPARED/'records'/p['candidate_group_id'];request=read_json(d/'request.json')
        tokens=len(encoding.encode(json.dumps({k:request[k] for k in ('messages','response_format')},ensure_ascii=False)))
        assert request['max_completion_tokens']==8192 and request['reasoning_effort']=='low'
        assert not set(request)&{'temperature','top_p','logprobs'}
        requests.append({'candidate_group_id':p['candidate_group_id'],'input_sha256':file_hash(d/'input.json'),
            'request_sha256':file_hash(d/'request.json'),'serialized_input_tokens':tokens,'estimated_input_tokens':math.ceil(tokens*1.2)+512})
    input_tokens=sum(r['estimated_input_tokens'] for r in requests)
    cost={'input_tokens_estimate':input_tokens,'input_usd_per_million':2.5,'cached_input_usd_per_million':0.25,
        'output_usd_per_million':15,'scenario_completion_tokens':86*1000,'maximum_completion_tokens':86*8192,
        'scenario_usd':round((input_tokens*2.5+86*1000*15)/1e6,6),
        'at_max_output_with_estimated_input_usd':round((input_tokens*2.5+86*8192*15)/1e6,6),
        'method':'Cached o200k_base serialized messages/schema +20% +512/request; standard USD, uncached input estimate; reasoning included in output, not added again; not a billing cap.',
        'source':'https://developers.openai.com/api/docs/models/gpt-5.4','checked_date':'2026-10-26',
        'spending_controls':'86 new attempts maximum, one/group, 8192 completion tokens each; no retries, repairs, fallback or verifier. No additional local USD cap found in project code/docs/config. Provider billing limits are unchanged and were not probed or raised.'}
    freeze={'version':1,'prepared_at':datetime.now(timezone.utc).isoformat(),
        'authorization':'Current user milestone: at most 86 new requests on remaining groups; reuse accepted four without calls.',
        'model':model,'reused_run':PILOT.relative_to(ROOT).as_posix(),'reused_manifest_sha256':file_hash(PILOT/'manifest.json'),
        'reused_configuration_sha256':old['config_sha256'],'reused_records_sha256':pilot_files,
        'prepared_run':PREPARED.relative_to(ROOT).as_posix(),'new_run':NEW_RUN.relative_to(ROOT).as_posix(),
        'final_dataset':FINAL.relative_to(ROOT).as_posix(),'selection_file':SELECTION.relative_to(ROOT).as_posix(),
        'selection_sha256':file_hash(SELECTION),'config':prepared['config'],'config_sha256':prepared['config_sha256'],
        'canonical_sha256':file_hash(CANONICAL),'grouping_sha256':file_hash(GROUPING),
        'remaining_groups':86,'remaining_identities':189,'remaining_obligations':46,
        'maximum_new_request_attempts':86,'reused_attempts':4,'requests':requests,'cost_estimate':cost,
        'assembly_script_sha256':file_hash(ROOT/'scripts/assemble_agent2_dataset.py'),
        'previous_test_receipt_sha256':file_hash(ROOT/'data/experiments/agent2_taxonomy_v7/validation.json'),
        'preparer_sha256':file_hash(__file__)}
    write(HERE/'freeze.json',freeze)
    write(HERE/'freeze_receipt.json',{'freeze_sha256':file_hash(HERE/'freeze.json')})
    write(HERE/'preflight.json',{'status':'PASS','pilot_groups':4,'pilot_identities':11,'pilot_source_messages':30,
        'pilot_inherited_obligations':3,'pilot_topics':5,'pilot_calls':4,'pilot_saved_responses':4,
        'pilot_unknown_completions':0,'remaining_groups':86,'remaining_identities':189,'remaining_obligations':46,
        'exact_producer_config_match':True,'exact_pilot_inputs_requests_results_match':True,
        'remaining_requests_prepared':86,'new_calls_so_far':0,'cost_estimate':cost})
    print(json.dumps({'preflight':'PASS','remaining_groups':86,'identities':189,'obligations':46,'cost':cost,'fixed_review_groups':sample},indent=2))


if __name__=='__main__':main()
