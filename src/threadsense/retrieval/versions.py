"""Version-aware applicability from recorded metadata only; no semantic policy resolution.

A lineage is one authoring document_id within a project and scope (or, for sources
without authoring IDs, the canonical record_id, which is version-independent).
Revisions are ordered only by source dates (effective_at, else the Slack created_at);
never by version strings, hashes, file times or ingestion time. Guidance revisions
(guidelines, FAQ) need an approval status to be current; decision records are history
and need none. Section supersession removes only the named section.

States per revision: CURRENT, SUPERSEDED_REVISION, NOT_YET_EFFECTIVE, NOT_APPROVED,
OTHER_BATCH_SCOPE, WITHDRAWN, UNRESOLVED. UNRESOLVED (ties, missing dates, ambiguous batch
scope) is never resolved here: it is reported as a diagnostic for the Advisor. A guidance
revision recorded as withdrawn ends its lineage when it is the latest: no earlier revision
becomes current again (WITHDRAWN, diagnostic WITHDRAWN_WITHOUT_REPLACEMENT). A supersedes
entry marked `withdrawn: true` removes the named section with no replacement.

Decision records are history unless `enactment` establishes a policy change: explicit TL
approval of the instruction by an authorized role, in-scope batch, effective at the reference
time, a recorded policy change (the decision declares the guidance it supersedes, or records
`policy_enacted`; an operational approval such as documentation work or an escalation is not
one), enactment (a later current announcement or guideline that links the decision through its
source_refs - preferred as the governing source - or the recorded execution state
`policy_enacted`), and no expiry, supersession or withdrawal. Approval alone, generic progress
states (posted, executed, completed, routed) and copying a draft are not enactment. A decision
that declares supersession without being enacted does not supersede anything: the reference is
reported as unverified (SUPERSEDING_DECISION_NOT_ENACTED) and the old section stays, flagged.
"""
from threadsense.routing import aware

