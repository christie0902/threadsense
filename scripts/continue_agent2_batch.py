"""Continue never-started Agent 2 groups in a new directory; never retry old attempts."""
import argparse
from pathlib import Path
import runpy

from threadsense.config import get_model_settings
from threadsense.handoff_inputs import ROOT
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_continuation import inspect_run, continue_batch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true', help='One paid attempt per never-started group.')
    mode.add_argument('--prepare', action='store_true', help='Save a combined offline snapshot; zero calls.')
    mode.add_argument('--dry-run', action='store_true', help='Read-only inspection (default).')
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--pilot', type=Path, required=True, help='The original full selection, not a subset.')
    parser.add_argument('--max-requests', type=int, help='Exact remaining request count, required with --run.')
    parser.add_argument('--output-dir', type=Path, help='New combined export directory.')
    args = parser.parse_args(argv)
    if (args.run or args.prepare) and not args.output_dir:
        parser.error('--output-dir is required for --run/--prepare; use a new directory.')
    try:
        payloads = load_candidate_payloads()
        model, _ = get_model_settings()
        runner = runpy.run_path(str(ROOT / 'scripts/run_agent2_batch.py'))
        selected, _ = runner['select_pilot'](payloads, args.pilot, model)
        info = inspect_run(args.source_dir, selected, model)
        print(f"Original selection: {len(selected)} groups, {sum(len(p['members']) for p in selected)} identities.")
        print(f"Saved attempts: {info['prior_request_attempts']}; responses: {info['available_responses']}; "
              f"unknown completion: {len(info['unknown'])}.")
        print(f"Never-started groups available to continue: {len(info['remaining'])}. No old attempt will be retried.")
        if not (args.run or args.prepare):
            print('Dry run: no model calls or writes.')
            return 0
        result = continue_batch(selected, args.source_dir, args.output_dir,
                                run=args.run, maximum_requests=args.max_requests)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"State: {result['state']}; new attempts this continuation: {result['continued_request_attempts']}; "
          f"cumulative attempts: {result['new_request_attempts']}; unprocessed: {result['unprocessed_groups']}.")
    return 1 if result['state'] in {'failed', 'interrupted'} else 0


if __name__ == '__main__':
    raise SystemExit(main())
