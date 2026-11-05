"""Acceptance safeguards for draft v11 / AdviceCard v4, through the real Advisor path (advise -> grounding_result ->
authorize -> assemble_card) on the current retrieval snapshot. Offline: scripted responses, no model calls.

Responses are the PREPARED fixture (recorded live drafts with hand-written detail sentences; not model output), with
grounding verdicts changed per case.
"""
from copy import deepcopy
import json

import pytest

from threadsense.agents import advisor_pilot as pilot, overnight
from threadsense.agents.advice_inputs import load_effective_view
from threadsense.agents.advisor_checks import sufficiency_verdict
from threadsense.agents.advisor_contracts import ActionSufficiency
from threadsense.agents.advisor_evidence import Budget
from threadsense.dashboard.review import review_view
from threadsense.routing import ROOT
from threadsense.severity_rubric import load_rubric

PREPARED = json.loads((ROOT/'tests/fixtures/agent3_presentation_prepared_responses.json').read_text(encoding='utf-8'))['responses']
SUBMIT, TIES, GREETINGS = 'gap:routed_440e64c7fbdcc49f', 'topic:cluster_f944891544b06f79/topic_1', 'topic:cluster_be4e3bac742eccb3/topic_1'

pytestmark = pytest.mark.skipif(not (overnight.INDEX_DIR/'manifest.json').is_file(), reason='retrieval snapshot not built')


@pytest.fixture(scope='module')
def env():
    view = load_effective_view(pilot.HANDOFF)
    retriever = overnight.open_snapshot(overnight.INDEX_DIR)
    yield view, retriever, {w['work_id']: w for w in overnight.plan(view)}
    retriever.client.close()


class Client:
    label = 'SCRIPTED_MOCK'

    def __init__(self, responses):
        self.responses = responses

    def complete(self, stage, payload, schema):
        return json.dumps(self.responses[stage], ensure_ascii=False)


def advise(env, work_id, *, verdicts=None, draft=None):
    view, retriever, work = env
    responses = deepcopy(PREPARED[work_id])
    if draft:
        draft(responses['draft'])
    given = {v['statement_id']: v for v in responses['grounding']['verdicts']}
    for sid, verdict in (verdicts or {}).items():
        if verdict is None:
            given.pop(sid, None)
        else:
            given[sid] = {'statement_id': sid, 'verdict': verdict, 'rationale': 'Test verdict.'}
    responses['grounding']['verdicts'] = list(given.values())
    w = work[work_id]
    scenario = {'id': work_id, 'candidate_group_id': w['candidate_group_id'], 'focus': w['topic_name'] or 'projection gap',
                **({'topic_id': w['topic_id']} if w['topic_id'] else {})}
    return pilot.advise(scenario, view=view, retriever=retriever, client=Client(responses), budget=Budget(overnight.PER_TOPIC),
                        rubric=load_rubric(None), run_id='safeguards', as_of=retriever.manifest['cutoff'])


def reasons(card):
    return sorted(r['code'] for r in card['needs_review_reasons'])


def displayed(card):
    action = card['recommended_action'] or {}
    return ' '.join([card['summary'], card['reasoning'], *card['details'], *card['review_notes'],
                     card['next_step'].get('rationale') or '', card['next_step'].get('explanation') or '',
                     *(action.get(k) or '' for k in ('instruction', 'rationale', 'draft_text', 'scope_note'))])


# ---- Safeguard 1: unsupported detail sentences and their dependents -------------------------------------------------

def test_unsupported_detail_and_its_dependent_are_absent_everywhere_and_do_not_route_review(env):
    base = advise(env, SUBMIT, verdicts={'detail:d4': 'SUPPORTED'})['card']
    held = advise(env, SUBMIT)['card']  # fixture: d4 UNSUPPORTED, d5 depends on d4
    texts = [s['text'] for s in PREPARED[SUBMIT]['draft']['detail_sentences']]
    assert len(base['details']) == 6 and held['details'] == [texts[i] for i in (0, 1, 2, 5)]
    for text in texts[3:5]:
        assert text not in displayed(held)
    # An optional presentation omission is not a review reason; the recommendation is unchanged.
    assert reasons(held) == reasons(base) == ['HIGH_SEVERITY', 'INHERITED_FLAG']
    assert held['checks']['grounding'] == base['checks']['grounding'] == 'PASSED'
    assert held['recommended_action'] == base['recommended_action']


