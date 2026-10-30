"""Milestone 6 backend: run catalog, decision store, idempotent saves, review actions and the retrieval loop.

Offline: no model calls. Runs come from the saved experiment directories (read only) and the labelled dashboard
fixture run; every store and snapshot lives in pytest's temp directory.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from threadsense.agents.advice_inputs import decision_record_from_source
from threadsense.dashboard import decision_sources
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decision_sources import build_snapshot, decision_markdown, ingest
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import FIXTURE_RUN_ROOT, Catalog
from threadsense.knowledge_markdown import markdown_text_source
from threadsense.retrieval.config import INDEX_DIR
from threadsense.retrieval.search import Retriever
from threadsense.routing import ROOT

from tests.retrieval_doubles import HashEncoder

SMOKE, OFFLINE_V1, OFFLINE_V2, FIXTURE = ('agent3_overnight_smoke_v1', 'agent3_overnight_offline_v1',
                                          'agent3_overnight_offline_v2', 'dashboard_states_fixture_v1')
RUN_DIRS = [ROOT/'data/experiments'/k for k in (SMOKE, OFFLINE_V1, OFFLINE_V2)] + [FIXTURE_RUN_ROOT/FIXTURE]


def tree_hash(paths):
    h = sha256()
    for root in paths:
        for path in sorted(Path(root).rglob('*')):
            if path.is_file():
                h.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    return h.hexdigest()


class Clock:
    def __init__(self, value='2026-10-30T15:00:00Z'):
        self.value = value

    def __call__(self):
        return self.value


@pytest.fixture(scope='module')
def catalog():
    return Catalog(include_fixtures=True)


@pytest.fixture
def env(tmp_path, catalog):
    clock = Clock()
    store = DecisionStore(tmp_path/'store.sqlite3')
    client = TestClient(create_app(catalog=catalog, store=store, clock=clock, static_dir=tmp_path/'no-static'))
    return client, store, clock, tmp_path


def card_named(catalog, run, topic):
    return next(c for c in catalog.get(run).cards.values() if c['topic_name'] == topic)


def post(client, run, card_id, body, key):
    return client.post(f'/api/runs/{run}/cards/{card_id}/decisions', json=body, headers={'Idempotency-Key': f'test-{key}'})


def test_runs_are_listed_separately_with_their_modes(env):
    client, *_ = env
    runs = {r['run_key']: r for r in client.get('/api/runs').json()['runs']}
    expected = {SMOKE: 'LIVE', OFFLINE_V1: 'SCRIPTED', OFFLINE_V2: 'SCRIPTED', FIXTURE: 'TEST_FIXTURE'}
    assert {k: runs[k]['mode'] for k in expected} == expected  # Later saved runs may also be listed, each separately.
    # Two directories share a run ID; they stay separate runs, each naming the other.
    assert runs[OFFLINE_V1]['shares_run_id_with'] == [OFFLINE_V2] and runs[OFFLINE_V2]['shares_run_id_with'] == [OFFLINE_V1]
    assert (runs[OFFLINE_V1]['failed'], runs[OFFLINE_V1]['status']) == (1, 'COMPLETE_WITH_FAILURES')
    assert (runs[FIXTURE]['failed'], runs[FIXTURE]['unprocessed'], runs[FIXTURE]['status']) == (1, 1, 'INCOMPLETE')
    assert (runs[SMOKE]['cards'], runs[SMOKE]['out_of_scope'], runs[SMOKE]['status']) == (2, 85, 'COMPLETE')


def test_brief_returns_saved_card_text_unchanged(env, catalog):
    client, *_ = env
    brief = client.get(f'/api/runs/{SMOKE}/brief').json()
    saved = json.loads((ROOT/'data/experiments'/SMOKE/'cards.json').read_text(encoding='utf-8'))
    assert [c['card'] for c in brief['cards']] == saved
    assert {c['semantic_source'] for c in brief['cards']} == {'LIVE_MODEL'}
    audio = next(c for c in brief['cards'] if c['card']['project_id'] == 'audio_multimodal')
    # The ToT alternative the final grounding call judged SUPPORTED and SUFFICIENT, distinct from the card draft.
    assert [a['candidate_id'] for a in audio['alternatives']] == ['report_now']
    v2 = client.get(f'/api/runs/{OFFLINE_V2}/brief').json()
    assert {c['semantic_source'] for c in v2['cards']} == {'SCRIPTED_PILOT', 'SCRIPTED_PLACEHOLDER'}
    rows = client.get(f'/api/runs/{OFFLINE_V1}/brief').json()['topics']
    assert sum(r['outcome'] == 'TOPIC_FAILED' for r in rows) == 1 and len(rows) == 87


def test_evidence_and_thread_views_label_superseded_sources(env, catalog):
    client, *_ = env
    run = catalog.get(OFFLINE_V2)
    labelled = [(cid, e) for cid in run.cards for e in run.evidence(cid) if e['superseded_label']]
    sections = [(cid, e) for cid, e in labelled if e['superseded_label'].startswith('Superseded section')]
    assert sections and {e['superseded_label'].split(' - ')[0] for _, e in labelled} <= {'Superseded section', 'Expired'}
    cid, entry = sections[0]
    detail = client.get(f"/api/runs/{OFFLINE_V2}/evidence/{entry['evidence_id']}").json()
    assert detail['superseded_label'] == entry['superseded_label'] and detail['excerpt'].startswith('[HISTORICAL - NOT CURRENT')
    assert detail['dates']['source_date'] and detail['scope']['project_id'] and detail['applicability']['replaced_by']
    smoke = catalog.get(SMOKE)
    card = next(iter(smoke.cards.values()))
    t = card['related_threads'][0]
    thread = client.get(f"/api/runs/{SMOKE}/threads/{t['channel_id']}/{t['thread_id']}").json()
    assert thread['permalink'] is None and thread['source'] == 'fixture'  # Fixtures store no permalinks; none invented.
    saved = [m for m in thread['messages'] if m['in_saved_evidence']]
    assert saved and all(m['matches_saved_evidence'] for m in saved)
    assert client.get(f'/api/runs/{SMOKE}/threads/C_AUDIO_GENERAL/1790941015.000132').status_code == 404  # Not in this run.


def test_approval_is_saved_once_and_is_not_execution(env, catalog):
    client, store, clock, tmp = env
    card = card_named(catalog, FIXTURE, '[Test fixture] Fictional phone number quarantine handling')
    body = {'kind': 'APPROVE_ACTION', 'actor_id': 'U006'}
    first = post(client, FIXTURE, card['card_id'], body, 'key-approve-1')
    assert first.status_code == 201 and first.json()['persisted'] and not first.json()['replayed']
    entry = first.json()['entry']
    assert entry['text'] == {'origin': 'MODEL_GROUNDED', 'model_grounded_text': card['recommended_action']['draft_text'],
                             'grounded_source': 'CARD_DRAFT', 'alternative_id': None, 'tl_text': None}
    d = entry['decision']
    assert (d['tl_response']['outcome'], d['tl_response']['approved_actions']) == ('APPROVED', ['POST_ALIGNMENT'])
    assert (d['execution']['state'], d['outcome']['state']) == ('NOT_EXECUTED', 'NOT_OBSERVED')
    # A browser retry after a lost response: same key and body -> the stored result, no second row.
    clock.value = '2026-10-30T15:05:00Z'
    again = post(client, FIXTURE, card['card_id'], body, 'key-approve-1')
    assert again.status_code == 200 and again.json()['replayed'] and again.json()['entry'] == entry
    # Same key, different content: refused; the first decision is unchanged.
    reused = post(client, FIXTURE, card['card_id'], {**body, 'text': 'Something else.'}, 'key-approve-1')
    assert reused.status_code == 422 and reused.json()['code'] == 'IDEMPOTENCY_KEY_REUSED'
    assert store.counts()['card_decisions'] == 1 and store.history('card', catalog.get(FIXTURE).ref) == [entry]
    # A restart reads the same store.
    reopened = TestClient(create_app(catalog=catalog, store=DecisionStore(store.path), static_dir=tmp/'none'))
    assert reopened.get(f'/api/runs/{FIXTURE}/decisions').json()['decisions'] == [entry]


def test_concurrent_duplicates_create_one_decision(env, catalog):
    client, store, *_ = env
    card = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'audio_multimodal')
    body = {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING'}
    with ThreadPoolExecutor(8) as pool:
        replies = list(pool.map(lambda _: post(client, SMOKE, card['card_id'], body, 'key-concurrent'), range(8)))
    assert sorted(r.status_code for r in replies) == [200] * 7 + [201]
    assert len({r.json()['entry']['entry_id'] for r in replies}) == 1 and store.counts()['card_decisions'] == 1
    entry = replies[0].json()['entry']
    # The card's own engineering draft is reused as model-grounded text.
    assert entry['text']['origin'] == 'MODEL_GROUNDED' and entry['decision']['tl_response']['approved_actions'] == ['ESCALATE_ENGINEERING']


def test_stale_edit_conflicts_and_a_new_decision_supersedes(env, catalog):
    client, store, clock, _ = env
    card = card_named(catalog, FIXTURE, '[Test fixture] Format adherence vs factual accuracy')
    first = post(client, FIXTURE, card['card_id'], {'kind': 'DISMISS', 'actor_id': 'U001', 'note': 'Covered elsewhere.'}, 'key-s1')
    assert first.status_code == 201
    stale = post(client, FIXTURE, card['card_id'], {'kind': 'CONFIRM_ANNOUNCEMENT', 'actor_id': 'U006'}, 'key-s2')
    assert stale.status_code == 409 and stale.json()['current_head']['entry_id'] == first.json()['entry']['entry_id']
    clock.value = '2026-10-30T16:00:00Z'
    head = first.json()['entry']['entry_id']
    second = post(client, FIXTURE, card['card_id'], {'kind': 'CONFIRM_ANNOUNCEMENT', 'actor_id': 'U006', 'expected_head': head}, 'key-s3')
    assert second.status_code == 201
    e = second.json()['entry']
    assert (e['sequence'], e['supersedes_entry_id']) == (2, head)
    assert [x['entry_id'] for x in store.history('card', catalog.get(FIXTURE).ref, card['card_id'])] == [head, e['entry_id']]


def test_each_structured_resolution(env, catalog):
    client, store, *_ = env
    faq = next(c for c in catalog.get(OFFLINE_V2).cards.values()
               if (c['recommended_action'] or {}).get('action_type') == 'UPDATE_FAQ')
    edited = faq['recommended_action']['draft_text'] + ' (Checked by the team lead.)'
    r = post(client, OFFLINE_V2, faq['card_id'], {'kind': 'CONFIRM_FAQ_UPDATE', 'actor_id': 'U006', 'text': edited}, 'key-r1').json()['entry']
    assert (r['text']['origin'], r['text']['tl_text'], r['decision']['tl_response']['outcome']) == ('TL_EDITED', edited, 'APPROVED_WITH_EDITS')
    assert r['decision']['original_advice']['proposed_text'] == faq['recommended_action']['draft_text']

    korean = card_named(catalog, OFFLINE_V2, 'Korean honorific level inconsistency QA')
    r = post(client, OFFLINE_V2, korean['card_id'], {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U001', 'expert': 'LANGUAGE_SPECIALIST'}, 'key-r2').json()['entry']
    assert r['text']['origin'] == 'MODEL_GROUNDED' and r['decision']['tl_response']['approved_actions'] == ['ROUTE_TO_LANGUAGE_SPECIALIST']

    submit = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'response_preference')
    assert submit['severity']['level'] == 'HIGH'
    r = post(client, SMOKE, submit['card_id'], {'kind': 'OVERRIDE_SEVERITY', 'actor_id': 'U006', 'severity': 'MEDIUM',
                                                'note': 'Workaround available for this batch.'}, 'key-r3').json()['entry']
    assert r['decision']['tl_response']['severity_override'] == {'proposed': 'HIGH', 'tl_selected': 'MEDIUM',
                                                                 'reason': 'Workaround available for this batch.'}
    assert r['decision']['tl_response']['outcome'] == 'OVERRIDDEN' and r['severity_override_is_not_rubric_change'] is True

    gap = next(c for c in catalog.get(OFFLINE_V2).cards.values() if c['recommended_action'] is None)
    r = post(client, OFFLINE_V2, gap['card_id'], {'kind': 'CONFIRM_ANNOUNCEMENT', 'actor_id': 'U006',
                                                  'text': 'Please keep examples in the batch thread.'}, 'key-r4').json()['entry']
    assert (r['text']['origin'], r['decision']['tl_response']['approved_actions']) == ('TL_WRITTEN', ['POST_ALIGNMENT'])
    r = post(client, OFFLINE_V1, gap['card_id'] if gap['card_id'] in catalog.get(OFFLINE_V1).cards else
             next(iter(catalog.get(OFFLINE_V1).cards)), {'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'Duplicate of another card.'},
             'key-r5').json()['entry']
    assert (r['decision']['tl_response']['outcome'], r['decision']['tl_response']['approved_actions']) == ('REJECTED', [])
    assert r['decision']['outcome']['state'] == 'NOT_OBSERVED'  # A disposition is not an observed resolution.

    alt_card = card_named(catalog, FIXTURE, '[Test fixture] Format adherence vs factual accuracy')
    r = post(client, FIXTURE, alt_card['card_id'], {'kind': 'CONFIRM_FAQ_UPDATE', 'actor_id': 'U006', 'alternative_id': 'faq_entry'},
             'key-r6').json()['entry']
    assert (r['text']['origin'], r['text']['grounded_source']) == ('MODEL_GROUNDED', 'SUPPORTED_ALTERNATIVE')
    assert r['decision']['original_advice']['proposed_action'] == 'UPDATE_FAQ'
    assert store.counts()['card_decisions'] == 6


@pytest.mark.parametrize('body, message', [
    ({'kind': 'APPROVE_ACTION', 'actor_id': 'U006'}, 'does not apply to a NEEDS_REVIEW card'),
    ({'kind': 'OVERRIDE_SEVERITY', 'actor_id': 'U006', 'severity': 'MEDIUM', 'note': 'x'}, 'different from the assessed MEDIUM'),
    ({'kind': 'DISMISS', 'actor_id': 'U006'}, 'Give the reason'),
    ({'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'x', 'text': 'y'}, 'carries no draft text'),
    ({'kind': 'DISMISS', 'actor_id': 'U019', 'note': 'x'}, 'not a recorded team lead'),
    ({'kind': 'CONFIRM_ANNOUNCEMENT', 'actor_id': 'U006', 'alternative_id': 'faq_entry'}, 'different action'),
    ({'kind': 'CONFIRM_FAQ_UPDATE', 'actor_id': 'U006', 'alternative_id': 'nope'}, 'not a supported alternative'),
    ({'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006'}, 'Choose the expert'),
])
def test_invalid_requests_are_refused_without_a_row(env, catalog, body, message):
    client, store, *_ = env
    card = card_named(catalog, FIXTURE, '[Test fixture] Format adherence vs factual accuracy')
    reply = post(client, FIXTURE, card['card_id'], body, 'key-invalid')
    assert reply.status_code == 422 and message in reply.json()['detail'], reply.json()
    assert store.counts() == {'requests': 0, 'card_decisions': 0, 'review_actions': 0, 'indexing': 0}


def test_observations_and_missing_keys_are_refused(env, catalog):
    client, *_ = env
    obs = card_named(catalog, FIXTURE, '[Test fixture] Repeated final line in exported audio')
    assert post(client, FIXTURE, obs['card_id'], {'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'x'}, 'key-obs').status_code == 422
    r = client.post(f"/api/runs/{FIXTURE}/cards/{obs['card_id']}/decisions", json={'kind': 'DISMISS', 'actor_id': 'U006'})
    assert r.status_code == 428


def test_model_review_actions_change_only_review_records(env, catalog):
    client, store, *_ = env
    before = tree_hash(RUN_DIRS)
    cards_before = client.get(f'/api/runs/{SMOKE}/brief').json()['cards']
    items = client.get(f'/api/runs/{SMOKE}/review-queue').json()['items']
    a, b, c = (i['item']['item_id'] for i in items[:3])
    act = lambda item, action, key, head=None: client.post(f'/api/runs/{SMOKE}/review-items/{item}/actions', headers={'Idempotency-Key': f'test-{key}'},
                                                          json={'action': action, 'actor_id': 'U001', 'expected_head': head})
    assert act(a, 'ACCEPT', 'key-m1').json()['entry']['effect'] == 'RESOLVED_FOR_RUN'
    assert act(b, 'REJECT', 'key-m2').json()['entry']['effect'] == 'NEGATIVE_EXAMPLE'
    deferred = act(c, 'DEFER', 'key-m3').json()['entry']
    assert act(a, 'ACCEPT', 'key-m1').json()['replayed']
    assert act(c, 'ACCEPT', 'key-m4').status_code == 409  # Stale: the DEFER is now the head.
    states = {i['item']['item_id']: i['review_state'] for i in client.get(f'/api/runs/{SMOKE}/review-queue').json()['items']}
    assert (states[a], states[b], states[c]) == ('ACCEPTED', 'REJECTED', 'OPEN')
    assert act(c, 'ACCEPT', 'key-m5', deferred['entry_id']).status_code == 201
    negatives = client.get(f'/api/runs/{SMOKE}/negative-examples').json()['items']
    assert [n['item']['item_id'] for n in negatives] == [b] and negatives[0]['item']['source_obligation']
    # Review actions are run-scoped: the same item in another run is untouched.
    assert all(i['review_state'] == 'OPEN' for i in client.get(f'/api/runs/{OFFLINE_V2}/review-queue').json()['items'])
    assert client.get(f'/api/runs/{SMOKE}/brief').json()['cards'] == cards_before
    assert store.counts()['card_decisions'] == 0 and tree_hash(RUN_DIRS) == before


def test_decisions_round_trip_through_the_canonical_ingestion_path(env, catalog):
    client, store, *_ = env
    card = card_named(catalog, FIXTURE, '[Test fixture] Fictional phone number quarantine handling')
    entry = post(client, FIXTURE, card['card_id'], {'kind': 'APPROVE_ACTION', 'actor_id': 'U006', 'text': 'Edited reminder.'},
                 'key-rt').json()['entry']
    record = markdown_text_source(decision_markdown(entry))
    assert (record.document_type, record.scope, record.source.project_id) == ('decision', 'project', card['project_id'])
    parsed = decision_record_from_source(record)
    assert parsed.model_dump(exclude={'source'}) == {k: v for k, v in entry['decision'].items() if k != 'source'}
    assert parsed.tl_response.outcome == 'APPROVED_WITH_EDITS' and parsed.tl_response.text == 'Edited reminder.'
    doc = ingest(entry)
    assert store.indexing()[entry['entry_id']]['status'] == 'PENDING'
    assert (store.indexing()[entry['entry_id']]['document_id'], store.indexing()[entry['entry_id']]['version_id']) == \
           (doc['document_id'], doc['version_id'])
    assert 'TL-edited text' in doc['text'] and 'not model-grounded' in doc['text'] and 'not executed' in doc['text']


NOW = '2026-10-31T12:00:00Z'  # Test clock for snapshot builds (a snapshot cutoff may not be in the future).


def test_later_snapshot_finds_saved_decisions_without_backdating(env, catalog, monkeypatch):
    client, store, clock, tmp = env
    card = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'audio_multimodal')
    first = post(client, SMOKE, card['card_id'], {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING'},
                 'key-ix1').json()['entry']
    assert (first['namespace'], first['judgment_provenance']) == ('operational', 'LIVE_MODEL')
    encoder, exports = HashEncoder(), tmp/'exports'
    build = lambda name, **kw: build_snapshot(store, tmp/name, encoder=encoder, export_dir=exports, now=NOW, **kw)
    with pytest.raises(ValueError, match='active retrieval index'):
        build_snapshot(store, INDEX_DIR, cutoff=NOW, encoder=encoder, export_dir=exports, now=NOW)
    with pytest.raises(ValueError, match='in the future'):
        build('snap_future', cutoff='2026-11-01T00:00:00Z')
    # A failed build records the failure; the decision is unchanged and indexes later.
    from threadsense.retrieval import index as index_module
    monkeypatch.setattr(index_module, 'build_index', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):
        build('snap_fail', cutoff=NOW)
    assert store.indexing()[first['entry_id']]['status'] == 'FAILED'
    assert store.history('card', catalog.get(SMOKE).ref) == [first]
    monkeypatch.undo()
    # The October 2 snapshot cannot contain a decision saved on October 30.
    early = build('snap_oct02', cutoff='2026-10-02T12:00:00Z')
    assert early['decisions_after_cutoff'] == [first['entry_id']] and early['decisions_indexed'] == 0
    later = build('snap_oct31', cutoff=NOW)
    assert later['decisions_indexed'] == 1 and store.indexing()[first['entry_id']]['status'] == 'INDEXED'
    retriever = Retriever(tmp/'snap_oct31', encoder=encoder)
    hits = [r for r in retriever.search('team lead routed playback failure to engineering', card['project_id'], top_k=20)['results']
            if r['metadata']['origin'] == 'tl_decision_store']
    assert hits and hits[0]['metadata']['decision_status'] == 'tl_approved'
    assert (hits[0]['metadata']['execution_status'], hits[0]['metadata']['outcome_status']) == ('not_executed', 'not_observed')
    assert hits[0]['collection'] == 'decisions' and hits[0]['metadata']['document_type'] == 'decision'  # Never guidance.
    assert {'namespace-operational', 'judgment-live-model'} <= set(hits[0]['metadata']['tags'])  # Provenance survives.
    from threadsense.agents.advisor_evidence import use_of
    assert use_of(hits[0]) == 'PRIOR_DECISION'  # History, not a standing rule.
    # Rebuilding with the same decisions is a no-op; nothing is duplicated.
    again = build('snap_oct31', cutoff=NOW)
    assert again['status'] == 'UP_TO_DATE' and again['exports'] == {'written': 0, 'unchanged': 1}
    # A newer disposition on the same card is a separate record in the same event series; the earlier one stays.
    clock.value = '2026-10-31T09:00:00Z'
    second = post(client, SMOKE, card['card_id'], {'kind': 'DISMISS', 'actor_id': 'U001', 'note': 'Engineering already has it.',
                                                   'expected_head': first['entry_id']}, 'key-ix2').json()['entry']
    final = build('snap_oct31b', cutoff=NOW)
    assert final['decisions_indexed'] == 2
    found = Retriever(tmp/'snap_oct31b', encoder=encoder).search('team lead decision playback engineering', card['project_id'], top_k=30)
    records = {r['document_id']: r['metadata'] for r in found['results'] if r['metadata']['origin'] == 'tl_decision_store'}
    assert {m['decision_status'] for m in records.values()} == {'tl_approved', 'tl_rejected'}
    assert len({m['event_series_id'] for m in records.values()}) == 1 and not found['withheld_by_version']
    assert second['sequence'] == 2 and second['decision']['event_series_id'] == first['decision']['event_series_id']


def test_test_and_demo_decisions_stay_out_of_default_snapshots(env, catalog):
    client, store, clock, tmp = env
    fixture_card = card_named(catalog, FIXTURE, '[Test fixture] Fictional phone number quarantine handling')
    scripted_card = next(c for c in catalog.get(OFFLINE_V2).cards.values()
                         if (c['recommended_action'] or {}).get('action_type') == 'ROUTE_TO_LANGUAGE_SPECIALIST')
    test_entry = post(client, FIXTURE, fixture_card['card_id'], {'kind': 'APPROVE_ACTION', 'actor_id': 'U006'}, 'key-ns1').json()['entry']
    demo_entry = post(client, OFFLINE_V2, scripted_card['card_id'], {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006',
                                                                    'expert': 'LANGUAGE_SPECIALIST'}, 'key-ns2').json()['entry']
    assert (test_entry['namespace'], test_entry['judgment_provenance']) == ('test', 'TEST_FIXTURE')
    assert (demo_entry['namespace'], demo_entry['judgment_provenance']) == ('demo', 'SCRIPTED_PILOT')
    encoder, exports = HashEncoder(), tmp/'exports'
    default = build_snapshot(store, tmp/'snap_default', cutoff=NOW, encoder=encoder, export_dir=exports, now=NOW)
    assert default['decisions_indexed'] == 0
    assert sorted(default['decisions_excluded_by_namespace']) == sorted([test_entry['entry_id'], demo_entry['entry_id']])
    documents = json.loads((tmp/'snap_default'/'documents.json').read_text(encoding='utf-8'))
    # The authored demo corpus is synthetic and stays in: only UI test data and scripted-run decisions are excluded.
    assert sum((d['metadata']['source_metadata'].get('authoring') or {}).get('synthetic') is True for d in documents.values()) >= 30
    assert not any(d['origin'] == 'tl_decision_store' for d in documents.values())
    opted = build_snapshot(store, tmp/'snap_test', cutoff=NOW, encoder=encoder, export_dir=exports, now=NOW, namespaces=('test',))
    assert opted['decisions_indexed'] == 1 and opted['decisions_excluded_by_namespace'] == [demo_entry['entry_id']]
    exported = sorted(p.relative_to(exports).parts[0] for p in exports.rglob('*.md'))
    assert exported == ['demo', 'test']


def test_runs_sharing_run_id_and_card_id_stay_isolated(tmp_path):
    import shutil
    roots = tmp_path/'runs'
    for name in ('instance_a', 'instance_b'):
        shutil.copytree(FIXTURE_RUN_ROOT/FIXTURE, roots/name)
    catalog = Catalog([roots])
    a, b = catalog.get('instance_a'), catalog.get('instance_b')
    assert a.brief['run_id'] == b.brief['run_id'] and set(a.cards) == set(b.cards) and a.ref != b.ref
    store = DecisionStore(tmp_path/'store.sqlite3')
    app = lambda c: TestClient(create_app(catalog=c, store=DecisionStore(store.path), clock=Clock(), static_dir=tmp_path/'none'))
    client = app(catalog)
    card_id = next(cid for cid, c in a.cards.items() if c['card_line'] == 'RECOMMENDED_ACTION')
    item_id = next(iter(a.queue))
    assert post(client, 'instance_a', card_id, {'kind': 'APPROVE_ACTION', 'actor_id': 'U006'}, 'key-iso1').status_code == 201
    assert client.post(f'/api/runs/instance_a/review-items/{item_id}/actions', headers={'Idempotency-Key': 'test-key-iso2'},
                       json={'action': 'REJECT', 'actor_id': 'U006'}).status_code == 201
    for c in (client, app(Catalog([roots]))):  # Before and after a restart.
        assert len(c.get('/api/runs/instance_a/decisions').json()['decisions']) == 1
        assert c.get('/api/runs/instance_b/decisions').json()['decisions'] == []
        states = {i['item']['item_id']: i['review_state'] for i in c.get('/api/runs/instance_b/review-queue').json()['items']}
        assert set(states.values()) == {'OPEN'}
        assert not next(x for x in c.get('/api/runs/instance_b/brief').json()['cards'] if x['card']['card_id'] == card_id)['resolved']
    # The same card in the other instance is decided independently (its own sequence 1); instance_a is unchanged.
    other = post(client, 'instance_b', card_id, {'kind': 'APPROVE_ACTION', 'actor_id': 'U001'}, 'key-iso3').json()['entry']
    assert other['sequence'] == 1 and other['run_instance'] == b.instance
    assert [e['actor_id'] for e in client.get('/api/runs/instance_a/decisions').json()['decisions']] == ['U006']
    # Replacing a directory's files makes a new instance: earlier rows are not shown as its decisions.
    queue = roots/'instance_a'/'review_queue.json'
    queue.write_text(queue.read_text(encoding='utf-8').replace('"origin"', ' "origin"', 1), encoding='utf-8')
    changed = app(Catalog([roots]))
    reply = changed.get('/api/runs/instance_a/decisions').json()
    assert reply['decisions'] == [] and reply['rows_for_other_instances'] == 2


def test_later_snapshot_keeps_earlier_announcements_with_their_applicability(tmp_path):
    from threadsense.agents.advisor_evidence import banner, use_of
    from threadsense.retrieval.index import build_index
    encoder = HashEncoder()
    later = build_index(tmp_path/'oct31', encoder=encoder, cutoff=NOW)
    window = later['corpus']['current_day_announcements']
    assert window['extracted'] == 0 and window['prior_announcements']['extracted'] == 23
    retriever = Retriever(tmp_path/'oct31', encoder=encoder)
    found = retriever.search('player never loads playback failure examples', 'audio_multimodal', top_k=10,
                             document_types=['announcement'])['results']
    prior = [r for r in found if r['metadata']['origin'] == 'prior_announcement']
    assert prior and not any(r['metadata']['origin'] == 'current_day_extraction' for r in found)
    # Leaving the 24-hour intake window is not expiry or supersession: the announcement keeps the use it had when it
    # was current-day (ANNOUNCEMENT: handling only once shown relevant and directive), with its collection labelled.
    assert all(use_of(r) == 'ANNOUNCEMENT' for r in prior)
    assert "collected before this run's 24-hour window" in banner(prior[0], 'ANNOUNCEMENT')
    # Same canonical identity and version as when the announcement was current-day; never duplicated.
    oct02 = build_index(tmp_path/'oct02', encoder=encoder)
    docs02 = json.loads((tmp_path/'oct02'/'documents.json').read_text(encoding='utf-8'))
    docs31 = json.loads((tmp_path/'oct31'/'documents.json').read_text(encoding='utf-8'))
    current02 = {k for k, d in docs02.items() if d['origin'] == 'current_day_extraction'}
    prior31 = {k for k, d in docs31.items() if d['origin'] == 'prior_announcement'}
    assert current02 == prior31 and len(prior31) == 23
    assert oct02['corpus']['current_day_announcements']['prior_announcements']['extracted'] == 0
    same02 = Retriever(tmp_path/'oct02', encoder=encoder).search('player never loads playback failure examples', 'audio_multimodal',
                                                                 top_k=10, document_types=['announcement'])['results']
    uses02 = {r['document_id']: use_of(r) for r in same02 if r['metadata']['origin'] == 'current_day_extraction'}
    assert all(uses02[r['document_id']] == use_of(r) for r in prior if r['document_id'] in uses02)


def test_plan_without_decisions_keeps_the_existing_fingerprint_inputs():
    from threadsense.retrieval.index import plan
    _, _, corpus, core = plan(HashEncoder())
    manifest = json.loads((INDEX_DIR/'manifest.json').read_text(encoding='utf-8'))
    assert 'decision_roots' not in core and 'tl_decisions' not in corpus
    assert core['corpus_fingerprint'] == manifest['corpus_fingerprint']  # The active snapshot stays current.


def test_api_never_writes_run_artifacts_or_corpus(env, catalog):
    client, *_ = env
    before = tree_hash([*RUN_DIRS, ROOT/'data/knowledge'])
    for run in (SMOKE, OFFLINE_V2, FIXTURE):
        brief = client.get(f'/api/runs/{run}/brief').json()
        for c in brief['cards'][:3]:
            client.get(f"/api/runs/{run}/cards/{c['card']['card_id']}")
    card = card_named(catalog, FIXTURE, '[Test fixture] Fictional phone number quarantine handling')
    post(client, FIXTURE, card['card_id'], {'kind': 'APPROVE_ACTION', 'actor_id': 'U006'}, 'key-w1')
    assert tree_hash([*RUN_DIRS, ROOT/'data/knowledge']) == before
    assert decision_sources.EXPORT_DIR.resolve().is_relative_to(ROOT/'.state')


def test_simulated_decisions_on_live_cards_stay_out_of_operational_snapshots(tmp_path, catalog):
    """A demo script's approval keeps the card's LIVE_MODEL judgment provenance but is demo data, not operational."""
    store = DecisionStore(tmp_path/'store.sqlite3')
    client = TestClient(create_app(catalog=catalog, store=store, clock=Clock(), static_dir=tmp_path/'none',
                                   decision_origin='DEMO_SCRIPT'))
    card = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'audio_multimodal')
    entry = post(client, SMOKE, card['card_id'], {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING'},
                 'key-demo1').json()['entry']
    assert (entry['decision_origin'], entry['namespace'], entry['judgment_provenance']) == ('DEMO_SCRIPT', 'demo', 'LIVE_MODEL')
    built = build_snapshot(store, tmp_path/'snap', cutoff=NOW, encoder=HashEncoder(), export_dir=tmp_path/'exports', now=NOW)
    assert built['decisions_indexed'] == 0 and built['decisions_excluded_by_namespace'] == [entry['entry_id']]
    from threadsense.knowledge_markdown import markdown_text_source
    authoring = markdown_text_source(decision_markdown(entry)).source_metadata['authoring']
    assert (authoring['decision_origin'], authoring['namespace'], authoring['judgment_provenance']) == ('DEMO_SCRIPT', 'demo', 'LIVE_MODEL')


def test_approved_unexecuted_decisions_are_history_not_policy(env, catalog):
    client, store, clock, tmp = env
    card = next(c for c in catalog.get(SMOKE).cards.values() if c['project_id'] == 'audio_multimodal')
    post(client, SMOKE, card['card_id'], {'kind': 'ROUTE_TO_EXPERT', 'actor_id': 'U006', 'expert': 'ENGINEERING'}, 'key-pol1')
    build_snapshot(store, tmp/'snap', cutoff=NOW, encoder=HashEncoder(), export_dir=tmp/'exports', now=NOW)
    from threadsense.agents.advisor_evidence import banner, use_of
    hits = [r for r in Retriever(tmp/'snap', encoder=HashEncoder()).search('engineering playback decision', 'audio_multimodal',
                                                                           top_k=30)['results'] if r['metadata']['origin'] == 'tl_decision_store']
    assert hits and {use_of(r) for r in hits} == {'PRIOR_DECISION'} and hits[0]['collection'] == 'decisions'
    assert 'execution_status: not_executed' in banner(hits[0], 'PRIOR_DECISION') and 'not a standing rule' in banner(hits[0], 'PRIOR_DECISION')
