"""Full ThreadSense run (Agent 1 -> grouping -> Agent 2 -> Agent 3) under one budget ledger and response store.

  preflight [--write FILE]                   zero calls: scope, wiring checks on frozen inputs, cost estimate by agent
  live --write DIR --run --max-cost USD      PAID: a new immutable run (hard ceiling in its ledger)
  resume DIR                                 continue the same run; answered requests are served, interrupted ones never resent
  replay --source DIR --write NEW            network disabled: re-execute every stage from saved responses
  branch --source DIR --write NEW [--run --max-cost USD]
                                             selective recomputation: unchanged requests are served from the source run,
                                             changed ones are sent (only with --run)
  render DIR                                 network disabled: load the run's briefing through the real dashboard

Model calls happen only with live/branch --run (and resume of a live run). Every request is reserved, persisted and
settled in DIR/ledger.sqlite3; DIR/objects holds exact request bodies and raw responses.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
HARD_CEILING = 39.0
TARGET = 30.0
# Historical usage behind the estimates (frozen runs; only the token profile is reused, never their results).
HISTORY = {
    'agent1_interpret': {'source': 'proxy: data/processed/agent1_verified_v3 revision_1 calls (same model, same thread inputs)',
                         'per_item': {'gpt-4o-mini-2024-07-18': (2800, 700)}, 'requests_per_item': 1.0},
    'agent1_verify': {'source': 'data/processed/agent1_verified_v3 (593 calls over 200 threads; usage from raw responses)',
                      'per_item': {'gpt-4.1': (804168 / 200, 337137 / 200), 'gpt-4o-mini-2024-07-18': (298516 / 200, 21643 / 200)},
                      'requests_per_item': 593 / 200, 'max_calls_per_item': 4,
                      'caps': [('gpt-4.1', 6144), ('gpt-4.1', 16384), ('gpt-4o-mini-2024-07-18', 4096), ('gpt-4.1', 16384)]},
    'agent2': {'source': 'data/experiments/agent2_taxonomy_final_v7/request_ledger.json (90 groups)',
               'per_item': {'gpt-5.4-2026-03-05': (69193 / 90, 11856 / 90)}, 'requests_per_item': 1.0,
               'caps': [('gpt-5.4-2026-03-05', 8192)]},
    'agent3': {'source': 'agent3_e2e_eval_v1 and agent3_v18_acceptance_v1 (16 work items, 33 requests, $1.80 at the input rate)',
               'per_item_usd_observed': (0.933 + 0.863) / 16, 'input_tokens_per_item': (204234 + 193733) / 16,
               'requests_per_item': 33 / 16},
}


def preflight():
    from threadsense.execution import pricing
    from threadsense.execution import pipeline as p
    from threadsense.source_ingestion import interpretation_threads
    threads, announcements, routing = interpretation_threads(p.FIXTURE, cutoff=p.CUTOFF, channels=None)
    eligible = len(threads)
    # Fresh grouping and taxonomy counts are only known after Agent 1; the estimate uses the last discussion-only
    # handoff (81 groups, 87 work items) with a margin, and is labelled as an estimate.
    groups_est, work_est = 81, 87
    margin = 1.25
    rows = []

    def cost(model, tin, tout):
        r = pricing.rates(model)
        return tin * r['input'] + tout * r['output']
    h = HISTORY['agent1_interpret']
    per = sum(cost(m, *t) for m, t in h['per_item'].items())
    rows.append({'agent': 'Agent 1 interpretation', 'model': p.ENV['THREADSENSE_MODEL'], 'work': f'{eligible} discussion threads',
                 'expected_requests': eligible, 'expected_input_tokens': eligible * 2800, 'expected_usd': eligible * per,
                 'exposure_usd': eligible * pricing.reservation('gpt-4o-mini-2024-07-18', 4000, 4096), 'basis': h['source']})
    h = HISTORY['agent1_verify']
    per = sum(cost(m, *t) for m, t in h['per_item'].items())
    worst = sum(pricing.reservation(m, 3000, cap) for m, cap in h['caps'])
    rows.append({'agent': 'Agent 1 verification', 'model': f"{p.ENV['THREADSENSE_VERIFIER_MODEL']} + {p.ENV['THREADSENSE_MODEL']} (revision)",
                 'work': f'{eligible} threads, at most 4 calls each', 'expected_requests': round(eligible * h['requests_per_item']),
                 'expected_input_tokens': round(eligible * sum(t[0] for t in h['per_item'].values())),
                 'expected_usd': eligible * per, 'exposure_usd': eligible * worst, 'basis': h['source']})
    h = HISTORY['agent2']
    per = sum(cost(m, *t) for m, t in h['per_item'].items())
    rows.append({'agent': 'Agent 2 taxonomy', 'model': f"{p.AGENT2_MODEL} (reasoning low)", 'work': f'~{groups_est} groups (estimate)',
                 'expected_requests': groups_est, 'expected_input_tokens': round(groups_est * 769),
                 'expected_usd': groups_est * per, 'exposure_usd': groups_est * pricing.reservation(p.AGENT2_MODEL, 1500, 8192),
                 'basis': h['source']})
    h = HISTORY['agent3']
    write_extra = h['input_tokens_per_item'] * (pricing.PRICES['gpt-6.1-sol']['cache_write'] - pricing.PRICES['gpt-6.1-sol']['input'])
    per = h['per_item_usd_observed'] + write_extra
    rows.append({'agent': 'Agent 3 advisor', 'model': 'openai/gpt-6.1-sol (medium reasoning, default tier)',
                 'work': f'~{work_est} work items (estimate), at most {p.AGENT3_PER_TOPIC} requests each',
                 'expected_requests': round(work_est * h['requests_per_item']), 'expected_input_tokens': round(work_est * h['input_tokens_per_item']),
                 'expected_usd': work_est * per, 'exposure_usd': work_est * p.AGENT3_PER_TOPIC * p.agent3_reservation(),
                 'basis': h['source'] + '; uncached input re-priced as 30-minute cache writes'})
    expected = sum(r['expected_usd'] for r in rows)
    for r in rows:
        r['expected_usd'], r['exposure_usd'] = round(r['expected_usd'], 2), round(r['exposure_usd'], 2)
    return {'scope': {'fixture': p.FIXTURE.relative_to(ROOT).as_posix(), 'cutoff': p.CUTOFF, 'source_threads': routing['input_threads'],
                      'discussion_threads': eligible, 'announcements_bypassing_agent1': len(announcements)},
            'by_agent': rows, 'expected_total_usd': round(expected, 2),
            'expected_total_with_margin_usd': round(expected * margin, 2), 'margin': margin,
            'conservative_exposure_usd': round(sum(r['exposure_usd'] for r in rows), 2),
            'hard_ceiling_usd': HARD_CEILING, 'target_usd': TARGET,
            'remaining_after_expected_usd': round(HARD_CEILING - expected, 2),
            'enforced': 'Only the ledger ceiling is enforced: each request reserves its maximum charge before sending and '
                        'is refused if it cannot fit. Estimates and exposure are not limits.',
            'fits_target': expected * margin <= TARGET,
            'prices_verified': pricing.VERIFIED, 'fee_rate': pricing.FEE_RATE,
            'batch_api': 'Not used: Agent 1 runs dependent per-thread stages through fingerprinted runners and Agent 2 one '
                         'synchronous request per group; batching would change those transports for <$0.2 (Agent 2) of savings.',
            'prompt_caching': 'Automatic provider caching; reads recorded as savings, Sol writes charged at 1.25x input.'}


def wiring_checks():
    """Zero-call checks that every stage's entry point accepts the run's inputs (frozen inputs as stand-ins, labelled)."""
    import contextlib
    import io
    import tempfile
    from threadsense.execution import pipeline as p
    out = {}
    batch = p.load_script('run_agent1_batch')
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out['agent1_interpret_dry_run_exit'] = batch.main(['--dry-run', '--limit', '0', '--fixture-root', str(p.FIXTURE)])
    out['agent1_interpret_selected'] = next((l for l in buf.getvalue().splitlines() if l.startswith('Selected')), None)
    from threadsense.source_ingestion import interpretation_threads
    with tempfile.TemporaryDirectory(dir='D:/tsb' if Path('D:/tsb').is_dir() else None) as tmp:
        view = Path(tmp)/'view'
        out['agent1_verify_source_view_channels'] = len(p.discussion_view(p.FIXTURE, view))
        eligible = {(t.project_id, t.batch_id, t.channel_id, t.thread_id)
                    for t in interpretation_threads(p.FIXTURE, cutoff=p.CUTOFF, channels=None)[0]}
        out['agent1_verify_source_view_equals_routed_discussions'] = p.discussion_identities(view) == eligible
        out['agent1_verify_source_view_threads'] = len(eligible)
    from threadsense.handoff_inputs import CANONICAL, GROUPING
    from threadsense.topic_inputs import load_candidate_payloads
    payloads = load_candidate_payloads(grouping_path=GROUPING, canonical_path=CANONICAL)
    out['agent2_payloads_from_frozen_inputs'] = len(payloads)
    out['agent3_reservation_per_request_usd'] = round(p.agent3_reservation(), 5)
    return out


def open_run(path, mode, *, limit=None, parents=()):
    from threadsense.execution.guard import Execution
    from threadsense.execution.pipeline import Run
    ex = Execution(path, mode=mode, limit_usd=limit, parents=parents)
    return Run(path, ex)


def start(path, mode, limit, parents=(), label='FRESH_LIVE', pipeline=None):
    """pipeline: threadsense-full-run-v2 for new live runs; a replay or branch keeps its parent's pipeline."""
    from threadsense.execution import pipeline as p
    if pipeline is None:
        pipeline = (p.read_json(Path(parents[0])/'run_manifest.json')['configuration'].get('pipeline', p.PIPELINE_V1)
                    if parents else p.PIPELINE_V2)
    if path.exists():
        raise SystemExit(f'{path} exists; every run writes a new directory (use resume).')
    path.mkdir(parents=True)
    p.write_json(path/'run_manifest.json', {'kind': label, 'mode': mode, 'parents': [str(x) for x in parents], 'created_at': p.now(),
                                            'hard_ceiling_usd': limit, 'target_usd': TARGET, 'configuration': p.configuration(pipeline),
                                            'checkout': p.checkout()})
    return open_run(path, mode, limit=limit, parents=parents)


