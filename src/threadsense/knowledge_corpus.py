"""Read-only discovery and validation of the knowledge corpus; no indexing or search.

Discovery is restricted to the documented source locations. The rubric, lexicon,
evaluation data, reports and folder READMEs are never ingested as documents.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from threadsense.knowledge_sources import iter_documents, normalize_document
from threadsense.routing import ROOT

KNOWLEDGE_ROOT = ROOT/'data/knowledge'
FIXTURE_ROOT = ROOT/'data/fixtures/slack_generated'
MARKDOWN_FOLDERS = {'instructions': {'instructions'}, 'faq': {'faq'}, 'decisions': {'decision', 'announcement'}}
EXCLUDED = {'severity_rubric.py': 'severity rubric policy, loaded separately',
            'domain_lexicon.json': 'terminology lexicon, not a document', 'README.md': 'folder README (bookkeeping)'}


def _rel(path, root):
    return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def discover(root=KNOWLEDGE_ROOT):
    root = Path(root)
    markdown = sorted(p for folder in MARKDOWN_FOLDERS for p in (root/folder).rglob('*.md') if p.name != 'README.md')
    json_files = sorted([*(root/'instructions/manual').rglob('*.json'), *(root/'faq/manual').rglob('*.json'),
                         *(p for d in ('manual', 'extracted') for p in root.glob(f'decisions/*/{d}/**/*.json'))])
    chosen = set(markdown) | set(json_files)
    excluded = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p not in chosen):
        reason = EXCLUDED.get(path.name) or ('bytecode cache' if '__pycache__' in path.parts else 'outside documented source locations')
        excluded.append({'file': _rel(path, root), 'reason': reason})
    return {'markdown': markdown, 'json': json_files, 'excluded': excluded}


def _documents(path):
    """Normalize one file in isolation so a failure is reported, not fatal."""
    return list(iter_documents([path]))


def _reference_issues(docs, root):
    """Missing targets/sections, asymmetric supersession, folder/project and broken links."""
    issues, supersession = [], []
    by_key = {(d['authoring']['document_id'], d['authoring']['version']): d for d in docs if d['authoring']}
    versions = defaultdict(list)
    for doc_id, version in by_key:
        versions[doc_id].append(version)
    for d in docs:
        meta, here = d['metadata']['source_metadata'], d['file']
        if not d['authoring']:
            continue
        for field, refs in (('source_refs', meta['source_refs']), ('supersedes', meta['supersession']['supersedes']),
                            ('superseded_by', meta['supersession']['superseded_by'])):
            for ref in refs:
                target = by_key.get((ref['document_id'], ref['version']))
                if target is None:
                    issues.append({'file': here, 'kind': 'missing_reference_target', 'field': field,
                                   'reference': f"{ref['document_id']}@{ref['version']}",
                                   'versions_in_corpus': sorted(versions.get(ref['document_id'], []))})
                # A supersession section always names a heading in the superseded document.
                elif ref.get('section') and ref['section'] not in (
                        meta if field == 'superseded_by' else target['metadata']['source_metadata'])['section_headings']:
                    issues.append({'file': here, 'kind': 'missing_reference_section', 'field': field,
                                   'reference': f"{ref['document_id']}@{ref['version']}#{ref['section']}"})
                if field == 'supersedes':
                    supersession.append({'from': f"{d['authoring']['document_id']}@{d['authoring']['version']}",
                                         'to': f"{ref['document_id']}@{ref['version']}", 'section': ref.get('section'),
                                         'granularity': ref['granularity']})
                if field in ('supersedes', 'superseded_by') and target is not None:
                    back = 'superseded_by' if field == 'supersedes' else 'supersedes'
                    mirror = [r for r in target['metadata']['source_metadata']['supersession'][back]
                              if (r['document_id'], r['version'], r.get('section')) ==
                              (d['authoring']['document_id'], d['authoring']['version'], ref.get('section'))]
                    if not mirror:
                        issues.append({'file': here, 'kind': 'asymmetric_supersession', 'field': field,
                                       'reference': f"{ref['document_id']}@{ref['version']}#{ref.get('section')}"})
        parts = Path(here).parts
        authoring_type, project = d['authoring']['document_type'], d['authoring']['project_id']
        if authoring_type not in MARKDOWN_FOLDERS.get(parts[0], {authoring_type}):
            issues.append({'file': here, 'kind': 'folder_document_type_mismatch', 'declared': authoring_type})
        if parts[0] == 'decisions' and len(parts) > 2 and parts[1] != project:
            issues.append({'file': here, 'kind': 'folder_project_mismatch', 'folder': parts[1], 'declared': project,
                           'detail': f'Front matter declares project_id {project!r} but the file is filed under '
                                     f'decisions/{parts[1]}/. Neither value is overridden; ingestion uses the declared project.'})
        for link in re.findall(r'\]\(([^)#\s]+\.md)\)', (Path(root)/here).read_text(encoding='utf-8-sig')):
            if not ((Path(root)/here).parent/link).resolve().is_file():
                issues.append({'file': here, 'kind': 'broken_markdown_link', 'link': link})
    return issues, supersession


def _fixture_messages(fixture_root):
    index = {}
    for path in sorted((Path(fixture_root)/'channels').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        for message in [*data.get('history', []), *(m for ms in data.get('replies', {}).values() for m in ms)]:
            index.setdefault((data['channel']['id'], message['ts']), message)
    return index


def _overlaps(docs, fixture_root):
    """Same Slack message or identical message text represented more than once."""
    overlaps, by_identity, by_text = [], defaultdict(list), defaultdict(list)
    for d in docs:
        source = d['metadata']['source']
        if source['system'] == 'slack':
            by_identity[(source['channel_id'], source['message_id'])].append(d['file'])
            by_text[sha256(d['metadata']['source_metadata'].get('root_message', {}).get('text', d['text']).encode('utf-8')).hexdigest()].append(d['file'])
    overlaps += [{'kind': 'same_slack_message_in_corpus', 'identity': list(k), 'files': v} for k, v in by_identity.items() if len(v) > 1]
    overlaps += [{'kind': 'same_slack_text_in_corpus', 'text_sha256': k, 'files': v} for k, v in by_text.items() if len(set(v)) > 1]
    if fixture_root is None or not Path(fixture_root).is_dir():
        return overlaps, 'FIXTURES_NOT_AVAILABLE'
    fixtures = _fixture_messages(fixture_root)
    fixture_text = defaultdict(list)
    for (channel, ts), message in fixtures.items():
        fixture_text[sha256(message.get('text', '').encode('utf-8')).hexdigest()].append([channel, ts])
    for identity, files in by_identity.items():
        if identity in fixtures:
            overlaps.append({'kind': 'corpus_slack_message_also_in_fixtures', 'identity': list(identity), 'files': files})
    for digest, files in by_text.items():
        for location in fixture_text.get(digest, []):
            if tuple(location) not in by_identity:
                overlaps.append({'kind': 'corpus_slack_text_in_other_fixture_message', 'fixture': location, 'files': files})
    return overlaps, f'checked against {len(fixtures)} fixture messages'


def validate_corpus(root=KNOWLEDGE_ROOT, *, fixture_root=FIXTURE_ROOT):
    """Normalize every discovered source and report counts and issues; writes nothing."""
    root = Path(root)
    found = discover(root)
    docs, failures, stable = [], [], True
    for path in [*found['markdown'], *found['json']]:
        rel = _rel(path, root)
        try:
            documents = _documents(path)
            again = _documents(path)
        except (ValueError, KeyError, TypeError, OSError) as error:
            failures.append({'file': rel, 'error': f'{type(error).__name__}: {error}'})
            continue
        stable &= [(d['document_id'], d['version_id']) for d in documents] == [(d['document_id'], d['version_id']) for d in again]
        for d in documents:
            d['file'] = rel
            d['authoring'] = d['metadata']['source_metadata'].get('authoring')
            docs.append(d)
    conflicts, duplicates = [], []
    claims, versions = defaultdict(set), defaultdict(list)
    for d in docs:
        versions[(d['document_id'], d['version_id'])].append(d['file'])
        if d['authoring']:
            claims[(d['authoring']['document_id'], d['authoring']['version'])].add((d['document_id'], d['version_id']))
    conflicts = [{'authoring_identity': f'{k[0]}@{k[1]}', 'canonical_versions': sorted(map(list, v))}
                 for k, v in claims.items() if len(v) > 1]
    duplicates = [{'document_id': k[0], 'version_id': k[1], 'files': v} for k, v in versions.items() if len(v) > 1]
    try:
        shared = len(list(iter_documents([*found['markdown'], *found['json']]))) if not failures else None
        shared_error = None
    except ValueError as error:
        shared, shared_error = None, str(error)
    references, supersession = _reference_issues(docs, root)
    overlaps, overlap_scope = _overlaps(docs, fixture_root)
    meta = lambda d: d['metadata']['source_metadata']
    return {
        'knowledge_root': _rel(root, ROOT) if root.resolve().is_relative_to(ROOT) else str(root),
        'discovered': {'markdown': len(found['markdown']), 'json': len(found['json'])},
        'excluded': found['excluded'],
        'normalized_documents': len(docs), 'unique_document_versions': len(versions),
        'shared_ingestion_documents': shared, 'shared_ingestion_error': shared_error,
        'counts': {
            'document_type': dict(Counter(d['metadata']['document_type'] for d in docs)),
            'authoring_record_kind': dict(Counter(str((d['authoring'] or {}).get('record_kind')) for d in docs)),
            'project_id': dict(Counter(str(d['metadata']['project_id']) for d in docs)),
            'source_system': dict(Counter(d['metadata']['source']['system'] for d in docs)),
            'status': dict(Counter(str((d['authoring'] or {}).get('status')) for d in docs)),
            'with_lifecycle': sum(meta(d).get('lifecycle') is not None for d in docs),
            'slack_snapshots_verified': sum('snapshot_verification' in meta(d) for d in docs)},
        'stable_ids_on_repeat': stable,
        'normalization_failures': failures, 'authoring_conflicts': conflicts, 'duplicate_representations': duplicates,
        'reference_issues': references, 'supersession': supersession,
        'overlapping_representations': overlaps, 'overlap_scope': overlap_scope,
        'documents': [{'file': d['file'], 'document_id': d['document_id'], 'version_id': d['version_id'],
                       'authoring': f"{d['authoring']['document_id']}@{d['authoring']['version']}" if d['authoring'] else None}
                      for d in docs]}
