"""Opt-in adaptive follow-up research (experiment; the production path stays 'batch').

batch (production): the draft names up to MAX_FOLLOW_UPS follow-up queries; all run together, then one revision.
react (opt-in): one query at a time. After each observation the revision step, which is needed anyway once new
evidence arrives, either finalizes the draft or names ONE targeted query for a gap the observation left open (written
from what it showed); at most MAX_ADAPTIVE_FOLLOW_UPS searches. Only that sequence demonstrates that a result changes
the next search; several queries written together do not.

Stops, recorded with every step's gap, query, returned and newly recovered evidence: NO_GAP (the draft names no
follow-up), GAP_FILLED (the revision no longer lists the gap), CONTROLLER_STOP (the revision kept the gap open but asked
for no further search), REPEATED_QUERY, NO_NEW_EVIDENCE (a search added nothing to the ledger; no revision is sent
for it), RETRIEVAL_BUDGET, FOLLOW_UP_LIMIT and REQUEST_CEILING. Model requests (revisions) are counted apart from local
searches. The four-request topic ceiling and the reserved grounding call are unchanged: before a revision may ask for a
second search, the remaining requests must cover a second revision, the option comparison if it would be triggered
and the final grounding; otherwise the revision is sent in final mode and the stop says a fifth request would have
been needed. No required stage is skipped to make room. Finding a record is reported apart from using it: `used`
needs the revised draft to cite it.
"""
import re

RESEARCH_MODES = ('batch', 'react')
MAX_ADAPTIVE_FOLLOW_UPS = 2
STOPWORDS = frozenset('a an and are as at by for from in into is it of on or than that the their this to was were with'.split())


def query_key(query):
    """Queries that differ only in case, punctuation or spacing are the same query."""
    return ' '.join(re.findall(r'\w+', (query or '').lower()))


def _terms(text):
    return {t for t in re.findall(r'[\w@.-]+', (text or '').lower().replace('—', ' ')) if t not in STOPWORDS and len(t) > 2}


def observation_terms(query, observation, earlier):
    """Query terms traceable to the previous observation: words or identifiers in the new query that appear in an
    observed item's title, authoring, sections or source date but in no earlier query or the topic label. Applies to
    any controller (model or scripted); it shows that the observation shaped the query, not why."""
    before = set().union(*(_terms(t) for t in earlier)) if earlier else set()
    found, sources = set(), []
    for item in observation:
        c = item.get('citation') or {}
        vocabulary = _terms(' '.join([c.get('title') or '', c.get('authoring') or '', ' '.join(c.get('sections') or []),
                                      ((item.get('dates') or {}).get('source_date') or '')[:10]]))
        hit = (_terms(query) & vocabulary) - before
        if hit:
            found |= hit
            sources.append(item['evidence_id'])
    return {'terms': sorted(found), 'evidence_ids': sources}


def gap_request(draft, exclude=()):
    """The first gap in a draft that names a follow-up query (None when none does)."""
    for gap in getattr(draft, 'gaps', None) or []:
        if gap.follow_up and gap.gap_id not in exclude:
            return {'gap_id': gap.gap_id, 'need': gap.need, 'query': gap.follow_up.query,
                    'source_types': list(gap.follow_up.source_types or []) or None, 'version_mode': gap.follow_up.version_mode}
    return None


def adaptive_research(tools, first, revise, *, room_for_another, topic_text='', max_follow_ups=MAX_ADAPTIVE_FOLLOW_UPS):
    """Sequential follow-ups. `first`: the draft's request (gap_request) or None. `revise(may_search, steps)` sends one
    revision (one model request) and returns {'draft', 'request', 'filled'} or None if it failed; with may_search False
    it must not return a request. `room_for_another()` -> (ok, note): whether a second search still fits the ceiling."""
    steps, seen, outcome = [], set(), {'draft': None, 'revisions': 0, 'stop_reason': None, 'note': None,
                                       'fifth_request_needed': False}
    request, earlier = first, [topic_text]
    if request is None:
        return {**outcome, 'steps': steps, 'stop_reason': 'NO_GAP'}
    while True:
        step = {'step': len(steps) + 1, 'gap_id': request['gap_id'], 'need': request['need'], 'query': request['query'],
                'source_types': request.get('source_types'), 'version_mode': request.get('version_mode'),
                'query_terms_from_observation': request.get('from_observation')}
        if query_key(request['query']) in seen:
            steps.append({**step, 'status': 'NOT_RUN_REPEATED_QUERY'})
            outcome['stop_reason'] = 'REPEATED_QUERY'
            break
        seen.add(query_key(request['query']))
        before = set(tools.ledger)
        found = tools.search(request['query'], purpose=f"adaptive:{request['need']}", source_types=request.get('source_types'),
                             version_mode=request.get('version_mode') or 'current', gap_id=request['gap_id'])
        trace = tools.trace[-1]
        new = [i for i in tools.ledger if i not in before]
        steps.append({**step, 'status': trace['status'], 'returned_ids': trace.get('result_ids', []),
                      'added_by_expansion': [a['evidence_id'] for a in trace.get('added', [])], 'new_evidence_ids': new})
        earlier.append(request['query'])
        if found is None:
            outcome['stop_reason'] = 'RETRIEVAL_BUDGET'
            break
        if not new:
            outcome['stop_reason'] = 'NO_NEW_EVIDENCE'
            break
        may_search = len(steps) < max_follow_ups
        if may_search:
            may_search, note = room_for_another()
            if not may_search:
                outcome.update(note=note, fifth_request_needed=True)
        result = revise(may_search, steps)
        outcome['revisions'] += 1
        if result is None:
            outcome['stop_reason'] = 'REVISION_FAILED'
            break
        outcome['draft'] = result.get('draft') or outcome['draft']
        nxt = result.get('request') if may_search else None
        if nxt is None:
            outcome['stop_reason'] = ('FOLLOW_UP_LIMIT' if len(steps) >= max_follow_ups else 'REQUEST_CEILING'
                                      if outcome['fifth_request_needed'] else 'GAP_FILLED' if result.get('filled')
                                      else 'CONTROLLER_STOP')
            break
        observed = [tools.ledger[i] for i in new if tools.ledger[i].get('origin') == 'retrieved_source']
        request = {**nxt, 'from_observation': observation_terms(nxt['query'], observed, earlier)}
    return {**outcome, 'steps': steps}