def go(run):
    from threadsense.execution.guard import Guard
    from threadsense.execution import pipeline as p
    stale = run.ex.ledger.recover()
    if stale:
        print(f'{len(stale)} request(s) from an interrupted process are UNCERTAIN (charged in full, never resent).')
    try:
        with Guard(run.ex):
            result = p.execute(run)
    finally:
        p.write_json(run.dir/'ledger_summary.json', run.ex.ledger.summary())
    print(json.dumps({'stages': result, 'ledger': run.ex.ledger.summary()}, indent=1, ensure_ascii=False))
    return 0 if all(r.get('status', 'COMPLETE') == 'COMPLETE' for r in result) and len(result) == len(run.stages) else 1


def render(path):
    """Load the run's Agent 3 output through the real dashboard (FastAPI TestClient) with the network disabled."""
    import tempfile
    from fastapi.testclient import TestClient
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.runs import Catalog
    from threadsense.execution.guard import Execution, Guard
    with tempfile.TemporaryDirectory() as tmp:
        ex = Execution(Path(tmp)/'render', mode='REPLAY', limit_usd=0.0)
        with Guard(ex):
            catalog = Catalog([path/'stages'/'agent3'])
            client = TestClient(create_app(catalog=catalog, store=DecisionStore(Path(tmp)/'d.sqlite3'), decision_origin='TEST',
                                           static_dir=Path(tmp)/'none'))
            brief = client.get('/api/runs/overnight_run/brief')
            cards = brief.json()['cards']
            statuses = {client.get(f"/api/runs/overnight_run/cards/{c['card']['card_id']}").status_code for c in cards}
        ex.close()
    report = {'brief_status': brief.status_code, 'cards': len(cards), 'card_endpoint_statuses': sorted(statuses),
              'network': 'disabled (sockets to non-loopback hosts refused)'}
    print(json.dumps(report, indent=1))
    return report


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    pf = sub.add_parser('preflight')
    pf.add_argument('--write', type=Path)
    lv = sub.add_parser('live')
    lv.add_argument('--write', type=Path, required=True)
    lv.add_argument('--run', action='store_true')
    lv.add_argument('--max-cost', type=float, required=True)
    rs = sub.add_parser('resume')
    rs.add_argument('run_dir', type=Path)
    rs.add_argument('--reason', help='Recorded with the resume when the checkout changed since the run started.')
    rp = sub.add_parser('replay')
    rp.add_argument('--source', type=Path, required=True)
    rp.add_argument('--write', type=Path, required=True)
    br = sub.add_parser('branch')
    br.add_argument('--source', type=Path, required=True)
    br.add_argument('--write', type=Path, required=True)
    br.add_argument('--run', action='store_true')
    br.add_argument('--max-cost', type=float, default=0.0)
    rd = sub.add_parser('render')
    rd.add_argument('run_dir', type=Path)
    args = parser.parse_args(argv)
    from threadsense.agents import advisor_pilot as pilot
    for k, v in pilot.QUIET_ENV.items():
        os.environ.setdefault(k, v)
    if args.command == 'preflight':
        report = {'estimate': preflight(), 'wiring': wiring_checks()}
        print(json.dumps(report, indent=1, ensure_ascii=False))
        if args.write:
            from threadsense.execution.pipeline import write_json
            write_json(args.write, report)
        return 0
    if args.command == 'live':
        if not args.run:
            parser.error('live needs --run (paid model calls).')
        if args.max_cost > HARD_CEILING:
            parser.error(f'--max-cost may not exceed the authorized ${HARD_CEILING}.')
        return go(start(args.write, 'LIVE', args.max_cost))
    if args.command == 'resume':
        from threadsense.execution import pipeline as p
        saved = p.read_json(args.run_dir/'run_manifest.json')
        if saved['configuration'] != p.configuration(saved['configuration'].get('pipeline', p.PIPELINE_V1)):
            parser.error('Semantic configuration changed since this run started; use branch for a new run.')
        current = p.checkout()
        if saved['checkout']['combined_sha256'] != current['combined_sha256'] or saved.get('resumes'):
            # Same models, prompts, schemas and inputs (checked above); an orchestration change is recorded, not hidden.
            saved.setdefault('resumes', []).append({'at': p.now(), 'checkout': current, 'reason': args.reason or 'not given'})
            p.write_json(args.run_dir/'run_manifest.json', saved)
        return go(open_run(args.run_dir, saved['mode'], parents=[Path(x) for x in saved['parents']]))
    if args.command == 'replay':
        return go(start(args.write, 'REPLAY', 0.0, parents=[args.source], label='REPLAY'))
    if args.command == 'branch':
        if args.run and args.max_cost <= 0:
            parser.error('branch --run needs --max-cost.')
        return go(start(args.write, 'LIVE' if args.run else 'REPLAY', args.max_cost, parents=[args.source], label='BRANCH'))
    if args.command == 'render':
        render(args.run_dir)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
