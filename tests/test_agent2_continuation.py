"""Continuation tests use real journals and mocked HTTP; no paid calls."""
import json

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import topic_continuation as continuation
from threadsense.agents import verification_requests as transport
from threadsense.handoff_inputs import read_json, identity
from threadsense.topic_inputs import load_candidate_payloads

MODEL = 'openai/gpt-4o-mini'


@pytest.fixture(scope='module')
def payloads():
    return load_candidate_payloads()


@pytest.fixture(autouse=True)
def no_unmocked_requests(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL', MODEL)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('A test tried to make a non-mocked request.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


def _response(payload):
    """Structure-only synthetic response, not a factual consolidation benchmark."""
    from tests.agent2_structured_fixtures import wiring_draft
    draft = wiring_draft(payload)
    return 200, json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(draft)}}]}).encode(), None


def _interrupted_run(monkeypatch, path, payloads):
    by_id = {p['candidate_group_id']: p for p in payloads}
    attempts = []
    def send(endpoint, body, key):
        gid = json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id']
        attempts.append(gid)
        if len(attempts) == 2:
            return 200, b'{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}', None
        if len(attempts) == 3:
            raise KeyboardInterrupt()
        return _response(by_id[gid])
    monkeypatch.setattr(transport, 'send_once', send)
    manifest = pipeline.execute_batch(payloads, path, run=True, maximum_requests=len(payloads))
    assert manifest['state'] == 'interrupted'
    return attempts


def test_full_coverage_continuation_calls_only_never_started_and_keeps_every_flag(monkeypatch, tmp_path, payloads):
    source, output = tmp_path / 'source', tmp_path / 'continued'
    old_attempts = _interrupted_run(monkeypatch, source, payloads)
    before = continuation.tree_hashes(source)
    old_records = read_json(source / 'consolidations.json')
    new_attempts = []
    by_id = {p['candidate_group_id']: p for p in payloads}
    def send(endpoint, body, key):
        gid = json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id']
        new_attempts.append(gid)
        assert gid not in old_attempts
        return _response(by_id[gid])
    monkeypatch.setattr(transport, 'send_once', send)
    result = continuation.continue_batch(payloads, source, output, run=True, maximum_requests=87)
    assert len(new_attempts) == len(set(new_attempts)) == 87
    assert result['new_request_attempts'] == 90 and result['continued_request_attempts'] == 87
    assert result['available_response_records'] == 89
    assert result['unknown_completion_requests'] == [old_attempts[-1]]
    assert result['unprocessed_groups'] == 0 and result['state'] == 'complete_with_review'
    assert result['processing_counts'] == {'CONSOLIDATED': 88, 'FAILED': 1, 'INTERRUPTED': 1}
    assert result['retained_input_identities'] == 200 and result['inherited_review_obligations'] == 49
    records = read_json(output / 'consolidations.json')
    assert records[:3] == old_records[:3]
    expected = {identity(m) for p in payloads for m in p['members'] if m['agent1_record']['review_required']}
    assert {identity(o) for o in read_json(output / 'member_review_queue.json')} == expected
    assert read_json(output / 'review_queue.json') == [r for r in records if r['review_required']]
    assert continuation.tree_hashes(source) == before
    for gid in old_attempts:
        for path in (source / 'records' / gid).iterdir():
            assert path.read_bytes() == (output / 'records' / gid / path.name).read_bytes()
    assert not continuation.inspect_run(output, payloads, MODEL)['remaining']


