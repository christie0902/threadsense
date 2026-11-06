"""Agent 1 relevance (judgment agent1-relevance-v1, stage v2): judged in the interpretation request, verified
structurally and, for proposed model exclusions, by the semantic verifier, and used only to decide what is clustered. Offline: parsing, verification and the zero-call stage on the cached full run."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from threadsense.agents import thread_relevance as tr
from threadsense.agents.advice_inputs import review_items_from_processing_history
from threadsense.handoff_inputs import load_routed_handoff
from threadsense.routing import ROOT

CANONICAL = ROOT/'data/experiments/threadsense_full_v1/stages/agent1_verify/agent1_verified_v2'
LABELS_PATH = ROOT/'data/evaluation/agent1_thread_relevance_labels_v1.json'
CUTOFF = '2026-10-02T12:00:00Z'
MESSAGES = [{'message_id': '1.1', 'timestamp': '2026-10-01T18:40:12Z'}, {'message_id': '1.2', 'timestamp': '2026-10-01T18:41:00Z'}]


def entry(relevance, *, evidence=('1.1', '1.2'), substantive=(), notice=None, reason='r'):
    return {'version': tr.RELEVANCE_VERSION, 'source': 'AGENT1_MODEL', 'status': 'JUDGED',
            'judgment': tr.ThreadRelevance.model_validate({
                'relevance': relevance, 'reason': reason, 'evidence_message_ids': list(evidence),
                'substantive_message_ids': list(substantive), 'notice': notice}).model_dump(mode='json')}


def decide(e, interpretation=None, cutoff=CUTOFF, semantic='SUPPORTED'):
    """semantic: the verifier's verdict on a proposed exclusion (None: not assessed)."""
    checked = tr.verify(e, MESSAGES, interpretation or {'central_question': None})
    if semantic and tr.needs_assessment(checked, MESSAGES, cutoff):
        checked['semantic'] = {'status': 'ASSESSED', 'verdict': semantic}
    return checked, tr.disposition(checked, MESSAGES, cutoff)


# --- The request: one interpretation call with an extended prompt and schema ------------------------------------

def test_relevance_rides_on_the_interpretation_request():
    from threadsense.agents.thread_interpreter import INTERPRETATION_RULES
    text = tr.prompt()
    assert text.startswith(INTERPRETATION_RULES.partition('\nOutput:\n')[0]) and 'Relevance:' in text
    assert text.index('Relevance:') < text.index('\nOutput:\n') and '{output_schema}' in text
    schema = tr.output_schema()
    assert 'relevance' in schema['required'] and 'authoritative_response_present' not in schema['properties']


def test_an_invalid_relevance_object_never_invalidates_the_interpretation():
    raw = {'thread_id': 't', 'summary': 's', 'central_question': None, 'resolution_state': 'UNRESOLVED',
           'authority_evidence_message_ids': [], 'resolution_rationale': 'r', 'confidence': 0.5}
    good = tr.parse_relevance(None, json.dumps({**raw, 'relevance': entry('PROJECT')['judgment']}))
    assert good['status'] == 'JUDGED' and good['judgment']['relevance'] == 'PROJECT'
    bad = tr.parse_relevance(None, json.dumps({**raw, 'relevance': {'relevance': 'SPAM'}}))
    assert bad['status'] == 'INVALID'
    checked, decided = decide(bad)
    assert checked['verification']['status'] == 'NOT_JUDGED' and decided == {**decided, 'disposition': 'CLUSTER', 'relevance': 'UNCERTAIN'}


# --- Dispositions ------------------------------------------------------------------------------------------------

def test_a_pure_greeting_goes_to_processing_history():
    checked, decided = decide(entry('SOCIAL_ONLY'))
    assert checked['verification']['status'] == 'VERIFIED' and decided['disposition'] == 'PROCESSING_HISTORY'
    assert decided['semantic_verdict'] == 'SUPPORTED'


@pytest.mark.parametrize('semantic', [None, 'CONTRADICTED', 'UNSUPPORTED', 'UNCERTAIN'])
def test_a_model_exclusion_without_a_supported_semantic_verdict_stays_eligible(semantic):
    checked, decided = decide(entry('SOCIAL_ONLY'), semantic=semantic)
    assert checked['verification']['status'] == 'VERIFIED'
    assert decided['disposition'] == 'CLUSTER' and decided['relevance'] == 'UNCERTAIN' and decided['proposed'] == 'SOCIAL_ONLY'
    assert (semantic or 'NOT_ASSESSED') in decided['basis']


