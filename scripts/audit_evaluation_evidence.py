"""Recompute the evaluation-audit figures (docs/evaluation-audit.md) from saved runs. Zero model calls, read-only.

Every number is read from files already in the repository; nothing is written. The `disclosure` section serves the
accepted briefing through the real dashboard API (FastAPI test client, throwaway decision store in a temp directory).
Sections:
  split        the six-thread audio cluster (Agent 2, live run) against the generator's latent topics
  example      the silent-clip versus player-failure decisions (consolidation stage of the accepted briefing)
  purity       every Agent 2 topic of the live run against the same labels (agreement, not human truth)
  resolution   Agent 1 resolution states of the live run against the generator's intended states (same caveat)
  grounding    the fictional-contact card: statements, who judged them, what was withheld and why
  disclosure   withheld statement text in the card-detail and feedback API and in the static demo bundle
  routing      Observation and withheld-recommendation cards in the accepted briefing
  audits       Agent 1 verification records whose evidence audit was unavailable or invalid
  limits       ledger rows, cost scope and request counts against their limits
  control      the unanswerable negative control in the saved live pilot runs

Not reproduced here (labelled in the report): the retrieval benchmark (scripts/evaluate_retrieval.py), the temporal
benchmarks (scripts/evaluate_temporal.py), the zero-call replay (scripts/replay_overnight_topic.py), and the developer
reviews of the over-resolved threads and mixed clusters, which are hand judgments of the source threads.

    uv run --locked python scripts/audit_evaluation_evidence.py [section ...] [--bundle=<path>]

--bundle checks another copy of the demo bundle in `disclosure` (for example one downloaded from the hosted demo).
"""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.dashboard import disclosure as dsc  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

EXP = ROOT/'data/experiments'
LIVE = EXP/'threadsense_full_v1'
BRIEF = EXP/'threadsense_full_v1_combined_v2'
REFRESH = EXP/'threadsense_full_v1_consolidated_refresh_v1'
REGROUND = EXP/'agent3_reground_v1'
AGENT2 = LIVE/'stages/agent2/agent2_v1/records'
VERIFY = LIVE/'stages/agent1_verify/agent1_verified_v2'
LABELS = ROOT/'data/evaluation/thread_blueprint_200.json'
BUNDLE = [ROOT/'web/demo/briefing.json']  # Replaced by --bundle.
AUDIO = 'cluster_4460290131b816bb'
EXAMPLE_SETS = ('cand_d173932bd13d', 'cand_674e589e8b59')
CARD = 'card_a03615c8bc678a84c906d5831a4ba1b0'
ORDER = {'UNRESOLVED': 0, 'PARTIALLY_RESOLVED': 1, 'RESOLVED_IN_THREAD': 2}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def labels():
    return {x['thread_id']: x for x in read(LABELS)}


def groups():
    for d in sorted(AGENT2.iterdir()):
        if (d/'result.json').is_file():
            yield d.name, read(d/'input.json'), read(d/'result.json')


def verified():
    records = read(VERIFY/'interpretations.json')
    return records['records'] if isinstance(records, dict) else records


def result_of(run, card_id):
    topic = run.topics.get(card_id) or {}
    return topic.get('result') or topic


def split():
    lab = labels()
    _, inp, res = next(g for g in groups() if g[0] == AUDIO)
    thread = {m['member_id']: m['thread_id'] for m in inp['members']}
    out = [m for t in res['topics'] for m in t['member_ids']]
    flagged = {m['member_id'] for m in inp['members'] if m['agent1_record'].get('review_required')}
    queue = (BRIEF/'review_queue.json').read_text(encoding='utf-8')
    run = Run(BRIEF)
    carried = {m for c in run.cards.values() if run.presentation(c['card_id'])['briefing']['status'] == 'IN_BRIEFING'
               for f in c['inherited_flags'] for m in f.get('member_ids', [])}
    return {'cluster': AUDIO, 'input_threads': len(thread), 'state': res['processing_state'],
            'topics': [{'name': t['topic_name'], 'threads': [thread[m] for m in t['member_ids']],
                        'latent_labels': dict(Counter(lab[thread[m]]['latent_topic'] for m in t['member_ids']))}
                       for t in res['topics']],
            'exact_partition': sorted(out) == sorted(thread) and len(out) == len(set(out)),
            'rejected': res['rejected_member_ids'], 'unassigned': res['unassigned_member_ids'],
            'flagged_threads': sorted(thread[m] for m in flagged), 'flags_on_active_cards': len(flagged & carried),
            'flagged_in_review_queue': sum(m in queue for m in flagged)}


