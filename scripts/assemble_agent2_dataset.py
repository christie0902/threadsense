"""Assemble immutable Agent 2 runs offline; preserve provenance and bound reviews.

No model calls or changed judgments. Copies exact per-group evidence so the existing
mandatory effective loader can validate the combined dataset without a new contract.
"""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import shutil

from threadsense.handoff_inputs import ROOT, read_json, file_hash, digest, identity
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_consolidation import build_request, parse_response, export_result
from threadsense.agents.topic_effective import REGISTRY, load_effective_output
from threadsense.agents.topic_pipeline import write_json
from threadsense.terminology import get_terms

SEMANTIC_CONFIG = ('schema_version', 'response_schema_version', 'prompt_version',
    'rubric_version', 'export_adapter_version', 'model', 'request_parameters',
    'response_format_sha256', 'glossary_sha256', 'maximum_requests_per_group',
    'automatic_retries', 'maximum_repairs', 'additional_verifier_calls')


def assemble_dataset(sources, output, payloads, *, registry=REGISTRY):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh final dataset directory.')
    from threadsense.topic_inputs import routing_manifest_for_payloads
    routing = routing_manifest_for_payloads(payloads)
    expected = {p['candidate_group_id']: p for p in payloads}
    if len(expected) != len(payloads):
        raise ValueError('Duplicate expected group identities.')
    old_registry = read_json(registry)
    records, provenance, source_runs, review_entries, source_reviews = {}, {}, [], [], []
    accepted, producer_code = None, None
    expected_review_ids = set()
    for source, kind in sources:
        source = Path(source).resolve()
        if kind not in {'reused', 'new'} or output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError('Invalid provenance or overlapping output/source directories.')
        manifest = read_json(source/'manifest.json')
        config = manifest['config']
        if routing is not None and read_json(source/'routing_manifest.json') != routing:
            raise ValueError('Source routing manifest changed or lost announcement obligations.')
        version = config['response_schema_version']
        if digest(config) != manifest['config_sha256']:
            raise ValueError('Source configuration fingerprint mismatch.')
        semantic = {k: config[k] for k in SEMANTIC_CONFIG}
        code = {k:v for k,v in config['code_sha256'].items() if k not in {'docs/agent2-review-supplements.json', 'data/metadata/agent2-review-supplements.json'}}
        if accepted is None:
            accepted, producer_code = semantic, code
        if semantic != accepted or code != producer_code:
            raise ValueError('Source model, contract, rubric, settings or producer code differ.')
        effective = load_effective_output(source, registry=registry)
        if effective['unapplied_findings']:
            raise ValueError('Source has stale review bindings; inspect before assembly.')
        expected_review_ids.update(o['obligation_id'] for o in effective['applied_content_obligations'])
        rows = read_json(source/'consolidations.json')
        group_ids = []
        for row in rows:
            gid = row['candidate_group_id']
            if gid not in expected or gid in records:
                raise ValueError('Duplicate or unknown source group.')
            p = expected[gid]; d = source/'records'/gid
            if read_json(d/'input.json') != p or row['members'] != p['members']:
                raise ValueError('Source input or full member lineage changed.')
            if read_json(d/'request.json') != build_request(p, get_terms(), config['model'], response_schema_version=version, export_adapter_version=config['export_adapter_version']):
                raise ValueError('Source request is incompatible with accepted construction.')
            if read_json(d/'result.json') != row:
                raise ValueError('Aggregate and per-group result differ.')
            if row['inherited_review_obligations'] != export_result(p, response_schema_version=version, export_adapter_version=config['export_adapter_version'])['inherited_review_obligations']:
                raise ValueError('Inherited obligations differ from canonical input.')
            if row['processing_state'] == 'CONSOLIDATED':
                raw = (d/'analysis.raw.txt').read_text(encoding='utf-8')
                if export_result(p, parse_response(p, raw, response_schema_version=version), state='CONSOLIDATED', response_schema_version=version, export_adapter_version=config['export_adapter_version']) != row:
                    raise ValueError('Accepted producer no longer reproduces the saved export.')
            elif row['processing_state'] not in {'FAILED', 'INTERRUPTED', 'NOT_RUN'}:
                raise ValueError('Unknown processing state.')
            records[gid] = row; group_ids.append(gid)
            provenance[gid] = {'origin':kind, 'source_run':source.as_posix(),
                'source_manifest_sha256':file_hash(source/'manifest.json'),
                'files':{q.name:file_hash(q) for q in d.iterdir() if q.is_file()}}
        for entry in old_registry['supplements']:
            if (ROOT/entry['run']).resolve() != source:
                continue
            review = read_json(ROOT/entry['path'])
            source_reviews.append(deepcopy(entry))
            for reviewed in review['entries']:
                if reviewed['candidate_group_id'] not in group_ids:
                    raise ValueError('Review refers to a group outside its source run.')
                copied = deepcopy(reviewed)
                copied['original_review_provenance'] = deepcopy(entry)
                # Input/raw/result copies below have identical bytes. The loader
                # rechecks these bindings against the final candidate; no transfer
                # to changed output or transplantation of a historical verdict.
                review_entries.append(copied)
        source_runs.append({'run':source.as_posix(), 'origin':kind,
            'manifest_sha256':file_hash(source/'manifest.json'), 'config_sha256':manifest['config_sha256'],
            'groups':group_ids})
    if set(records) != set(expected):
        raise ValueError('Final dataset has missing groups.')
    ordered = [records[p['candidate_group_id']] for p in payloads]
    identities = [identity(m) for r in ordered for m in r['members']]
    input_ids = [identity(m) for p in payloads for m in p['members']]
    if len(identities) != len(set(identities)) or Counter(identities) != Counter(input_ids):
        raise ValueError('Final identities are missing or duplicated.')
    output.mkdir(parents=True)
    if routing is not None:
        write_json(output/'routing_manifest.json', routing, exclusive=True)
    for gid, origin in provenance.items():
        src = Path(origin['source_run'])/'records'/gid
        dest = output/'records'/gid
        shutil.copytree(src, dest)
        if {p.name:file_hash(p) for p in dest.iterdir() if p.is_file()} != origin['files']:
            raise ValueError('Copied evidence differs from original source.')
    write_json(output/'consolidations.json', ordered, exclusive=True)
    write_json(output/'review_queue.json', [r for r in ordered if r['review_required']], exclusive=True)
    obligations = [o for r in ordered for o in r['inherited_review_obligations']]
    write_json(output/'member_review_queue.json', obligations, exclusive=True)
    supplement = {'origin':'Evidence-bound aggregation of Codex-assisted source reviews; not human approval or independent ground truth',
        'run':output.as_posix(), 'source_supplements':source_reviews, 'entries':review_entries,
        'method':'Only unchanged copied source/raw/result bytes inherit findings; original review provenance retained per entry.'}
    review_path = output/'combined_review_supplement.json'
    write_json(review_path, supplement, exclusive=True)
    view = load_effective_output(output, registry=registry, additional_supplements=(review_path,))
    if view['unapplied_findings'] or {o['obligation_id'] for o in view['applied_content_obligations']} != expected_review_ids:
        raise ValueError('Combined effective reviews differ from their original bound findings.')
    updated = deepcopy(old_registry)
    def stored(path):
        return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
    updated['supplements'].append({'run':stored(output), 'path':stored(review_path), 'sha256':file_hash(review_path)})
    write_json(registry, updated)
    view = load_effective_output(output, registry=registry)
    write_json(output/'effective_output.json', view, exclusive=True)
    calls = {kind:sum('call.json' in p['files'] for p in provenance.values() if p['origin']==kind) for kind in ('new','reused')}
    unknown, starts, responses = [], [], 0
    for gid,p in provenance.items():
        files=p['files']; d=output/'records'/gid
        responses += 'response.json' in files
        if 'started.json' in files and 'call.json' not in files:
            starts.append(gid)
        if 'call.json' in files and ('response.json' not in files or
                ('completion_status.json' in files and read_json(d/'completion_status.json').get('provider_completion_unknown'))):
            unknown.append(gid)
    counts = dict(Counter(r['processing_state'] for r in ordered))
    manifest = {'dataset_manifest_version':1, 'schema_version':accepted['schema_version'],
        'state':'incomplete' if counts.get('NOT_RUN',0) else 'complete_with_review' if view['review_queue'] else 'complete',
        'accepted_configuration':accepted, 'producer_code_sha256':producer_code,
        'groups':len(ordered), 'identities':len(identities), 'inherited_review_obligations':len(obligations),
        'processing_counts':counts, 'unprocessed_groups':counts.get('NOT_RUN',0),
        'new_request_attempts':calls['new'], 'reused_original_attempts':calls['reused'],
        'total_original_attempts':sum(calls.values()), 'available_responses':responses,
        'unknown_completion_requests':unknown, 'started_without_call_markers':starts,
        'automated_review_groups':sum(r['review_required'] for r in ordered), 'effective_review_groups':len(view['review_queue']),
        'source_runs':source_runs, 'record_provenance':provenance,
        'assembly_script_sha256':file_hash(__file__), 'assembly_model_calls':0,
        'canonical_sha256':file_hash(output/'consolidations.json'),
        'effective_sha256':file_hash(output/'effective_output.json'),
        'review_supplement_sha256':file_hash(review_path)}
    write_json(output/'manifest.json', manifest, exclusive=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reused-run', type=Path, required=True)
    parser.add_argument('--new-run', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args=parser.parse_args()
    historical=read_json(args.reused_run/'manifest.json')['config']['export_adapter_version']!='taxonomy-to-canonical-v2'
    result=assemble_dataset([(args.reused_run,'reused'),(args.new_run,'new')],args.output_dir,load_candidate_payloads(historical=historical))
    print({k:result[k] for k in ('state','groups','identities','inherited_review_obligations','processing_counts','new_request_attempts','reused_original_attempts')})
    return 1 if result['unprocessed_groups'] else 0


if __name__=='__main__':
    raise SystemExit(main())
