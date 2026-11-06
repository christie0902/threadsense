"""Combine the consolidated derivation with the targeted Agent 3 refresh into one briefing. Zero model calls.

    uv run --locked python scripts/derive_combined_brief.py                      # checks and counts only (read-only)
    uv run --locked python scripts/derive_combined_brief.py --write data/experiments/<new dir>
    uv run --locked python scripts/derive_combined_brief.py --reground <saved reground_topic.py result> [...] \
        --previous data/experiments/threadsense_full_v1_combined_v1 --write data/experiments/<new dir>      # v2

Inputs (all saved, none modified): the consolidated derivation (reused cards, processing history, consolidation
record, review queue) and the refresh run that advised each consolidated issue live. Each refreshed work item is
revalidated through the normal advisor path with its recorded generations and grounding verdicts
(advisor_pilot.ReplayClient, same-rules replay): the current checks run again, a recorded verdict is reused only for the
content it judged, and anything the corrected checks now send that was never judged stays PENDING (withheld). The
briefing policy then routes each refreshed card as it does every other card.

Inventories: the unaffected reused cards and the refreshed consolidated issues form the brief; the cards a refreshed
issue replaced stay as history reachable only through that issue's lineage; processing history is unchanged. Every
source thread and review obligation is accounted for exactly once. Decisions bind to this new run instance.

combined-briefing-v2 (--reground): a saved targeted live re-grounding (scripts/reground_topic.py --run) replaces the
revalidated result of its work item, only after the card is reproduced exactly from the refresh run's recorded
generations (plus the recorded wording edits) and the saved live grounding response, and every displayed statement is
SUPPORTED with its saved text and evidence. Human-written statements are labelled as human edits verified by the live
model; TL suggestions are listed as not judged. With --previous, every other card must be byte-identical to that run.
"""
import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents import action_coordination, briefing_policy as policy  # noqa: E402
from threadsense.agents.advisor_pilot import PILOT_VERSION  # noqa: E402
from threadsense.agents.overnight import _card_order, brief_card, report  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

CONSOLIDATED = ROOT/'data/experiments/threadsense_full_v1_consolidated_v1'
REFRESH = ROOT/'data/experiments/threadsense_full_v1_consolidated_refresh_v1'
LABELS = ROOT/'data/evaluation/briefing_relevance_labels_v2.json'
FORMAT_EDITS = ROOT/'data/evaluation/agent3_format_card_wording_v1.json'
SUGGESTIONS = ROOT/'data/evaluation/agent3_tl_suggestions_v1.json'
VERSION = 'combined-briefing-v1'
VERSION_V2 = 'combined-briefing-v2'
EDIT_FIELDS = {'summary': 'Summary sentence', 'action:need': 'Reason to intervene', 'severity': 'Severity signal',
               'detail': 'Detail sentence', 'claim': 'Finding'}
CHECKS = {'pilot_version': PILOT_VERSION,
          'author_count_scope': 'Plural counts are checked against message authors only when they are about authors or reporters '
                                '(team roles; generic people/users as the subject or agent of a reporting verb).',
          'temporal_eligibility': 'Several current sources that the final grounding recorded as agreeing, with every other cited '
                                  'item out of the running by recorded state, resolve a declared conflict; an UNDETERMINED '
                                  'declared conflict whose rule-stating current sources agree is a documentation-status finding.',
          'partial_pending': 'With some verdicts recorded, a statement never judged is withheld as unjudged; the judged ones stand.'}