def test_second_interruption_can_continue_without_retrying_first_interruption(monkeypatch, tmp_path, payloads):
    selected = payloads[:5]
    source, second, third = tmp_path / 'source', tmp_path / 'second', tmp_path / 'third'
    _interrupted_run(monkeypatch, source, selected)
    def interrupt(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(transport, 'send_once', interrupt)
    result = continuation.continue_batch(selected, source, second, run=True, maximum_requests=2)
    assert result['state'] == 'interrupted' and result['unprocessed_groups'] == 1
    assert result['new_request_attempts'] == 4
    calls = []
    def send(endpoint, body, key):
        calls.append(json.loads(json.loads(body)['messages'][1]['content'])['candidate_group_id'])
        return _response(selected[-1])
    monkeypatch.setattr(transport, 'send_once', send)
    result = continuation.continue_batch(selected, second, third, run=True, maximum_requests=1)
    assert calls == [selected[-1]['candidate_group_id']]
    assert result['new_request_attempts'] == 5 and result['continued_request_attempts'] == 1
    assert len(result['unknown_completion_requests']) == 2
    assert result['unprocessed_groups'] == 0


def test_hard_stop_uses_child_journal_even_when_combined_reports_are_stale(monkeypatch, tmp_path, payloads):
    selected = payloads[:5]
    source, prepared = tmp_path / 'source', tmp_path / 'prepared'
    _interrupted_run(monkeypatch, source, selected)
    continuation.continue_batch(selected, source, prepared)
    info = continuation.inspect_run(prepared, selected, MODEL)
    assert len(info['remaining']) == 2
    gid = selected[3]['candidate_group_id']
    # Emulate a process kill after call/start persistence, before any response or report update.
    directory = prepared / 'new_requests' / 'records' / gid
    pipeline.write_json(directory / 'started.json', {'maximum_requests': 1})
    pipeline.write_json(directory / 'call.json', {'attempt': 1})
    before = continuation.tree_hashes(prepared)
    recovered = continuation.inspect_run(prepared, selected, MODEL)
    assert [p['candidate_group_id'] for p in recovered['remaining']] == [selected[4]['candidate_group_id']]
    assert recovered['records'][gid]['processing_state'] == 'INTERRUPTED'
    assert gid in recovered['unknown'] and recovered['prior_request_attempts'] == 4
    assert continuation.tree_hashes(prepared) == before


def test_started_without_call_marker_is_also_excluded(monkeypatch, tmp_path, payloads):
    selected = payloads[:4]
    source = tmp_path / 'source'
    _interrupted_run(monkeypatch, source, selected)
    gid = selected[3]['candidate_group_id']
    pipeline.write_json(source / 'records' / gid / 'started.json', {'maximum_requests': 1})
    info = continuation.inspect_run(source, selected, MODEL)
    assert info['remaining'] == []
    assert info['started_without_call'] == [gid]
    assert gid in info['unknown']


@pytest.mark.parametrize('mutation', ['config', 'request', 'input', 'flags'])
def test_changed_source_is_rejected_before_attempts(monkeypatch, tmp_path, payloads, mutation):
    selected = payloads[:4]
    source = tmp_path / 'source'
    _interrupted_run(monkeypatch, source, selected)
    if mutation == 'config':
        path = source / 'manifest.json'
        data = read_json(path); data['config_sha256'] = 'changed'
    elif mutation == 'request':
        path = source / 'records' / selected[-1]['candidate_group_id'] / 'request.json'
        data = read_json(path); data['temperature'] = 1
    elif mutation == 'input':
        path = source / 'records' / selected[-1]['candidate_group_id'] / 'input.json'
        data = read_json(path); data['members'] = []
    else:
        path = source / 'consolidations.json'
        data = read_json(path); data[0]['inherited_review_obligations'] = []
    pipeline.write_json(path, data)
    with pytest.raises(ValueError):
        continuation.continue_batch(selected, source, tmp_path / 'bad', run=True, maximum_requests=1)
    assert not (tmp_path / 'bad').exists()


def test_offline_prepare_no_credentials_and_wrong_budget_no_output(monkeypatch, tmp_path, payloads):
    selected = payloads[:4]
    source = tmp_path / 'source'
    _interrupted_run(monkeypatch, source, selected)
    def forbidden(*args):
        raise AssertionError('Offline operation read credentials or sent a request.')
    monkeypatch.setattr(pipeline.config, 'get_api_key', forbidden)
    monkeypatch.setattr(transport, 'send_once', forbidden)
    with pytest.raises(ValueError, match='1 never-started'):
        continuation.continue_batch(selected, source, tmp_path / 'wrong', run=True, maximum_requests=4)
    assert not (tmp_path / 'wrong').exists()
    with pytest.raises(FileExistsError):
        continuation.continue_batch(selected, source, source)
    prepared = tmp_path / 'prepared'
    result = continuation.continue_batch(selected, source, prepared)
    assert result['state'] == 'prepared_no_calls' and result['continued_request_attempts'] == 0
    assert result['new_request_attempts'] == 3 and result['unprocessed_groups'] == 1
    assert not list((prepared / 'new_requests').rglob('call.json'))
    with pytest.raises(FileExistsError):
        continuation.continue_batch(selected, source, prepared)


def test_fatal_failure_preserves_earlier_results_and_later_pending_groups(monkeypatch, tmp_path, payloads):
    selected = payloads[:5]
    source, output = tmp_path / 'source', tmp_path / 'continued'
    _interrupted_run(monkeypatch, source, selected)
    monkeypatch.setattr(transport, 'send_once', lambda *args: (401, b'{}', None))
    with pytest.raises(transport.VerificationConfigurationError):
        continuation.continue_batch(selected, source, output, run=True, maximum_requests=2)
    manifest = read_json(output / 'manifest.json')
    assert manifest['state'] == 'failed' and manifest['unprocessed_groups'] == 1
    assert manifest['new_request_attempts'] == 4 and manifest['continued_request_attempts'] == 1
    assert len(read_json(output / 'consolidations.json')) == 5
