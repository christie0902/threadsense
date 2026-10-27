"""One-off v7 milestone receipt builder. Zero calls; refuses existing destinations.

Synthetic response exports validate wiring only. Selection uses canonical summaries,
never hidden evaluation labels, source re-interpretation or previous model answers.
"""
from collections import Counter
import json
import math
import os
from pathlib import Path
import runpy

from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.agents.topic_consolidation import build_request, parse_response, export_result
from threadsense.agents.topic_diagnostics import describe_exception
from threadsense.handoff_inputs import ROOT, CANONICAL, GROUPING, IDENTITY, digest, file_hash, identity
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.terminology import get_terms

EXPERIMENT = Path(__file__).resolve().parent
PREVIEW = ROOT/'data/processed/agent2_taxonomy_v7_offline'
PREPARED = ROOT/'data/processed/agent2_taxonomy_pilot_v7_prepared'
FUTURE_RUN = ROOT/'data/processed/agent2_taxonomy_pilot_v7'
PILOT = ROOT/'docs/agent2-taxonomy-pilot-v7.json'
MODEL = 'openai/gpt-5.4-2026-03-05'
SELECTION = [
    ('cluster_bc1ccc03c19a64cf', 'Coherence: two canonical interpretations about overlapping speakers.'),
    ('cluster_b3bfce178039d7d4', 'Split/outlier opportunity: calibration scheduling and queue assignments are distinct announcements. No mandatory expected partition.'),
    ('cluster_6b59d13144282285', 'Flagged mixed playback/silence interpretations; preserve both inherited disputes without reinterpretation.'),
    ('cluster_be4e3bac742eccb3', 'Non-operational singleton: friendly language-day greetings; no manufactured question.'),
]


def forbidden(*args, **kwargs):
    raise AssertionError('This preparation is offline; credentials and live API calls are prohibited.')


def write(path, data):
    pipeline.write_json(path, data, exclusive=True)


