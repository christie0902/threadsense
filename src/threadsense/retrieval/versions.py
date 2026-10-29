"""Version-aware applicability from recorded metadata only; no semantic policy resolution.

A lineage is one authoring document_id within a project and scope (or, for sources
without authoring IDs, the canonical record_id, which is version-independent).
Revisions are ordered only by source dates (effective_at, else the Slack created_at);
never by version strings, hashes, file times or ingestion time. Guidance revisions
(guidelines, FAQ) need an approval status to be current; decision records are history
and need none. Section supersession removes only the named section.

States per revision: CURRENT, SUPERSEDED_REVISION, NOT_YET_EFFECTIVE, NOT_APPROVED,
OTHER_BATCH_SCOPE, UNRESOLVED. UNRESOLVED (ties, missing dates, ambiguous batch
scope) is never resolved here: it is reported as a diagnostic for the Advisor.
"""
from threadsense.routing import aware

APPROVED = frozenset({'approved', 'tl_approved'})
# Approved document whose named sections were replaced; its other sections still apply.
PARTIALLY_SUPERSEDED = frozenset({'partially_superseded'})
GUIDANCE = frozenset({'guidelines', 'faq'})
CURRENT_STATES = frozenset({'CURRENT', 'UNRESOLVED'})


def _time(value):
    if not value:
        return None
    return aware(value + 'T00:00:00Z' if len(value) == 10 else value)


def lineage_of(chunk):
    m = chunk['metadata']
    if m['authoring_document_id']:
        return ('authoring', m['project_id'], m['scope'], m['authoring_document_id'])
    return ('record', chunk['document_id'])


def _revision_date(m):
    return m.get('effective_at') or m.get('created_at')


class VersionIndex:
    def __init__(self, chunks):
        self.lineages, self.by_authoring = {}, {}
        for key, chunk in chunks.items():
            m = chunk['metadata']
            revision = self.lineages.setdefault(lineage_of(chunk), {}).setdefault(chunk['version_id'], {
                'document_id': chunk['document_id'], 'version_id': chunk['version_id'],
                'authoring_version': m['authoring_version'], 'date': _revision_date(m),
                'date_basis': 'effective_at' if m.get('effective_at') else 'created_at' if m.get('created_at') else None,
                'status': m['status'], 'collection': chunk['collection'], 'batch_id': m['batch_id'],
                'citation': {k: chunk['citation'][k] for k in ('document_id', 'version_id', 'authoring', 'title')},
                'supersedes': chunk['supersession']['document_supersedes'], 'chunk_ids': []})
            revision['chunk_ids'].append(key)
            if m['authoring_document_id']:
                self.by_authoring.setdefault((m['project_id'], m['authoring_document_id'], m['authoring_version']), revision)
        # Supersession declared by the superseding side: (target id, target version) -> declaring revisions.
        self.declared = {}
        for revisions in self.lineages.values():
            for r in revisions.values():
                for target in r['supersedes']:
                    self.declared.setdefault((target['document_id'], target['version']), []).append((r, target))

    def assess(self, reference, batch=None):
        """Per-revision state and diagnostics at a reference time (as-of or index cutoff)."""
        reference = _time(reference)
        states, diagnostics = {}, []
        for lineage, revisions in self.lineages.items():
            applicable = []
            for version_id, r in revisions.items():
                when = _time(r['date'])
                if when is not None and reference is not None and when > reference:
                    states[version_id] = 'NOT_YET_EFFECTIVE'
                elif r['collection'] in GUIDANCE and r['status'] not in APPROVED | PARTIALLY_SUPERSEDED:
                    states[version_id] = 'NOT_APPROVED'
                else:
                    applicable.append(r)
            # Batch scope only chooses among revisions: an earlier-batch record with no
            # in-scope alternative stays eligible as history (results mark other_batch).
            in_scope = [r for r in applicable if batch is None or r['batch_id'] in (None, batch)]
            if batch is not None and in_scope and len(in_scope) < len(applicable):
                for r in applicable:
                    if r not in in_scope:
                        states[r['version_id']] = 'OTHER_BATCH_SCOPE'
                applicable = in_scope
            issue = None
            if len(applicable) > 1:
                dated = [r for r in applicable if r['date']]
                latest = max((_time(r['date']) for r in dated), default=None)
                top = [r for r in dated if _time(r['date']) == latest]
                if len(dated) != len(applicable):
                    issue = 'MISSING_REVISION_DATE'
                elif len(top) > 1:
                    issue = 'TIED_REVISION_DATES'
                elif batch is None and len({r['batch_id'] for r in applicable}) > 1:
                    issue = 'AMBIGUOUS_BATCH_APPLICABILITY'
                if issue:
                    for r in applicable:
                        states[r['version_id']] = 'UNRESOLVED'
                else:
                    for r in applicable:
                        states[r['version_id']] = 'CURRENT' if r is top[0] else 'SUPERSEDED_REVISION'
            elif applicable:
                states[applicable[0]['version_id']] = 'CURRENT'
            kinds = [issue] if issue else ['NO_APPLICABLE_REVISION'] if not applicable and len(revisions) > 1 else []
            if any(states[v] == 'NOT_YET_EFFECTIVE' for v in revisions):
                kinds.append('FUTURE_EFFECTIVE_REVISION')
            for kind in kinds:
                diagnostics.append({'kind': kind, 'lineage': list(lineage),
                                    'revisions': [self.describe(r, states) for r in revisions.values()]})
        return states, diagnostics

    def describe(self, revision, states):
        return {**revision['citation'], 'authoring_version': revision['authoring_version'], 'date': revision['date'],
                'date_basis': revision['date_basis'], 'status': revision['status'], 'batch_id': revision['batch_id'],
                'state': states.get(revision['version_id'])}

    def section_supersession(self, chunk, states):
        """Applicable section/document supersession of this chunk, plus unverifiable references."""
        m, applied, unresolved = chunk['metadata'], [], []
        if not m['authoring_document_id']:
            return applied, unresolved
        refs = [dict(r, declared_by='this_document') for r in chunk['supersession']['chunk_superseded_by']]
        for r, target in self.declared.get((m['authoring_document_id'], m['authoring_version']), []):
            if target['granularity'] == 'document' or target.get('section') in chunk['sections']:
                refs.append({'document_id': r['citation']['authoring'].split('@')[0],
                             'version': r['authoring_version'], 'section': target.get('section'),
                             'granularity': target['granularity'], 'declared_by': 'superseding_document'})
        seen = set()
        for ref in refs:
            key = (ref['document_id'], ref['version'], ref.get('section'))
            if key in seen:
                continue
            seen.add(key)
            source = self.by_authoring.get((m['project_id'], ref['document_id'], ref['version']))
            if source is None:
                unresolved.append({**ref, 'reason': 'SUPERSEDING_SOURCE_NOT_INDEXED'})
            elif states.get(source['version_id']) == 'NOT_YET_EFFECTIVE':
                unresolved.append({**ref, 'reason': 'SUPERSEDING_SOURCE_NOT_YET_EFFECTIVE', 'superseding': source['citation']})
            elif source['status'] not in APPROVED:
                unresolved.append({**ref, 'reason': 'SUPERSEDING_SOURCE_NOT_APPROVED', 'superseding': source['citation']})
            else:
                applied.append({**ref, 'superseding': source['citation'], 'superseding_date': source['date']})
        return applied, unresolved