@pytest.mark.parametrize('broken, finding', [
    (entry('SOCIAL_ONLY', evidence=('1.1',)), 'must cite every message'),
    (entry('ROUTINE_ADMIN', evidence=('1.1', '9.9')), 'unknown message 9.9'),
    (entry('MIXED'), 'MIXED without substantive messages'),
    (entry('TIME_BOUND_NOTICE'), 'without a notice message')])
def test_an_unverified_exclusion_stays_eligible(broken, finding):
    checked, decided = decide(broken)
    assert checked['verification']['status'] == 'UNVERIFIED' and any(finding in f for f in checked['verification']['findings'])
    assert decided['disposition'] == 'CLUSTER' and decided['relevance'] == 'UNCERTAIN'


def test_a_greeting_label_on_a_thread_with_a_question_is_not_trusted():
    checked, decided = decide(entry('SOCIAL_ONLY'), {'central_question': 'Should this be QN?'})
    assert checked['verification']['status'] == 'UNVERIFIED' and decided['disposition'] == 'CLUSTER'


@pytest.mark.parametrize('kind', ['PROJECT', 'UNCERTAIN'])
def test_observations_without_questions_answered_evidence_and_uncertain_threads_are_clustered(kind):
    _, decided = decide(entry(kind), {'central_question': None, 'resolution_state': 'RESOLVED_IN_THREAD'})
    assert decided['disposition'] == 'CLUSTER'


def test_a_mixed_thread_is_clustered_on_its_substance_and_kept_whole():
    _, decided = decide(entry('MIXED', substantive=('1.2',)))
    assert decided == {**decided, 'disposition': 'CLUSTER', 'relevance': 'MIXED', 'substantive_message_ids': ['1.2']}


def test_missing_and_legacy_judgments_are_uncertain_and_eligible():
    for e in (None, {'status': 'MISSING'}):
        checked, decided = decide(e)
        assert checked['verification']['status'] == 'NOT_JUDGED' and decided['disposition'] == 'CLUSTER'


def test_notices_are_judged_against_the_cutoff_and_expiry_is_not_completion():
    same_day = entry('TIME_BOUND_NOTICE', notice={'message_id': '1.1', 'day_offset': 0, 'local_end_time': '18:00'})
    _, current = decide(same_day)  # no timezone recorded: 6 PM can be as late as 12:30Z next day (UTC+05:30)
    assert current['disposition'] == 'CLUSTER' and current['notice_latest_end_utc'] == '2026-10-02T12:30:00Z'
    _, expired = decide(same_day, cutoff='2026-10-02T12:30:00Z')
    assert expired['disposition'] == 'PROCESSING_HISTORY' and 'not completion' in expired['basis']
    dated = entry('TIME_BOUND_NOTICE', notice={'message_id': '1.2', 'local_date': '2026-09-30', 'local_end_time': '09:00'})
    assert decide(dated)[1]['disposition'] == 'PROCESSING_HISTORY'


# --- The zero-call stage on the cached full run ---------------------------------------------------------------

pytestmark_run = pytest.mark.skipif(not CANONICAL.is_dir(), reason='full live run not present')


@pytestmark_run
def test_the_stage_keeps_every_thread_and_writes_a_loadable_clustering_input(tmp_path):
    labels = tr.load_labels(json.loads(LABELS_PATH.read_text(encoding='utf-8')))
    summary = tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, labels=labels)
    assert (summary['threads'], summary['clustered'], summary['processing_history']) == (177, 174, 3)
    assert summary['by_source'] == {'AUDITED_LABEL': 9, 'MISSING': 168}
    history = json.loads((tmp_path/'rel'/'processing_history.json').read_text(encoding='utf-8'))
    assert sorted(h['relevance'] for h in history) == ['ROUTINE_ADMIN', 'SOCIAL_ONLY', 'SOCIAL_ONLY']
    assert all(h['original_thread']['messages'] and h['agent1_record'] for h in history)
    discussion, announcements, _ = load_routed_handoff(tmp_path/'rel'/'clustering_input'/'interpretations.json')
    assert len(discussion) == 174 and not announcements
    rows = {r['thread_id']: r for r in json.loads((tmp_path/'rel'/'relevance.json').read_text(encoding='utf-8'))['threads']}
    assert rows['1790903659.000050']['disposition'] == 'CLUSTER'  # next-day shift coverage: still upcoming at the cutoff
    assert rows['1790896509.000047']['relevance'] == 'PROJECT'  # answered tie question kept as evidence


