"""Briefing eligibility and Observation routing (briefing-routing-v2), from saved structured results only.

Two questions are kept apart:
- Relevance: does the card belong in the team lead's morning brief? No pipeline stage judges this, so it comes from a
  versioned relevance label bound to the card's members and saved source messages (a changed thread voids the label).
  An unlabelled card stays in the brief: uncertain relevance never hides content.
- Next step: is a recommendation available? OBSERVATION needs a supported NO_ACTION reason (next step
  NO_ACTION_NEEDED). A withheld, unproven or unavailable next step keeps the card in NEEDS_REVIEW under the matching
  reason, with its outstanding step taken from statements the final grounding judged SUPPORTED, or from the card's fixed
  next-step explanation. Nothing here writes or rewords model text, invents a verdict or proposes an action.

Exclusion only moves a card to history: it needs an excluding label, a supported no-action reason, and no review
reason, inherited flag, queue item, projection gap or outstanding step; otherwise the card stays in the brief and the
blocking conditions are recorded.

v2 (labels briefing-relevance-labels-v2) adds, over v1:
- ROUTINE_ADMIN: an administrative exchange with no project finding. It can go to history while its thread is still
  open (a MONITORING step); the open status, resolution state and step are kept on the card, nothing is resolved.
- ROUTINE_NOTICE: time-bound notices (closures, shift coverage). History only when every notice's latest possible end
  is at or before the run's briefing cutoff; a notice still current at the cutoff keeps the card in the brief. Expiry
  is never read as completion: the resolution state is unchanged.
- A label's evidence_statement_ids must all be statements the final grounding judged SUPPORTED, or the label does not
  exclude the card.
Relevance is not classified automatically: it comes only from audited, input-bound labels, and unknown relevance
stays visible.
"""
from datetime import datetime
from hashlib import sha256
import json

from threadsense.agents.advice_contracts import STEP_REVIEW_CODES, AdviceCardV5

POLICY_VERSION = 'briefing-routing-v2'
LABELS_CONTRACT = 'briefing-relevance-labels-v2'
LABELS_CONTRACTS = ('briefing-relevance-labels-v1', LABELS_CONTRACT)  # v1 labels carry no v2 values or evidence.
OPEN_STATES = ('UNRESOLVED', 'PARTIALLY_RESOLVED')
EXCLUSIONS = {'SOCIAL_ONLY': 'EXCLUDED_SOCIAL', 'ROUTINE_NO_FINDING': 'HISTORY_ROUTINE', 'ROUTINE_ADMIN': 'HISTORY_ROUTINE',
              'ROUTINE_NOTICE': 'HISTORY_ROUTINE'}
FOLLOW_UP = 'Pending follow-up'
LABELS = {'WAITING_ON_REQUESTED_STEP': FOLLOW_UP, 'THREAD_STILL_OPEN': FOLLOW_UP, 'OPEN_QUESTION': FOLLOW_UP,
          'RECOMMENDATION_NEEDS_REVIEW': 'Recommendation needs review',
          'NO_ACTION_CHOICE_NEEDS_REVIEW': 'No-action choice needs review', 'NO_RECOMMENDATION': 'No recommendation available',
          'MONITORING': 'Still open (no action needed now)'}
STEP_KINDS = {'RECOMMENDATION_WITHHELD': 'RECOMMENDATION_NEEDS_REVIEW', 'NO_INTERVENTION_PROPOSED': 'NO_ACTION_CHOICE_NEEDS_REVIEW',
              'NO_RECOMMENDATION_AVAILABLE': 'NO_RECOMMENDATION'}
REASON_DETAILS = {
    'NO_ACTION_NOT_SUPPORTED': 'The advisor chose no intervention, but the final evidence check did not support its reason.',
    'RECOMMENDATION_WITHHELD': 'The advisor proposed an action that is not shown because it did not pass the checks.',
    'NO_RECOMMENDATION': 'No next step could be stated from this run.',
    'OPEN_FOLLOW_UP': 'A related thread is still open and no supported next step is shown.'}
REASON_NOTES = {'NO_ACTION_NOT_SUPPORTED': 'No-action choice needs review: its reason did not pass the evidence check.',
                'RECOMMENDATION_WITHHELD': 'Recommendation needs review: the proposed action did not pass the checks.',
                'NO_RECOMMENDATION': 'No recommendation is available for this topic.',
                'OPEN_FOLLOW_UP': 'A related thread is still open; see the pending follow-up.'}


