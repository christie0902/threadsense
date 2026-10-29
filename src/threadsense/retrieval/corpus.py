"""Collect normalized documents for indexing; no model calls, no source writes.

Authored knowledge comes through knowledge_corpus.discover + iter_documents.
Current-day announcements come through the existing fixture routing and
extract_announcement path, carrying any matching Agent 1 canonical member.
"""
from collections import Counter
from pathlib import Path

from threadsense.knowledge_corpus import discover
from threadsense.knowledge_sources import extract_announcement, iter_documents, normalize_document
from threadsense.routing import IDENTITY, ROOT, digest
from threadsense.source_ingestion import existing_canonical_members, fixture_routes


def _rel(path, root):
    path = Path(path).resolve()
    return path.relative_to(Path(root).resolve()).as_posix() if path.is_relative_to(Path(root).resolve()) else path.name


def knowledge_documents(knowledge_root):
    found = discover(knowledge_root)
    documents = []
    for path in [*found['markdown'], *found['json']]:
        for document in iter_documents([path]):
            documents.append({**document, 'origin': 'knowledge_store', 'source_file': _rel(path, knowledge_root)})
    # The shared iterator also rejects conflicting authoring identities across files.
    shared = list(iter_documents([*found['markdown'], *found['json']]))
    return documents, len(shared)


def current_day_announcements(fixture_root, cutoff, canonical_members=None):
    """Announcement threads with activity in [cutoff-24h, cutoff), via the existing extractor."""
    discussion, announcements, routes = fixture_routes(fixture_root, cutoff=cutoff)
    members = existing_canonical_members() if canonical_members is None else canonical_members
    by_identity = {tuple(m[k] for k in IDENTITY): m for m in members}
    documents, failures = [], list(routes.get('selection_failures', []))
    for thread in announcements:
        key = tuple(thread.get(k) for k in IDENTITY)
        try:
            # captured_at is the snapshot cutoff so builds are reproducible; it is a
            # receipt excluded from version hashes, never a source date.
            record = extract_announcement(thread, captured_at=cutoff, canonical_member=by_identity.get(key))
        except (ValueError, KeyError, TypeError) as error:
            failures.append({'identity': dict(zip(IDENTITY, key)), 'error': str(error)})
            continue
        documents.append({**normalize_document(record), 'origin': 'current_day_extraction',
                          'source_file': f"{_rel(fixture_root, ROOT)}#{thread['channel_id']}/{thread['thread_id']}"})
    receipt = {'fixture_root': _rel(fixture_root, ROOT), 'cutoff': cutoff, 'window': routes.get('window'),
               'source_threads_in_window': routes.get('source_threads_in_window'),
               'discussion_threads': len(discussion), 'announcement_threads': len(announcements),
               'extracted': len(documents), 'with_inherited_agent1': sum(d['metadata']['inherited_agent1'] is not None for d in documents),
               'extraction_failures': failures}
    return documents, receipt


def collect(knowledge_root, fixture_root, cutoff, canonical_members=None):
    """Deduplicate identical (document, version) pairs; report overlapping Slack messages."""
    knowledge, shared_count = knowledge_documents(knowledge_root)
    announcements, receipt = current_day_announcements(Path(fixture_root), cutoff, canonical_members)
    unique, duplicates = {}, []
    for document in [*knowledge, *announcements]:
        key = (document['document_id'], document['version_id'])
        if key in unique:
            duplicates.append({'document_id': key[0], 'version_id': key[1], 'source_file': document['source_file']})
            continue
        unique[key] = document
    documents = list(unique.values())
    slack = Counter((d['metadata']['source']['channel_id'], d['metadata']['source']['message_id'])
                    for d in documents if d['metadata']['source']['system'] == 'slack')
    overlaps = [{'channel_id': c, 'message_id': m, 'documents': n} for (c, m), n in slack.items() if n > 1]
    fingerprint = digest(sorted([d['document_id'], d['version_id']] for d in documents))
    return documents, {'knowledge_documents': len(knowledge), 'shared_iterator_documents': shared_count,
                       'current_day_announcements': receipt, 'duplicates_removed': duplicates,
                       'overlapping_slack_messages': overlaps, 'documents': len(documents),
                       'corpus_fingerprint': fingerprint}
