"""Replay a saved topic's exact retrieval steps against its own snapshot and classify each missing expected source.
Read-only, zero model calls.

Per expected source (the demo scenario matrix, or the open evaluation case), across the topic's recorded steps:
- NEVER_SEARCHED: no step's document types (or project) could return it;
- FILTERED_OUT: searched for, but excluded by date/batch/version filters before ranking;
- RANKED_BELOW_CUTOFF: eligible, but outside the step's top_k (best rank reported);
- RETRIEVED_NOT_USED: in the evidence ledger but not cited on the card;
- RETRIEVED_AND_CITED.

  uv run --locked python scripts/diagnose_retrieval_misses.py [--write <new path>]
"""
import argparse
import json
from pathlib import Path
import sys

CASES = [  # (label, run directory, work ID or None for the open case)
    ('audio trial outcome (smoke)', 'data/experiments/agent3_overnight_smoke_v1', 'topic:cluster_6b59d13144282285/topic_2'),
    ('already announced (final eval)', 'data/experiments/agent3_final_eval_v1', 'topic:cluster_e6a79dfad226e738/topic_2'),
    ('QA misalignment (final eval)', 'data/experiments/agent3_final_eval_v1', 'topic:cluster_f944891544b06f79/topic_2'),
]


def topic_result(run, work_id):
    for path in sorted((Path(run)/'topics').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['work_item']['work_id'] == work_id:
            return data
    raise LookupError(work_id)


def chunk_matches(ref, chunk):
    m = chunk['metadata']
    if 'slack' in ref:
        return [m.get('channel_id'), m.get('thread_id')] == list(ref['slack']) and m['source_system'] == 'slack'
    return m['authoring_document_id'] == ref['authoring'] and ('section' not in ref or ref['section'] in chunk['sections'])


def diagnose(retriever, run, work_id, expected):
    data = topic_result(run, work_id)
    result, card = data['result'], data['result']['card']
    ledger, cited = result['evidence_ledger'], {(r.get('note') or '').split(' ')[0] for r in card['supporting_sources']}
    out = []
    for ref in expected:
        keys = [k for k, c in retriever.chunks.items() if chunk_matches(ref, c)]
        in_ledger = [k for k, e in ledger.items() if e.get('origin') == 'retrieved_source' and e['citation']['chunk_id'] in keys]
        steps = []
        for step in result['retrieval_trace']:
            types = step['source_types']
            doc_type = retriever.chunks[keys[0]]['metadata']['document_type'] if keys else None
            searched = doc_type in types
            filters = {'batch': step['batch'], 'as_of': step['as_of'], 'version_mode': step['version_mode'], 'document_types': types}
            selection = retriever.select(result['topic']['project_id'], **filters)
            eligible = [k for k in keys if k in selection['eligible']]
            rank = None
            if eligible:
                wide = retriever.search(step['query'], result['topic']['project_id'], top_k=60, mmr_lambda=step['mmr_lambda'],
                                        **filters)['results']
                rank = min((r['rank'] for r in wide if r['chunk_id'] in eligible), default=None)
            steps.append({'step': step['step'], 'purpose': step['purpose'], 'searched_type': searched,
                          'eligible_chunks': len(eligible), 'best_rank': rank, 'top_k': step['top_k'],
                          'withheld_by_version': [w for w in selection['withheld'] if w.get('document_id') in
                                                  {retriever.chunks[k]['document_id'] for k in keys}][:2]})
        if any(e for e in in_ledger if e in cited):
            status = 'RETRIEVED_AND_CITED'
        elif in_ledger:
            status = 'RETRIEVED_NOT_USED'
        elif not any(s['searched_type'] for s in steps):
            status = 'NEVER_SEARCHED'
        elif not any(s['eligible_chunks'] for s in steps if s['searched_type']):
            status = 'FILTERED_OUT'
        else:
            status = 'RANKED_BELOW_CUTOFF'
        out.append({'ref': ref, 'status': status, 'chunks_in_index': len(keys), 'steps': steps})
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', type=Path, help='New path for the JSON report.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.retrieval.search import Retriever
    matrix = {s['work_id']: s for s in json.loads(Path('data/evaluation/agent3_demo_scenarios.json').read_text(encoding='utf-8'))['scenarios']}
    retriever = Retriever()
    report = []
    for label, run, work_id in CASES:
        manifest = json.loads((Path(run)/'run_manifest.json').read_text(encoding='utf-8'))['fingerprints']['index']
        if manifest['build_fingerprint'] != retriever.manifest['build_fingerprint']:
            parser.error(f'{run} used snapshot {manifest["build_fingerprint"][:12]}, not the active one; replay needs it.')
        expected = [s['ref'] for s in matrix[work_id]['expected_sources']]
        rows = diagnose(retriever, run, work_id, expected)
        report.append({'case': label, 'run': run, 'work_id': work_id, 'snapshot': manifest['build_fingerprint'], 'sources': rows})
        print(f'\n{label} ({run})')
        for r in rows:
            best = [s['best_rank'] for s in r['steps'] if s['best_rank']]
            print(f"  {r['status']:20} {r['ref']}  best rank {min(best) if best else '-'}; "
                  + '; '.join(f"step {s['step']} {s['purpose']}: type {'yes' if s['searched_type'] else 'no'}, "
                              f"eligible {s['eligible_chunks']}, rank {s['best_rank']}/{s['top_k']}" for s in r['steps']))
    retriever.client.close()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
