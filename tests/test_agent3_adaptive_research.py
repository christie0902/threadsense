"""Opt-in adaptive (react) follow-up research. Offline: controller decisions come from fakes or the deterministic
stand-in (advisor_research.scripted_decision), never from a model. These tests check the controller's sequencing, stop
rules and request accounting, not a model's research judgment.
"""
import json

import pytest

from threadsense.agents import advisor_research as research
from threadsense.agents.advisor_evidence import Budget, ResearchTools
from threadsense.agents.advisor_pilot import BUDGET, advise
from threadsense.severity_rubric import load_rubric
from tests.test_agent3_advisor import SCEN, Fake, draft_for, retriever, supported, view  # noqa: F401 - fixtures

FROZEN_QUERY = ('Audio multimodal batch 05 one-reload playback trial ending August 28 2026: observed results and decisions '
                'extending, ending or replacing the trial; applicability to batch 06 player never loads or waveform '
                'visible with no playback')  # agent3_open_evaluation_cases.json, audio_trial_outcome_followup_miss
OUTCOME = 'audio-playback-trial-outcome@1.0'
APPROVAL = 'audio-playback-trial-approval@1.0'


def record(eid, title, authoring, date, decision, outcome, execution='not_executed'):
    return {'evidence_id': eid, 'origin': 'retrieved_source', 'source_type': 'decision',
            'citation': {'title': title, 'authoring': authoring, 'sections': ['Decision']}, 'dates': {'source_date': date},
            'recorded_states': {'decision_status': decision, 'execution_status': execution, 'outcome_status': outcome}}


APPROVED = record('k:approval', 'AUDIO-20260824-01 - Approve a limited playback trial', 'trial-approval@1.0',
                  '2026-08-24T14:00:00Z', 'tl_approved', 'not_observed')
OBSERVED = record('k:outcome', 'Playback trial outcome', 'trial-outcome@1.0', '2026-08-27T16:00:00Z', 'reported',
                  'unsuccessful_in_sample', 'trial_completed')
GAP = {'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'query': 'previous playback workaround trial outcome',
       'source_types': ['decision'], 'version_mode': 'history'}


class Tools:
    """ResearchTools double: query -> items (None: retrieval budget exhausted). Same ledger and trace contract."""

    def __init__(self, results):
        self.results, self.ledger, self.trace = results, {}, []

    def search(self, query, *, purpose, source_types=None, version_mode='current', gap_id=None):
        items = next((v for k, v in self.results.items() if research.query_key(k) == research.query_key(query)), [])
        if items is None:
            self.trace.append({'status': 'SKIPPED_BUDGET'})
            return None
        for item in items:
            self.ledger.setdefault(item['evidence_id'], item)
        self.trace.append({'status': 'DONE', 'result_ids': [i['evidence_id'] for i in items], 'added': []})
        return {'results': items}


def stand_in(tools, gap=GAP, calls=None):
    """Revision whose research decision is the deterministic stand-in, reading the latest observation."""
    def revise(may_search, steps):
        if calls is not None:
            calls.append(may_search)
        observed = [tools.ledger[i] for i in steps[-1]['returned_ids'] + steps[-1]['added_by_expansion'] if i in tools.ledger]
        decision = research.scripted_decision(gap, observed, tools.ledger)
        return {'draft': None, 'request': decision['request'] if may_search else None, 'filled': decision['filled']}
    return revise


def room(ok=True):
    return lambda: (ok, None if ok else 'a fifth request for this topic')


def test_no_follow_up_requested_means_no_search_and_no_revision():
    tools = Tools({})
    out = research.adaptive_research(tools, None, stand_in(tools), room_for_another=room())
    assert out['stop_reason'] == 'NO_GAP' and out['steps'] == [] and out['revisions'] == 0 and tools.trace == []


def test_paired_first_observation_outcome_stops_approval_only_targets_the_next_query():
    """Same gap and first query. Branch A observes the outcome: one search, then stop. Branch B observes only the
    approval: the next query is written from that approval and recovers the outcome."""
    a = Tools({GAP['query']: [APPROVED, OBSERVED]})
    branch_a = research.adaptive_research(a, GAP, stand_in(a), room_for_another=room())
    assert branch_a['stop_reason'] == 'GAP_FILLED' and len(branch_a['steps']) == 1 and branch_a['revisions'] == 1

    targeted = 'Outcome of AUDIO-20260824-01 - Approve a limited playback trial (trial-approval@1.0): observed results after 2026-08-24'
    b = Tools({GAP['query']: [APPROVED], targeted: [OBSERVED]})
    branch_b = research.adaptive_research(b, GAP, stand_in(b), room_for_another=room())
    first, second = branch_b['steps']
    assert first['new_evidence_ids'] == ['k:approval'] and second['query'] == targeted
    assert second['query_terms_from_observation']['evidence_ids'] == ['k:approval']
    assert {'audio-20260824-01', 'trial-approval@1.0', '2026-08-24'} <= set(second['query_terms_from_observation']['terms'])
    assert second['new_evidence_ids'] == ['k:outcome'] and branch_b['stop_reason'] == 'FOLLOW_UP_LIMIT'
    assert branch_b['revisions'] == 2  # The second observation is read by one final revision.


