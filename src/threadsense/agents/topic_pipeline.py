"""Bounded, nonblocking Agent 2 processing and evidence retention.

One request per candidate, deterministic validation, no repair/retry/verifier calls.
Existing output directories are never resumed or silently overwritten.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from threadsense import config
from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_requests import complete_once as complete_topic_once, model_parameters, response_format
from threadsense.agents.topic_consolidation import (
    build_request, parse_response, export_result, PROMPT_VERSION, EXPORT_ADAPTER_VERSION, RUBRIC_VERSION, RESPONSE_SCHEMA_VERSION,
)
from threadsense.agents.topic_diagnostics import describe_exception
from threadsense.agents.topic_effective import load_effective_output
from threadsense.handoff_inputs import ROOT, digest, file_hash, identity
from threadsense.terminology import get_terms

CODE_FILES = (
    'src/threadsense/handoff_inputs.py', 'src/threadsense/topic_inputs.py',
    'src/threadsense/topic_grouping.py', 'scripts/run_thread_grouping.py',
    'src/threadsense/agents/topic_contracts.py', 'src/threadsense/agents/topic_consolidation.py',
    'src/threadsense/agents/topic_taxonomy.py', 'src/threadsense/legacy/agent2/topic_consolidation_v6.py',
    'src/threadsense/legacy/agent2/topic_contracts_v5.py',
    'src/threadsense/legacy/agent2/topic_contracts_v6.py',
    'src/threadsense/legacy/agent2/topic_contracts_v2.py',
    'src/threadsense/legacy/agent2/topic_contracts_v3.py',
    'src/threadsense/legacy/agent2/topic_contracts_v4.py',
    'src/threadsense/legacy/agent2/topic_consolidation_v2.py',
    'src/threadsense/legacy/agent2/topic_consolidation_v3.py',
    'src/threadsense/legacy/agent2/topic_consolidation_v4.py',
    'src/threadsense/routing.py', 'data/config/channel_routes.json',
    'src/threadsense/metadata_paths.py',
    'src/threadsense/legacy/severity_types.py',
    'src/threadsense/legacy/topic_taxonomy_v7.py', 'src/threadsense/legacy/taxonomy_severity_v7.py',
    'src/threadsense/legacy/agent2/operational_severity.py', 'src/threadsense/legacy/agent2/topic_evidence.py',
    'src/threadsense/agents/topic_diagnostics.py',
    'src/threadsense/agents/topic_requests.py',
    'src/threadsense/agents/topic_effective.py', 'data/metadata/agent2-review-supplements.json',
    'src/threadsense/agents/thread_interpreter.py',
    'src/threadsense/agents/topic_pipeline.py', 'src/threadsense/agents/verification_requests.py',
    'src/threadsense/config.py', 'src/threadsense/terminology.py',
    'scripts/run_agent2_batch.py',
)

def configuration(payloads, model):
    return {'schema_version':8 if EXPORT_ADAPTER_VERSION=='taxonomy-to-canonical-v2' else RESPONSE_SCHEMA_VERSION, 'response_schema_version':RESPONSE_SCHEMA_VERSION, 'prompt_version':PROMPT_VERSION,
            'rubric_version':RUBRIC_VERSION, 'export_adapter_version':EXPORT_ADAPTER_VERSION,
            'model':model, 'maximum_requests_per_group':1,
            'request_parameters': model_parameters(model), 'response_format_sha256': digest(response_format()),
            'automatic_retries':0, 'maximum_repairs':0, 'additional_verifier_calls':0,
            'payload_sha256':digest(payloads), 'glossary_sha256':digest(get_terms()),
            'code_sha256':{p:file_hash(ROOT/p) for p in CODE_FILES}}

def write_bytes(path, content, *, exclusive=False):
    """Keep incomplete writes separate; any persistence failure is fatal."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open('xb') as handle:
            handle.write(content)
            handle.flush()
        return
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as handle:
        handle.write(content)
        handle.flush()
    temporary.replace(path)

