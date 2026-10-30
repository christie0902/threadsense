"""Build a NEW retrieval snapshot that includes saved TL decisions, at an explicit later cutoff.

Zero model calls. Default: plan only (which decisions would be included, which are after the cutoff). --build
exports the decisions (derived Markdown, existing ingestion path) and builds the snapshot into --index-dir, which
must not be the active index (.index/retrieval). Decisions recorded after --cutoff are excluded and reported,
never backdated. Indexing status is recorded per decision in the store; a failed build leaves decisions unchanged.

  uv run --locked python scripts/build_decision_snapshot.py --cutoff 2026-10-31T12:00:00Z --index-dir .index/retrieval_tl_20261031
  uv run --locked python scripts/build_decision_snapshot.py --cutoff 2026-10-31T12:00:00Z --index-dir .index/retrieval_tl_20261031 --build
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    from threadsense.dashboard.decision_sources import EXPORT_DIR
    from threadsense.dashboard.decisions import STORE_PATH
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cutoff', required=True, help='Snapshot cutoff (ISO 8601, timezone required).')
    parser.add_argument('--index-dir', type=Path, required=True, help='New snapshot directory (not .index/retrieval).')
    parser.add_argument('--decision-db', type=Path, default=STORE_PATH)
    parser.add_argument('--export-dir', type=Path, default=EXPORT_DIR)
    parser.add_argument('--build', action='store_true', help='Export and build (otherwise plan only).')
    parser.add_argument('--rebuild', action='store_true', help='Replace a snapshot built from different sources.')
    parser.add_argument('--allow-download', action='store_true', help='Permit fetching the pinned embedding model (setup only).')
    args = parser.parse_args(argv)
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.routing import aware
    aware(args.cutoff)
    if not args.decision_db.is_file():
        parser.error(f'No decision store at {args.decision_db}.')
    store = DecisionStore(args.decision_db)
    entries = store.all_card_decisions()
    included = [e for e in entries if aware(e['recorded_at']) <= aware(args.cutoff)]
    if not args.build:
        print(json.dumps({'cutoff': args.cutoff, 'decisions': len(entries), 'would_include': len(included),
                          'after_cutoff': [e['entry_id'] for e in entries if e not in included],
                          'indexing': {k: v['status'] for k, v in store.indexing().items()}}, indent=2))
        return 0
    from threadsense.dashboard.decision_sources import build_snapshot
    from threadsense.retrieval.embeddings import SentenceEncoder
    try:
        encoder = SentenceEncoder(allow_download=args.allow_download)
    except OSError as error:
        parser.error(f'Embedding model unavailable offline ({error}). Run once with --allow-download.')
    print(json.dumps(build_snapshot(store, args.index_dir, cutoff=args.cutoff, encoder=encoder, export_dir=args.export_dir,
                                    rebuild=args.rebuild), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
