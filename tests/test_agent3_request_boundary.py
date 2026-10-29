"""Model-call limits at the actual HTTP request boundary, offline (DETERMINISTIC).

A fake provider replaces httpx's transport and every non-loopback socket connection is refused,
so nothing leaves the machine and the key is a dummy. Measured with the earlier Agent/Crew client
(OpenAI SDK defaults): a 5xx or connection error sent 3 requests per stage, a 429 sent 9, and a
non-final-answer reply made CrewAI send a second, forced-final-answer request. The live client now
sends exactly one request per stage whatever the reply.
"""
import json
import socket
from types import SimpleNamespace

import httpx
import pytest

from threadsense.agents import advisor_pilot
from threadsense.agents.advisor_contracts import GroundingJudgment
from threadsense.agents.advisor_evidence import Budget
from threadsense.agents.advisor_pilot import BoundaryNotObserved, CrewAIClient, Stages

VALID = '{"verdicts": []}'


def completion(content):
    return {'id': 'offline', 'object': 'chat.completion', 'created': 1, 'model': 'gpt-4o-mini',
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}}


def reply_ok(request, content=VALID):
    return httpx.Response(200, json=completion(content), request=request)


def reply_status(status):
    return lambda request: httpx.Response(status, json={'error': {'message': 'offline', 'type': 'server_error'}}, request=request)


def reply_connect_error(request):
    raise httpx.ConnectError('offline connect error', request=request)