def test_a_detail_sentence_on_a_failed_claim_is_withheld_and_the_claim_is_the_review_reason(env):
    result = advise(env, SUBMIT, verdicts={'detail:d4': 'SUPPORTED', 'claim:c11': 'UNSUPPORTED'})
    card = result['card']
    texts = [s['text'] for s in PREPARED[SUBMIT]['draft']['detail_sentences']]
    assert texts[3] not in card['details'] and texts[4] not in card['details']  # both condense c11
    assert 'GROUNDING_FAILURE' in reasons(card)
    failure = next(r for r in card['needs_review_reasons'] if r['code'] == 'GROUNDING_FAILURE')
    assert 'claim:c11' in failure['detail'] and 'detail:' not in failure['detail']


def test_review_view_lists_withheld_detail_as_an_omission_not_a_dispute(env):
    result = advise(env, SUBMIT)
    view = review_view(result['card'], result)
    other = {w['statement_id']: w for w in view['withheld'] if not w['blocking']}
    assert {'detail:d4', 'detail:d5'} <= set(other)
    assert not any(i['code'] == 'GROUNDING_FAILURE' for i in view['items'])
    assert not any(c['kind'] == 'WITHHELD' for c in view['checks'])  # not in "What to check"


def test_detail_sentences_can_never_be_action_premises():
    sufficiency = ActionSufficiency(verdict='SUFFICIENT', essential_statement_ids=['detail:d1'], rationale='x')
    final = {'detail:d1': 'SUPPORTED', 'claim:c1': 'SUPPORTED'}
    assert sufficiency_verdict(['claim:c1'], sufficiency, final, final) == 'ESSENTIAL_ID_NOT_A_PREMISE'
    raw = deepcopy(PREPARED[SUBMIT]['draft'])
    raw['proposed_action']['support_claim_ids'].append('detail:d1')
    with pytest.raises(ValueError, match='Action support must reference claims'):
        pilot.AdvisorDraft.model_validate(raw)


# ---- Safeguard 2: "No action needed" needs a supported action:no_action ---------------------------------------------

@pytest.mark.parametrize('verdict', [None, 'PARTIALLY_SUPPORTED', 'UNSUPPORTED'])
def test_missing_or_failed_no_action_judgment_is_no_intervention_proposed(env, verdict):
    supported = advise(env, TIES)['card']
    card = advise(env, TIES, verdicts={'action:no_action': verdict})['card']
    assert supported['next_step']['status'] == 'NO_ACTION_NEEDED'
    assert card['next_step']['status'] == 'NO_INTERVENTION_PROPOSED' and card['next_step']['rationale'] is None
    assert PREPARED[TIES]['draft']['proposed_action']['rationale'] not in displayed(card)
    # Review requirements are unchanged either way (the failed severity assessment keeps Needs Review).
    assert card['card_line'] == supported['card_line'] == 'NEEDS_REVIEW'
    assert reasons(card) == reasons(supported) == ['GROUNDING_FAILURE', 'OTHER']


def test_rejected_no_action_reason_is_never_sent_and_never_no_action_needed(env):
    def leak(draft):
        draft['proposed_action']['rationale'] += ' See member_4ae1700632c4a55ae1a24a4d.'
    result = advise(env, TIES, draft=leak)  # the judge's SUPPORTED verdict is ignored for a rejected statement
    statement = next(s for s in result['grounding']['statements'] if s['statement_id'] == 'action:no_action')
    assert statement['verdict'].startswith('REJECTED_')
    assert result['card']['next_step']['status'] == 'NO_INTERVENTION_PROPOSED'
    assert reasons(result['card']) == ['GROUNDING_FAILURE', 'OTHER']


def test_no_action_state_never_adds_or_removes_review(env):
    supported = advise(env, GREETINGS)['card']
    unjudged = advise(env, GREETINGS, verdicts={'action:no_action': None})['card']
    assert (supported['card_line'], supported['next_step']['status']) == ('OBSERVATION', 'NO_ACTION_NEEDED')
    assert (unjudged['card_line'], unjudged['next_step']['status']) == ('OBSERVATION', 'NO_INTERVENTION_PROPOSED')
    assert reasons(unjudged) == reasons(supported) == []
