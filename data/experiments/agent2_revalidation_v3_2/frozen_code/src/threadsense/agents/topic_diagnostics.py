"""Actionable, source-bound validation diagnostics for live parsing and offline replay."""
from pydantic import ValidationError
from threadsense.handoff_inputs import IDENTITY


class ConsolidationValidationError(ValueError):
    def __init__(self, category, message, path=(), *, evidence_reference=None, member_id=None):
        super().__init__(message)
        self.category, self.path = category, list(path)
        self.evidence_reference, self.member_id = evidence_reference, member_id


def diagnostic(payload, category, message, path=(), *, evidence_reference=None, member_id=None, exception_type=None):
    members = {m['member_id']: m for m in payload['members']}
    member = members.get(member_id)
    return {'stage': category, 'category': category, 'exception_type': exception_type,
            'message': message, 'field_path': list(path),
            'candidate_group_id': payload['candidate_group_id'],
            'group_identity': {k: payload[k] for k in ('project_id', 'batch_id', 'candidate_group_id')},
            'member_id': member_id,
            'member_identity': {k: member[k] for k in IDENTITY} if member else None,
            'group_member_identities': [{k: m[k] for k in IDENTITY} for m in payload['members']],
            'offending_evidence_reference': evidence_reference}


def describe_exception(payload, error):
    if isinstance(error, ConsolidationValidationError):
        return [diagnostic(payload, error.category, str(error), error.path,
                           evidence_reference=error.evidence_reference, member_id=error.member_id,
                           exception_type=type(error).__name__)]
    if isinstance(error, ValidationError):
        result = []
        for item in error.errors(include_url=False):
            category = ('malformed_json' if item['type'] == 'json_invalid' else
                        'custom_consistency' if item['type'] == 'value_error' else 'schema')
            value = item.get('input')
            ref = value if isinstance(value, dict) and ('message_id' in value or 'evidence_id' in value) else None
            detail = diagnostic(payload, category, item['msg'], item['loc'], evidence_reference=ref,
                                member_id=ref.get('member_id') if ref else None,
                                exception_type=type(error).__name__)
            detail['error_type'] = item['type']
            result.append(detail)
        return result
    return [diagnostic(payload, 'processing', f'{type(error).__name__}: processing failed; inspect saved raw evidence.',
                       exception_type=type(error).__name__)]


def legacy_diagnostics(payload, raw, error):
    """Locate a v2 validator's generic error without changing the replay verdict."""
    if isinstance(error, ValidationError):
        return describe_exception(payload, error)
    from collections import Counter
    import json
    data = json.loads(raw)
    members = {m['member_id']: m for m in payload['members']}
    assigned = [mid for t in data['topics'] for mid in t['member_ids']]
    if Counter(assigned) != Counter(members.keys()):
        return [diagnostic(payload, 'membership', str(error), ('topics',), exception_type=type(error).__name__)]
    for ti, topic in enumerate(data['topics']):
        cited = set()
        for field in ('shared_issue', 'representative_question', 'relevant_differences', 'open_questions', 'supported_answers', 'uncertainties'):
            value = topic.get(field)
            items = value if isinstance(value, list) else [value] if value else []
            for ci, claim in enumerate(items):
                path = ['topics', ti, field] + ([ci] if isinstance(value, list) else [])
                for ri, ref in enumerate(claim['evidence']):
                    loc = path + ['evidence', ri]
                    mid = ref['member_id']
                    category = None
                    if mid not in topic['member_ids']:
                        category = 'cross_topic_evidence'
                    else:
                        messages = {m['message_id']: m for m in members[mid]['original_thread']['messages']}
                        if ref['message_id'] not in messages:
                            category = 'invalid_message_reference'
                        elif ref['quote'].strip() not in messages[ref['message_id']]['text']:
                            category = 'quotation_mismatch'
                        cited.add(mid)
                    if category:
                        return [diagnostic(payload, category, str(error), loc, evidence_reference=ref,
                                           member_id=mid, exception_type=type(error).__name__)]
        if cited != set(topic['member_ids']):
            return [diagnostic(payload, 'membership', str(error), ('topics', ti), exception_type=type(error).__name__)]
        for ai, answer in enumerate(topic['supported_answers']):
            if not any(ref['message_id'] != members[ref['member_id']]['thread_id'] for ref in answer['evidence']):
                return [diagnostic(payload, 'answer_evidence', str(error), ('topics', ti, 'supported_answers', ai),
                                   evidence_reference=answer['evidence'], exception_type=type(error).__name__)]
    return [diagnostic(payload, 'custom_consistency', str(error), exception_type=type(error).__name__)]
