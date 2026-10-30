"""Milestone 5 overnight workflow, offline. Test-double encoder index; semantic stages are scripted (the placeholder
judges nothing) or fakes. DETERMINISTIC unless a test says otherwise; nothing here says anything about model quality.
"""
import json

import pytest

from threadsense.agents import advisor_pilot as pilot
from threadsense.agents import overnight
from threadsense.agents.advice_inputs import load_effective_view, obligation_keys
from threadsense.handoff_inputs import read_json
from threadsense.retrieval.config import FIXTURE_CUTOFF
from threadsense.retrieval.index import build_index
from threadsense.retrieval.search import Retriever
from tests.retrieval_doubles import HashEncoder

ROUTING = read_json(pilot.HANDOFF/'routing_manifest.json')


@pytest.fixture(scope='module')
def retriever(tmp_path_factory):
    index = tmp_path_factory.mktemp('overnight')/'index'
    build_index(index, encoder=HashEncoder())
    return Retriever(index, encoder=HashEncoder())


@pytest.fixture(scope='module')
def view():
    return load_effective_view(pilot.HANDOFF)


def runtime(out, retriever, *, client=None, **kw):
    return overnight.Runtime(out, client=client or Placeholder(), cutoff=FIXTURE_CUTOFF, retriever_factory=lambda: retriever, **kw)


class Placeholder(overnight.HandoffScriptedClient):
    """The scripted placeholder for every topic (pilot judgments cite real-index evidence IDs); counts calls."""

    def __init__(self, interrupt_at=None):
        super().__init__()
        self.calls, self.interrupt_at = [], interrupt_at

    def complete(self, stage, payload, schema):
        self.calls.append((payload['scenario_id'], stage))
        if self.interrupt_at == (payload['scenario_id'], stage):
            raise KeyboardInterrupt('simulated interruption')
        return json.dumps(overnight.placeholder(stage, payload))

    def source(self, work_id):
        return 'SCRIPTED_PLACEHOLDER'


def first_topics(view, n=3):
    return [w['work_id'] for w in overnight.plan(view) if w['kind'] == 'TOPIC'][:n]


@pytest.fixture(scope='module')
def full(retriever, tmp_path_factory):
    out = tmp_path_factory.mktemp('full')/'run'
    rt = runtime(out, retriever)
    state = overnight.run(rt)
    return rt, state, out


def test_full_handoff_offline_accounts_for_every_member_and_obligation(full, view):
    """The complete handoff, offline: one work item per topic and per projection-gap group, a card for each, and a
    disposition for every member, inherited obligation, announcement-route member and obligation and naming caution.
    Expected counts come from the inputs, not from fixed totals."""
    rt, state, out = full
    brief, accounting = read_json(out/'morning_brief.json'), read_json(out/'accounting.json')
    counts = brief['counts']
    members = [m['member_id'] for r in view['records'] for m in r['members']]
    topics = sum(len(r['topics']) for r in view['records'])
    gaps = sum(1 for r in view['records'] if r['unassigned_member_ids'] and any(x.startswith('Projection gap') for x in r['review_reasons']))
    assert accounting['status'] == 'COMPLETE' and accounting['issues'] == []
    assert brief['incomplete_work'] == [], brief['incomplete_work']
    assert sorted(m['member_id'] for m in accounting['members']) == sorted(members)
    assert counts['topics'] == topics and counts['projection_gap_groups'] == gaps and counts['cards'] == topics + gaps
    assert counts['members_on_cards'] == len(members)
    assert counts['inherited_agent1_obligations'] == sum(len(r['inherited_review_obligations']) for r in view['records'])
    assert counts['naming_cautions'] == sum(len(r['content_review_obligations']) for r in view['records'])
    assert counts['announcement_route_members'] == len(ROUTING['announcement_sources'])
    assert counts['announcement_route_obligations'] == sum(m['agent1_record']['review_required'] for m in ROUTING['announcement_sources'])
    queue = read_json(out/'review_queue.json')
    keys = {('agent1', i['member_ids'][0]) if i['origin'] == 'agent1' and i['candidate_group_id'] != 'announcement_route'
            else ('content', i['obligation_id']) if i['origin'] == 'assisted_content_review' else None for i in queue}
    assert obligation_keys(view) <= keys
    assert len(queue) == counts['inherited_agent1_obligations'] + counts['naming_cautions'] + counts['announcement_route_obligations']
    # The Model Review Queue is separate from the cards; cards link back by ID only.
    assert all('card_line' not in i for i in queue) and all(i['related_card_ids'] for i in queue if i['origin'] == 'agent1'
                                                             and i['candidate_group_id'] != 'announcement_route')
    gap_cards = [c for c in brief['cards'] if c['lineage']['topic_id'] is None]
    assert len(gap_cards) == gaps and all('projection gap' in c['topic_name'] for c in gap_cards)  # No taxonomy invented.
    assert brief['semantic_judgments'] == 'SCRIPTED_MOCK' and {c['semantic_source'] for c in brief['cards']} == {'SCRIPTED_PLACEHOLDER'}
    assert brief['status'] == 'COMPLETE' and (out/'morning_brief.md').read_text(encoding='utf-8').startswith('# Morning brief')