def source_digest(result, member_ids):
    """Hash of the saved source messages of the card's members (evidence ledger excerpts): the binding of a relevance
    label. Any change to those messages, or to the member set, gives a different digest."""
    rows = sorted((e['member_id'], e['channel_id'], e['message_id'], e.get('excerpt') or '')
                  for e in (result.get('evidence_ledger') or {}).values()
                  if e.get('origin') == 'member_message' and e.get('member_id') in set(member_ids))
    payload = {'members': sorted(member_ids), 'messages': rows}
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def load_labels(raw):
    """Relevance labels keyed by sorted member IDs. raw: the parsed labels file."""
    if raw.get('contract_version') not in LABELS_CONTRACTS:
        raise ValueError(f"Unsupported relevance labels {raw.get('contract_version')!r}.")
    out = {}
    for label in raw['labels']:
        key = tuple(sorted(label['member_ids']))
        if key in out:
            raise ValueError(f"Two relevance labels cover members {list(key)}.")
        out[key] = {**label, 'label_source': raw['label_source']}
    return out


def relevance(card, result, labels):
    """(relevance, label or None, note): UNLABELLED when no label covers exactly these members or its source digest no
    longer matches the saved messages."""
    members = card['lineage']['member_ids']
    label = labels.get(tuple(sorted(members)))
    if label is None:
        return 'UNLABELLED', None, None
    if label['source_sha256'] != source_digest(result, members):
        return 'UNLABELLED', None, f"Relevance label {label['label_id']} no longer matches the saved messages; not applied."
    return label['relevance'], label, None


def _time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def notice_check(label, cutoff):
    """Blocking reasons for a ROUTINE_NOTICE label: each notice's latest possible end must be at or before the cutoff."""
    notices = label.get('notices') or []
    if not notices:
        return ['the notice label records no notices']
    if not cutoff:
        return ['the briefing cutoff is unknown']
    return [f"a notice is still current at the briefing cutoff ({n['member_id']}: latest end {n['latest_end_utc']})"
            for n in notices if _time(n['latest_end_utc']) > _time(cutoff)]


def evidence_check(label, result):
    """Blocking reasons when the label's audit evidence is not SUPPORTED in this saved result."""
    statements = _verdicts(result)
    return [f'audit evidence {sid} is not a SUPPORTED statement' for sid in label.get('evidence_statement_ids') or []
            if (statements.get(sid) or {}).get('verdict') != 'SUPPORTED']


def _verdicts(result):
    return {s['statement_id']: s for s in ((result or {}).get('grounding') or {}).get('statements') or []}


def open_threads(result):
    """Member threads the final grounding judged still open (SUPPORTED resolution statements), each with its supported
    basis and whether a SUPPORTED team-lead thread instruction in that thread is still waiting on its answer."""
    statements, draft = _verdicts(result), ((result or {}).get('drafts') or {}).get('final') or {}
    ledger = (result or {}).get('evidence_ledger') or {}
    requests = {}
    for claim in draft.get('claims') or []:
        statement = statements.get(f"claim:{claim['claim_id']}") or {}
        if claim['kind'] != 'THREAD_INSTRUCTION' or statement.get('verdict') != 'SUPPORTED':
            continue
        for eid in claim['evidence_ids']:
            entry = ledger.get(eid) or {}
            if entry.get('origin') == 'member_message' and entry.get('author_role') == 'TEAM_LEAD':
                requests.setdefault(entry['member_id'], []).append(statement['statement_id'])
    out = []
    for row in draft.get('resolution') or []:
        sid = f"resolution:{row['member_id']}"
        statement = statements.get(sid) or {}
        if row['state'] not in OPEN_STATES or statement.get('verdict') != 'SUPPORTED':
            continue
        if statement['text'] != f"Member thread {row['member_id']} is {row['state']}: {row['basis']}":
            continue  # The judged text is not this basis; nothing is reused.
        out.append({'member_id': row['member_id'], 'state': row['state'], 'basis': row['basis'], 'statement_id': sid,
                    'team_lead_requests': sorted(set(requests.get(row['member_id'], [])))})
    return out


def outstanding_step(card, result):
    """The outstanding step for a card without a supported action, or MONITORING for a supported no-action decision on an
    open thread; None when nothing is outstanding."""
    status = card['next_step']['status']
    if status == 'ACTION_RECOMMENDED':
        return None
    threads = open_threads(result)
    waiting = [t for t in threads if t['team_lead_requests']]
    question = next((s for s in _verdicts(result).values() if s['kind'] == 'OPEN_QUESTION' and s.get('verdict') == 'SUPPORTED'), None)
    if status == 'NO_ACTION_NEEDED':
        kind, chosen = ('MONITORING', threads) if threads else (None, [])
    elif waiting:  # Threads waiting on a team-lead request first, then any other open thread.
        kind, chosen = 'WAITING_ON_REQUESTED_STEP', waiting + [t for t in threads if not t['team_lead_requests']]
    elif question:
        return {'kind': 'OPEN_QUESTION', 'label': LABELS['OPEN_QUESTION'], 'details': [question['text']],
                'statement_ids': [question['statement_id']], 'text_source': 'SUPPORTED_STATEMENTS'}
    elif threads:
        kind, chosen = 'THREAD_STILL_OPEN', threads
    else:
        kind = STEP_KINDS[status]
        explanation = card['next_step'].get('explanation')
        return {'kind': kind, 'label': LABELS[kind], 'details': [explanation] if explanation else [], 'statement_ids': [],
                'text_source': 'FIXED_EXPLANATION'}
    if kind is None:
        return None
    return {'kind': kind, 'label': LABELS[kind], 'details': [t['basis'] for t in chosen],
            'statement_ids': [t['statement_id'] for t in chosen], 'text_source': 'SUPPORTED_STATEMENTS'}


