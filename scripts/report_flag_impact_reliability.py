"""Flag-impact reliability report (zero calls, read-only by default).

Uses the frozen live shadow run (data/experiments/agent3_flag_impact_live_v1) as regression evidence:
- catalogue: every reference element_id sent for every flagged card of the saved runs is in the validation catalogue;
- history: PriorFinding statuses for every inherited Agent 1 obligation of the bound handoff;
- live: each saved live judgment re-validated under the current rules. This is a DIAGNOSTIC_REINTERPRETATION of
  recorded responses, not a new live result; the recorded v1 assessments are shown beside it unchanged;
- reuse: whether ReplayClient may reuse the recorded statement verdicts and flag judgments under the current rules.

    uv run python scripts/report_flag_impact_reliability.py            # print
    uv run python scripts/report_flag_impact_reliability.py --write    # also write data/experiments/agent3_flag_impact_reliability_v1/
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents import advisor_pilot as pilot, flag_impact as fi  # noqa: E402
from threadsense.agents.advice_inputs import load_effective_view  # noqa: E402
from threadsense.agents.flag_provenance import FlagSource  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

LIVE = ROOT/'data/experiments/agent3_flag_impact_live_v1'
RUNS = ('agent3_summary_eval_v1', 'agent3_writing_eval_v17_v1', 'agent3_policy_eval_v1', 'agent3_final_eval_v1',
        'agent3_repair_eval_v1', 'agent3_overnight_offline_v2', 'agent3_flag_impact_live_v1')
OUT = ROOT/'data/experiments/agent3_flag_impact_reliability_v1'


def catalogue_check():
    rows = {}
    for name in RUNS:
        run, cards, outside = Run(ROOT/'data/experiments'/name), 0, []
        for card_id, card in run.cards.items():
            if card['inherited_flags'] and card_id in run.topics:
                prepared, _, _ = fi.prepare_saved(card, run.topics[card_id]['result'], run.flag_source)
                sent = {r['element_id'] for i in prepared['inputs'] for r in i['references']}
                outside += sorted(sent - set(prepared['element_ids']))
                cards += 1
        rows[name] = {'flagged_cards': cards, 'references_outside_catalogue': outside}
    return rows


def history_scan():
    view = load_effective_view(ROOT/'data/processed/agent2_handoff_v2_projection')
    source, counts, entries = FlagSource.from_view(view, 'reliability#scan'), Counter(), []
    for row in view['records']:
        for o in row.get('inherited_review_obligations', []):
            flag = {'origin': 'agent1', 'kind': o.get('kind') or 'inherited_agent1_review', 'detail': None,
                    'candidate_group_id': row['candidate_group_id'], 'member_ids': [o['member_id']],
                    'obligation_id': o.get('obligation_id')}
            [prov] = source.provenance({'card_id': None, 'inherited_flags': [flag]})
            counts.update(h.status for h in prov.finding_history)
            entries += [{'member_id': o['member_id'], 'effective_attempt': prov.effective_attempt, 'status': h.status,
                         'category': h.finding.category, 'disputed_fields': h.finding.disputed_fields, 'basis': h.basis}
                        for h in prov.finding_history]
    return {'obligations': sum(len(r.get('inherited_review_obligations', [])) for r in view['records']),
            'prior_findings_by_status': dict(counts), 'prior_findings': entries}


def live_diagnostic():
    run, rows = Run(LIVE), []
    for card_id, card in run.cards.items():
        result = run.topics[card_id]['result']
        prepared, verdicts, states = fi.prepare_saved(card, result, run.flag_source)
        raw = json.loads(next(c for c in result['model_calls'] if c['stage'] == 'grounding')['raw'])['flag_impacts']
        recorded = {a['flag_id']: a for a in result['flag_impact']['assessments']}
        inputs = {i['flag_id']: i for i in prepared['inputs']}
        for a in fi.validate(raw, prepared, verdicts=verdicts, member_states=states, source='REPLAY'):
            old = recorded[a.flag_id]
            rows.append({'topic_id': card['lineage']['topic_id'], 'flag_id': a.flag_id, 'kind': a.kind,
                         'label': 'DIAGNOSTIC_REINTERPRETATION',
                         'recorded_live': {k: old[k] for k in ('contract_version', 'model_impact', 'impact', 'validation_issues')},
                         'current_rules': {'impact': a.impact, 'validation_issues': a.validation_issues,
                                           'open_finding_ids': a.open_finding_ids, 'finding_ids_judged': a.finding_ids,
                                           'reference_ids': a.reference_ids, 'unassessed_reference_ids': a.unassessed_reference_ids},
                         'resolved_findings': inputs[a.flag_id]['resolved_findings'],
                         'card_reasons': [r['code'] for r in card['needs_review_reasons']]})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--write', action='store_true', help=f'write {OUT.relative_to(ROOT)} (must not exist)')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    replay = pilot.ReplayClient(LIVE)
    report = {'version': 'agent3-flag-impact-reliability-v1', 'production_routing': 'unchanged',
              'model_calls': 0, 'flag_impact_fingerprint': pilot.flag_impact_fingerprint(),
              'catalogue': catalogue_check(), 'history': history_scan(), 'live_diagnostic': live_diagnostic(),
              'reuse': {'statement_verdicts_reusable': replay.grounding_inputs_same,
                        'flag_judgments_reusable': replay.flag_rules_same,
                        'note': 'Statement verdicts depend only on the grounding rules, evidence view and grounding schema, '
                                'which are unchanged. The flag-impact rules and sent schema changed (v2 findings, '
                                'finding_ids), so every recorded flag judgment needs a new judgment.'}}
    for name, row in report['catalogue'].items():
        print(f"catalogue {name:30} flagged cards {row['flagged_cards']:3}  outside: {row['references_outside_catalogue'] or 'none'}")
    print('history', report['history']['obligations'], 'obligations;', report['history']['prior_findings_by_status'])
    for r in report['live_diagnostic']:
        print(f"{r['topic_id']:36} {r['kind'][:22]:22} recorded {r['recorded_live']['model_impact']}->{r['recorded_live']['impact']:8} "
              f"current {r['current_rules']['impact']:8} {r['current_rules']['validation_issues'][:1]}")
    print('reuse', report['reuse']['statement_verdicts_reusable'], report['reuse']['flag_judgments_reusable'])
    if args.write:
        OUT.mkdir(parents=True, exist_ok=False)
        (OUT/'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}/report.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
