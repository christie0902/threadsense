"""Evaluate the bounded retrieval expansion (type coverage + recorded-link related records) offline, zero model calls.

Two parts, reported separately (labels are not changed):
1. Recorded failure cases: each saved topic's exact retrieval steps are replayed through ResearchTools against the
   same snapshot, with expansion off and on; does each previously missing expected source reach the evidence ledger?
2. Existing benchmarks (tuned cases, holdout): each case query through ResearchTools as the initial current-guidance
   search and as prior-decision research (history); labelled sources reached, distractors and must-exclude sources
   added, and the input added (characters and approximate tokens). Ranked results are unchanged by construction, so
   nothing is displaced; the additions are listed.

  uv run --locked python scripts/evaluate_retrieval_expansion.py [--write <new path>]
"""
import argparse
import json
from pathlib import Path
import sys

FAILURES = [('audio trial outcome', 'data/experiments/agent3_overnight_smoke_v1', 'topic:cluster_6b59d13144282285/topic_2'),
            ('already announced', 'data/experiments/agent3_final_eval_v1', 'topic:cluster_e6a79dfad226e738/topic_2'),
            ('QA misalignment', 'data/experiments/agent3_final_eval_v1', 'topic:cluster_f944891544b06f79/topic_2')]


def tools(retriever, project, batch, as_of, expansion):
    from threadsense.agents.advisor_evidence import Budget, ResearchTools
    return ResearchTools(retriever, project=project, batch=batch, as_of=as_of, budget=Budget({}), expansion=expansion)


def matches(ref, item):
    citation = item.get('citation') or {}
    if 'slack' in ref:
        source = citation.get('source') or {}
        return [source.get('channel_id'), source.get('thread_id')] == list(ref['slack'])
    return (citation.get('authoring') or '').split('@')[0] == ref['authoring'] and (
        'section' not in ref or ref['section'] in (citation.get('sections') or []))


def failure_cases(retriever, matrix):
    from diagnose_retrieval_misses import topic_result  # Sibling script (scripts/ is on the path when run).
    out = []
    for label, run, work_id in FAILURES:
        result = topic_result(run, work_id)['result']
        topic, expected = result['topic'], [s['ref'] for s in matrix[work_id]['expected_sources']]
        rows = {}
        for expansion in (False, True):
            t = tools(retriever, topic['project_id'], topic['batch_id'], topic['as_of'], expansion)
            for step in result['retrieval_trace']:
                t.search(step['query'], purpose=step['purpose'], source_types=step['source_types'], version_mode=step['version_mode'])
            items = list(t.ledger.values())
            rows[expansion] = {'found': [ref for ref in expected if any(matches(ref, i) for i in items)],
                               'added': [{'authoring': i['citation']['authoring'] or i['citation']['title'], **{k: v for k, v in i['retrieved_as'].items() if k != 'links'}}
                                         for i in items if i.get('retrieved_as')]}
        out.append({'case': label, 'expected': expected, 'found_without': rows[False]['found'], 'found_with': rows[True]['found'],
                    'recovered': [r for r in rows[True]['found'] if r not in rows[False]['found']],
                    'still_missing': [r for r in expected if r not in rows[True]['found']], 'added': rows[True]['added']})
    return out


def benchmark(retriever, cases):
    rows = []
    for case in cases:
        f = case['filters']
        for mode, purpose, types in (('current', 'initial_current_guidance', None), ('history', 'gap:PRIOR_DECISION_OUTCOME', ['decision', 'announcement', 'guideline'])):
            t = tools(retriever, case['project'], f.get('batch'), f.get('as_of') or retriever.manifest['cutoff'], True)
            found = t.search(case['query'], purpose=purpose, source_types=types, version_mode=mode)
            primary = [i for i in found['results'] if not i.get('retrieved_as')]
            added = [i for i in found['results'] if i.get('retrieved_as')]
            def kind(item):
                return next((c for c, key in (('R', 'relevant'), ('X', 'must_exclude'), ('D', 'distractors'), ('C', 'context'))
                             if any(matches(ref, item) for ref in case.get(key, []))), '-')
            got = lambda items: [ref for ref in case['relevant'] if any(matches(ref, i) for i in items)]
            rows.append({'id': case['id'], 'search': mode, 'answerable': case['answerable'],
                         'relevant_primary': len(got(primary)), 'relevant_with_added': len(got(primary + added)),
                         'relevant_total': len(case['relevant']),
                         'added': [{'kind': kind(i), 'role': i['retrieved_as']['role'],
                                    'authoring': i['citation']['authoring'] or i['citation']['title']} for i in added],
                         'added_chars': sum(len(i['excerpt']) for i in added)})
    summary = {}
    for mode in ('current', 'history'):
        part = [r for r in rows if r['search'] == mode]
        kinds = [a['kind'] for r in part for a in r['added']]
        summary[mode] = {'cases': len(part), 'cases_gaining_relevant': sum(r['relevant_with_added'] > r['relevant_primary'] for r in part),
                         'relevant_recovered': sum(r['relevant_with_added'] - r['relevant_primary'] for r in part),
                         'records_added': len(kinds), 'relevant': kinds.count('R'), 'context': kinds.count('C'),
                         'distractors': kinds.count('D'), 'must_exclude': kinds.count('X'), 'unlabelled': kinds.count('-'),
                         'added_chars': sum(r['added_chars'] for r in part),
                         'added_tokens_approx': round(sum(r['added_chars'] for r in part) / 4)}
    return {'summary': summary, 'cases': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', type=Path, help='New path for the JSON report.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    from threadsense.retrieval.evaluate import CASES, HOLDOUT
    from threadsense.retrieval.search import Retriever
    retriever = Retriever()
    matrix = {s['work_id']: s for s in json.loads(Path('data/evaluation/agent3_demo_scenarios.json').read_text(encoding='utf-8'))['scenarios']}
    report = {'index_build_fingerprint': retriever.manifest['build_fingerprint'], 'failure_cases': failure_cases(retriever, matrix),
              'tuned_cases': benchmark(retriever, json.loads(CASES.read_text(encoding='utf-8'))['cases']),
              'holdout': benchmark(retriever, json.loads(HOLDOUT.read_text(encoding='utf-8'))['cases'])}
    retriever.client.close()
    print(json.dumps({'failure_cases': [{k: c[k] for k in ('case', 'recovered', 'still_missing', 'added')} for c in report['failure_cases']],
                      'tuned_cases': report['tuned_cases']['summary'], 'holdout': report['holdout']['summary']}, ensure_ascii=False, indent=1))
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