def follow_up_entries(steps):
    """Adaptive steps in the production follow_ups shape (coverage checks and the topic result read this)."""
    return [{'gap_id': s['gap_id'], 'need': s['need'], 'query': s['query'], 'source_types': s['source_types'],
             'version_mode': s['version_mode'], 'status': 'DONE' if s['status'] == 'DONE' else 'SKIPPED_BUDGET'
             if s['status'] == 'SKIPPED_BUDGET' else 'NOT_RUN', 'new_evidence_ids': s.get('new_evidence_ids', [])}
            for s in steps]


def used_evidence(draft, ids):
    """Recovered evidence the draft actually cites (claims, action targets, severity); finding is not using."""
    if draft is None:
        return []
    cited = {e for c in draft.claims for e in c.evidence_ids}
    action = draft.proposed_action
    if action is not None:
        cited |= {t.evidence_id for t in action.targets or []}
    return [i for i in ids if i in cited]


# ---- Offline stand-in for the controller decision (experiments and tests only; never used in a live run) -----------

def _series(e):
    """Recorded document-name stem: 'audio-playback-trial' for audio-playback-trial-approval@1.0 and -outcome@1.0."""
    return ((e.get('citation') or {}).get('authoring') or '').split('@')[0].rsplit('-', 1)[0]


def scripted_decision(gap, observation, ledger):
    """A deterministic stand-in for the revision's research decision, reading only recorded fields. `observation`: the
    items the last search returned, in rank order (expansion additions after them). The gap is taken to concern the
    best-ranked decision record observed and its recorded series (same document-name stem, or a recorded related-record
    link to it). PRIOR_DECISION_OUTCOME: an observed outcome (outcome_status other than not_observed or undetermined) in
    that series fills the gap; an approval in it with no observed outcome yields a query built from that approval's
    title, authoring and date; a deferred record in it that requested evidence yields a query for that evidence.
    Otherwise stop. It tests the controller's plumbing and stop rules, not a model's judgment of relevance."""
    if gap['need'] != 'PRIOR_DECISION_OUTCOME':
        return {'request': None, 'filled': False, 'basis': 'need not handled by the stand-in'}
    decisions = [e for e in observation if e.get('origin') == 'retrieved_source' and e.get('source_type') == 'decision']
    if not decisions:
        return {'request': None, 'filled': False, 'basis': 'no decision record observed'}
    focus = _series(decisions[0])

    def in_series(e):
        links = {link['from'] for link in (e.get('retrieved_as') or {}).get('links') or []}
        return _series(e) == focus or any(link.rsplit('-', 1)[0] == focus for link in links)
    series = [e for e in ledger.values() if e.get('origin') == 'retrieved_source' and e.get('source_type') == 'decision'
              and in_series(e)]
    for e in series:
        if (e.get('recorded_states') or {}).get('outcome_status') not in (None, 'not_observed', 'undetermined'):
            return {'request': None, 'filled': True, 'basis': f"observed outcome {e['evidence_id']} in series {focus}"}
    for e in series:
        states, c = e.get('recorded_states') or {}, e.get('citation') or {}
        date = ((e.get('dates') or {}).get('source_date') or '')[:10]
        if states.get('decision_status') == 'tl_approved' and states.get('outcome_status') == 'not_observed':
            query = f"Outcome of {c.get('title')} ({c.get('authoring')}): observed results after {date}"
        elif states.get('execution_status') == 'evidence_requested':
            query = f"Requested evidence for {c.get('title')} ({c.get('authoring')}) after {date}: comparison result"
        else:
            continue
        return {'request': {'gap_id': gap['gap_id'], 'need': gap['need'], 'query': query, 'source_types': ['decision'],
                            'version_mode': 'history'}, 'filled': False, 'basis': f"query built from {e['evidence_id']} (series {focus})"}
    return {'request': None, 'filled': False, 'basis': f'nothing in series {focus} points to a further record'}