def write_json(path, payload, **kwargs):
    write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8'), **kwargs)

def reports(output, payloads, records, run_config, state):
    flattened = [m for record in records for m in record['members']]
    expected = [identity(m) for p in payloads for m in p['members']]
    actual = [identity(m) for m in flattened]
    if len(set(expected)) != len(expected) or Counter(actual) != Counter(expected):
        raise ValueError('Agent 2 export lost or duplicated membership.')
    obligations = [o for record in records for o in record['inherited_review_obligations']]
    expected_flags = {identity(m) for p in payloads for m in p['members'] if m['agent1_record']['review_required']}
    if len(obligations) != len(expected_flags) or {identity(o) for o in obligations} != expected_flags:
        raise ValueError('Agent 2 export lost or duplicated inherited review obligations.')
    calls = list((output/'records').glob('*/call.json'))
    response_files = list((output/'records').glob('*/response.json'))
    started_without_call = [p.parent.name for p in (output/'records').glob('*/started.json') if not p.with_name('call.json').exists()]
    unknown = [p.parent.name for p in calls if not p.with_name('response.json').exists()
               or (p.with_name('completion_status.json').exists()
                   and json.loads(p.with_name('completion_status.json').read_text(encoding='utf-8')).get('provider_completion_unknown'))]
    manifest = {'schema_version':run_config['schema_version'], 'state':state,
                'updated_at':datetime.now(timezone.utc).isoformat(),
                'config':run_config, 'config_sha256':digest(run_config),
                'selected_groups':len(payloads), 'retained_input_identities':len(actual),
                'inherited_review_obligations':len(obligations),
                'member_verification_counts':dict(Counter(m['agent1_record']['verification_status'] for m in flattened)),
                'processing_counts':dict(Counter(r['processing_state'] for r in records)),
                'factual_validity_counts':dict(Counter(r.get('factual_validity', 'LEGACY') for r in records)),
                'severity_validity_counts':dict(Counter(r.get('severity_validity', 'LEGACY') for r in records)),
                'unprocessed_groups':sum(r['processing_state']=='NOT_RUN' for r in records),
                'new_request_attempts':len(calls), 'available_response_records':len(response_files),
                'unknown_completion_requests':unknown, 'maximum_request_attempts':len(payloads),
                'started_without_call_markers': started_without_call,
                'review_group_count':sum(r['review_required'] for r in records)}
    write_json(output/'consolidations.json', records)
    if run_config['response_schema_version'] == 7:
        manifest.pop('factual_validity_counts')
        manifest.pop('severity_validity_counts')
        manifest['taxonomy_validity_counts'] = dict(Counter(r['taxonomy_validity'] for r in records))
        manifest['member_disposition_counts'] = dict(Counter(d['disposition'] for r in records for d in r['member_dispositions']))
    write_json(output/'review_queue.json', [r for r in records if r['review_required']])
    # Independent of topic count, ordinary recommendations, and any future briefing UI.
    write_json(output/'member_review_queue.json', obligations)
    write_json(output/'manifest.json', manifest)
    # This is the maintained downstream view; raw canonical artifacts stay intact.
    write_json(output/'effective_output.json', load_effective_output(output))
    return manifest

