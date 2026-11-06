"""The Observation demo fixture: two hand-written OBSERVATION cards served as a labelled test fixture, separate from
live runs. No model calls."""
from fastapi.testclient import TestClient

from threadsense.agents.advice_contracts import AdviceCardV5
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog
from threadsense.routing import ROOT

FIXTURES = ROOT/'tests/fixtures/observation_demo_runs'


def test_two_labelled_observations_with_a_supported_reason_and_no_open_request(tmp_path):
    client = TestClient(create_app(catalog=Catalog([FIXTURES]), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    run = next(r for r in client.get('/api/runs').json()['runs'] if r['run_key'] == 'observation_demo_fixture_v1')
    assert run['mode'] == 'TEST_FIXTURE' and run['namespace'] == 'test'
    cards = [c for c in client.get('/api/runs/observation_demo_fixture_v1/brief').json()['cards']]
    assert sorted(c['card']['topic_name'] for c in cards) == ['Slow waveform rendering on long clips (recovered)',
                                                               'Unrequested markdown headers in plain-text answers']
    for c in cards:
        card = AdviceCardV5.model_validate(c['card'])
        assert card.card_line == 'OBSERVATION' and card.next_step.status == 'NO_ACTION_NEEDED' and card.next_step.rationale
        assert card.outstanding_step is None and not card.needs_review_reasons and card.resolution_status == 'RESOLVED_IN_THREAD'
        assert c['semantic_source'] == 'TEST_FIXTURE' and c['cited_evidence']
