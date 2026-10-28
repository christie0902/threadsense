"""Refresh tentative candidates using the frozen, approved grouping implementation."""
from collections import Counter, defaultdict
from copy import deepcopy
import importlib.util
from pathlib import Path

from threadsense.handoff_inputs import (
    ROOT, CANONICAL, BASELINE_GROUPING, load_handoff, read_json, file_hash, identity,
    review_provenance, load_routed_handoff,
)

def approved_grouping():
    # Exact byte copy of the approved algorithm, isolated from the routed CLI.
    path = ROOT / 'src/threadsense/legacy/grouping_v1.py'
    baseline = read_json(BASELINE_GROUPING)
    if file_hash(path) != baseline['script_sha256']:
        raise ValueError('Approved grouping implementation changed; inspect explicitly.')
    spec = importlib.util.spec_from_file_location('threadsense_approved_grouping', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = baseline['config']
    if (config['algorithm'], config['linkage'], config['metric'], config['scope']) != (
            'agglomerative', 'complete', 'cosine', 'project_and_batch'):
        raise ValueError('Unsupported baseline grouping configuration.')
    if (config['embedding']['model'], config['embedding']['revision']) != (module.MODEL, module.MODEL_REVISION):
        raise ValueError('Baseline local embedding model differs.')
    if config['packages'] != module.package_versions():
        raise ValueError('Grouping packages differ from the approved baseline; no silent change.')
    return module, baseline

def group_members(members, vectors, implementation, threshold, *, historical=False):
    """Use the original algorithm per scope; enforce full identity at the boundary."""
    if not historical:
        from threadsense.routing import require_discussion
        for member in members:require_discussion(member)
    by_identity = {identity(m):m for m in members}
    if len(by_identity) != len(members):
        raise ValueError('Duplicate full member identity.')
    records = [m['agent1_record'] for m in members]
    scopes = defaultdict(list)
    for i, record in enumerate(records):
        scopes[(record['project_id'], record['batch_id'])].append(i)
    groups = []
    for indices in scopes.values():
        # Same project/batch algorithm; avoids conflating equal IDs across scopes.
        groups.extend(implementation.group_records([records[i] for i in indices], vectors[indices], threshold))
    groups.sort(key=lambda g:(g['project_id'], g['batch_id'] or '', -g['thread_count'], g['cluster_id']))
    assigned = []
    for group in groups:
        complete = []
        for old in group['threads']:
            key = (group['project_id'], group['batch_id'], old['channel_id'], old['thread_id'])
            complete.append(deepcopy(by_identity[key]['agent1_record']))
            assigned.append(key)
        group['threads'] = complete
        group['review_required'] = any(r['review_required'] for r in complete)
        group['review_member_count'] = sum(r['review_required'] for r in complete)
        group['grouping_status'] = 'TENTATIVE_CANDIDATE'
        group['representative_text_is_established_fact'] = False
    if len(assigned) != len(members) or len(set(assigned)) != len(assigned) or set(assigned) != set(by_identity):
        raise ValueError('Grouping lost, duplicated, or invented an input identity.')
    return groups

def refresh_grouping(output, input_path=CANONICAL):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a new grouping directory; frozen evidence is never overwritten.')
    members, announcements, routing = load_routed_handoff(input_path)
    implementation, baseline = approved_grouping()
    # Explicit offline mode: reuse the existing local model path, never download/fallback.
    import os
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    output.mkdir(parents=True)
    (output/'embedding_cache').mkdir()
    vectors, cache_key, truncated, embedding = implementation.get_embeddings(
        [m['agent1_record'] for m in members], output/'embedding_cache', implementation.package_versions())
    if embedding != baseline['config']['embedding']:
        raise ValueError('Embedding configuration changed from frozen baseline.')
    groups = group_members(members, vectors, implementation, baseline['config']['distance_threshold'])
    report = {
        'format_version':3, 'grouping_status':'TENTATIVE_CANDIDATES',
        'routing_manifest':routing,
        'input_path':str(Path(input_path).resolve()), 'input_sha256':file_hash(input_path),
        'baseline_grouping_path':str(BASELINE_GROUPING), 'baseline_grouping_sha256':file_hash(BASELINE_GROUPING),
        'approved_script_sha256':baseline['script_sha256'], 'config':deepcopy(baseline['config']),
        'embedding_cache_key':cache_key,
        'truncated_embedding_inputs':[list(identity(members[i])) for i in truncated],
        'review_evidence':review_provenance(),
        'thread_count':len(members), 'cluster_count':len(groups),
        'singleton_count':sum(g['is_singleton'] for g in groups),
        'review_member_count':sum(m['agent1_record']['review_required'] for m in members),
        'status_counts':dict(Counter(m['agent1_record']['verification_status'] for m in members)),
        'clusters':groups,
    }
    implementation.write_json(output/'clusters.json', report)
    implementation.write_text(output/'cluster_review.csv', implementation.review_csv(groups))
    return report
