"""Rebuild a completed run offline with Agent 1 relevance and Agent 2 consolidation (threadsense-full-run-v2 stages).
Zero model calls.

    uv run --locked python scripts/derive_consolidated_run.py                      # checks and counts only (read-only)
    uv run --locked python scripts/derive_consolidated_run.py --write data/experiments/<new dir>

Inputs (all saved, none modified): the full run (Agent 1 export, grouping, Agent 2 view), its briefing-repaired cards,
audited thread relevance labels (in place of the Agent 1 relevance judgment the run never made) and prepared Agent 2
consolidation decisions (in place of live consolidation judgments). Provenance of each is recorded.

The derived run keeps every source thread and review obligation exactly once in one inventory: briefing cards reused
unchanged (bindings checked), consolidated issues pending fresh grounding (their original cards linked and attributed,
never edited), and processing history. No card text or verdict is created; approvals stay bound to the run instance
they were recorded on.
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

from threadsense.agents import action_coordination, thread_relevance, topic_merge  # noqa: E402
from threadsense.agents.advice_inputs import load_effective_view  # noqa: E402
from threadsense.agents.overnight import report  # noqa: E402

FULL = ROOT/'data/experiments/threadsense_full_v1'
CARDS = ROOT/'data/experiments/threadsense_full_v1_briefing_v2'
LABELS = ROOT/'data/evaluation/agent1_thread_relevance_labels_v1.json'
DECISIONS = ROOT/'data/evaluation/agent2_consolidation_decisions_v1.json'
VERSION = 'consolidated-derivation-v1'
AGENT3_REQUESTS_PER_TOPIC = 4  # execution.pipeline.AGENT3_PER_TOPIC: the per-topic request ceiling
AGENT3_USD_PER_TOPIC = 0.139   # threadsense_full_v1 ledger: agent3 charged $11.28 over 81 topics
AGENT2_USD_PER_REQUEST = 0.004  # threadsense_full_v1 ledger: agent2 charged $0.31 over 76 requests


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def stage_dir(full, stage):
    m = read_json(full/'stages'/stage/'stage_manifest.json')
    path = full/m['output']
    if m['status'] != 'COMPLETE':
        raise SystemExit(f'{stage} is not complete in {full}.')
    from threadsense.execution.pipeline import tree_hash
    if tree_hash(path) != m['output_tree_sha256']:
        raise SystemExit(f'{stage} output changed since the run recorded it; refusing to derive.')
    return path


def grouping_unchanged(canonical, grouping_dir, history_ids):
    """The approved grouping algorithm on the eligible threads (cached vectors, no model load) gives the parent's
    clusters minus the excluded threads, or the derivation stops (Agent 2 would need a new run)."""
    import numpy as np
    from threadsense.handoff_inputs import identity, load_routed_handoff
    from threadsense.topic_grouping import approved_grouping
    members, _, _ = load_routed_handoff(canonical)
    implementation, baseline = approved_grouping()
    vectors, _, _, _ = implementation.get_embeddings([m['agent1_record'] for m in members], Path(grouping_dir)/'embedding_cache',
                                                     implementation.package_versions())
    keep = [i for i, m in enumerate(members) if identity(m) not in history_ids]
    fresh = implementation.group_records([members[i]['agent1_record'] for i in keep], np.asarray(vectors)[keep],
                                         baseline['config']['distance_threshold'])
    def partition(groups):
        return sorted(sorted((t['channel_id'], t['thread_id']) for t in g['threads']) for g in groups)
    parent = read_json(Path(grouping_dir)/'clusters.json')['clusters']
    excluded = {(c, t) for _, _, c, t in history_ids}
    expected = sorted(kept for g in partition(parent) if (kept := [x for x in g if x not in excluded]))
    same = partition(fresh) == expected
    removed = [g['cluster_id'] for g in parent if all((g['project_id'], g['batch_id'], t['channel_id'], t['thread_id']) in history_ids
                                                       for t in g['threads'])]
    return {'unchanged': same, 'parent_clusters': len(parent), 'eligible_clusters': len(fresh),
            'removed_singleton_clusters': removed, 'method': 'approved grouping_v1 algorithm on cached vectors (no model load)'}


def derive(full, cards_run, labels_path, decisions_path):
    canonical_dir = stage_dir(full, 'agent1_verify')
    grouping_dir, agent2_dir = stage_dir(full, 'grouping'), stage_dir(full, 'agent2')
    cutoff = read_json(cards_run/'morning_brief.json')['cutoff']
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='ts_derive_'))
    labels = thread_relevance.load_labels(read_json(labels_path))
    relevance = thread_relevance.build_stage(canonical_dir, tmp/'relevance', cutoff=cutoff, labels=labels)
    history = read_json(tmp/'relevance'/'processing_history.json')
    history_ids = {(h['project_id'], h['batch_id'], h['channel_id'], h['thread_id']) for h in history}
    grouping = grouping_unchanged(canonical_dir/'interpretations.json', grouping_dir, history_ids)
    if not grouping['unchanged']:
        raise SystemExit('Excluding processing-history threads changes the grouping; Agent 2 needs a new run, not a derivation.')
    view = load_effective_view(agent2_dir)
    member_of = {(m['project_id'], m['batch_id'], m['channel_id'], m['thread_id']): m['member_id']
                 for r in view['records'] for m in r['members']}
    history_members = {member_of[k] for k in history_ids}
    for h in history:
        h['member_id'] = member_of[(h['project_id'], h['batch_id'], h['channel_id'], h['thread_id'])]
    kept = {**view, 'records': [r for r in view['records'] if not {m['member_id'] for m in r['members']} <= history_members]}
    if any({m['member_id'] for m in r['members']} & history_members for r in kept['records']):
        raise SystemExit('A processing-history thread shares an Agent 2 group with clustered threads.')
    vectors = topic_merge.member_vectors(canonical_dir/'interpretations.json', grouping_dir)
    topics = topic_merge.topics_of(kept, vectors)
    consolidation = topic_merge.consolidate(topics, topic_merge.PreparedJudge(read_json(decisions_path)))
    shutil.rmtree(tmp, ignore_errors=True)
    return relevance, history, grouping, view, kept, consolidation, cutoff


def build(full, cards_run, labels_path, decisions_path):
    relevance, history, grouping, view, kept, consolidation, cutoff = derive(full, cards_run, labels_path, decisions_path)
    topics = {t['topic_id']: t for r in kept['records'] for t in r['topics']}
    merged = {tid: m for m in consolidation['merges'] for tid in m['source_topic_ids']}
    history_members = {h['member_id'] for h in history}
    results = {}
    for path in sorted((cards_run/'topics').glob('*.json')):
        data = read_json(path)
        results[data['result']['card']['card_id']] = (path, data)
    cards, rows = [], []
    for card_id, (path, data) in results.items():
        card = data['result']['card']
        members, tid = set(card['lineage']['member_ids']), card['lineage']['topic_id']
        if members <= history_members:
            inventory, why = 'PROCESSING_HISTORY', 'All its threads are processing history (Agent 1 relevance); card kept as a record, not briefed.'
        elif tid in merged:
            inventory, why = 'CONSOLIDATED_PENDING', (f"Its topic is part of consolidated issue {merged[tid]['consolidated_topic_id']}; "
                                                      'this advice stays attributed to the original topic until fresh grounding.')
        else:
            topic = topics.get(tid)
            if topic is None or sorted(topic['member_ids']) != sorted(members) or card['lineage']['agent2_export_sha256'] != view['canonical_sha256']:
                raise SystemExit(f'{card_id}: its Agent 2 binding no longer matches; it cannot be reused.')
            inventory, why = 'BRIEF', 'Reused unchanged: same topic members, Agent 2 export and saved evidence.'
        cards.append(card)
        rows.append({'card_id': card_id, 'topic_id': tid, 'topic_name': card['topic_name'], 'project_id': card['project_id'],
                     'member_ids': sorted(members), 'card_line': card['card_line'], 'briefing_v2': card['briefing']['status'],
                     'inventory': inventory, 'basis': why,
                     'consolidated_topic_id': merged[tid]['consolidated_topic_id'] if tid in merged else None,
                     'topic_file': path.name, 'topic_file_sha256': file_hash(path)})
    by_card = {r['card_id']: r for r in rows}
    pending = []
    for m in consolidation['merges']:
        source = [r for r in rows if r['consolidated_topic_id'] == m['consolidated_topic_id']]
        source_cards = [results[r['card_id']][1]['result']['card'] for r in source]
        pending.append({**{k: m[k] for k in ('consolidated_topic_id', 'topic_name', 'project_id', 'batch_id', 'source_topic_ids',
                                            'candidate_group_ids', 'member_ids', 'flagged_member_ids', 'subquestions', 'rationale')},
                        'status': 'PENDING_FRESH_GROUNDING',
                        'source_cards': [{'card_id': c['card_id'], 'topic_id': c['lineage']['topic_id'], 'topic_name': c['topic_name'],
                                          'card_line': c['card_line'], 'next_step': c['next_step']['status'],
                                          'review_codes': sorted({x['code'] for x in c['needs_review_reasons']}),
                                          'inherited_flags': len(c['inherited_flags'])} for c in source_cards],
                        'open_subquestions': [q for q in m['subquestions'] if q['resolution_state'] != 'RESOLVED_IN_THREAD'],
                        'review_codes_carried': sorted({x['code'] for c in source_cards for x in c['needs_review_reasons']}),
                        'judgment_provenance': consolidation['judge_provenance'],
                        'refresh': {'requests_ceiling': AGENT3_REQUESTS_PER_TOPIC, 'work_id': f"consolidated:{m['consolidated_topic_id']}"}})
    shared = action_coordination.coordinate(action_coordination.entries_from_results(
        [results[c][1]['result'] for c in results if by_card[c]['inventory'] != 'PROCESSING_HISTORY']))
    for action in shared['coordinated_actions']:
        for c in action['cards']:
            c['inventory'] = by_card[c['card_id']]['inventory']
            c['consolidated_topic_id'] = by_card[c['card_id']]['consolidated_topic_id']
    return relevance, history, grouping, consolidation, cards, rows, pending, shared, results, cutoff


def check_accounting(full_cards, rows, pending, history, queue, all_members):
    """Every source thread exactly once across the inventories; every review obligation exactly once in the queue."""
    seen = Counter()
    for r in rows:
        if r['inventory'] == 'BRIEF':
            seen.update(r['member_ids'])
    for p in pending:
        seen.update(p['member_ids'])
    seen.update(h['member_id'] for h in history)
    issues = [f'{m} accounted {n} times' for m, n in seen.items() if n != 1]
    if set(seen) != set(all_members):
        issues.append(f'{len(set(all_members) - set(seen))} threads missing from the inventories')
    if len(rows) != len(full_cards):
        issues.append('card count changed')
    if len({i['item_id'] for i in queue}) != len(queue):
        issues.append('duplicate review items')
    if issues:
        raise SystemExit('Accounting check failed: ' + '; '.join(issues[:5]))
    return {'threads': len(seen), 'brief_card_threads': sum(len(r['member_ids']) for r in rows if r['inventory'] == 'BRIEF'),
            'consolidated_threads': sum(len(p['member_ids']) for p in pending), 'processing_history_threads': len(history),
            'review_items': len(queue)}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--full', type=Path, default=FULL)
    parser.add_argument('--cards', type=Path, default=CARDS)
    parser.add_argument('--labels', type=Path, default=LABELS)
    parser.add_argument('--decisions', type=Path, default=DECISIONS)
    parser.add_argument('--write', type=Path, help='New output directory (refused if it exists).')
    args = parser.parse_args(argv)
    relevance, history, grouping, consolidation, cards, rows, pending, shared, results, cutoff = build(
        args.full, args.cards, args.labels, args.decisions)
    parent_brief = read_json(args.cards/'morning_brief.json')
    queue = read_json(args.cards/'review_queue.json')
    accounting = check_accounting(read_json(args.cards/'cards.json'), rows, pending, history, queue,
                                  [m['member_id'] for m in read_json(args.cards/'accounting.json')['members']])
    brief_rows = [r for r in rows if r['inventory'] == 'BRIEF']
    summary = {
        'before': {'cards': len(rows), 'in_brief': parent_brief['briefing']['in_briefing'],
                   'in_brief_by_line': parent_brief['briefing']['in_briefing_by_line'],
                   'history': len(parent_brief['briefing']['not_in_briefing']), 'agent2_topics': consolidation['counts']['topics_in'] + sum(
                       1 for r in rows if r['inventory'] == 'PROCESSING_HISTORY')},
        'after': {'briefing_items': len(brief_rows) + len(pending), 'reused_cards_in_brief': len(brief_rows),
                  'reused_cards_by_line': dict(Counter(r['card_line'] for r in brief_rows)),
                  'consolidated_issues_pending': len(pending), 'cards_under_consolidated_issues': sum(len(p['source_cards']) for p in pending),
                  'processing_history_threads': len(history), 'processing_history_cards': sum(1 for r in rows if r['inventory'] == 'PROCESSING_HISTORY'),
                  'topics_after_consolidation': consolidation['counts']['topics_out'], 'shared_actions': len(shared['coordinated_actions'])},
        'accounting': accounting, 'relevance': relevance, 'grouping': grouping, 'consolidation': consolidation['counts']}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    if not args.write:
        print('Read-only: pass --write <new dir> to save the derived run.')
        return 0
    out = args.write
    if out.exists():
        parser.error(f'{out} exists; derived runs go to a new directory.')
    tmp = out/'relevance'
    thread_relevance.build_stage(stage_dir(args.full, 'agent1_verify'), tmp, cutoff=cutoff,
                                 labels=thread_relevance.load_labels(read_json(args.labels)))
    write_json(tmp/'processing_history.json', history)  # with member IDs resolved from the Agent 2 view
    shutil.copytree(args.cards/'topics', out/'topics')
    for name in ('cards.json', 'review_queue.json', 'accounting.json', 'diagnostics.json'):
        shutil.copy2(args.cards/name, out/name)
    write_json(out/'consolidation.json', consolidation)
    write_json(out/'coordinated_actions.json', shared)
    inventory = {r['card_id']: r for r in rows}
    brief = dict(parent_brief)
    brief['cards'] = [{**c, 'inventory': inventory[c['card_id']]['inventory'],
                       'consolidated_topic_id': inventory[c['card_id']]['consolidated_topic_id']} for c in parent_brief['cards']]
    brief['briefing'] = {**parent_brief['briefing'], 'in_briefing': len(brief_rows) + len(pending),
                         'in_briefing_by_line': dict(Counter(r['card_line'] for r in brief_rows)),
                         'not_in_briefing': [n for n in parent_brief['briefing']['not_in_briefing']
                                             if inventory[n['card_id']]['inventory'] == 'BRIEF']}
    brief['consolidation'] = {'version': consolidation['version'], 'judge_provenance': consolidation['judge_provenance'],
                              'counts': consolidation['counts'], 'merges': [{k: m[k] for k in ('consolidated_topic_id', 'topic_name',
                                                                                                  'source_topic_ids')} for m in consolidation['merges']],
                              'pending': pending}
    brief['processing_history'] = [{'member_id': h['member_id'], 'project_id': h['project_id'], 'channel_id': h['channel_id'],
                                    'thread_id': h['thread_id'], 'relevance': h['relevance'], 'basis': h['basis'],
                                    'source': h['relevance_entry']['source'], 'label_id': h['relevance_entry'].get('label_id'),
                                    'outcome': f"PROCESSING_HISTORY ({h['relevance']}; not clustered)",
                                    'inherited_agent1_obligation': h['review_required'],
                                    'card_id': next((r['card_id'] for r in rows if h['member_id'] in r['member_ids']), None)}
                                   for h in history]
    brief['coordinated_actions'] = shared
    brief['semantic_note'] = (parent_brief['semantic_note'] + ' Relevance and consolidation applied offline '
                              f'({VERSION}): audited labels and prepared Agent 2 decisions, no model call.')
    brief['derivation'] = {'version': VERSION, 'provenance': 'OFFLINE_CACHED_REBUILD', 'model_calls': 0,
                           'parent_run': rel(args.full), 'cards_from': rel(args.cards), 'parent_run_key': args.cards.name,
                           'policy_version': VERSION,
                           'relevance_labels': {'path': rel(args.labels), 'sha256': file_hash(args.labels)},
                           'consolidation_decisions': {'path': rel(args.decisions), 'sha256': file_hash(args.decisions)}}
    write_json(out/'morning_brief.json', brief)
    (out/'morning_brief.md').write_text(report(brief), encoding='utf-8')
    manifest = read_json(args.cards/'run_manifest.json')
    manifest['derivation'] = {**brief['derivation'], 'parents': [rel(args.full), rel(args.cards)]}
    write_json(out/'run_manifest.json', manifest)
    reuse = Counter(r['inventory'] for r in rows)
    refresh = [{'consolidated_topic_id': p['consolidated_topic_id'], 'topic_name': p['topic_name'],
                'work_id': p['refresh']['work_id'], 'source_cards': [c['topic_name'] for c in p['source_cards']],
                'requests_ceiling': AGENT3_REQUESTS_PER_TOPIC} for p in pending]
    refresh_plan = {
        'command': ('uv run --locked python scripts/run_agent3_overnight.py --run --cutoff ' + cutoff
                    + f" --write data/experiments/<new dir> --handoff {rel(stage_dir(args.full, 'agent2'))}"
                    + f" --fixture-root {rel(args.full/'snapshot'/'slack')} --consolidation {rel(out/'consolidation.json')}"
                    + f" --processing-history {rel(out/'relevance'/'processing_history.json')} "
                    + ' '.join(f"--only {r['work_id']}" for r in refresh)
                    + f' --max-requests {AGENT3_REQUESTS_PER_TOPIC * len(refresh)} --max-cost 4.00'),
        'preview': 'the same command without --run and --write plans the work with zero calls',
        'requests_ceiling': AGENT3_REQUESTS_PER_TOPIC * len(refresh),
        'expected_usd': round(AGENT3_USD_PER_TOPIC * len(refresh), 2), 'max_cost_usd': 4.00,
        'live_agent2_consolidation': {'requests': len(consolidation['judgments']),
                                      'expected_usd': round(AGENT2_USD_PER_REQUEST * len(consolidation['judgments']), 2),
                                      'note': 'replaces the prepared decisions with live Agent 2 judgments (agent2_consolidate stage)'}}
    write_json(out/'derivation.json', {
        'version': VERSION, 'provenance': 'OFFLINE_CACHED_REBUILD', 'model_calls': 0,
        'parents': {'full_run': rel(args.full), 'cards': rel(args.cards),
                    'cards_sha256': file_hash(args.cards/'cards.json')},
        'inputs': {'relevance_labels': brief['derivation']['relevance_labels'] | {'source': read_json(args.labels)['label_source']},
                   'consolidation_decisions': brief['derivation']['consolidation_decisions'] | {'source': read_json(args.decisions)['decision_source']}},
        'summary': summary, 'cache_reuse': {'cards': dict(reuse), 'agent2_topics_reused': consolidation['counts']['topics_in'],
                                            'agent1_interpretations_reused': relevance['threads']},
        'inventory': rows, 'consolidated_pending': pending, 'processing_history': brief['processing_history'],
        'coordinated_actions': shared, 'targeted_agent3_refresh': refresh, 'refresh_plan': refresh_plan,
        'approvals': 'Decisions bind to run_key#run_instance; this new directory starts with none, and no decision on a parent card is carried over.'})
    (out/'REVIEW.md').write_text(review_markdown(summary, rows, pending, history, consolidation, shared, refresh, refresh_plan),
                                 encoding='utf-8')
    print(f'Wrote {out}')
    return 0


def review_markdown(summary, rows, pending, history, consolidation, shared, refresh, plan):
    names = {r['topic_id']: r['topic_name'] for r in rows}
    lines = ['# Relevance and consolidation repair (offline)', '',
             'Zero model calls. Relevance: audited thread labels (developer audit, not confirmed by a team lead; no automatic '
             'relevance classifier). Consolidation: prepared Agent 2 decisions (PREPARED_AUDIT), not live judgments.', '',
             f"Before: {summary['before']['in_brief']} briefing items from {summary['before']['cards']} cards. After: "
             f"{summary['after']['briefing_items']} briefing items ({summary['after']['reused_cards_in_brief']} reused cards + "
             f"{summary['after']['consolidated_issues_pending']} consolidated issues pending fresh grounding); "
             f"{summary['after']['processing_history_threads']} threads in processing history.", '',
             '## Processing history (excluded from clustering)', '']
    lines += [f"- {h['channel_id']} {h['thread_id']} ({h['relevance']}, {h['relevance_entry']['source']}): {h['basis']}" for h in history]
    lines += ['', '## Consolidated issues (pending fresh grounding)', '']
    for p in pending:
        lines.append(f"- **{p['topic_name']}** <- " + '; '.join(f"{c['topic_name']} ({c['card_line'].replace('_', ' ').lower()})"
                                                               for c in p['source_cards']))
        lines.append(f"  Basis: {p['rationale']}")
        if p['open_subquestions']:
            lines.append(f"  Open subquestions: {len(p['open_subquestions'])}; review codes kept: {', '.join(p['review_codes_carried']) or 'none'}.")
    lines += ['', '## Candidate sets kept separate', '']
    for j in consolidation['judgments']:
        if (j['judgment'] or {}).get('decision') != 'SAME_ISSUE':
            lines.append(f"- {' || '.join(names.get(t, t) for t in j['topic_ids'])}: {(j['judgment'] or {}).get('decision', j['status'])}. "
                         f"{(j['judgment'] or {}).get('rationale', '; '.join(j['problems']))}")
    lines += ['', '## Shared actions', '']
    for a in shared['coordinated_actions']:
        lines.append(f"- {a['label']} ({'; '.join(t['document'] + ' - ' + t['section'] for t in a['targets'])}): "
                     + '; '.join(f"{c['topic_name']} [{', '.join(c['review_codes']) or 'no review codes'}]" for c in a['cards']))
        lines.append(f"  {a['note']} Related, not coordinated: " + ('; '.join(w['topic_name'] for w in a['related_withheld']) or 'none'))
    lines += ['', '## Targeted Agent 3 refresh (not run)', '']
    lines += [f"- {r['topic_name']} ({r['work_id']}): up to {r['requests_ceiling']} requests" for r in refresh]
    lines += ['', f"Ceiling {plan['requests_ceiling']} requests, --max-cost ${plan['max_cost_usd']:.2f} (expected about "
              f"${plan['expected_usd']:.2f} at the full run's average). Preview with zero calls by dropping --run and --write:", '',
              '```', plan['command'], '```', '',
              f"Live Agent 2 consolidation judgments in place of the prepared decisions: {plan['live_agent2_consolidation']['requests']} "
              f"requests, about ${plan['live_agent2_consolidation']['expected_usd']:.2f}."]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    raise SystemExit(main())