def main():
    assert not FUTURE_RUN.exists()
    for p in (PREVIEW, PREPARED, PILOT, EXPERIMENT/'freeze.json', EXPERIMENT/'synthetic_exports'):
        if p.exists(): raise FileExistsError(f'Preserve existing artifacts: {p}')
    os.environ['THREADSENSE_MODEL'] = MODEL
    os.environ['THREADSENSE_AGENT2_REASONING_EFFORT'] = 'low'
    pipeline.config.get_api_key = forbidden
    transport.send_once = transport.complete_once = forbidden
    payloads = load_candidate_payloads()
    ids = {p['candidate_group_id']:p for p in payloads}
    selected = [ids[gid] for gid, _ in SELECTION]
    preview = pipeline.execute_batch(payloads, PREVIEW, run=False, maximum_requests=90)
    prepared = pipeline.execute_batch(selected, PREPARED, run=False, maximum_requests=4)
    pilot = {'schema_version':2, 'response_schema_version':7,
        'origin':'OFFLINE_PREPARED_TAXONOMY_PILOT_NOT_EXECUTED_NOT_LIVE_AUTHORIZATION',
        'model':MODEL, 'canonical_sha256':file_hash(CANONICAL), 'grouping_sha256':file_hash(GROUPING),
        'maximum_request_attempts':4, 'requests_per_group':1, 'automatic_retries':0,
        'repairs':0, 'additional_verifier_calls':0, 'configuration_sha256':prepared['config_sha256'],
        'cases':[{'case_id':f'case_{i+1:02}', 'candidate_group_id':p['candidate_group_id'],
            'anchor_thread_id':p['members'][0]['thread_id'],
            'member_identities':[{k:m[k] for k in IDENTITY} for m in p['members']],
            'source_message_count':sum(len(m['original_thread']['messages']) for m in p['members']),
            'inherited_review_count':sum(m['agent1_record']['review_required'] for m in p['members'])}
            for i,p in enumerate(selected)]}
    write(PILOT, pilot)
    select = runpy.run_path(str(ROOT/'scripts/run_agent2_batch.py'))['select_pilot']
    checked, bound = select(payloads, PILOT, MODEL)
    assert checked == selected and bound == 4

    # Deliberate synthetic partition failure and rejection of flagged members.
    flagged = [p for p in payloads if any(m['agent1_record']['review_required'] for m in p['members'])]
    failed_gid, rejected_gid = [p['candidate_group_id'] for p in flagged[:2]]
    synthetic = EXPERIMENT/'synthetic_exports'
    rows=[]
    for p in payloads:
        gid=p['candidate_group_id']; mids=[m['member_id'] for m in p['members']]
        d={'topics':[{'topic_name':'Synthetic grouping (offline wiring only)',
            'rationale':'Synthetic assignment exercises structural export, not grouping quality.',
            'member_ids':mids}], 'rejected_member_ids':[]}
        if gid == failed_gid: d={'topics':[], 'rejected_member_ids':[]}
        elif gid == rejected_gid: d={'topics':[], 'rejected_member_ids':mids}
        directory=synthetic/'records'/gid
        write(directory/'input.json',p)
        write(directory/'request.json',build_request(p,get_terms(),MODEL))
        raw=json.dumps(d,ensure_ascii=False)
        pipeline.write_bytes(directory/'analysis.raw.txt',raw.encode('utf-8'),exclusive=True)
        try:
            row=export_result(p,parse_response(p,raw),state='CONSOLIDATED')
        except ValueError as error:
            details=describe_exception(p,error)
            row=export_result(p,state='FAILED',error='Synthetic missing-member response, intentionally invalid.',diagnostics=details)
            write(directory/'diagnostics.json',details)
        write(directory/'SYNTHETIC.json',{'origin':'SYNTHETIC_OFFLINE_WIRING_ONLY','model_calls':0})
        write(directory/'result.json',row)
        rows.append(row)
    manifest=pipeline.reports(synthetic,payloads,rows,pipeline.configuration(payloads,MODEL),'synthetic_offline_validation_not_live')
    manifest.update(artifact_origin='SYNTHETIC_OFFLINE_WIRING_ONLY', model_calls=0,
                    intentionally_failed_group=failed_gid, intentionally_rejected_group=rejected_gid)
    pipeline.write_json(synthetic/'manifest.json',manifest)
    assert sum(len(r['members']) for r in rows)==200
    assert sum(len(r['inherited_review_obligations']) for r in rows)==49

    # Local cached tokenizer only; no token-count API or tokenizer download.
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'.cache/tiktoken')
    assert (ROOT/'.cache/tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790').exists()
    import tiktoken
    enc=tiktoken.get_encoding('o200k_base')
    request_receipts=[]
    for p in selected:
        directory=PREPARED/'records'/p['candidate_group_id']
        request=json.loads((directory/'request.json').read_text(encoding='utf-8'))
        token_text=json.dumps({k:request[k] for k in ('messages','response_format')},ensure_ascii=False)
        local=len(enc.encode(token_text)); budget=math.ceil(local*1.2)+512
        request_receipts.append({'candidate_group_id':p['candidate_group_id'],
            'input_sha256':file_hash(directory/'input.json'),'request_sha256':file_hash(directory/'request.json'),
            'local_serialized_input_tokens':local,'budgeted_input_tokens':budget,
            'maximum_completion_tokens':request['max_completion_tokens']})
    token_input=sum(r['budgeted_input_tokens'] for r in request_receipts)
    pricing={'input_usd_per_million':2.5,'output_usd_per_million':15,
        'cached_input_usd_per_million':0.25,'cache_assumption':'No cache discount assumed',
        'source':'https://developers.openai.com/api/docs/models/gpt-5.4','checked_date':'2026-10-26',
        'estimated_input_tokens':token_input, 'scenario_output_tokens':4*1000,
        'scenario_usd':round((token_input*2.5+4*1000*15)/1e6,4),
        'at_output_limit_usd_with_estimated_input':round((token_input*2.5+4*8192*15)/1e6,4),
        'method':'Cached o200k_base on serialized messages/schema +20% and 512 overhead tokens per request; approximate USD standard-tier estimate, not a billing cap. Reasoning and visible tokens share output budget.'}
    freeze={'experiment_version':1,'state':'prepared_no_calls','response_schema_version':7,
        'selection_basis':'Canonical Agent 1 summaries/questions only; no hidden labels or new source interpretation.',
        'live_execution_authorized':False,'maximum_new_requests':4,'requests_per_group':1,
        'retries':0,'repairs':0,'fallback_calls':0,'additional_verifiers':0,
        'config':prepared['config'],'configuration_sha256':prepared['config_sha256'],
        'canonical_sha256':file_hash(CANONICAL),'grouping_sha256':file_hash(GROUPING),
        'pilot_path':PILOT.relative_to(ROOT).as_posix(),'pilot_sha256':file_hash(PILOT),
        'prepared_directory':PREPARED.relative_to(ROOT).as_posix(),
        'fresh_live_destination':FUTURE_RUN.relative_to(ROOT).as_posix(),
        'preview_directory':PREVIEW.relative_to(ROOT).as_posix(),
        'selected_identities':prepared['retained_input_identities'],
        'selected_inherited_obligations':prepared['inherited_review_obligations'],
        'requests':request_receipts,'pricing':pricing,'preparer_sha256':file_hash(__file__)}
    write(EXPERIMENT/'freeze.json',freeze)
    write(EXPERIMENT/'freeze_receipt.json',{'freeze_sha256':file_hash(EXPERIMENT/'freeze.json')})
    write(EXPERIMENT/'selection_review.json',{'origin':'ASSISTED_OFFLINE_SELECTION_REVIEW_NOT_MODEL_INPUT',
        'not_semantic_approval':True,'cases':[{'candidate_group_id':gid,'reason':reason} for gid,reason in SELECTION]})
    write(EXPERIMENT/'request_ledger.json',{'state':'prepared_not_executed','new_paid_attempts':0,
        'saved_provider_responses':0,'unknown_completions':0,'maximum_future_attempts':4,
        'cases':[{'candidate_group_id':gid,'attempts':0,'status':'NOT_RUN'} for gid,_ in SELECTION],
        'live_ledger_location':'Future run records/*/started.json, call.json, response.json, completion_status.json; original attempt evidence is never overwritten.'})
    write(EXPERIMENT/'coverage_receipt.json',{
        'origin':'OFFLINE_STRUCTURE_ONLY_NOT_GROUPING_ACCURACY',
        'preview':{k:preview[k] for k in ('selected_groups','retained_input_identities','inherited_review_obligations','processing_counts','member_disposition_counts','new_request_attempts')},
        'synthetic':{k:manifest[k] for k in ('processing_counts','member_disposition_counts','inherited_review_obligations','new_request_attempts')},
        'synthetic_inherited_by_disposition':dict(Counter(d['disposition'] for r in rows for d in r['member_dispositions']
            if next(m for m in r['members'] if m['member_id']==d['member_id'])['agent1_record']['review_required'])),
        'all_full_identities_preserved':{identity(m) for r in rows for m in r['members']}=={identity(m) for p in payloads for m in p['members']},
        'synthetic_failed_group':failed_gid,'synthetic_rejected_group':rejected_gid})
    for path in (PREVIEW,PREPARED,synthetic):
        assert not list(path.rglob('call.json')) and not list(path.rglob('response.json'))
    print(json.dumps({'preview_groups':len(payloads),'members':200,'obligations':49,
        'pilot_identities':prepared['retained_input_identities'], 'pilot_obligations':prepared['inherited_review_obligations'],
        'synthetic_dispositions':manifest['member_disposition_counts'],'cost_estimate':pricing},indent=2))


if __name__ == '__main__':
    main()
