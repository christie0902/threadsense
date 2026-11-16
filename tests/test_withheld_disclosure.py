"""Statements withheld from a card never reach a reviewer: not through the card-detail API (its Technical view), the
feedback targets or feedback history, and not through the static demo bundle, which is a snapshot of that API.

Before dashboard/disclosure.py, `details.diagnostics[*].text` and `targets.statements[*].text` served every withheld
statement verbatim (46 withheld statements on 26 cards of the accepted briefing). The saved run files keep the text
for audit and replay; this checks only what is served. Zero model calls."""
import json
import re
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.dashboard import disclosure
from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.routing import ROOT

RUN = ROOT/'data/experiments/threadsense_full_v1_combined_v2'
BUNDLE = ROOT/'web/demo/briefing.json'
CARD = 'card_a03615c8bc678a84c906d5831a4ba1b0'  # Fictional contact details: the README's worked example.
WITHHELD = {'claim:c5': 'REJECTED_SOURCE_FACT_PRESENTS_HISTORY_AS_CURRENT',
            'alternative:observe_existing_review': 'UNSUPPORTED',
            'summary:s2': 'SUPPORTED'}  # SUPPORTED, but withheld because it depends on claim:c5.
REASONS = ['HIGH_SEVERITY', 'INHERITED_FLAG', 'TEMPORAL_CONFLICT', 'GROUNDING_FAILURE']


def result_of(run, card_id):
    topic = run.topics.get(card_id) or {}
    return topic.get('result') or topic


def withheld_texts(run, card_id):
    result = result_of(run, card_id)
    held = disclosure.withheld_ids(result)
    texts = {d['statement_id']: d['text'] for d in result.get('diagnostics') or [] if d.get('text')}
    texts |= {s['statement_id']: s['text'] for s in (result.get('grounding') or {}).get('statements') or []
              if s['statement_id'] in held and s.get('text')}
    shown = {s['text'] for s in (result.get('grounding') or {}).get('statements') or []
             if s['statement_id'] not in held and s.get('text')}
    return {k: v for k, v in texts.items() if v not in shown}  # The same words shown as another, supported statement.


def strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, str):
        yield value


def served_copies(texts, *bodies):
    """Withheld statement IDs copied into the given responses: a served string holds the whole text, or more than a
    quarter of its 12-word runs. Lower overlap is shared wording (a withheld draft reuses phrases of supported claims,
    source excerpts and the judge's recorded reason, which are served on purpose)."""
    words = lambda s: ' '.join(re.findall(r"[\w'’]+", s.lower()))
    served = [words(s) for b in bodies for s in strings(b)]
    hits = []
    for sid, text in texts.items():
        w = words(text).split()
        runs = {' '.join(w[i:i + 12]) for i in range(max(1, len(w) - 11))}
        if any(words(text) in s or sum(r in s for r in runs) * 4 > len(runs) for s in served):
            hits.append(sid)
    return sorted(hits)


@pytest.fixture(scope='module')
def served(tmp_path_factory):
    root = tmp_path_factory.mktemp('runs')
    shutil.copytree(RUN, root/RUN.name, ignore=shutil.ignore_patterns('screenshots'))
    client = TestClient(create_app(catalog=Catalog([root]), store=DecisionStore(root/'d.sqlite3'), session_actor='U006'))
    return client, Run(root/RUN.name)


def test_saved_artifacts_still_hold_the_withheld_text_for_audit_and_replay():
    run = Run(RUN)
    texts = withheld_texts(run, CARD)
    assert set(texts) == set(WITHHELD)
    verdicts = {s['statement_id']: s['verdict'] for s in result_of(run, CARD)['grounding']['statements']}
    assert {sid: verdicts[sid] for sid in WITHHELD} == WITHHELD
    assert len(verdicts) == 41


def test_card_detail_serves_ids_verdicts_and_reasons_but_no_withheld_text(served):
    client, run = served
    texts = withheld_texts(run, CARD)
    body = client.get(f'/api/runs/{RUN.name}/cards/{CARD}').json()
    assert served_copies(texts, body) == []
    diagnostics = {d['statement_id']: d for d in body['details']['diagnostics']}
    assert set(diagnostics) == set(WITHHELD)
    for sid, verdict in WITHHELD.items():
        d = diagnostics[sid]
        assert (d['verdict'], d['text'], d['text_withheld']) == (verdict, None, True)
    assert diagnostics['summary:s2']['withheld_because'] == 'depends on withheld claim:c5'
    assert diagnostics['alternative:observe_existing_review']['rationale']  # The judge's recorded reason stays.
    # Review reasons and the approved card content still render from the same response.
    assert [r['code'] for r in body['card']['needs_review_reasons']] == REASONS
    assert [r['code'] for r in body['details']['needs_review_reasons']] == REASONS
    assert {w['statement_id'] for w in body['review']['withheld']} == set(WITHHELD)
    why = {w['statement_id']: w['why'] for w in body['review']['withheld']}
    assert why['summary:s2'] == 'it depends on another withheld statement (finding (source fact))'  # was 'supported'
    supported = [s['text'] for s in result_of(run, CARD)['grounding']['statements']
                 if s['statement_id'].startswith('summary:') and s['statement_id'] not in WITHHELD]
    assert supported and all(s in body['card']['summary'] for s in supported)
    assert body['card']['recommended_action']['draft_text']


