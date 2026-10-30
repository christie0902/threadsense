"""Milestone 7: a saved TL decision reaches a later overnight run, offline.

save a decision (dashboard API, live smoke card) -> build a later snapshot at a coherent cutoff -> run the Advisor
through the overnight graph on that snapshot (scripted judgments) -> the decision is in the topic's saved evidence as
a prior record (approved, not executed, not observed). Test-double encoder; zero model calls.
"""
import json

from fastapi.testclient import TestClient
import pytest

from threadsense.agents import overnight
from threadsense.agents.advisor_evidence import open_retriever
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decision_sources import build_snapshot
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog
from threadsense.handoff_inputs import read_json
from threadsense.retrieval.index import snapshot_sources
from threadsense.routing import ROOT, aware
from tests.retrieval_doubles import HashEncoder

SMOKE = 'agent3_overnight_smoke_v1'
SAVED_AT = '2026-10-30T15:00:00Z'   # After the run it answers (smoke run cutoff 2026-10-02T12:00:00Z).
CUTOFF = '2026-10-31T06:00:00Z'     # Later than the decision; not in the future relative to the build clock.


def snapshot_retriever(index_dir):
    return lambda: open_retriever(index_dir, encoder=HashEncoder(), **snapshot_sources(read_json(index_dir/'manifest.json')))


@pytest.fixture(scope='module')
def loop(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('loop')
    store = DecisionStore(tmp/'store.sqlite3')
    catalog = Catalog([ROOT/'data/experiments'])
    client = TestClient(create_app(catalog=catalog, store=store, clock=lambda: SAVED_AT, static_dir=tmp/'none'))
    card = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'audio_multimodal')
    first = client.post(f"/api/runs/{SMOKE}/cards/{card['card_id']}/decisions", headers={'Idempotency-Key': 'feedback-loop-1'},
                        json={'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING',
                              'note': 'Send the consolidated playback report; ask whether the reload trial applies.'}).json()['entry']
    built = build_snapshot(store, tmp/'snapshot', cutoff=CUTOFF, encoder=HashEncoder(), export_dir=tmp/'exports', now=CUTOFF)
    rt = overnight.Runtime(tmp/'run', client=overnight.HandoffScriptedClient(), cutoff=CUTOFF, only=['audio_playback'],
                           retriever_factory=snapshot_retriever(tmp/'snapshot'))
    state = overnight.run(rt)
    rt.retriever.client.close()
    return {'tmp': tmp, 'store': store, 'decision': first, 'built': built, 'rt': rt, 'state': state, 'card': card}


def test_snapshot_is_later_and_includes_the_decision_without_backdating(loop):
    built, decision = loop['built'], loop['decision']
    assert aware(decision['recorded_at']) <= aware(CUTOFF) and built['decisions_indexed'] == 1
    assert built['current_day_announcements'] == 0 and built['prior_announcements']['extracted'] == 23
    manifest = read_json(loop['tmp']/'run'/'run_manifest.json')['fingerprints']
    assert manifest['cutoff'] == CUTOFF and manifest['index']['cutoff'] == CUTOFF
    assert manifest['index']['tl_decisions_included'] == 1 and manifest['index']['prior_announcements'] == 23
    assert manifest['index']['build_fingerprint'] == built['build_fingerprint'] and manifest['fixture_sha256']


def test_overnight_run_retrieves_the_saved_decision_as_history(loop):
    result = next(read_json(p) for p in (loop['tmp']/'run'/'topics').glob('*.json'))
    ledger = result['result']['evidence_ledger']
    decisions = [e for e in ledger.values() if ((e.get('citation') or {}).get('authoring') or '').startswith('tl-decision-')]
    assert decisions, sorted(ledger)
    entry = decisions[0]
    assert entry['use'] == 'PRIOR_DECISION'  # History, not a standing rule or current policy.
    assert entry['recorded_states'] == {'status': 'tl_approved', 'decision_status': 'tl_approved',
                                        'execution_status': 'not_executed', 'outcome_status': 'not_observed'}
    assert 'execution_status: not_executed' in entry['excerpt'] and 'history, not a standing rule' in entry['excerpt']
    assert entry['excerpt'].startswith('[PRIOR RECORD')


def test_brief_labels_the_handoff_as_a_replay_not_new_activity(loop):
    brief = read_json(loop['tmp']/'run'/'morning_brief.json')
    activity = brief['handoff_activity']
    assert activity['replay_of_earlier_handoff'] and activity['discussion_threads_in_window'] == 0
    assert aware(activity['last_message_at']) < aware(brief['window']['start'])
    assert brief['counts']['window_announcements'] == 0
    assert brief['snapshot']['tl_decisions_included'] == 1
    report = (loop['tmp']/'run'/'morning_brief.md').read_text(encoding='utf-8')
    assert 'not new Slack activity' in report and '1 saved TL decisions' in report


def test_a_resume_never_switches_the_snapshot(loop):
    tmp, store = loop['tmp'], loop['store']
    other = build_snapshot(store, tmp/'snapshot_b', cutoff='2026-10-31T05:00:00Z', encoder=HashEncoder(),
                           export_dir=tmp/'exports', now=CUTOFF)
    assert other['build_fingerprint'] != loop['built']['build_fingerprint']
    rt = overnight.Runtime(tmp/'run', client=overnight.HandoffScriptedClient(), cutoff='2026-10-31T05:00:00Z',
                           only=['audio_playback'], retriever_factory=snapshot_retriever(tmp/'snapshot_b'))
    with pytest.raises(overnight.OvernightError, match='changed since the run started'):
        overnight.run(rt)
    rt.retriever.client.close()
    # A run cutoff that differs from the snapshot cutoff is refused before any work.
    rt = overnight.Runtime(tmp/'run_c', client=overnight.HandoffScriptedClient(), cutoff='2026-10-02T12:00:00Z',
                           only=['audio_playback'], retriever_factory=snapshot_retriever(tmp/'snapshot'))
    with pytest.raises(overnight.OvernightError, match='differs from the retrieval snapshot cutoff'):
        overnight.run(rt)
    rt.retriever.client.close()


def test_the_decision_store_is_unchanged_by_the_run(loop):
    store = loop['store']
    assert store.counts()['card_decisions'] == 1
    assert json.dumps(store.all_card_decisions()[0], sort_keys=True) == json.dumps(loop['decision'], sort_keys=True)
