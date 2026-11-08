"""Shadow ToT policy (agent3-tot-shadow-partial-order-v1), controller fingerprints and replay boundaries. PREPARED
judgments and hand-built candidate records: these show the controller and the policy's decision boundary, not model
accuracy. Saved live comparisons are evaluated separately (scripts/evaluate_tot_shadow.py)."""
import importlib.util
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.agents import advisor_tot, overnight, tot_policy
from tests.test_agent3_advisor import Fake, retriever, run, supported, view  # noqa: F401 - fixtures reused
from tests.test_agent3_corrections import fallback_draft
from tests.test_agent3_tot_v3 import SCENARIO, candidate, choice_draft, comparison, guide_of, members

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT/'data/experiments/threadsense_full_v1_combined_v2'
RATINGS = {'evidence_support': 'STRONG', 'need_strength': 'STRONG', 'severity_fit': 'FITS', 'temporal_scope': 'CONSISTENT',
           'proportionality': 'FITS'}


def saved(cid, action_type='POST_ALIGNMENT', **extra):
    """A candidate as check_candidates saves it: valid, issue-free, with premises; ratings overridable."""
    c = {'candidate_id': cid, 'action_type': action_type, 'draft_text': f'{cid} text.', 'rationale': 'It helps.',
         'instruction': None, 'evidence_ids': ['k:g'], 'valid': True, 'issues': [], 'premise_ids': ['c1'],
         'recorded_applicability': 'CURRENT', 'applicability': 'CURRENT', **RATINGS,
         'intervention_need': {'kind': 'OPERATIONAL_PROBLEM', 'statement': 'Reports describe a current failure.',
                               'evidence_ids': ['m:1']} if action_type != 'NO_ACTION' else None}
    if action_type == 'NO_ACTION':
        c['need_strength'] = 'NONE'
    return {**c, **extra}


# ---- Partial order --------------------------------------------------------------------------------------------------

def test_a_genuine_clear_advantage():
    a = tot_policy.assess(saved('INC', evidence_support='PARTIAL'), saved('B'))
    assert a['assessment'] == 'CLEAR_ADVANTAGE' and a['supporting'] == ['evidence_support'] and not a['opposing'] + a['unresolved']


def test_equal_ratings_are_a_tie_even_between_different_actions():
    a = tot_policy.assess(saved('INC', 'SCHEDULE_ALIGNMENT'), saved('B', 'POST_ALIGNMENT'))
    assert a['assessment'] == 'RATING_TIE' and {d['relation'] for d in a['dimensions']} == {'EQUAL'}


def test_competing_advantages_are_a_trade_off():
    a = tot_policy.assess(saved('INC', evidence_support='PARTIAL'), saved('B', severity_fit='PARTIAL'))
    assert a['assessment'] == 'TRADE_OFF' and a['supporting'] == ['evidence_support'] and a['opposing'] == ['severity_fit']


@pytest.mark.parametrize('incumbent, challenger, dimension, reason', [
    ({}, {'severity_fit': 'UNKNOWN'}, 'severity_fit', 'UNKNOWN'),
    ({'need_strength': None}, {}, 'need_strength', 'MISSING'),
    ({}, {'temporal_scope': 'UNCLEAR'}, 'temporal_scope', 'UNKNOWN'),
    ({}, {'proportionality': 'UNCLEAR'}, 'proportionality', 'UNKNOWN'),
])
def test_unknown_or_missing_ratings_never_establish_at_least_as_good(incumbent, challenger, dimension, reason):
    a = tot_policy.assess(saved('INC', evidence_support='PARTIAL', **incumbent), saved('B', **challenger))
    assert a['assessment'] == 'INSUFFICIENT_COMPARISON' and a['unresolved'] == [dimension]
    assert next(d for d in a['dimensions'] if d['dimension'] == dimension)['reason'] == reason


