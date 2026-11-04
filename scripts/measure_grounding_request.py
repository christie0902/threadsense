"""Count every final grounding request of saved live overnight runs with the opt-in flag-impact context, zero calls.

Each topic is replayed through the current Advisor with flag_impact=True (recorded draft, revision and ToT outputs;
same snapshot and expansion setting). At the grounding stage the payload is captured and turned into the exact HTTP
body the live CrewAI client would send, at a fake transport (outbound sockets refused, dummy key), and counted with
RequestGuard's rule (o200k_base per message + 8). The same request without the flag context is counted too. Nothing is
sent and the input-token limit is not changed; the largest request is compared with it. Runs whose recorded snapshot
is no longer at its path are skipped and listed.

  uv run --locked python scripts/measure_grounding_request.py [--write <new path>]
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
_spec = importlib.util.spec_from_file_location('measure_revision_request', ROOT/'scripts/measure_revision_request.py')
revision = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(revision)


def live_runs():
    for path in sorted((ROOT/'data/experiments').iterdir()):
        manifest = path/'run_manifest.json'
        if manifest.is_file() and (path/'topics').is_dir():
            m = json.loads(manifest.read_text(encoding='utf-8'))
            if (m.get('fingerprints') or {}).get('semantic_client', {}).get('label') == 'CREWAI_LIVE' or \
                    (m.get('fingerprints') or {}).get('semantic_client', {}).get('settings'):
                yield path, m


def measure_run(path, manifest, retrievers):
    from threadsense.agents import advisor_pilot as pilot, overnight
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_contracts import GroundingJudgment
    from threadsense.agents.advisor_evidence import Budget
    from threadsense.severity_rubric import load_rubric
    fp = manifest['fingerprints']
    settings = fp['semantic_client']['settings']
    index = ROOT/(fp['index'].get('index_dir') or '.index/retrieval')
    retriever = retrievers.setdefault(str(index), overnight.open_snapshot(index))
    if retriever.manifest['build_fingerprint'] != fp['index']['build_fingerprint']:
        return None, 'recorded snapshot is no longer at its path'
    view = load_effective_view(ROOT/fp['handoff']['run'])
    plan = {w['work_id']: w for w in overnight.plan(view)}
    rows = []
    for topic_file in sorted((path/'topics').rglob('*.json')):
        work = json.loads(topic_file.read_text(encoding='utf-8')).get('work_item') or {}
        item = plan.get(work.get('work_id'))
        if item is None:
            continue
        scenario = {'id': item['work_id'], 'candidate_group_id': item['candidate_group_id'],
                    'focus': item['topic_name'] or 'projection gap', **({'topic_id': item['topic_id']} if item['topic_id'] else {})}
        seen = {}

        class Measuring(pilot.ReplayClient):
            def complete(self, stage, payload, schema):
                if stage == 'grounding' and not seen:
                    seen.update(payload=payload, schema=schema)
                    raise pilot.RecordedFailure('RESOURCE', 'measured offline; not sent')
                return super().complete(stage, payload, schema)
        pilot.advise(scenario, view=view, retriever=retriever, client=Measuring(path), budget=Budget(overnight.PER_TOPIC),
                     rubric=load_rubric(None), run_id=manifest['run_id'], as_of=retriever.manifest['cutoff'],
                     flag_impact=True)
        if not seen:
            rows.append({'work_id': item['work_id'], 'grounding_requested': False})
            continue
        with_flags = revision.count(revision.exact_request(seen['payload'], seen['schema'], settings)['messages'])
        plain = {k: v for k, v in seen['payload'].items() if k != 'flag_impacts'}
        plain.update(rules=pilot.GROUNDING_RULES, output_schema=pilot.sent_schema(GroundingJudgment))
        without = revision.count(revision.exact_request(plain, GroundingJudgment, settings)['messages'])
        flags = seen['payload'].get('flag_impacts') or []
        rows.append({'work_id': item['work_id'], 'grounding_requested': True, 'flags_sent': len(flags),
                     'input_tokens_with_flag_context': with_flags, 'input_tokens_without': without,
                     'flag_context_tokens': with_flags - without, 'input_token_limit': settings['input_token_limit'],
                     'fits': with_flags <= settings['input_token_limit']})
    return rows, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', type=Path, help='New path for the JSON report.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    report, skipped, retrievers = {'runs': {}}, {}, {}
    for path, manifest in live_runs():
        rows, reason = measure_run(path, manifest, retrievers)
        if rows is None:
            skipped[path.name] = reason
        else:
            report['runs'][path.name] = rows
    measured = [dict(r, run=name) for name, rows in report['runs'].items() for r in rows if r.get('grounding_requested')]
    largest = max(measured, key=lambda r: r['input_tokens_with_flag_context'], default=None)
    report.update(counter='RequestGuard: o200k_base per message + 8', requests_measured=len(measured), skipped=skipped,
                  largest=largest, all_fit=all(r['fits'] for r in measured),
                  largest_flag_context=max(measured, key=lambda r: r['flag_context_tokens'], default=None),
                  requests_per_topic='unchanged: the assessment rides on the one reserved grounding request')
    print(json.dumps({k: v for k, v in report.items() if k != 'runs'}, ensure_ascii=False, indent=1))
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
