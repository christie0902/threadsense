"""Build a lessons-from-human-review snapshot for Agent 1 and Agent 2 runs. Zero model calls.

Default: plan only (which lessons are active at --cutoff and which are left out). --write FILE writes the snapshot
(a new file; an existing file is accepted only if byte-identical). Lessons deactivated or superseded after the cutoff
are still in that cutoff's snapshot; later snapshots reflect the change. Use it with:

  uv run --locked python scripts/run_agent1_batch.py --relevance --lessons FILE ...
  uv run --locked python scripts/run_agent2_batch.py --prepare --lessons FILE ...

  uv run --locked python scripts/build_lesson_snapshot.py --cutoff 2026-11-10T12:00:00Z
  uv run --locked python scripts/build_lesson_snapshot.py --cutoff 2026-11-10T12:00:00Z --write .state/dashboard/lesson_snapshots/lessons_20261110.json
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    from threadsense.dashboard.decisions import STORE_PATH
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cutoff', required=True, help='Snapshot cutoff (ISO 8601, timezone required; not in the future).')
    parser.add_argument('--decision-db', type=Path, default=STORE_PATH, help='Dashboard store holding the lesson events.')
    parser.add_argument('--namespace', action='append', choices=('operational', 'demo', 'test'),
                        help='Lesson namespaces to include (repeatable; default operational: lessons saved on live runs).')
    parser.add_argument('--write', type=Path, help='Write the snapshot to this new file.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.dashboard.decisions import DecisionStore, now_iso
    from threadsense.dashboard.lessons import build_snapshot
    from threadsense.routing import aware
    if aware(args.cutoff) > aware(now_iso()):
        parser.error(f'Cutoff {args.cutoff} is in the future; lessons saved later would fall inside it.')
    if not args.decision_db.is_file():
        parser.error(f'No dashboard store at {args.decision_db}.')
    snapshot = build_snapshot(DecisionStore(args.decision_db).lessons(), cutoff=args.cutoff,
                              namespaces=tuple(args.namespace or ('operational',)))
    summary = {'cutoff': snapshot['cutoff'], 'namespaces': snapshot['namespaces'], 'snapshot_sha256': snapshot['snapshot_sha256'],
               'lessons': [{k: l[k] for k in ('lesson_id', 'target_agent', 'applies_to', 'project_id', 'category')}
                           for l in snapshot['lessons']], 'excluded': snapshot['excluded']}
    if not args.write:
        print(json.dumps({'plan_only': True, **summary}, indent=1, ensure_ascii=False))
        return 0
    body = (json.dumps(snapshot, indent=1, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    if args.write.exists():
        if args.write.read_bytes() != body:
            parser.error(f'{args.write} exists with different content; snapshots are immutable, choose a new file.')
    else:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        with open(args.write, 'xb') as handle:
            handle.write(body)
    print(json.dumps({'written': str(args.write), **summary}, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
