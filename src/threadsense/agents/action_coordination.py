"""Shared actions (action-coordination-v1): one briefing action for distinct topics that support the same verified edit.

Coordination is separate from topic consolidation and never implies a shared root cause. Two cards are coordinated only
when both show a supported operational action (next step ACTION_RECOMMENDED) and their saved proposals match exactly in
action type and structured targets: the same document version, section and kind of change. Wording is never compared.
Each card keeps its own text, review reasons and decisions; the shared entry only links them. A proposal on the same
target whose action was withheld is listed as related, never coordinated.
"""
from hashlib import sha256
import json

VERSION = 'action-coordination-v1'


def _document(evidence_id):
    """'k:<document>@<version>:<chunk>' -> '<document>@<version>' (the chunk is not part of the target)."""
    parts = (evidence_id or '').split(':')
    return parts[1] if len(parts) >= 3 and parts[0] == 'k' else evidence_id


def target_key(proposal):
    """(action_type, targets) of a saved proposal, or None when it names no structured target."""
    targets = sorted((_document(t['evidence_id']), t['section'], t['change']) for t in proposal.get('targets') or [])
    return (proposal['action_type'], tuple(targets)) if targets else None


def coordinate(entries):
    """entries: [{'card': card dict, 'proposal': saved final proposed_action or None}]."""
    shown, withheld = {}, {}
    for e in entries:
        card, proposal = e['card'], e['proposal']
        key = target_key(proposal) if proposal else None
        if key is None or proposal['action_type'] == 'NO_ACTION':
            continue
        (shown if card['next_step']['status'] == 'ACTION_RECOMMENDED' else withheld).setdefault(key, []).append(e)
    actions, related = [], []
    for key, group in sorted(shown.items()):
        topics = {e['card']['lineage']['topic_id'] for e in group}
        if len(group) < 2 or len(topics) < 2:
            continue
        action_type, targets = key
        actions.append({
            'action_id': 'shared_' + sha256(json.dumps([action_type, targets]).encode()).hexdigest()[:12],
            'action_type': action_type, 'label': group[0]['card']['recommended_action']['label'],
            'targets': [{'document': d, 'section': s, 'change': c} for d, s, c in targets],
            'match': {'action_type': True, 'document_version': True, 'section': True, 'change': True,
                      'basis': 'saved proposals: identical action type and structured targets; wording not compared'},
            'shared_cause': False,
            'note': 'Distinct topics support the same edit; this does not mean they share a cause.',
            'cards': [{'card_id': e['card']['card_id'], 'topic_id': e['card']['lineage']['topic_id'],
                       'topic_name': e['card']['topic_name'], 'card_line': e['card']['card_line'],
                       'review_codes': sorted({r['code'] for r in e['card']['needs_review_reasons']}),
                       'instruction': e['card']['recommended_action'].get('instruction'),
                       'scope_note': e['card']['recommended_action'].get('scope_note')} for e in group],
            'related_withheld': [{'card_id': w['card']['card_id'], 'topic_name': w['card']['topic_name'],
                                  'next_step': w['card']['next_step']['status']} for w in withheld.get(key, [])]})
    # Withheld proposals naming a coordinated document section with a different change.
    sections = {(t['document'], t['section']) for a in actions for t in a['targets']}
    listed = {w['card_id'] for a in actions for w in a['related_withheld']}
    for key, group in sorted(withheld.items()):
        for e in group:
            if any((d, s) in sections for d, s, _ in key[1]) and e['card']['card_id'] not in listed:
                related.append({'card_id': e['card']['card_id'], 'topic_name': e['card']['topic_name'],
                                'next_step': e['card']['next_step']['status'],
                                'targets': [{'document': d, 'section': s, 'change': c} for d, s, c in key[1]],
                                'why_not_coordinated': 'its proposed action was not shown (withheld by the checks)'})
    return {'version': VERSION, 'coordinated_actions': actions, 'related_unverified_proposals': related}


def entries_from_results(results):
    """Coordination entries from saved topic results ({'card', 'drafts'})."""
    return [{'card': r['card'], 'proposal': ((r.get('drafts') or {}).get('final') or {}).get('proposed_action')}
            for r in results if r.get('card')]