@pytest.fixture
def provider(monkeypatch):
    """Fake provider at the transport; `requests` lists every request body that reached it."""
    for name, value in advisor_pilot.QUIET_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-offline-test')
    monkeypatch.setenv('THREADSENSE_MODEL', 'openai/gpt-4o-mini')
    connect = socket.socket.connect

    def local_only(sock, address, *args, **kwargs):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            raise OSError(f'network blocked in tests: {address[0]}')
        return connect(sock, address, *args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', local_only)
    state = SimpleNamespace(reply=reply_ok, requests=[])

    def handle(transport, request):
        state.requests.append(json.loads(request.content))
        return state.reply(request)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', handle)
    return state


@pytest.mark.parametrize('reply, status, blocked', [
    (reply_ok, 'OK', 0),
    (lambda r: reply_ok(r, 'Thought: I need a tool\nAction: search\nAction Input: {"q": 1}'), 'FAILED', 0),  # No forced re-ask.
    (reply_status(500), 'FAILED', 0),  # Provider SDK retries disabled.
    (reply_status(429), 'FAILED', 1),  # CrewAI's fixed rate-limit retry is refused before it is sent.
    (reply_connect_error, 'FAILED', 0),
])
def test_one_stage_sends_exactly_one_http_request(provider, reply, status, blocked):
    """DETERMINISTIC. Whatever the reply, one stage sends one request with the configured limits."""
    provider.reply = reply
    stages = Stages(CrewAIClient(), Budget({'model_calls_per_topic': 4}), 'scenario')
    stages('grounding', {'rules': 'Judge each statement.'}, GroundingJudgment)
    [entry] = stages.log
    assert entry['status'] == status and len(provider.requests) == 1
    stats = entry['http_requests']
    assert (stats['sent'], stats['blocked'], stats['hosts']) == (1, blocked, ['api.openai.com']) and len(stats['responses']) == 1
    if reply is reply_ok:  # Provider usage and returned model are recorded from the response.
        assert stats['responses'][0]['model'] == 'gpt-4o-mini' and stats['responses'][0]['usage']['total_tokens'] == 8
    body = provider.requests[0]
    assert body['model'] == 'gpt-4o-mini' and body['temperature'] == 0 and 'tools' not in body
    assert body['max_tokens'] == advisor_pilot.MAX_COMPLETION_TOKENS and body['response_format'] == {'type': 'json_object'}
    assert [m['role'] for m in body['messages']] == ['system', 'user']
    assert httpx.HTTPTransport.handle_request.__name__ == 'handle'  # The guard restored the transport.


def test_budget_counts_requests_one_to_one(provider):
    """DETERMINISTIC. Four stages on a 4-call topic budget send four requests; the fifth is refused unsent."""
    stages = Stages(CrewAIClient(), Budget({'model_calls_per_topic': 4}), 'scenario')
    for stage in ('draft', 'revision', 'tot', 'grounding', 'extra'):
        stages(stage, {'rules': 'r'}, GroundingJudgment)
    assert [e['status'] for e in stages.log] == ['OK'] * 4 + ['SKIPPED_BUDGET'] and len(provider.requests) == 4


def test_a_response_that_bypasses_the_guarded_transport_stops_the_run(provider):
    """DETERMINISTIC. If a reply arrives without any request through the guarded transport, call accounting is
    unverifiable, so the run stops instead of recording an unmonitored call."""
    client = CrewAIClient()
    client.llm = SimpleNamespace(call=lambda messages: VALID)
    with pytest.raises(BoundaryNotObserved):
        Stages(client, Budget({}), 'scenario')('draft', {'rules': 'r'}, GroundingJudgment)


# ---- Comparison arms: parameters, cost reservation, resource limits (DETERMINISTIC) -----------------------

def comparison_arms():
    import importlib.util
    from threadsense.handoff_inputs import ROOT
    spec = importlib.util.spec_from_file_location('comparison', ROOT/'scripts/run_agent3_model_comparison.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ARMS


def arm_stage(arm, ledger=None, **overrides):
    from threadsense.agents.advisor_pilot import live_settings
    client = CrewAIClient({**live_settings(**comparison_arms()[arm]), **overrides}, ledger=ledger)
    return Stages(client, Budget({}), 'scenario')


def test_each_arm_sends_its_model_parameters(provider):
    """The installed client sends temperature 0 and max_tokens for the baseline; for the reasoning model no
    temperature, max_completion_tokens (reasoning included), reasoning_effort medium and the standard service tier."""
    bodies = {}
    for arm in comparison_arms():
        provider.requests.clear()
        arm_stage(arm)('grounding', {'rules': 'r'}, GroundingJudgment)
        bodies[arm] = {k: v for k, v in provider.requests[0].items() if k != 'messages'}
    assert bodies['gpt-4o-mini'] == {'model': 'gpt-4o-mini', 'max_tokens': 4096, 'temperature': 0.0,
                                     'response_format': {'type': 'json_object'}}
    assert bodies['gpt-6.1-sol'] == {'model': 'gpt-6.1-sol', 'max_completion_tokens': 16384, 'reasoning_effort': 'medium',
                                     'service_tier': 'default', 'response_format': {'type': 'json_object'}}


def test_cost_is_reserved_before_sending_and_unknown_usage_is_charged_in_full(provider):
    """Each request reserves its maximum cost (input limit and output limit at list prices) first; a request whose
    reservation would exceed the budget is not sent; a failed request with no reported usage is charged its full
    reservation; a successful one is settled at the provider's usage."""
    from threadsense.agents.advisor_pilot import CostLedger
    ledger = CostLedger(0.30)  # Room for one gpt-6.1-sol reservation (~$0.204), not two.
    stages = arm_stage('gpt-6.1-sol', ledger)
    stages('draft', {'rules': 'r'}, GroundingJudgment)
    provider.reply = reply_status(500)
    stages = arm_stage('gpt-6.1-sol', ledger)
    stages('revision', {'rules': 'r'}, GroundingJudgment)
    [ok], [failed] = ledger.entries[:1], stages.log
    assert ok['basis'] == 'provider usage' and ok['charged_usd'] < 0.001
    assert failed['failure_class'] == 'PROVIDER' and ledger.entries[1]['charged_usd'] == ledger.entries[1]['reserved_usd']
    sent = len(provider.requests)
    stages('grounding', {'rules': 'r'}, GroundingJudgment)  # Spent ~$0.204 + ~$0; another reservation would exceed $0.30.
    assert stages.log[-1]['failure_class'] == 'RESOURCE' and 'CostBudgetExceeded' in stages.log[-1]['error']
    assert len(provider.requests) == sent and ledger.reserved_usd == 0


def test_input_limit_and_output_exhaustion_are_resource_failures(provider):
    """An input over the per-request limit is refused unsent; finish_reason length and timeouts are RESOURCE
    failures (one request each), not schema or semantic results."""
    stages = arm_stage('gpt-4o-mini', input_token_limit=50)
    stages('draft', {'rules': 'r' * 400}, GroundingJudgment)
    assert stages.log[0]['failure_class'] == 'RESOURCE' and 'InputLimitExceeded' in stages.log[0]['error'] and not provider.requests

    def truncated(request):
        body = completion('{"verdicts": [')
        body['choices'][0]['finish_reason'] = 'length'
        return httpx.Response(200, json=body, request=request)
    provider.reply = truncated
    stages = arm_stage('gpt-6.1-sol')
    stages('draft', {'rules': 'r'}, GroundingJudgment)
    assert stages.log[0]['failure_class'] == 'RESOURCE' and 'OutputLimitReached' in stages.log[0]['error']

    def timeout(request):
        raise httpx.ReadTimeout('offline timeout', request=request)
    provider.reply = timeout
    stages = arm_stage('gpt-6.1-sol')
    stages('draft', {'rules': 'r'}, GroundingJudgment)
    assert stages.log[0]['failure_class'] == 'RESOURCE' and len(provider.requests) == 2