def test_feedback_targets_and_history_hide_withheld_text_and_the_stored_report_keeps_it(served):
    client, run = served
    texts = withheld_texts(run, CARD)
    base = f'/api/runs/{RUN.name}/cards/{CARD}/feedback'
    targets = {s['id']: s for s in client.get(base).json()['targets']['statements']}
    assert len(targets) == 41
    assert all((targets[sid]['text'], targets[sid]['text_withheld']) == (None, True) for sid in WITHHELD)
    assert all(s['text'] and 'text_withheld' not in s for sid, s in targets.items() if sid not in WITHHELD)
    posted = client.post(base, headers={'Idempotency-Key': 'withheld-1'}, json={
        'actor_id': 'U006', 'category': 'VERIFIER_FALSE_REJECTION', 'target_kind': 'STATEMENT', 'target_id': 'claim:c5',
        'what_is_wrong': 'The help page copy is described as superseded, not as current.', 'use_in_future_runs': False})
    assert posted.status_code == 201
    history = client.get(base).json()['history']
    assert served_copies(texts, posted.json(), history, client.get(f'/api/runs/{RUN.name}/feedback').json()) == []
    assert history[0]['report']['target']['text_withheld'] is True
    stale = client.post(f"{base.rsplit('/cards', 1)[0]}/feedback/{history[0]['feedback_id']}/actions",
                        headers={'Idempotency-Key': 'withheld-2'},
                        json={'action': 'WITHDRAW', 'actor_id': 'U006', 'expected_head': 'not-the-head'})
    assert stale.status_code == 409 and served_copies(texts, stale.json()) == []
    stored = DecisionStore(run.path.parent/'d.sqlite3').feedback(feedback_id=history[0]['feedback_id'])
    assert stored[0]['report']['target']['earlier_text'] == texts['claim:c5']


def test_no_card_of_the_accepted_briefing_serves_a_withheld_statement(served):
    client, run = served
    exposed, checked, statements = {}, 0, 0
    for card_id in run.cards:
        texts = withheld_texts(run, card_id)
        if not texts:
            continue
        checked += 1
        statements += len(texts)
        detail = client.get(f'/api/runs/{RUN.name}/cards/{card_id}').json()
        feedback = client.get(f'/api/runs/{RUN.name}/cards/{card_id}/feedback').json()
        if hits := served_copies(texts, detail, feedback):
            exposed[card_id] = hits
    assert (checked, statements, exposed) == (26, 46, {})  # every withheld (card, statement) pair


def test_static_demo_bundle_has_no_withheld_text_for_the_fictional_contact_card():
    bundle = json.loads(BUNDLE.read_text(encoding='utf-8'))
    run = Run(RUN)
    texts = withheld_texts(run, CARD)
    base = f"/api/runs/{bundle['run_key']}"
    detail = bundle['responses'][f'{base}/cards/{CARD}']['body']
    feedback = bundle['responses'][f'{base}/cards/{CARD}/feedback']['body']
    [item] = [c for c in bundle['responses'][f'{base}/brief']['body']['cards'] if c['card']['card_id'] == CARD]
    assert served_copies(texts, detail, feedback, item) == []
    assert [r['code'] for r in item['card']['needs_review_reasons']] == REASONS
    assert {w['statement_id'] for w in item['review']['withheld']} == set(WITHHELD)
    assert all(d['text_withheld'] for d in detail['details']['diagnostics'])
    assert item['card']['summary'] == run.cards[CARD]['summary']


def test_static_demo_bundle_holds_none_of_the_27_withheld_only_texts():
    """The 46 withheld statements carry 37 distinct texts; 10 of them are templated sentences ("U008 reports … being
    affected") that other cards show as supported statements. The other 27 are never shown anywhere and must not be
    anywhere in the public bundle."""
    run, held, shown = Run(RUN), set(), set()
    for card_id in run.cards:
        result = result_of(run, card_id)
        ids = disclosure.withheld_ids(result)
        held |= {d['text'] for d in result.get('diagnostics') or [] if d['statement_id'] in ids}
        shown |= {s['text'] for s in (result.get('grounding') or {}).get('statements') or [] if s['statement_id'] not in ids}
    only = held - shown
    assert (len(held), len(held & shown), len(only)) == (37, 10, 27)
    text = BUNDLE.read_text(encoding='utf-8')
    assert [t[:60] for t in only if json.dumps(t, ensure_ascii=False)[1:-1] in text] == []


def test_withheld_ids_include_dependent_supported_statements_and_unjudged_ones():
    result = {'grounding': {'statements': [{'statement_id': 'a', 'kind': 'CLAIM', 'verdict': 'SUPPORTED', 'text': 'shown'},
                                           {'statement_id': 'b', 'kind': 'SUMMARY', 'verdict': 'SUPPORTED', 'text': 'depends on c'},
                                           {'statement_id': 'c', 'kind': 'CLAIM', 'verdict': 'UNSUPPORTED', 'text': 'rejected'},
                                           {'statement_id': 'd', 'kind': 'CLAIM', 'verdict': 'NOT_JUDGED', 'text': 'pending'}]},
              'diagnostics': [{'code': 'WITHHELD_STATEMENT', 'statement_id': 'b', 'text': 'depends on c',
                               'verdict': 'SUPPORTED', 'withheld_because': 'depends on withheld c'}]}
    assert disclosure.withheld_ids(result) == {'b', 'c', 'd'}
    assert disclosure.diagnostics(result)[0]['text'] is None and disclosure.diagnostics({}) is None
    assert [s['text'] for s in disclosure.statements(result)] == ['shown', None, None, None]
    assert [s['text'] for s in disclosure.statements(result, reveal=True)] == ['shown', 'depends on c', 'rejected', 'pending']
