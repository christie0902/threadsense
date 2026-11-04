"""Flag-impact assessment in the final grounding call (opt-in shadow; zero calls).

PREPARED: the judge's flag_impacts entries are hand-written stand-ins (tests/fixtures/agent3_flag_impact_prepared_
judgments.json and the Fake client below), never model output. DETERMINISTIC: validation, binding, replay reuse and the
recorded Agent 1 context. Production grounding requests and routing are unchanged unless flag_impact=True."""
import json
from pathlib import Path
import socket

import pytest

from threadsense.agents import advisor_pilot as pilot, flag_impact as fi
from threadsense.agents.advisor_contracts import AdvisorDraft
from threadsense.agents.advisor_evidence import Budget
from threadsense.dashboard.runs import Run
from tests.test_agent3_advisor import Fake, draft_for, retriever, run, sent_payload, supported, view  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT/'data/experiments'
PREPARED = json.loads((ROOT/'tests/fixtures/agent3_flag_impact_prepared_judgments.json').read_text(encoding='utf-8'))
saved = pytest.mark.skipif(not (EXP/'agent3_summary_eval_v1').is_dir() or not (ROOT/'data/processed/agent1_verified_v3').is_dir(),
                           reason='saved runs and the Agent 1 lineage base are needed')


def saved_case(run_name, topic_id):
    run = Run(EXP/run_name)
    card_id = next(c for c, v in run.cards.items() if v['lineage'].get('topic_id') == topic_id)
    card, result = run.cards[card_id], run.topics[card_id]['result']
    return run, card, result, *fi.prepare_saved(card, result, run.flag_source)


@saved
@pytest.mark.parametrize('name', sorted(PREPARED['cases']))
def test_prepared_judgments_are_validated_conservatively(name):
    case = PREPARED['cases'][name]
    _, _, _, prepared, verdicts, states = saved_case(case['run'], case['topic_id'])
    out = {a.flag_id: a for a in fi.validate(case['judgments'], prepared, verdicts=verdicts, member_states=states,
                                             source='PREPARED')}
    assert {k: out[k].impact for k in case['expected']} == case['expected']
    for a in out.values():
        assert a.retains_review == (a.impact != 'INDEPENDENT')
        assert a.judgment_source == ('PREPARED' if a.model_impact else 'NONE')


@saved
def test_displayed_member_resolution_stays_relevant_and_diagnostics_only_state_may_not():
    _, _, _, prepared, verdicts, states = saved_case('agent3_writing_eval_v17_v1', 'cluster_f944891544b06f79/topic_2')
    member = 'member_42af0c53b9dee102697caa09'
    deps = next(d for p, d in zip(prepared['provenance'], prepared['dependencies']) if p['member_ids'] == [member])
    assert next(l for l in deps['links'] if l['element'] == 'TOPIC_RESOLUTION')['relation'] == 'INVARIANT'
    assert states[member] == 'RESOLVED_IN_THREAD'  # counted in the displayed thread status
    case = PREPARED['cases']['tie_displayed_member_mixed_topic']
    [a] = [x for x in fi.validate(case['judgments'], prepared, verdicts=verdicts, member_states=states, source='PREPARED')
           if x.flag_id == 'flag_4e3e3ce94ee96df81ece44da0fb0da4f']
    assert a.model_impact == 'INDEPENDENT' and a.impact == 'AFFECTS' and 'thread status' in a.validation_issues[0]


@saved
def test_projection_gap_is_not_sent_and_keeps_its_rule():
    _, _, _, prepared, verdicts, states = saved_case('agent3_writing_eval_v17_v1', None)
    assert len(prepared['provenance']) == 3 and len(prepared['inputs']) == 2
    out = fi.validate([], prepared, verdicts=verdicts, member_states=states, source='PREPARED')
    assert [(a.status, a.impact, a.retains_review) for a in out] == [
        ('NOT_ASSESSED', 'UNKNOWN', True), ('NOT_ASSESSED', 'UNKNOWN', True), ('GROUPING_RULE', 'UNKNOWN', True)]