def test_a_repeated_query_is_not_run():
    tools = Tools({GAP['query']: [APPROVED]})

    def revise(may_search, steps):
        return {'draft': None, 'request': {**GAP, 'query': 'Previous playback-workaround trial, outcome?'}, 'filled': False}
    out = research.adaptive_research(tools, GAP, revise, room_for_another=room())
    assert out['stop_reason'] == 'REPEATED_QUERY' and [s['status'] for s in out['steps']] == ['DONE', 'NOT_RUN_REPEATED_QUERY']
    assert len(tools.trace) == 1


def test_no_new_evidence_stops_without_a_revision_request():
    tools = Tools({GAP['query']: [APPROVED]})
    tools.ledger['k:approval'] = APPROVED  # Already observed by the initial search.
    calls = []
    out = research.adaptive_research(tools, GAP, stand_in(tools, calls=calls), room_for_another=room())
    assert out['stop_reason'] == 'NO_NEW_EVIDENCE' and out['revisions'] == 0 and calls == []


def test_exhausted_retrieval_budget_stops():
    tools = Tools({GAP['query']: None})
    out = research.adaptive_research(tools, GAP, stand_in(tools), room_for_another=room())
    assert out['stop_reason'] == 'RETRIEVAL_BUDGET' and out['revisions'] == 0


def test_request_ceiling_sends_the_revision_in_final_mode_and_says_a_fifth_request_was_needed():
    tools = Tools({GAP['query']: [APPROVED]})
    calls = []
    out = research.adaptive_research(tools, GAP, stand_in(tools, calls=calls), room_for_another=room(False))
    assert calls == [False] and out['stop_reason'] == 'REQUEST_CEILING' and out['fifth_request_needed']
    assert len(out['steps']) == 1


def test_a_failed_revision_is_recorded():
    tools = Tools({GAP['query']: [APPROVED]})
    out = research.adaptive_research(tools, GAP, lambda may, steps: None, room_for_another=room())
    assert out['stop_reason'] == 'REVISION_FAILED' and out['revisions'] == 1


def test_an_outcome_from_another_series_does_not_fill_the_gap():
    """The repeated-ending case: the best-ranked record requested evidence; an unrelated approval and its outcome
    (another series) were also returned. The stand-in pursues the requested evidence instead of stopping."""
    review = record('k:review', 'Repeated ending retained as an observation', 'audio-repeat-observation-review@1.0',
                    '2026-09-29T14:00:00Z', 'tl_deferred', 'undetermined', 'evidence_requested')
    other_approval = record('k:headset-approval', 'Approve a headset check', 'audio-headset-check-approval@1.0',
                            '2026-09-21T14:00:00Z', 'tl_approved', 'not_observed')
    other_outcome = record('k:headset-outcome', 'Headset check outcome', 'audio-headset-check-outcome@1.0',
                           '2026-09-22T15:00:00Z', 'reported', 'resolved_in_checked_tasks', 'diagnostic_completed')
    ledger = {e['evidence_id']: e for e in (review, other_approval, other_outcome)}
    decision = research.scripted_decision(GAP, [review, other_outcome, other_approval], ledger)
    assert not decision['filled'] and 'audio-repeat-observation-review@1.0' in decision['request']['query']


def test_gap_not_handled_by_the_stand_in_stops():
    decision = research.scripted_decision({**GAP, 'need': 'CURRENT_HANDLING'}, [APPROVED], {'k:approval': APPROVED})
    assert decision['request'] is None and not decision['filled']


# ---- Through advise (test-double index; fakes for every model stage) ----------------------------------------------

def gap_draft(payload, confidence=0.9):
    return draft_for(payload, confidence=confidence, evidence_sufficiency='INSUFFICIENT', gaps=[
        {'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'description': 'Outcome of the earlier playback trial.',
         'follow_up': {'query': 'previous playback workaround trial outcome', 'source_types': ['decision'],
                       'version_mode': 'history'}}])


