"""Shared execution layer: response store, budget ledger and transport guard. Offline: fake transports, no network."""
import json
import socket
import threading

import httpx
import pytest

from threadsense.agents import verification_requests as vr
from threadsense.execution import pricing
from threadsense.execution.guard import Execution, Guard, NetworkDisabled, UncertainRequest, cache_key
from threadsense.execution.ledger import BudgetExceeded, Ledger, LedgerError
from threadsense.execution.store import CacheCorruption, PersistenceFailure, Store

URL = 'https://api.openai.com/v1/chat/completions'


def body(prompt='Hello', model='gpt-4o-mini-2024-07-18', max_tokens=100):
    return {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens}


def reply(text='ok', model='gpt-4o-mini-2024-07-18', usage=None):
    return json.dumps({'id': 'chatcmpl-1', 'model': model, 'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
                       'usage': usage or {'prompt_tokens': 10, 'completion_tokens': 5,
                                          'prompt_tokens_details': {'cached_tokens': 4}}}).encode()


class FakeProvider:
    """Replaces the real transport underneath the guard; records every request that would reach the network."""

    def __init__(self, monkeypatch, responses=None, *, error=None):
        self.calls, self.responses, self.error = [], list(responses or []), error
        fake = self

        def handle(transport, request):
            fake.calls.append(json.loads(request.content))
            if fake.error:
                raise fake.error
            status, content = fake.responses.pop(0) if fake.responses else (200, reply())
            return httpx.Response(status, content=content, headers={'x-request-id': f'req_{len(fake.calls)}'}, request=request)
        monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', handle)


def post(payload, headers=None):
    with httpx.Client() as client:
        return client.post(URL, json=payload, headers={'Authorization': 'Bearer sk-test', **(headers or {})})


def live(tmp_path, name='run', limit=5.0, parents=()):
    return Execution(tmp_path/name, mode='LIVE', limit_usd=limit, parents=parents)


