"""Markdown knowledge files (mock-knowledge-markdown-v1) -> the shared SourceRecord.

Parsing only: no retrieval, no chunking, no authority or precedence inference.
The full front matter is preserved in source_metadata['authoring']; canonical
record/version IDs come from SourceRecord and never depend on the file path.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

import yaml

from threadsense.knowledge_sources import SourceIdentity, SourceRecord
from threadsense.routing import aware, slack_datetime

AUTHORING_SCHEMA = 'mock-knowledge-markdown-v1'
DOCUMENT_TYPES = {'instructions': 'guideline', 'faq': 'faq', 'decision': 'decision', 'announcement': 'announcement'}
# Detailed authoring kinds -> existing canonical record_kind; the original stays in metadata.
RECORD_KINDS = {
    'decision': {'advice_review', 'follow_up', 'expert_referral', 'expert_review', 'escalation_receipt'},
    'announcement': {None, 'channel_announcement'},
    'instructions': {None}, 'faq': {None},
}
APPROVED = {'approved', 'tl_approved'}
# Bookkeeping sections: link lists duplicate source_refs; raw snapshots stay provenance.
BOOKKEEPING_SECTIONS = {'Referenced records', 'Source snapshot'}
SNAPSHOT_ENCODING = 'sha256 of UTF-8 JSON with sorted keys and separators (",", ":")'
REQUIRED = ('authoring_schema', 'document_id', 'document_type', 'project_id', 'scope', 'version',
            'effective_at', 'status', 'authority', 'source')


class _NoImplicitTimestamps(yaml.SafeLoader):
    """Safe YAML that keeps timestamps as their original strings."""


_NoImplicitTimestamps.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != 'tag:yaml.org,2002:timestamp']
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()}


def split_front_matter(text):
    match = re.match(r'\A---\n(.*?)\n---\n(.*)\Z', text.replace('\r\n', '\n'), re.S)
    if not match:
        raise ValueError('Markdown source needs YAML front matter between --- lines.')
    front = yaml.load(match.group(1), Loader=_NoImplicitTimestamps)
    if not isinstance(front, dict):
        raise ValueError('Front matter must be a mapping.')
    return front, match.group(2)


def sections(body):
    """Split at level-2 headings: [(heading or None, text)], in order, without loss."""
    parts, heading, lines = [], None, []
    for line in body.split('\n'):
        if line.startswith('## '):
            parts.append((heading, '\n'.join(lines)))
            heading, lines = line[3:].strip(), [line]
        else:
            lines.append(line)
    parts.append((heading, '\n'.join(lines)))
    return parts


def retrieval_text(body):
    return '\n'.join(text for heading, text in sections(body) if heading not in BOOKKEEPING_SECTIONS).strip()


def section_headings(body):
    return [heading for heading, _ in sections(body) if heading is not None]


def _snapshot(body):
    found = [text for heading, text in sections(body) if heading == 'Source snapshot']
    if len(found) != 1:
        raise ValueError('An embedded Slack source needs exactly one Source snapshot section.')
    block = re.search(r'```json\n(.*?)\n```', found[0], re.S)
    if not block:
        raise ValueError('Source snapshot needs one fenced JSON block.')
    return json.loads(block.group(1))


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def verify_slack_snapshot(front, snapshot):
    """Check identity and declared hashes against the embedded snapshot."""
    source, message, channel = front['source'], snapshot.get('message', {}), snapshot.get('channel', {})
    _check(source.get('evidence_location') == 'embedded:source-snapshot', 'Unsupported Slack evidence location.')
    _check(isinstance(message.get('ts'), str) and message['ts'] == source['message_id'], 'Snapshot ts differs from message_id.')
    _check(channel.get('id') == source['channel_id'], 'Snapshot channel differs from channel_id.')
    _check(message.get('user') == source.get('author_id'), 'Snapshot author differs from author_id.')
    _check(source['thread_id'] == message.get('thread_ts', message['ts']), 'Snapshot thread differs from thread_id.')
    _check(channel.get('project_id') == front['project_id'], 'Snapshot channel project differs from project_id.')
    _check(channel.get('batch_id') == front.get('batch_id'), 'Snapshot channel batch differs from batch_id.')
    text_hash = sha256(message.get('text', '').encode('utf-8')).hexdigest()
    _check(text_hash == source.get('message_text_sha256'), 'message_text_sha256 does not match snapshot text.')
    body = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    _check(sha256(body).hexdigest() == source.get('embedded_snapshot_sha256'), 'embedded_snapshot_sha256 does not match.')
    return {'message_text_sha256': 'MATCH', 'embedded_snapshot_sha256': 'MATCH', 'encoding': SNAPSHOT_ENCODING}


def _refs(values, field):
    _check(isinstance(values, list), f'{field} must be a list.')
    result = []
    for ref in values:
        _check(isinstance(ref, dict) and ref.get('document_id') and isinstance(ref.get('version'), str),
               f'{field} entries need document_id and a quoted version string.')
        # Section-level references stay section-level; never widened to a whole document.
        result.append({**deepcopy(ref), 'granularity': 'section' if ref.get('section') else 'document'})
    return result


def lifecycle(front):
    """original advice -> TL response -> execution -> outcome, as recorded (no mapping)."""
    if 'decision_status' not in front:
        return None
    return {'original_advice': deepcopy(front.get('originating_advice')),
            'tl_response': deepcopy(front.get('tl_response')), 'decision_status': front['decision_status'],
            'execution_status': front.get('execution_status'), 'outcome_status': front.get('outcome_status'),
            'severity_override': deepcopy(front.get('severity_override'))}


def markdown_source(path):
    """Parse one Markdown knowledge file into a validated SourceRecord."""
    front, body = split_front_matter(Path(path).read_text(encoding='utf-8-sig'))
    missing = [key for key in REQUIRED if key not in front]
    _check(not missing, f'Missing front matter: {missing}.')
    _check(front['authoring_schema'] == AUTHORING_SCHEMA, f"Unsupported authoring schema {front['authoring_schema']!r}.")
    authoring_type, kind = front['document_type'], front.get('record_kind')
    _check(authoring_type in DOCUMENT_TYPES, f'Unknown document_type {authoring_type!r}.')
    _check(kind in RECORD_KINDS[authoring_type], f'record_kind {kind!r} is not mapped for {authoring_type}.')
    _check(isinstance(front['version'], str), 'version must be a quoted string (e.g. \'1.0\').')
    for field in ('effective_at', 'last_updated', 'valid_until', 'review_due_at'):
        if front.get(field) is not None:
            _check(isinstance(front[field], str), f'{field} must be a quoted timestamp string.')
            aware(front[field])
    if front.get('valid_until'):
        _check(aware(front['valid_until']) >= aware(front['effective_at']), 'valid_until precedes effective_at.')
    authority, source = front['authority'], front['source']
    _check(isinstance(authority, dict) and authority.get('role') and authority.get('provenance'),
           'authority needs role and provenance.')
    canonical = DOCUMENT_TYPES[authoring_type]
    supersession = {'supersedes': _refs(front.get('supersedes', []), 'supersedes'),
                    'superseded_by': _refs(front.get('superseded_by', []), 'superseded_by')}
    metadata = {'authoring': deepcopy(front),
                'canonical_mapping': {'authoring_document_type': authoring_type, 'document_type': canonical,
                                      'authoring_record_kind': kind, 'record_kind': canonical},
                'source_refs': _refs(front.get('source_refs', []), 'source_refs'),
                'supersession': supersession, 'section_headings': section_headings(body),
                'lifecycle': lifecycle(front)}
    status = front.get('decision_status', front['status'])
    actor = authority.get('actor_id', authority.get('approved_by'))
    record_authority = {'recorded_role': authority['role'], 'actor_id': actor, 'provenance': authority['provenance'],
                        'authoring_status': front['status'],
                        'approval_status': 'EXPLICIT_SOURCE_MARKER' if status in APPROVED else 'NO_APPROVAL_MARKER',
                        'explicit_approval': {'by': actor, 'role': authority['role'], 'status': status}
                            if status in APPROVED else None}
    scope = {'project_id': front['project_id'], 'batch_id': front.get('batch_id')}
    if source.get('system') == 'slack':
        snapshot = _snapshot(body)
        metadata.update(snapshot_verification=verify_slack_snapshot(front, snapshot),
                        root_message=deepcopy(snapshot['message']), channel=deepcopy(snapshot['channel']),
                        archive_note=retrieval_text(body))
        message = snapshot['message']
        identity = SourceIdentity(system='slack', **scope, channel_id=source['channel_id'],
                                  thread_id=source['thread_id'], message_id=source['message_id'])
        record_authority.update(author_recorded_role=authority['role'] if actor == message['user'] else None,
                                channel_membership_is_not_approval=True, reactions_are_not_approval=True)
        return SourceRecord(source=identity, scope=front['scope'], document_type=canonical, record_kind=canonical,
            original_text=message['text'],
            author={'id': message['user'], 'name': None, 'recorded_role': record_authority['author_recorded_role']},
            reactions=deepcopy(message.get('reactions', [])), source_metadata=metadata, authority=record_authority,
            created_at=slack_datetime(message['ts']).isoformat(), effective_at=front['effective_at'],
            supersedes=whole_document_supersedes(supersession))
    _check(source.get('system') == 'manual' and source.get('manual_key'), 'Manual sources need source.manual_key.')
    text = retrieval_text(body)
    _check(text, 'Markdown source has no retrievable prose.')
    # Manual records carry no creation time; last_updated stays authoring metadata.
    return SourceRecord(source=SourceIdentity(system='manual', **scope, manual_key=source['manual_key']),
        scope=front['scope'], document_type=canonical, record_kind=canonical, original_text=text,
        source_metadata=metadata, authority=record_authority, effective_at=front['effective_at'],
        supersedes=whole_document_supersedes(supersession))


def whole_document_supersedes(supersession):
    """Only whole-document references populate SourceRecord.supersedes."""
    return [f"{ref['document_id']}@{ref['version']}" for ref in supersession['supersedes']
            if ref['granularity'] == 'document']


def authoring_key(record):
    authoring = (record.get('source_metadata') or {}).get('authoring') if isinstance(record, dict) else None
    return (authoring['document_id'], authoring['version']) if authoring else None
