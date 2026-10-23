"""Inspect or save one canonical candidate; never overwrite historical Agent 2 inputs."""
import argparse
from pathlib import Path
from threadsense.handoff_inputs import ROOT
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_pipeline import write_json

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group-id')
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'data/processed/agent2_candidate_input_v2.json')
    args = parser.parse_args(argv)
    payloads = load_candidate_payloads()
    payload = next((p for p in payloads if p['candidate_group_id'] == args.group_id), None) if args.group_id else payloads[0]
    if payload is None:
        parser.error('Unknown candidate group ID.')
    print(f"Loaded {len(payloads)} candidates from the finalized handoff; selected {payload['candidate_group_id']} ({len(payload['members'])} members).")
    if args.write:
        write_json(args.output, payload, exclusive=True)
        print(f'Saved: {args.output}')
    else:
        print('Read-only inspection. Use --write to save a new input file.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
