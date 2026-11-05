"""Flag-impact reliability pass (zero calls): one element catalogue, finding history across attempts, explicit coverage.

PREPARED: hand-written judgments. DIAGNOSTIC: the frozen live run's saved responses (data/experiments/
agent3_flag_impact_live_v1) re-validated under the current rules; that is an offline reinterpretation, never a new
live result. DETERMINISTIC: provenance history, catalogue and coverage."""
import json
from pathlib import Path

import pytest

from threadsense.agents import advisor_pilot as pilot, flag_impact as fi
from threadsense.agents.advice_contracts import SourceArtifact
from threadsense.agents.flag_provenance import _finding, _prior
from tests.test_agent3_advisor import Fake, draft_for, retriever, run, sent_payload, supported, view  # noqa: F401
from tests.test_agent3_flag_impact import EXP, saved, saved_case

LIVE = 'agent3_flag_impact_live_v1'
live = pytest.mark.skipif(not (EXP/LIVE).is_dir(), reason='the frozen live shadow run is needed')
TIE, REPEAT, PLAYBACK = 'cluster_f944891544b06f79/topic_2', 'cluster_b7e5234380f9ea67/topic_1', 'cluster_6b59d13144282285/topic_2'
CENTRAL, TIE_MEMBER = 'flag_06e1381c31326fb163ea485a102ad4c3', 'flag_4e3e3ce94ee96df81ece44da0fb0da4f'


def recorded_raw(result):
    """The judge's raw flag_impacts from a saved grounding response (DIAGNOSTIC replay, not a new judgment)."""
    return json.loads(next(c for c in result['model_calls'] if c['stage'] == 'grounding')['raw'])['flag_impacts']


def assess(judgments, prepared, verdicts, states, flag, source='PREPARED'):
    return next(a for a in fi.validate(judgments, prepared, verdicts=verdicts, member_states=states, source=source)
                if a.flag_id == flag)


# ---- 1. One catalogue ---------------------------------------------------------------------------------------------

@saved
@pytest.mark.parametrize('run_name', ['agent3_summary_eval_v1', 'agent3_writing_eval_v17_v1', 'agent3_policy_eval_v1',
                                      'agent3_final_eval_v1', 'agent3_repair_eval_v1', 'agent3_overnight_offline_v2', LIVE])
def test_every_emitted_reference_is_in_the_one_catalogue(run_name):
    if not (EXP/run_name).is_dir():
        pytest.skip(f'{run_name} not present')
    from threadsense.dashboard.runs import Run
    saved_run, checked = Run(EXP/run_name), 0
    for card_id, card in saved_run.cards.items():
        if not card['inherited_flags'] or card_id not in saved_run.topics:
            continue
        prepared, verdicts, states = fi.prepare_saved(card, saved_run.topics[card_id]['result'], saved_run.flag_source)
        sent = {r['element_id'] for i in prepared['inputs'] for r in i['references']}
        assert sent <= set(prepared['element_ids'])
        echo = [{'flag_id': i['flag_id'], 'impact': 'AFFECTS', 'explanation': 'Prepared: names every reference sent.',
                 'element_ids': sorted({r['element_id'] for r in i['references']})} for i in prepared['inputs']]
        for a in fi.validate(echo, prepared, verdicts=verdicts, member_states=states, source='PREPARED'):
            assert not any(i.startswith('Unknown element IDs') for i in a.validation_issues)
        checked += 1
    assert checked


@live
def test_action_context_is_accepted_and_genuinely_unknown_ids_are_not():
    _, _, _, prepared, verdicts, states = saved_case(LIVE, TIE)
    assert 'action:context' in prepared['element_ids']
    base = {'flag_id': TIE_MEMBER, 'impact': 'AFFECTS', 'explanation': 'Prepared.'}
    for ids, unknown in ((['action:context', 'thread_status'], False), (['claim:c99'], True),
                         (['action:premise:c1'], True), (['severity.matched_signals[0]'], True)):
        a = assess([{**base, 'element_ids': ids}], prepared, verdicts, states, TIE_MEMBER)
        assert (a.impact == 'UNKNOWN') == unknown
        assert any(i.startswith('Unknown element IDs') for i in a.validation_issues) == unknown


