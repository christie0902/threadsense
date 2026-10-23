"""Refresh Agent 2 candidates locally from finalized Agent 1; zero paid calls."""
import argparse
from pathlib import Path
from threadsense.handoff_inputs import ROOT, CANONICAL, load_handoff
from threadsense.topic_grouping import approved_grouping, refresh_grouping

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Compute local embeddings and write a new grouping directory.')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data/processed/grouping_agent1_v3')
    args = parser.parse_args(argv)
    members = load_handoff(CANONICAL)
    _, baseline = approved_grouping()
    print(f"Canonical inputs: {len(members)}; review obligations: {sum(m['agent1_record']['review_required'] for m in members)}")
    print(f"Approved threshold: {baseline['config']['distance_threshold']}; local CPU embedding model unchanged.")
    if not args.write:
        print('Dry run: no embeddings computed or files written.')
        return 0
    result = refresh_grouping(args.output_dir)
    print(f"Wrote {result['cluster_count']} groups; {result['singleton_count']} singletons; all {result['thread_count']} identities assigned once.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
