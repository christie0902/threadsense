"""Deterministic request-local aliases and exact original-message evidence."""
from copy import deepcopy
from threadsense.handoff_inputs import IDENTITY, identity
from threadsense.agents.thread_interpreter import AUTHORITY_ENDORSEMENTS


def evidence_catalog(payload):
    members, entries = {}, {}
    for index, member in enumerate(sorted(payload['members'], key=lambda m: tuple(str(x) for x in identity(m))), 1):
        alias = f'M{index:02d}'
        members[alias] = member
        for message in member['original_thread']['messages']:
            eid = f'E{len(entries) + 1:03d}'
            entries[eid] = {
                'evidence_id': eid, 'member_id': alias, 'canonical_member_id': member['member_id'],
                **{k: member[k] for k in IDENTITY},
                'message_id': message['message_id'], 'quote': message['text'],
                'is_reply': message['message_id'] != member['thread_id'],
                'author_id': message['author_id'], 'author_name': message['author_name'],
                'author_role': message['author_role'], 'reactions': deepcopy(message['reactions']),
            }
    return members, entries


def tl_endorsements(entry):
    return [{'reaction': r['name'], 'user_id': uid, 'target_message_id': entry['message_id']}
            for r in entry['reactions'] if r['name'] in AUTHORITY_ENDORSEMENTS
            for uid in r['users'] if r.get('reactor_roles', {}).get(uid) == 'TEAM_LEAD']


def resolve_reference(entry):
    return {'evidence_id': entry['evidence_id'], 'member_id': entry['canonical_member_id'],
            **{k: entry[k] for k in IDENTITY}, 'message_id': entry['message_id'],
            'quote': entry['quote'], 'quotation_scope': 'entire_original_message',
            'author_id': entry['author_id'], 'author_role': entry['author_role'],
            'reactions': deepcopy(entry['reactions']), 'tl_endorsements': tl_endorsements(entry)}


def resolve_cited_fields(value, catalog):
    """Add exact quotations; keep evidence IDs for source traceability."""
    if isinstance(value, list):
        return [resolve_cited_fields(v, catalog) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: resolve_cited_fields(v, catalog) for k, v in value.items()}
    if 'evidence_ids' in result:
        result['evidence'] = [resolve_reference(catalog[eid]) for eid in result['evidence_ids']]
    return result