def test_applicability_is_a_gate_not_a_preference():
    """Mixed current and historical evidence is not ranked below current-only; historical-only support for an operational
    action is rejected by the existing check (HISTORICAL_ONLY_SUPPORT), so the challenger is INELIGIBLE."""
    mixed = tot_policy.assess(saved('INC'), saved('B', recorded_applicability='MIXED', applicability='MIXED'))
    assert mixed['assessment'] == 'RATING_TIE' and mixed['applicability']['role'] == 'ELIGIBILITY_GATE'
    history = tot_policy.assess(saved('INC'), saved('B', recorded_applicability='HISTORICAL_ONLY', issues=['HISTORICAL_ONLY_SUPPORT']))
    assert history['assessment'] == 'INELIGIBLE' and 'HISTORICAL_ONLY_SUPPORT' in history['ineligible_reason']


def test_excessive_and_insufficient_are_different_problems():
    a = tot_policy.assess(saved('INC', proportionality='EXCESSIVE'), saved('B', proportionality='INSUFFICIENT'))
    assert a['assessment'] == 'INSUFFICIENT_COMPARISON'
    assert next(d for d in a['dimensions'] if d['dimension'] == 'proportionality')['reason'] == 'INCOMPARABLE'
    assert tot_policy.assess(saved('INC', proportionality='EXCESSIVE'), saved('B'))['assessment'] == 'CLEAR_ADVANTAGE'
    assert tot_policy.assess(saved('INC', proportionality='EXCESSIVE'), saved('B', proportionality='EXCESSIVE'))['assessment'] == 'RATING_TIE'


def test_intervening_versus_observing_is_left_to_the_final_grounding():
    """NO_ACTION keeps its current handling: need strength is not compared across intervention and observation."""
    a = tot_policy.assess(saved('INC'), saved('WAIT', 'NO_ACTION'))
    assert a['assessment'] == 'INSUFFICIENT_COMPARISON' and a['unresolved'] == ['need_strength']
    assert next(d for d in a['dimensions'] if d['dimension'] == 'need_strength')['reason'] == 'INTERVENTION_VS_OBSERVATION'


@pytest.mark.parametrize('extra, reason', [
    ({'valid': False}, 'not valid'), ({'issues': ['APPLICABILITY_OVERSTATED']}, 'candidate issues'),
    ({'premise_ids': []}, 'no draft claim shares its evidence'), ({'action_type': 'UPDATE_DOCUMENTATION'}, 'action contract'),
])
def test_existing_gates_make_a_challenger_ineligible(extra, reason):
    a = tot_policy.assess(saved('INC'), saved('B', evidence_support='STRONG', **extra))
    assert a['assessment'] == 'INELIGIBLE' and a['ineligible_reason'].startswith(reason)


# ---- Proposals and post-grounding outcomes ----------------------------------------------------------------------------

def compared(decision, preferred, *cands, close=False):
    return {'status': 'COMPARED', 'contract_version': 'agent3-tot-comparison-v3', 'decision': decision, 'close_call': close,
            'model_preferred_candidate_id': preferred, 'rationale': 'Prose.', 'candidates': list(cands)}


def test_a_close_call_is_never_turned_into_a_preference():
    """Even when the ratings show a clear advantage (as in one saved live close call), only explicit replacements are
    assessed; the close call keeps production handling."""
    tot = compared('CLOSE_CALL', None, saved('INC', incumbent=True, need_strength='PARTIAL'), saved('B'), close=True)
    record = tot_policy.shadow({'tot': tot, 'card': {'recommended_action': None}})
    assert record['proposal'] == 'CLOSE_CALL' and record['outcome']['status'] == 'SAME_AS_PRODUCTION'
    assert record['unproposed_relations'][0]['assessment'] == 'CLEAR_ADVANTAGE' and 'assessment' not in record


