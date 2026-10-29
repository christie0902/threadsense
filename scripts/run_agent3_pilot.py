"""Agent 3 Advisor pilot (Milestone 4).

Default (no flags): zero model calls. Checks index freshness once, builds the topic
packets and shows each topic's initial retrieval, the size of its first request, the
call budget and the live model/request configuration.

  --scripted FILE --write DIR   offline run; semantic judgments come from FILE (SCRIPTED_MOCK)
  --run --write DIR             live run through CrewAI: PAID model calls (see THREADSENSE_MODEL);
                                at most 4 per topic and 28 per run, one HTTP request each

Outputs go to a new directory only. Nothing else is written.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--scripted', type=Path, help='Prepared semantic responses (offline, no model calls).')
    parser.add_argument('--run', action='store_true', help='Live model calls (paid).')
    parser.add_argument('--write', type=Path, help='New output directory for a scripted or live run.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')  # Topic text includes Korean; Windows consoles default to cp1252.
    from threadsense.agents import advisor_pilot
    for name, value in advisor_pilot.QUIET_ENV.items():  # Before CrewAI/LiteLLM load.
        os.environ.setdefault(name, value)
    from threadsense.agents.advisor_evidence import StaleIndexError
    if args.run and args.scripted:
        parser.error('Choose --run or --scripted, not both.')
    if (args.run or args.scripted) and not args.write:
        parser.error('--run and --scripted need --write DIR (a new directory).')
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; pilot runs write to a new directory.')
    try:
        if not (args.run or args.scripted):
            planned = advisor_pilot.plan()
            print(json.dumps({**planned, 'live_configuration': advisor_pilot.live_settings()}, ensure_ascii=False, indent=1))
            return 0
        client = advisor_pilot.CrewAIClient() if args.run else advisor_pilot.ScriptedClient(args.scripted)
        run = advisor_pilot.run_pilot(client=client)
    except StaleIndexError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    out = advisor_pilot.write_outputs(args.write, run)
    print(json.dumps(run['manifest'], ensure_ascii=False, indent=1))
    print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