@pytestmark_run
def test_an_excluded_thread_keeps_its_review_obligation(tmp_path):
    records = json.loads((CANONICAL/'interpretations.json').read_text(encoding='utf-8'))
    flagged = next(r for r in records if r['review_required'])
    source = json.loads((CANONICAL/flagged['lineage']['source_file']).read_text(encoding='utf-8'))
    ids = [m['message_id'] for m in source['messages']]
    raw = {'contract_version': tr.LABELS_CONTRACT, 'label_source': 'TEST', 'labels': [
        {'label_id': 'test', 'channel_id': flagged['channel_id'], 'thread_id': flagged['thread_id'], 'input_sha256': flagged['input_sha256'],
         'judgment': {'relevance': 'ROUTINE_ADMIN', 'reason': 'test', 'evidence_message_ids': ids, 'substantive_message_ids': [], 'notice': None}}]}
    summary = tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, labels=tr.load_labels(raw))
    assert summary['processing_history'] == 1 and summary['processing_history_obligations'] == 1
    history = json.loads((tmp_path/'rel'/'processing_history.json').read_text(encoding='utf-8'))
    assert history[0]['obligation']['review_reasons'] == flagged['review_reasons']
    items = review_items_from_processing_history([{**history[0], 'member_id': 'member_x'}])
    assert len(items) == 1 and items[0].kind == 'inherited_agent1_review_processing_history'
    queue = json.loads((tmp_path/'rel'/'clustering_input'/'review_queue.json').read_text(encoding='utf-8'))
    assert flagged['thread_id'] not in {q['thread_id'] for q in queue} and len(queue) == sum(r['review_required'] for r in records) - 1


@pytestmark_run
def test_a_label_bound_to_other_input_is_not_applied(tmp_path):
    raw = json.loads(LABELS_PATH.read_text(encoding='utf-8'))
    raw = deepcopy(raw)
    for label in raw['labels']:
        label['input_sha256'] = '0' * 64
    summary = tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, labels=tr.load_labels(raw))
    assert summary['processing_history'] == 0 and summary['by_source'] == {'MISSING': 177}


# --- Semantic verification of proposed exclusions (agent1-relevance-v2), prepared verifier responses -------------

GREETINGS = ('1790901493.000191', '1790911349.000052')
AVATAR, NOISE = '1790894591.000100', '1790856028.000143'
OBSERVATION, OBSERVATION_2 = '1790860406.000119', '1790873741.000176'  # statements without a question


def model_judgments(choices):
    """Agent 1 model relevance entries for chosen threads of the cached export (everything else has none)."""
    out = []
    for record in json.loads((CANONICAL/'interpretations.json').read_text(encoding='utf-8')):
        if record['thread_id'] not in choices:
            continue
        source = json.loads((CANONICAL/record['lineage']['source_file']).read_text(encoding='utf-8'))
        ids = [m['message_id'] for m in source['messages']]
        relevance, substantive = choices[record['thread_id']]
        out.append({'input_sha256': record['input_sha256'], 'relevance': {
            'version': tr.RELEVANCE_VERSION, 'source': 'AGENT1_MODEL', 'status': 'JUDGED', 'judgment': {
                'relevance': relevance, 'reason': f'{relevance.lower()} (test)', 'evidence_message_ids': ids,
                'substantive_message_ids': ids[substantive:substantive + 1] if substantive is not None else [], 'notice': None}}})
    return out


def prepared(verdicts, calls):
    """A verifier stand-in returning prepared ProseComparison responses, parsed as live responses are."""
    def assessor(thread, unit):
        calls.append(thread.thread_id)
        verdict = verdicts[thread.thread_id]
        message = thread.messages[0]
        quote = message.text[:24] if verdict != 'BAD_QUOTE' else 'not in the thread at all'
        raw = json.dumps({'prose_assessments': [{
            'unit_id': unit['unit_id'], 'candidate_text': unit['candidate_text'], 'source_interpretation': 'what the thread says',
            'verdict': 'SUPPORTED' if verdict == 'BAD_QUOTE' else verdict, 'evidence_message_ids': [message.message_id],
            'evidence_quotes': [quote], 'explanation': 'prepared test response'}]})
        return tr.parse_assessment(thread, raw, unit)
    return assessor