def example():
    """The presentation's silent-clip versus player-failure case: separate clusters before Agent 2, kept distinct at
    consolidation by prepared (developer) decisions, not by a model judgment."""
    lab = labels()
    clusters = {}
    for name, inp, res in groups():
        if name in ('cluster_3a9de1cf4cf6b8d4', 'cluster_7b875e31f162f4f3', 'cluster_e6a79dfad226e738'):
            thread = {m['member_id']: m['thread_id'] for m in inp['members']}
            clusters[name] = [{'topic': t['topic_name'], 'threads': [thread[m] for m in t['member_ids']],
                               'latent_labels': dict(Counter(lab[thread[m]]['latent_topic'] for m in t['member_ids']))}
                              for t in res['topics']]
    judged = [j for j in read(BRIEF/'consolidation.json')['judgments'] if j['candidate_set_id'] in EXAMPLE_SETS]
    return {'agent2_clusters': clusters,
            'consolidation': [{'set': j['candidate_set_id'], 'topics': j['topic_ids'], 'decision': j['judgment']['decision'],
                               'provenance': j['provenance'], 'rationale': j['judgment']['rationale']} for j in judged]}


def purity():
    """Topic purity: a thread agrees when its topic's most common latent label is its own label (numerator), over all
    threads Agent 2 placed in a topic (denominator). Full separation: a cluster whose threads carry 2+ labels counts as
    separated only if every topic Agent 2 made from it carries one label. Over-splitting is not penalised by purity,
    so single-label clusters that Agent 2 split are counted separately."""
    lab = labels()
    topics, mixed, separated, baseline, over_split = [], [], 0, 0, []
    for name, inp, res in groups():
        thread = {m['member_id']: m['thread_id'] for m in inp['members']}
        cluster = Counter(lab[t]['latent_topic'] for t in thread.values())
        baseline += cluster.most_common(1)[0][1]
        parts = [Counter(lab[thread[m]]['latent_topic'] for m in t['member_ids']) for t in res['topics']]
        topics += parts
        if len(cluster) > 1:
            ok = all(len(p) == 1 for p in parts)
            separated += ok
            if not ok:
                mixed.append({'cluster': name, 'labels': dict(cluster), 'topics': [t['topic_name'] for t in res['topics']]})
        elif len(parts) > 1:
            over_split.append({'cluster': name, 'label': next(iter(cluster)), 'topics': [t['topic_name'] for t in res['topics']]})
    members = sum(sum(p.values()) for p in topics)
    agree = sum(p.most_common(1)[0][1] for p in topics)
    return {'agent2_topics': len(topics), 'threads_in_topics': members, 'threads_matching_topic_majority': agree,
            'clustering_only_matching_cluster_majority': baseline, 'fully_pure_topics': sum(len(p) == 1 for p in topics),
            'clusters_with_mixed_labels': len(mixed) + separated, 'mixed_clusters_fully_separated': separated,
            'mixed_clusters_left_together': mixed, 'single_label_clusters_split': over_split}


def resolution():
    """Exact agreement: Agent 1's resolution_state equals the generator's intended resolution_state, over every thread
    Agent 1 verified in the live run."""
    lab = labels()
    pairs = [(r['thread_id'], lab[r['thread_id']]['resolution_state'], r['interpretation']['resolution_state'],
              r['verification_status']) for r in verified()]
    over = [{'thread': t, 'label': a, 'agent1': b, 'verification': v} for t, a, b, v in pairs if ORDER[b] > ORDER[a]]
    return {'threads': len(pairs), 'agree': sum(a == b for _, a, b, _ in pairs),
            'agent1_more_open_than_label': sum(ORDER[b] < ORDER[a] for _, a, b, _ in pairs),
            'agent1_more_resolved_than_label': len(over),
            'disagreements': {f'{a} -> {b}': n for (a, b), n in
                              Counter((a, b) for _, a, b, _ in pairs if a != b).most_common()},
            'more_resolved_threads': sorted(over, key=lambda x: -ORDER[x['agent1']])}


