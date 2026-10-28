"""Canonical Agent 2 preflight/preparation and explicitly bounded live pilot."""
import argparse
from collections import Counter
from pathlib import Path

from threadsense.config import get_model_settings
from threadsense.handoff_inputs import ROOT, CANONICAL, GROUPING, read_json, file_hash, identity, digest
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_consolidation import build_request
from threadsense.agents.topic_pipeline import execute_batch, configuration
from threadsense.terminology import get_terms

def select_pilot(payloads, path, model):
    pilot = read_json(path)
    if pilot['schema_version'] != 2 or pilot['canonical_sha256'] != file_hash(CANONICAL) or pilot['grouping_sha256'] != file_hash(GROUPING):
        raise ValueError('Pilot inputs changed; inspect the prepared selection.')
    if pilot['model'] != model:
        raise ValueError('Configured model differs from the prepared pilot.')
    ids = [case['candidate_group_id'] for case in pilot['cases']]
    by_id = {p['candidate_group_id']:p for p in payloads}
    if len(set(ids)) != len(ids) or not set(ids) <= set(by_id):
        raise ValueError('Pilot has duplicate or unknown groups.')
    selected = [by_id[gid] for gid in ids]
    if not selected or len(selected) != pilot['maximum_request_attempts']:
        raise ValueError('Pilot request bound differs from selection.')
    if pilot['configuration_sha256'] != digest(configuration(selected, model)):
        raise ValueError('Pilot code/configuration changed; inspect the changes, then use '
                         'scripts/prepare_agent2_pilot.py to prepare a new offline pilot. '
                         'Keep the original pilot and use new output paths.')
    return selected, pilot['maximum_request_attempts']

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true', help='One paid attempt per selected pilot group; zero retries.')
    mode.add_argument('--prepare', action='store_true', help='Write exact requests and pending handoff; zero calls.')
    mode.add_argument('--dry-run', action='store_true', help='Read-only inspection (default).')
    parser.add_argument('--limit', type=int, default=0, help='Offline selection size; 0 means all.')
    parser.add_argument('--pilot', type=Path, help='Evidence-bound prepared pilot selection.')
    parser.add_argument('--max-requests', type=int, help='Explicit live request ceiling; must match the pilot.')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data/processed/agent2_discussions_v8_offline')
    args = parser.parse_args(argv)
    if args.limit < 0 or (args.pilot and args.limit):
        parser.error('Use a nonnegative limit, or a pilot selection, not both.')
    if args.run and not args.pilot:
        parser.error('Live execution requires the prepared --pilot selection and --max-requests.')
    try:
        payloads = load_candidate_payloads()
        model, _ = get_model_settings()
        if args.pilot:
            selected, ceiling = select_pilot(payloads, args.pilot, model)
        else:
            selected, ceiling = (payloads[:args.limit] if args.limit else payloads), None
        if args.run and args.max_requests != ceiling:
            raise ValueError('--max-requests must equal the prepared pilot bound.')
        for payload in selected:
            build_request(payload, get_terms(), model)
        members = [m for p in selected for m in p['members']]
        print(f"Canonical coverage: {sum(len(p['members']) for p in payloads)} inputs in {len(payloads)} groups.")
        print(f"Selected: {len(selected)} groups, {len(members)} identities, {sum(m['agent1_record']['review_required'] for m in members)} inherited review obligations.")
        print('Member statuses:', dict(Counter(m['agent1_record']['verification_status'] for m in members)))
        if not (args.run or args.prepare):
            print('Dry run: no model calls or writes.')
            return 0
        result = execute_batch(selected, args.output_dir, run=args.run, maximum_requests=ceiling)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"State: {result['state']}; attempts: {result['new_request_attempts']}; unprocessed groups: {result['unprocessed_groups']}")
    counts = result['processing_counts']
    print('Processing outcomes: ' + ', '.join(
        f"{state}={counts.get(state, 0)}" for state in ('CONSOLIDATED', 'FAILED', 'INTERRUPTED', 'NOT_RUN')))
    print(f"Saved responses: {result['available_response_records']}; unknown completions: {len(result['unknown_completion_requests'])}")
    return 1 if result['state'] in {'failed', 'interrupted'} else 0

if __name__ == '__main__':
    raise SystemExit(main())