@saved
def test_record_binds_inputs_and_replay_reuses_only_unchanged_inputs():
    run, card, result, prepared, verdicts, states = saved_case('agent3_summary_eval_v1', 'cluster_fb1dce1eeeedc4cb/topic_1')
    payload = {'scenario_id': result['scenario']['id'], 'statements': [
        {k: s[k] for k in ('statement_id', 'kind', 'text', 'evidence_ids')} for s in result['grounding']['statements']],
        'member_threads': [{'evidence_id': e} for e in result['evidence_ledger'] if e.startswith('m:')],
        'retrieved_sources': [{'evidence_id': e} for e in result['evidence_ledger'] if not e.startswith('m:')],
        'flag_impacts': prepared['inputs']}
    judgments = [
        {'flag_id': 'flag_135b903cdf5f8a936db129c317c7c3b4', 'impact': 'AFFECTS', 'element_ids': ['thread_status'],
         'explanation': 'Prepared.'}]
    assessed = fi.validate(judgments, prepared, verdicts=verdicts, member_states=states, source='PREPARED')
    record = fi.record(assessed, prepared, payload=payload, ledger=result['evidence_ledger'], card=card)
    assert record.card_text_sha256 == fi.card_text(card) and record.inputs_sha256 == fi.inputs_digest(payload)
    client = pilot.ReplayClient(run.path)
    rec = client.recorded[payload['scenario_id']]
    assert client._judgment(payload, rec)['flag_impacts'] == []  # This older run recorded no flag judgment.
    assert client.reuse_log[-1]['reason'] == 'no flag-impact judgment recorded'
    rec['flag_impact'], client.flag_rules_same = record.model_dump(mode='json'), True
    assert client._judgment(payload, rec)['flag_impacts'] == fi.recorded_judgments(record.model_dump(mode='json'))
    changed = {**payload, 'statements': [{**payload['statements'][0], 'text': 'Changed.'}] + payload['statements'][1:]}
    assert client._judgment(changed, rec)['flag_impacts'] == []
    assert client.reuse_log[-1]['reason'] == 'flag-impact inputs changed'
    client.flag_rules_same = False
    assert client._judgment(payload, rec)['flag_impacts'] == []
    assert client.reuse_log[-1]['reason'] == 'flag-impact rules changed'


def grounding_task(client):
    return sent_payload(next(text for stage, text in client.calls if stage == 'grounding'))


def judge_all(impact_value='AFFECTS'):
    def respond(payload):
        return {**supported(payload), 'flag_impacts': [
            {'flag_id': f['flag_id'], 'impact': impact_value, 'element_ids': ['title'], 'explanation': 'Prepared.'}
            for f in payload.get('flag_impacts', [])]}
    return respond


def test_opt_in_uses_the_same_grounding_request_and_leaves_routing_unchanged(retriever, view):
    plain = Fake(draft=draft_for, grounding=supported)
    base = run('json_vs_prose', plain, retriever, view)
    shadow = Fake(draft=draft_for, grounding=judge_all())
    result = run('json_vs_prose', shadow, retriever, view, flag_impact=True)
    assert [s for s, _ in plain.calls] == [s for s, _ in shadow.calls]  # Same stages: no extra request.
    assert len([s for s, _ in shadow.calls if s == 'grounding']) == 1 and len(shadow.calls) <= 4
    sent, before = grounding_task(shadow), grounding_task(plain)
    assert 'flag_impacts' not in before
    assert fi.FLAG_IMPACT_RULES not in next(t for s, t in plain.calls if s == 'grounding')  # Production request unchanged.
    assert fi.FLAG_IMPACT_RULES in next(t for s, t in shadow.calls if s == 'grounding')
    assert [f['kind'] for f in sent['flag_impacts']] == ['inherited_agent1_review']
    assert sent['flag_impacts'][0]['findings'][0]['category'] == 'RESOLUTION'
    assert sent['flag_impacts'][0]['attempt_errors'][0]['stage'] == 'REVISION_FAILED'
    assert 'flag_impact' not in base and result['flag_impact']['status'] == 'ASSESSED'
    [a] = result['flag_impact']['assessments']
    assert (a['impact'], a['judgment_source'], a['retains_review']) == ('AFFECTS', 'PREPARED', True)
    assert result['flag_impact']['card_text_sha256'] == fi.card_text(result['card'])
    for key in ('card_id', 'card_line', 'needs_review_reasons', 'summary', 'recommended_action'):
        assert result['card'][key] == base['card'][key]


