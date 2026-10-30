"""Milestone 7 demonstration, offline (zero model calls): a TL decision reaches a later overnight run.

1. Save a TL decision through the dashboard API on the live smoke run's audio card (operational namespace), at the
   real current time, into a NEW decision store.
2. Build a NEW retrieval snapshot whose cutoff is after the save and not in the future (real embedding model, offline).
3. Run the Advisor through the overnight graph on that snapshot (scripted judgments, audio topic only). The handoff's
   discussions are labelled a replay of an earlier handoff; no Slack activity is invented for the new window.
4. Report whether the decision is in the topic's saved evidence, with its approval, execution and outcome states.

  uv run --locked python scripts/run_feedback_loop_demo.py --write data/experiments/agent3_feedback_loop_offline_v1
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', type=Path, required=True, help='New output directory (summary, overnight run).')
    parser.add_argument('--store', type=Path, help='New decision store (default <write>/decision_store.sqlite3).')
    parser.add_argument('--snapshot', type=Path, help='New snapshot directory (default .index/retrieval_feedback_<time>).')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.write.exists():
        parser.error(f'{args.write} exists; write to a new directory.')
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    from fastapi.testclient import TestClient
    from threadsense.agents import overnight
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decision_sources import build_snapshot
    from threadsense.dashboard.decisions import DecisionStore, now_iso
    from threadsense.dashboard.runs import Catalog
    from threadsense.handoff_inputs import read_json
    from threadsense.retrieval.embeddings import SentenceEncoder
    from threadsense.routing import ROOT
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    store_path = args.store or args.write/'decision_store.sqlite3'
    snapshot = args.snapshot or ROOT/f'.index/retrieval_feedback_{stamp}'
    if store_path.exists() or snapshot.exists():
        parser.error('The store and snapshot must be new.')
    args.write.mkdir(parents=True)
    store = DecisionStore(store_path)
    catalog = Catalog()
    run = catalog.get('agent3_overnight_smoke_v1')
    card = next(c for c in run.cards.values() if c['project_id'] == 'audio_multimodal')
    # A simulated approval: demo namespace, never operational, although the card itself is live-model output.
    client = TestClient(create_app(catalog=catalog, store=store, static_dir=args.write/'no-static', decision_origin='DEMO_SCRIPT'))
    reply = client.post(f"/api/runs/{run.key}/cards/{card['card_id']}/decisions", headers={'Idempotency-Key': f'demo-{stamp}'},
                        json={'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING',
                              'note': 'Send the consolidated playback report; ask whether the batch-05 reload trial applies.'})
    if reply.status_code != 201:
        parser.error(f'Save failed: {reply.json()}')
    decision = reply.json()['entry']
    cutoff = now_iso()  # After the save; never in the future.
    built = build_snapshot(store, snapshot, cutoff=cutoff, encoder=SentenceEncoder(), export_dir=args.write/'decision_exports',
                           namespaces=('demo',))  # Explicit opt-in: a demo snapshot, not an operational one.
    rt = overnight.Runtime(args.write/'overnight_run', client=overnight.HandoffScriptedClient(), cutoff=cutoff,
                           only=['audio_playback'], index_dir=snapshot)
    overnight.run(rt)
    topic = next(read_json(p) for p in (args.write/'overnight_run'/'topics').glob('*.json'))
    ledger = topic['result']['evidence_ledger']
    found = [{k: e[k] for k in ('evidence_id', 'use', 'recorded_states', 'dates', 'excerpt')}
             for e in ledger.values() if ((e.get('citation') or {}).get('authoring') or '').startswith('tl-decision-')]
    trace = [{k: s.get(k) for k in ('step', 'purpose', 'query', 'version_mode', 'result_ids')} for s in topic['result']['retrieval_trace']]
    brief = read_json(args.write/'overnight_run'/'morning_brief.json')
    summary = {
        'model_calls': 0, 'decision': {k: decision[k] for k in ('entry_id', 'recorded_at', 'kind', 'namespace', 'decision_origin',
                                                               'judgment_provenance',
                                                               'run_key', 'run_instance', 'card_id')},
        'decision_record_states': {'tl_response': decision['decision']['tl_response']['outcome'],
                                   'execution': decision['decision']['execution']['state'],
                                   'outcome': decision['decision']['outcome']['state']},
        'snapshot': {k: built[k] for k in ('index_dir', 'cutoff', 'build_fingerprint', 'decisions_indexed', 'namespaces',
                                           'current_day_announcements', 'prior_announcements')},
        'overnight_run': {'dir': (args.write/'overnight_run').as_posix(), 'run_id': brief['run_id'], 'status': brief['status'],
                          'snapshot': brief['snapshot'], 'handoff_activity': brief['handoff_activity'],
                          'card_line': topic['result']['card']['card_line'], 'semantic_source': topic['workflow']['semantic_source']},
        'decision_in_topic_evidence': found, 'retrieval_trace': trace,
        'note': ('Scripted judgments were prepared against the October 2 index, so statements citing evidence IDs that this '
                 'snapshot does not return stay unjudged; the card shows only what passed. The point here is retrieval.'),
    }
    (args.write/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('decision', 'decision_record_states', 'snapshot')}
                     | {'decision_found': bool(found), 'uses': [f['use'] for f in found]}, ensure_ascii=False, indent=1))
    return 0 if found else 1


if __name__ == '__main__':
    sys.exit(main())
