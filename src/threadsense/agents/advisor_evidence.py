"""Advisor evidence: index freshness, the evidence ledger, agent-facing serialization, budgets.

Everything a model sees about a source is in its evidence item: citation identity,
applicability (with any replacement), dates, scope, authority and recorded states.
The status of superseded, expired or unresolved material is also written into the
excerpt itself, so it cannot be read apart from the text. Retrieval runs only through
ResearchTools, which charges every call to a finite budget.
"""
from functools import cache
import json

from threadsense.retrieval.config import FIXTURE_ROOT, INDEX_DIR
from threadsense.retrieval.index import RetrievalIndexError

REBUILD = 'uv run --locked python scripts/build_retrieval_index.py --rebuild'
SOURCE_TYPES = ('guideline', 'faq', 'decision', 'announcement')
# How an item may be used. CURRENT_GUIDANCE supports "what applies now"; an ANNOUNCEMENT does so only once
# the draft establishes (and grounding verifies) that it is relevant and directs handling for this topic.
# Routine reminders, schedules and example-collection notes are announcements too. CURRENT_HANDLING is that
# established state; the ledger never assigns it by source type.
USES = ('CURRENT_GUIDANCE', 'CURRENT_HANDLING', 'ANNOUNCEMENT', 'PRIOR_DECISION', 'HISTORY_ONLY', 'UNRESOLVED_VERSION',
        'MEMBER_REPORT')


class StaleIndexError(RuntimeError):
    """The retrieval index does not match the current corpus or code; rebuild it."""


class BudgetExhausted(RuntimeError):
    pass


def open_retriever(index_dir=INDEX_DIR, *, encoder=None, retriever_class=None, **sources):
    """Open the index and check freshness once, before any research. Never rebuilds."""
    from threadsense.retrieval.search import Retriever
    try:
        retriever = (retriever_class or Retriever)(index_dir, encoder=encoder)
    except RetrievalIndexError as error:
        raise StaleIndexError(f'{error} Rebuild with: {REBUILD}') from None
    if retriever.staleness(**sources) != 'CURRENT':
        raise StaleIndexError(f'Retrieval index at {index_dir} is stale: the knowledge corpus, fixtures or chunking '
                              f'changed since it was built. Rebuild with: {REBUILD}')
    return retriever


class Budget:
    """Finite call ceilings per topic and per run; exceeding one raises, never waits or retries."""

    def __init__(self, limits):
        self.limits, self.used, self.topic = dict(limits), {}, {}

    def start_topic(self):
        self.topic = {}

    def charge(self, kind):
        limit = self.limits.get(f'{kind}_per_topic')
        if limit is not None and self.topic.get(kind, 0) >= limit:
            raise BudgetExhausted(f'{kind}_per_topic={limit} reached')
        total = self.limits.get(f'{kind}_total')
        if total is not None and self.used.get(kind, 0) >= total:
            raise BudgetExhausted(f'{kind}_total={total} reached')
        self.topic[kind] = self.topic.get(kind, 0) + 1
        self.used[kind] = self.used.get(kind, 0) + 1

    def remaining(self, kind):
        """Calls still allowed for this topic (None: unlimited)."""
        left = [limit - used for limit, used in ((self.limits.get(f'{kind}_per_topic'), self.topic.get(kind, 0)),
                                                 (self.limits.get(f'{kind}_total'), self.used.get(kind, 0)))
                if limit is not None]
        return min(left) if left else None

    def topic_usage(self):
        return dict(self.topic)


def knowledge_evidence_id(result):
    m = result['metadata']
    if m['authoring_document_id']:
        return f"k:{m['authoring_document_id']}@{m['authoring_version']}:{result['chunk_id'][6:14]}"
    return f"k:slack:{m['channel_id']}:{m['thread_id']}:{result['chunk_id'][6:14]}"


def use_of(result):
    """Deterministic use category from version applicability, record kind and expiry."""
    applicability = result['version']['applicability']
    if applicability == 'UNRESOLVED':
        return 'UNRESOLVED_VERSION'
    if applicability != 'CURRENT' or result.get('expired_as_of'):
        return 'HISTORY_ONLY'
    kind = result['metadata']['document_type']
    if kind in ('guideline', 'faq'):
        return 'CURRENT_GUIDANCE'
    return 'ANNOUNCEMENT' if kind == 'announcement' else 'PRIOR_DECISION'


