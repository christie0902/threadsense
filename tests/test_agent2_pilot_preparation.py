"""Reviewed pilot refreshes preserve evidence and never call a model."""
from copy import deepcopy
import json
import runpy

import pytest

from threadsense.handoff_inputs import ROOT, read_json, file_hash, identity
from threadsense.topic_inputs import load_candidate_payloads
from tests.legacy_agent2 import bind_v7
from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_consolidation_v3 import parse_response, export_result

prepare_pilot = runpy.run_path(str(ROOT / 'scripts/prepare_agent2_pilot.py'))['prepare_pilot']
select_pilot = runpy.run_path(str(ROOT / 'scripts/run_agent2_batch.py'))['select_pilot']
SOURCE = ROOT / 'docs/agent2-pilot-v2.json'
PREPARED = ROOT / 'data/processed/agent2_pilot_prepared_v2'


@pytest.fixture(scope='module')
def payloads():
    return load_candidate_payloads(historical=True)


@pytest.fixture(autouse=True)
def forbid_calls(monkeypatch, payloads, current_preparation):
    bind_v7(monkeypatch)
    def forbidden(*args, **kwargs):
        raise AssertionError('Pilot preparation must not retrieve credentials or call a model.')
    monkeypatch.setenv('THREADSENSE_MODEL', 'openai/gpt-4o-mini')
    monkeypatch.setattr(pipeline.config, 'get_api_key', forbidden)
    monkeypatch.setattr(transport, 'send_once', forbidden)
    monkeypatch.setattr(transport, 'complete_once', forbidden)
    monkeypatch.setitem(prepare_pilot.__globals__, 'load_candidate_payloads', lambda: payloads)


@pytest.fixture(scope='module')
def current_preparation(tmp_path_factory, payloads):
    """Explicit historical v7-contract preparation for code-refresh tests; historical v2 data is never augmented."""
    global SOURCE, PREPARED
    old = read_json(ROOT / 'docs/agent2-pilot-v2.json')
    ids = [c['candidate_group_id'] for c in old['cases']]
    selected = [next(p for p in payloads if p['candidate_group_id']==gid) for gid in ids]
    target = tmp_path_factory.mktemp('agent2-v3-pilot')
    SOURCE, PREPARED = target / 'source.json', target / 'prepared'
    with pytest.MonkeyPatch.context() as patch:
        bind_v7(patch)
        patch.setenv('THREADSENSE_MODEL', 'openai/gpt-4o-mini')
        manifest = pipeline.execute_batch(selected, PREPARED, run=False, maximum_requests=4)
    old['configuration_sha256'] = manifest['config_sha256']
    old['response_schema_version'] = manifest['config']['response_schema_version']
    pipeline.write_json(SOURCE, old, exclusive=True)
    return SOURCE, PREPARED


