"""Offline replay of a saved model comparison or single live run through the current pipeline (zero model calls).

Each arm's recorded draft, revision and ToT outputs are fed back unchanged; a recorded grounding verdict is reused
only where the statement's kind, text, evidence and attributions and the full evidence context are unchanged (ACTION
and ALTERNATIVE statements with premises are not reused; see advisor_pilot.ReplayClient). Every judgment the current
pipeline needs that was not recorded (for example sufficiency or source agreement) is PENDING, never invented.

  --source DIR     a comparison directory (experiment.json with "arms") or a single run such as
                   data/experiments/agent3_acceptance_v1 (experiment.json with "arm"); default: the comparison
  (default)        print the per-case summary; nothing is written
  --write DIR      also write each arm to DIR/<arm>/ (a single run: to DIR/) and DIR/replay_summary.json (a new directory)
"""
import argparse
import json
from pathlib import Path
import sys

SOURCE = Path('data/experiments/agent3_model_comparison_v1')


def summarize(run):
    rows = []
    for r in run['results']:
        card, g = r.get('card') or {}, r.get('grounding') or {}
        verdicts = {s['statement_id']: s['verdict'] for s in g.get('statements', [])}
        rows.append({'case': r['scenario']['id'], 'card_line': card.get('card_line'), 'grounding': g.get('status'),
                     'basis': g.get('basis'), 'pending': g.get('pending', []),
                     'action_proposed': ((r.get('drafts') or {}).get('final') or {}).get('proposed_action', {}) and
                     r['drafts']['final']['proposed_action']['action_type'],
                     'action_verdict': verdicts.get('action'), 'action_on_card': (card.get('recommended_action') or {}).get('action_type'),
                     'severity': f"{card['severity']['level']} {card['severity']['assessment_status']}" if card else None,
                     'severity_issues': (r.get('severity') or {}).get('issues'), 'severity_notes': (r.get('severity') or {}).get('notes'),
                     'resolution': card.get('resolution_status'),
                     'normalization': [d for d in r.get('diagnostics', []) if d['code'] in ('ROLE_LABEL_CORRECTED', 'RECURRENCE_RECLASSIFIED')],
                     'rejected': g.get('rejected'), 'action_source': r.get('action_source'), 'action_notes': r.get('action_notes'),
                     'temporal': [(f['code'], f['status']) for f in (r.get('temporal') or {}).get('findings', [])],
                     'model_calls': [(c['stage'], c['status']) for c in r.get('model_calls', [])]})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--write', type=Path, help='New output directory.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; write to a new directory.')
    from threadsense.agents import advisor_pilot as pilot
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import open_retriever
    from threadsense.handoff_inputs import read_json
    experiment = read_json(args.source/'experiment.json')
    retriever, view = open_retriever(), load_effective_view(pilot.HANDOFF)
    single = 'arms' not in experiment  # A single run: its results sit directly under the source directory.
    arms = {experiment['arm']: args.source} if single else {arm: args.source/arm for arm in experiment['arms']}
    cases = {p.stem for p in (args.source/'results').glob('*.json')} if single else set(experiment['cases'])
    spec = {'scenarios': [s for s in read_json(pilot.SCENARIOS)['scenarios'] if s['id'] in cases]}
    summary = {'source': args.source.as_posix(), 'pilot_version': pilot.PILOT_VERSION, 'prompts_now': pilot.prompt_fingerprints(),
               'prompts_recorded': experiment['prompts'], 'pilot_version_recorded': experiment.get('pilot_version'),
               'model_calls': 0, 'arms': {}}
    for arm, source in arms.items():
        client = pilot.ReplayClient(source)
        run = pilot.run_pilot(client=client, retriever=retriever, view=view, scenarios=spec,
                              budget_limits=experiment['budget'] if single else experiment['budget_per_arm'])
        summary['arms'][arm] = {'cases': summarize(run), 'reused_verdicts': run['manifest']['replay']['reused_verdicts'],
                                'not_reused': run['manifest']['replay']['pending_or_not_reused']}
        if args.write:
            pilot.write_outputs(args.write if single else args.write/arm, run)
    text = json.dumps(summary, ensure_ascii=False, indent=1)
    if args.write:
        args.write.mkdir(parents=True, exist_ok=True)
        (args.write/'replay_summary.json').write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
