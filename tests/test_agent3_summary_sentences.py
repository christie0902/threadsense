"""Sentence-level summary judgment (draft v9), from the recorded TL-summary attribution failure.

agent3_policy_eval_v1 (and agent3_final_eval_v1 before it) withheld the whole JSON-versus-prose summary because its
first sentence gave all three askers a question ("format against factual accuracy") that one of them did not ask; the
second sentence was supported. RECORDED tests read that run's draft, evidence ledger and verdicts unchanged; replay
reuses a verdict only for unchanged content. PREPARED tests script the judge (labelled); display selection is
DETERMINISTIC: a sentence is shown only if SUPPORTED, with its condensed claims and earlier sentences shown, never
rewritten."""
import json

import pytest

from threadsense.agents.advisor_checks import presentation_issues, shown_summary, statements
from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.advisor_pilot import ReplayClient, _json_text
from threadsense.handoff_inputs import ROOT
from tests.test_agent3_advisor import (  # noqa: F401 - fixtures reused
    Fake, codes, draft_for, retriever, run, sent_payload, supported, view,
)

RUN = ROOT/'data/experiments/agent3_policy_eval_v1'
TOPIC = RUN/'topics/topic__cluster_fb1dce1eeeedc4cb__topic_1.json'
FIRST = ('Two QA tutors and a tutor ask how to weigh requested format against factual accuracy; the supplied threads do '
         'not settle their preference questions.')
SECOND = 'The current FAQ requires separate scoring and case evidence, not a universal priority rule.'


@pytest.fixture(scope='module')
def recorded():
    result = json.loads(TOPIC.read_text(encoding='utf-8'))['result']
    raw = json.loads(_json_text(next(c['raw'] for c in result['model_calls'] if c['stage'] == 'draft')))
    return result, raw, result['evidence_ledger']


def split(raw, first_depends=(), second_depends=()):
    """The recorded draft with its recorded summary text written as two sentences (no word changed)."""
    value = {k: v for k, v in raw.items() if k != 'summary'}
    return AdvisorDraft.model_validate({**value, 'contract_version': 'agent3-advisor-draft-v9', 'summary_sentences': [
        {'text': FIRST, 'support_claim_ids': ['c1', 'c6'], 'depends_on': list(first_depends)},
        {'text': SECOND, 'support_claim_ids': ['c2'], 'depends_on': list(second_depends)}]})


def replay_verdicts(result, ledger, stmts, same_inputs=None):
    """Replay the recorded grounding for these statements. same_inputs=True simulates a run recorded with the current
    grounding rules, evidence view and schema (to test the statement-level binding on its own)."""
    client = ReplayClient(RUN)
    if same_inputs is not None:
        client.grounding_inputs_same = same_inputs
    payload = {'scenario_id': result['scenario']['id'], 'statements': stmts,
               'member_threads': [{'evidence_id': e} for e in ledger if e.startswith('m:')],
               'retrieved_sources': [{'evidence_id': e} for e in ledger if not e.startswith('m:')]}
    judged = {v['statement_id']: v['verdict'] for v in client._judgment(payload, client.recorded[payload['scenario_id']])['verdicts']}
    return judged, {e['statement_id']: e for e in client.reuse_log}


def test_recorded_summary_is_one_sentence_pair_and_the_judge_was_right(recorded):
    """RECORDED. The withheld summary is exactly the two sentences above; the judge's reason concerns only the first;
    the starter it names asked about format versus prose, while the claim that kept the questions apart passed."""
    result, raw, ledger = recorded
    by_id = {s['statement_id']: s for s in result['grounding']['statements']}
    assert raw['summary'] == f'{FIRST} {SECOND}' and by_id['summary']['verdict'] == 'PARTIALLY_SUPPORTED'
    assert 'JSON-versus-prose starter' in by_id['summary']['rationale'] and by_id['claim:c1']['verdict'] == 'SUPPORTED'
    asked = {a['user_id']: ledger[a['evidence_id']]['excerpt'] for a in by_id['claim:c1']['attributions']}
    assert 'accurate' in asked['U019'] and 'accuracy' in asked['U018']
    assert 'prose' in asked['U007'] and 'accura' not in asked['U007']  # format versus presentation, not accuracy
    assert result['card']['summary'].startswith("The advisor's summary is not shown")


def test_replaying_the_recorded_draft_reuses_the_recorded_verdict_only_with_unchanged_inputs(recorded):
    """RECORDED. Unchanged text, evidence and context: the recorded PARTIALLY_SUPPORTED is reused, never upgraded. The
    recorded run's grounding rules and evidence view predate prompts v11, so in fact nothing is reused (PENDING)."""
    result, raw, ledger = recorded
    draft = AdvisorDraft.model_validate(raw)
    stmts = [s for s in statements(draft, ledger) if s['statement_id'] == 'summary']
    judged, log = replay_verdicts(result, ledger, stmts, same_inputs=True)
    assert judged == {'summary': 'PARTIALLY_SUPPORTED'} and log['summary']['reused']
    judged, log = replay_verdicts(result, ledger, stmts)
    assert judged == {} and log['summary']['reason'].startswith('grounding rules, evidence view or schema changed')
    assert shown_summary(draft, lambda sid: judged.get(sid) == 'SUPPORTED') == (None, [])


