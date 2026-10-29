"""Deterministic chunks with full provenance; one chunk corpus for dense and BM25.

Guidelines/FAQ: one chunk per level-2 section, prefixed with the document title.
Decisions/announcements: the whole record when it fits; otherwise consecutive
sections packed under a header that repeats the record kind and its decision,
execution and outcome states, so proposed advice stays distinguishable from the
TL response. Oversized units split at paragraph, line, sentence, then word
boundaries. Nothing is truncated: every chunk is checked against the token limit.
"""
import re

from threadsense.knowledge_markdown import sections
from threadsense.retrieval.config import CHUNKING_VERSION, COLLECTIONS
from threadsense.routing import digest


def _authoring(metadata):
    return metadata['source_metadata'].get('authoring') or {}


def title_of(document):
    meta = document['metadata']
    for text in (document['text'], meta['source_metadata'].get('archive_note') or ''):
        first = text.lstrip().split('\n', 1)[0]
        if first.startswith('# '):
            return first[2:].strip()
    source = meta['source']
    channel = (meta['source_metadata'].get('channel') or {}).get('name') or source.get('channel_id')
    return f"Slack {meta['record_kind']} in {channel} at {meta.get('created_at')}"


def projection(document):
    """Flat, filterable view of the normalized metadata (the full metadata stays in the sidecar)."""
    meta = document['metadata']
    authoring, source = _authoring(meta), meta['source']
    inherited = (meta.get('inherited_agent1') or {}).get('agent1_record') or {}
    date = authoring.get('effective_at') or meta.get('effective_at') or meta.get('created_at')
    basis = 'effective_at' if (authoring.get('effective_at') or meta.get('effective_at')) else 'created_at' if meta.get('created_at') else None
    return {
        'document_type': meta['document_type'], 'record_kind': meta['record_kind'],
        'authoring_record_kind': authoring.get('record_kind'), 'collection': COLLECTIONS[meta['document_type']],
        'authoring_document_id': authoring.get('document_id'), 'authoring_version': authoring.get('version'),
        'project_id': source.get('project_id'), 'batch_id': source.get('batch_id'), 'scope': meta['scope'],
        'source_system': source['system'], 'channel_id': source.get('channel_id'), 'thread_id': source.get('thread_id'),
        'message_id': source.get('message_id'), 'manual_key': source.get('manual_key'),
        'status': authoring.get('status'), 'decision_status': authoring.get('decision_status'),
        'execution_status': authoring.get('execution_status'), 'outcome_status': authoring.get('outcome_status'),
        'event_series_id': authoring.get('event_series_id'), 'tags': list(authoring.get('tags') or []),
        'effective_at': meta.get('effective_at'), 'created_at': meta.get('created_at'),
        'valid_until': authoring.get('valid_until'), 'source_date': date, 'source_date_basis': basis,
        'approval_status': meta['authority'].get('approval_status'),
        'authority_role': meta['authority'].get('recorded_role') or meta['authority'].get('author_recorded_role'),
        'authority_actor': meta['authority'].get('actor_id') or (meta.get('author') or {}).get('id'),
        'authority_provenance': meta['authority'].get('provenance'),
        'review_required': inherited.get('review_required'), 'review_reasons': list(inherited.get('review_reasons') or []),
        'agent1_verification_status': inherited.get('verification_status'),
        'origin': document['origin'], 'synthetic': authoring.get('synthetic'),
    }


def citation(document, chunk_sections):
    meta, proj = document['metadata'], projection(document)
    return {'document_id': document['document_id'], 'version_id': document['version_id'],
            'authoring': f"{proj['authoring_document_id']}@{proj['authoring_version']}" if proj['authoring_document_id'] else None,
            'sections': chunk_sections, 'source': meta['citation_provenance'], 'source_file': document['source_file'],
            'title': title_of(document)}


def _header(document):
    proj, title = projection(document), title_of(document)
    if proj['collection'] != 'decisions':
        return title
    states = [f"{label}: {proj[key]}" for label, key in (
        ('record', 'authoring_record_kind'), ('decision status', 'decision_status'),
        ('execution', 'execution_status'), ('outcome', 'outcome_status')) if proj.get(key)]
    return title + (f"\n[{'; '.join(states)}]" if states else '')


