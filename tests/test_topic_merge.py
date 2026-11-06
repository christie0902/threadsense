"""Agent 2 consolidation (agent2-consolidation-v1) on the cached full run: bounded candidates, judged merges, whole-group
validation, and the consolidated handoff reaching Agent 3. Offline: cached embeddings, prepared or scripted judgments."""
from copy import deepcopy
import json

import pytest

from threadsense.agents import topic_merge as tm
from threadsense.agents.advice_inputs import apply_consolidation, load_effective_view
from threadsense.routing import ROOT

FULL = ROOT/'data/experiments/threadsense_full_v1/stages'
DECISIONS = json.loads((ROOT/'data/evaluation/agent2_consolidation_decisions_v1.json').read_text(encoding='utf-8'))
pytestmark = pytest.mark.skipif(not FULL.is_dir(), reason='full live run not present')
DATES = ('cluster_2845c1b030fe6d60/topic_1', 'cluster_abd05f6abf50117f/topic_1', 'cluster_f0695830b5417b7e/topic_1')
FICTIONAL = ('cluster_9378eb54bc546fcd/topic_1', 'cluster_d9ad05f5bda622e1/topic_1')


@pytest.fixture(scope='module')
def view():
    return load_effective_view(FULL/'agent2'/'agent2_v1')


@pytest.fixture(scope='module')
def topics(view):
    vectors = tm.member_vectors(FULL/'agent1_verify'/'agent1_verified_v2'/'interpretations.json', FULL/'grouping'/'grouping_v1')
    return tm.topics_of(view, vectors)


class Scripted:
    """Accepts exactly the listed topic sets; everything else DISTINCT."""
    provenance = 'SCRIPTED_TEST'

    def __init__(self, same=(), raw=None):
        self.same, self.raw, self.calls = [set(s) for s in same], raw, []

    def __call__(self, cset, payload, by_id):
        self.calls.append(cset['topic_ids'])
        if self.raw:
            return tm.MergeJudgment.model_validate({**self.raw, 'candidate_set_id': cset['candidate_set_id']}), None
        hit = set(cset['topic_ids']) in self.same
        return tm.MergeJudgment(candidate_set_id=cset['candidate_set_id'], decision='SAME_ISSUE' if hit else 'DISTINCT',
                                same_issue_topic_ids=cset['topic_ids'] if hit else [], consolidated_name='Merged' if hit else None,
                                rationale='scripted', distinguishing_factors=[]), None


def test_candidates_are_bounded_cross_group_and_within_scope(topics):
    sets, over = tm.candidates(topics)
    by_id = {t['topic_id']: t for t in topics}
    assert len(sets) == 37 and not over and all(2 <= len(s['topic_ids']) <= tm.LIMITS['max_set_size'] for s in sets)
    for s in sets:
        ts = [by_id[t] for t in s['topic_ids']]
        assert len({(t['project_id'], t['batch_id']) for t in ts}) == 1 and len({t['candidate_group_id'] for t in ts}) == len(ts)
    capped, rest = tm.candidates(topics, {**tm.LIMITS, 'max_sets': 5})
    assert len(capped) == 5 and len(rest) == 32


def test_a_valid_cross_group_merge_keeps_every_thread_flag_and_subquestion(topics):
    record = tm.consolidate(topics, Scripted([FICTIONAL]))
    (merge,) = record['merges']
    by_id = {t['topic_id']: t for t in topics}
    assert merge['source_topic_ids'] == sorted(FICTIONAL) and len(merge['candidate_group_ids']) == 2
    assert merge['member_ids'] == sorted(m for t in FICTIONAL for m in by_id[t]['member_ids'])
    assert merge['flagged_member_ids'] == sorted(m for t in FICTIONAL for m in by_id[t]['flagged_member_ids']) and merge['flagged_member_ids']
    assert len(merge['subquestions']) == 6 and all(q['central_question'] for q in merge['subquestions'])
    assert record['counts']['topics_out'] == len(topics) - 1 and record['counts']['requests'] == 0


def test_near_matches_stay_separate_under_the_prepared_decisions(topics):
    record = tm.consolidate(topics, tm.PreparedJudge(DECISIONS))
    merged = {t for m in record['merges'] for t in m['source_topic_ids']}
    for pair in (('cluster_b2dd7d5b611c1fbb/topic_1', 'cluster_db20d884110726af/topic_1'),   # Korean vs Japanese specialist route
                 ('cluster_23fab6d43c64532d/topic_1', 'cluster_995c46bccbc8d59d/topic_1'),   # different submit failure modes
                 ('cluster_7e30e869d7c995fa/topic_1', 'cluster_b2dd7d5b611c1fbb/topic_1')):  # mixed topic
        assert not set(pair) & merged
    assert set(FICTIONAL) <= merged and record['counts'] == {**record['counts'], 'merges': 14, 'topics_merged': 29, 'judged': 38}
    assert record['judge_provenance'] == 'PREPARED_AUDIT' and {j['provenance'] for j in record['judgments']} == {'PREPARED_AUDIT'}


