"""Prepare/preflight a paired freeze; --run executes exactly one authorized arm."""
import argparse
from pathlib import Path
from threadsense.agents.topic_comparison import prepare_comparison, preflight_comparison, run_arm


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--arm', choices=['A','B'])
    parser.add_argument('--max-requests', type=int)
    args = parser.parse_args(argv)
    if args.run and (args.arm is None or args.max_requests != 6):
        parser.error('--run requires --arm A/B and --max-requests 6.')
    if not args.run and (args.arm is not None or args.max_requests is not None):
        parser.error('Preparation/preflight inspect both arms; arm/budget flags belong to --run.')
    try:
        if args.prepare:
            freeze = prepare_comparison(args.experiment)
            print(f"Prepared both arms; 0 calls. Estimate USD {freeze['cost_estimates']['estimated_total_usd']:.4f}.")
        elif args.run:
            result = run_arm(args.experiment,args.arm,args.max_requests)
            print(f"Arm {args.arm}: {result['processing_counts']}; attempts={result['new_request_attempts']}; unprocessed={result['unprocessed_groups']}")
            return int(result['state'] in {'failed','interrupted'})
        else:
            freeze, selected = preflight_comparison(args.experiment)
            print('Both frozen arms valid: same 6 groups, 18 identities, 5 inherited obligations per arm; 0 calls.')
        return 0
    except (ValueError,RuntimeError,OSError,KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