def grounding():
    run = Run(BRIEF)
    result = result_of(run, CARD)
    g = result['grounding']
    statements = g['statements']
    raw = next(c for c in result['model_calls'] if c['stage'] == 'grounding')['raw']
    reply = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
    model_ids = {v['statement_id'] for v in reply['verdicts']}
    held = dsc.withheld_ids(result)
    why = {d['statement_id']: d.get('withheld_because') for d in result.get('diagnostics') or []}
    card = run.cards[CARD]
    return {'card': CARD, 'semantic_source': run.semantic_source(CARD), 'card_line': card['card_line'],
            'review_reasons': [r['code'] for r in card['needs_review_reasons']], 'confidence': card['confidence'],
            'statements_in_final_grounding': len(statements), 'verdicts': dict(Counter(s['verdict'] for s in statements)),
            'judged_by_model_in_grounding_request': len(model_ids),
            'rejected_before_the_request': g.get('rejected'),
            'not_in_model_reply': sorted({s['statement_id'] for s in statements} - model_ids),
            'withheld_from_card': [{'id': sid, 'verdict': next(s['verdict'] for s in statements if s['statement_id'] == sid),
                                    'withheld_because': why.get(sid)} for sid in sorted(held)],
            'same_in_refresh_run': [s['statement_id'] for s in statements] == [
                s['statement_id'] for s in read(REFRESH/'topics/consolidated__consolidated_1eef9f984ee99bde.json')['result']
                ['grounding']['statements']]}


def disclosure():
    """Withheld statement text served per card (exact text, in that card's own detail and feedback responses), and
    withheld-only texts anywhere in the static demo bundle. A text that is also a shown, supported statement on some
    card (templated reporter sentences) is not withheld-only."""
    from fastapi.testclient import TestClient
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.runs import Catalog
    run = Run(BRIEF)
    held_by_card, shown = {}, set()
    for cid in run.cards:
        result = result_of(run, cid)
        ids = dsc.withheld_ids(result)
        texts = {d['statement_id']: d['text'] for d in result.get('diagnostics') or [] if d.get('text')}
        for s in (result.get('grounding') or {}).get('statements') or []:
            if s['statement_id'] in ids:
                texts[s['statement_id']] = s['text']
            else:
                shown.add(s['text'])
        if texts:
            held_by_card[cid] = texts
    exposed = {}
    with tempfile.TemporaryDirectory() as tmp:
        catalog = Catalog([EXP])
        catalog.runs = {BRIEF.name: catalog.get(BRIEF.name)}
        client = TestClient(create_app(catalog=catalog, store=DecisionStore(Path(tmp)/'d.sqlite3'), static_dir=Path(tmp)/'none'))
        for cid, texts in held_by_card.items():
            body = json.dumps([client.get(f'/api/runs/{BRIEF.name}/cards/{cid}').json(),
                               client.get(f'/api/runs/{BRIEF.name}/cards/{cid}/feedback').json()], ensure_ascii=False)
            hits = [sid for sid, t in texts.items() if t not in shown and json.dumps(t, ensure_ascii=False)[1:-1] in body]
            if hits:
                exposed[cid] = hits
    distinct = {t for texts in held_by_card.values() for t in texts.values()}
    only = distinct - shown
    bundle = BUNDLE[0].read_text(encoding='utf-8')
    return {'cards_with_withheld_statements': len(held_by_card),
            'withheld_statements': sum(len(t) for t in held_by_card.values()),
            'distinct_withheld_texts': len(distinct), 'also_shown_as_supported_on_another_card': len(distinct & shown),
            'distinct_withheld_only_texts': len(only),
            'api_cards_serving_withheld_text': exposed,
            'demo_bundle': str(BUNDLE[0]), 'demo_bundle_withheld_only_texts': sum(json.dumps(t, ensure_ascii=False)[1:-1] in bundle for t in only)}


def routing():
    run = Run(BRIEF)
    rows = []
    for cid, card in run.cards.items():
        if run.presentation(cid)['briefing']['status'] != 'IN_BRIEFING':
            continue
        status = card['next_step']['status']
        if card['card_line'] == 'OBSERVATION':
            verdict = {s['statement_id']: s['verdict'] for s in result_of(run, cid)['grounding']['statements']}.get('action:no_action')
            rows.append({'card': cid, 'topic': card['topic_name'], 'line': 'OBSERVATION', 'no_action_reason': verdict,
                         'review_reasons': len(card['needs_review_reasons'])})
        elif status == 'RECOMMENDATION_WITHHELD':
            step = card['outstanding_step'] or {}
            rows.append({'card': cid, 'topic': card['topic_name'], 'line': card['card_line'], 'action': card['recommended_action'],
                         'follow_up': step.get('kind'), 'follow_up_source': step.get('text_source')})
    return rows


def audits():
    records = verified()
    queue = (BRIEF/'review_queue.json').read_text(encoding='utf-8')
    hit = [r for r in records if any('unavailable or invalid' in str(x) for x in r.get('review_reasons') or [])]
    rejected = read(LIVE/'final/run_summary.json')['unfinished_work']['agent1_rejected_threads']
    return {'verified_threads': len(records), 'audit_unavailable_or_invalid': len(hit),
            'their_status': dict(Counter(r['verification_status'] for r in hit)),
            'in_briefing_review_queue': sum(r['thread_id'] in queue for r in hit),
            'agent1_rejections_recorded_as_unfinished': [(r['thread_id'], r['rule']) for r in rejected]}


