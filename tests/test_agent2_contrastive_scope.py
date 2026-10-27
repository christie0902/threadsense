"""Prompt delivery/citation regressions, not tests of live model understanding."""
from copy import deepcopy
import json

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.agents import topic_pipeline as pipeline, verification_requests as transport
from threadsense.agents.topic_consolidation_v6 import build_request, parse_response, PROMPT_VERSION
from threadsense.handoff_inputs import ROOT, read_json
from threadsense.terminology import get_terms
from tests.agent2_inventory_fixtures import GIDS, payload
from tests.agent2_structured_fixtures import reviewed_draft

MODEL = 'openai/gpt-5.4-2026-03-05'
BEGIN = 'BEGIN SYNTHETIC QUESTION-SCOPE CONTRAST'
END = 'END SYNTHETIC QUESTION-SCOPE CONTRAST\n\n'


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('THREADSENSE_MODEL', MODEL)
    monkeypatch.setenv('THREADSENSE_AGENT2_REASONING_EFFORT', 'low')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-offline-key')
    def forbidden(*args, **kwargs):
        raise AssertionError('No live network in offline prompt tests.')
    monkeypatch.setattr(transport, 'send_once', forbidden)


def test_exact_wire_changes_only_prompt_version_and_one_synthetic_contrast(monkeypatch, tmp_path):
    sent = []
    def send(endpoint, body, key):
        sent.append(body)
        return 200, json.dumps({'model': MODEL.split('/', 1)[1], 'choices': [
            {'finish_reason': 'stop', 'message': {'content': json.dumps(reviewed_draft(GIDS[1]))}}]}).encode(), None
    monkeypatch.setattr(transport, 'send_once', send)
    run = tmp_path/'run'
    pipeline.execute_batch([payload(GIDS[1])], run, run=True, maximum_requests=1)
    assert len(sent) == 1 and sent[0] == (run/'records'/GIDS[1]/'request.json').read_bytes()
    wire = json.loads(sent[0])
    # Preserve the historical v5.3-versus-v5.2 experiment assertion exactly.
    # The live adapter's v6 delivery is checked separately below and in v6 tests.
    current = read_json(ROOT/'data/processed/agent2_contrastive_v5_3/records'/GIDS[1]/'request.json')
    previous = read_json(ROOT/'data/processed/agent2_reasoning_low_v5_2/records'/GIDS[1]/'request.json')
    assert current['messages'][1] == previous['messages'][1]
    assert {k:v for k,v in current.items() if k != 'messages'} == {k:v for k,v in previous.items() if k != 'messages'}
    system = current['messages'][0]['content']
    assert wire['messages'][0]['content'].startswith(f'Prompt version: {PROMPT_VERSION}\n')
    assert PROMPT_VERSION == 'agent2-inventory-v6'
    assert system.count(BEGIN) == system.count(END) == 1
    prefix, rest = system.split(BEGIN)
    block, suffix = rest.split(END)
    assert (prefix + suffix).replace('agent2-inventory-v5.3', 'agent2-inventory-v5.2') == previous['messages'][0]['content']
    for phrase in ('Where should I report an export failure?', 'May I submit the incomplete export?',
                   'same reply', '"status":"ANSWERED"', '"status":"OPEN"', '"kind":"INSTRUCTION"',
                   'PARTIAL requires an actual substantive component', 'indirect but unambiguous',
                   'exact keyword repetition is unnecessary', 'Guidance and authority',
                   'must never appear in your response'):
        assert phrase in block
    for forbidden in (*GIDS, 'Quarantine', 'review_supplement', 'source_review_findings', 'positive_control', 'negative_control'):
        assert forbidden not in system
    assert 'SYNTH_' not in current['messages'][1]['content']
    assert current['reasoning_effort'] == 'low' and current['max_completion_tokens'] == 8192
    assert not {'temperature', 'top_p', 'logprobs'} & current.keys()


@pytest.mark.parametrize('target', ['inventory', 'summary', 'answer_link'])
def test_illustrative_references_cannot_pass_as_actual_source_or_answer_links(target):
    p = payload(GIDS[1]); draft = deepcopy(reviewed_draft(GIDS[1])); t = draft['topics'][0]
    if target == 'inventory':
        t['inventory'][0]['evidence_id'] = 'SYNTH_E_Q'
    elif target == 'summary':
        t['shared_issue']['evidence_ids'] = ['SYNTH_E_R']
    else:
        q = next(i for i in t['inventory'] if i['kind'] == 'QUESTION')
        q['question'].update(status='ANSWERED', answer_item_ids=['SYNTH_A'])
    with pytest.raises(ValueError):
        parse_response(p, json.dumps(draft))
