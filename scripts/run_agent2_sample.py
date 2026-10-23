"""Inspect one finalized candidate; --run permits one request with no repair."""
import argparse
from threadsense.config import get_model_settings, get_api_key
from threadsense.handoff_inputs import ROOT
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_consolidation import validate_input, validate_output
from threadsense.agents.topic_pipeline import execute_batch

OUTPUT = ROOT/'data/processed/agent2_sample_v2/consolidations.json'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='One request maximum; no retries/repairs.')
    parser.add_argument('--group-id', help='Choose a refreshed candidate; default is first stable group.')
    args = parser.parse_args(argv)
    try:
        if args.run:
            _, key_name = get_model_settings()
            get_api_key(key_name)
        payloads = load_candidate_payloads()
        payload = next((p for p in payloads if p['candidate_group_id'] == args.group_id), None) if args.group_id else payloads[0]
        if payload is None:
            raise ValueError('Unknown candidate group ID.')
        members = validate_input(payload)
        print(f"Input OK: {len(members)} threads; candidate {payload['candidate_group_id']}")
        if not args.run:
            print('Preflight passed. No API calls or writes.')
            return 0
        result = execute_batch([payload], OUTPUT.parent, run=True, maximum_requests=1)
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    return int(result['state'] in {'failed','interrupted'})

if __name__ == '__main__':
    raise SystemExit(main())
