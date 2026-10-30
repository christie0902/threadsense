"""Milestone 5 overnight Agent 3 workflow (LangGraph over the existing CrewAI Advisor).

Default (no --write/--resume): zero model calls. Loads and validates the handoff, extracts the window's announcements,
checks the retrieval snapshot, and prints the work plan, the worst-case request/cost reservation and the graph.

  --scripted --write DIR      offline run of every in-scope work item with scripted judgments (SCRIPTED_MOCK)
  --run --write DIR           PAID: live Sol run; needs --max-requests and --max-cost (run-wide limits)
  --resume DIR                continue an interrupted run; options come from DIR/run_manifest.json and inputs must be
                              unchanged; completed topics are reused, the spent budget is kept
  --release WORK_ID           with --resume: explicitly process an interrupted topic again (its earlier request may
                              have been sent and charged)
  --only ID                   restrict to work items (work ID, topic ID or pilot scenario ID); repeatable

The run cutoff is explicit and must equal the retrieval snapshot's cutoff. Per topic: at most 4 model calls (one HTTP
request each, zero retries), 6 retrievals, 24,000 input tokens per request. Every run writes a new directory.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ARM = 'gpt-6.1-sol'


def live_settings():
    from threadsense.agents import advisor_pilot as pilot
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).with_name('run_agent3_model_comparison.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return pilot.live_settings(**module.ARMS[ARM])


def build_runtime(out, mode, *, cutoff, only, max_requests, max_cost, release=(), index_dir=None):
    from threadsense.agents import advisor_pilot as pilot
    from threadsense.agents import overnight
    if mode == 'LIVE':
        settings = live_settings()
        prices = pilot.model_prices(settings['model'])
        per_request = settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output']
        ledger = overnight.PersistentLedger(max_cost, per_request)
        client = pilot.CrewAIClient(settings, ledger=ledger)
        return overnight.Runtime(out, client=client, cutoff=cutoff, only=only, max_requests=max_requests, ledger=ledger,
                                 mode=mode, release=release, settings=settings, index_dir=index_dir or overnight.INDEX_DIR)
    return overnight.Runtime(out, client=overnight.HandoffScriptedClient(), cutoff=cutoff, only=only,
                             max_requests=max_requests, mode=mode, release=release, index_dir=index_dir or overnight.INDEX_DIR)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cutoff', help='Run cutoff (ISO 8601 with Z); the window is the 24 hours before it.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--scripted', action='store_true')
    group.add_argument('--run', action='store_true', help='Live model calls (paid).')
    parser.add_argument('--write', type=Path, help='New run directory.')
    parser.add_argument('--resume', type=Path, help='Existing run directory to continue.')
    parser.add_argument('--only', action='append', help='Work ID, topic ID or pilot scenario ID (repeatable).')
    parser.add_argument('--max-requests', type=int, help='Run-wide HTTP request ceiling.')
    parser.add_argument('--max-cost', type=float, help='Run-wide dollar budget (live).')
    parser.add_argument('--release', action='append', default=[], help='With --resume: reprocess this interrupted work ID.')
    parser.add_argument('--index-dir', type=Path, help='Retrieval snapshot (default .index/retrieval); its cutoff must equal '
                        '--cutoff. A resume always uses the snapshot recorded in the run manifest.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    from threadsense.agents import overnight
    from threadsense.handoff_inputs import read_json
    if args.resume:
        if args.write or args.scripted or args.run or args.only or args.max_requests or args.max_cost or args.cutoff or args.index_dir:
            parser.error('--resume takes its options from the run manifest; pass only --release.')
        saved = read_json(args.resume/'run_manifest.json')['fingerprints']
        if not saved['index'].get('index_dir'):
            parser.error('This run predates recorded snapshot paths; it cannot be resumed safely. Start a new run directory.')
        rt = build_runtime(args.resume, saved['mode'], cutoff=saved['cutoff'], only=saved['only'],
                           max_requests=saved['budget_limits']['model_calls_total'], max_cost=saved['cost_limit_usd'],
                           release=args.release, index_dir=overnight.ROOT/saved['index']['index_dir']
                           if not Path(saved['index']['index_dir']).is_absolute() else Path(saved['index']['index_dir']))
    else:
        if not args.cutoff:
            parser.error('--cutoff is required (the run window is explicit).')
        if args.release:
            parser.error('--release only applies with --resume.')
        if args.write and args.write.exists():
            parser.error(f'{args.write} exists; every run writes a new directory (use --resume to continue one).')
        if (args.scripted or args.run) and not args.write:
            parser.error('--scripted/--run need --write DIR.')
        if args.run and (args.max_requests is None or args.max_cost is None):
            parser.error('--run needs --max-requests and --max-cost.')
        mode = 'LIVE' if args.run else 'SCRIPTED'
        if not args.write:  # Zero-call plan.
            return plan_only(args, overnight, pilot)
        if args.run:
            settings = live_settings()
            prices = pilot.model_prices(settings['model'])
            per_request = settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output']
            if per_request * overnight.REQUESTS_TO_START > args.max_cost:
                parser.error(f'--max-cost ${args.max_cost} cannot cover one topic (two reservations of ${per_request:.4f}).')
        rt = build_runtime(args.write, mode, cutoff=args.cutoff, only=args.only, max_requests=args.max_requests,
                           max_cost=args.max_cost, index_dir=args.index_dir)
    try:
        state = overnight.run(rt)
    except overnight.OvernightError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    brief = rt.brief
    print(json.dumps({'status': brief['status'], 'run_id': brief['run_id'], 'semantic_judgments': brief['semantic_judgments'],
                      'counts': brief['counts'], 'usage': brief['usage']['totals'],
                      'incomplete_work': [{k: w.get(k) for k in ('work_id', 'outcome', 'detail')} for w in brief['incomplete_work']],
                      'accounting': brief['accounting'], 'graph_state': state}, ensure_ascii=False, indent=1))
    print(f'Wrote {rt.out}')
    return 0 if brief['accounting']['status'] == 'COMPLETE' else 1


def plan_only(args, overnight, pilot):
    rt = overnight.Runtime(Path('.'), client=overnight.HandoffScriptedClient(), cutoff=args.cutoff, only=args.only,
                           index_dir=args.index_dir or overnight.INDEX_DIR)
    try:
        overnight.load_handoff(rt)
        overnight.extract_announcements(rt)
        overnight.prepare_retrieval(rt)
        rt.work = overnight.plan(rt.view, rt.only)
    except overnight.OvernightError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    finally:
        if rt.retriever is not None:
            rt.retriever.client.close()
    settings = live_settings()
    prices = pilot.model_prices(settings['model'])
    per_request = settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output']
    in_scope = [w for w in rt.work if w['in_scope']]
    worst = overnight.PER_TOPIC['model_calls_per_topic'] * len(in_scope)
    print(json.dumps({
        'model_calls': 0, 'cutoff': args.cutoff, 'window': rt.extraction['window'],
        'snapshot': {'index_dir': str(rt.index_dir), 'build_fingerprint': rt.retriever.manifest['build_fingerprint'],
                     'decision_roots': rt.retriever.manifest.get('decision_roots')},
        'handoff_activity': rt.handoff_activity,
        'handoff_members': sum(len(r['members']) for r in rt.view['records']),
        'work_items': len(rt.work), 'in_scope': len(in_scope),
        'by_kind': {k: sum(1 for w in in_scope if w['kind'] == k) for k in ('TOPIC', 'PROJECTION_GAP')},
        'window_announcements': rt.extraction['announcement_threads_in_window'],
        'window_announcements_in_snapshot': sum(o['in_retrieval_snapshot'] for o in rt.extraction['record_outcomes']),
        'live_arm': {k: settings[k] for k in ('model', 'reasoning_effort', 'service_tier', 'max_completion_tokens_per_call',
                                              'input_token_limit')},
        'worst_case': {'requests': worst, 'reservation_per_request_usd': round(per_request, 6),
                       'reservation_usd': round(worst * per_request, 2)},
        'graph': overnight.build_graph(rt).get_graph().draw_mermaid()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