def _reason(code):
    return {'code': code, 'detail': REASON_DETAILS[code], 'obligation_ids': [], 'evidence': []}


def apply(card, result, *, labels, queue_member_ids=(), projection_gap=False, cutoff=None):
    """(v5 card data without derivation, changes). card: a saved v4 card; result: its saved topic result; queue_member_ids:
    members that have a Model Review Queue item; cutoff: the run's briefing cutoff (ISO UTC), for notice labels."""
    if card.get('contract_version') != 'agent3-advice-card-v4':
        raise ValueError(f"{POLICY_VERSION} applies to v4 cards, not {card.get('contract_version')!r}.")
    status = card['next_step']['status']
    reasons, notes = list(card['needs_review_reasons']), list(card['review_notes'])
    codes, changes = {r['code'] for r in reasons}, []
    step = outstanding_step(card, result)
    added = []
    if status in STEP_REVIEW_CODES:
        added.append(STEP_REVIEW_CODES[status])
        if step['kind'] in ('WAITING_ON_REQUESTED_STEP', 'THREAD_STILL_OPEN'):
            added.append('OPEN_FOLLOW_UP')
    for code in added:
        if code not in codes:
            reasons.append(_reason(code))
            notes.append(REASON_NOTES[code])
    operational = status == 'ACTION_RECOMMENDED'
    line = 'NEEDS_REVIEW' if reasons else 'RECOMMENDED_ACTION' if operational else 'OBSERVATION'
    rel, label, label_note = relevance(card, result, labels)
    blocked = []
    if rel in EXCLUSIONS:
        members = set(card['lineage']['member_ids'])
        checks = (('it has review reasons', bool(reasons)), ('it carries inherited flags', bool(card['inherited_flags'])),
                  ('a member has a Model Review Queue item', bool(members & set(queue_member_ids))),
                  ('its threads have no assigned topic', projection_gap),
                  ('it has an outstanding step', step is not None and not (rel == 'ROUTINE_ADMIN' and step['kind'] == 'MONITORING')),
                  ('it has no supported no-action reason', status != 'NO_ACTION_NEEDED'))
        blocked = [why for why, hit in checks if hit] + evidence_check(label, result)
        if rel == 'ROUTINE_NOTICE':
            blocked += notice_check(label, cutoff)
    briefing = {'status': EXCLUSIONS[rel] if rel in EXCLUSIONS and not blocked else 'IN_BRIEFING', 'relevance': rel,
                'label_id': label['label_id'] if label else None, 'label_source': label['label_source'] if label else None,
                'kept_because': blocked + ([label_note] if label_note else []),
                'basis': label.get('basis') if label else None,
                'evidence_statement_ids': list(label.get('evidence_statement_ids') or []) if label else []}
    data = {**card, 'contract_version': 'agent3-advice-card-v5', 'card_line': line, 'needs_review_reasons': reasons,
            'review_notes': list(dict.fromkeys(notes)), 'briefing': briefing, 'outstanding_step': step}
    if line != card['card_line']:
        changes.append({'field': 'card_line', 'before': card['card_line'], 'after': line,
                        'reason': f'Next step {status}: an observation needs a supported no-action reason.'})
    if added:
        changes.append({'field': 'needs_review_reasons', 'before': sorted(codes), 'after': sorted({r['code'] for r in reasons}),
                        'reason': f'Next step {status} keeps the card in review; outstanding step {step["kind"]}.'})
    if briefing['status'] != 'IN_BRIEFING':
        kept_open = f" Its thread stays {card['resolution_status']} and its open step is kept." if step else ''
        changes.append({'field': 'briefing.status', 'before': 'IN_BRIEFING', 'after': briefing['status'],
                        'reason': f"Relevance label {label['label_id']} ({rel}): {label.get('basis') or 'no basis recorded'}"
                                  f" No review reason, flag or queue item.{kept_open}"})
    elif blocked:
        changes.append({'field': 'briefing.status', 'before': 'IN_BRIEFING', 'after': 'IN_BRIEFING',
                        'reason': f"Relevance label {label['label_id']} ({rel}) not applied: " + '; '.join(blocked) + '.'})
    if step and line == card['card_line'] and not added:
        changes.append({'field': 'outstanding_step', 'before': None, 'after': step['kind'],
                        'reason': 'Outstanding step stated from supported statements.'
                        if step['text_source'] == 'SUPPORTED_STATEMENTS' else 'Outstanding step stated from the fixed explanation.'})
    return data, changes


def validate(data):
    return AdviceCardV5.model_validate(data).model_dump(mode='json')