def test_new_pilot_keeps_selection_requests_and_flags_and_rejects_later_code_changes(tmp_path, monkeypatch, payloads):
    old_hash = file_hash(SOURCE)
    pilot_path, output = tmp_path / 'new-pilot.json', tmp_path / 'prepared'
    pilot, manifest = prepare_pilot(SOURCE, PREPARED, pilot_path, output,
                                   'Synthetic test review note, never model input.')
    old = read_json(SOURCE)
    assert file_hash(SOURCE) == old_hash
    assert pilot['cases'] == old['cases']
    assert pilot['maximum_request_attempts'] == 4
    assert manifest['retained_input_identities'] == 15
    assert manifest['inherited_review_obligations'] == 5
    assert manifest['processing_counts'] == {'NOT_RUN': 4}
    assert manifest['new_request_attempts'] == 0
    assert manifest['config_sha256'] == pilot['configuration_sha256']
    assert pilot['preparation_review']['model_requests_changed'] == []
    assert 'src/threadsense/routing.py' in manifest['config']['code_sha256']
    selected, bound = select_pilot(payloads, pilot_path, old['model'])
    assert len(selected) == bound == 4
    for payload in selected:
        gid = payload['candidate_group_id']
        request = output / 'records' / gid / 'request.json'
        assert request.read_bytes() == (PREPARED / 'records' / gid / 'request.json').read_bytes()
        assert 'Synthetic test review note' not in request.read_text(encoding='utf-8')
    assert not list(output.rglob('call.json'))
    assert not list(output.rglob('response.json'))
    before = (output / 'manifest.json').read_bytes()
    with pytest.raises(FileExistsError, match='new pilot and output paths'):
        prepare_pilot(SOURCE, PREPARED, pilot_path, output, 'Reviewed')
    assert (output / 'manifest.json').read_bytes() == before
    # A later edit to the routing dependency must invalidate this pilot.
    original_hash = pipeline.file_hash
    monkeypatch.setattr(pipeline, 'file_hash', lambda p: 'changed' if p.name == 'routing.py' else original_hash(p))
    with pytest.raises(ValueError, match='Pilot code/configuration changed'):
        select_pilot(payloads, pilot_path, old['model'])


@pytest.mark.parametrize('mutation, message', [
    ('canonical', 'inputs changed'),
    ('model', 'model differs'),
    ('member', 'member identities'),
    ('flags', 'review obligations changed'),
    ('bound', 'request bound'),
    ('retry', 'zero retries'),
    ('fingerprint', 'original pilot fingerprint'),
])
def test_refresh_rejects_changed_inputs_selection_budget_or_unbound_source(tmp_path, mutation, message):
    pilot = deepcopy(read_json(SOURCE))
    if mutation == 'canonical': pilot['canonical_sha256'] = 'changed'
    elif mutation == 'model': pilot['model'] = 'different'
    elif mutation == 'member': pilot['cases'][0]['member_identities'][0]['channel_id'] = 'different'
    elif mutation == 'flags': pilot['cases'][0]['inherited_review_count'] = 0
    elif mutation == 'bound': pilot['maximum_request_attempts'] = 5
    elif mutation == 'retry': pilot['automatic_retries'] = 1
    else: pilot['configuration_sha256'] = 'changed'
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(pilot), encoding='utf-8')
    new_pilot, output = tmp_path / 'new-pilot.json', tmp_path / 'prepared'
    with pytest.raises(ValueError, match=message):
        prepare_pilot(source, PREPARED, new_pilot, output, 'Synthetic test review.')
    assert not new_pilot.exists() and not output.exists()


def test_review_note_is_required_before_preparation(tmp_path):
    with pytest.raises(ValueError, match='review-note'):
        prepare_pilot(SOURCE, PREPARED, tmp_path / 'pilot.json', tmp_path / 'prepared', ' ')
    assert not (tmp_path / 'prepared').exists()


def test_rubric_severity_leaves_member_disputes_intact(payloads):
    fixture = read_json(ROOT / 'tests/fixtures/agent2_hardening_v3.json')
    draft = next(c['draft'] for c in fixture['cases'] if c['candidate_group_id']=='cluster_6b59d13144282285')
    payload = next(p for p in payloads if p['candidate_group_id'] == draft['candidate_group_id'])
    exported = export_result(payload, parse_response(payload, json.dumps(draft)), state='CONSOLIDATED')
    assert exported['topics'][0]['preliminary_severity']['level'] == 'MEDIUM'
    assert exported['topics'][0]['preliminary_severity']['severity_is_provisional'] is True
    assert exported['review_required'] is True
    assert exported['members'] == payload['members']
    expected = {identity(m) for m in payload['members'] if m['agent1_record']['review_required']}
    assert {identity(o) for o in exported['inherited_review_obligations']} == expected
    assert not exported['topics'][0]['supported_answers']
    assert exported['topics'][0]['provisional_answers'][0]['reliability'] == 'PROVISIONAL'
