"""Evaluate retrieval on the labelled cases (BM25-only, dense-only, RRF, RRF + MMR). Read-only.

Uses the built index and the local embedding model offline. --report writes the full
JSON to a new path; nothing else is written.
"""
import argparse
import json
from pathlib import Path
import sys

from threadsense.retrieval.config import INDEX_DIR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-dir', type=Path, default=INDEX_DIR)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--report', type=Path, help='New path for the full JSON report.')
    parser.add_argument('--mmr-lambda', type=float, help='Override MMR lambda for this evaluation only (default: retrieval DEFAULTS, 0.9).')
    parser.add_argument('--summary-only', action='store_true')
    parser.add_argument('--holdout', action='store_true', help='Evaluate the separate holdout cases instead.')
    args = parser.parse_args(argv)
    if args.report and args.report.exists():
        parser.error('--report must be a new path.')
    from threadsense.retrieval.evaluate import CASES, HOLDOUT, evaluate
    from threadsense.retrieval.search import Retriever
    cases = json.loads((HOLDOUT if args.holdout else CASES).read_text(encoding='utf-8'))['cases']
    report = evaluate(Retriever(args.index_dir), cases, top_k=args.top_k, mmr_lambda=args.mmr_lambda)
    for case in [] if args.summary_only else report['cases']:
        print(f"\n{case['id']}: {case['query']}")
        for name, v in case['variants'].items():
            recall = '-' if v['recall'] is None else f"{v['recall']:.2f}"
            print(f"  {name:15} recall={recall} first={v['first_relevant_rank']} | " + ', '.join(v['top']))
            if v['must_exclude_violations']:
                print(f"  {'':15} MUST-EXCLUDE VIOLATION: {v['must_exclude_violations']}")
    print('\nLegend: R relevant, C acceptable context, D misleading near-match, X must be excluded, - unlabelled')
    print(json.dumps(report['summary'], indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
