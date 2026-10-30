"""Milestone 7 investigation: does a bounded lookup over RECORDED links recover the audio trial-outcome miss, and what
does it cost on the retrieval evaluation and holdout? Read-only, zero model calls; uses the active index.

Baseline: the frozen follow-up query from the open evaluation case at top_k 5 (hybrid RRF + MMR, the Advisor's
settings). Variant: the same results plus at most --limit records linked to a returned decision record by
source_refs (forward or backward) or a shared event_series_id (retrieval/related.py). Evaluated once on the tuned
cases and once on the holdout; nothing is tuned here.

  uv run --locked python scripts/evaluate_related_lookup.py [--report <new path>]
"""
import argparse
import json
from pathlib import Path
import sys


def score(retriever, cases, related, matches, limit, links):
    rows = []
    for case in cases:
        search = retriever.search(case['query'], case['project'], top_k=5, **case['filters'])
        extra = related(retriever, search, case['project'], limit=limit, links=links, **case['filters'])['added']
        def kinds(results):
            out = []
            for r in results:
                k = next((c for c, key in (('R', 'relevant'), ('X', 'must_exclude'), ('D', 'distractors'), ('C', 'context'))
                          if any(matches(ref, r) for ref in case.get(key, []))), '-')
                out.append(k)
            return out
        base, add = kinds(search['results']), kinds(extra)
        found = lambda results: [ref for ref in case['relevant'] if any(matches(ref, r) for r in results)]
        rows.append({'id': case['id'], 'answerable': case['answerable'],
                     'recall_base': len(found(search['results'])) / len(case['relevant']) if case['relevant'] else None,
                     'recall_with_links': len(found(search['results'] + extra)) / len(case['relevant']) if case['relevant'] else None,
                     'added': [{'kind': k, 'authoring': r['metadata']['authoring_document_id'], 'links': r['links']} for k, r in zip(add, extra)],
                     'added_kinds': add})
    scored = [r for r in rows if r['answerable'] and r['recall_base'] is not None]
    summary = {'cases': len(rows), 'answerable': len(scored),
               'mean_recall_base': round(sum(r['recall_base'] for r in scored) / len(scored), 3),
               'mean_recall_with_links': round(sum(r['recall_with_links'] for r in scored) / len(scored), 3),
               'cases_improved': sum(r['recall_with_links'] > r['recall_base'] for r in scored),
               'records_added': sum(len(r['added']) for r in rows),
               'added_relevant': sum(r['added_kinds'].count('R') for r in rows),
               'added_context': sum(r['added_kinds'].count('C') for r in rows),
               'added_distractors': sum(r['added_kinds'].count('D') for r in rows),
               'added_must_exclude': sum(r['added_kinds'].count('X') for r in rows),
               'added_unlabelled': sum(r['added_kinds'].count('-') for r in rows)}
    return {'summary': summary, 'cases': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--limit', type=int, default=2)
    parser.add_argument('--report', type=Path, help='New path for the JSON report.')
    args = parser.parse_args(argv)
    if args.report and args.report.exists():
        parser.error('--report must be a new path.')
    from threadsense.retrieval.evaluate import CASES, HOLDOUT, matches
    from threadsense.retrieval.related import LINKS, related
    from threadsense.retrieval.search import Retriever
    from threadsense.routing import ROOT
    retriever = Retriever()
    case = json.loads((ROOT/'data/evaluation/agent3_open_evaluation_cases.json').read_text(encoding='utf-8'))['cases'][0]
    search = retriever.search(case['query'], case['project'], top_k=case['top_k'], **case['filters'])
    linked = related(retriever, search, case['project'], limit=args.limit, **case['filters'])
    audio = {'case': case['id'], 'baseline_top5': [r['citation']['authoring'] or r['document_id'] for r in search['results']],
             'baseline_has_expected': any((r['citation']['authoring'] or '').startswith(case['expected'][0]['authoring']) for r in search['results']),
             'added': [{'authoring': a['citation']['authoring'], 'links': a['links']} for a in linked['added']],
             'candidates': linked['candidates']}
    audio['with_links_has_expected'] = any((a['authoring'] or '').startswith(case['expected'][0]['authoring']) for a in audio['added'])
    report = {'index_build_fingerprint': retriever.manifest['build_fingerprint'], 'limit': args.limit, 'audio_case': audio}
    for name, path in (('tuned_cases', CASES), ('holdout', HOLDOUT)):
        cases = json.loads(path.read_text(encoding='utf-8'))['cases']
        report[name] = {variant: score(retriever, cases, related, matches, args.limit, links)
                        for variant, links in (('all_links', LINKS), ('source_refs_only', ('forward', 'backward')),
                                               ('series_only', ('series',)))}
    retriever.client.close()
    print(json.dumps({'audio_case': audio, **{n: {v: r['summary'] for v, r in report[n].items()} for n in ('tuned_cases', 'holdout')}},
                     indent=1))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