def run(retriever, view, client, mode):  # noqa: F811
    return advise(SCEN['audio_playback'], view=view, retriever=retriever, client=client, budget=Budget(BUDGET),
                  rubric=load_rubric(None), run_id='run_test', as_of=retriever.manifest['cutoff'], research_mode=mode)


def test_batch_mode_is_unchanged_and_records_no_adaptive_trace(retriever, view):  # noqa: F811
    client = Fake(draft=gap_draft, revision=draft_for, grounding=supported)
    result = run(retriever, view, client, 'batch')
    assert 'adaptive_research' not in result and [f['status'] for f in result['follow_ups']] == ['DONE']


def test_react_mode_through_advise_stays_within_four_requests(retriever, view):  # noqa: F811
    client = Fake(draft=gap_draft, revision=draft_for, grounding=supported)  # The revision drops the gap: filled.
    result = run(retriever, view, client, 'react')
    trace = result['adaptive_research']
    assert trace['stop_reason'] in ('GAP_FILLED', 'NO_NEW_EVIDENCE')
    assert [s for s, _ in client.calls].count('revision') == trace['model_requests']['revisions'] <= 1
    assert len(client.calls) <= 4 and client.calls[-1][0] == 'grounding'
    assert trace['local_searches'] == len(trace['steps']) == 1
    assert all(e in result['evidence_ledger'] for e in trace['recovered_evidence_ids'])
    assert set(trace['used_evidence_ids']) <= set(trace['recovered_evidence_ids'])


def test_react_mode_never_skips_a_required_stage_for_a_second_search(retriever, view):  # noqa: F811
    """Low confidence triggers the option comparison: draft + revision + comparison + grounding already use the four
    requests, so the revision is sent in final mode (no second search) and the stop records the fifth request."""
    seen = []

    def revision(payload):
        seen.append('ONE more search' in payload['rules'])
        return gap_draft(payload, confidence=0.5)  # Still asks for a search; ignored in final mode.
    client = Fake(draft=lambda p: gap_draft(p, confidence=0.5), revision=revision, tot=ValueError('comparison not scripted'),
                  grounding=supported)
    result = run(retriever, view, client, 'react')
    trace = result['adaptive_research']
    if not trace['steps'] or not trace['steps'][0]['new_evidence_ids']:
        pytest.skip('precondition: the test index returned no new evidence for the first query')
    assert seen == [False] and trace['stop_reason'] == 'REQUEST_CEILING' and trace['fifth_request_needed']
    assert 'fifth request' in trace['note']
    stages = {c['stage']: c['status'] for c in result['model_calls']}
    assert stages == {'draft': 'OK', 'revision': 'OK', 'tot': 'FAILED', 'grounding': 'OK'}  # Attempted, not skipped.


# ---- Real local retrieval (skipped when the pinned embedding model is not cached) ----------------------------------

@pytest.fixture(scope='module')
def real_retriever():
    try:
        from threadsense.agents.advisor_evidence import open_retriever
        r = open_retriever()
    except Exception as error:  # noqa: BLE001 - missing model or index: skip, never rebuild here
        pytest.skip(f'Active retrieval index or pinned embedding model unavailable: {error}')
    return r


def tools_for(r, expansion):
    return ResearchTools(r, project='audio_multimodal', batch='audio_batch_06', as_of=r.manifest['cutoff'],
                         budget=Budget({'retrieval_calls_per_topic': 6}), top_k=5, expansion=expansion)


def test_real_retrieval_paired_audio_trial(real_retriever):
    gap = {**GAP, 'query': FROZEN_QUERY, 'source_types': ['decision', 'announcement', 'guideline']}
    a = tools_for(real_retriever, expansion=True)  # Production: recorded-link expansion adds the outcome.
    branch_a = research.adaptive_research(a, gap, stand_in(a, gap), room_for_another=room())
    assert any(OUTCOME in i for i in branch_a['steps'][0]['new_evidence_ids'])
    assert branch_a['stop_reason'] == 'GAP_FILLED' and len(branch_a['steps']) == 1

    b = tools_for(real_retriever, expansion=False)  # The frozen miss: the first observation holds the approval only.
    branch_b = research.adaptive_research(b, gap, stand_in(b, gap), room_for_another=room())
    first, second = branch_b['steps']
    assert any(APPROVAL in i for i in first['new_evidence_ids']) and not any(OUTCOME in i for i in first['new_evidence_ids'])
    assert any(APPROVAL in i for i in second['query_terms_from_observation']['evidence_ids'])
    assert any(OUTCOME in i for i in second['new_evidence_ids'])
    json.dumps(branch_b)  # The trace is serializable as saved.