GROUNDING_HARD_USD = 0.2118      # one grounding request at the input-token limit and output cap (gpt-6.1-sol list prices)
GROUNDING_RECORDED_USD = 0.0538  # mean recorded grounding charge of the 14 refreshed items


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def _replay_module():
    spec = importlib.util.spec_from_file_location('replay_overnight_topic', ROOT/'scripts/replay_overnight_topic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_parents(consolidated, refresh):
    """The refresh advised exactly the consolidation and processing history of this derivation."""
    fp = read_json(refresh/'run_manifest.json')['fingerprints']
    for key, path in (('consolidation', consolidated/'consolidation.json'),
                      ('processing_history', consolidated/'relevance'/'processing_history.json')):
        if (fp.get(key) or {}).get('sha256') != file_hash(path):
            raise SystemExit(f'The refresh run was not advised on this {key} record; refusing to combine.')
    brief = read_json(refresh/'morning_brief.json')
    if brief['accounting']['status'] != 'COMPLETE' or brief.get('incomplete_work'):
        raise SystemExit('The refresh run is not complete.')


def revalidate(refresh):
    """{work_id: (recorded topic, replayed result, summary)} for every refreshed item, zero calls."""
    from threadsense.agents import overnight
    replay = _replay_module()
    view = replay.recorded_view(refresh)
    retriever = overnight.open_snapshot(ROOT/'.index/retrieval')
    out = {}
    try:
        for path in sorted((refresh/'topics').glob('*.json')):
            topic = read_json(path)
            result, summary = replay.replay(refresh, topic['work_item']['work_id'], view=view, retriever=retriever)
            if summary['model_calls_sent']:
                raise SystemExit('A revalidation sent a request.')
            out[topic['work_item']['work_id']] = (path, topic, result, summary)
    finally:
        retriever.client.close()
    return out


def _brief(value):
    """A changed field as a short record: review codes, notes or the check statuses."""
    if isinstance(value, list) and value and isinstance(value[0], dict) and 'code' in value[0]:
        return sorted({v['code'] for v in value})
    return value


def changed_fields(before, after):
    return sorted(k for k in set(before) | set(after) if digest(before.get(k)) != digest(after.get(k)))


def verify_reground(refresh, path, view, retriever):
    """(saved result, verification) for a saved targeted re-grounding, or SystemExit. Zero calls: the card is rebuilt
    from the refresh run's recorded generations with the recorded edits and the saved live grounding response."""
    from threadsense.agents import advisor_pilot as pilot
    saved = read_json(path)
    result, edits, wid = saved['result'], saved['edits'], saved['plan']['work_id']
    grounding_raw = next(c['raw'] for c in result['model_calls'] if c['stage'] == 'grounding')
    regrounding = _script('reground_topic')

    class Saved(pilot.ReplayClient):
        def complete(self, stage, payload, schema):
            if stage == edits.get('stage'):
                raw = json.loads(pilot._json_text(self.recorded[payload['scenario_id']]['raw'][stage]))
                self.recorded[payload['scenario_id']]['raw'][stage] = json.dumps(regrounding.apply_edits(raw, edits['edits']), ensure_ascii=False)
            if stage == 'grounding':
                return grounding_raw
            return super().complete(stage, payload, schema)
    rebuilt, _ = _replay_module().replay(refresh, wid, view=view, retriever=retriever, client=Saved(refresh))
    issues = []
    if digest(rebuilt['card']) != digest(result['card']):
        issues.append('the card does not reproduce from the recorded generations and the saved grounding response')
    if digest(rebuilt['grounding']['statements']) != digest(result['grounding']['statements']):
        issues.append('the statements and verdicts do not reproduce')
    g, card = result['grounding'], result['card']
    statements = {x['statement_id']: x for x in g['statements']}
    if g['status'] != 'PASSED' or g['unjudged'] or g['pending']:
        issues.append(f"grounding {g['status']}")
    ledger = set(result['evidence_ledger'])
    if any(not set(x['evidence_ids']) <= ledger for x in g['statements']):
        issues.append('a statement cites evidence outside the saved ledger')
    for x in g['statements']:  # A summary or detail sentence is on the card exactly when it was judged SUPPORTED.
        if x['kind'] in ('SUMMARY', 'DETAIL'):
            shown = x['text'] in card['summary'] or x['text'] in (card.get('details') or [])
            if shown != (x['verdict'] == 'SUPPORTED'):
                issues.append(f"{x['statement_id']} shown={shown} with verdict {x['verdict']}")
    for e in edits['edits']:
        x = statements.get(e['statement_id'])
        if not x or x['verdict'] != 'SUPPORTED' or e['text'] not in x['text']:
            issues.append(f"edited {e['statement_id']} is not the SUPPORTED statement")
    draft = (result['drafts']['final'] or {}).get('proposed_action') or {}
    if card['recommended_action'] and (statements.get('action', {}).get('verdict') != 'SUPPORTED'
                                       or card['recommended_action']['draft_text'] != draft.get('draft_text')):
        issues.append('the displayed action is not the judged model draft')
    if issues:
        raise SystemExit(f'{path}: ' + '; '.join(issues))
    edited = [{'statement_id': e['statement_id'], 'field': EDIT_FIELDS.get(e['statement_id'].split(':')[0] if e['statement_id'] != 'action:need'
                                                                           else 'action:need', e['statement_id']),
               'text': statements[e['statement_id']]['text'], 'provenance': 'HUMAN_EDIT_VERIFIED_BY_LIVE_MODEL',
               'verdict': 'SUPPORTED', 'judge_rationale': statements[e['statement_id']]['rationale'],
               'replaced_text': e['expected']} for e in edits['edits']]
    return saved, {'path': rel(path), 'sha256': file_hash(path), 'work_id': wid, 'charged_usd': round(sum(u['charged_usd'] for u in saved['usage']), 6),
                   'edits_provenance': edits['provenance'], 'human_edits': edited, 'reproduced': True,
                   'statements_supported': sum(x['verdict'] == 'SUPPORTED' for x in g['statements']), 'statements': len(g['statements'])}


def _script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(consolidated, refresh, labels_path, regrounds=(), suggestions=None):
    check_parents(consolidated, refresh)
    parent = read_json(consolidated/'morning_brief.json')
    refresh_run = Run(refresh)
    queue = read_json(consolidated/'review_queue.json')
    if [i['item_id'] for i in queue] != [i['item_id'] for i in read_json(refresh/'review_queue.json')]:
        raise SystemExit('The refresh run queued different review items.')
    queue_members = {m for item in queue for m in item['member_ids']}
    labels = policy.load_labels(read_json(labels_path))
    consolidation = read_json(consolidated/'consolidation.json')
    merges = {m['consolidated_topic_id']: m for m in consolidation['merges']}
    pending = {p['consolidated_topic_id']: p for p in parent['consolidation']['pending']}
    parent_results = {read_json(p)['result']['card']['card_id']: read_json(p) for p in sorted((consolidated/'topics').glob('*.json'))}
    revalidated = revalidate(refresh)
    overlays = {}
    if regrounds:
        from threadsense.agents import overnight
        view, retriever = _replay_module().recorded_view(refresh), overnight.open_snapshot(ROOT/'.index/retrieval')
        try:
            for path in regrounds:
                saved, verification = verify_reground(refresh, Path(path), view, retriever)
                wid = verification['work_id']
                topic_path, topic, _, summary = revalidated[wid]
                revalidated[wid] = (topic_path, topic, saved['result'], summary)
                overlays[wid] = verification
        finally:
            retriever.client.close()
    tl = {s['work_id']: s for s in (suggestions or {}).get('suggestions', [])}
    refresh_sources = {e['card_id']: e['semantic_source'] for e in read_json(refresh/'morning_brief.json')['cards']}
    cards, topics, rows, refreshed, corrections = {}, {}, [], [], []
    for wid, (path, topic, result, summary) in revalidated.items():
        recorded = topic['result']['card']
        cid = result['card']['lineage']['topic_id']
        merge, source = merges[cid], pending[cid]
        if sorted(result['card']['lineage']['member_ids']) != sorted(merge['member_ids']):
            raise SystemExit(f'{wid}: the refreshed card does not cover its consolidated members.')
        data, changes = policy.apply(result['card'], result, labels=labels, queue_member_ids=queue_members, cutoff=parent['cutoff'])
        overlay = overlays.get(wid)
        new_id = 'card_' + digest({'parent_card': recorded['card_id'], 'derivation': VERSION, 'policy': policy.POLICY_VERSION,
                                   'parent_run_instance': refresh_run.instance, 'checks': CHECKS,
                                   **({'reground_sha256': overlay['sha256']} if overlay else {})})[:32]
        revalidation = {'checks': CHECKS, 'changed_verdicts': summary['changed_verdicts'], 'pending': summary['pending'],
                        'verdicts_reused': summary['reuse']['reused'], 'not_reused': summary['reuse']['not_reused'],
                        'card_fields_changed': changed_fields(recorded, result['card'])}
        checked = [{'field': f, 'before': _brief(recorded.get(f)), 'after': _brief(result['card'].get(f)),
                    'reason': f'Revalidated under {PILOT_VERSION} checks with the recorded verdicts (zero calls).'}
                   for f in revalidation['card_fields_changed']]
        if overlay:
            checked = [{'field': f, 'before': _brief(recorded.get(f)), 'after': _brief(result['card'].get(f)),
                        'reason': f"Targeted live re-grounding ({overlay['path']}, ${overlay['charged_usd']:.3f}); reproduced offline from its saved response."}
                       for f in revalidation['card_fields_changed']] + [
                       {'field': e['field'], 'before': e['replaced_text'], 'after': e['text'],
                        'reason': 'HUMAN_EDIT_VERIFIED_BY_LIVE_MODEL: developer-written wording judged SUPPORTED by the live model.'}
                       for e in overlay['human_edits']]
        data.update(card_id=new_id, derivation={
            'policy_version': f'{VERSION_V2 if overlay else VERSION}+{policy.POLICY_VERSION}', 'parent_run': rel(refresh),
            'parent_run_instance': refresh_run.instance, 'parent_card_id': recorded['card_id'],
            'parent_card_sha256': digest(recorded), 'parent_contract_version': recorded['contract_version'],
            'changes': checked + changes})
        card = policy.validate(data)
        cards[new_id] = card
        topics[path.name] = {**topic, 'workflow': {**topic['workflow'], 'card_id': new_id, 'card_line': card['card_line']},
                             'result': {**result, 'card': card},
                             'derivation': {'version': VERSION_V2 if overlay else VERSION, 'parent_topic_file': rel(path), 'parent_topic_sha256': file_hash(path),
                                            'replaced': ['result (revalidated replay)', 'workflow.card_id', 'workflow.card_line'],
                                            'advice_provenance': 'LIVE_TARGETED_REGROUNDING' if overlay else 'LIVE_ADVICE_REVALIDATED_OFFLINE',
                                            'revalidation': revalidation, **({'reground': overlay} if overlay else {})}}
        replaced = [{'card_id': c['card_id'], 'topic_id': c['topic_id'], 'topic_name': c['topic_name'], 'card_line': c['card_line'],
                     'review_codes': c['review_codes']} for c in source['source_cards']]
        refreshed.append({'consolidated_topic_id': cid, 'topic_name': merge['topic_name'], 'card_id': new_id, 'work_id': wid,
                          'rationale': merge['rationale'], 'judgment_provenance': consolidation['judge_provenance'],
                          'advice_provenance': 'LIVE_TARGETED_REGROUNDING' if overlay else 'LIVE_ADVICE_REVALIDATED_OFFLINE',
                          'replaced_cards': replaced, 'human_edits': overlay['human_edits'] if overlay else [],
                          'tl_suggestions': [{k: tl[wid][k] for k in ('field', 'text', 'basis')} | {'status': 'NOT_JUDGED'}] if wid in tl else [],
                          'member_ids': sorted(merge['member_ids'])})
        rows.append({'card_id': new_id, 'topic_name': card['topic_name'], 'project_id': card['project_id'], 'inventory': 'BRIEF',
                     'card_line': card['card_line'], 'member_ids': sorted(merge['member_ids']), 'consolidated_topic_id': cid,
                     'source': 'REFRESHED', 'semantic_source': refresh_sources[recorded['card_id']], 'parent_card_id': recorded['card_id'],
                     **({'reground': overlay['path']} if overlay else {})})
        if revalidation['card_fields_changed'] or revalidation['changed_verdicts']:
            corrections.append({'card_id': new_id, 'topic_name': card['topic_name'], 'parent_card_id': recorded['card_id'],
                                'card_fields_changed': revalidation['card_fields_changed'],
                                'changed_verdicts': revalidation['changed_verdicts'], 'pending': revalidation['pending'],
                                'temporal_before': topic['result']['temporal'], 'temporal_after': result['temporal'],
                                'review_codes_before': sorted({r['code'] for r in recorded['needs_review_reasons']}),
                                'review_codes_after': sorted({r['code'] for r in card['needs_review_reasons']}),
                                'review_notes_after': card['review_notes']})
    replaced_by = {c['card_id']: r['card_id'] for r in refreshed for c in r['replaced_cards']}
    for entry in parent['cards']:
        card = parent_results[entry['card_id']]['result']['card']
        inventory = 'REPLACED' if entry['inventory'] == 'CONSOLIDATED_PENDING' else entry['inventory']
        cards[card['card_id']] = card
        rows.append({'card_id': card['card_id'], 'topic_name': card['topic_name'], 'project_id': card['project_id'],
                     'inventory': inventory, 'card_line': card['card_line'], 'member_ids': sorted(card['lineage']['member_ids']),
                     'consolidated_topic_id': entry.get('consolidated_topic_id'), 'source': 'REUSED',
                     'semantic_source': entry['semantic_source'], 'replaced_by': replaced_by.get(card['card_id'])})
    if set(replaced_by) != {r['card_id'] for r in rows if r['inventory'] == 'REPLACED'}:
        raise SystemExit('A replaced card is not linked from exactly one refreshed issue.')
    brief_results = [topics[n]['result'] for n in topics] + [parent_results[r['card_id']]['result'] for r in rows
                                                              if r['source'] == 'REUSED' and r['inventory'] == 'BRIEF']
    shared = action_coordination.coordinate(action_coordination.entries_from_results(brief_results))
    for action in shared['coordinated_actions']:
        for c in action['cards']:
            c['inventory'] = 'BRIEF'
    return parent, queue, consolidation, cards, topics, rows, refreshed, corrections, shared, revalidated, overlays


def check_accounting(rows, history, queue, all_members, consolidated_accounting):
    """Every source thread exactly once across the brief and processing history; the replaced cards' threads exactly
    those of the refreshed issues; every review item once, each on a briefed thread or processing history."""
    seen = Counter()
    for r in rows:
        if r['inventory'] == 'BRIEF':
            seen.update(r['member_ids'])
    seen.update(h['member_id'] for h in history)
    issues = [f'{m} accounted {n} times' for m, n in seen.items() if n != 1]
    if set(seen) != set(all_members):
        issues.append(f'{len(set(all_members) - set(seen))} threads missing')
    replaced = {m for r in rows if r['inventory'] == 'REPLACED' for m in r['member_ids']}
    refreshed = {m for r in rows if r['source'] == 'REFRESHED' for m in r['member_ids']}
    if replaced != refreshed:
        issues.append('replaced cards and refreshed issues cover different threads')
    if len({i['item_id'] for i in queue}) != len(queue):
        issues.append('duplicate review items')
    on_brief = {m for r in rows if r['inventory'] == 'BRIEF' for m in r['member_ids']} | {h['member_id'] for h in history}
    if any(not set(i['member_ids']) <= on_brief for i in queue):
        issues.append('a review item is not on a briefed thread or processing history')
    if issues:
        raise SystemExit('Accounting check failed: ' + '; '.join(issues[:5]))
    return {'threads': len(seen), 'brief_threads': sum(len(r['member_ids']) for r in rows if r['inventory'] == 'BRIEF'),
            'processing_history_threads': len(history), 'replaced_card_threads': len(replaced),
            'review_items': len(queue), 'review_items_unchanged_from': consolidated_accounting}


def remaining_judgments(corrections, refresh, format_edits):
    """Targeted grounding requests that would settle what this derivation leaves unjudged or withheld."""
    out = []
    for c in corrections:
        if c['pending']:
            out.append({'card': c['topic_name'], 'why': f"{', '.join(c['pending'])} not judged: the corrected author-count check "
                        'now sends it, and no recorded verdict exists.', 'requests': 1, 'stage': 'grounding',
                        'command': f"uv run --locked python scripts/reground_topic.py --run-dir {rel(refresh)} --work "
                                   f"{c['work_id']} --run --write data/experiments/<new path>.json",
                        'hard_cost_usd': GROUNDING_HARD_USD, 'expected_usd': GROUNDING_RECORDED_USD})
    edits = read_json(format_edits)
    out.append({'card': 'Format compliance versus accuracy', 'why': 'Three statements judged PARTIALLY_SUPPORTED withheld the '
                'action and severity; candidate wording (DEVELOPER_CANDIDATE_PENDING_GROUNDING) restates them per author.',
                'requests': 1, 'stage': 'grounding',
                'command': f"uv run --locked python scripts/reground_topic.py --run-dir {rel(refresh)} --work {edits['work_id']} "
                           f"--edits {rel(format_edits)} --run --write data/experiments/<new path>.json",
                'hard_cost_usd': GROUNDING_HARD_USD, 'expected_usd': GROUNDING_RECORDED_USD})
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--consolidated', type=Path, default=CONSOLIDATED)
    parser.add_argument('--refresh', type=Path, default=REFRESH)
    parser.add_argument('--labels', type=Path, default=LABELS)
    parser.add_argument('--format-edits', type=Path, default=FORMAT_EDITS)
    parser.add_argument('--reground', type=Path, action='append', default=[],
                        help='Saved scripts/reground_topic.py --run result to apply (combined-briefing-v2).')
    parser.add_argument('--suggestions', type=Path, default=SUGGESTIONS, help='TL suggestions (not judged), with --reground.')
    parser.add_argument('--previous', type=Path, help='The combined briefing this one supersedes: every other card must match it.')
    parser.add_argument('--write', type=Path, help='New output directory (refused if it exists).')
    args = parser.parse_args(argv)
    version = VERSION_V2 if args.reground else VERSION
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; derived runs go to a new directory.')
    parent, queue, consolidation, cards, topics, rows, refreshed, corrections, shared, revalidated, overlays = build(
        args.consolidated, args.refresh, args.labels, args.reground, read_json(args.suggestions) if args.reground else None)
    supersedes = compare_previous(args.previous, cards, rows, overlays, refreshed) if args.previous else None
    for c in corrections:
        c['work_id'] = next(r['work_id'] for r in refreshed if r['card_id'] == c['card_id'])
    history = read_json(args.consolidated/'relevance'/'processing_history.json')
    accounting = check_accounting(rows, history, queue, [m['member_id'] for m in read_json(args.consolidated/'accounting.json')['members']],
                                  rel(args.consolidated/'review_queue.json'))
    brief_rows = [r for r in rows if r['inventory'] == 'BRIEF']
    plan = remaining_judgments(corrections, args.refresh, args.format_edits)
    summary = {'briefing_items': len(brief_rows), 'by_line': dict(Counter(r['card_line'] for r in brief_rows)),
               'reused': len([r for r in brief_rows if r['source'] == 'REUSED']), 'refreshed': len(refreshed),
               'refreshed_by_line': dict(Counter(r['card_line'] for r in brief_rows if r['source'] == 'REFRESHED')),
               'replaced_cards': sum(1 for r in rows if r['inventory'] == 'REPLACED'),
               'processing_history': {'threads': len(history), 'cards': sum(1 for r in rows if r['inventory'] == 'PROCESSING_HISTORY')},
               'shared_actions': len(shared['coordinated_actions']), 'accounting': accounting,
               'revalidation': {'items': len(revalidated), 'cards_unchanged': len(revalidated) - len(corrections),
                                'cards_corrected': [c['topic_name'] for c in corrections],
                                'model_calls': 0},
               'remaining_judgments': {'requests': sum(p['requests'] for p in plan),
                                       'hard_cost_usd': round(sum(p['hard_cost_usd'] for p in plan), 4)}}
    if overlays:
        summary['targeted_regrounding'] = {'requests': len(overlays), 'charged_usd': round(sum(o['charged_usd'] for o in overlays.values()), 3),
                                           'cards': [o['work_id'] for o in overlays.values()], 'rebuild_model_calls': 0}
        summary['remaining_judgments'] = {'requests': 0, 'hard_cost_usd': 0.0}
        plan = [p for p in plan if not any(o['work_id'] in p['command'] for o in overlays.values())]
    if supersedes:
        summary['supersedes'] = supersedes
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    if not args.write:
        print('Read-only: pass --write <new dir> to save the combined briefing.')
        return 0
    out = args.write
    shutil.copytree(args.consolidated/'relevance', out/'relevance')
    (out/'topics').mkdir(parents=True)
    for path in sorted((args.consolidated/'topics').glob('*.json')):
        shutil.copy2(path, out/'topics'/path.name)
    for name, topic in topics.items():
        write_json(out/'topics'/name, topic)
    for name in ('review_queue.json', 'accounting.json', 'diagnostics.json', 'consolidation.json'):
        shutil.copy2(args.consolidated/name, out/name)
    write_json(out/'cards.json', list(cards.values()))
    write_json(out/'coordinated_actions.json', shared)
    sources = {r['card_id']: r['semantic_source'] for r in rows}
    inventory = {r['card_id']: r for r in rows}
    brief = dict(parent)
    marks = {r['card_id']: r for r in refreshed}
    brief['cards'] = [{**brief_card(c, sources[c['card_id']]), 'inventory': inventory[c['card_id']]['inventory'],
                       'consolidated_topic_id': inventory[c['card_id']]['consolidated_topic_id'],
                       'replaced_by': inventory[c['card_id']].get('replaced_by'),
                       **({'human_edits': marks[c['card_id']]['human_edits']} if marks.get(c['card_id'], {}).get('human_edits') else {}),
                       **({'tl_suggestions': marks[c['card_id']]['tl_suggestions']} if marks.get(c['card_id'], {}).get('tl_suggestions') else {}),
                       **({'supersedes_card_id': supersedes['replaced'][c['card_id']]} if supersedes and c['card_id'] in supersedes['replaced'] else {})}
                      for c in sorted(cards.values(), key=_card_order)]
    in_brief = [c for c in cards.values() if inventory[c['card_id']]['inventory'] == 'BRIEF' and c['briefing']['status'] == 'IN_BRIEFING']
    brief['counts'] = {**parent['counts'], 'cards': len(cards), 'cards_by_line': dict(Counter(c['card_line'] for c in cards.values()))}
    brief['briefing'] = {**parent['briefing'], 'in_briefing': len(in_brief),
                         'in_briefing_by_line': dict(Counter(c['card_line'] for c in in_brief)),
                         'not_in_briefing': [n for n in parent['briefing']['not_in_briefing'] if inventory[n['card_id']]['inventory'] == 'BRIEF']}
    brief['consolidation'] = {**parent['consolidation'], 'pending': [], 'refreshed': refreshed}
    brief['coordinated_actions'] = shared
    brief['usage'] = {'totals': read_json(args.refresh/'morning_brief.json')['usage']['totals'], 'note':
                      'Live requests of the refresh run; this combination and its revalidation made none.',
                      **({'targeted_regrounding': summary['targeted_regrounding']} if overlays else {})}
    brief['semantic_note'] = ('Combined briefing (zero model calls): 49 cards reused from the cached full run and 14 consolidated '
                              'issues advised live in the refresh run, revalidated offline under the current checks. Relevance '
                              'labels and consolidation decisions are developer audits (no live judgment recorded).')
    brief['derivation'] = {'version': version, 'provenance': 'OFFLINE_COMBINATION', 'model_calls': 0,
                           'parents': [rel(args.consolidated), rel(args.refresh), *(rel(r) for r in args.reground)],
                           **({'supersedes': rel(args.previous)} if args.previous else {}),
                           'parent_run_key': args.consolidated.name,
                           'refresh_run_key': args.refresh.name, 'refresh_run_instance': Run(args.refresh).instance,
                           'checks': CHECKS, 'provenance_of_parts': {
                               'agent3_advice': 'LIVE_MODEL (refresh run gpt-6.1-sol; reused cards from threadsense_full_v1)',
                               'agent1_relevance': parent['derivation']['relevance_labels'] | {'source': 'DEVELOPER_AUDIT'},
                               'agent2_consolidation': parent['derivation']['consolidation_decisions'] | {'source': consolidation['judge_provenance']}}}
    write_json(out/'morning_brief.json', brief)
    (out/'morning_brief.md').write_text(report(brief), encoding='utf-8')
    manifest = read_json(args.consolidated/'run_manifest.json')
    manifest['derivation'] = brief['derivation']
    write_json(out/'run_manifest.json', manifest)
    write_json(out/'derivation.json', {'version': version, 'summary': summary, 'inventory': rows, 'refreshed': refreshed,
                                       'targeted_regrounding': list(overlays.values()), 'supersedes': supersedes,
                                       'corrections': corrections, 'remaining_judgments': plan,
                                       'format_card': format_diagnosis(revalidated, args.format_edits),
                                       'approvals': 'Decisions bind to run_key#run_instance; this directory starts with none.'})
    print(f'Wrote {out}')
    return 0


def compare_previous(previous, cards, rows, overlays, refreshed):
    """Every card that is not a targeted re-grounding is byte-identical to the superseded combined briefing; each
    re-grounded card names the card it replaces there."""
    before = {c['card_id']: c for c in read_json(previous/'cards.json')}
    by_parent = {c['derivation']['parent_card_id']: c['card_id'] for c in before.values() if c.get('derivation')}
    regrounded = {r['card_id'] for r in refreshed if r['work_id'] in {o['work_id'] for o in overlays.values()}}
    replaced, issues = {}, []
    for cid, card in cards.items():
        if cid in regrounded:
            old = by_parent.get(card['derivation']['parent_card_id'])
            if old is None or old in cards:
                issues.append(f'{cid}: no superseded card to replace')
            replaced[cid] = old
        elif cid not in before or digest(before[cid]) != digest(card):
            issues.append(f'{cid} differs from {previous.name}')
    if set(before) - set(cards) != set(replaced.values()):
        issues.append('cards other than the re-grounded ones were removed')
    if issues:
        raise SystemExit('Comparison with the superseded briefing failed: ' + '; '.join(issues[:5]))
    return {'previous': rel(previous), 'previous_run_instance': Run(previous).instance, 'replaced': replaced,
            'unchanged_cards': len(cards) - len(replaced)}


def format_diagnosis(revalidated, edits_path):
    """The format card's rejected statements against their cited claims, and the candidate wording (not judged)."""
    edits = read_json(edits_path)
    _, _, result, _ = revalidated[edits['work_id']]
    statements = {s['statement_id']: s for s in result['grounding']['statements']}
    return {'work_id': edits['work_id'], 'cause': 'One grouped description, reused in the summary, the intervention need and the '
            'severity signal, attributes an accuracy-versus-format question to all three thread starters; the RP-3824 starter asks '
            'about a required JSON object answered in well-written prose. Every claim is SUPPORTED; the partial need withheld the '
            'action (NO_INTERVENTION_NEED) and the partial signal left severity unassessed.',
            'membership': 'Kept: both subquestions (format versus accuracy; required JSON versus prose quality) share one handling '
                          'rule (score required-format compliance separately; no universal priority; collect the pair) and each '
                          'claim names its own author and thread.',
            'rejected': [{'statement_id': sid, 'verdict': statements[sid]['verdict'], 'text': statements[sid]['text'],
                          'judge': statements[sid]['rationale'], 'evidence_ids': statements[sid]['evidence_ids']}
                         for sid in (e['statement_id'] for e in edits['edits'])],
            'candidate_wording': {'path': rel(edits_path), 'provenance': edits['provenance'],
                                  'statements': {e['statement_id']: e['text'] for e in edits['edits']}}}


if __name__ == '__main__':
    sys.exit(main())