def _split_text(text, budget, count):
    """Split one oversized unit at the coarsest boundary that fits; never drop text."""
    for pattern in (r'\n\s*\n', r'\n', r'(?<=[.!?])\s+'):
        parts = [p for p in re.split(pattern, text) if p.strip()]
        if len(parts) > 1:
            return [piece for part in parts for piece in
                    ([part] if count(part) <= budget else _split_text(part, budget, count))]
    words, pieces, current = text.split(), [], []
    for word in words:
        if current and count(' '.join([*current, word])) > budget:
            pieces.append(' '.join(current))
            current = []
        current.append(word)
    return pieces + ([' '.join(current)] if current else [])


def _pack(units, header, count, limit):
    """Greedily pack (sections, text) units into chunks within the limit."""
    chunks, current_sections, current = [], [], []
    for unit_sections, text in units:
        candidate = '\n\n'.join([header, *current, text])
        if current and count(candidate) > limit:
            chunks.append((current_sections, current))
            current_sections, current = [], []
        current_sections = [*current_sections, *[s for s in unit_sections if s not in current_sections]]
        current.append(text)
    if current:
        chunks.append((current_sections, current))
    return chunks


def chunk_document(document, count, limit):
    meta = document['metadata']
    collection = COLLECTIONS[meta['document_type']]
    header = _header(document)
    parts = sections(document['text'])
    if parts and parts[0][0] is None and parts[0][1].strip().startswith('# ') and '\n' not in parts[0][1].strip():
        parts = parts[1:]  # A title-only preamble is already in the header.
    elif parts and parts[0][0] is None:
        parts[0] = ('Preamble' if len(parts) > 1 else None, parts[0][1])
    whole = '\n\n'.join([header, document['text'].strip()])
    if collection == 'decisions' and count(whole) <= limit:
        planned = [([h for h, _ in parts if h], [document['text'].strip()])]
    else:
        units = []
        for heading, text in parts:
            text = text.strip()
            label = [heading] if heading else []
            if count('\n\n'.join([header, text])) <= limit:
                units.append((label, text))
                continue
            first, rest = (text.split('\n', 1) + [''])[:2] if heading else ('', text)
            pieces = _split_text(rest, limit - count(header) - count(first) - 8, count)
            units += [(label, f"{first} (part {i}/{len(pieces)})\n{piece}" if heading else piece)
                      for i, piece in enumerate(pieces, 1)]
        if collection == 'decisions':
            planned = _pack(units, header, count, limit)
        else:
            planned = [(label, [text]) for label, text in units]
    supersession = meta['source_metadata'].get('supersession') or {'supersedes': [], 'superseded_by': []}
    chunks = []
    for index, (chunk_sections, texts) in enumerate(planned):
        body = '\n\n'.join(texts)
        indexed = '\n\n'.join([header, body])
        tokens = count(indexed)
        if tokens > limit:
            raise ValueError(f"{document['document_id']} chunk {index} exceeds {limit} tokens ({tokens}).")
        superseded = [ref for ref in supersession['superseded_by']
                      if ref['granularity'] == 'document' or ref.get('section') in chunk_sections]
        chunks.append({
            'chunk_id': 'chunk_' + digest([CHUNKING_VERSION, document['document_id'], document['version_id'], index])[:32],
            'collection': collection, 'document_id': document['document_id'], 'version_id': document['version_id'],
            'chunk_index': index, 'chunk_count': len(planned), 'sections': chunk_sections,
            'text': body, 'indexed_text': indexed, 'token_count': tokens,
            'citation': citation(document, chunk_sections), 'metadata': projection(document),
            'supersession': {'chunk_superseded_by': superseded, 'document_supersedes': supersession['supersedes'],
                             'document_superseded_by': supersession['superseded_by']},
        })
    covered = ''.join(c['text'] for c in chunks)
    for heading, text in parts:
        for word in re.findall(r'\w+', text)[:3] + re.findall(r'\w+', text)[-3:]:
            if word not in covered:
                raise ValueError(f"{document['document_id']}: chunking lost content near {heading!r}.")
    return chunks
