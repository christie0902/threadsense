"""Agent 3 Milestone 4 acceptance pilot: the six handoff scenarios plus the payroll control, once, with gpt-6.1-sol.

Default (no flags): zero model calls. Prints the request settings, list prices, the worst-case cost reservation and
each scenario's first-request size.

  --run --write DIR   PAID: one run through the CrewAI Agent/Task path; DIR/experiment.json holds the cost ledger.

Limits: 4 requests per scenario, 28 in total; a $6.00 experiment budget with each request's maximum cost reserved before
it is sent; 20,000 input tokens per request (checked on the exact request body); 16,384 generated tokens per request,
reasoning included; the existing 120 s timeout; zero retries; no model fallback. A configuration rejection or an
exhausted budget stops further requests (every scenario still gets its card). Failures are kept, never rerun.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ARM = 'gpt-6.1-sol'
BUDGET = {'model_calls_per_topic': 4, 'model_calls_total': 28, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 42}
MAX_REQUESTS = 28
COST_LIMIT_USD = 6.00


def comparison_arms():
    import importlib.util
    spec = importlib.util.spec_from_file_location('comparison', Path(__file__).with_name('run_agent3_model_comparison.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ARMS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', action='store_true', help='Live model calls (paid).')
    parser.add_argument('--write', type=Path, help='New output directory for --run.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    if args.run and not args.write:
        parser.error('--run needs --write DIR (a new directory).')
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; write the acceptance run to a new directory.')
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import StaleIndexError, open_retriever
    settings = pilot.live_settings(**comparison_arms()[ARM])
    prices = pilot.model_prices(settings['model'])
    per_request = settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output']
    worst = round(per_request * BUDGET['model_calls_total'], 4)
    if worst > COST_LIMIT_USD or BUDGET['model_calls_total'] > MAX_REQUESTS:
        print(f'Refused: worst case ${worst} exceeds ${COST_LIMIT_USD} or {MAX_REQUESTS} requests.', file=sys.stderr)
        return 2
    try:
        retriever = open_retriever()
    except StaleIndexError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    view = load_effective_view(pilot.HANDOFF)
    config = {'arm': ARM, 'settings': settings, 'prices_per_token': prices, 'budget': BUDGET, 'max_requests': MAX_REQUESTS,
              'cost_limit_usd': COST_LIMIT_USD, 'worst_case_reservation_usd': worst,
              'reservation_per_request_usd': round(per_request, 6), 'prompts': pilot.prompt_fingerprints(),
              'pilot_version': pilot.PILOT_VERSION,
              'index': {k: retriever.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
              'handoff_canonical_sha256': view['canonical_sha256']}
    if not args.run:
        planned = pilot.plan(retriever=retriever, view=view)
        print(json.dumps({**config, 'model_calls': 0, 'scenarios_planned': [
            {k: s[k] for k in ('id', 'status', 'draft_prompt_tokens_estimate')} for s in planned['scenarios']]},
            ensure_ascii=False, indent=1))
        return 0
    ledger = pilot.CostLedger(COST_LIMIT_USD)
    client = pilot.CrewAIClient(settings, ledger=ledger)
    run = pilot.run_pilot(client=client, retriever=retriever, view=view, budget_limits=BUDGET)
    pilot.write_outputs(args.write, run)
    experiment = {**config, 'cost_ledger': ledger.summary(), 'http_requests': run['manifest']['http_requests'],
                  'halted': repr(client.halted) if client.halted else None}
    (args.write/'experiment.json').write_text(json.dumps(experiment, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: experiment[k] for k in ('http_requests', 'halted')}, indent=1))
    print(f"Spent ${ledger.spent_usd:.4f} of ${COST_LIMIT_USD:.2f}. Wrote {args.write}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
