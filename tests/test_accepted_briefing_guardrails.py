"""Routing guardrails on every card the dashboard serves for the accepted briefing (threadsense_full_v1_combined_v2).

The rules are tested on synthetic cards elsewhere; this checks the saved briefing itself, as served by the real API, so a
card line and the dashboard category can never disagree with the evidence behind them. Zero model calls."""
from collections import Counter
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.routing import ROOT

RUN = ROOT/'data/experiments/threadsense_full_v1_combined_v2'


@pytest.fixture(scope='module')
def served(tmp_path_factory):
    root = tmp_path_factory.mktemp('runs')
    shutil.copytree(RUN, root/RUN.name, ignore=shutil.ignore_patterns('screenshots'))
    client = TestClient(create_app(catalog=Catalog([root]), store=DecisionStore(root/'d.sqlite3'), session_actor='U006'))
    brief = client.get(f'/api/runs/{RUN.name}/brief')
    assert brief.status_code == 200
    active = [c for c in brief.json()['cards'] if c['presentation']['briefing']['status'] == 'IN_BRIEFING']
    return active, Run(root/RUN.name)


def codes(card):
    return {r['code'] for r in card['needs_review_reasons']}


def test_active_briefing_counts(served):
    active, _ = served
    assert Counter(c['card']['card_line'] for c in active) == {'NEEDS_REVIEW': 52, 'RECOMMENDED_ACTION': 8, 'OBSERVATION': 3}


def test_high_severity_stays_in_review_whatever_the_confidence(served):
    active, _ = served
    high = [c['card'] for c in active if c['card']['severity']['level'] == 'HIGH']
    assert high and max(k['confidence'] for k in high) >= 0.9  # high confidence does not lift a HIGH card out of review
    assert all(k['card_line'] == 'NEEDS_REVIEW' and 'HIGH_SEVERITY' in codes(k) for k in high)


def test_inherited_flags_and_review_reasons_keep_cards_in_review(served):
    active, _ = served
    for c in active:
        k = c['card']
        if k['inherited_flags'] or k['needs_review_reasons']:
            assert k['card_line'] == 'NEEDS_REVIEW', k['card_id']
        if k['card_line'] == 'RECOMMENDED_ACTION':
            assert k['recommended_action'] and k['next_step']['status'] == 'ACTION_RECOMMENDED', k['card_id']


def test_a_withheld_recommendation_keeps_its_open_follow_up(served):
    active, _ = served
    withheld = [c['card'] for c in active if c['card']['next_step']['status'] == 'RECOMMENDATION_WITHHELD']
    assert withheld
    for k in withheld:
        assert k['card_line'] == 'NEEDS_REVIEW' and k['recommended_action'] is None
        assert 'RECOMMENDATION_WITHHELD' in codes(k) and k['outstanding_step'], k['card_id']


def test_an_observation_rests_on_a_supported_no_action_reason(served):
    active, run = served
    observations = [c for c in active if c['card']['card_line'] == 'OBSERVATION']
    assert observations
    for c in observations:
        k = c['card']
        assert k['next_step']['status'] == 'NO_ACTION_NEEDED' and not k['needs_review_reasons']
        assert not c['presentation']['unsupported_observation']  # the dashboard shows it as an Observation, not review
        topic = run.topics[k['card_id']]
        statements = (topic.get('result') or topic)['grounding']['statements']  # derived runs nest the saved result
        verdicts = {s['statement_id']: s['verdict'] for s in statements}
        assert verdicts.get('action:no_action') == 'SUPPORTED', k['card_id']
