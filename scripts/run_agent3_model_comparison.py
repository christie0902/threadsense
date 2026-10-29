"""Agent 3 Milestone 4: bounded model comparison on three pilot cases (small; not a benchmark).

Default (no flags): zero model calls. Prints each arm's request settings, list prices, the
worst-case cost reservation and each case's first-request size.

  --run --write DIR   PAID: both arms, same prompts, schemas, corpus, index and initial retrieval;
                      each arm writes DIR/<arm>/; DIR/experiment.json holds the shared cost ledger.

Limits: 4 requests per case, 12 per arm, 24 in total; a $3.00 application budget across both
arms, with each request's maximum cost reserved before it is sent; 20,000 input tokens per
request; zero retries; no model fallback. Failures are kept as results and never rerun.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ARMS = {
    'gpt-4o-mini': {'model': 'openai/gpt-4o-mini', 'temperature': 0, 'max_completion_tokens': 4096},
    # Reasoning model: temperature is not sent; the output limit includes reasoning tokens.
    'gpt-6.1-sol': {'model': 'openai/gpt-6.1-sol', 'temperature': None, 'reasoning_effort': 'medium',
                    'service_tier': 'default', 'max_completion_tokens': 16384},
}
CASES = ('audio_playback', 'json_vs_prose', 'repeated_ending')
BUDGET_PER_ARM = {'model_calls_per_topic': 4, 'model_calls_total': 12, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 18}
MAX_REQUESTS = 24
COST_LIMIT_USD = 3.00


def worst_case(settings, prices, requests):
    return requests * (settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output'])


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
        parser.error(f'{args.write} exists; write each experiment to a new directory.')
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import StaleIndexError, open_retriever
    from threadsense.handoff_inputs import read_json
    spec = {'scenarios': [s for s in read_json(pilot.SCENARIOS)['scenarios'] if s['id'] in CASES]}
    arms = {name: pilot.live_settings(**cfg) for name, cfg in ARMS.items()}
    prices = {name: pilot.model_prices(s['model']) for name, s in arms.items()}
    per_arm = BUDGET_PER_ARM['model_calls_total']
    reservation = {name: round(worst_case(arms[name], prices[name], per_arm), 4) for name in arms}
    if sum(reservation.values()) > COST_LIMIT_USD or per_arm * len(arms) > MAX_REQUESTS:
        print(f'Refused: worst case {reservation} exceeds ${COST_LIMIT_USD} or {MAX_REQUESTS} requests.', file=sys.stderr)
        return 2
    try:
        retriever = open_retriever()
    except StaleIndexError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    view = load_effective_view(pilot.HANDOFF)
    config = {'cases': list(CASES), 'arms': arms, 'prices_per_token': prices, 'budget_per_arm': BUDGET_PER_ARM,
              'max_requests': MAX_REQUESTS, 'cost_limit_usd': COST_LIMIT_USD, 'worst_case_reservation_usd': reservation,
              'prompts': pilot.prompt_fingerprints(), 'pilot_version': pilot.PILOT_VERSION,
              'index': {k: retriever.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
              'handoff_canonical_sha256': view['canonical_sha256']}
    if not args.run:
        planned = pilot.plan(retriever=retriever, view=view, scenarios=spec)
        print(json.dumps({**config, 'model_calls': 0, 'cases_planned': [
            {k: s[k] for k in ('id', 'status', 'initial_query', 'draft_prompt_tokens_estimate')} for s in planned['scenarios']]},
            ensure_ascii=False, indent=1))
        return 0
    ledger = pilot.CostLedger(COST_LIMIT_USD)
    args.write.mkdir(parents=True)
    runs = {}
    for name, settings in arms.items():  # Same retriever, view, cases and prompts; no tuning between arms.
        client = pilot.CrewAIClient(settings, ledger=ledger)
        runs[name] = pilot.run_pilot(client=client, retriever=retriever, view=view, scenarios=spec, budget_limits=BUDGET_PER_ARM)
        pilot.write_outputs(args.write/name, runs[name])
    initial = {name: {r['scenario']['id']: r['retrieval_trace'][0]['result_ids'] for r in run['results']} for name, run in runs.items()}
    sent = {name: run['manifest']['http_requests'] for name, run in runs.items()}
    experiment = {**config, 'cost_ledger': ledger.summary(), 'http_requests': sent,
                  'total_requests': sum(v['sent'] for v in sent.values()),
                  'identical_initial_retrieval': len({json.dumps(v, sort_keys=True) for v in initial.values()}) == 1,
                  'initial_retrieval': initial}
    (args.write/'experiment.json').write_text(json.dumps(experiment, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: experiment[k] for k in ('total_requests', 'http_requests', 'identical_initial_retrieval')}, indent=1))
    print(f"Spent ${ledger.spent_usd:.4f} of ${COST_LIMIT_USD:.2f}. Wrote {args.write}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
