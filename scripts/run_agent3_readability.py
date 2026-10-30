"""Agent 3 Milestone 4 readability verification (pilot v6): audio playback and Submit failure, once, on the acceptance arm.

Pilot v6 changes what the model writes (team lead-facing summary, instruction, rationale, copyable draft, review note;
writing guide and two STYLE ONLY examples; no IDs in display text) and raises the input cap to 24,000 tokens, which the
closeout run's audio and Submit revisions exceeded at 20,000. The zero-call replay of the closeout responses
(data/experiments/agent3_closeout_replay_v1) cannot verify new wording, so these two scenarios run once.

Default (no flags): zero model calls. Prints the request settings, list prices and the reservation per request.

  --run --write DIR   PAID: one run through the CrewAI Agent/Task path; DIR/experiment.json holds the cost ledger.

Limits: the acceptance arm (gpt-6.1-sol, medium reasoning, standard tier, 16,384 generated tokens, 24,000 input tokens per
request checked on the exact body, 120 s timeout, zero retries, no fallback); 4 requests per scenario, 8 in total; a $2.00
experiment budget with each request's maximum cost reserved before it is sent (worst case of all 8 requests: about $1.69).
Failures are kept, never rerun.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

SCENARIOS = ('audio_playback', 'submit_failure')
BUDGET = {'model_calls_per_topic': 4, 'model_calls_total': 8, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 12}
COST_LIMIT_USD = 2.00


def acceptance():
    spec = importlib.util.spec_from_file_location('acceptance', Path(__file__).with_name('run_agent3_acceptance.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        parser.error(f'{args.write} exists; write the readability run to a new directory.')
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import StaleIndexError, open_retriever
    from threadsense.handoff_inputs import read_json
    accepted = acceptance()
    arm = accepted.ARM
    settings = pilot.live_settings(**accepted.comparison_arms()[arm])
    prices = pilot.model_prices(settings['model'])
    per_request = settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output']
    worst = round(per_request * BUDGET['model_calls_total'], 4)
    if worst > COST_LIMIT_USD:
        print(f'Refused: worst case ${worst} exceeds ${COST_LIMIT_USD}.', file=sys.stderr)
        return 2
    try:
        retriever = open_retriever()
    except StaleIndexError as error:
        print(f'Refused: {error}', file=sys.stderr)
        return 2
    view = load_effective_view(pilot.HANDOFF)
    spec = {'scenarios': [s for s in read_json(pilot.SCENARIOS)['scenarios'] if s['id'] in SCENARIOS]}
    config = {'arm': arm, 'settings': settings, 'prices_per_token': prices, 'budget': BUDGET, 'scenarios': list(SCENARIOS),
              'cost_limit_usd': COST_LIMIT_USD, 'reservation_per_request_usd': round(per_request, 6),
              'worst_case_all_requests_usd': round(per_request * BUDGET['model_calls_total'], 4),
              'binding_limit': 'request count (worst case within the ledger)', 'prompts': pilot.prompt_fingerprints(),
              'pilot_version': pilot.PILOT_VERSION, 'baseline_run': 'data/experiments/agent3_closeout_v1',
              'index': {k: retriever.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
              'handoff_canonical_sha256': view['canonical_sha256']}
    if not args.run:
        print(json.dumps({**config, 'model_calls': 0}, ensure_ascii=False, indent=1))
        return 0
    ledger = pilot.CostLedger(COST_LIMIT_USD)
    client = pilot.CrewAIClient(settings, ledger=ledger)
    run = pilot.run_pilot(client=client, retriever=retriever, view=view, scenarios=spec, budget_limits=BUDGET)
    pilot.write_outputs(args.write, run)
    experiment = {**config, 'cost_ledger': ledger.summary(), 'http_requests': run['manifest']['http_requests'],
                  'halted': repr(client.halted) if client.halted else None}
    (args.write/'experiment.json').write_text(json.dumps(experiment, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: experiment[k] for k in ('http_requests', 'halted')}, indent=1))
    print(f"Spent ${ledger.spent_usd:.4f} of ${COST_LIMIT_USD:.2f}. Wrote {args.write}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
