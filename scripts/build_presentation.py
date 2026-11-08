"""Presentation layer for a combined briefing, from saved records only. Zero model calls.

    uv run --locked python scripts/build_presentation.py                       # checks and prints (read-only)
    uv run --locked python scripts/build_presentation.py --write              # presentation.json + regenerated morning_brief.md

Writes nothing that binds decisions or carries judged content: the run's instance files (run_manifest, morning_brief.json,
cards.json, review_queue.json), card text, verdicts and routing are unchanged. presentation.json holds display labels and
clearly attributed editorial notes, bound to the run instance it was built for:

- active totals (briefing cards and their threads) apart from processing history, the review queue and the directory's
  historical card records;
- usage by stage from the saved ledgers (campaign ledger, refresh run, targeted checks, offline assembly);
- posting suggestions (not judged) kept apart from the judged copyable drafts, each with its saved source;
- close calls rendered as "Choose a next step" with every saved, eligible option;
- editorial notes (developer, not judged) that clarify a review point, each with its saved sources.

The original export is kept as exports/morning_brief.derivation.md before morning_brief.md is regenerated.
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

from threadsense.agents.overnight import report  # noqa: E402
from threadsense.dashboard.runs import Run  # noqa: E402

RUN = ROOT/'data/experiments/threadsense_full_v1_combined_v2'
CAMPAIGN = ROOT/'data/experiments/threadsense_full_v1'
REFRESH = ROOT/'data/experiments/threadsense_full_v1_consolidated_refresh_v1'
REGROUND = ROOT/'data/experiments/agent3_reground_v1'
CONTRACT = 'briefing-presentation-v1'
EDITORIAL = 'EDITORIAL_NOTE (developer, from saved records; not judged by a model)'
SUGGESTION = 'POSTING_SUGGESTION (developer, from saved records; not judged by a model; not part of the copyable draft)'
STATUS_NOTE = 'k:slack:C_RP_ANNOUNCEMENTS:1790936513.000019:8237860f'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def totals(run, brief):
    entries = {c['card_id']: c for c in brief['cards']}
    active = [c for c in entries.values() if c['inventory'] == 'BRIEF' and c['briefing']['status'] == 'IN_BRIEFING']
    records = Counter(c['inventory'] for c in entries.values())
    threads = {m for c in active for m in c['lineage']['member_ids']}
    return {'active_cards': len(active), 'active_threads': len(threads),
            'by_line': {k: sum(c['card_line'] == k for c in active) for k in ('NEEDS_REVIEW', 'RECOMMENDED_ACTION', 'OBSERVATION')},
            'processing_history_threads': len(brief.get('processing_history') or []),
            'review_queue_items': len(brief['model_review_queue']),
            'card_records': {'total': len(entries), 'active': len(active), 'replaced_history': records.get('REPLACED', 0),
                             'processing_history': records.get('PROCESSING_HISTORY', 0),
                             'note': 'Every card record saved in this directory, including cards replaced by combined issues '
                                     '(history) and processing-history cards; not an active total.'}}


def stage_costs():
    ledger = read_json(CAMPAIGN/'final/run_summary.json')['ledger']
    fresh = [s for s in ledger['by_stage'] if s['origin'] == 'FRESH_LIVE']
    refresh = read_json(REFRESH/'morning_brief.json')['usage']['totals']
    checks = [u for f in sorted(REGROUND.glob('*.json')) for u in read_json(f)['usage']]
    exact = sum(u['charged_usd'] for u in checks)
    return [
        {'stage': 'Full pipeline (Agent 1 to Agent 3, campaign ledger)', 'requests': sum(s['requests'] for s in fresh),
         'charged_usd': round(ledger['committed_usd'], 4), 'source': rel(CAMPAIGN/'final/run_summary.json'),
         'note': f"{sum(s['requests'] for s in ledger['by_stage'] if s['origin'] != 'FRESH_LIVE')} further responses reused at no charge."},
        {'stage': 'Consolidated-issue refresh (14 issues, Agent 3)', 'requests': refresh['requests_sent'],
         'charged_usd': round(refresh['charged_usd'], 4), 'source': rel(REFRESH/'morning_brief.json')},
        {'stage': 'Targeted grounding checks (2 cards)', 'requests': len(checks), 'charged_usd': round(exact, 3),
         'charged_usd_exact': round(exact, 6), 'source': rel(REGROUND)},
        {'stage': 'Offline assembly (combined briefings and this presentation)', 'requests': 0, 'charged_usd': 0.0,
         'source': 'derivation.json (model_calls 0)'}]


def card_named(run, name):
    return next(cid for cid, c in run.cards.items() if c['topic_name'] == name)


def note(placement, label, text, run, card_id, evidence_ids):
    ledger = {}
    for cid in run.cards:
        ledger.update(run.ledger(cid))
    missing = [e for e in evidence_ids if e not in ledger]
    if missing:
        raise SystemExit(f'{label}: sources not saved in this run: {missing}')
    return {'placement': placement, 'label': label, 'text': text, 'provenance': EDITORIAL,
            'sources': [{'evidence_id': e, 'excerpt': ledger[e]['excerpt'][:200]} for e in evidence_ids]}


def build(run_dir):
    run, brief = Run(run_dir), read_json(run_dir/'morning_brief.json')
    entries = {c['card_id']: c for c in brief['cards']}
    cards = {}

    # Format reminder: where to post (the status note's own thread) and the optional JSON-versus-prose line.
    fmt = card_named(run, 'Format compliance versus accuracy')
    status = run.evidence_entry(STATUS_NOTE)
    if 'factuality versus instruction adherence' not in status['excerpt'] or 'keep examples in this thread' not in status['excerpt']:
        raise SystemExit('The saved status note does not say what the suggestion relies on.')
    cards[fmt] = {'posting_suggestions': [
        {'label': 'Where to post', 'provenance': SUGGESTION,
         'text': 'Consider replying in the October 2, 10:21 UTC batch status note in #response-preference-announcements, '
                 'which asks people to keep factuality-versus-instruction examples in its thread.',
         'source': {'evidence_id': STATUS_NOTE, 'channel_id': 'C_RP_ANNOUNCEMENTS', 'thread_id': '1790936513.000019',
                    'posted_at': '2026-10-02T10:21:53Z', 'excerpt': status['excerpt'][:220]}},
        *[{'label': 'Optional addition when posting', 'provenance': SUGGESTION,
           'text': s['text'].removeprefix('Optional addition when posting: '), 'source': None}
          for s in entries[fmt].get('tl_suggestions') or []]]}

    # Close call: both saved, eligible options.
    nsfw = card_named(run, 'NSFW suggestive-content threshold')
    action, alts = run.cards[nsfw]['recommended_action'], run.alternatives(nsfw)
    eligible = [a for a in alts if a.get('closely_matched')]
    question = next((n.removeprefix('Open question: ') for n in run.cards[nsfw]['review_notes'] if n.startswith('Open question: ')), None)
    cards[nsfw] = {'choice': {
        'heading': 'Choose a next step', 'basis': 'Closely matched options, none preferred by the saved comparison; both passed '
                                                 'the final evidence check. The card stays in review.',
        'options': [{'label': action['label'], 'instruction': action['instruction'], 'condition': action.get('scope_note'),
                     'draft_text': action['draft_text'], 'origin': 'CARD_ACTION'}]
                   + [{'label': a['label'], 'instruction': a['instruction'], 'condition': None, 'why': a.get('rationale'),
                       'draft_text': a['draft_text'], 'origin': 'SAVED_ALTERNATIVE'} for a in eligible],
        'open_question': question, 'review_required': bool(run.cards[nsfw]['needs_review_reasons'])}}

    # Fictional-contact QN: what the inspection identified versus what stays open, next to the proposed edit.
    qn = card_named(run, 'QN handling for fictional contact details')
    finding = next(f for f in run.topics[qn]['result']['temporal']['findings'] if f['code'] == 'DOCUMENTATION_STATUS_UNRESOLVED')
    sync = next(e for e in finding['evidence_ids'] if 'doc-sync' in e)
    cards[qn] = {'editorial_notes': [note(
        'ACTION', 'Confirm before editing',
        "The earlier documentation inspection identified the old QN help page's Contact details section as the remaining "
        "stale wording. Whether the October 2 status note's “guide” refers to that same document is not established; "
        'confirm that before making this edit.', run, qn, [sync, finding['unsettled'][0], 'k:safety-qn-help-page@1.0:983cdeaa'])]}

    # Queue coverage: attribute "today" and "tomorrow" to their posts; the timezone is not recorded.
    queue = card_named(run, 'Queue coverage and closure reminders')
    cards[queue] = {'editorial_notes': [note(
        'SUMMARY', 'Timing unconfirmed',
        '“Today” is from the closure reminder posted 2026-10-01 18:40 UTC; “tomorrow” is from the coverage post '
        'posted 2026-10-02 01:14 UTC. No timezone is recorded for either post, so the days they refer to are unconfirmed.',
        run, queue, ['m:C_RP_GENERAL:1790880012.001400', 'm:C_RP_GENERAL:1790903659.000050'])]}

    return {'contract': CONTRACT, 'run_key': run.key, 'run_instance': run.instance, 'model_calls': 0,
            'provenance': 'Display layer from saved records; card text, verdicts, routing and decisions unchanged.',
            'built_from': {f: file_hash(run_dir/f) for f in ('run_manifest.json', 'morning_brief.json', 'cards.json', 'review_queue.json')},
            'totals': totals(run, brief), 'stage_costs': stage_costs(), 'cards': cards}


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args(argv)
    presentation = build(args.run)
    print(json.dumps({k: presentation[k] for k in ('totals', 'stage_costs')}, indent=1, ensure_ascii=False))
    if not args.write:
        print('Read-only: pass --write to save presentation.json and regenerate morning_brief.md.')
        return 0
    original = args.run/'exports'/'morning_brief.derivation.md'
    if not original.exists():
        original.parent.mkdir(exist_ok=True)
        shutil.copy2(args.run/'morning_brief.md', original)
    (args.run/'presentation.json').write_text(json.dumps(presentation, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (args.run/'morning_brief.md').write_text(report(read_json(args.run/'morning_brief.json'), presentation), encoding='utf-8')
    print(f"Wrote {rel(args.run/'presentation.json')} and {rel(args.run/'morning_brief.md')} (original kept at {rel(original)})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
