"""Summarize one fresh-15 run from its saved outputs only (never the answer key). Read-only.

Maps runtime IDs back to the fixture's T01-T15 and PILOT-K01-K06 (id_map.json) and writes nothing unless --write is given.

    uv run --locked python experiments/fresh_15_v1/summarize_run.py <run dir> [--write <new json path>]
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

HERE = Path(__file__).resolve().parent
ID_MAP = json.loads((HERE/'id_map.json').read_text(encoding='utf-8'))
THREAD_T = {v['thread_id']: k for k, v in ID_MAP['threads'].items()}
MESSAGE_T = {(v['channel_id'], ts): (k, i) for k, v in ID_MAP['threads'].items() for i, ts in enumerate(v['messages'])}
DOC_K = {(v['document_id'], v['version']): k for k, v in ID_MAP['knowledge'].items()}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def latest(stage_dir, prefix):
    found = sorted(p for p in Path(stage_dir).iterdir() if p.is_dir() and p.name.startswith(prefix) and not p.name.endswith('_sources'))
    return found[-1]


def evidence_label(eid):
    """m:<channel>:<ts> -> T05#1 (message index); k:<doc>@<version>:<hash> -> PILOT-K02; k:slack:<channel>:<ts>:<hash> -> T15."""
    parts = eid.split(':')
    if parts[0] == 'm' and len(parts) >= 3:
        t = MESSAGE_T.get((parts[1], parts[2]))
        return f'{t[0]}#{t[1]}' if t else eid
    if eid.startswith('k:slack:') and len(parts) >= 4:
        t = MESSAGE_T.get((parts[2], parts[3]))
        return f'{t[0]} (announcement)' if t else eid
    if parts[0] == 'k' and '@' in parts[1]:
        doc, version = parts[1].split('@', 1)
        return DOC_K.get((doc, version), eid)
    return eid