@pytest.mark.parametrize('assessed, challenger_on_card, incumbent, expected', [
    ('CLEAR_ADVANTAGE', True, saved('INC', incumbent=True, grounding='SUPPORTED', sufficiency={'check': 'SUPPORTED'}), 'REPLACEMENT_STANDS'),
    ('RATING_TIE', True, saved('INC', 'SCHEDULE_ALIGNMENT', incumbent=True, grounding='SUPPORTED', sufficiency={'check': 'SUPPORTED'}),
     'TL_CHOICE'),
    ('RATING_TIE', True, saved('INC', incumbent=True, grounding='SUPPORTED', sufficiency={'check': 'SUPPORTED'}), 'INCUMBENT_KEPT'),
    ('TRADE_OFF', True, saved('INC', 'SCHEDULE_ALIGNMENT', incumbent=True, grounding='UNSUPPORTED'), 'SINGLE_ELIGIBLE_ACTION'),
    ('TRADE_OFF', False, saved('INC', 'SCHEDULE_ALIGNMENT', incumbent=True, grounding='SUPPORTED', sufficiency={'check': 'SUPPORTED'}),
     'SINGLE_ELIGIBLE_ACTION'),
    ('CLEAR_ADVANTAGE', False, saved('INC', incumbent=True, grounding='PARTIALLY_SUPPORTED'), 'NO_ELIGIBLE_ACTION'),
    ('RATING_TIE', True, saved('INC', 'NO_ACTION', incumbent=True, grounding='SUPPORTED'), 'TL_CHOICE'),  # NO_ACTION: no sufficiency
])
def test_post_grounding_viability_decides_what_the_shadow_would_show(assessed, challenger_on_card, incumbent, expected):
    """Never offers an unsupported option; one eligible action never becomes an unresolved choice."""
    link = {'candidate_id': 'B', 'basis': 'SELECTED'} if challenger_on_card else {'candidate_id': None, 'basis': 'NO_CARD_ACTION'}
    out = tot_policy.outcome(assessed, incumbent, saved('B'), link)
    assert out['status'] == expected
    if expected == 'SINGLE_ELIGIBLE_ACTION':
        assert len(out['eligible_after_grounding']) == 1


def highly_rated_replacement(payload):
    """An explicit REPLACE_INCUMBENT whose challenger out-rates the incumbent (need strength)."""
    value = comparison(payload, 'B', [candidate('B', 'ESCALATE_ENGINEERING', [guide_of(payload)] + members(payload)[:1],
                                                'Playback fails for several tasks; please investigate.', need_ids=members(payload)[:1])])
    value['candidates'][0]['need_strength'] = 'PARTIAL'
    return value


def test_a_highly_rated_candidate_that_fails_grounding_does_not_stand(retriever, view):
    """Production selects B; the final grounding rejects it. The shadow records CLEAR_ADVANTAGE from the ratings but the
    outcome follows the verdicts: only the incumbent remains eligible. Card and routing are production's."""
    result = run(SCENARIO, Fake(draft=choice_draft, tot=highly_rated_replacement,
                                grounding=lambda p: supported(p, action='UNSUPPORTED')), retriever, view, tot_shadow=True)
    shadow = result['tot']['shadow_policy']
    assert shadow['proposal'] == 'EXPLICIT_REPLACEMENT' and shadow['assessment'] == 'CLEAR_ADVANTAGE'
    assert shadow['supporting'] == ['need_strength'] and shadow['agrees_with_model']
    assert shadow['outcome']['status'] == 'SINGLE_ELIGIBLE_ACTION' and shadow['outcome']['eligible_after_grounding'] == ['INC']
    assert result['card']['recommended_action'] is None  # Production: the selected B was withheld; no fallback to it.


