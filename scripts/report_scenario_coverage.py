"""Expected-versus-observed for the demo scenario matrix (data/evaluation/agent3_demo_scenarios.json). Read-only,
zero model calls. Reads saved runs: overnight runs (topics/*.json) and Advisor pilot runs (results/<scenario>.json).

Validation level per result: live (LIVE_MODEL), scripted (prepared pilot judgments), placeholder (judges nothing).
Checks: action within the acceptable set; required review reasons and card line present; each expected source
retrieved into the evidence ledger with the expected relation (recall is reported, not required). Severity is recorded
only (pending TL rubric decision for rule-confusion topics). "must_not" items need a reader; they are listed.

  uv run --locked python scripts/report_scenario_coverage.py --run data/experiments/agent3_overnight_smoke_v1 ... [--write <new dir>]
"""
import argparse
import json
from pathlib import Path
import sys

MATRIX = Path('data/evaluation/agent3_demo_scenarios.json')
LEVELS = {'LIVE_MODEL': 'live', 'SCRIPTED_PILOT': 'scripted', 'SCRIPTED_PLACEHOLDER': 'placeholder', 'SCRIPTED_MOCK': 'scripted'}
RELATION_USES = {'CURRENT_GUIDANCE': {'CURRENT_GUIDANCE'}, 'ANNOUNCEMENT': {'ANNOUNCEMENT', 'CURRENT_HANDLING'},
                 'PRIOR_DECISION': {'PRIOR_DECISION', 'HISTORY_ONLY'}, 'HISTORY': {'HISTORY_ONLY', 'PRIOR_DECISION'}}


def results_of(run):
    """(scenario-matching key, result, level) for every saved topic result in a run directory."""
    run = Path(run)
    if (run/'morning_brief.json').is_file():
        for path in sorted((run/'topics').rglob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('result'):
                yield data['work_item']['work_id'], data['result'], LEVELS.get(data['workflow'].get('semantic_source'), 'unknown')
    elif (run/'results').is_dir():
        manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
        level = LEVELS.get(manifest.get('semantic_judgments'), 'scripted')
        for path in sorted((run/'results').glob('*.json')):
            yield f'pilot:{path.stem}', json.loads(path.read_text(encoding='utf-8')), level


def matches(ref, entry):
    citation = entry.get('citation') or {}
    if 'slack' in ref:
        source = citation.get('source') or {}
        return [source.get('channel_id'), source.get('thread_id')] == list(ref['slack'])
    authoring = (citation.get('authoring') or '').split('@')[0]
    return authoring == ref['authoring'] and ('section' not in ref or ref['section'] in (citation.get('sections') or []))


def observe(scenario, result, level):
    card, ledger = result['card'], result.get('evidence_ledger') or {}
    cited = {(r.get('note') or '').split(' ')[0] for r in card.get('supporting_sources') or []}
    action = (card.get('recommended_action') or {}).get('action_type')
    codes = sorted({r['code'] for r in card['needs_review_reasons']})
    sources = []
    for expected in scenario['expected_sources']:
        hits = [(k, e) for k, e in ledger.items() if e.get('origin') == 'retrieved_source' and matches(expected['ref'], e)]
        uses = sorted({e['use'] for _, e in hits})
        sources.append({'ref': expected['ref'], 'relation': expected['relation'], 'retrieved': bool(hits), 'uses': uses,
                        'cited': any(k in cited for k, _ in hits),
                        'relation_ok': None if not hits else all(u in RELATION_USES[expected['relation']] for u in uses)})
    missing_reasons = [c for c in scenario['required_review_reasons'] if c not in codes]
    return {
        'level': level, 'card_line': card['card_line'], 'action_type': action,
        'action_ok': None if action is None else action in scenario['acceptable_actions'],
        'review_reasons': codes, 'required_reasons_ok': not missing_reasons, 'missing_reasons': missing_reasons,
        'card_line_ok': scenario['required_card_line'] in (None, card['card_line']),
        'inherited_flags': len(card.get('inherited_flags') or []),
        'grounding': card['checks']['grounding'], 'tot': (result.get('tot') or {}).get('status'),
        'severity': f"{card['severity']['level']} ({card['severity']['assessment_status']})",
        'sources_retrieved': f"{sum(s['retrieved'] for s in sources)}/{len(sources)}",
        'relation_violations': [s['ref'] for s in sources if s['relation_ok'] is False], 'sources': sources,
        'summary': card['summary'], 'review_notes': card.get('review_notes') or [],
        'action_label': (card.get('recommended_action') or {}).get('label')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--write', type=Path, help='New directory for coverage.json and coverage.md.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; write to a new directory.')
    sys.stdout.reconfigure(encoding='utf-8')
    matrix = json.loads(MATRIX.read_text(encoding='utf-8'))
    rows = []
    for scenario in matrix['scenarios']:
        keys = {scenario['work_id'], f"pilot:{scenario['pilot_scenario']}" if scenario['pilot_scenario'] else None}
        observed = []
        for run in args.run:
            for key, result, level in results_of(run):
                if key in keys:
                    observed.append({'run': run.as_posix(), **observe(scenario, result, level)})
        rows.append({'id': scenario['id'], 'demo_case': scenario['demo_case'], 'work_id': scenario['work_id'],
                     'acceptable_actions': scenario['acceptable_actions'], 'required_review_reasons': scenario['required_review_reasons'],
                     'must_not': scenario['must_not'], 'observed': observed,
                     'validation_levels': sorted({o['level'] for o in observed}) or ['not run']})
    lines = ['# Demo scenario coverage: expected versus observed', '',
             'Levels: live = real model calls; scripted = prepared judgments; placeholder = judges nothing. Severity is recorded, '
             'not scored (pending TL rubric decision for rule-confusion topics). Source columns count expected sources retrieved '
             'into the evidence ledger; a relation violation means the source was retrieved but used differently than expected.', '',
             '| Scenario | Run | Level | Card line | Action | Action OK | Required reasons | Sources | Relation violations | ToT | Severity |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in rows:
        if not row['observed']:
            lines.append(f"| {row['id']} | - | not run | | | | | | | | |")
        for o in row['observed']:
            lines.append(f"| {row['id']} | {Path(o['run']).name} | {o['level']} | {o['card_line']} | {o['action_type'] or 'none shown'} | "
                         f"{'-' if o['action_ok'] is None else 'yes' if o['action_ok'] else 'NO'} | "
                         f"{'yes' if o['required_reasons_ok'] and o['card_line_ok'] else 'NO ' + str(o['missing_reasons'])} | "
                         f"{o['sources_retrieved']} | {len(o['relation_violations']) or '-'} | {o['tot']} | {o['severity']} |")
    report = {'matrix': matrix['version'], 'runs': [r.as_posix() for r in args.run], 'scenarios': rows}
    print('\n'.join(lines))
    if args.write:
        args.write.mkdir(parents=True)
        (args.write/'coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        (args.write/'coverage.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
