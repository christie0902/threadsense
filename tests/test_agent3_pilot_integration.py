"""Agent 3 pilot with real local embeddings (offline). Semantic judgments are scripted, not model output.

Skipped when the pinned embedding model is not cached. Checks that the scripted responses
still cite evidence IDs the real index produces, and that recovery of an omitted handling
announcement works with real rankings.
"""
import json

import httpx
import pytest

from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import sent_payload
from tests.test_agent3_request_boundary import completion, provider  # noqa: F401 - fixture reused here

SCRIPTED = ROOT/'tests/fixtures/agent3_pilot_scripted_judgments.json'


@pytest.fixture(scope='module')
def real(tmp_path_factory):
    try:
        from threadsense.retrieval.embeddings import SentenceEncoder
        encoder = SentenceEncoder()
    except OSError as error:
        pytest.skip(f'Pinned embedding model not cached locally: {error}')
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_pilot import HANDOFF
    from threadsense.retrieval.index import build_index
    from threadsense.retrieval.search import Retriever
    index = tmp_path_factory.mktemp('pilot')/'retrieval'
    build_index(index, encoder=encoder)
    return Retriever(index, encoder=encoder), load_effective_view(HANDOFF)


def test_scripted_pilot_runs_end_to_end_within_budget(real):
    from threadsense.agents.advisor_pilot import BUDGET, ScriptedClient, run_pilot
    retriever, view = real
    run = run_pilot(client=ScriptedClient(SCRIPTED), retriever=retriever, view=view)
    results = {r['scenario']['id']: r for r in run['results']}
    assert all(c['status'] == 'OK' for r in results.values() for c in r['model_calls']), 'scripted IDs drifted from the index'
    cards = {k: r for k, r in results.items() if r['status'] == 'CARD'}
    assert len(cards) == 6 and results['control_unsupported_payroll']['control_outcome'] == 'UNSUPPORTED'
    assert {k: r['grounding']['status'] for k, r in cards.items()} == {
        'audio_playback': 'PASSED', 'json_vs_prose': 'PASSED', 'fictional_pii': 'PASSED', 'korean_register': 'PASSED',
        'submit_failure': 'FAILED', 'repeated_ending': 'PASSED'}
    assert {k for k, r in cards.items() if r['tot']['status'] != 'NOT_TRIGGERED'} == {'json_vs_prose', 'repeated_ending'}
    pii = cards['fictional_pii']
    assert [f['status'] for f in pii['temporal']['findings']] == ['RESOLVED_BY_RECORDED_SUPERSESSION']
    assert any(t['purpose'] == 'supersession_check' for t in pii['retrieval_trace'])
    assert all(r['coverage']['uncarried_obligations'] == [] for r in cards.values())
    assert all(r['card']['card_line'] == 'NEEDS_REVIEW' for r in cards.values())  # Every topic carries upstream flags.
    assert all(r['model_calls'][-1]['stage'] == 'grounding' for r in cards.values())  # Final grounding is the last call.
    # Submit: the "same cause" inference is withheld from the card and kept in diagnostics.
    submit = cards['submit_failure']
    [withheld] = [d for d in submit['diagnostics'] if d['code'] == 'WITHHELD_STATEMENT']
    assert withheld['statement_id'] == 'claim:c5' and 'share the cause' in withheld['text']
    assert 'share the cause' not in json.dumps(submit['card']) and 'claim:c5: UNSUPPORTED' in json.dumps(submit['card'])
    # PII: both announcements verified as handling; the action targets only the stale help-page section.
    assert len(pii['established_handling']) == 2
    scope = pii['card']['recommended_action']['scope_note']
    assert "CORRECT safety-qn-help-page@1.0 section 'Contact details'" in scope and 'instructions@' not in scope and 'faq@' not in scope
    # Resolution from member threads: audio is MIXED (Agent 1 recorded one PARTIALLY_RESOLVED, unverified); PII is
    # UNRESOLVED although Agent 1 recorded two members as PARTIALLY_RESOLVED.
    assert cards['audio_playback']['card']['resolution_status'] == 'MIXED'
    assert pii['card']['resolution_status'] == 'UNRESOLVED'
    assert [a['state'] for a in pii['resolution']['agent1_attributed']].count('PARTIALLY_RESOLVED') == 2
    # ToT alternatives carry their own verdicts: the rejected JSON-first rule is not grounded.
    json_tot = {c['candidate_id']: c['grounding'] for c in cards['json_vs_prose']['tot']['candidates']}
    assert json_tot == {'A': 'SUPPORTED', 'B': 'UNSUPPORTED', 'C': 'PARTIALLY_SUPPORTED'}
    used = run['manifest']['budget_consumed']
    assert used['model_calls'] <= BUDGET['model_calls_total'] and used['retrieval_calls'] <= BUDGET['retrieval_calls_total']
    assert all(r['budget']['consumed'].get('model_calls', 0) <= BUDGET['model_calls_per_topic'] for r in cards.values())


