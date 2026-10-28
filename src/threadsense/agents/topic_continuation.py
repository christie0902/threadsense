"""Continue only never-started groups, retaining original evidence in a new export."""
from pathlib import Path
import shutil

from threadsense import config
from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents.topic_consolidation import build_request, export_result
from threadsense.handoff_inputs import ROOT, digest, file_hash, read_json
from threadsense.terminology import get_terms

CONTROLLER_FILES = ('src/threadsense/agents/topic_continuation.py', 'scripts/continue_agent2_batch.py')
STATES = {'NOT_RUN', 'CONSOLIDATED', 'FAILED', 'INTERRUPTED'}


def controller_hashes():
    return {p: file_hash(ROOT / p) for p in CONTROLLER_FILES}


def tree_hashes(directory):
    return {p.relative_to(directory).as_posix(): file_hash(p)
            for p in sorted(directory.rglob('*')) if p.is_file()}


def _records(rows, payloads):
    by_id = {p['candidate_group_id']: p for p in payloads}
    if len(rows) != len(by_id) or {r['candidate_group_id'] for r in rows} != set(by_id):
        raise ValueError('Saved export has missing or duplicate groups.')
    for row in rows:
        payload = by_id[row['candidate_group_id']]
        pending = export_result(payload)
        if (row['processing_state'] not in STATES or row['members'] != payload['members']
                or row['inherited_review_obligations'] != pending['inherited_review_obligations']
                or (pending['review_required'] and not row['review_required'])):
            raise ValueError('Saved record changed member identities or review obligations.')
    return {r['candidate_group_id']: r for r in rows}


def inspect_run(source, payloads, model):
    """Use per-request evidence even when a hard stop left aggregate reports stale."""
    source = Path(source).resolve()
    from threadsense.topic_inputs import routing_manifest_for_payloads
    routing = routing_manifest_for_payloads(payloads)
    if routing is not None and read_json(source/'routing_manifest.json') != routing:
        raise ValueError('Source routing manifest changed or lost announcement obligations.')
    manifest = read_json(source / 'manifest.json')
    expected = pipeline.configuration(payloads, model)
    if manifest['config'] != expected or manifest['config_sha256'] != digest(expected):
        raise ValueError('Source run code/configuration differs from the prepared selection.')
    if (manifest.get('continuation_code_sha256') is not None
            and manifest['continuation_code_sha256'] != controller_hashes()):
        raise ValueError('Continuation controller changed; inspect it before continuing.')
    rows = _records(read_json(source / 'consolidations.json'), payloads)
    by_id = {p['candidate_group_id']: p for p in payloads}
    directories = {gid: [source / 'records' / gid] for gid in by_id}
    # A continuation's isolated execution journal is authoritative after a hard stop.
    journal = source / 'new_requests'
    if (journal / 'manifest.json').exists():
        journal_rows = read_json(journal / 'consolidations.json')
        if not {r['candidate_group_id'] for r in journal_rows} <= by_id.keys():
            raise ValueError('Execution journal contains an unknown group.')
        journal_payloads = [by_id[r['candidate_group_id']] for r in journal_rows]
        journal_config = pipeline.configuration(journal_payloads, model)
        journal_manifest = read_json(journal / 'manifest.json')
        if (journal_manifest['config'] != journal_config
                or journal_manifest['config_sha256'] != digest(journal_config)):
            raise ValueError('Execution journal configuration differs from the source run.')
        rows.update(_records(journal_rows, journal_payloads))
        for payload in journal_payloads:
            directories[payload['candidate_group_id']].append(journal / 'records' / payload['candidate_group_id'])
    elif (journal / 'records').exists():
        # Before the initial journal manifest, execution has not begun. Fail closed
        # on anything other than incomplete input/request preparation.
        if any(p.is_file() and p.name not in {'input.json', 'request.json', 'request.json.tmp', 'input.json.tmp'}
               for p in (journal / 'records').rglob('*')):
            raise ValueError('Execution evidence exists without a journal manifest; inspect it before continuing.')
    artifacts, remaining, unknown, started_without_call = {}, [], [], []
    call_count = response_count = 0
    for payload in payloads:
        gid = payload['candidate_group_id']
        files = {}
        for directory in directories[gid]:
            if read_json(directory / 'input.json') != payload:
                raise ValueError('Saved input differs from the canonical candidate.')
            if read_json(directory / 'request.json') != build_request(payload, get_terms(), model):
                raise ValueError('Saved request differs from current code/model.')
            files.update({p.name: p for p in directory.iterdir() if p.is_file()})
            if (directory / 'result.json').exists():
                result = read_json(directory / 'result.json')
                rows[gid] = _records([result], [payload])[gid]
        artifacts[gid] = files
        has_execution = bool(set(files) - {'input.json', 'request.json'})
        row = rows[gid]
        if row['processing_state'] == 'NOT_RUN' and not has_execution:
            remaining.append(payload)
        else:
            if row['processing_state'] == 'NOT_RUN':
                rows[gid] = export_result(payload, state='INTERRUPTED', error=(
                    'Execution evidence exists without a finalized result; retained for review without retry.'))
            if 'response.json' not in files:
                unknown.append(gid)
            if 'started.json' in files and 'call.json' not in files:
                started_without_call.append(gid)
        call_count += 'call.json' in files
        response_count += 'response.json' in files
    return {'source': source, 'manifest': manifest, 'records': rows, 'artifacts': artifacts,
            'remaining': remaining, 'unknown': unknown, 'started_without_call': started_without_call,
            'prior_request_attempts': call_count, 'available_responses': response_count,
            'reserved_groups': len(payloads) - len(remaining)}


