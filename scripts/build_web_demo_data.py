"""Snapshot the dashboard API for one saved run into a JSON bundle for the static web demo (`npm run build:demo`).

Every GET response the UI can request for that run is recorded through the real FastAPI app over an empty, throwaway
decision store: run list, brief, card details, flags, AI-feedback context, evidence entries and thread views (followed
until no new evidence or thread link appears), the review queue, decisions and lessons. No model calls, no network.
The run directory is only read. Read-only by default (prints the plan); --write saves the bundle.

  uv run --locked python scripts/build_web_demo_data.py [--run threadsense_full_v1_combined_v2] [--write web/demo/briefing.json]
"""
import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.routing import ROOT

DEFAULT_RUN = 'threadsense_full_v1_combined_v2'
CONTRACT = 'threadsense-web-demo-v1'
TEAM_LEAD = 'U006'
# Nothing machine-specific or secret may reach a public bundle. Checked on the serialized JSON text, where a literal
# backslash is written as two (so an escaped newline after a colon is not a drive path).
FORBIDDEN = [re.compile(p) for p in (r'(?<![A-Za-z])[A-Za-z]:(\\\\|/)(?!/)', r'/Users/', r'/home/', r'sk-[A-Za-z0-9]{12,}',
                                       r'OPENAI_API_KEY', r'OPENROUTER_API_KEY', r'\.env\b', r'Christie')]
# Some upstream records name their export file by absolute path; the public copy names it relative to the repository.
ROOT_PREFIXES = sorted({f'{ROOT}\\', f'{ROOT}/', f'{ROOT.as_posix()}/'}, key=len, reverse=True)


def relative_paths(value, count):
    if isinstance(value, str):
        for prefix in ROOT_PREFIXES:
            if prefix.lower() in value.lower():
                count[0] += 1
                value = re.sub(re.escape(prefix), '', value, flags=re.IGNORECASE)
        return value
    if isinstance(value, dict):
        return {k: relative_paths(v, count) for k, v in value.items()}
    if isinstance(value, list):
        return [relative_paths(v, count) for v in value]
    return value


def links(value, found):
    """Evidence IDs and (channel, thread) pairs referenced anywhere in a response."""
    if isinstance(value, dict):
        if isinstance(value.get('evidence_id'), str):
            found['evidence'].add(value['evidence_id'])
        if value.get('kind') == 'evidence' and isinstance(value.get('id'), str):
            found['evidence'].add(value['id'])
        if value.get('kind') == 'thread' and value.get('channel') and value.get('thread'):
            found['threads'].add((value['channel'], value['thread']))
        if isinstance(value.get('channel_id'), str) and isinstance(value.get('thread_id'), str):
            found['threads'].add((value['channel_id'], value['thread_id']))
        for v in value.values():
            links(v, found)
    elif isinstance(value, list):
        for v in value:
            links(v, found)


def snapshot(run_key, roots):
    catalog = Catalog(roots)
    run = catalog.get(run_key)
    catalog.runs = {run.key: run}  # Only the presentation run is listed.
    with tempfile.TemporaryDirectory() as tmp:
        store = DecisionStore(Path(tmp)/'demo.sqlite3')
        client = TestClient(create_app(catalog=catalog, store=store, static_dir=Path(tmp)/'none',
                                       decision_origin='DEMO_SCRIPT', session_actor=TEAM_LEAD))
        responses = {}

        def get(path):
            r = client.get(path)
            responses[path] = {'status': r.status_code, 'body': r.json()}
            return r.status_code == 200 and r.json()

        base = f'/api/runs/{quote(run_key)}'
        for path in ('/api/runs', f'{base}/brief', f'{base}/decisions', f'{base}/review-queue', f'{base}/feedback',
                     '/api/lessons', f'{base}/negative-examples'):
            get(path)
        found = {'evidence': set(), 'threads': set()}
        for item in responses[f'{base}/brief']['body']['cards']:
            cid = item['card']['card_id']
            for path in (f'{base}/cards/{cid}', f'{base}/cards/{cid}/flags', f'{base}/cards/{cid}/feedback'):
                get(path)
        done = {'evidence': set(), 'threads': set()}
        while True:
            for body in [r['body'] for r in responses.values()]:
                links(body, found)
            todo_e, todo_t = found['evidence'] - done['evidence'], found['threads'] - done['threads']
            if not todo_e and not todo_t:
                break
            for e in sorted(todo_e):
                get(f'{base}/evidence/{quote(e, safe="")}')
            for c, t in sorted(todo_t):
                get(f'{base}/threads/{c}/{t}')
            done['evidence'] |= todo_e
            done['threads'] |= todo_t
    return run, responses, done


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', default=DEFAULT_RUN)
    parser.add_argument('--runs', type=Path, action='append', help='Run root (default data/experiments).')
    parser.add_argument('--write', type=Path, help='Write the bundle here (for example web/demo/briefing.json).')
    args = parser.parse_args()
    run, responses, done = snapshot(args.run, args.runs or [ROOT/'data/experiments'])
    rewritten = [0]
    responses = relative_paths(responses, rewritten)
    bundle = {'contract_version': CONTRACT, 'run_key': run.key, 'run_instance': run.instance, 'team_lead': TEAM_LEAD,
              'note': 'Synthetic presentation data: saved GET responses of the local dashboard API for one run.',
              'absolute_paths_made_relative': rewritten[0], 'responses': dict(sorted(responses.items()))}
    text = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    leaks = sorted({m.group(0) for p in FORBIDDEN for m in p.finditer(text)})
    statuses = {}
    for r in responses.values():
        statuses[r['status']] = statuses.get(r['status'], 0) + 1
    print(f'run {run.key} ({run.instance}): {len(responses)} responses {statuses}; {len(done["evidence"])} evidence, '
          f'{len(done["threads"])} threads; {rewritten[0]} absolute paths made relative; {len(text) / 1e6:.2f} MB; sha256 {hashlib.sha256(text.encode()).hexdigest()[:16]}')
    if leaks:
        print(f'Refused: machine-specific or secret-looking text in the bundle: {leaks}', file=sys.stderr)
        return 1
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding='utf-8')
        print(f'wrote {args.write}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
