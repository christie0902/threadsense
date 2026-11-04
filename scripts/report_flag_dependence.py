"""Shadow report: flag provenance and card dependencies for the nine audited cards (zero calls, read-only by default).

For each inherited flag it shows what code establishes (upstream finding recovered or not; direct and derived references
through the displayed card; topic-resolution invariance) beside the human assessment in
data/evaluation/agent3_flag_dependence_labels_v1.json, and whether that assessment is supported by the recorded links or
still rests on semantic judgment. Production routing is unchanged; the proposed rule is evaluated two ways: from the
human labels, and from code alone (which can never establish independence, so it promotes nothing).

    uv run python scripts/report_flag_dependence.py            # print
    uv run python scripts/report_flag_dependence.py --write    # also write data/experiments/agent3_flag_dependence_v1/
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents.flag_provenance import dependencies  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

LABELS = ROOT/'data/evaluation/agent3_flag_dependence_labels_v1.json'
OUT = ROOT/'data/experiments/agent3_flag_dependence_v1'
REFERENCE = {'DIRECT', 'DERIVED'}
QUEUE_SIZE, GAPS = 52, 8


def run_hashes(runs):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for r in runs for p in sorted((ROOT/'data/experiments'/r).rglob('*')) if p.is_file()}


def find_card(run, topic_id):
    ids = [cid for cid, c in run.cards.items() if c['lineage'].get('topic_id') == topic_id]
    if len(ids) != 1:
        raise SystemExit(f'{run.key}: expected one card for topic {topic_id}, found {len(ids)}.')
    return ids[0]


def obligation_key(prov):
    return prov.obligation_key if prov.category != 'TOPIC_GROUPING' else None


def assess(label, prov, deps):
    """Whether the human label is supported by what the code can establish."""
    shown = [l for l in deps.links if l.displayed and l.relation in REFERENCE]
    refs = sorted({l.element_id for l in shown})
    invariant = [l.element_id for l in deps.links if l.relation == 'INVARIANT']
    if label == 'PRESERVED':
        ok = prov.category == 'TOPIC_GROUPING' and prov.queue_item_id is None
        return ('SUPPORTED' if ok else 'CONTRADICTED'), 'Projection gap: card-only grouping condition, no queue item.'
    if label == 'UNKNOWN':
        ok = prov.recovery in {'NOT_NARROWED', 'UNAVAILABLE'}
        return ('SUPPORTED' if ok else 'NEEDS_SEMANTIC_ASSESSMENT'), (
            f'Code: {prov.recovery}; the dispute cannot be narrowed to fields or messages.' if ok
            else 'Code recovered a specific finding; the label could now be revisited.')
    if label == 'AFFECTS':
        if refs:
            return 'SUPPORTED_BY_REFERENCES', f'Displayed elements reference the dispute: {", ".join(refs)}' + (
                f'; code shows {", ".join(invariant)} invariant' if invariant else '') + '. The effect itself is semantic.'
        return 'NEEDS_SEMANTIC_ASSESSMENT', 'No displayed reference recorded; the label rests on reading the card.'
    if prov.recovery != 'RECOVERED':
        return 'CONTRADICTED', f'Independence needs a narrowed dispute; code: {prov.recovery}.'
    return 'NEEDS_SEMANTIC_ASSESSMENT', (
        f'Code cannot establish independence. The label judges these displayed references harmless: '
        f'{", ".join(refs) or "none"}' + (f'; code establishes {", ".join(invariant)} invariant' if invariant else '') + '.')


def line(card, remaining):
    action = card.get('recommended_action')
    return 'NEEDS_REVIEW' if remaining else 'RECOMMENDED_ACTION' if action and action['action_type'] != 'NO_ACTION' else 'OBSERVATION'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--write', action='store_true', help=f'write the report to {OUT.relative_to(ROOT)} (must not exist)')
    args = parser.parse_args(argv)
    labels = json.loads(LABELS.read_text(encoding='utf-8'))
    runs = sorted({c['run'] for c in labels['cases']})
    before = run_hashes(runs)
    rows, problems, loaded = [], [], {}
    for case in labels['cases']:
        run = loaded.setdefault(case['run'], Run(ROOT/'data/experiments'/case['run']))
        card_id = find_card(run, case['topic_id'])
        card, result = run.cards[card_id], (run.topics.get(card_id) or {}).get('result')
        provs = run.flag_source.provenance(card)
        by_key = {(f.get('obligation_key'), f.get('kind')): f for f in case['flags']}
        flags = []
        for prov in provs:
            entry = by_key.get((obligation_key(prov), None)) or by_key.get((None, prov.kind))
            if entry is None:
                problems.append(f"{case['scenario']}: no label for flag {prov.flag_index} ({prov.kind})")
                continue
            deps = dependencies(card, result, prov, run.flag_source)
            verdict, why = assess(entry['label'], prov, deps)
            flags.append({'flag_index': prov.flag_index, 'kind': prov.kind, 'obligation_key': obligation_key(prov),
                          'queue_item_id': prov.queue_item_id, 'recovery': prov.recovery,
                          'card_detail_is': prov.card_detail_is,
                          'findings': [{'category': f.category, 'nature': f.nature, 'fields': f.disputed_fields,
                                        'message_ids': f.message_ids} for f in prov.findings],
                          'attempt_errors': [e.stage for e in prov.attempt_errors],
                          'links': {r: sorted({l.element_id for l in deps.links if l.relation == r and l.displayed})
                                    for r in ('DIRECT', 'DERIVED', 'INVARIANT', 'NOT_ESTABLISHED', 'SAME_THREAD')},
                          'hidden_links': sorted({f'{l.relation}:{l.element_id}' for l in deps.links if not l.displayed}),
                          'record_gaps': deps.record_gaps, 'human_label': entry['label'], 'label_basis': entry['basis'],
                          'code_check': verdict, 'code_note': why})
            if prov.category != 'TOPIC_GROUPING' and prov.queue_item_id not in {i for i in run.queue}:
                problems.append(f"{case['scenario']}: flag {prov.flag_index} has no item in the run's queue")
        if len(provs) != len(card['inherited_flags']) or len(case['flags']) != len(provs):
            problems.append(f"{case['scenario']}: flag count mismatch")
        reasons = [r['code'] for r in card['needs_review_reasons']]
        keep = [f for f in flags if f['human_label'] in {'AFFECTS', 'UNKNOWN', 'PRESERVED'}]
        by_labels = [r for r in reasons if r != 'INHERITED_FLAG' or keep]
        rows.append({'scenario': case['scenario'], 'run': case['run'], 'prompt_version': case['prompt_version'],
                     'run_ref': run.ref, 'card_id': card_id, 'current_line': card['card_line'], 'reasons': reasons,
                     'proposed_line_human_labels': line(card, by_labels), 'remaining_human_labels': by_labels,
                     'proposed_line_code_only': card['card_line'] if 'INHERITED_FLAG' in reasons else line(card, reasons),
                     'flags': flags})
    accounting = {}
    for name, run in loaded.items():
        acc = json.loads((run.path/'accounting.json').read_text(encoding='utf-8'))
        accounting[name] = {'queue_items': len(run.queue), 'projection_gaps': len(acc['projection_gaps']),
                            'status': acc['status']}
        if (len(run.queue), len(acc['projection_gaps']), acc['status']) != (QUEUE_SIZE, GAPS, 'COMPLETE'):
            problems.append(f'{name}: accounting differs: {accounting[name]}')
        if any(i.kind == 'projection_gap' for i in run.queue.values()):
            problems.append(f'{name}: a projection gap appears in the queue')
    unchanged = run_hashes(runs) == before
    report = {'version': 'agent3-flag-dependence-report-v1', 'labels': labels['version'], 'label_type': labels['label_type'],
              'production_routing': 'unchanged', 'rows': rows, 'accounting': accounting,
              'saved_runs_unchanged': unchanged, 'files_checked': len(before), 'problems': problems}
    for r in rows:
        print(f"{r['scenario']:21} {r['run']:27} {r['prompt_version']:5} {r['current_line']:13} "
              f"labels->{r['proposed_line_human_labels']:18} code->{r['proposed_line_code_only']}")
        for f in r['flags']:
            print(f"    [{f['flag_index']}] {f['kind']:24} {f['recovery']:14} label={f['human_label']:11} {f['code_check']}")
    print(f"saved runs unchanged: {unchanged} ({len(before)} files); accounting: {accounting}; problems: {problems or 'none'}")
    if args.write:
        OUT.mkdir(parents=True, exist_ok=False)
        (OUT/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'wrote {OUT.relative_to(ROOT)}/report.json')
    return 1 if problems or not unchanged else 0


if __name__ == '__main__':
    raise SystemExit(main())