def test_a_chain_of_accepted_pairs_merges_only_as_a_judged_whole(topics):
    pairs = [DATES[:2], DATES[1:]]
    blocked = tm.consolidate(topics, Scripted(pairs))
    assert not blocked['merges'] and blocked['blocked_components'][0]['topic_ids'] == sorted(DATES)
    assert blocked['blocked_components'][0]['outcome'] == 'KEPT_SEPARATE_CHAIN_NOT_CONFIRMED'
    whole = tm.consolidate(topics, Scripted(pairs + [DATES]))
    assert [m['source_topic_ids'] for m in whole['merges']] == [sorted(DATES)] and len(whole['merges'][0]['judgment_set_ids']) == 3
    strict = tm.consolidate(topics, Scripted(pairs + [DATES]), {**tm.LIMITS, 'whole_centroid_min': 0.9})
    assert not strict['merges'] and 'whole-group floor' in strict['blocked_components'][0]['reason']


def test_an_invalid_or_unbound_judgment_never_merges(topics):
    bad = tm.consolidate(topics, Scripted(raw={'decision': 'SAME_ISSUE', 'same_issue_topic_ids': ['cluster_x/topic_1', 'cluster_y/topic_1'],
                                               'consolidated_name': 'x', 'rationale': 'r', 'distinguishing_factors': []}))
    assert not bad['merges'] and {j['status'] for j in bad['judgments']} == {'INVALID'}
    stale = deepcopy(DECISIONS)
    for d in stale['decisions']:
        for tid in d['topic_members']:
            d['topic_members'][tid] = d['topic_members'][tid][:-1] + ['member_other']
    unbound = tm.consolidate(topics, tm.PreparedJudge(stale))
    assert not unbound['merges'] and {j['status'] for j in unbound['judgments']} == {'NOT_ASSESSED'}


def test_the_live_judge_builds_one_strict_request_without_sending_it(topics, monkeypatch):
    monkeypatch.setenv('THREADSENSE_AGENT2_REASONING_EFFORT', 'low')
    judge = tm.LiveJudge('openai/gpt-5.4-2026-03-05')
    sets, _ = tm.candidates(topics)
    body = judge.request(tm.model_input(sets[0], {t['topic_id']: t for t in topics}))
    schema = body['response_format']['json_schema']
    assert schema['strict'] and set(schema['schema']['required']) == set(tm.MergeJudgment.model_fields)
    assert body['reasoning_effort'] == 'low' and 'temperature' not in body
    payload = json.loads(body['messages'][-1]['content'])
    assert 'action' not in json.dumps(payload).lower().replace('interaction', '')  # no Agent 3 advice reaches the judge


def test_the_consolidated_handoff_reaches_agent3_as_one_work_item(view, topics):
    from threadsense.agents import overnight
    from threadsense.agents.advisor_pilot import topic_packet
    record = tm.consolidate(topics, tm.PreparedJudge(DECISIONS))
    joined = apply_consolidation(view, record)
    work = overnight.plan(joined)
    consolidated = [w for w in work if w['kind'] == 'CONSOLIDATED_TOPIC']
    assert len(consolidated) == 14 and len(work) == len(overnight.plan(view)) - 29 + 14
    assert sorted(m for w in work for m in w['member_ids']) == sorted(m for w in overnight.plan(view) for m in w['member_ids'])
    item = next(w for w in consolidated if set(w['source_topic_ids']) == set(FICTIONAL))
    packet = topic_packet(joined, {'id': item['work_id'], 'candidate_group_id': item['candidate_group_id'],
                                   'topic_id': item['topic_id'], 'consolidated_topic_id': item['topic_id']})
    assert packet['handoff_contract'] == 'agent2-taxonomy-handoff-v3' and len(packet['records']) == 2
    assert sorted(packet['member_ids']) == sorted(item['member_ids']) and len(packet['threads']) == 6
    with pytest.raises(ValueError):
        apply_consolidation(view, {**record, 'pass_through_topic_ids': record['pass_through_topic_ids'][1:]})
