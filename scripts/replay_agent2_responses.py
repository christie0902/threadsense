"""Replay historical v2 responses offline; never count the continuation subset twice."""
import argparse
from collections import Counter
from pathlib import Path

from threadsense.handoff_inputs import read_json, file_hash
from threadsense.legacy.agent2.topic_consolidation_v2 import parse_response
from threadsense.agents.topic_diagnostics import legacy_diagnostics
from threadsense.agents.topic_pipeline import write_json


def replay(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError('Use a new diagnostics directory outside the historical run.')
    rows = read_json(source / 'consolidations.json')
    if len(rows) != len({r['candidate_group_id'] for r in rows}):
        raise ValueError('Combined run contains duplicate groups.')
    results, counts = [], Counter()
    for row in rows:
        directory = source / 'records' / row['candidate_group_id']
        payload = read_json(directory / 'input.json')
        result = {'candidate_group_id': row['candidate_group_id'], 'historical_state': row['processing_state'],
                  'source_directory': directory.as_posix(), 'input_sha256': file_hash(directory / 'input.json'),
                  'diagnostics': []}
        raw_path = directory / 'analysis.raw.txt'
        if not raw_path.exists():
            result['replay_verdict'] = 'no_saved_response'
        else:
            raw = raw_path.read_text(encoding='utf-8')
            result['raw_sha256'] = file_hash(raw_path)
            try:
                parse_response(payload, raw)
                result['replay_verdict'] = 'accepted'
            except (ValueError, KeyError, TypeError) as error:
                result['diagnostics'] = legacy_diagnostics(payload, raw, error)
                categories = {d['category'] for d in result['diagnostics']}
                result['replay_verdict'] = next((c for c in ('malformed_json', 'schema', 'custom_consistency') if c in categories), result['diagnostics'][0]['category'])
        counts[result['replay_verdict']] += 1
        results.append(result)
    summary = {'mode': 'original_v2_response_replay_not_a_v3_evaluation', 'model_calls': 0,
               'combined_groups': len(rows), 'response_replay_counts': dict(counts),
               'historical_status_counts': dict(Counter(r['processing_state'] for r in rows)),
               'historically_consolidated_threads': sum(len(r['members']) for r in rows if r['processing_state'] == 'CONSOLIDATED'),
               'retained_threads': sum(len(r['members']) for r in rows),
               'inherited_review_obligations': sum(len(r['inherited_review_obligations']) for r in rows),
               'request_attempts': sum((source/'records'/r['candidate_group_id']/'call.json').exists() for r in rows),
               'saved_http_responses': sum((source/'records'/r['candidate_group_id']/'response.json').exists() for r in rows),
               'http_status_counts': dict(Counter(str(read_json(source/'records'/r['candidate_group_id']/'response.json')['http_status'])
                   for r in rows if (source/'records'/r['candidate_group_id']/'response.json').exists())),
               'unknown_completion_requests': [r['candidate_group_id'] for r in rows
                   if (source/'records'/r['candidate_group_id']/'call.json').exists()
                   and not (source/'records'/r['candidate_group_id']/'response.json').exists()],
               'source_manifest_sha256': file_hash(source / 'manifest.json')}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'summary.json', summary, exclusive=True)
    write_json(output / 'diagnostics.json', results, exclusive=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(replay(args.source_dir, args.output_dir))
