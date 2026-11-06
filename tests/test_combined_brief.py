"""The combined briefing (49 reused cards + 14 refreshed consolidated issues) through the dashboard, its revalidation,
and decision/evidence isolation across the consolidated, refresh and combined runs. Zero model calls."""
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT/'data/experiments'
COMBINED, CONSOLIDATED, REFRESH = 'threadsense_full_v1_combined_v1', 'threadsense_full_v1_consolidated_v1', 'threadsense_full_v1_consolidated_refresh_v1'
pytestmark = pytest.mark.skipif(not (EXP/COMBINED).is_dir(), reason='combined derived run not present')


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    root = tmp_path_factory.mktemp('runs')
    for name in (COMBINED, CONSOLIDATED, REFRESH):
        shutil.copytree(EXP/name, root/name, ignore=shutil.ignore_patterns('screenshots'))
    store = DecisionStore(tmp_path_factory.mktemp('store')/'d.sqlite3')
    return TestClient(create_app(catalog=Catalog([root]), store=store, session_actor='U006'))


def _cards(client, key):
    return {c['card']['card_id']: c for c in client.get(f'/api/runs/{key}/brief').json()['cards']}


def _named(cards, name):
    return next(c for c in cards.values() if c['card']['topic_name'] == name)


def test_combined_brief_counts_inventories_and_accounting(client):
    brief = client.get(f'/api/runs/{COMBINED}/brief').json()
    cards = {c['card']['card_id']: c for c in brief['cards']}
    inventory = lambda c: c['presentation']['inventory']
    in_brief = [c for c in cards.values() if inventory(c) == 'BRIEF' and c['card']['briefing']['status'] == 'IN_BRIEFING']
    lines = sorted(c['card']['card_line'] for c in in_brief)
    assert len(in_brief) == 63 and lines.count('NEEDS_REVIEW') == 53 and lines.count('RECOMMENDED_ACTION') == 7
    assert lines.count('OBSERVATION') == 3
    assert sum(inventory(c) == 'PROCESSING_HISTORY' for c in cards.values()) == 3
    assert not any(inventory(c) == 'REPLACED' for c in cards.values())  # replaced cards are not served as cards
    combined = [c for c in cards.values() if c['presentation']['combined']]
    assert len(combined) == 14 and sum(len(c['presentation']['combined']['replaced_cards']) for c in combined) == 29
    derivation = json.loads((EXP/COMBINED/'derivation.json').read_text(encoding='utf-8'))
    assert derivation['summary']['accounting']['threads'] == 177 and derivation['summary']['accounting']['review_items'] == 37
    assert derivation['summary']['revalidation']['model_calls'] == 0
    run = brief['run']
    assert run['consolidation']['refreshed'] and run['consolidation']['pending'] == []
    parts = json.loads((EXP/COMBINED/'morning_brief.json').read_text(encoding='utf-8'))['derivation']['provenance_of_parts']
    assert parts['agent1_relevance']['source'] == 'DEVELOPER_AUDIT' and parts['agent2_consolidation']['source'] == 'PREPARED_AUDIT'
    assert parts['agent3_advice'].startswith('LIVE_MODEL')


def test_replaced_cards_appear_only_through_lineage(client):
    combined = _cards(client, COMBINED)
    issue = _named(combined, 'QN handling for fictional contact details')
    replaced = issue['presentation']['combined']['replaced_cards']
    assert sorted(c['topic_name'] for c in replaced) == ['Fictional placeholder contact details and QN handling',
                                                          'QN handling for fictional phone numbers']
    for c in replaced:
        assert client.get(f"/api/runs/{COMBINED}/cards/{c['card_id']}").status_code == 404
        assert client.get(f"/api/runs/{CONSOLIDATED}/cards/{c['card_id']}").status_code == 200  # still readable where it was briefed


def test_revalidated_cards_carry_the_corrected_checks(client):
    combined = _cards(client, COMBINED)
    overlap = _named(combined, 'Overlapping speech in transcription')
    reasons = {r['code']: r['detail'] for r in overlap['card']['needs_review_reasons']}
    assert reasons['GROUNDING_FAILURE'] == 'Withheld from this card: claim:c1: PENDING' and overlap['card']['recommended_action']
    assert 'have not been checked against the evidence yet' in ' '.join(overlap['card']['review_notes'])
    business = _named(combined, 'Public business contact details are not private PII')
    assert 'TEMPORAL_CONFLICT' not in {r['code'] for r in business['card']['needs_review_reasons']}
    assert business['card']['checks']['temporal_conflict'] == 'NONE_FOUND'
    fictional = _named(combined, 'QN handling for fictional contact details')
    item = next(i for i in fictional['review']['items'] if i['code'] == 'TEMPORAL_CONFLICT')
    assert item['title'] == 'A documentation question is unresolved'
    assert [f['code'] for f in item['findings']] == ['DOCUMENTATION_STATUS_UNRESOLVED']
    assert item['findings'][0]['links'] and 'October status note' in item['findings'][0]['detail']


def test_older_scoring_card_surfaces_its_supported_pending_step(client):
    card = _named(_cards(client, COMBINED), 'Older scoring guide screenshot versus newer pinned note')['card']
    step = card['outstanding_step']
    assert step['kind'] == 'WAITING_ON_REQUESTED_STEP' and step['text_source'] == 'SUPPORTED_STATEMENTS'
    assert any('dated' in d or 'change history' in d or 'version' in d for d in step['details'])


def test_decisions_and_evidence_stay_isolated_across_the_three_runs(client):
    runs = {r['run_key']: r for r in client.get('/api/runs').json()['runs']}
    assert len({runs[k]['run_instance'] for k in (COMBINED, CONSOLIDATED, REFRESH)}) == 3
    combined, refresh = _cards(client, COMBINED), _cards(client, REFRESH)
    issue = _named(combined, 'Overlapping speech in transcription')
    parent_id = issue['card']['derivation']['parent_card_id']
    assert parent_id in refresh and parent_id not in combined
    assert client.get(f'/api/runs/{REFRESH}/cards/{issue["card"]["card_id"]}').status_code == 404
    # A reused card keeps its ID in both runs; its decision binds to the run instance it was made on.
    reused = _named(combined, 'QA inconsistency on tie judgments')['card']['card_id']
    assert reused in _cards(client, CONSOLIDATED)
    for key, cid, idem in ((COMBINED, issue['card']['card_id'], 'combined-iso-0001'), (COMBINED, reused, 'combined-iso-0002')):
        saved = client.post(f'/api/runs/{key}/cards/{cid}/decisions', json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'test'},
                            headers={'Idempotency-Key': idem})
        assert saved.status_code in (200, 201), saved.text
    assert client.get(f'/api/runs/{CONSOLIDATED}/decisions').json()['decisions'] == []
    assert client.get(f'/api/runs/{REFRESH}/decisions').json()['decisions'] == []
    assert len(client.get(f'/api/runs/{COMBINED}/decisions').json()['decisions']) == 2
    # Evidence resolves inside the run that cites it.
    eid = next(e['evidence_id'] for e in issue['cited_evidence'] if not e.get('missing_from_ledger'))
    assert client.get(f'/api/runs/{COMBINED}/evidence/{eid}').status_code == 200
