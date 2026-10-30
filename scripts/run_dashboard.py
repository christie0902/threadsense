"""Serve the morning-brief dashboard (FastAPI API + the built React app in web/dist) on localhost.

No model calls, no Slack posting. Reads overnight run directories (data/experiments/*/morning_brief.json) and,
with --include-test-fixtures, the labelled dashboard fixture runs. TL decisions are written only to the decision
store (default .state/dashboard/tl_decisions.sqlite3, ignored by git).

  uv run --locked python scripts/run_dashboard.py                  # http://127.0.0.1:8000
  npm --prefix web run dev                                         # frontend dev server (proxies /api to :8000)
"""
import argparse
from pathlib import Path
import sys


def main(argv=None):
    from threadsense.dashboard.decisions import STORE_PATH
    from threadsense.dashboard.runs import RUN_ROOTS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--runs', type=Path, action='append', help='Run root directory (repeatable; default data/experiments).')
    parser.add_argument('--include-test-fixtures', action='store_true',
                        help='Also list the labelled dashboard fixture runs (tests/fixtures/dashboard_runs).')
    parser.add_argument('--decision-db', type=Path, default=STORE_PATH, help='SQLite decision store (created if missing).')
    args = parser.parse_args(argv)
    if args.host not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('The dashboard has no authentication; serve it on localhost only.')
    import uvicorn
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.runs import Catalog
    app = create_app(catalog=Catalog(args.runs or RUN_ROOTS, include_fixtures=args.include_test_fixtures),
                     store=DecisionStore(args.decision_db))
    print(f'Decision store: {args.decision_db}', flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')
    return 0


if __name__ == '__main__':
    sys.exit(main())