def _copy_evidence(info, output):
    for gid, files in info['artifacts'].items():
        target = output / 'records' / gid
        target.mkdir(parents=True, exist_ok=True)
        for name, source_file in files.items():
            destination = target / name
            if source_file.resolve() != destination.resolve():
                shutil.copy2(source_file, destination)


def _report(output, payloads, model, state, provenance):
    info = inspect_run(output, payloads, model)
    _copy_evidence(info, output)
    result = pipeline.reports(output, payloads,
        [info['records'][p['candidate_group_id']] for p in payloads],
        pipeline.configuration(payloads, model), state)
    result.update(continuation_code_sha256=controller_hashes(), continuation=provenance,
                  continued_request_attempts=result['new_request_attempts'] - provenance['prior_request_attempts'],
                  unknown_completion_requests=info['unknown'],
                  started_without_call_marker=info['started_without_call'])
    pipeline.write_json(output / 'manifest.json', result)
    return result


def continue_batch(payloads, source, output, *, run=False, maximum_requests=None):
    """Copy the old run, execute only untouched groups, and merge without retries."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise FileExistsError('Use a new continuation directory outside the source run.')
    model, key_name = config.get_model_settings()
    source_snapshot = tree_hashes(source)
    info = inspect_run(source, payloads, model)
    remaining = info['remaining']
    if not remaining:
        raise ValueError('No never-started groups remain. Existing attempts are not retried.')
    if (run and maximum_requests != len(remaining)) or (maximum_requests is not None and maximum_requests != len(remaining)):
        raise ValueError(f'--max-requests must equal the {len(remaining)} never-started groups.')
    if info['reserved_groups'] + len(remaining) != len(payloads):
        raise ValueError('Continuation would exceed the original selection bound.')
    if run:
        config.get_api_key(key_name)
    output.mkdir(parents=True, exist_ok=False)
    from threadsense.topic_inputs import routing_manifest_for_payloads
    routing = routing_manifest_for_payloads(payloads)
    if routing is not None:
        pipeline.write_json(output/'routing_manifest.json', routing, exclusive=True)
    _copy_evidence(info, output)
    if tree_hashes(source) != source_snapshot:
        raise ValueError('Source run changed during inspection. Stop its process before continuing.')
    provenance = {'source_run': source.as_posix(), 'source_snapshot_sha256': digest(source_snapshot),
                  'prior_request_attempts': info['prior_request_attempts'],
                  'prior_reserved_groups': info['reserved_groups'],
                  'maximum_new_requests': len(remaining),
                  'original_maximum_requests': len(payloads), 'retries': 0}
    pipeline.write_json(output / 'source_snapshot.json', source_snapshot, exclusive=True)
    pipeline.reports(output, payloads, [info['records'][p['candidate_group_id']] for p in payloads],
                     pipeline.configuration(payloads, model), 'continuation_preparing')
    _report(output, payloads, model, 'running' if run else 'prepared_no_calls', provenance)
    try:
        journal = pipeline.execute_batch(remaining, output / 'new_requests', run=run,
                                         maximum_requests=len(remaining))
    except BaseException as error:
        _report(output, payloads, model, 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed', provenance)
        raise
    state = journal['state']
    if state in {'complete', 'complete_with_review'}:
        combined = inspect_run(output, payloads, model)
        state = 'complete_with_review' if any(r['review_required'] for r in combined['records'].values()) else 'complete'
    return _report(output, payloads, model, state, provenance)
