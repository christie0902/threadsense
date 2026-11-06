"""The restored responsibilities end to end, offline: Agent 3 on a consolidated handoff with processing history, shared
actions, the cached derived run, and the v1/v2 pipeline split. No model calls (scripted placeholder, test-double index,
prepared decisions)."""
from copy import deepcopy
import json
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.agents import action_coordination as ac
from threadsense.agents import overnight, topic_merge as tm
from threadsense.agents.advice_contracts import validate_card
from threadsense.agents.advice_inputs import load_effective_view
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.execution import pipeline as p
from threadsense.retrieval.index import build_index
from threadsense.retrieval.search import Retriever
from threadsense.routing import ROOT
from tests.retrieval_doubles import HashEncoder
from tests.test_agent3_overnight import Placeholder

FULL = ROOT/'data/experiments/threadsense_full_v1'
STAGES = FULL/'stages'
CARDS = ROOT/'data/experiments/threadsense_full_v1_briefing_v2'
DERIVED = ROOT/'data/experiments/threadsense_full_v1_consolidated_v1'
DECISIONS = json.loads((ROOT/'data/evaluation/agent2_consolidation_decisions_v1.json').read_text(encoding='utf-8'))
FICTIONAL = {'cluster_9378eb54bc546fcd/topic_1', 'cluster_d9ad05f5bda622e1/topic_1'}
pytestmark = pytest.mark.skipif(not FULL.is_dir(), reason='full live run not present')


def topic_results():
    return [json.loads(f.read_text(encoding='utf-8'))['result'] for f in sorted((STAGES/'agent3'/'overnight_run'/'topics').glob('*.json'))]


# --- Agent 3 on a consolidated handoff ----------------------------------------------------------------------------

@pytest.fixture(scope='module')
def consolidated_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('v2')
    view = load_effective_view(STAGES/'agent2'/'agent2_v1')
    history_groups = {'cluster_be4e3bac742eccb3', 'cluster_c9bdba359e6e7cd2', 'cluster_024655fb52cc3352'}
    history = [{'member_id': m['member_id'], **{k: m[k] for k in ('project_id', 'batch_id', 'channel_id', 'thread_id')},
                'relevance': 'SOCIAL_ONLY', 'basis': 'test', 'agent1_record': m['agent1_record']}
               for r in view['records'] if r['candidate_group_id'] in history_groups for m in r['members']]
    flagged = deepcopy(history[0])  # a flagged thread in processing history: its obligation must reach the queue
    flagged.update(member_id='member_flagged_history', thread_id='1790000000.000001',
                   agent1_record={**flagged['agent1_record'], 'review_required': True, 'review_reason': 'test obligation'})
    history.append(flagged)
    v2 = {**view, 'records': [r for r in view['records'] if r['candidate_group_id'] not in history_groups]}
    vectors = tm.member_vectors(STAGES/'agent1_verify'/'agent1_verified_v2'/'interpretations.json', STAGES/'grouping'/'grouping_v1')
    record = tm.consolidate(tm.topics_of(v2, vectors), tm.PreparedJudge(DECISIONS))
    (tmp/'consolidation.json').write_text(json.dumps(record), encoding='utf-8')
    (tmp/'history.json').write_text(json.dumps(history), encoding='utf-8')
    index = tmp/'index'
    build_index(index, encoder=HashEncoder())
    retriever = Retriever(index, encoder=HashEncoder())
    fictional = next(m['consolidated_topic_id'] for m in record['merges'] if set(m['source_topic_ids']) == FICTIONAL)
    rt = overnight.Runtime(tmp/'run', client=Placeholder(), cutoff='2026-10-02T12:00:00Z', retriever_factory=lambda: retriever,
                           handoff=STAGES/'agent2'/'agent2_v1', fixture_root=FULL/'snapshot'/'slack',
                           consolidation=tmp/'consolidation.json', processing_history=tmp/'history.json',
                           only=[f'consolidated:{fictional}', 'topic:cluster_aa0548b34bd2cbdc/topic_1'])
    original = overnight.load_effective_view
    overnight.load_effective_view = lambda handoff: v2  # the v2 handoff never contained the processing-history threads
    try:
        overnight.run(rt)
    finally:
        overnight.load_effective_view = original
    return rt, record, history


