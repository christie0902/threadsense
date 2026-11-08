"""Offline evaluation of the shadow ToT policy (agent3-tot-shadow-partial-order-v1) on saved live comparisons.

Zero model calls; read-only unless --write names a NEW directory. Reads the topic results of the given saved live runs
(default: the full live run and the consolidated refresh), keeps each distinct comparison once (copied artifacts are
deduplicated by the SHA-256 of the comparison's candidates, decision and verdicts), derives the card-action link for
records saved before tot.card_action existed, and reports the shadow record next to the model's own decision. Saved
artifacts are not modified. Live comparisons with no proposed replacement cannot show how the replacement rule behaves
in practice; prepared cases are in tests/test_agent3_tot_shadow.py.

    uv run --locked python scripts/evaluate_tot_shadow.py
    uv run --locked python scripts/evaluate_tot_shadow.py --write data/experiments/agent3_tot_shadow_eval_v1
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
# The full live run, its network-disabled replay (the same comparisons: deduplicated, never counted twice) and the refresh.
RUNS = ('data/experiments/threadsense_full_v1/stages/agent3/overnight_run',
        'data/experiments/threadsense_full_v1_replay/stages/agent3/overnight_run',
        'data/experiments/threadsense_full_v1_consolidated_refresh_v1')
KEYS = ('candidate_id', 'action_type', 'draft_text', 'evidence_ids', 'evidence_support', 'applicability', 'severity_fit',
        'need_strength', 'temporal_scope', 'proportionality', 'incumbent', 'issues', 'grounding')


def comparison_key(tot):
    body = {'decision': tot.get('decision'), 'close_call': tot.get('close_call'), 'preferred': tot.get('model_preferred_candidate_id'),
            'candidates': [{k: c.get(k) for k in KEYS} for c in tot['candidates']]}
    return sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def evaluate(runs):
    from threadsense.agents import advisor_tot, tot_policy
    seen, rows, duplicates = {}, [], 0
    for run in runs:
        for path in sorted((ROOT/run/'topics').rglob('*.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            result = record.get('result', record)
            tot = result.get('tot') or {}
            if tot.get('status') != 'COMPARED':
                continue
            key = comparison_key(tot)
            if key in seen:
                duplicates += 1
                seen[key]['copies'].append(path.relative_to(ROOT).as_posix())
                continue
            action = result['card'].get('recommended_action')
            link = tot.get('card_action') or advisor_tot.card_action_candidate(
                tot, SimpleNamespace(**action) if action else None, (action or {}).get('source'))
            shadow = tot_policy.shadow({**result, 'tot': {**tot, 'card_action': link}})
            row = {'topic': result['topic'].get('topic_label'), 'run': run, 'card_id': result['card']['card_id'],
                   'card_line': result['card']['card_line'], 'triggers': tot['triggers'],
                   'controller_recorded': tot.get('controller', 'agent3-tot-controller-v1 (not recorded)'),
                   'card_action': link, 'choice_after_grounding': (tot.get('choice_after_grounding') or {}).get('status'),
                   'shadow': shadow, 'comparison_sha256': key, 'copies': [path.relative_to(ROOT).as_posix()]}
            seen[key] = row
            rows.append(row)
    return rows, duplicates


def summarize(rows, duplicates):
    relations = Counter(r['assessment'] for row in rows for r in row['shadow'].get('unproposed_relations', []))
    by_type = Counter((r['assessment'], 'NO_ACTION' if r['action_type'] == 'NO_ACTION' else 'OPERATIONAL')
                      for row in rows for r in row['shadow'].get('unproposed_relations', []))
    return {'distinct_comparisons': len(rows), 'duplicate_copies_skipped': duplicates,
            'model_decisions': dict(Counter(row['shadow']['model']['decision'] for row in rows)),
            'proposals': dict(Counter(row['shadow']['proposal'] for row in rows)),
            'shadow_outcomes': dict(Counter(row['shadow']['outcome']['status'] for row in rows)),
            'explicit_replacements_assessed': sum(row['shadow']['proposal'] == 'EXPLICIT_REPLACEMENT' for row in rows),
            'unproposed_relations': dict(relations),
            'unproposed_relations_by_type': {f'{a} / {t}': n for (a, t), n in sorted(by_type.items())},
            'incumbent_issues': [{'topic': row['topic'], **{k: d[k] for k in ('candidate_id', 'issues', 'disposition')},
                                  'affected_premises': d.get('affected_premises', []),
                                  'non_current_citations': d.get('non_current_citations', [])}
                                 for row in rows for d in row['shadow']['incumbent_issues']]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runs', action='append', help='Saved live run directory with topics/ (repeatable).')
    parser.add_argument('--write', type=Path, help='New output directory (report.json).')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.agents import tot_policy
    rows, duplicates = evaluate(args.runs or RUNS)
    report = {'policy': tot_policy.fingerprint(), 'model_calls': 0, 'runs': list(args.runs or RUNS),
              'basis': 'LIVE comparisons as saved (model ratings and final-grounding verdicts); the shadow policy is applied '
                       'offline and changes no artifact.', 'summary': summarize(rows, duplicates), 'comparisons': rows}
    print(json.dumps(report['summary'], ensure_ascii=False, indent=1))
    for row in rows:
        s = row['shadow']
        print(f"- {row['topic']}: model {s['model']['decision']}; proposal {s['proposal']}; outcome {s['outcome']['status']}; "
              f"unproposed {[(r['candidate_id'], r['assessment']) for r in s.get('unproposed_relations', [])]}")
    if args.write:
        if args.write.exists():
            parser.error(f'{args.write} exists; write a new directory.')
        args.write.mkdir(parents=True)
        (args.write/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f'Wrote {args.write}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
