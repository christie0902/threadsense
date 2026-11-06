"""Re-ground one work item of a saved overnight run from its recorded generations, with prepared wording edits.

The recorded draft, revision and ToT outputs are replayed (advisor_pilot.ReplayClient); `--edits` replaces named
strings in one recorded generation, each checked against the text it expects to replace. The final grounding request
is the only request that could be sent:

- default (zero calls): the request is built and counted exactly as the live client would send it (RequestGuard's
  count against the input-token limit), the deterministic checks run on the edited text, and the plan is printed;
- `--run --write <new path>` (paid, one request): the grounding request goes to the live model; every other stage
  stays the recorded output, and the result records the edits and their provenance.

  uv run --locked python scripts/reground_topic.py --run-dir data/experiments/threadsense_full_v1_consolidated_refresh_v1 \
      --work consolidated:consolidated_90b29c234158a34b --edits <edits.json>
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
EDITS_CONTRACT = 'agent3-generation-edits-v1'


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_edits(raw, edits):
    """The recorded generation with each edit applied; refuses an edit whose current text is not the expected one."""
    value = copy.deepcopy(raw)
    for edit in edits:
        node = value
        for key in edit['path'][:-1]:
            node = node[key]
        if node[edit['path'][-1]] != edit['expected']:
            raise SystemExit(f"Edit at {edit['path']} does not match the recorded text; refusing.")
        node[edit['path'][-1]] = edit['text']
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--edits', type=Path, help=f'{EDITS_CONTRACT} file (none: re-ground the recorded generations as they are).')
    parser.add_argument('--run', action='store_true', help='Send the one grounding request (paid).')
    parser.add_argument('--write', type=Path, help='New path for the result (with --run).')
    args = parser.parse_args(argv)
    if args.run and (not args.write or args.write.exists()):
        parser.error('--run needs --write with a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.agents import advisor_pilot as pilot, overnight
    from threadsense.agents.advisor_contracts import GroundingJudgment
    from threadsense.agents.advisor_evidence import Budget
    from threadsense.severity_rubric import load_rubric
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    replay_script, measure = _script('replay_overnight_topic'), _script('measure_revision_request')
    edits = (json.loads(args.edits.read_text(encoding='utf-8')) if args.edits else
             {'contract': EDITS_CONTRACT, 'work_id': args.work, 'stage': None, 'edits': [], 'provenance': 'RECORDED_GENERATIONS_UNCHANGED'})
    if edits.get('contract') != EDITS_CONTRACT or edits['work_id'] != args.work:
        parser.error('The edits file is not for this work item.')
    manifest = json.loads((args.run_dir/'run_manifest.json').read_text(encoding='utf-8'))
    fp = manifest['fingerprints']
    settings = fp['semantic_client']['settings']
    retriever = overnight.open_snapshot(ROOT/(fp['index'].get('index_dir') or '.index/retrieval'))
    if retriever.manifest['build_fingerprint'] != fp['index']['build_fingerprint']:
        parser.error('The recorded snapshot is no longer the one at that path.')
    view = replay_script.recorded_view(args.run_dir)
    item = next(w for w in overnight.plan(view) if w['work_id'] == args.work)
    scenario = {'id': args.work, 'candidate_group_id': item['candidate_group_id'], 'focus': item['topic_name'],
                **({'topic_id': item['topic_id']} if item['topic_id'] else {}),
                **({'consolidated_topic_id': item['topic_id']} if item['kind'] == 'CONSOLIDATED_TOPIC' else {})}
    captured, live = {}, None
    if args.run:
        settings_now = _script('run_agent3_overnight').live_settings()
        if settings_now['model'] != settings['model']:
            parser.error('The live model differs from the recorded run.')
        prices = pilot.model_prices(settings_now['model'])
        per_request = settings_now['input_token_limit'] * prices['input'] + settings_now['max_completion_tokens_per_call'] * prices['output']
        live = pilot.CrewAIClient(settings_now, ledger=pilot.CostLedger(per_request))

    class Regrounding(pilot.ReplayClient):
        label = 'REGROUND_RECORDED_GENERATIONS'

        def complete(self, stage, payload, schema):
            if stage == edits['stage']:
                value = apply_edits(json.loads(pilot._json_text(self.recorded[payload['scenario_id']]['raw'][stage])), edits['edits'])
                self.recorded[payload['scenario_id']]['raw'][stage] = json.dumps(value, ensure_ascii=False)
            if stage == 'grounding':
                captured.update(payload=payload, schema=schema)
                if live is None:
                    raise pilot.RecordedFailure('RESOURCE', 'grounding request measured offline; not sent')
                return live.complete(stage, payload, schema)
            return super().complete(stage, payload, schema)
    client = Regrounding(args.run_dir)
    try:
        result = pilot.advise(scenario, view=view, retriever=retriever, client=client, budget=Budget(overnight.PER_TOPIC),
                              rubric=load_rubric(None), run_id=manifest['run_id'], as_of=retriever.manifest['cutoff'])
    finally:
        retriever.client.close()
    if not captured:
        print(json.dumps({'work_id': args.work, 'grounding_requested': False, 'card_line': result['card']['card_line']}, indent=1))
        return 1
    tokens = measure.count(measure.exact_request(captured['payload'], captured['schema'], settings)['messages'])
    prices = pilot.model_prices(settings['model'])
    edited = {e['statement_id'] for e in edits['edits']}
    sent = {s['statement_id']: s for s in captured['payload']['statements']}
    rejected = (result.get('grounding') or {}).get('rejected') or {}
    plan = {'work_id': args.work, 'requests': 1, 'stage': 'grounding', 'model': settings['model'],
            'input_tokens': tokens, 'input_token_limit': settings['input_token_limit'], 'fits': tokens <= settings['input_token_limit'],
            'hard_cost_usd': round(settings['input_token_limit'] * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output'], 4),
            'cost_at_measured_input_usd': round(tokens * prices['input'] + settings['max_completion_tokens_per_call'] * prices['output'], 4),
            'statements_sent': len(sent), 'edited_statements_sent': sorted(edited & set(sent)),
            'edited_statements_rejected_before_sending': {k: v for k, v in rejected.items() if k in edited},
            'edits_provenance': edits['provenance']}
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    if args.run:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps({'plan': plan, 'edits': edits, 'usage': live.ledger.entries, 'result': result},
                                         ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