def test_agent3_advises_a_consolidated_issue_as_one_card(consolidated_run):
    rt, record, _ = consolidated_run
    brief = json.loads((rt.out/'morning_brief.json').read_text(encoding='utf-8'))
    cards = json.loads((rt.out/'cards.json').read_text(encoding='utf-8'))
    card = next(c for c in cards if c['lineage']['handoff_contract'] == 'agent2-taxonomy-handoff-v3')
    validate_card(card)
    merge = next(m for m in record['merges'] if m['consolidated_topic_id'] == card['lineage']['topic_id'])
    assert set(card['lineage']['source_topic_ids']) == FICTIONAL and len(card['lineage']['candidate_group_ids']) == 2
    assert sorted(card['lineage']['member_ids']) == merge['member_ids'] and len(card['related_threads']) == 6
    flagged = {m for f in card['inherited_flags'] for m in f['member_ids'] if f['origin'] == 'agent1'}
    assert flagged == set(merge['flagged_member_ids'])  # flags from both source groups
    assert brief['counts']['consolidated_topics'] == 14 and brief['consolidation']['counts']['merges'] == 14


def test_processing_history_is_its_own_inventory_with_obligations(consolidated_run):
    rt, _, history = consolidated_run
    accounting = json.loads((rt.out/'accounting.json').read_text(encoding='utf-8'))
    queue = json.loads((rt.out/'review_queue.json').read_text(encoding='utf-8'))
    assert accounting['status'] == 'COMPLETE', accounting['issues']
    assert sorted(h['member_id'] for h in accounting['processing_history']) == sorted(h['member_id'] for h in history)
    assert accounting['counts']['processing_history_obligations'] == 1
    assert [q['member_ids'] for q in queue if q['kind'] == 'inherited_agent1_review_processing_history'] == [['member_flagged_history']]
    text = (rt.out/'morning_brief.md').read_text(encoding='utf-8')
    assert '## Processing history' in text and '## Consolidated topics' in text


# --- Shared actions -------------------------------------------------------------------------------------------------

def test_the_duplicate_contact_details_edit_is_one_shared_action_with_review_reasons_kept():
    shared = ac.coordinate(ac.entries_from_results(topic_results()))
    (action,) = shared['coordinated_actions']
    assert action['targets'] == [{'document': 'safety-qn-help-page@1.0', 'section': 'Contact details', 'change': 'CORRECT'}]
    assert {c['topic_id'] for c in action['cards']} == FICTIONAL and action['shared_cause'] is False
    assert {c['topic_name']: c['review_codes'] for c in action['cards']} == {
        'QN handling for fictional phone numbers': ['GROUNDING_FAILURE', 'INHERITED_FLAG'],
        'Fictional placeholder contact details and QN handling': ['INHERITED_FLAG']}
    assert [w['topic_name'] for w in action['related_withheld']] == ['Conflicting QN guidance sources']


def test_similar_wording_alone_never_coordinates_actions():
    results = topic_results()
    entries = ac.entries_from_results(results)
    contact = [e for e in entries if e['card']['lineage']['topic_id'] in FICTIONAL]
    other_section = deepcopy(contact[1])
    other_section['proposal']['targets'] = [{**t, 'section': 'Minors'} for t in other_section['proposal']['targets']]
    assert not ac.coordinate([contact[0], other_section])['coordinated_actions']
    withheld = deepcopy(contact[1])
    withheld['card']['next_step'] = {**withheld['card']['next_step'], 'status': 'RECOMMENDATION_WITHHELD'}
    assert not ac.coordinate([contact[0], withheld])['coordinated_actions']
    no_target = [{**e, 'proposal': {**e['proposal'], 'targets': []}} for e in contact]
    assert not ac.coordinate(no_target)['coordinated_actions']
    same_topic = deepcopy(contact[1])
    same_topic['card']['lineage']['topic_id'] = contact[0]['card']['lineage']['topic_id']
    assert not ac.coordinate([contact[0], same_topic])['coordinated_actions']


# --- The cached derived run ---------------------------------------------------------------------------------------

needs_derived = pytest.mark.skipif(not DERIVED.is_dir(), reason='derived run not written')


@needs_derived
def test_every_thread_and_obligation_is_in_exactly_one_inventory():
    d = json.loads((DERIVED/'derivation.json').read_text(encoding='utf-8'))
    members = [m for r in d['inventory'] if r['inventory'] == 'BRIEF' for m in r['member_ids']]
    members += [m for x in d['consolidated_pending'] for m in x['member_ids']] + [h['member_id'] for h in d['processing_history']]
    assert len(members) == len(set(members)) == 177
    parent_queue = json.loads((CARDS/'review_queue.json').read_text(encoding='utf-8'))
    assert json.loads((DERIVED/'review_queue.json').read_text(encoding='utf-8')) == parent_queue and len(parent_queue) == 37
    assert d['summary']['after'] == {**d['summary']['after'], 'briefing_items': 63, 'reused_cards_in_brief': 49,
                                     'consolidated_issues_pending': 14, 'processing_history_threads': 3}
    assert d['model_calls'] == 0 and d['summary']['grouping']['unchanged'] is True