def test_the_outbound_catalogue_is_what_validation_accepts(retriever, view):
    """End to end: a judge naming every reference element_id and finding ID it was sent is never rejected for an
    unknown ID."""
    def echo(payload):
        return {**supported(payload), 'flag_impacts': [
            {'flag_id': f['flag_id'], 'impact': 'AFFECTS', 'element_ids': sorted({r['element_id'] for r in f['references']}),
             'finding_ids': [x['finding_id'] for x in f['findings']], 'explanation': 'Prepared.'}
            for f in payload.get('flag_impacts', [])]}
    client = Fake(draft=draft_for, grounding=echo)
    result = run('json_vs_prose', client, retriever, view, flag_impact=True)
    sent = sent_payload(next(text for stage, text in client.calls if stage == 'grounding'))['flag_impacts']
    assert sent and all(f['findings'][0]['finding_id'] == 'F1' and 'resolved_findings' in f for f in sent)
    assert result['flag_impact']['contract_version'] == 'agent3-flag-impact-record-v2'
    for a in result['flag_impact']['assessments']:
        assert a['impact'] == 'AFFECTS' and not any('Unknown' in i for i in a['validation_issues'])


# ---- 2. Finding history -------------------------------------------------------------------------------------------

def test_prior_finding_rules():
    src = SourceArtifact(path='records/x/result.json')

    def status(attempt, values, kept, text='Prose unit x: UNSUPPORTED.', fields=('summary',), kept_fields=()):
        item = {'explanation': text, 'disputed_fields': list(fields), 'category': 'X'}
        return _prior(_finding('agent1_verification', attempt, item, 'C', 'member_x', src), item, attempt, values, kept,
                      set(kept_fields)).status
    coverage = 'Independent decision coverage establishes UNRESOLVED; interpretation reports PARTIALLY_RESOLVED. '
    res = ('resolution_state', 'resolution_rationale')
    # The revision was kept (the finding is the original's):
    assert status('original', {'resolution_state': 'PARTIALLY_RESOLVED', 'resolution_rationale': 'a'},
                  {'resolution_state': 'UNRESOLVED', 'resolution_rationale': 'a'}, coverage, res) == 'CORRECTED'
    assert status('original', {'authoritative_response_present': True}, {'authoritative_response_present': False},
                  fields=('authoritative_response_present',)) == 'CORRECTED'
    assert status('original', {'summary': 'a'}, {'summary': 'b'}) == 'UNCERTAIN'  # Rewritten prose.
    assert status('original', {'summary': 'a'}, {'summary': 'a'}) == 'UNCERTAIN'  # Unchanged, silently re-accepted.
    assert status('original', {'summary': 'a'}, {'summary': 'b'}, kept_fields={'summary'}) == 'SUPERSEDED'
    assert status('original', {'resolution_state': 'PARTIALLY_RESOLVED'}, {'resolution_state': 'RESOLVED_IN_THREAD'},
                  coverage, res) == 'OPEN'  # The kept state still differs from the coverage state.
    # The original was kept (the finding is the discarded revision's):
    assert status('revision', {'summary': 'a'}, {'summary': 'a'}) == 'OPEN'
    assert status('revision', {'summary': 'a'}, {'summary': 'b'}) == 'SUPERSEDED'
    assert status('revision', None, {'summary': 'a'}) == 'UNCERTAIN'


@live
def test_corrected_and_superseded_earlier_findings_do_not_block():
    """Tie thread: the original attempt's resolution and authority findings were corrected by the kept revision (state
    now the coverage state, authority fields changed, the revision's check silent on them); the other member's
    discarded revision finding disputes values only that revision held. Neither is an open finding."""
    _, _, _, prepared, _, _ = saved_case(LIVE, TIE)
    by_flag = {i['flag_id']: i for i in prepared['inputs']}
    central = by_flag[CENTRAL]
    assert [f['category'] for f in central['findings']] == ['CENTRAL_QUESTION'] and not central['attempt_errors']
    assert [(f['status'], f['category']) for f in central['resolved_findings']] == [('CORRECTED', 'RESOLUTION'),
                                                                                   ('CORRECTED', 'AUTHORITY')]
    assert 'coverage established (UNRESOLVED)' in central['resolved_findings'][0]['basis']
    member = by_flag[TIE_MEMBER]
    assert [f['finding_id'] for f in member['findings']] == ['F1', 'F2']
    assert [f['status'] for f in member['resolved_findings']] == ['SUPERSEDED']


