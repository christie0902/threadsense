"""Bounded related-record lookup over RECORDED links only (Milestone 7 investigation; the Advisor does not use it).

For decision-collection results of a search, add other records explicitly linked to them:
- forward: the returned record's source_refs name the other record's authoring document;
- backward: the other record's source_refs name the returned record;
- series: both records carry the same recorded event_series_id.
Candidates come from the same eligible set as the search (Retriever.select: scope, batch, date, type and version
filters), never include a returned document, and at most `limit` documents are added (the first eligible chunk of
each, newest first). Nothing is inferred from text similarity and no document is named in advance.
"""
LINKS = ('forward', 'backward', 'series')


def _refs(retriever, chunk):
    meta = retriever.document(chunk['document_id'], chunk['version_id'])['metadata']['source_metadata']
    return {ref['document_id'] for ref in meta.get('source_refs') or []}


def related(retriever, search, project, *, limit=2, links=LINKS, **filters):
    eligible = retriever.select(project, **filters)['eligible']
    returned = {r['document_id'] for r in search['results']}
    first = {}
    for key in sorted(eligible, key=lambda k: (retriever.chunks[k]['document_id'], retriever.chunks[k]['chunk_index'])):
        first.setdefault(retriever.chunks[key]['document_id'], key)
    found = {}
    for result in search['results']:
        m = result['metadata']
        if result['collection'] != 'decisions' or not m['authoring_document_id']:
            continue
        forward = _refs(retriever, retriever.chunks[result['chunk_id']]) if 'forward' in links else set()
        for doc, key in first.items():
            if doc in returned:
                continue
            c = retriever.chunks[key]
            cm = c['metadata']
            reasons = []
            if cm['authoring_document_id'] and cm['authoring_document_id'] in forward:
                reasons.append('forward')
            if 'backward' in links and m['authoring_document_id'] in _refs(retriever, c):
                reasons.append('backward')
            if 'series' in links and m['event_series_id'] and cm['event_series_id'] == m['event_series_id']:
                reasons.append('series')
            if reasons:
                entry = found.setdefault(doc, {'chunk_id': key, 'document_id': doc, 'links': []})
                entry['links'] += [{'link': r, 'from': m['authoring_document_id']} for r in reasons]
    ordered = sorted(found.values(), key=lambda e: retriever.chunks[e['chunk_id']]['metadata']['source_date'] or '', reverse=True)
    added = []
    for entry in ordered[:limit]:
        c = retriever.chunks[entry['chunk_id']]
        added.append({**entry, 'collection': c['collection'], 'version_id': c['version_id'], 'sections': c['sections'],
                      'text': c['text'], 'citation': c['citation'], 'metadata': c['metadata'], **eligible[entry['chunk_id']]})
    return {'added': added, 'candidates': len(ordered), 'limit': limit, 'links': list(links)}