def _replacements(version):
    return [{'replaced_by': s['superseding']['authoring'], 'section': s.get('section'),
             'replacement_effective': s.get('superseding_date')} for s in version['section_superseded_by']]


def banner(result, use):
    """Status line placed in front of the excerpt itself."""
    version, m = result['version'], result['metadata']
    if use == 'HISTORY_ONLY':
        reasons = []
        if version['applicability'] == 'SECTION_SUPERSEDED':
            reasons += [f"section '{r['section']}' superseded by {r['replaced_by']} (effective {r['replacement_effective']})"
                        for r in _replacements(version)]
        elif version['applicability'] != 'CURRENT':
            reasons.append(f"revision state {version['applicability']}")
        if result.get('expired_as_of'):
            reasons.append(f"valid_until {m['valid_until']} has passed")
        return f"[HISTORICAL - NOT CURRENT GUIDANCE: {'; '.join(reasons)}. May explain an old rule; do not apply it as current.]"
    if use == 'UNRESOLVED_VERSION':
        return '[UNRESOLVED VERSION: competing revisions could not be ordered from recorded dates/scope; do not choose one.]'
    if use == 'ANNOUNCEMENT':
        return (f"[ANNOUNCEMENT posted {m['source_date']} by {m['authority_role'] or 'unknown role'} "
                f"({m['batch_id'] or m['scope']}): not established as handling for this topic until you show it is "
                'relevant and gives a directive.]')
    if use == 'PRIOR_DECISION':
        states = '; '.join(f"{k}: {m[k]}" for k in ('decision_status', 'execution_status', 'outcome_status') if m.get(k))
        return f"[PRIOR RECORD ({m['authoring_record_kind'] or m['record_kind']}; {states or 'no recorded states'}) - history, not a standing rule.]"
    return None


def evidence_item(result, evidence_id):
    """The complete agent-facing representation of one retrieved chunk."""
    m, version, use = result['metadata'], result['version'], use_of(result)
    note = banner(result, use)
    citation = result['citation']
    return {
        'evidence_id': evidence_id, 'origin': 'retrieved_source', 'use': use,
        'citation': {'document_id': result['document_id'], 'version_id': result['version_id'], 'chunk_id': result['chunk_id'],
                     'authoring': citation['authoring'], 'title': citation['title'], 'sections': result['sections'],
                     'source': citation['source']},
        'source_type': m['document_type'], 'record_kind': m['authoring_record_kind'] or m['record_kind'],
        'applicability': {'state': version['applicability'], 'revision_state': version['state'],
                          'version_mode': version['mode'], 'replaced_by': _replacements(version),
                          'unverified_supersession': version['unverified_supersession'],
                          'supersedes': version['supersedes'],
                          'other_revisions': [{k: r[k] for k in ('authoring', 'date', 'status', 'state')}
                                              for r in version['other_revisions']]},
        'dates': {'source_date': m['source_date'], 'basis': m['source_date_basis'], 'effective_at': m['effective_at'],
                  'created_at': m['created_at'], 'valid_until': m['valid_until'], 'expired_as_of': result.get('expired_as_of'),
                  'reference_time': version['reference_time']},
        'scope': {'project_id': m['project_id'], 'batch_id': m['batch_id'], 'scope': m['scope'],
                  'batch_relation': result.get('batch_relation')},
        'authority': {'role': m['authority_role'], 'actor': m['authority_actor'], 'approval_status': m['approval_status'],
                      'provenance': m['authority_provenance']},
        'recorded_states': {k: m[k] for k in ('status', 'decision_status', 'execution_status', 'outcome_status')},
        'upstream_review': {'review_required': m['review_required'], 'review_reasons': m['review_reasons']}
            if m['review_required'] else None,
        'excerpt': f'{note}\n{result["text"]}' if note else result['text'],
    }


def withheld_item(entry):
    citation = entry['citation']
    return {'authoring': citation['authoring'], 'document_id': citation['document_id'], 'version_id': citation['version_id'],
            'sections': entry['sections'], 'state': entry['state'],
            'replaced_by': [{'replaced_by': s['superseding']['authoring'], 'section': s.get('section')}
                            for s in entry['section_superseded_by']],
            'note': 'Withheld from current-guidance results before ranking; retrievable with version_mode=history.'}