def test_missing_or_failed_flag_judgments_stay_unknown(retriever, view):
    result = run('json_vs_prose', Fake(draft=draft_for, grounding=supported), retriever, view, flag_impact=True)
    [a] = result['flag_impact']['assessments']
    assert (a['status'], a['impact'], a['validation_issues']) == ('NOT_ASSESSED', 'UNKNOWN', ['No judgment returned for this flag.'])
    failed = run('json_vs_prose', Fake(draft=draft_for, grounding=RuntimeError('provider down')), retriever, view, flag_impact=True)
    assert failed['flag_impact']['status'] == 'NOT_ASSESSED' and not failed['flag_impact']['assessments']


def test_projection_gap_end_to_end_keeps_grouping_rule(retriever, view):
    shadow = Fake(draft=draft_for, grounding=judge_all('INDEPENDENT'))
    result = run('submit_failure', shadow, retriever, view, flag_impact=True)
    kinds = [f['kind'] for f in grounding_task(shadow)['flag_impacts']]
    assert 'projection_gap' not in kinds
    gap = next(a for a in result['flag_impact']['assessments'] if a['kind'] == 'projection_gap')
    assert (gap['status'], gap['retains_review']) == ('GROUPING_RULE', True)
    # An INDEPENDENT without a basis is not accepted.
    assert all(a['impact'] == 'UNKNOWN' for a in result['flag_impact']['assessments'] if a['kind'] != 'projection_gap')


def test_agent1_context_is_saved_with_its_hash_for_every_run(retriever, view):
    client = Fake(draft=draft_for, grounding=supported)
    result = run('json_vs_prose', client, retriever, view)
    draft_payload = sent_payload(next(text for stage, text in client.calls if stage == 'draft'))
    [context] = result['agent1_context']
    assert context['content'] == draft_payload['agent1_interpretations']
    entry = next(c for c in result['model_calls'] if c['stage'] == 'draft')
    assert entry['agent1_context'] == {'sha256': context['sha256'], 'boundary': 'NO_HTTP_REQUEST'}
    text = json.dumps(context['content'], ensure_ascii=False)
    assert pilot.sha256(text.encode('utf-8')).hexdigest() == context['sha256']


def test_agent1_context_is_checked_in_the_http_body_actually_sent(monkeypatch):
    """The live client's request is captured at the transport (never sent; dummy key; sockets refused)."""
    import httpx
    for k, v in pilot.QUIET_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-offline-test')
    connect = socket.socket.connect

    def refuse(sock, address, *a, **kw):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            raise OSError('network blocked in test')
        return connect(sock, address, *a, **kw)
    monkeypatch.setattr(socket.socket, 'connect', refuse)

    def capture(transport, request):
        raise RuntimeError('captured, not sent')
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', capture)
    client = pilot.CrewAIClient({**pilot.live_settings('openai/gpt-4o-mini'), 'input_token_limit': None})
    stages = pilot.Stages(client, Budget({'model_calls': 4}), 'boundary')
    context = [{'member_id': 'member_x', 'summary': 'Linh reports the Submit button stays grey — "B" chosen.'}]
    assert stages('draft', {'rules': 'Rules.', 'agent1_interpretations': context}, AdvisorDraft) is None
    entry = stages.log[-1]
    assert entry['status'] == 'FAILED' and entry['agent1_context']['boundary'] == 'IN_HTTP_BODY'
    assert stages.agent1_context() == [{'sha256': entry['agent1_context']['sha256'], 'content': context}]


@saved
def test_older_runs_are_labelled_not_assessed_in_the_dashboard():
    run = Run(EXP/'agent3_summary_eval_v1')
    card_id = next(c for c, v in run.cards.items() if v['lineage'].get('topic_id') == 'cluster_fb1dce1eeeedc4cb/topic_1')
    [flag] = run.flags(card_id)
    assert flag['impact'] == {'status': 'NOT_ASSESSED', 'note': fi.NOT_ASSESSED_NOTE}
    assert flag['provenance']['recovery'] == 'RECOVERED'