def execute_batch(payloads, output, *, run=False, maximum_requests=None, model_override=None):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a new Agent 2 output directory; never retry/resume an old attempt.')
    model, key_name = config.get_model_settings()
    if model_override is not None:
        model = model_override
        model_parameters(model)  # Explicit, reviewed OpenAI profiles only.
        key_name = 'OPENAI_API_KEY'
    requests = [build_request(p, get_terms(), model) for p in payloads]
    from threadsense.topic_inputs import routing_manifest_for_payloads
    routing = routing_manifest_for_payloads(payloads)
    if not payloads or (maximum_requests is not None and len(payloads) > maximum_requests):
        raise ValueError('Selection exceeds the explicit request bound, or is empty.')
    if run:
        config.get_api_key(key_name)  # Missing configuration must fail before writes/attempts.
    run_config = configuration(payloads, model)
    output.mkdir(parents=True, exist_ok=False)
    if routing is not None:
        write_json(output/'routing_manifest.json', routing, exclusive=True)
    records = [export_result(p) for p in payloads]
    for payload, request in zip(payloads, requests):
        directory = output/'records'/payload['candidate_group_id']
        write_json(directory/'input.json', payload, exclusive=True)
        write_json(directory/'request.json', request, exclusive=True)
    reports(output, payloads, records, run_config, 'running' if run else 'prepared_no_calls')
    if not run:
        return reports(output, payloads, records, run_config, 'prepared_no_calls')
    for index, (payload, request) in enumerate(zip(payloads, requests)):
        directory = output/'records'/payload['candidate_group_id']
        write_json(directory/'started.json', {'started_at':datetime.now(timezone.utc).isoformat(),
                                             'maximum_requests':1}, exclusive=True)

        def artifact(name, body):
            path = directory/name
            if name == 'request.json' and path.read_bytes() == body:
                return  # This is the exact prepared request; no request mutation.
            write_bytes(path, body, exclusive=True)

        try:
            raw = complete_topic_once(model, key_name, request,
                on_raw_output=lambda raw:write_bytes(directory/'analysis.raw.txt', raw.encode('utf-8'), exclusive=True),
                on_artifact=artifact)
            analysis = parse_response(payload, raw)
            records[index] = export_result(payload, analysis, state='CONSOLIDATED')
        except (transport.EvidencePersistenceError, transport.VerificationConfigurationError) as error:
            # Do not start another group after fatal configuration/persistence failure.
            details = describe_exception(payload, error)
            records[index] = export_result(payload, state='FAILED',
                error=f'Fatal {getattr(error, "category", "configuration_or_persistence")} failure; inspect retained artifacts.',
                diagnostics=details)
            if isinstance(error, transport.VerificationConfigurationError):
                write_json(directory/'diagnostics.json', details, exclusive=True)
                write_json(directory/'result.json', records[index], exclusive=True)
            reports(output, payloads, records, run_config, 'failed')
            raise
        except KeyboardInterrupt:
            records[index] = export_result(payload, state='INTERRUPTED', error='Interrupted; provider completion is unknown unless a response was saved.')
            write_json(directory/'result.json', records[index], exclusive=True)
            return reports(output, payloads, records, run_config, 'interrupted')
        except Exception as error:
            details = describe_exception(payload, error)
            try:
                write_json(directory/'diagnostics.json', details, exclusive=True)
            except OSError as persistence_error:
                records[index] = export_result(payload, state='FAILED', error='Fatal diagnostic persistence failure; raw evidence retained.')
                reports(output, payloads, records, run_config, 'failed')
                raise transport.EvidencePersistenceError('Cannot persist validation diagnostics.') from persistence_error
            first = details[0]
            records[index] = export_result(payload, state='FAILED',
                error=f"{first['category']} at {first['field_path']}: {first['message']}", diagnostics=details)
        try:
            write_json(directory/'result.json', records[index], exclusive=True)
            reports(output, payloads, records, run_config, 'running')
        except OSError as persistence_error:
            records[index] = export_result(payload, state='FAILED', error='Fatal result/report persistence failure; inspect retained request/response evidence.')
            # If the filesystem is still available, leave an explicit failed manifest.
            # A second write failure also propagates; later groups are never called.
            reports(output, payloads, records, run_config, 'failed')
            raise transport.EvidencePersistenceError('Cannot persist consolidation result/report.') from persistence_error
    state = 'complete_with_review' if any(r['review_required'] for r in records) else 'complete'
    return reports(output, payloads, records, run_config, state)