@cache
def user_directory(path=FIXTURE_ROOT/'users.json'):
    """Canonical user directory: ID -> {name, role}."""
    data = json.loads(path.read_text(encoding='utf-8'))
    return {u['id']: {'name': u['name'], 'role': u['role']} for u in (data['users'] if isinstance(data, dict) else data)}


def member_messages(members, directory=None):
    """Member Slack messages are the only incident-fact evidence. Display names come from the user directory and stay
    internal (attribution checks); models see canonical IDs and roles (model_view). Each message records who started
    its thread."""
    directory, items = user_directory() if directory is None else directory, []

    def name(user_id):
        return (directory.get(user_id) or {}).get('name')
    for member in members:
        thread = member['original_thread']
        root = next((m for m in thread['messages'] if m['message_id'] == thread['thread_id']), None)
        for message in thread['messages']:
            items.append({'evidence_id': f"m:{thread['channel_id']}:{message['message_id']}", 'origin': 'member_message',
                          'use': 'MEMBER_REPORT', 'member_id': member['member_id'], 'channel_id': thread['channel_id'],
                          'thread_id': thread['thread_id'], 'message_id': message['message_id'],
                          'author_id': message['author_id'], 'author_name': name(message['author_id']),
                          'author_role': message['author_role'], 'timestamp': message['timestamp'],
                          'thread_starter_id': root and root['author_id'], 'thread_starter_role': root and root['author_role'],
                          'reactions': [{'name': r.get('name'), 'users': [{'id': u, 'name': name(u)} for u in r.get('users') or []]}
                                        for r in message.get('reactions') or []],
                          'excerpt': message['text']})
    return items


def model_view(item):
    """What a model sees of an evidence item: people by canonical ID and role, no display names (card prose uses
    roles). The ledger keeps the names for attribution checks."""
    if item.get('origin') != 'member_message':
        return item
    return {**{k: v for k, v in item.items() if k != 'author_name'},
            'reactions': [{'name': r['name'], 'users': [u['id'] for u in r['users']]} for r in item['reactions']]}


class ResearchTools:
    """Guideline / FAQ / decision / announcement retrieval for one topic, charged to the budget."""

    def __init__(self, retriever, *, project, batch, as_of, budget, top_k=5, ledger=None):
        self.retriever, self.project, self.batch, self.as_of = retriever, project, batch, as_of
        self.budget, self.top_k = budget, top_k
        self.ledger = {} if ledger is None else ledger
        self.trace, self.withheld, self.diagnostics = [], {}, {}

    def search(self, query, *, purpose, source_types=None, version_mode='current', gap_id=None):
        step = {'step': len(self.trace) + 1, 'purpose': purpose, 'gap_id': gap_id, 'query': query,
                'source_types': list(source_types or SOURCE_TYPES), 'version_mode': version_mode,
                'as_of': self.as_of, 'batch': self.batch, 'top_k': self.top_k}
        try:
            self.budget.charge('retrieval_calls')
        except BudgetExhausted as error:
            self.trace.append({**step, 'status': 'SKIPPED_BUDGET', 'detail': str(error)})
            return None
        # as_of applies in both modes, so history never reaches past the cutoff.
        response = self.retriever.search(query, self.project, batch=self.batch, as_of=self.as_of, top_k=self.top_k,
                                         version_mode=version_mode, document_types=list(source_types) if source_types else None)
        ids, new = [], []
        for result in response['results']:
            evidence_id = knowledge_evidence_id(result)
            if evidence_id not in self.ledger:
                self.ledger[evidence_id] = evidence_item(result, evidence_id)
                new.append(evidence_id)
            ids.append(evidence_id)
        for entry in response['withheld_by_version']:
            self.withheld.setdefault(entry['chunk_id'], withheld_item(entry))
        for diagnostic in response['version_diagnostics']:
            self.diagnostics.setdefault(repr(sorted(diagnostic.items(), key=str)), diagnostic)
        self.trace.append({**step, 'status': 'DONE', 'mode': response['mode'], 'use_mmr': response['use_mmr'],
                           'mmr_lambda': response['config']['mmr_lambda'], 'result_ids': ids, 'new_evidence_ids': new,
                           'eligible_chunks': response['eligible_chunks']})
        return {'query': query, 'version_mode': version_mode, 'results': [self.ledger[i] for i in ids]}

    def notes(self):
        return {'withheld_by_version': list(self.withheld.values()), 'version_diagnostics': list(self.diagnostics.values())}
