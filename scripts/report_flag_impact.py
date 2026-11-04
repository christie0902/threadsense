"""Shadow routing comparison for the flag-impact assessment (zero calls, read-only by default).

For the nine audited cards (data/evaluation/agent3_flag_dependence_labels_v1.json) it reports the flag-impact record
saved with each run (older runs: NOT_ASSESSED, so the shadow line equals the current line) and, where prepared
judgments exist (tests/fixtures/agent3_flag_impact_prepared_judgments.json, PREPARED: hand-written, not model output),
the validated assessments and the line the proposed rule would give. The proposed rule only removes INHERITED_FLAG when
every flag on the card is a validated INDEPENDENT outside the grouping rule; every other reason stays. Production
routing is unchanged.

    uv run python scripts/report_flag_impact.py            # print
    uv run python scripts/report_flag_impact.py --write    # also write data/experiments/agent3_flag_impact_shadow_v1/
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents import flag_impact as fi  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

LABELS = ROOT/'data/evaluation/agent3_flag_dependence_labels_v1.json'
PREPARED = ROOT/'tests/fixtures/agent3_flag_impact_prepared_judgments.json'
OUT = ROOT/'data/experiments/agent3_flag_impact_shadow_v1'


def shadow_line(card, assessments):
    reasons = [r['code'] for r in card['needs_review_reasons']]
    release = bool(assessments) and len(assessments) == len(card['inherited_flags']) and \
        not any(a['retains_review'] for a in assessments)
    remaining = [r for r in reasons if r != 'INHERITED_FLAG' or not release]
    action = card.get('recommended_action')
    line = 'NEEDS_REVIEW' if remaining else 'RECOMMENDED_ACTION' if action and action['action_type'] != 'NO_ACTION' \
        else 'OBSERVATION'
    return line, remaining


def evaluate(run, topic_id, judgments):
    card_id = next(c for c, v in run.cards.items() if v['lineage'].get('topic_id') == topic_id)
    card, result = run.cards[card_id], run.topics[card_id]['result']
    prepared, verdicts, states = fi.prepare_saved(card, result, run.flag_source)
    out = [a.model_dump(mode='json') for a in fi.validate(judgments, prepared, verdicts=verdicts, member_states=states,
                                                          source='PREPARED')]
    return card, result, out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--write', action='store_true', help=f'write {OUT.relative_to(ROOT)} (must not exist)')
    args = parser.parse_args(argv)
    labels, prepared = (json.loads(p.read_text(encoding='utf-8')) for p in (LABELS, PREPARED))
    runs, rows = {}, []
    for case in labels['cases']:
        run = runs.setdefault(case['run'], Run(ROOT/'data/experiments'/case['run']))
        card_id = next(c for c, v in run.cards.items() if v['lineage'].get('topic_id') == case['topic_id'])
        card, result = run.cards[card_id], run.topics[card_id]['result']
        saved = result.get('flag_impact') or fi.not_assessed().model_dump(mode='json')
        row = {'scenario': case['scenario'], 'run': case['run'], 'prompt_version': case['prompt_version'],
               'current_line': card['card_line'], 'saved_assessment': saved['status'],
               'shadow_line_saved': shadow_line(card, saved['assessments'])[0]}
        matches = [(n, c) for n, c in prepared['cases'].items() if (c['run'], c['topic_id']) == (case['run'], case['topic_id'])]
        prepared_rows = []
        for name, c in sorted(matches, key=lambda x: x[0]):
            _, _, out = evaluate(run, case['topic_id'], c['judgments'])
            line, remaining = shadow_line(card, out)
            prepared_rows.append({'case': name, 'label': 'PREPARED', 'shadow_line': line, 'remaining_reasons': remaining,
                                  'assessments': [{k: a[k] for k in ('flag_id', 'kind', 'status', 'model_impact', 'impact',
                                                                     'validation_issues')} for a in out]})
        row['prepared'] = prepared_rows
        rows.append(row)
    extra = []
    for name, c in sorted(prepared['cases'].items()):
        if (c['run'], c['topic_id']) not in {(x['run'], x['topic_id']) for x in labels['cases']}:
            run = runs.setdefault(c['run'], Run(ROOT/'data/experiments'/c['run']))
            card, _, out = evaluate(run, c['topic_id'], c['judgments'])
            line, remaining = shadow_line(card, out)
            extra.append({'case': name, 'run': c['run'], 'mode': run.mode, 'current_line': card['card_line'],
                          'label': 'PREPARED', 'shadow_line': line, 'remaining_reasons': remaining,
                          'assessments': [{k: a[k] for k in ('flag_id', 'kind', 'status', 'model_impact', 'impact',
                                                             'validation_issues')} for a in out]})
    moved = [r['scenario'] for r in rows if r['shadow_line_saved'] != r['current_line']] + \
        [p['case'] for r in rows for p in r['prepared'] if p['shadow_line'] != r['current_line']] + \
        [e['case'] for e in extra if e['shadow_line'] != e['current_line']]
    report = {'version': 'agent3-flag-impact-shadow-v1', 'production_routing': 'unchanged', 'rows': rows,
              'other_prepared_cases': extra, 'moved': moved}
    for r in rows:
        print(f"{r['scenario']:21} {r['run']:27} {r['prompt_version']:5} {r['current_line']:13} saved={r['saved_assessment']:12} "
              f"shadow={r['shadow_line_saved']}")
        for p in r['prepared']:
            print(f"    PREPARED {p['case']:36} -> {p['shadow_line']:13} " +
                  '; '.join(f"{a['kind'][:14]}:{a['model_impact']}->{a['impact']}" for a in p['assessments']))
    for e in extra:
        print(f"PREPARED {e['case']} ({e['run']}, {e['mode']}): {e['current_line']} -> {e['shadow_line']} " +
              '; '.join(f"{a['kind'][:14]}:{a['model_impact']}->{a['impact']}" for a in e['assessments']))
    print('moved:', moved or 'none')
    if args.write:
        OUT.mkdir(parents=True, exist_ok=False)
        (OUT/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}/report.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