def summarize(run):
    run = Path(run)
    out = {'run': run.name}
    manifest = read(run/'run_manifest.json')
    only = manifest['configuration'].get('agent3_only')
    st = (HERE.parents[1]/only['source_run']/'stages') if only else run/'stages'  # upstream stages
    out['kind'] = manifest.get('kind')
    out['agent3_only'] = only
    out['experiment'] = {k: v for k, v in manifest['configuration']['experiment'].items() if k in ('arm', 'route_labels', 'models', 'delivery', 'transport', 'allowed_to_send')}
    out['parents'] = manifest.get('parents')
    out['resumes'] = [{'at': r['at'], 'reason': r['reason']} for r in manifest.get('resumes') or []]
    # Ingestion and routing.
    interp_dir = latest(st/'agent1_interpret', 'agent1_interpretations_v')
    routing = read(interp_dir/'routing_manifest.json')
    rejected = read(interp_dir/'review_required.json')
    ann_dir = interp_dir/'announcement_sources'
    out['ingestion'] = {'roots': routing.get('input_threads'), 'discussion': routing.get('eligible_threads'),
                        'announcement': routing.get('announcement_threads'),
                        'announcement_ids': sorted(THREAD_T.get(e['identity']['thread_id'], e['identity']['thread_id'])
                                                   for e in routing.get('entries', []) if e['route'] == 'ANNOUNCEMENT'),
                        'announcement_source_files': sorted(p.name for p in ann_dir.rglob('*.json'))[:6] if ann_dir.exists() else [],
                        'agent1_rejected': [THREAD_T.get(r['thread_id'], r['thread_id']) for r in rejected]}
    # Agent 1 verification and relevance.
    ver = read(latest(st/'agent1_verify', 'agent1_verified_v')/'interpretations.json')
    ver = ver['records'] if isinstance(ver, dict) else ver
    rel_dir = latest(st/'agent1_relevance', 'relevance_v')
    history = {h.get('thread_id') or h.get('member_id') for h in read(rel_dir/'processing_history.json')} if (rel_dir/'processing_history.json').is_file() else set()
    out['agent1'] = {}
    for r in ver:
        t = THREAD_T.get(r['thread_id'], r['thread_id'])
        i = r['interpretation']
        out['agent1'][t] = {'resolution_state': i['resolution_state'], 'verification_status': r['verification_status'],
                            'review_required': r.get('review_required'), 'review_reasons': r.get('review_reasons'),
                            'authority_messages': [evidence_label(f"m:{r['channel_id']}:{m}") for m in i.get('authority_evidence_message_ids') or []],
                            'central_question': i.get('central_question'), 'resolution_rationale': i.get('resolution_rationale'),
                            'processing_history': r['thread_id'] in history}
    out['agent1_counts'] = {'threads': len(ver), 'verification': dict(Counter(r['verification_status'] for r in ver)),
                            'review_required': sum(bool(r.get('review_required')) for r in ver), 'processing_history': len(history)}
    # Grouping and Agent 2.
    member_t = {}
    groups = []
    a2 = latest(st/'agent2', 'agent2_v')
    for d in sorted((a2/'records').iterdir()):
        if not (d/'result.json').is_file():
            continue
        inp, res = read(d/'input.json'), read(d/'result.json')
        for m in inp['members']:
            member_t[m['member_id']] = THREAD_T.get(m['thread_id'], m['thread_id'])
        groups.append({'cluster': d.name, 'state': res['processing_state'], 'threads': sorted(member_t[m['member_id']] for m in inp['members']),
                       'topics': [{'topic_id': f"{d.name}/{t.get('topic_key', '')}".rstrip('/'), 'name': t['topic_name'],
                                   'threads': sorted(member_t[m] for m in t['member_ids'])} for t in res['topics']],
                       'rejected': [member_t.get(m, m) for m in res.get('rejected_member_ids') or []],
                       'unassigned': [member_t.get(m, m) for m in res.get('unassigned_member_ids') or []]})
    a2m = read(a2/'manifest.json')
    cons = read(latest(st/'agent2_consolidate', 'consolidation_v')/'consolidation.json')
    out['agent2'] = {'groups': groups, 'retained_identities': a2m.get('retained_input_identities'),
                     'inherited_review_obligations': a2m.get('inherited_review_obligations'),
                     'consolidation': cons.get('counts')}
    # Agent 3 cards and queue.
    o3 = run/'stages'/'agent3'/'overnight_run'
    cards = read(o3/'cards.json')
    brief = read(o3/'morning_brief.json')
    topics_dir = o3/'topics'
    results = {}
    for f in topics_dir.rglob('*.json'):
        r = read(f)
        res = r.get('result') or r
        if isinstance(res, dict) and res.get('card'):
            results[res['card']['card_id']] = res
    out['cards'] = []
    for c in cards:
        res = results.get(c['card_id']) or {}
        g = res.get('grounding') or {}
        verdicts = Counter(s['verdict'] for s in g.get('statements') or [])
        a = c.get('recommended_action') or {}
        out['cards'].append({
            'card_id': c['card_id'], 'topic': c['topic_name'], 'threads': sorted(member_t.get(m, m) for m in c['lineage']['member_ids']),
            'line': c['card_line'], 'next_step': c['next_step']['status'], 'severity': c['severity']['level'],
            'review_reasons': [r['code'] for r in c['needs_review_reasons']],
            'inherited_flags': [{'kind': f['kind'], 'threads': sorted(member_t.get(m, m) for m in f.get('member_ids') or [])} for f in c['inherited_flags']],
            'action': {'type': a.get('action_type'), 'instruction': a.get('instruction'), 'scope_note': a.get('scope_note'),
                       'draft_text': a.get('draft_text')} if a else None,
            'summary': c['summary'], 'details': c.get('details'),
            'outstanding_step': c.get('outstanding_step'),
            'cited': sorted({evidence_label((s.get('note') or '').split(' ')[0]) for s in c.get('supporting_sources') or [] if s.get('note')}),
            'grounding': {'status': g.get('status'), 'verdicts': dict(verdicts),
                          'structural_issues': dict(Counter(i.get('code') for i in g.get('structural_issues') or [] if isinstance(i, dict)))},
            'cited_evidence_ids': sorted({evidence_label(e) for s in (g.get('statements') or []) if s.get('verdict') == 'SUPPORTED'
                                          for e in s.get('evidence_ids') or []}),
            'model_calls': [(m['stage'], m.get('status')) for m in res.get('model_calls') or []],
            'budget': (res.get('budget') or {}).get('consumed')})
    queue = read(o3/'review_queue.json')
    out['review_queue'] = [{'kind': q['kind'], 'threads': sorted(member_t.get(m, m) for m in q['member_ids']), 'reason': q['reason'][:200],
                            'related_cards': q['related_card_ids']} for q in queue]
    out['brief'] = {'status': brief.get('status'), 'counts': brief.get('counts'), 'accounting': (brief.get('accounting') or {}).get('status'),
                    'incomplete_work': len(brief.get('incomplete_work') or []), 'usage': (brief.get('usage') or {}).get('totals')}
    # Accounting of the 15 inputs.
    carded = {t for c in out['cards'] for t in c['threads']}
    out['input_accounting'] = {t: ('announcement -> knowledge source' if t in out['ingestion']['announcement_ids'] else
                                   'agent1 rejected' if t in out['ingestion']['agent1_rejected'] else
                                   'processing history' if out['agent1'].get(t, {}).get('processing_history') else
                                   'card' if t in carded else 'unaccounted') for t in sorted(ID_MAP['threads'])}
    # Timing, briefing check and ledger.
    out['timing'] = read(run/'timing.json') if (run/'timing.json').is_file() else None
    out['usable_briefing'] = read(run/'usable_briefing.json') if (run/'usable_briefing.json').is_file() else None
    con = sqlite3.connect(f"file:{(run/'ledger.sqlite3').as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute('select * from requests')]
    con.close()
    out['ledger'] = {'rows': len(rows), 'by_stage': {}, 'charged_usd': round(sum(r['charged_usd'] or 0 for r in rows), 6),
                     'hosts': dict(Counter(r['endpoint'].split('/')[2] for r in rows)),
                     'models': dict(Counter(f"{r['stage']}|{r['origin'].split(':')[0]}|{r['model']}|{r['returned_model']}" for r in rows)),
                     'openai_rows': sum('openai' in r['endpoint'] or 'gpt-' in (r['model'] or '') for r in rows),
                     'non_200': [{k: r[k] for k in ('stage', 'state', 'http_status', 'error')} for r in rows
                                 if r['state'] not in ('SETTLED', 'REUSED') or (r['http_status'] or 200) != 200]}
    for r in rows:
        s = out['ledger']['by_stage'].setdefault(r['stage'], Counter())
        s[f"requests_{r['origin'].split(':')[0]}"] += 1
        s['charged_usd'] += r['charged_usd'] or 0
        if r['origin'] == 'FRESH_LIVE' and r['usage']:
            u = json.loads(r['usage']) or {}  # null when the provider reported no usage (UNCERTAIN)
            s['input_tokens'] += u.get('input_tokens', u.get('prompt_tokens')) or 0
            s['output_tokens'] += u.get('output_tokens', u.get('completion_tokens')) or 0
            s['cache_read_tokens'] += u.get('cache_read_input_tokens') or (u.get('prompt_tokens_details') or {}).get('cached_tokens') or 0
            s['cache_write_tokens'] += u.get('cache_creation_input_tokens') or 0
            s['reasoning_tokens'] += (u.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
    out['ledger']['by_stage'] = {k: {kk: (round(vv, 6) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                                 for k, v in out['ledger']['by_stage'].items()}
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--write', type=Path)
    args = parser.parse_args(argv)
    report = summarize(args.run_dir)
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.write:
        if args.write.exists():
            parser.error('--write must be a new path.')
        args.write.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
