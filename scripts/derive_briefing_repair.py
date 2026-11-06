"""Re-apply briefing eligibility and Observation routing (briefing_policy.POLICY_VERSION) to a saved overnight run.
Zero model calls.

    uv run --locked python scripts/derive_briefing_repair.py                      # audit and counts only (read-only)
    uv run --locked python scripts/derive_briefing_repair.py --write data/experiments/<new dir>

The parent run is never modified. The derived run is a separate overnight-run directory (loadable by the dashboard)
whose cards are AdviceCard v5 with new card IDs, so no decision recorded on a parent card applies to them. Card text,
verdicts, evidence and accounting come from the parent unchanged; only card line, review reasons, briefing eligibility
and the outstanding step are recomputed, each change listed per card in derivation.json.

Relevance is not classified automatically: it comes from audited, input-bound labels (--labels), and a card with no
matching label stays in the brief.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents import briefing_policy as policy  # noqa: E402
from threadsense.agents.overnight import _card_order, brief_card, report  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

PARENT = ROOT/'data/experiments/threadsense_full_v1/stages/agent3/overnight_run'
LABELS = ROOT/'data/evaluation/briefing_relevance_labels_v2.json'
DERIVATION_VERSION = 'briefing-repair-derivation-v2'
RELEVANCE_METHOD = ('Audited, input-bound relevance labels (developer audit, not confirmed by a team lead); no automatic '
                    'relevance classification. Unlabelled cards, or cards whose saved messages changed, stay in the brief.')
# Fields that carry model text, verdict-bound content or accounting: identical in the parent and the derived card.
UNCHANGED = ('project_id', 'topic_name', 'summary', 'severity', 'severity_is_provisional', 'resolution_status',
             'recommended_action', 'reasoning', 'supporting_sources', 'related_threads', 'confidence', 'confidence_band',
             'inherited_flags', 'checks', 'lineage', 'details', 'next_step')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def saved_judgment(result, card):
    """The saved NO_ACTION judgment or why a recommendation is withheld: verdicts of the next-step statements."""
    statements = {s['statement_id']: s for s in result['grounding']['statements']}
    out = {k: statements[k]['verdict'] for k in ('action', 'action:no_action', 'action:need', 'action:rationale') if k in statements}
    proposed = ((result['drafts'].get('final') or {}).get('proposed_action') or {}).get('action_type')
    return {'proposed_action': proposed, 'verdicts': out, 'next_step': card['next_step']['status'],
            'shown_text': card['next_step'].get('rationale') or card['next_step'].get('explanation')}


def revision_candidate(result, card):
    """A card whose next step might be filled only by a new grounded recommendation (never generated here)."""
    status, statements = card['next_step']['status'], {s['statement_id']: s for s in result['grounding']['statements']}
    if status not in ('RECOMMENDATION_WITHHELD', 'NO_INTERVENTION_PROPOSED'):
        return None
    need = (statements.get('action:need') or {}).get('verdict')
    step = card['outstanding_step'] or {}
    if need == 'SUPPORTED':
        return 'The need to intervene was judged SUPPORTED but the proposed action failed a check; a targeted revision could repair the action.'
    if step.get('kind') in ('THREAD_STILL_OPEN', 'OPEN_QUESTION'):
        return 'A thread is still open with no team-lead request pending and no supported next step; a targeted revision could propose one.'
    return None


def derive(parent_dir, labels_path):
    parent = Run(parent_dir)
    labels_raw = read_json(labels_path)
    labels = policy.load_labels(labels_raw)
    queue = read_json(parent_dir/'review_queue.json')
    queue_members = {m for item in queue for m in item['member_ids']}
    accounting = read_json(parent_dir/'accounting.json')
    gaps = {m for g in accounting.get('projection_gaps') or [] for m in g['member_ids']}
    topics, cards, rows, id_map = {}, [], [], {}
    for path in sorted((parent_dir/'topics').glob('*.json')):
        topic = read_json(path)
        result, card = topic['result'], topic['result']['card']
        data, changes = policy.apply(card, result, labels=labels, queue_member_ids=queue_members,
                                     projection_gap=bool(set(card['lineage']['member_ids']) & gaps), cutoff=parent.brief['cutoff'])
        new_id = 'card_' + sha256(canonical({'parent_card': card['card_id'], 'policy': policy.POLICY_VERSION,
                                              'parent_run_instance': parent.instance}).encode('utf-8')).hexdigest()[:32]
        data['card_id'] = new_id
        data['derivation'] = {'policy_version': policy.POLICY_VERSION, 'parent_run': rel(parent_dir),
                              'parent_run_instance': parent.instance, 'parent_card_id': card['card_id'],
                              'parent_card_sha256': digest(card), 'parent_contract_version': card['contract_version'],
                              'changes': changes}
        derived = policy.validate(data)
        drift = [f for f in UNCHANGED if derived[f] != card[f]]
        if drift:
            raise SystemExit(f"{card['card_id']}: text or verdict-bound fields changed: {drift}")
        id_map[card['card_id']] = new_id
        topics[path.name] = {**topic, 'workflow': {**topic['workflow'], 'card_id': new_id, 'card_line': derived['card_line']},
                             'result': {**result, 'card': derived},
                             'derivation': {'policy_version': policy.POLICY_VERSION, 'parent_topic_file': rel(path),
                                            'parent_topic_sha256': sha256(path.read_bytes()).hexdigest(),
                                            'replaced': ['result.card', 'workflow.card_id', 'workflow.card_line']}}
        cards.append(derived)
        rel_ = derived['briefing']
        rows.append({'topic_file': path.name, 'parent_card_id': card['card_id'], 'card_id': new_id, 'topic_name': card['topic_name'],
                     'project_id': card['project_id'], 'member_ids': card['lineage']['member_ids'],
                     'before': {'card_line': card['card_line'], 'next_step': card['next_step']['status'],
                                'review_codes': sorted({r['code'] for r in card['needs_review_reasons']})},
                     'after': {'card_line': derived['card_line'], 'briefing': rel_['status'],
                               'review_codes': sorted({r['code'] for r in derived['needs_review_reasons']}),
                               'outstanding_step': derived['outstanding_step']},
                     'relevance': {'value': rel_['relevance'], 'label_id': rel_['label_id'], 'kept_because': rel_['kept_because'],
                                   **{k: (labels.get(tuple(sorted(card['lineage']['member_ids']))) or {}).get(k)
                                      for k in ('basis', 'uncertainty', 'evidence_statement_ids', 'notices', 'audit')}},
                     'resolution_status': card['resolution_status'],
                     'saved_judgment': saved_judgment(result, card),
                     'open_threads': policy.open_threads(result),
                     'revision_candidate': revision_candidate(result, derived),
                     'changes': changes})
    # Accounting and queue: same members and obligations, card references remapped to the derived IDs.
    new_queue = [{**item, 'related_card_ids': sorted(id_map[c] for c in item['related_card_ids'])} for item in queue]
    new_accounting = {**accounting, 'members': [{**m, 'card_id': id_map.get(m['card_id'], m['card_id'])} for m in accounting['members']]}
    check_accounting(parent_dir, accounting, queue, new_accounting, new_queue, cards, id_map)
    return parent, labels_raw, topics, cards, rows, new_queue, new_accounting


def check_accounting(parent_dir, accounting, queue, new_accounting, new_queue, cards, id_map):
    """Every input stays accounted for: members once each, on the same (remapped) card; every queue item and obligation."""
    before = Counter(m['member_id'] for m in accounting['members'])
    after = Counter(m['member_id'] for m in new_accounting['members'])
    on_cards = Counter(mid for c in cards for mid in c['lineage']['member_ids'])
    issues = []
    if before != after:
        issues.append('member accounting changed')
    if set(on_cards) != {m['member_id'] for m in accounting['members'] if m['card_id']} or any(n != 1 for n in on_cards.values()):
        issues.append('members are not each on exactly one card')
    if [i['item_id'] for i in queue] != [i['item_id'] for i in new_queue] or \
            [i.get('source_obligation') for i in queue] != [i.get('source_obligation') for i in new_queue]:
        issues.append('review queue items or obligations changed')
    if len(cards) != len(read_json(parent_dir/'cards.json')) or len(id_map) != len(cards):
        issues.append('card count changed')
    if issues:
        raise SystemExit('Accounting check failed: ' + '; '.join(issues))


def brief_of(parent, parent_dir, cards, queue, accounting, labels_path, out_name):
    b = dict(parent.brief)
    in_brief = [c for c in cards if c['briefing']['status'] == 'IN_BRIEFING']
    counts = {**b['counts'], 'cards_by_line': dict(Counter(c['card_line'] for c in cards))}
    sources = {id_map_c['card_id']: parent.semantic_source(id_map_c['derivation']['parent_card_id']) for id_map_c in cards}
    b.update({
        'run_id': b['run_id'], 'counts': counts,
        'semantic_note': (f"Live model judgments (LIVE_MODEL) from {rel(parent_dir)}; card routing re-applied offline under "
                          f"{policy.POLICY_VERSION} (no model call; card text and verdicts unchanged)."),
        'cards': [brief_card(c, sources[c['card_id']]) for c in sorted(cards, key=_card_order)],
        'model_review_queue': queue,
        'briefing': {'policy_version': policy.POLICY_VERSION, 'in_briefing': len(in_brief),
                     'in_briefing_by_line': dict(Counter(c['card_line'] for c in in_brief)),
                     'not_in_briefing': [{'card_id': c['card_id'], 'topic_name': c['topic_name'], 'status': c['briefing']['status'],
                                          'relevance': c['briefing']['relevance'], 'label_id': c['briefing']['label_id'],
                                          'basis': c['briefing']['basis'], 'resolution_status': c['resolution_status'],
                                          'open_step': (c['outstanding_step'] or {}).get('kind')}
                                         for c in cards if c['briefing']['status'] != 'IN_BRIEFING'],
                     'labels': rel(labels_path), 'relevance_method': RELEVANCE_METHOD, 'cutoff': b['cutoff']},
        'derivation': {'version': DERIVATION_VERSION, 'policy_version': policy.POLICY_VERSION, 'parent_run': rel(parent_dir),
                       'parent_run_key': parent.key, 'parent_run_instance': parent.instance, 'run_key': out_name,
                       'provenance': 'OFFLINE_POLICY_APPLICATION', 'model_calls': 0}})
    return b


def summarize(rows, cards):
    before = Counter(r['before']['card_line'] for r in rows)
    after = Counter(r['after']['card_line'] for r in rows)
    in_brief = [r for r in rows if r['after']['briefing'] == 'IN_BRIEFING']
    return {'cards': len(rows), 'before_by_line': dict(before), 'after_by_line': dict(after),
            'briefing': {'in_briefing': len(in_brief), 'in_briefing_by_line': dict(Counter(r['after']['card_line'] for r in in_brief)),
                         'not_in_briefing': dict(Counter(r['after']['briefing'] for r in rows if r['after']['briefing'] != 'IN_BRIEFING'))},
            'high_severity_in_briefing': sum(1 for c in cards if c['briefing']['status'] == 'IN_BRIEFING' and c['severity']['level'] == 'HIGH'),
            'changed_cards': sum(1 for r in rows if r['changes']),
            'line_changes': dict(Counter(f"{r['before']['card_line']} -> {r['after']['card_line']}" for r in rows
                                         if r['before']['card_line'] != r['after']['card_line'])),
            'outstanding_steps': dict(Counter((r['after']['outstanding_step'] or {}).get('kind') for r in rows
                                              if r['after']['outstanding_step']))}


def audit_markdown(rows, summary, parent_dir):
    lines = ['# Briefing eligibility audit (briefing-routing-v1)', '',
             f'Source: `{rel(parent_dir)}` (immutable). Zero model calls. Relevance labels: `{rel(LABELS)}` '
             '(developer audit, not confirmed by a team lead).', '', RELEVANCE_METHOD, '',
             f"Before: {summary['before_by_line']}. After: {summary['after_by_line']}. In the brief: "
             f"{summary['briefing']['in_briefing']} {summary['briefing']['in_briefing_by_line']}; history "
             f"{summary['briefing']['not_in_briefing']}.", '',
             '| Topic | Before | Next step | Relevance | Outstanding | Saved judgment | After | Brief |', '|---|---|---|---|---|---|---|---|']
    for r in sorted(rows, key=lambda r: (not r['changes'], r['before']['card_line'], r['topic_name'])):
        if r['before']['next_step'] == 'ACTION_RECOMMENDED' and not r['changes']:
            continue
        step = r['after']['outstanding_step']
        verdicts = ', '.join(f'{k} {v}' for k, v in r['saved_judgment']['verdicts'].items()) or 'none'
        lines.append(f"| {r['topic_name']} | {r['before']['card_line']} | {r['before']['next_step']} | {r['relevance']['value']} | "
                     f"{step['label'] if step else '-'} | {r['saved_judgment']['proposed_action']}: {verdicts} | "
                     f"{r['after']['card_line']} | {r['after']['briefing']} |")
    n = sum(1 for r in rows if r['before']['next_step'] == 'ACTION_RECOMMENDED' and not r['changes'])
    lines += ['', f'{n} cards with a supported recommended action are unchanged and not listed.', '',
              '## Relevance decisions', '']
    for r in sorted(rows, key=lambda r: r['topic_name']):
        if r['relevance']['value'] == 'PROJECT' and r['relevance']['audit'] != 'REVIEWED_2026-11-06':
            continue
        lines.append(f"- **{r['topic_name']}** ({r['relevance']['value']} -> {r['after']['briefing']}, resolution "
                     f"{r['resolution_status']}): {r['relevance']['basis']}")
        if r['relevance']['evidence_statement_ids']:
            lines.append(f"  Evidence (SUPPORTED statements): {', '.join(r['relevance']['evidence_statement_ids'])}.")
        for n in r['relevance']['notices'] or []:
            lines.append(f"  Notice {n['member_id']} \"{n['notice']}\": latest end {n['latest_end_utc']}.")
        if r['relevance']['kept_because']:
            lines.append(f"  Kept in the brief because: {'; '.join(r['relevance']['kept_because'])}.")
    lines.append('')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, default=PARENT)
    parser.add_argument('--labels', type=Path, default=LABELS)
    parser.add_argument('--write', type=Path, help='New output directory (refused if it exists).')
    args = parser.parse_args(argv)
    parent, labels_raw, topics, cards, rows, queue, accounting = derive(args.source, args.labels)
    summary = summarize(rows, cards)
    print(json.dumps(summary, indent=1))
    if not args.write:
        print('Read-only: pass --write <new dir> to save the derived run.')
        return 0
    out = args.write
    if out.exists():
        parser.error(f'{out} exists; derived runs go to a new directory.')
    (out/'topics').mkdir(parents=True)
    for name, topic in topics.items():
        write_json(out/'topics'/name, topic)
    write_json(out/'cards.json', cards)
    write_json(out/'review_queue.json', queue)
    write_json(out/'accounting.json', accounting)
    shutil.copy2(args.source/'diagnostics.json', out/'diagnostics.json')
    manifest = read_json(args.source/'run_manifest.json')
    manifest['derivation'] = {'version': DERIVATION_VERSION, 'policy_version': policy.POLICY_VERSION, 'parent_run': rel(args.source),
                              'parent_run_instance': parent.instance, 'labels': rel(args.labels),
                              'labels_sha256': sha256(args.labels.read_bytes()).hexdigest(), 'model_calls': 0}
    write_json(out/'run_manifest.json', manifest)
    brief = brief_of(parent, args.source, cards, queue, accounting, args.labels, out.name)
    write_json(out/'morning_brief.json', brief)
    (out/'morning_brief.md').write_text(report(brief), encoding='utf-8')
    write_json(out/'derivation.json', {
        'version': DERIVATION_VERSION, 'policy_version': policy.POLICY_VERSION, 'provenance': 'OFFLINE_POLICY_APPLICATION',
        'model_calls': 0, 'parent': {'run': rel(args.source), 'run_key': parent.key, 'run_instance': parent.instance,
                                     'cards_sha256': parent.cards_sha256},
        'labels': {'path': rel(args.labels), 'sha256': sha256(args.labels.read_bytes()).hexdigest(),
                   'contract_version': labels_raw['contract_version'], 'label_source': labels_raw['label_source'],
                   'relevance_method': RELEVANCE_METHOD},
        'cutoff': parent.brief['cutoff'],
        'summary': summary,
        'manual_review': [{'card_id': r['card_id'], 'topic_name': r['topic_name'], 'why': why} for r in rows for why in (
            ([f"Re-routed {r['before']['card_line']} -> {r['after']['card_line']}: the saved record does not establish that "
              'no intervention is needed; the team lead decides.'] if r['before']['card_line'] != r['after']['card_line'] else [])
            + ([f"Relevance label uncertain: {r['relevance']['uncertainty']}"] if (r['relevance']['uncertainty'] or 'LOW') != 'LOW' else [])
            + ([f"Left the brief ({r['after']['briefing']}) on a developer relevance label; confirm it is not project content."]
               if r['after']['briefing'] != 'IN_BRIEFING' else []))],
        'revision_candidates': [{'card_id': r['card_id'], 'topic_name': r['topic_name'], 'why': r['revision_candidate']}
                                for r in rows if r['revision_candidate']],
        'cards': rows})
    (out/'AUDIT.md').write_text(audit_markdown(rows, summary, args.source), encoding='utf-8')
    print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
