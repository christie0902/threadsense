"""Frozen six-by-two comparison preparation and bounded, explicitly invoked execution."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from threadsense.legacy.agent2.topic_consolidation_v6 import build_request, PROMPT_VERSION
from threadsense.agents import topic_pipeline
from threadsense.agents.topic_pipeline import execute_batch, configuration, write_json
from threadsense.agents.topic_requests import BASELINE_MODEL, COMPARISON_MODEL, MAX_COMPLETION_TOKENS
from threadsense.handoff_inputs import ROOT, read_json, file_hash, digest, identity
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.terminology import get_terms

MODELS = {'A': BASELINE_MODEL, 'B': COMPARISON_MODEL}
SOURCE_RUN = ROOT / 'data/processed/agent2_inventory_pilot_v4'
SOURCE_SELECTION = ROOT / 'docs/agent2-inventory-pilot-v4.json'
CONTROLLER_FILES = ('src/threadsense/legacy/agent2/topic_comparison.py', 'scripts/run_agent2_comparison.py')
DOCS = {
    'structured_outputs': 'https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat',
    'chat_parameters': 'https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create',
    'gpt54_parameters': 'https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.4',
    'arm_a_pricing': 'https://developers.openai.com/api/docs/models/gpt-4o-mini',
    'arm_b_pricing': 'https://developers.openai.com/api/docs/models/gpt-5.4',
}
MEASURES = {
    'schema_acceptance': 'Record provider refusal/incompletion separately; validate response shape under v5 without repair.',
    'source_accounting': 'Every source message has items or an explicit disposition; every member has substantive inventory; list exact omissions.',
    'questions': 'Source-review actual handling questions, status and same-thread answer links; diagnostics/context cannot substitute.',
    'guidance': 'Retain all scoped TL/endorsed instructions, tentative advice and conditions; announcement/root/reply roles remain distinct.',
    'unsupported_claims': 'List each unsupported synthesis/difference/impact with exact source evidence and affected fields.',
    'severity': 'Assess operational criterion, actual scope and reported versus observed evidence independently of flags; unknown/unassessed remains visible.',
    'review_preservation': 'All five inherited obligations and applicable new content findings survive; HIGH is nonblocking.',
    'latency': 'Use completion_status.json elapsed wall seconds; missing/old latency is unknown, never zero.',
    'token_usage': 'Use provider usage: input, cached input, completion and reasoning tokens; distinguish estimates from billed usage.',
}


def selected_payloads():
    selection = read_json(SOURCE_SELECTION)
    ids = [c['candidate_group_id'] for c in selection['cases']]
    if len(ids) != len(set(ids)) or len(ids) != 6:
        raise ValueError('Comparison requires exactly the same six unique pilot groups.')
    all_payloads = {p['candidate_group_id']: p for p in load_candidate_payloads()}
    chosen = [all_payloads[gid] for gid in ids]
    for p in chosen:
        if p != read_json(SOURCE_RUN/'records'/p['candidate_group_id']/'input.json'):
            raise ValueError('Comparison source differs from the completed v4 run.')
    if len({identity(m) for p in chosen for m in p['members']}) != 18 or sum(
            m['agent1_record']['review_required'] for p in chosen for m in p['members']) != 5:
        raise ValueError('Comparison membership/review coverage changed.')
    return chosen


def controller_hashes():
    return {p: file_hash(ROOT/p) for p in CONTROLLER_FILES}


def prepare_comparison(experiment):
    if topic_pipeline.RESPONSE_SCHEMA_VERSION != 6:
        raise ValueError('Historical semantic comparison is inactive under taxonomy v7; use the current prepared pilot.')
    experiment = Path(experiment).resolve()
    if experiment.exists():
        raise FileExistsError('Use a new comparison directory; preserve all previous freezes.')
    selected = selected_payloads()
    requests = {arm: [build_request(p, get_terms(), model) for p in selected] for arm, model in MODELS.items()}
    for a, b in zip(requests['A'], requests['B']):
        if a['messages'] != b['messages'] or a['response_format'] != b['response_format']:
            raise ValueError('Both arms must have identical semantic instructions, sources and schema.')
    arms = {}
    for arm, model in MODELS.items():
        prepared = experiment/'prepared'/arm
        manifest = execute_batch(selected, prepared, run=False, maximum_requests=6, model_override=model)
        arms[arm] = {'model': model, 'maximum_requests': 6, 'config': manifest['config'],
            'config_sha256': manifest['config_sha256'], 'prepared_dir': f'prepared/{arm}',
            'run_dir': f'runs/{arm}', 'requests': [
                {'candidate_group_id': p['candidate_group_id'],
                 'request_sha256': file_hash(prepared/'records'/p['candidate_group_id']/'request.json'),
                 'input_sha256': file_hash(prepared/'records'/p['candidate_group_id']/'input.json')}
                for p in selected]}
    # Estimates are deliberately local and avoid API token-count/probe calls.
    import json
    input_estimate = sum(len(json.dumps({'messages':r['messages'], 'response_format':r['response_format']},
                                      ensure_ascii=False))/4 + 32 for r in requests['A'])
    rates = {'A': {'input_per_million':0.15, 'output_per_million':0.60},
             'B': {'input_per_million':2.50, 'output_per_million':15.00}}
    costs = {}
    for arm, rate in rates.items():
        costs[arm] = {**rate, 'estimated_input_tokens':round(input_estimate),
            'assumed_output_tokens':12000,
            'estimated_usd':round((input_estimate*rate['input_per_million']+12000*rate['output_per_million'])/1e6, 4),
            'at_output_limit_usd_with_estimated_input':round((input_estimate*rate['input_per_million']+
                6*MAX_COMPLETION_TOKENS*rate['output_per_million'])/1e6, 4)}
    freeze = {'experiment_version':1,'prepared_at':datetime.now(ZoneInfo('America/New_York')).isoformat(),
        'state':'prepared_not_executed','prompt_version':PROMPT_VERSION,'response_schema_version':5,
        'rubric_version':arms['B']['config']['rubric_version'],
        'source_run':SOURCE_RUN.relative_to(ROOT).as_posix(),
        'source_manifest_sha256':file_hash(SOURCE_RUN/'manifest.json'),
        'source_selection_sha256':file_hash(SOURCE_SELECTION),
        'selected_groups':[p['candidate_group_id'] for p in selected],
        'identities':18,'inherited_obligations':5,'maximum_new_requests_total':12,
        'requests_per_group_per_arm':1,'retries':0,'repairs':0,'fallback_calls':0,'extra_verifiers':0,
        'controller_sha256':controller_hashes(),'arms':arms,
        'parameter_differences':{'model':'Both explicitly pinned; A matches the observed v4 response snapshot.',
            'reasoning_effort':'A: not applicable/omitted; B: none explicitly.',
            'temperature':'0 for both; documented as supported on GPT-5.4 with reasoning none.',
            'token_limit':'max_completion_tokens=8192 for both; includes reasoning and visible tokens; deprecated max_tokens omitted.',
            'verbosity':'Provider default, no arm-specific style instruction.'},
        'measures':MEASURES,'source_review_required_before_model_selection':True,
        'not_an_unbiased_accuracy_benchmark':True,
        'official_sources':DOCS,'documentation_checked_date':'2026-10-24',
        'cost_estimates':{'arms':costs,'estimated_total_usd':round(sum(c['estimated_usd'] for c in costs.values()),4),
            'at_output_limit_total_usd_with_estimated_input':round(sum(c['at_output_limit_usd_with_estimated_input'] for c in costs.values()),4),
            'method':'Local characters/4 +32 per request estimate, 2000 completion tokens/group scenario; uncached standard USD prices. Not exact token counts or a billing cap.',
            'account_access':'Not probed; unsupported model/schema errors stop that arm without fallback.'}}
    write_json(experiment/'freeze.json', freeze, exclusive=True)
    write_json(experiment/'freeze_receipt.json', {'freeze_sha256':file_hash(experiment/'freeze.json')}, exclusive=True)
    write_json(experiment/'source_review_template.json', {'origin':'pending_assisted_source_review_not_model_input',
        'model_selection':None,'cases':[{'arm':arm,'candidate_group_id':p['candidate_group_id'],
            'source_output_bindings':None,'findings':[],**{key:None for key in MEASURES}} for arm in MODELS for p in selected]}, exclusive=True)
    return freeze


def preflight_comparison(experiment):
    if topic_pipeline.RESPONSE_SCHEMA_VERSION != 6:
        raise ValueError('Historical semantic comparison is inactive under taxonomy v7; preserve its original artifacts.')
    experiment = Path(experiment).resolve()
    freeze = read_json(experiment/'freeze.json')
    if read_json(experiment/'freeze_receipt.json')['freeze_sha256'] != file_hash(experiment/'freeze.json'):
        raise ValueError('Comparison freeze changed.')
    selected = selected_payloads()
    if (freeze['controller_sha256'] != controller_hashes()
            or freeze['source_manifest_sha256'] != file_hash(SOURCE_RUN/'manifest.json')
            or freeze['source_selection_sha256'] != file_hash(SOURCE_SELECTION)
            or freeze['selected_groups'] != [p['candidate_group_id'] for p in selected]
            or freeze['maximum_new_requests_total'] != 12):
        raise ValueError('Comparison code, selection or source fingerprint changed.')
    for arm, model in MODELS.items():
        record = freeze['arms'][arm]
        config = configuration(selected, model)
        if record['model'] != model or record['config'] != config or record['config_sha256'] != digest(config):
            raise ValueError('Frozen arm configuration no longer matches current code.')
        if record['maximum_requests'] != 6 or record['prepared_dir'] != f'prepared/{arm}' or record['run_dir'] != f'runs/{arm}':
            raise ValueError('Arm paths/budget changed.')
        for p, saved in zip(selected, record['requests']):
            d = experiment/record['prepared_dir']/'records'/p['candidate_group_id']
            if (saved['candidate_group_id'] != p['candidate_group_id'] or
                    file_hash(d/'request.json') != saved['request_sha256'] or
                    file_hash(d/'input.json') != saved['input_sha256'] or read_json(d/'input.json') != p or
                    read_json(d/'request.json') != build_request(p,get_terms(),model)):
                raise ValueError('Frozen request/input changed; no execution allowed.')
        if len(record['requests']) != 6:
            raise ValueError('Incomplete frozen arm.')
    return freeze, selected


def run_arm(experiment, arm, maximum_requests):
    """Only called by explicit --run. Fixed fresh paths prevent repeats/unknown retries."""
    freeze, selected = preflight_comparison(experiment)
    if arm not in MODELS or maximum_requests != 6:
        raise ValueError('Select arm A/B and exactly --max-requests 6.')
    target = Path(experiment)/freeze['arms'][arm]['run_dir']
    return execute_batch(selected, target, run=True, maximum_requests=6, model_override=MODELS[arm])