@needs_derived
def test_cards_are_reused_byte_for_byte_and_merged_advice_stays_attributed():
    assert (DERIVED/'cards.json').read_bytes() == (CARDS/'cards.json').read_bytes()
    d = json.loads((DERIVED/'derivation.json').read_text(encoding='utf-8'))
    pending = {x['consolidated_topic_id']: x for x in d['consolidated_pending']}
    for row in d['inventory']:
        if row['inventory'] == 'CONSOLIDATED_PENDING':
            assert row['card_id'] in {c['card_id'] for c in pending[row['consolidated_topic_id']]['source_cards']}
    assert all(x['status'] == 'PENDING_FRESH_GROUNDING' and x['judgment_provenance'] == 'PREPARED_AUDIT' for x in pending.values())
    fictional = next(x for x in pending.values() if set(x['source_topic_ids']) == FICTIONAL)
    assert fictional['review_codes_carried'] == ['GROUNDING_FAILURE', 'INHERITED_FLAG'] and fictional['open_subquestions']


@needs_derived
def test_the_derived_run_loads_with_its_own_decisions_and_inventories(tmp_path):
    for name, src in (('cards', CARDS), ('derived', DERIVED)):
        shutil.copytree(src, tmp_path/name/src.name)
    client = TestClient(create_app(catalog=Catalog([tmp_path/'cards', tmp_path/'derived']), store=DecisionStore(tmp_path/'d.sqlite3'),
                                   session_actor='U006'))
    brief = client.get(f'/api/runs/{DERIVED.name}/brief').json()
    by_inventory = {}
    for c in brief['cards']:
        by_inventory.setdefault(c['presentation']['inventory'], []).append(c)
    assert {k: len(v) for k, v in by_inventory.items()} == {'BRIEF': 49, 'CONSOLIDATED_PENDING': 29, 'PROCESSING_HISTORY': 3}
    phone = next(c for c in brief['cards'] if c['card']['topic_name'] == 'QN handling for fictional phone numbers')
    assert phone['presentation']['consolidated']['topic_name'] == 'QN handling for fictional contact details'
    assert phone['presentation']['shared_actions'][0]['other_cards'][0]['topic_name'] == 'Fictional placeholder contact details and QN handling'
    card_id = phone['card']['card_id']  # same card version in both runs; decisions still bind to each run instance
    saved = client.post(f'/api/runs/{CARDS.name}/cards/{card_id}/decisions', json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 't'},
                        headers={'Idempotency-Key': 'consolidated-0001'})
    assert saved.status_code in (200, 201), saved.text
    assert client.get(f'/api/runs/{DERIVED.name}/decisions').json()['decisions'] == []
    assert Run(tmp_path/'derived'/DERIVED.name).ref != Run(tmp_path/'cards'/CARDS.name).ref


# --- Pipeline versions ------------------------------------------------------------------------------------------

def test_v1_runs_keep_their_stages_and_configuration(tmp_path, monkeypatch):
    from threadsense.execution.guard import Execution
    monkeypatch.setattr(p, 'load_script', lambda name: type('M', (), {'live_settings': staticmethod(lambda: {
        k: None for k in ('model', 'reasoning_effort', 'service_tier', 'input_token_limit', 'max_completion_tokens_per_call',
                          'timeout_seconds', 'provider_sdk_max_retries', 'model_fallback')})}))
    monkeypatch.setattr(p, 'tree_hash', lambda *a, **k: 'x')
    monkeypatch.setattr(p, 'file_hash', lambda *a, **k: 'x')
    monkeypatch.setattr(p, 'read_json', lambda path: json.loads(open(path, encoding='utf-8').read()) if 'run_manifest' in str(path)
                        else {'build_fingerprint': 'x'})
    v1, v2 = p.configuration(p.PIPELINE_V1), p.configuration(p.PIPELINE_V2)
    assert 'agent1_relevance' not in v1 and v1['pipeline'] == p.PIPELINE_V1
    assert v2['agent2_consolidation']['version'] == tm.CONSOLIDATION_VERSION and v2['pipeline'] == p.PIPELINE_V2
    old = tmp_path/'old'
    run = p.Run(old, Execution(old, mode='LIVE', limit_usd=1.0))
    assert run.stages == p.STAGES
    new = tmp_path/'new'
    new.mkdir()
    (new/'run_manifest.json').write_text(json.dumps({'configuration': {'pipeline': p.PIPELINE_V2}}), encoding='utf-8')
    assert p.Run(new, Execution(new, mode='LIVE', limit_usd=1.0)).stages == p.STAGES_V2
    saved = json.loads((FULL/'run_manifest.json').read_text(encoding='utf-8'))['configuration']
    assert saved['pipeline'] == p.PIPELINE_V1  # the completed run replays and resumes as v1
