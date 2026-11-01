"""temporal-golden-policy-v1 is a separate benchmark derived from temporal-golden-v1 (DETERMINISTIC, no evaluation run):
the v1 file is unchanged, the 14 carried cases are identical, and T02 is replaced by labelled negative and positive
enactment cases."""
from hashlib import sha256
import json

from threadsense.routing import ROOT

V1 = ROOT/'data/evaluation/temporal_golden.json'
POLICY = json.loads((ROOT/'data/evaluation/temporal_golden_policy_v1.json').read_text(encoding='utf-8'))


def test_v1_is_unchanged_and_carried_cases_are_identical():
    v1 = json.loads(V1.read_text(encoding='utf-8'))
    assert sha256(V1.read_bytes()).hexdigest() == POLICY['derived_from']['sha256']
    carried = {c['id']: c for c in POLICY['cases']}
    assert [c['id'] for c in v1['cases'] if c['id'] != 'T02_authorized_tl_directive'] == POLICY['derived_from']['unchanged_cases']
    assert all(carried[c['id']] == c for c in v1['cases'] if c['id'] != 'T02_authorized_tl_directive')
    assert v1['defaults'] == POLICY['defaults']


def test_t02_is_replaced_by_one_negative_and_two_positive_cases():
    ids = [c['id'] for c in POLICY['cases']]
    assert 'T02_authorized_tl_directive' not in ids and len(ids) == 17
    t02 = {c['id'][:4]: c for c in POLICY['cases'] if c['id'].startswith('T02')}
    assert t02['T02N']['expected']['decision'] == 'ABSTAIN' and t02['T02N']['expected']['documentation_update_target'] is None
    assert {'D', 'G'} == set(t02['T02N']['expected']['must_not_win'])
    assert t02['T02A']['expected']['policy']['governing_sources'] == ['A']
    assert t02['T02E']['expected']['policy']['governing_sources'] == ['D']
    assert 'NOT permitted as a provisional decided baseline' in POLICY['enactment_policy']['eligible_older_guideline']