def test_a_model_preference_the_ratings_do_not_establish_stays_visible(retriever, view):
    def tie(payload):
        return comparison(payload, 'B', [candidate('B', 'NO_ACTION', [guide_of(payload)] + members(payload)[:1], 'Keep observing.')])
    result = run(SCENARIO, Fake(draft=choice_draft, tot=tie, grounding=supported), retriever, view, tot_shadow=True)
    shadow = result['tot']['shadow_policy']
    assert shadow['assessment'] == 'INSUFFICIENT_COMPARISON' and not shadow['agrees_with_model']
    assert shadow['model'] == {**shadow['model'], 'decision': 'REPLACE_INCUMBENT', 'preferred_candidate_id': 'B'}
    assert 'would not let that preference stand on its own' in shadow['note']
    assert result['action_source'] == 'TOT'  # Production is unchanged: the shadow never routes.


# ---- Withheld incumbent duplicated under another ID ---------------------------------------------------------------------

def test_a_withheld_incumbent_duplicated_under_another_id_cannot_return(retriever, view):
    def duplicate(payload):
        guide = payload['draft']['claims'][1]['evidence_ids']
        inc = payload['incumbent']
        need = inc['intervention_need']['evidence_ids']
        return {'candidates': [candidate('INC', inc['action_type'], guide, inc['draft_text'], incumbent=True, need_ids=need),
                               candidate('DUP', inc['action_type'], guide, inc['draft_text'] + ' ', need_ids=need)],
                'preferred_candidate_id': 'DUP', 'close_call': False, 'decision': 'KEEP_INCUMBENT', 'rationale': 'Same text.'}
    result = run('audio_playback', Fake(draft=fallback_draft, tot=duplicate,
                                        grounding=lambda p: supported(p, essential=['claim:c2', 'claim:c3'])), retriever, view)
    verdicts = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    assert verdicts['action'] == 'ESSENTIAL_PREMISE_NOT_PASSED' and verdicts['alternative:DUP'] == 'SUPPORTED'
    assert result['card']['recommended_action'] is None and result['action_source'] == 'DRAFT'
    assert any(n.startswith('No ToT fallback: preferred candidate DUP is the incumbent') for n in result['action_notes'])


# ---- TL decisions keep the candidate link -------------------------------------------------------------------------------