def test_live_request_is_reserved_saved_and_settled(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    with Guard(ex), ex.stage('agent1_interpret', 'agent1'):
        response = post(body())
    assert response.status_code == 200 and response.json()['choices'][0]['message']['content'] == 'ok'
    (row,) = ex.ledger.rows()
    assert (row['state'], row['origin'], row['stage']) == ('SETTLED', 'FRESH_LIVE', 'agent1_interpret')
    assert ex.store.get(row['response_sha']) == reply() and json.loads(ex.store.get(row['request_sha'])) == body()
    assert b'sk-test' not in ex.store.get(row['request_sha'])  # Credentials are never stored.
    expected = 6 * 0.15e-6 + 4 * 0.075e-6 + 5 * 0.60e-6
    assert row['charged_usd'] == pytest.approx(expected) and row['provider_request_id'] == 'req_1'
    assert row['cache_savings_usd'] == pytest.approx(4 * (0.15e-6 - 0.075e-6))
    assert len(provider.calls) == 1


def test_exact_replay_makes_zero_calls_and_ignores_headers(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    with Guard(ex):
        first = post(body('a')).content
        post(body('b'))
    ex.close()
    replay = Execution(tmp_path/'replay', mode='REPLAY', limit_usd=5.0, parents=[tmp_path/'run'])
    with Guard(replay):
        again = post(body('a'), headers={'User-Agent': 'changed-ui/2'}).content  # A UI/header change keeps the key.
        post(body('b'))
        with pytest.raises(NetworkDisabled):
            post(body('new prompt'))
    assert again == first and len(provider.calls) == 2
    assert {r['origin'] for r in replay.ledger.rows()} == {'REUSED_PARENT:run'}
    assert replay.ledger.committed_usd() == 0


def test_changed_downstream_prompt_invalidates_only_that_request(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    with Guard(ex):
        post(body('upstream'))
        post(body('downstream prompt v1', model='gpt-6.1-sol', max_tokens=50))
    ex.close()
    branch = live(tmp_path, 'branch', parents=[tmp_path/'run'])
    with Guard(branch):
        post(body('upstream'))
        post(body('downstream prompt v2', model='gpt-6.1-sol', max_tokens=50))
    origins = [(json.loads(branch.store.get(r['request_sha']))['messages'][0]['content'], r['origin']) for r in branch.ledger.rows()]
    assert origins == [('upstream', 'REUSED_PARENT:run'), ('downstream prompt v2', 'FRESH_LIVE')]
    assert len(provider.calls) == 3


def test_raw_output_survives_a_parsing_failure(tmp_path, monkeypatch):
    FakeProvider(monkeypatch, [(200, b'{"choices": [ not json')])
    ex = live(tmp_path)
    with Guard(ex):
        response = post(body())
        with pytest.raises(ValueError):
            response.json()
    (row,) = ex.ledger.rows()
    assert ex.store.get(row['response_sha']) == b'{"choices": [ not json'
    assert row['state'] == 'UNCERTAIN' and ex.ledger.committed_usd() == pytest.approx(row['reserved_usd'])  # No usage: kept.


def test_restart_never_duplicates_completed_or_uncertain_requests(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    with Guard(ex):
        post(body('done'))
    ex.close()
    # Completed: served from this run's own saved response.
    again = live(tmp_path)
    with Guard(again):
        assert post(body('done')).status_code == 200
    assert len(provider.calls) == 1 and again.ledger.rows()[-1]['origin'] == 'REUSED_RUN'
    # Uncertain: the process stops during the attempt.
    provider.error = KeyboardInterrupt()
    with Guard(again), pytest.raises(KeyboardInterrupt):
        post(body('interrupted'))
    assert again.ledger.rows(cache_key('POST', URL, json.dumps(body('interrupted')).encode()))[0]['state'] == 'UNCERTAIN'
    provider.error = None
    again.close()
    restarted = live(tmp_path)
    with Guard(restarted), pytest.raises(UncertainRequest):
        post(body('interrupted'))
    assert len(provider.calls) == 2  # the interrupted attempt only; never resent


def test_a_process_killed_after_marking_sent_leaves_an_uncertain_charge(tmp_path):
    ledger = Ledger(tmp_path/'l.sqlite3', 5.0)
    rid = ledger.reserve(cache_key='k', stage='s', agent='a', endpoint=URL, model='gpt-4.1', reserved_usd=0.5, request_sha='x')
    ledger.mark_sent(rid)
    ledger.close()
    reopened = Ledger(tmp_path/'l.sqlite3', 5.0)
    assert reopened.recover() == [rid] and reopened.rows()[0]['state'] == 'UNCERTAIN'
    assert reopened.committed_usd() == pytest.approx(0.5)


def test_sdk_retry_of_a_failed_attempt_is_refused(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch, [(500, b'{"error": {"message": "server"}}')])
    ex = live(tmp_path)
    with Guard(ex):
        assert post(body()).status_code == 500
        with pytest.raises(UncertainRequest):
            post(body())  # what an SDK retry would send
    assert len(provider.calls) == 1


def test_concurrent_reservations_cannot_overspend(tmp_path):
    Ledger(tmp_path/'l.sqlite3', 10.0).close()
    results = []

    def worker(i):
        ledger = Ledger(tmp_path/'l.sqlite3', 10.0)
        try:
            ledger.reserve(cache_key=f'k{i}', stage='s', agent='a', endpoint=URL, model='m', reserved_usd=1.0, request_sha='x')
            results.append(True)
        except BudgetExceeded:
            results.append(False)
        finally:
            ledger.close()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 10
    assert Ledger(tmp_path/'l.sqlite3', 10.0).committed_usd() == pytest.approx(10.0)


def test_budget_ceiling_and_persistence_failures_prevent_sending(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    tight = live(tmp_path, 'tight', limit=0.0001)
    with Guard(tight), pytest.raises(BudgetExceeded):
        post(body(max_tokens=4096))
    ex = live(tmp_path)
    monkeypatch.setattr(Store, 'put', lambda self, data: (_ for _ in ()).throw(PersistenceFailure('disk full')))
    with Guard(ex), pytest.raises(PersistenceFailure):
        post(body())
    monkeypatch.undo()
    FakeProvider(monkeypatch).calls = provider.calls
    ex2 = live(tmp_path, 'ledgerfail')
    monkeypatch.setattr(ex2.ledger, 'reserve', lambda **k: (_ for _ in ()).throw(LedgerError('locked')))
    with Guard(ex2), pytest.raises(LedgerError):
        post(body())
    assert provider.calls == [] and tight.ledger.rows() == []


def test_corrupted_cache_is_rejected_never_served_or_replaced(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    with Guard(ex):
        post(body())
    (row,) = ex.ledger.rows()
    ex.store.path(row['response_sha']).write_bytes(b'tampered')
    ex.close()
    replay = Execution(tmp_path/'replay', mode='REPLAY', limit_usd=5.0, parents=[tmp_path/'run'])
    with Guard(replay), pytest.raises(CacheCorruption):
        post(body())
    resumed = live(tmp_path)
    with Guard(resumed), pytest.raises(CacheCorruption):
        post(body())
    assert len(provider.calls) == 1


def test_changed_statement_text_never_reuses_a_grounding_verdict():
    old = body(json.dumps({'statements': [{'statement_id': 'summary:s1', 'text': 'Two tutors report X.'}]}), model='gpt-6.1-sol')
    new = body(json.dumps({'statements': [{'statement_id': 'summary:s1', 'text': 'Three tutors report X.'}]}), model='gpt-6.1-sol')
    assert cache_key('POST', URL, json.dumps(old).encode()) != cache_key('POST', URL, json.dumps(new).encode())
    assert cache_key('POST', URL, json.dumps(old).encode()) == cache_key('POST', URL, json.dumps(old, indent=2).encode())


def test_single_attempt_verification_transport_is_guarded(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(vr, 'send_once', lambda endpoint, data, key: (sent.append(data) or (200, reply(model='gpt-4.1'), None)))
    ex = live(tmp_path)
    with Guard(ex):
        payload = json.dumps(body(model='gpt-4.1')).encode()
        assert vr.send_once(URL, payload, 'sk-test')[0] == 200
        assert vr.send_once(URL, payload, 'sk-test')[1] == reply(model='gpt-4.1')  # served, not resent
    assert len(sent) == 1 and [r['origin'] for r in ex.ledger.rows()] == ['FRESH_LIVE', 'REUSED_RUN']
    monkeypatch.setattr(vr, 'send_once', lambda endpoint, data, key: (206, b'{"partial', 'Incomplete HTTP response; no retry.'))
    with Guard(ex):
        status, raw, failure = vr.send_once(URL, json.dumps(body('other', model='gpt-4.1')).encode(), 'sk-test')
    assert failure and raw == b'{"partial'


def test_replay_blocks_every_non_loopback_connection(tmp_path):
    replay = Execution(tmp_path/'r', mode='REPLAY', limit_usd=1.0)
    with Guard(replay):
        with pytest.raises(NetworkDisabled):
            socket.create_connection(('192.0.2.1', 443), timeout=1)
        with pytest.raises(NetworkDisabled), httpx.Client() as client:
            client.get('https://example.org/')


def test_async_provider_requests_are_refused(tmp_path):
    import asyncio
    ex = live(tmp_path)

    async def call():
        async with httpx.AsyncClient() as client:
            await client.post(URL, json=body())
    with Guard(ex), pytest.raises(NetworkDisabled):
        asyncio.run(call())
    assert ex.ledger.rows() == []


def test_ceiling_is_fixed_per_run(tmp_path):
    Ledger(tmp_path/'l.sqlite3', 39.0).close()
    with pytest.raises(LedgerError):
        Ledger(tmp_path/'l.sqlite3', 45.0)


def test_prices_match_the_local_cost_map_and_sol_reserves_cache_writes():
    import litellm
    for name, r in pricing.PRICES.items():
        entry = litellm.model_cost[name]
        assert (entry['input_cost_per_token'], entry['output_cost_per_token']) == pytest.approx((r['input'], r['output']))
    assert pricing.reservation('gpt-6.1-sol', 1000, 100) == pytest.approx(1000 * 2.5e-6 + 100 * 1e-5)
    assert pricing.settled_cost('gpt-6.1-sol', {'prompt_tokens': 1000, 'completion_tokens': 10,
                                                'prompt_tokens_details': {'cached_tokens': 600}}) == pytest.approx(
        400 * 2.5e-6 + 600 * 1e-7 + 10 * 1e-5)  # unreported writes priced as writes
    with pytest.raises(pricing.PricingUnavailable):
        pricing.rates('gpt-unknown')


def test_requests_from_worker_threads_use_the_same_ledger(tmp_path, monkeypatch):
    """CrewAI sends from a worker thread; the ledger connection is shared under a lock."""
    provider = FakeProvider(monkeypatch)
    ex = live(tmp_path)
    errors = []

    def worker(prompt):
        try:
            post(body(prompt))
        except BaseException as error:  # noqa: BLE001
            errors.append(error)
    with Guard(ex):
        threads = [threading.Thread(target=worker, args=(f'p{i}',)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert errors == [] and len(provider.calls) == 5 and len(ex.ledger.rows()) == 5