APPROVED = frozenset({'approved', 'tl_approved'})
WITHDRAWN = frozenset({'withdrawn'})
AUTHORIZED_ROLES = frozenset({'TEAM_LEAD'})
# The only recorded execution state that names enactment of the policy change itself.
ENACTED = frozenset({'policy_enacted'})
GOVERNING_TYPES = {'announcement': 'LINKED_ANNOUNCEMENT', 'guideline': 'LINKED_GUIDELINE', 'faq': 'LINKED_GUIDELINE'}
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
    def __init__(self, chunks, refs_of=None):
        """`refs_of(document_id, version_id)`: the recorded source_refs of a source version (Retriever.document);
        without it no linked governing source can be found, so only recorded enactment counts."""
        self.lineages, self.by_authoring, self.refs_of, self._linked = {}, {}, refs_of, None
        for key, chunk in chunks.items():
            m = chunk['metadata']
            revision = self.lineages.setdefault(lineage_of(chunk), {}).setdefault(chunk['version_id'], {
                'document_id': chunk['document_id'], 'version_id': chunk['version_id'],
                'authoring_version': m['authoring_version'], 'date': _revision_date(m),
                'date_basis': 'effective_at' if m.get('effective_at') else 'created_at' if m.get('created_at') else None,
                'status': m['status'], 'collection': chunk['collection'], 'batch_id': m['batch_id'],
                'citation': {k: chunk['citation'][k] for k in ('document_id', 'version_id', 'authoring', 'title')},
                'supersedes': chunk['supersession']['document_supersedes'], 'chunk_ids': [],
                **{k: m.get(k) for k in ('document_type', 'project_id', 'decision_status', 'execution_status',
                                         'authority_role', 'approval_status', 'valid_until', 'source_system')}})
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
                elif r['collection'] in GUIDANCE and r['status'] not in APPROVED | PARTIALLY_SUPERSEDED | WITHDRAWN:
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
                elif top[0]['status'] in WITHDRAWN:  # The latest revision withdraws the guidance; nothing replaces it.
                    for r in applicable:
                        states[r['version_id']] = 'WITHDRAWN'
                else:
                    for r in applicable:
                        states[r['version_id']] = 'CURRENT' if r is top[0] else 'SUPERSEDED_REVISION'
            elif applicable:
                states[applicable[0]['version_id']] = 'WITHDRAWN' if applicable[0]['status'] in WITHDRAWN else 'CURRENT'
            kinds = [issue] if issue else ['NO_APPLICABLE_REVISION'] if not applicable and len(revisions) > 1 else []
            if any(states.get(v) == 'WITHDRAWN' for v in revisions):
                kinds.append('WITHDRAWN_WITHOUT_REPLACEMENT')
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

    def linked(self, revision):
        """Revisions whose recorded source_refs name this revision's authoring document (same project)."""
        if self.refs_of is None:
            return []
        if self._linked is None:
            self._linked = {}
            for revisions in self.lineages.values():
                for r in revisions.values():
                    for ref in self.refs_of(r['document_id'], r['version_id']) or []:
                        self._linked.setdefault((r['project_id'], ref['document_id']), []).append((r, ref))
        document_id = (revision['citation']['authoring'] or '@').split('@')[0]
        return [r for r, ref in self._linked.get((revision['project_id'], document_id), [])
                if ref.get('version') in (None, revision['authoring_version'])]

    def enactment(self, revision, states, reference, batch=None, _seen=frozenset()):
        """Whether a decision record establishes current handling at `reference` (None for other source types).
        Returns status ENACTED or NOT_ENACTED, basis (LINKED_ANNOUNCEMENT, LINKED_GUIDELINE or RECORDED_ENACTMENT),
        governing_sources (authoring IDs; a linked source is preferred over the decision itself), the missing
        evidence codes and the recorded fields checked. Only recorded metadata is read."""
        if revision.get('document_type') != 'decision':
            return None
        reference, when, missing = _time(reference), _time(revision['date']), []
        if revision['decision_status'] not in APPROVED or revision['approval_status'] != 'EXPLICIT_SOURCE_MARKER':
            missing.append('NO_TL_APPROVAL')
        if revision['authority_role'] not in AUTHORIZED_ROLES:
            missing.append('APPROVER_NOT_AUTHORIZED')
        if batch is not None and revision['batch_id'] not in (None, batch):
            missing.append('OUT_OF_SCOPE')
        if when is None:
            missing.append('NO_EFFECTIVE_DATE')
        elif reference is not None and when > reference:
            missing.append('NOT_YET_EFFECTIVE')
        if not revision['supersedes'] and revision['execution_status'] not in ENACTED:
            missing.append('NOT_A_POLICY_CHANGE')  # Nothing recorded says which rule this decision changes.
        governing = [r for r in self.linked(revision) if r.get('document_type') in GOVERNING_TYPES
                     and states.get(r['version_id']) == 'CURRENT' and (batch is None or r['batch_id'] in (None, batch))
                     and _time(r['date']) and when and _time(r['date']) >= when
                     and not (r['valid_until'] and reference and _time(r['valid_until']) < reference)
                     and (r['document_type'] != 'announcement' or (r['authority_role'] in AUTHORIZED_ROLES
                                                                  and r['execution_status'] in (None, 'posted')))]
        governing.sort(key=lambda r: (r['document_type'] != 'announcement', r['date'], r['citation']['authoring'] or ''))
        if not governing and revision['execution_status'] not in ENACTED:
            missing.append('NO_ENACTMENT_EVIDENCE')
        if revision['valid_until'] and reference and _time(revision['valid_until']) < reference:
            missing.append('EXPIRED')
        state = states.get(revision['version_id'])
        if state == 'SUPERSEDED_REVISION':
            missing.append('SUPERSEDED')
        elif state == 'WITHDRAWN':
            missing.append('WITHDRAWN')
        authoring = (revision['citation']['authoring'] or '@').split('@')
        for r, target in self.declared.get((authoring[0], revision['authoring_version']), []):
            if target['granularity'] == 'document' and r['version_id'] not in _seen and self._applies(
                    r, states, reference, batch, _seen | {revision['version_id']}):
                missing.append('WITHDRAWN' if target.get('withdrawn') else 'SUPERSEDED')
                break
        return {'status': 'NOT_ENACTED' if missing else 'ENACTED',
                'basis': None if missing else GOVERNING_TYPES[governing[0]['document_type']] if governing else 'RECORDED_ENACTMENT',
                'governing_sources': [] if missing else [r['citation']['authoring'] for r in governing] or [revision['citation']['authoring']],
                'missing': list(dict.fromkeys(missing)),
                'recorded': {k: revision[k] for k in ('decision_status', 'execution_status', 'authority_role', 'batch_id',
                                                      'valid_until')} | {'effective_at': revision['date']}}

    def _applies(self, source, states, reference, batch, seen):
        """A superseding source is applicable: approved and effective; a decision only when enacted."""
        if states.get(source['version_id']) == 'NOT_YET_EFFECTIVE' or source['status'] not in APPROVED:
            return False
        found = self.enactment(source, states, reference, batch, seen)
        return found is None or found['status'] == 'ENACTED'

    def section_supersession(self, chunk, states, reference=None, batch=None):
        """Applicable section/document supersession of this chunk, plus unverifiable references. A reference marked
        `withdrawn` removes the section with no replacement (applied with withdrawn true)."""
        m, applied, unresolved = chunk['metadata'], [], []
        if not m['authoring_document_id']:
            return applied, unresolved
        refs = [dict(r, declared_by='this_document') for r in chunk['supersession']['chunk_superseded_by']]
        for r, target in self.declared.get((m['authoring_document_id'], m['authoring_version']), []):
            if target['granularity'] == 'document' or target.get('section') in chunk['sections']:
                refs.append({'document_id': r['citation']['authoring'].split('@')[0],
                             'version': r['authoring_version'], 'section': target.get('section'),
                             'granularity': target['granularity'], 'declared_by': 'superseding_document',
                             **({'withdrawn': True} if target.get('withdrawn') else {})})
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
            elif (found := self.enactment(source, states, reference, batch)) and found['status'] != 'ENACTED':
                # Approval alone does not change policy: the old section stays, flagged as unverified supersession.
                unresolved.append({**ref, 'reason': 'SUPERSEDING_DECISION_NOT_ENACTED', 'superseding': source['citation'],
                                   'missing': found['missing']})
            else:
                applied.append({**ref, 'superseding': source['citation'], 'superseding_date': source['date'],
                                'withdrawn': bool(ref.get('withdrawn'))})
        return applied, unresolved