@pytest.mark.skipif(not DEMO.is_dir(), reason='demo baseline not present')
def test_tl_decisions_record_the_alternative_and_the_card_action_link(tmp_path):
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.runs import Catalog
    root = tmp_path/'runs'
    shutil.copytree(DEMO, root/DEMO.name, ignore=shutil.ignore_patterns('screenshots'))
    client = TestClient(create_app(catalog=Catalog([root]), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    brief = client.get(f'/api/runs/{DEMO.name}/brief').json()
    card = next(c for c in brief['cards'] if c['card']['topic_name'] == 'NSFW suggestive-content threshold')
    cid = card['card']['card_id']
    details = client.get(f'/api/runs/{DEMO.name}/cards/{cid}').json()['details']
    assert details['action_candidate'] == {'candidate_id': 'focused_discussion', 'basis': 'INCUMBENT'}
    assert [a['candidate_id'] for a in card['alternatives']] == ['written_clarification_request']
    entry = client.post(f'/api/runs/{DEMO.name}/cards/{cid}/decisions', headers={'Idempotency-Key': 'tot-link-1'},
                        json={'kind': 'CONFIRM_ANNOUNCEMENT', 'actor_id': 'U006', 'alternative_id': 'written_clarification_request'}).json()['entry']
    assert (entry['text']['grounded_source'], entry['text']['alternative_id']) == ('SUPPORTED_ALTERNATIVE', 'written_clarification_request')
    assert entry['decision']['original_advice']['advice_id'] == f'{cid}:written_clarification_request'


# ---- Fingerprints and replay isolation ----------------------------------------------------------------------------------

def test_the_controller_fingerprint_covers_controller_code_not_only_the_prompt(monkeypatch):
    before = advisor_tot.controller_fingerprint()
    assert before['version'] == advisor_tot.CONTROLLER_VERSION and advisor_tot.select in advisor_tot.CONTROLLER_FUNCTIONS
    assert {advisor_tot.fallback, advisor_tot.finalize, advisor_tot.choice_after_grounding} <= set(advisor_tot.CONTROLLER_FUNCTIONS)

    def select(tot, draft):  # a changed selection rule with the same prompt
        return draft, None
    monkeypatch.setattr(advisor_tot, 'CONTROLLER_FUNCTIONS', tuple(select if f is advisor_tot.select else f
                                                                   for f in advisor_tot.CONTROLLER_FUNCTIONS))
    assert advisor_tot.controller_fingerprint()['sha256'] != before['sha256']
    from threadsense.agents import advisor_pilot as pilot
    assert 'tot_controller' not in pilot.prompt_fingerprints()  # the prompt fingerprint alone would not have shown it


def test_a_resume_under_other_controller_rules_or_shadow_setting_is_refused(retriever, view, tmp_path):
    from tests.test_agent3_overnight import Placeholder, first_topics, runtime
    from threadsense.handoff_inputs import read_json
    ids, out = first_topics(view, 1), tmp_path/'run'
    overnight.run(runtime(out, retriever, only=ids))
    fp = read_json(out/'run_manifest.json')['fingerprints']
    assert fp['tot_controller'] == advisor_tot.controller_fingerprint() and 'tot_shadow_policy' not in fp
    with pytest.raises(overnight.OvernightError, match='tot_shadow_policy'):
        overnight.run(runtime(out, retriever, only=ids, tot_shadow=True))
    manifest = read_json(out/'run_manifest.json')
    manifest['fingerprints']['tot_controller'] = {'version': 'agent3-tot-controller-v1', 'sha256': '0' * 64}
    (out/'run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(overnight.OvernightError, match='tot_controller'):  # recorded results are never reused under new rules
        overnight.run(runtime(out, retriever, only=ids, client=Placeholder()))


def test_the_shadow_changes_no_request_card_or_route(retriever, view):
    sent = {}

    def grounding(tag):
        return lambda p: sent.setdefault(tag, []).append(json.dumps(p, sort_keys=True)) or supported(p)
    off = run(SCENARIO, Fake(draft=choice_draft, tot=highly_rated_replacement, grounding=grounding('off')), retriever, view)
    on = run(SCENARIO, Fake(draft=choice_draft, tot=highly_rated_replacement, grounding=grounding('on')), retriever, view,
             tot_shadow=True)
    assert sent['off'] == sent['on'] and off['card'] == on['card'] and off['action_source'] == on['action_source']
    assert 'shadow_policy' not in off['tot'] and on['tot']['shadow_policy']['policy'] == tot_policy.SHADOW_POLICY_VERSION
    assert off['tot']['controller'] == on['tot']['controller'] == advisor_tot.CONTROLLER_VERSION


def test_a_replay_under_changed_rules_is_labelled_a_rebuild(tmp_path):
    spec = importlib.util.spec_from_file_location('full', ROOT/'scripts'/'run_threadsense_full.py')
    full = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(full)
    config = {'pipeline': 'threadsense-full-run-v2', 'agent3_tot_controller': advisor_tot.controller_fingerprint(), 'x': 1}
    parent = tmp_path/'parent'
    parent.mkdir()
    (parent/'run_manifest.json').write_text(json.dumps({'configuration': config}), encoding='utf-8')
    assert full.rules_vs_parent(config, [parent]) == {'parent': str(parent), 'status': 'SAME_RULES', 'changed': []}
    older = {k: v for k, v in config.items() if k != 'agent3_tot_controller'}  # recorded before controller v2
    (parent/'run_manifest.json').write_text(json.dumps({'configuration': older}), encoding='utf-8')
    assert full.rules_vs_parent(config, [parent])['changed'] == ['agent3_tot_controller']
    assert full.rules_vs_parent(config, []) is None
