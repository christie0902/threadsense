"""Export reviewer feedback as evaluation candidates (JSONL). Zero model calls; reads the dashboard store only.

Two files, never mixed: confirmed_cases.jsonl (an authorized team lead confirmed the report) and
unconfirmed_suggestions.jsonl (submitted, not confirmed). Withdrawn and superseded reports are left out and listed in
export_manifest.json. Each line references the original input and output (run instance, card, topic-result file and
its hash, threads, evidence IDs, model/prompt/knowledge/rubric versions) and carries the feedback, correction, scope
and confirmation status. Labels are reviewer assertions (label_status REVIEWER_ASSERTION_NOT_GROUND_TRUTH) for
evaluation only, never training data. See docs/human-feedback-loop.md for turning a confirmed case into a regression
test.

  uv run --locked python scripts/export_feedback_cases.py                          # counts only
  uv run --locked python scripts/export_feedback_cases.py --write D:/tsb/feedback_cases_20261110
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    from threadsense.dashboard.decisions import STORE_PATH
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--decision-db', type=Path, default=STORE_PATH)
    parser.add_argument('--namespace', action='append', choices=('operational', 'demo', 'test'),
                        help='Feedback namespaces to export (repeatable; default operational).')
    parser.add_argument('--write', type=Path, help='New output directory.')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.feedback import CASE_CONTRACT, evaluation_cases
    if not args.decision_db.is_file():
        parser.error(f'No dashboard store at {args.decision_db}.')
    namespaces = tuple(args.namespace or ('operational',))
    confirmed, unconfirmed, excluded = evaluation_cases(DecisionStore(args.decision_db).feedback(), namespaces=namespaces)
    manifest = {'case_contract': CASE_CONTRACT, 'namespaces': sorted(namespaces), 'confirmed_cases': len(confirmed),
                'unconfirmed_suggestions': len(unconfirmed), 'excluded': excluded,
                'note': 'Evaluation candidates from reviewer feedback. Reviewer assertions, not ground truth; not training '
                        'data; counts are workflow metrics and say nothing about model accuracy.'}
    if not args.write:
        print(json.dumps({'plan_only': True, **manifest}, indent=1, ensure_ascii=False))
        return 0
    if args.write.exists():
        parser.error(f'{args.write} exists; every export writes a new directory.')
    args.write.mkdir(parents=True)
    for name, cases in (('confirmed_cases.jsonl', confirmed), ('unconfirmed_suggestions.jsonl', unconfirmed)):
        (args.write/name).write_text(''.join(json.dumps(c, ensure_ascii=False, sort_keys=True) + '\n' for c in cases),
                                     encoding='utf-8')
    (args.write/'export_manifest.json').write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'written': str(args.write), **manifest}, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