@pytestmark_run
def test_the_semantic_verifier_decides_each_proposed_model_exclusion(tmp_path):
    choices = {GREETINGS[0]: ('SOCIAL_ONLY', None), GREETINGS[1]: ('SOCIAL_ONLY', None), AVATAR: ('ROUTINE_ADMIN', None),
               NOISE: ('MIXED', 1), OBSERVATION: ('SOCIAL_ONLY', None), OBSERVATION_2: ('SOCIAL_ONLY', None)}
    verdicts = {GREETINGS[0]: 'SUPPORTED', GREETINGS[1]: 'SUPPORTED', AVATAR: 'SUPPORTED',
                OBSERVATION: 'CONTRADICTED', OBSERVATION_2: 'BAD_QUOTE'}
    calls = []
    summary = tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, interpretations=model_judgments(choices),
                             assessor=prepared(verdicts, calls))
    assert sorted(calls) == sorted(verdicts)  # one request per proposed exclusion; none for MIXED or unjudged threads
    rows = {r['thread_id']: r for r in json.loads((tmp_path/'rel'/'relevance.json').read_text(encoding='utf-8'))['threads']}
    for t in (*GREETINGS, AVATAR):  # pure greetings and routine administration, confirmed
        assert rows[t]['disposition'] == 'PROCESSING_HISTORY' and rows[t]['semantic_verdict'] == 'SUPPORTED'
    assert rows[NOISE]['disposition'] == 'CLUSTER' and rows[NOISE]['relevance'] == 'MIXED' and 'semantic' not in rows[NOISE]['relevance_entry']
    # A false social exclusion of a useful observation without a question: contradicted, so it stays eligible.
    assert rows[OBSERVATION]['disposition'] == 'CLUSTER' and rows[OBSERVATION]['relevance'] == 'UNCERTAIN'
    assert 'CONTRADICTED' in rows[OBSERVATION]['basis']
    # A response that fails the verifier's evidence validation is INVALID: no exclusion.
    assert rows[OBSERVATION_2]['relevance_entry']['semantic']['status'] == 'INVALID' and rows[OBSERVATION_2]['disposition'] == 'CLUSTER'
    assert (summary['clustered'], summary['processing_history']) == (174, 3)
    assert summary['version'] == tr.STAGE_VERSION and summary['semantic_assessments'] == {'CONTRADICTED': 1, 'INVALID': 1, 'SUPPORTED': 3}


@pytestmark_run
def test_without_the_semantic_verifier_model_exclusions_stay_eligible(tmp_path):
    choices = {GREETINGS[0]: ('SOCIAL_ONLY', None), AVATAR: ('ROUTINE_ADMIN', None)}
    summary = tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, interpretations=model_judgments(choices))
    assert summary['processing_history'] == 0 and summary['semantic_assessments'] == {'NOT_ASSESSED': 2}


@pytestmark_run
def test_audited_labels_are_explicit_exclusions_attributed_to_their_source(tmp_path):
    labels = tr.load_labels(json.loads(LABELS_PATH.read_text(encoding='utf-8')))
    tr.build_stage(CANONICAL, tmp_path/'rel', cutoff=CUTOFF, labels=labels, assessor=lambda *a: pytest.fail('no model call'))
    history = json.loads((tmp_path/'rel'/'processing_history.json').read_text(encoding='utf-8'))
    assert len(history) == 3 and {h['relevance_entry']['source'] for h in history} == {'AUDITED_LABEL'}
    assert {h['relevance_entry']['semantic']['status'] for h in history} == {'NOT_REQUIRED'}


def test_the_semantic_request_is_the_verifiers_prose_comparison_with_one_unit():
    from threadsense.agents.prose_comparison import PROSE_RULES
    from threadsense.models import Thread
    records = json.loads((CANONICAL/'interpretations.json').read_text(encoding='utf-8')) if CANONICAL.is_dir() else []
    if not records:
        pytest.skip('full live run not present')
    source = json.loads((CANONICAL/records[0]['lineage']['source_file']).read_text(encoding='utf-8'))
    unit = tr.exclusion_unit({'relevance': 'SOCIAL_ONLY', 'reason': 'Greetings only.'})
    body = tr.semantic_request(Thread.model_validate(source), unit, 'openai/gpt-4.1')
    system, user = body['messages'][0]['content'], json.loads(body['messages'][1]['content'])
    assert system.startswith(PROSE_RULES) and user['candidate_prose_units'] == [unit]
    assert unit['candidate_text'].startswith(tr.CLAIMS['SOCIAL_ONLY']) and len(tr.semantic_fingerprint()) == 64


def test_the_runner_records_relevance_only_when_asked():
    text = (ROOT/'scripts/run_agent1_batch.py').read_text(encoding='utf-8')
    assert 'if args.relevance:' in text and 'config["relevance"]' in text
    assert 'result, relevance = ti.interpret_thread(thread), None' in text  # without --relevance the call is unchanged
