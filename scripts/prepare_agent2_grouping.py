"""Refresh Agent 2 candidates locally from finalized Agent 1; zero paid calls."""
import argparse
from pathlib import Path
from threadsense.handoff_inputs import ROOT, CANONICAL, load_routed_handoff
from threadsense.topic_grouping import approved_grouping, refresh_grouping

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Compute local embeddings and write a new grouping directory.')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data/processed/grouping_discussions_v1')
    parser.add_argument('--routing-manifest', type=Path, help='Save the complete source/eligible/announcement accounting without embeddings.')
    args = parser.parse_args(argv)
    members, announcements, routing = load_routed_handoff(CANONICAL)
    _, baseline = approved_grouping()
    print(f"Canonical inputs: {routing['input_threads']}; eligible: {len(members)}; announcement sources: {len(announcements)}")
    print(f"Discussion obligations: {sum(m['agent1_record']['review_required'] for m in members)}; announcement obligations retained: {sum(m['agent1_record']['review_required'] for m in announcements)}")
    if args.routing_manifest:
        from threadsense.agents.topic_pipeline import write_json
        write_json(args.routing_manifest,routing,exclusive=True)
    print(f"Approved threshold: {baseline['config']['distance_threshold']}; local CPU embedding model unchanged.")
    if not args.write:
        print('Zero-call inspection: no embeddings computed; only an explicitly requested routing manifest may be written.')
        return 0
    result = refresh_grouping(args.output_dir)
    print(f"Wrote {result['cluster_count']} groups; {result['singleton_count']} singletons; all {result['thread_count']} identities assigned once.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
