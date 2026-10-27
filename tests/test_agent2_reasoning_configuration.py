"""Offline request compatibility only; synthetic completions imply no semantic accuracy."""
import json

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline, topic_requests as requests
from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_consolidation_v6 import build_request
from threadsense.handoff_inputs import ROOT, read_json
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, payload
from tests.agent2_structured_fixtures import reviewed_draft, assert_only_question_uncertainty_schema_changed


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv(requests.REASONING_ENV, raising=False)
    monkeypatch.setenv('THREADSENSE_MODEL', requests.COMPARISON_MODEL)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-offline-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('Live transport forbidden in offline tests.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


@pytest.mark.parametrize('gid', [GIDS[0], GIDS[1]])
def test_saved_v52_semantics_identical_with_only_explicit_configuration_delta(monkeypatch, gid):
    directory = ROOT/'data/processed/agent2_focused_v5_2/records'/gid
    p = read_json(directory/'input.json')
    historical = read_json(directory/'request.json')
    # Exercise the frozen v5.2 instructions through the current adapter. Later
    # versioned prompts must not alter this historical configuration comparison.
    system = historical['messages'][0]['content']
    inputs = json.loads(historical['messages'][1]['content'])
    current_format = requests.response_format()
    assert_only_question_uncertainty_schema_changed(current_format, historical['response_format'])
    # Freeze the historical schema while testing its historical request parameters.
    monkeypatch.setattr(requests, 'response_format', lambda *args, **kwargs: historical['response_format'])
    assert requests.request_body(requests.COMPARISON_MODEL, system, inputs) == historical
    monkeypatch.setenv(requests.REASONING_ENV, 'low')
    low = requests.request_body(requests.COMPARISON_MODEL, system, inputs)
    expected = dict(historical, reasoning_effort='low')
    expected.pop('temperature')
    assert low == expected
    assert low['max_completion_tokens'] == 8192
    assert not {'temperature', 'top_p', 'logprobs'} & low.keys()
    current = build_request(p, get_terms(), requests.COMPARISON_MODEL)
    current_inputs = json.loads(current['messages'][1]['content'])
    assert current_inputs.pop('schema_version') == 6
    assert inputs.pop('schema_version') == 5
    assert current_inputs == inputs
    assert {k:v for k,v in current.items() if k != 'messages'} == {k:v for k,v in low.items() if k != 'messages'}


@pytest.mark.parametrize('effort,model', [
    ('medium', requests.COMPARISON_MODEL), ('', requests.COMPARISON_MODEL),
    ('low', requests.BASELINE_MODEL), ('low', 'openai/gpt-5.4'),
])
def test_unreviewed_configurations_fail_closed(monkeypatch, effort, model):
    monkeypatch.setenv(requests.REASONING_ENV, effort)
    with pytest.raises(ValueError):
        requests.request_body(model, 'Synthetic instructions', {'input': 'Synthetic source'})


@pytest.mark.parametrize('finish_reason', ['stop', 'length'])
def test_low_actual_wire_omits_sampling_defaults_and_never_retries(monkeypatch, tmp_path, finish_reason):
    monkeypatch.setenv(requests.REASONING_ENV, 'low')
    original_builder = transport.request_body
    def builder(*args, **kwargs):
        return dict(original_builder(*args, **kwargs), top_p=1, logprobs=False)
    monkeypatch.setattr(transport, 'request_body', builder)
    captured = []
    usage = {'prompt_tokens': 100, 'completion_tokens': 8192 if finish_reason == 'length' else 250,
             'prompt_tokens_details': {'cached_tokens': 0},
             'completion_tokens_details': {'reasoning_tokens': 128}}
    def send(endpoint, body, key):
        captured.append(body)
        return 200, json.dumps({'model': 'gpt-5.4-2026-03-05', 'usage': usage,
            'choices': [{'finish_reason': finish_reason,
                         'message': {'content': json.dumps(reviewed_draft(GIDS[0]))}}]}).encode(), None
    monkeypatch.setattr(transport, 'send_once', send)
    run = tmp_path/'run'
    manifest = pipeline.execute_batch([payload(GIDS[0])], run, run=True, maximum_requests=1)
    d = run/'records'/GIDS[0]
    assert len(captured) == manifest['new_request_attempts'] == 1
    assert captured[0] == (d/'request.json').read_bytes()
    wire = json.loads(captured[0])
    assert wire['model'] == 'gpt-5.4-2026-03-05' and wire['reasoning_effort'] == 'low'
    assert not {'temperature', 'top_p', 'logprobs', 'max_tokens'} & wire.keys()
    assert wire['max_completion_tokens'] == 8192
    assert manifest['config']['request_parameters'] == {'max_completion_tokens': 8192, 'reasoning_effort': 'low'}
    status = read_json(d/'completion_status.json')
    assert status['usage'] == usage and status['finish_reason'] == finish_reason
    assert status['status'] == ('COMPLETED' if finish_reason == 'stop' else 'INCOMPLETE_OUTPUT')
    assert read_json(d/'result.json')['processing_state'] == ('CONSOLIDATED' if finish_reason == 'stop' else 'FAILED')
    assert (d/'response.raw.bin').exists() and (d/'analysis.raw.txt').exists()