def test_real_rankings_recover_an_omitted_handling_announcement(real):
    from threadsense.agents.advisor_evidence import Budget
    from threadsense.agents.advisor_pilot import BUDGET, advise
    from threadsense.severity_rubric import load_rubric
    from tests.test_agent3_advisor import ANNOUNCEMENT, SCEN, Fake, draft_for, supported
    retriever, view = real

    def draft(payload):
        return draft_for(payload, evidence_sufficiency='INSUFFICIENT', gaps=[
            {'gap_id': 'g1', 'need': 'CURRENT_HANDLING', 'description': 'No current handling announcement in the evidence.',
             'follow_up': {'query': 'LT player never starts playback handling reminder', 'source_types': ['announcement']}}])
    client = Fake(draft=draft, revision=draft_for, grounding=supported)
    result = advise(SCEN['audio_playback'], view=view, retriever=retriever, client=client, budget=Budget(BUDGET),
                    rubric=load_rubric(None), run_id='run_test', as_of=retriever.manifest['cutoff'],
                    initial='Was the previous playback workaround approved and did it work?')
    initial, follow = result['retrieval_trace'][0], result['retrieval_trace'][1]
    assert not any(ANNOUNCEMENT in i for i in initial['result_ids']), 'precondition: real top five omit the announcement'
    assert any(ANNOUNCEMENT in i for i in follow['new_evidence_ids'])


def test_live_client_sends_one_request_per_stage_end_to_end(real, provider):  # noqa: F811
    """DETERMINISTIC request accounting with the live CrewAI client against a fake provider (offline): the fake
    replies with the scripted responses, so cards match the scripted run, and HTTP requests equal stage calls."""
    from threadsense.agents.advisor_pilot import BUDGET, CrewAIClient, ScriptedClient, run_pilot
    retriever, view = real
    scripted = json.loads(SCRIPTED.read_text(encoding='utf-8'))['responses']

    def reply(request):
        text = json.loads(request.content)['messages'][-1]['content']
        payload = sent_payload(text)
        return httpx.Response(200, json=completion(json.dumps(scripted[payload['scenario_id']][payload['stage']])), request=request)
    provider.reply = reply
    live = run_pilot(client=CrewAIClient(), retriever=retriever, view=view)
    offline = run_pilot(client=ScriptedClient(SCRIPTED), retriever=retriever, view=view)
    calls = [c for r in live['results'] for c in r['model_calls']]
    assert all(c['status'] == 'OK' and c['http_requests']['sent'] == 1 and c['http_requests']['blocked'] == 0 for c in calls)
    assert len(provider.requests) == len(calls) == live['manifest']['budget_consumed']['model_calls'] <= BUDGET['model_calls_total']
    assert live['manifest']['http_requests'] == {'sent': len(calls), 'blocked': 0}
    assert live['manifest']['live_request_settings']['http_requests_per_stage'] == 1
    view_of = lambda run: {r['scenario']['id']: (r['status'], (r.get('card') or {}).get('card_line'), (r.get('card') or {}).get('checks'),
                                                 (r.get('card') or {}).get('summary')) for r in run['results']}  # noqa: E731
    assert view_of(live) == view_of(offline)
