"""Read the canonical Agent 1 export without regenerating or filtering it."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from threadsense.agents.contracts import ThreadInterpretation
from threadsense.agents.verification_handoff import digest
from threadsense.models import Thread

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / 'data/processed/agent1_verified_v3/interpretations.json'
GROUPING = ROOT / 'data/processed/grouping_agent1_v3/clusters.json'
BASELINE_GROUPING = ROOT / 'data/processed/grouping/clusters.json'
IDENTITY = ('project_id', 'batch_id', 'channel_id', 'thread_id')
REVIEW_FILES = (ROOT / 'docs/agent1-pilot-content-review.json',
                ROOT / 'data/processed/agent1_full_batch_review_v3/content_review.json')

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity(record):
    return tuple(record[k] for k in IDENTITY)

def member_id(record):
    return 'member_' + digest(list(identity(record)))[:24]

def load_handoff(path=CANONICAL):
    """Fail closed on broken lineage/coverage; semantic review flags remain inputs."""
    path = Path(path).resolve()
    records = read_json(path)
    if path == CANONICAL.resolve():
        receipt = read_json(ROOT / 'data/processed/agent1_full_batch_review_v3/run_receipt.json')
        for relative, expected in receipt['final_artifact_sha256'].items():
            if file_hash(ROOT / relative) != expected:
                raise ValueError('Finalized Agent 1 evidence changed since its completion receipt.')
    manifest = read_json(path.parent / 'manifest.json')
    queue = read_json(path.parent / 'review_queue.json')
    if not isinstance(records, list) or not records:
        raise ValueError('Canonical handoff must contain records.')
    if manifest.get('unprocessed') != 0 or manifest.get('retained') != len(records):
        raise ValueError('Canonical handoff coverage is incomplete.')
    if manifest.get('coverage') != 'all_source_threads' or manifest['config']['source_count'] != len(records):
        raise ValueError('Canonical handoff must cover all source threads.')
    if queue != [r for r in records if r['review_required']]:
        raise ValueError('Canonical review queue differs from retained obligations.')
    if dict(Counter(r['verification_status'] for r in records)) != {k:v for k,v in manifest['counts'].items() if v}:
        raise ValueError('Canonical status counts differ from manifest.')
    seen, loaded = set(), []
    export_hash = file_hash(path)
    for record in records:
        key = identity(record)
        if key in seen or any(not isinstance(record[k], str) or not record[k].strip()
                              for k in ('project_id', 'channel_id', 'thread_id')):
            raise ValueError('Duplicate or invalid full thread identity.')
        if record['batch_id'] is not None and not isinstance(record['batch_id'], str):
            raise ValueError('Invalid batch identity.')
        seen.add(key)
        for field in ('automated_verification_status', 'verification_status'):
            if record[field] not in {'VERIFIED', 'CORRECTED', 'NEEDS_REVIEW'}:
                raise ValueError('Unknown verification status.')
        if record['review_required'] != (record['verification_status'] == 'NEEDS_REVIEW'):
            raise ValueError('Inconsistent review flag.')
        if record['review_required'] and (not record['provisional_fields'] or not record['review_reasons']):
            raise ValueError('Review obligation lacks fields/reasons.')
        candidate = ThreadInterpretation.model_validate(record['interpretation'])
        if candidate.thread_id != record['thread_id'] or digest(record['interpretation']) != record['candidate_sha256']:
            raise ValueError('Candidate identity/hash mismatch.')
        lineage = record['lineage']
        source_path = (path.parent / lineage['source_file']).resolve()
        result_path = (path.parent / lineage['verification_file']).resolve()
        if not source_path.is_relative_to(path.parent / 'sources') or not result_path.is_relative_to(path.parent / 'records'):
            raise ValueError('Canonical source/result reference escapes evidence directory.')
        source, result = read_json(source_path), read_json(result_path)
        Thread.model_validate(source)
        if identity(source) != key or digest(source) != record['input_sha256']:
            raise ValueError('Source identity/hash mismatch.')
        if record['source_message_ids'] != [m['message_id'] for m in source['messages']]:
            raise ValueError('Source message lineage mismatch.')
        if (result['result_sha256'] != digest(result['result'])
                or result['result']['interpretation'] != record['interpretation']
                or lineage['effective_candidate_sha256'] != record['candidate_sha256']):
            raise ValueError('Retained result/candidate lineage mismatch.')
        # Keep the complete immutable canonical row, including unknown future metadata.
        loaded.append({**{k:record[k] for k in IDENTITY}, 'member_id':member_id(record),
                       'agent1_record':deepcopy(record), 'original_thread':source,
                       'agent1_export_file':str(path), 'agent1_export_sha256':export_hash,
                       'agent1_lineage_base':str(path.parent)})
    return sorted(loaded, key=lambda m:tuple(v or '' for v in identity(m)))

def review_provenance():
    """Retain both registries as evidence; never refresh/reinterpret the export."""
    return [{'path':p.relative_to(ROOT).as_posix(), 'sha256':file_hash(p)} for p in REVIEW_FILES]