@saved
def test_unresolved_finding_of_a_discarded_attempt_stays_open_and_blocks_clearance():
    """Playback thread (member 8ce5853): the kept revision rewrote the prose fields an earlier finding disputed and its
    check raised nothing. The record does not establish a correction (a human content review of this thread found the
    revised summary still carried a disputed claim), so the finding is UNCERTAIN, sent as open, and blocks INDEPENDENT."""
    _, _, _, prepared, verdicts, states = saved_case('agent3_overnight_offline_v2', PLAYBACK)
    prov = next(p for p in prepared['provenance'] if p['member_ids'] == ['member_8ce5853bbd6b1a416c28b76f'])
    statuses = sorted((h['status'], h['finding']['category']) for h in prov['finding_history'])
    assert statuses == [('CORRECTED', 'AUTHORITY'), ('CORRECTED', 'RESOLUTION'), ('UNCERTAIN', 'TERMINOLOGY')]
    prior = next(h for h in prov['finding_history'] if h['status'] == 'UNCERTAIN')
    assert 'rewritten prose' in prior['basis']
    flag = next(x for x in prepared['inputs'] if x['flag_id'] == prov['flag_id'])
    uncertain = [f for f in flag['findings'] if f['status'] == 'UNCERTAIN']
    assert len(uncertain) == 1 and uncertain[0]['category'] == 'TERMINOLOGY' and uncertain[0]['from_discarded_attempt']
    refs = sorted({r['element_id'] for r in flag['references'] if r['relation'] in fi.COVERED})
    judgment = {'flag_id': prov['flag_id'], 'impact': 'INDEPENDENT', 'element_ids': refs or ['title'],
                'finding_ids': [f['finding_id'] for f in flag['findings']], 'explanation': 'Prepared.',
                'independence_basis': 'Prepared.'}
    a = assess([judgment], prepared, verdicts, states, prov['flag_id'])
    assert a.impact == 'UNKNOWN' and a.uncertain_finding_ids == [uncertain[0]['finding_id']]
    assert a.validation_issues[0].startswith('The record cannot establish whether an earlier finding was corrected')


# ---- 3. Coverage --------------------------------------------------------------------------------------------------

@saved
def test_independent_must_account_for_every_open_finding_and_the_member_state_itself():
    """Member 42af in the scripted run (its state only in diagnostics), with the run's record gap removed to isolate
    the rules: F1 alone, an unknown finding ID, or topic invariance alone do not clear; F1+F2 with the member's own
    resolution assessed does. With the record gap in place nothing clears. PREPARED judgments."""
    _, _, _, gapped, verdicts, states = saved_case('agent3_overnight_offline_v2', TIE)
    prepared = {**gapped, 'dependencies': [{**d, 'record_gaps': []} for d in gapped['dependencies']]}
    base = {'flag_id': TIE_MEMBER, 'impact': 'INDEPENDENT', 'explanation': 'Prepared.', 'independence_basis': 'Prepared.'}
    member = ['resolution:member_42af0c53b9dee102697caa09']

    def impact(source=prepared, **kw):
        a = assess([{**base, **kw}], source, verdicts, states, TIE_MEMBER)
        return a.impact, a.validation_issues
    assert impact(element_ids=member, finding_ids=['F1']) == ('UNKNOWN', ['Open findings not accounted for: F2.'])
    assert impact(element_ids=member, finding_ids=['F1', 'F2', 'F9'])[0] == 'UNKNOWN'
    assert impact(element_ids=['topic_resolution'], finding_ids=['F1', 'F2'])[0] == 'UNKNOWN'
    assert impact(element_ids=member, finding_ids=['F1', 'F2']) == ('INDEPENDENT', [])
    assert impact(gapped, element_ids=member, finding_ids=['F1', 'F2'])[1][0].startswith('Dependency coverage is incomplete')