def limits():
    con = sqlite3.connect(f"file:{(LIVE/'ledger.sqlite3').as_posix()}?mode=ro", uri=True)
    try:
        rows = con.execute('select origin, state, count(*), round(sum(charged_usd), 6) from requests group by 1, 2').fetchall()
        stages = con.execute('select stage, origin, count(*), round(sum(charged_usd), 6) from requests group by 1, 2').fetchall()
        over = con.execute('select count(*) from requests where charged_usd > reserved_usd + 1e-9').fetchone()[0]
        errors = con.execute("select count(*) from requests where (error is not null and error != '') or http_status != 200").fetchone()[0]
    finally:
        con.close()
    per_thread = Counter(len(list(d.glob('*.call.json'))) for d in (VERIFY/'records').iterdir() if d.is_dir())
    calls, retrievals, over_topic = Counter(), Counter(), 0
    for f in (LIVE/'stages/agent3/overnight_run/topics').rglob('*.json'):
        budget = read(f)['result']['budget']
        used, cap = budget['consumed'], budget['limits']
        calls[used['model_calls']] += 1
        retrievals[used['retrieval_calls']] += 1
        over_topic += used['model_calls'] > cap['model_calls_per_topic'] or used['retrieval_calls'] > cap['retrieval_calls_per_topic']
    refresh = read(REFRESH/'morning_brief.json')['usage']
    card_item = next(w for w in refresh['per_work_item'] if w['work_id'] == 'consolidated:consolidated_1eef9f984ee99bde')
    reground = {f.stem: round(sum(u['charged_usd'] for u in read(f)['usage']), 6) for f in sorted(REGROUND.glob('*.json'))}
    return {'live_run': {'ledger_rows': {f'{o}:{s}': {'rows': n, 'charged_usd': c} for o, s, n, c in rows},
                         'by_stage': [{'stage': s, 'origin': o, 'rows': n, 'charged_usd': c} for s, o, n, c in stages],
                         'rows_with_errors': errors, 'charged_over_reserved': over,
                         'ceiling_usd': read(LIVE/'ledger_summary.json')['limit_usd']},
            'refresh_run': {'requests_sent': refresh['totals']['requests_sent'], 'charged_usd': refresh['totals']['charged_usd'],
                            'fictional_contact_card': {'requests': card_item['requests_sent'], 'charged_usd': card_item['charged_usd']}},
            'reground_run_charged_usd': reground,
            'agent1_verify_calls_per_thread': dict(sorted(per_thread.items())), 'agent1_verify_limit': 4,
            'agent3_model_calls_per_topic': dict(sorted(calls.items())), 'agent3_retrievals_per_topic': dict(sorted(retrievals.items())),
            'agent3_limits': {'model_calls': 4, 'retrievals': 6}, 'agent3_topics_over_a_limit': over_topic}


def control():
    out = {}
    for name in ('agent3_pilot_live_v1', 'agent3_acceptance_v1'):
        r = read(EXP/name/'results/control_unsupported_payroll.json')
        draft = r['drafts']['final'] or {}
        out[name] = {'question': r['scenario']['question'], 'retrieved_results': r['retrieved_results'],
                     'model_calls': [c['stage'] for c in r['model_calls']], 'evidence_sufficiency': draft.get('evidence_sufficiency'),
                     'claims': len(draft.get('claims') or []), 'action': draft.get('action'),
                     'grounding': (r['grounding'] or {}).get('status'), 'card': r['card'], 'outcome': r['control_outcome']}
    return out


SECTIONS = {'split': split, 'example': example, 'purity': purity, 'resolution': resolution, 'grounding': grounding,
            'disclosure': disclosure, 'routing': routing, 'audits': audits, 'limits': limits, 'control': control}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    args = argv if argv is not None else sys.argv[1:]
    for a in [a for a in args if a.startswith('--bundle=')]:
        BUNDLE[0] = Path(a.split('=', 1)[1])
    names = [a for a in args if not a.startswith('--bundle=')] or list(SECTIONS)
    unknown = set(names) - set(SECTIONS)
    if unknown:
        raise SystemExit(f'Unknown section(s): {sorted(unknown)}; choose from {sorted(SECTIONS)}.')
    print(json.dumps({name: SECTIONS[name]() for name in names}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
