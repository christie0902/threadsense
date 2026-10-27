"""Export the maintained effective view, including registered review supplements. No calls."""
import argparse
from pathlib import Path
from threadsense.agents.topic_effective import load_effective_output
from threadsense.agents.topic_pipeline import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New view file; historical output is never overwritten.')
    args = parser.parse_args()
    view = load_effective_output(args.run_dir)
    write_json(args.output, view, exclusive=True)
    print(f"Effective view: {len(view['records'])} groups; {len(view['review_queue'])} requiring review; "
          f"{len(view['unapplied_findings'])} unapplied findings. Zero calls.")


if __name__ == '__main__':
    main()
