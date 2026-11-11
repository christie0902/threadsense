"""Build a reviewer-feedback snapshot: the confirmed, opted-in corrections a later Agent 3 run may receive as context.

Zero model calls. Default: plan only (what would be included or excluded, and why). --write FILE writes the snapshot
(a new file; an existing file is accepted only if it is byte-identical). The snapshot is computed from the feedback
events recorded at or before --cutoff, so a later withdrawal or supersession changes later snapshots only. Pass the
file to `scripts/run_agent3_overnight.py --feedback-snapshot FILE`; its cutoff may not be later than the run cutoff.

  uv run --locked python scripts/build_feedback_snapshot.py --cutoff 2026-11-10T12:00:00Z
  uv run --locked python scripts/build_feedback_snapshot.py --cutoff 2026-11-10T12:00:00Z --write .state/dashboard/feedback_snapshots/fb_20261110.json
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    from threadsense.dashboard.decisions import STORE_PATH
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cutoff', required=True, help='Snapshot cutoff (ISO 8601, timezone required; not in the future).')
    parser.add_argument('--decision-db', type=Path, default=STORE_PATH, help='Dashboard store holding the feedback events.')
    parser.add_argument('--namespace', action='append', choices=('operational', 'demo', 'test'),
                        help='Feedback namespaces to include (repeatable; default operational: feedback on live runs).')
    parser.add_argument('--write', type=Path, help='Write the snapshot to this new file.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.dashboard.decisions import DecisionStore, now_iso
    from threadsense.dashboard.feedback import build_snapshot
    from threadsense.routing import aware
    if aware(args.cutoff) > aware(now_iso()):
        parser.error(f'Cutoff {args.cutoff} is in the future; feedback recorded later would fall inside it.')
    if not args.decision_db.is_file():
        parser.error(f'No dashboard store at {args.decision_db}.')
    snapshot = build_snapshot(DecisionStore(args.decision_db).feedback(), cutoff=args.cutoff,
                              namespaces=tuple(args.namespace or ('operational',)))
    summary = {'cutoff': snapshot['cutoff'], 'namespaces': snapshot['namespaces'], 'snapshot_sha256': snapshot['snapshot_sha256'],
               'corrections': [{k: c[k] for k in ('feedback_id', 'category', 'confirmed_at')} | {'project_id': c['scope']['project_id'],
                               'threads': len(c['scope']['threads'])} for c in snapshot['corrections']],
               'excluded': snapshot['excluded']}
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