def test_sentences_need_new_judgment_in_replay(recorded):
    """RECORDED. The same words as two sentences are new statements: replay has no verdict for them (nothing is
    carried over from the whole-summary verdict), so nothing is shown."""
    result, raw, ledger = recorded
    stmts = [s for s in statements(split(raw), ledger) if s['kind'] == 'SUMMARY']
    assert [s['statement_id'] for s in stmts] == ['summary:s1', 'summary:s2']
    judged, log = replay_verdicts(result, ledger, stmts)
    assert judged == {} and {e['reason'] for e in log.values()} == {'not recorded'}
    assert shown_summary(split(raw), lambda sid: judged.get(sid) == 'SUPPORTED')[0] is None


def test_changed_dependency_needs_new_judgment(recorded, monkeypatch):
    """RECORDED + DETERMINISTIC. A recorded sentence verdict is reused only while its dependencies are unchanged."""
    result, raw, ledger = recorded
    old = {s['statement_id']: {**s, 'model_verdict': 'SUPPORTED', 'verdict': 'SUPPORTED'}
           for s in statements(split(raw), ledger) if s['kind'] == 'SUMMARY'}
    client = ReplayClient(RUN)
    client.grounding_inputs_same = True  # isolate the statement-level binding
    rec = {**client.recorded[result['scenario']['id']], 'statements': old}
    changed = [s for s in statements(split(raw, second_depends=[1]), ledger) if s['kind'] == 'SUMMARY']
    payload = {'scenario_id': result['scenario']['id'], 'statements': changed,
               'member_threads': [{'evidence_id': e} for e in ledger if e.startswith('m:')],
               'retrieved_sources': [{'evidence_id': e} for e in ledger if not e.startswith('m:')]}
    judged = {v['statement_id'] for v in client._judgment(payload, rec)['verdicts']}
    assert judged == {'summary:s1'} and client.reuse_log[-1]['reason'] == 'content changed'


def test_sentence_carries_the_attributions_and_evidence_of_its_claims(recorded):
    """DETERMINISTIC. The first sentence is judged against the three askers' own messages (and the claim it condenses
    about the threads), not against every material claim, so the judge sees whom the group wording covers."""
    _, raw, ledger = recorded
    s1 = next(s for s in statements(split(raw), ledger) if s['statement_id'] == 'summary:s1')
    assert {a['user_id'] for a in s1['attributions'] if a['relation'] == 'AUTHOR'} >= {'U019', 'U007', 'U018'}
    assert 'k:rp-tie-calibration-outcome@1.0:053fe48a' not in s1['evidence_ids']
    s2 = next(s for s in statements(split(raw), ledger) if s['statement_id'] == 'summary:s2')
    assert s2['evidence_ids'] == ['k:response-preference-faq@1.1:fa9b6a3d'] and 'attributions' not in s2


def test_group_count_is_checked_against_the_sentences_own_people(recorded):
    """DETERMINISTIC. Counted against the authors of the claims a sentence condenses: five askers over c1's three
    authors fails, although the whole-summary evidence (every material claim) has five distinct authors."""
    _, raw, ledger = recorded
    value = {k: v for k, v in raw.items() if k != 'summary'}
    wide = 'Five tutors ask how to weigh requested format against response quality.'
    sentence = AdvisorDraft.model_validate({**value, 'summary_sentences': [{'text': wide, 'support_claim_ids': ['c1']}]})
    whole = AdvisorDraft.model_validate({**raw, 'summary': wide})
    issue = lambda d: [i for i in presentation_issues(d, ledger) if i['statement_id'].startswith('summary')]  # noqa: E731
    assert [i['code'] for i in issue(sentence)] == ['PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']
    assert issue(whole) == []


@pytest.mark.parametrize('verdicts, depends, shown, held', [
    ({'summary:s1': 'PARTIALLY_SUPPORTED'}, (), SECOND, []),                      # the recorded failure, per sentence
    ({'summary:s1': 'PARTIALLY_SUPPORTED'}, (1,), None, ['summary:s2']),         # the second refers back: withheld too
    ({}, (), f'{FIRST} {SECOND}', []),                                            # both supported: shown as written
    ({'claim:c2': 'UNSUPPORTED'}, (), FIRST, ['summary:s2']),                     # condensed claim withheld
    ({'summary:s1': 'PENDING', 'summary:s2': 'PENDING'}, (), None, []),           # unjudged is never shown
])
def test_display_selection(recorded, verdicts, depends, shown, held):
    """PREPARED verdicts, DETERMINISTIC selection; the shown text is the drafted sentences, never repaired."""
    _, raw, _ = recorded
    ok = lambda sid: verdicts.get(sid, 'SUPPORTED') == 'SUPPORTED'  # noqa: E731
    text, kept_back = shown_summary(split(raw, second_depends=depends), ok)
    assert text == shown and [sid for sid, _ in kept_back] == held


