"""Compare the repair-pass live run with the frozen Milestone 7 baseline on the same work items. Read-only, zero calls.

Per topic: proposed vs shown action and its intervention-need verdict; expected sources retrieved / cited (demo
scenario matrix) and records added outside the ranking; summary shown or withheld; withheld statements; inherited
flags kept; ToT triggers and the open question with its verdict; requests, tokens and cost.

  uv run --locked python scripts/compare_repair_runs.py --baseline data/experiments/agent3_final_eval_v1 \
      --run data/experiments/agent3_repair_eval_v1 [--write <new dir>]
"""
import argparse
import json
from pathlib import Path
import sys


def topics(run):
    out = {}
    for path in sorted((Path(run)/'topics').rglob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('result'):
            out[data['work_item']['work_id']] = data['result']
    return out


def matches(ref, item):
    citation = item.get('citation') or {}
    if 'slack' in ref:
        source = citation.get('source') or {}
        return [source.get('channel_id'), source.get('thread_id')] == list(ref['slack'])
    return (citation.get('authoring') or '').split('@')[0] == ref['authoring'] and (
        'section' not in ref or ref['section'] in (citation.get('sections') or []))


def row(result, scenario):
    card, ledger = result['card'], result['evidence_ledger']
    verdicts = {s['statement_id']: s for s in result['grounding']['statements']}
    draft = result['drafts']['final'] or {}
    proposed = draft.get('proposed_action') or {}
    cited = {(r.get('note') or '').split(' ')[0] for r in card['supporting_sources']}
    sources = []
    for expected in scenario['expected_sources']:
        hits = [k for k, e in ledger.items() if e.get('origin') == 'retrieved_source' and matches(expected['ref'], e)]
        sources.append({'ref': expected['ref'], 'retrieved': bool(hits), 'cited': any(k in cited for k in hits),
                        'added_as': sorted({(ledger[k].get('retrieved_as') or {}).get('role', 'PRIMARY') for k in hits})})
    usage = {'requests': 0, 'input_tokens': 0, 'output_tokens': 0, 'charged_usd': 0.0}
    for call in result['model_calls']:
        stats = call.get('http_requests') or {}
        usage['requests'] += stats.get('sent', 0)
        usage['charged_usd'] += stats.get('charged_usd') or 0
        for response in stats.get('responses') or []:
            u = response.get('usage') or {}
            usage['input_tokens'] += u.get('prompt_tokens', 0)
            usage['output_tokens'] += u.get('completion_tokens', 0)
    withheld = [s for s in result['grounding']['statements'] if s['verdict'] != 'SUPPORTED' and s['kind'] != 'ALTERNATIVE']
    flags = {m for f in card['inherited_flags'] for m in f['member_ids']}
    need = proposed.get('intervention_need') or {}
    return {
        'card_line': card['card_line'], 'proposed_action': proposed.get('action_type'),
        'shown_action': (card['recommended_action'] or {}).get('action_type'),
        'intervention_need': need.get('kind'), 'need_verdict': (verdicts.get('action:need') or {}).get('verdict'),
        'action_verdict': (verdicts.get('action') or {}).get('verdict'),
        'acceptable': scenario['acceptable_actions'],
        'sources_retrieved': f"{sum(s['retrieved'] for s in sources)}/{len(sources)}",
        'sources_cited': f"{sum(s['cited'] for s in sources)}/{len(sources)}", 'sources': sources,
        'summary_shown': (verdicts.get('summary') or {}).get('verdict') == 'SUPPORTED', 'summary': card['summary'],
        'summary_verdict': (verdicts.get('summary') or {}).get('verdict'),
        'withheld_statements': len(withheld), 'withheld': [{'id': s['statement_id'], 'kind': s['kind'], 'verdict': s['verdict']} for s in withheld],
        'inherited_flags_kept': set(scenario['inherited_obligation_member_ids']) <= flags,
        'review_reasons': sorted({r['code'] for r in card['needs_review_reasons']}),
        'tot_triggers': (result.get('tot') or {}).get('triggers'), 'tot_status': (result.get('tot') or {}).get('status'),
        'open_question': draft.get('open_question'), 'open_question_verdict': (verdicts.get('open_question') or {}).get('verdict'),
        'grounding': result['grounding']['status'], 'usage': {**usage, 'charged_usd': round(usage['charged_usd'], 6)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--write', type=Path)
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; write to a new directory.')
    sys.stdout.reconfigure(encoding='utf-8')
    matrix = {s['work_id']: s for s in json.loads(Path('data/evaluation/agent3_demo_scenarios.json').read_text(encoding='utf-8'))['scenarios']}
    base, new = topics(args.baseline), topics(args.run)
    rows = [{'scenario': matrix[w]['id'], 'work_id': w, 'baseline': row(base[w], matrix[w]), 'repair': row(new[w], matrix[w])}
            for w in new if w in base and w in matrix]
    total = lambda side: {k: round(sum(r[side]['usage'][k] for r in rows), 6) for k in ('requests', 'input_tokens', 'output_tokens', 'charged_usd')}
    lines = ['| Scenario | Run | Line | Proposed -> shown | Need (verdict) | Sources retrieved / cited | Summary | Withheld | Flags kept | ToT triggers / open Q verdict | Requests, $ |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        for side in ('baseline', 'repair'):
            o = r[side]
            lines.append(f"| {r['scenario']} | {side} | {o['card_line']} | {o['proposed_action']} -> {o['shown_action'] or 'none'} | "
                         f"{o['intervention_need'] or '-'} ({o['need_verdict'] or '-'}) | {o['sources_retrieved']} / {o['sources_cited']} | "
                         f"{'shown' if o['summary_shown'] else 'withheld (' + str(o['summary_verdict']) + ')'} | {o['withheld_statements']} | "
                         f"{'yes' if o['inherited_flags_kept'] else 'NO'} | {o['tot_triggers']} / {o['open_question_verdict'] or '-'} | "
                         f"{o['usage']['requests']}, {o['usage']['charged_usd']:.4f} |")
    report = {'baseline': args.baseline.as_posix(), 'run': args.run.as_posix(), 'rows': rows,
              'totals': {'baseline': total('baseline'), 'repair': total('repair')}}
    print('\n'.join(lines))
    print(json.dumps(report['totals'], indent=1))
    if args.write:
        args.write.mkdir(parents=True)
        (args.write/'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        (args.write/'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