def test_announcements_stay_outside_interpretation_and_are_in_the_snapshot(full):
    """Window announcements go through the existing zero-call ingestion with canonical IDs, are found in the retrieval
    snapshot, and are never interpretation work; announcement-route members are not Advisor topics."""
    rt, _, out = full
    brief = read_json(out/'morning_brief.json')
    assert brief['announcement_extraction']['agent1_interpretation_calls'] == 0 and brief['announcement_extraction']['model_calls'] == 0
    assert all(a['in_retrieval_snapshot'] and a['document_id'].startswith('knowledge_') for a in brief['announcements_in_window'])
    route = {m['member_id'] for m in ROUTING['announcement_sources']}
    assert not route & {m for w in rt.work for m in w['member_ids']}


def test_model_calls_happen_only_inside_the_advisor(full):
    """Every model call is an Advisor stage of some topic (draft, revision, ToT, grounding); the graph adds none, and
    the final grounding is each topic's last call."""
    rt, _, _ = full
    stages = [c[1] for c in rt.client.calls]
    assert set(stages) <= {'draft', 'revision', 'tot', 'grounding'}
    per_topic = {}
    for wid, stage in rt.client.calls:
        per_topic.setdefault(wid, []).append(stage)
    assert all(s[-1] == 'grounding' and s.count('grounding') == 1 and s.count('tot') <= 1 for s in per_topic.values())
    assert sum(len(r['result']['model_calls']) for r in rt.results.values()) == len(rt.client.calls)


def test_one_topic_failure_does_not_stop_the_others(retriever, view, tmp_path):
    """A topic whose processing raises is recorded as TOPIC_FAILED with its members and review items; the others still
    get cards and the run accounts for everyone."""
    ids = first_topics(view)

    def advise(scenario, **kw):
        if scenario['id'] == ids[1]:
            raise RuntimeError('simulated pipeline failure')
        return pilot.advise(scenario, **kw)
    rt = runtime(tmp_path/'run', retriever, only=ids, advise=advise)
    overnight.run(rt)
    brief = read_json(tmp_path/'run'/'morning_brief.json')
    assert brief['status'] == 'COMPLETE_WITH_FAILURES' and brief['accounting']['status'] == 'COMPLETE'
    [failed] = brief['incomplete_work']
    assert failed['work_id'] == ids[1] and failed['outcome'] == 'TOPIC_FAILED' and failed['failure_class'] == 'PIPELINE'
    assert failed['member_ids'] and 'simulated pipeline failure' in failed['error']
    assert brief['counts']['work_by_outcome']['CARD'] == 2


def test_budget_exhaustion_stops_requests_and_keeps_the_rest_unprocessed(retriever, view, tmp_path):
    """A run-wide ceiling of 5 requests: the first topic uses 3, the second fits only draft and grounding (its ToT is
    skipped to keep the grounding call), the third cannot start. It is UNPROCESSED_BUDGET with its members and review
    items intact, and no further request is made."""
    ids = first_topics(view)
    client = Placeholder()
    rt = runtime(tmp_path/'run', retriever, client=client, only=ids, max_requests=5)
    overnight.run(rt)
    brief = read_json(tmp_path/'run'/'morning_brief.json')
    assert len(client.calls) == 5 and brief['status'] == 'INCOMPLETE'
    [left] = brief['incomplete_work']
    assert left['work_id'] == ids[2] and left['outcome'] == 'UNPROCESSED_BUDGET' and left['member_ids']
    assert 'run request budget' in left['detail']
    second = read_json(tmp_path/'run'/'topics'/f"{ids[1].replace(':', '__').replace('/', '__')}.json")['result']['model_calls']
    assert [(c['stage'], c['status']) for c in second] == [('draft', 'OK'), ('tot', 'SKIPPED_RESERVED_FOR_GROUNDING'),
                                                            ('grounding', 'OK')]
    assert brief['accounting']['status'] == 'COMPLETE'