@live
def test_affects_lists_are_known_effects_and_references_stay_beside_them():
    """Repeated ending (DIAGNOSTIC replay of the live responses): both AFFECTS judgments stay as the judge gave them,
    with the deterministic references they did not name recorded beside them (the reporter count and HIGH signal for
    the AUDIO-9012 member; the whole summary for the title caution). Nothing is released."""
    _, _, result, prepared, verdicts, states = saved_case(LIVE, REPEAT)
    out = {a.flag_id: a for a in fi.validate(recorded_raw(result), prepared, verdicts=verdicts, member_states=states,
                                             source='REPLAY')}
    member, title = out['flag_9d20ed872d018f64ffb30bd9f5632a39'], out['flag_15a6bbd45a49ff8b339a508bb91f7766']
    assert member.impact == title.impact == 'AFFECTS' and member.retains_review and title.retains_review
    assert {'reporter:U011', 'severity:signal:HIGH[3]', 'claim:c4', 'summary:s1'} <= set(member.unassessed_reference_ids)
    assert {'resolution:member_a05733133a11c3689d715928', 'thread_status'} <= \
        set(member.reference_ids) - set(member.unassessed_reference_ids)
    assert title.reference_ids == ['summary', 'title'] and title.unassessed_reference_ids == ['summary']
    assert any(i.startswith('Known effects only') for i in member.validation_issues)


# ---- 5. Saved live responses ------------------------------------------------------------------------------------

@live
def test_live_tie_judgments_replayed_under_v2_diagnostic_only():
    """DIAGNOSTIC: the saved live responses predate finding_ids, so the central-question INDEPENDENT cannot account for
    F1 and stays UNKNOWN (no longer because of action:context). With F1 added by hand (PREPARED, not a model result)
    it would validate; the member-resolution flag and HIGH severity still keep the card in review."""
    _, card, result, prepared, verdicts, states = saved_case(LIVE, TIE)
    raw = recorded_raw(result)
    out = {a.flag_id: a for a in fi.validate(raw, prepared, verdicts=verdicts, member_states=states, source='REPLAY')}
    assert out[CENTRAL].impact == 'UNKNOWN' and out[CENTRAL].validation_issues == ['Open findings not accounted for: F1.']
    assert out[TIE_MEMBER].impact == 'AFFECTS'
    patched = [{**j, 'finding_ids': ['F1']} if j['flag_id'] == CENTRAL else j for j in raw]
    out = {a.flag_id: a for a in fi.validate(patched, prepared, verdicts=verdicts, member_states=states, source='PREPARED')}
    assert out[CENTRAL].impact == 'INDEPENDENT' and out[TIE_MEMBER].retains_review
    assert {'HIGH_SEVERITY', 'INHERITED_FLAG'} <= {r['code'] for r in card['needs_review_reasons']}


@live
def test_recorded_live_flag_judgments_need_a_new_judgment():
    client = pilot.ReplayClient(EXP/LIVE)
    # Prompts v18 changed the grounding rules (DETAIL, NO_ACTION_RATIONALE), so the recorded statement verdicts are no
    # longer reusable either; until then they were (grounding inputs unchanged through v17).
    assert not client.grounding_inputs_same and not client.flag_rules_same
    payload = {'scenario_id': next(iter(client.recorded)), 'statements': [], 'member_threads': [], 'retrieved_sources': [],
               'flag_impacts': []}
    assert client._judgment(payload, client.recorded[payload['scenario_id']])['flag_impacts'] == []
    assert client.reuse_log[-1]['reason'] == 'flag-impact rules changed'


@live
def test_frozen_live_run_is_read_not_rewritten():
    path = Path(EXP/LIVE/'run_manifest.json')
    before = path.read_bytes()
    saved_case(LIVE, TIE)
    assert path.read_bytes() == before