def test_contract_rules():
    """DETERMINISTIC. Sentences condense claims of the draft, depend only on earlier sentences, and `summary` is their
    text; a draft without sentences keeps one summary judged as a whole."""
    base = {'reasoning': 'r', 'evidence_sufficiency': 'SUFFICIENT', 'severity': {'level': 'LOW', 'rationale': 'x'},
            'confidence': 0.5, 'open_confirmation': 'NONE',
            'claims': [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': 'A tutor asks.', 'evidence_ids': ['m:x']}]}
    one = {'text': 'A tutor asks.', 'support_claim_ids': ['c1']}
    assert AdvisorDraft.model_validate({**base, 'summary_sentences': [one]}).summary == 'A tutor asks.'
    for bad in ({'summary_sentences': [{**one, 'support_claim_ids': ['c9']}]},
                {'summary_sentences': [{**one, 'depends_on': [1]}]},
                {'summary_sentences': [one], 'summary': 'Something else.'},
                {}):
        with pytest.raises(ValueError):
            AdvisorDraft.model_validate({**base, **bad})
    legacy = AdvisorDraft.model_validate({**base, 'summary': 'A tutor asks.', 'contract_version': 'agent3-advisor-draft-v8'})
    assert [s['statement_id'] for s in statements(legacy, {'m:x': {}}) if s['kind'] == 'SUMMARY'] == ['summary']


# --- End to end (PREPARED judge; the advisor's own routing and display) ----------------------------------------------

SCENARIO = 'json_vs_prose'


def grounded(client):
    return sent_payload(next(text for stage, text in client.calls if stage == 'grounding'))['statements']


def sentence_draft(payload, second_depends=()):
    starters = [i for i in payload['member_evidence'] if i['author_id'] == i['thread_starter_id']][:3]
    asked = 'Three members ask how to weigh requested format against response quality.'
    base = draft_for(payload)
    claims = [{'claim_id': 'c1', 'kind': 'INCIDENT_FACT', 'text': asked, 'evidence_ids': [i['evidence_id'] for i in starters],
               'attributions': [{'user_id': i['author_id'], 'relation': 'AUTHOR', 'evidence_id': i['evidence_id']}
                                for i in starters]}] + [c for c in base['claims'] if c['claim_id'] == 'c2']
    assert len(starters) == 3 and len(claims) == 2
    return {**base, 'summary': None, 'claims': claims, 'summary_sentences': [
        {'text': asked, 'support_claim_ids': ['c1']},
        {'text': 'Current guidance covers it.', 'support_claim_ids': ['c2'], 'depends_on': list(second_depends)}]}


def test_one_unsupported_sentence_keeps_the_other_and_still_routes_to_review(retriever, view):
    client = Fake(draft=sentence_draft, grounding=lambda p: supported(p, **{'summary:s1': 'PARTIALLY_SUPPORTED'}))
    result = run(SCENARIO, client, retriever, view)
    card = result['card']
    assert card['summary'] == 'Current guidance covers it.'
    assert card['card_line'] == 'NEEDS_REVIEW' and 'GROUNDING_FAILURE' in codes(result)
    assert any('summary:s1' in r['detail'] for r in card['needs_review_reasons'] if r['code'] == 'GROUNDING_FAILURE')
    assert result['grounding']['status'] != 'PASSED'
    sent = next(s for s in grounded(client) if s['statement_id'] == 'summary:s1')
    assert len(sent['attributions']) == 3


def test_a_sentence_referring_back_to_a_withheld_one_is_not_shown(retriever, view):
    client = Fake(draft=lambda p: sentence_draft(p, second_depends=[1]),
                  grounding=lambda p: supported(p, **{'summary:s1': 'PARTIALLY_SUPPORTED'}))
    result = run(SCENARIO, client, retriever, view)
    assert result['card']['summary'].startswith("The advisor's summary is not shown")
    assert 'not shown because it depends on text that was not shown' in result['card']['reasoning']
    sent = next(s for s in grounded(client) if s['statement_id'] == 'summary:s2')
    assert sent['depends_on'] == ['summary:s1']


def test_unjudged_sentence_is_not_shown_and_grounding_does_not_pass(retriever, view):
    def judge(payload):
        out = supported(payload)
        return {**out, 'verdicts': [v for v in out['verdicts'] if v['statement_id'] != 'summary:s2']}
    result = run(SCENARIO, Fake(draft=sentence_draft, grounding=judge), retriever, view)
    assert 'Current guidance covers it.' not in result['card']['summary'] and result['grounding']['status'] != 'PASSED'