def test_interrupted_run_resumes_without_repeating_paid_work(retriever, view, tmp_path):
    """Interrupted during the second topic's grounding: on resume the first topic is reused with no new call, the second
    is not resent (its completion is uncertain) and stays visible, the third is processed, and the budget is not
    reset. Releasing the interrupted topic explicitly processes it."""
    ids, out = first_topics(view), tmp_path/'run'
    first = Placeholder(interrupt_at=(first_topics(view)[1], 'grounding'))
    with pytest.raises(KeyboardInterrupt):
        overnight.run(runtime(out, retriever, client=first, only=ids))
    used = read_json(out/'progress'/'run_state.json')['budget_used']['model_calls']
    assert used == len(first.calls) == 6 and (out/'progress'/'in_flight'/f"{ids[1].replace(':', '__').replace('/', '__')}.json").exists()
    assert not [p for p in (out/'topics').rglob('*.json') if p.parent != out/'topics']  # Flat result files.
    second = Placeholder()
    rt = runtime(out, retriever, client=second, only=ids)
    overnight.run(rt)
    assert {c[0] for c in second.calls} == {ids[2]}  # Nothing repeated, nothing resent.
    outcomes = {w: rt.outcomes[w]['outcome'] for w in ids}
    assert outcomes == {ids[0]: 'CARD', ids[1]: 'INTERRUPTED_UNCERTAIN', ids[2]: 'CARD'}
    assert rt.outcomes[ids[0]]['reused_on_resume'] is True
    assert read_json(out/'progress'/'run_state.json')['budget_used']['model_calls'] == used + 3
    brief = read_json(out/'morning_brief.json')
    assert brief['status'] == 'INCOMPLETE' and [w['work_id'] for w in brief['incomplete_work']] == [ids[1]]
    third = Placeholder()
    released = runtime(out, retriever, client=third, only=ids, release=[ids[1]])
    overnight.run(released)
    assert {c[0] for c in third.calls} == {ids[1]} and released.outcomes[ids[1]]['outcome'] == 'CARD'


def test_resume_refuses_changed_inputs_or_configuration(retriever, view, tmp_path):
    """A resume with a different run budget, scope or cutoff refuses; results are never reused across them."""
    ids, out = first_topics(view), tmp_path/'run'
    overnight.run(runtime(out, retriever, only=ids))
    with pytest.raises(overnight.OvernightError, match='budget_limits'):
        overnight.run(runtime(out, retriever, only=ids, max_requests=7))
    with pytest.raises(overnight.OvernightError, match='only|work_plan'):
        overnight.run(runtime(out, retriever, only=ids[:2]))
    other = overnight.Runtime(out, client=Placeholder(), cutoff='2026-10-01T12:00:00Z', retriever_factory=lambda: retriever, only=ids)
    with pytest.raises(overnight.OvernightError, match='cutoff'):
        overnight.run(other)


def test_uncertain_request_is_charged_on_resume_and_the_budget_is_kept(tmp_path):
    """A reservation still open when the run stopped is charged in full on resume (never assumed unsent)."""
    path, limits = tmp_path/'state.json', {'model_calls_total': 8}
    ledger = overnight.PersistentLedger(2.0, 0.2)
    state = overnight.RunState(path, limits, ledger)
    prices = {'input': 2e-06, 'output': 1e-05}
    reservation = ledger.reserve(prices, 24000, 16384, 'a:draft')
    ledger.settle(reservation, prices, {'prompt_tokens': 1000, 'completion_tokens': 100}, 'a:draft')
    ledger.reserve(prices, 24000, 16384, 'a:grounding')  # Interrupted before settlement.
    state.budget.charge('model_calls'), state.budget.charge('model_calls')
    resumed_ledger = overnight.PersistentLedger(2.0, 0.2)
    resumed = overnight.RunState(path, limits, resumed_ledger)
    assert resumed.budget.used['model_calls'] == 2 and resumed.uncertain
    assert resumed_ledger.spent_usd == pytest.approx(1000 * 2e-06 + 100 * 1e-05 + 24000 * 2e-06 + 16384 * 1e-05)
    assert resumed_ledger.entries[-1]['basis'].startswith('uncertain completion')
    assert resumed.can_start(type('C', (), {'halted': None})())[0]


def test_unsaved_run_state_stops_the_run_and_keeps_the_rest(retriever, view, tmp_path, monkeypatch):
    """A failed save of the run state (budget/ledger) is a PERSISTENCE failure, not a topic's stage failure: the run
    stops before sending requests its saved budget would not show, and later topics stay unprocessed with their
    members. (The Windows WinError 5 file lock seen inside the repo is one such cause.)"""
    ids, saves = first_topics(view), []
    real = overnight.write_json

    def flaky(path, payload, **kw):
        if str(path).endswith('run_state.json'):
            saves.append(path)
            if len(saves) == 6:  # During the second topic.
                raise PermissionError(5, 'Access is denied (simulated lock)')
        return real(path, payload, **kw)
    monkeypatch.setattr(overnight, 'write_json', flaky)
    client = Placeholder()
    rt = runtime(tmp_path/'run', retriever, client=client, only=ids)
    overnight.run(rt)
    outcomes = {w: rt.outcomes[w] for w in ids}
    assert outcomes[ids[0]]['outcome'] == 'CARD'
    assert (outcomes[ids[1]]['outcome'], outcomes[ids[1]]['failure_class']) == ('TOPIC_FAILED', 'PERSISTENCE')
    assert outcomes[ids[2]]['outcome'] == 'UNPROCESSED_RUN_STOPPED' and ids[2] not in {c[0] for c in client.calls}
    assert read_json(tmp_path/'run'/'morning_brief.json')['status'] == 'INCOMPLETE'
