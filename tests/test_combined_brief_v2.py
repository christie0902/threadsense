"""combined-briefing-v2: the combined briefing with the two targeted live re-groundings applied (overlap and format cards).
Counts, labels, export, and decision isolation against combined v1. Zero model calls."""
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.dashboard.app import create_app
from threadsense.dashboard.decision_sources import decision_markdown, export, ingest
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT/'data/experiments'
V2, V1 = 'threadsense_full_v1_combined_v2', 'threadsense_full_v1_combined_v1'
pytestmark = pytest.mark.skipif(not (EXP/V2).is_dir(), reason='combined v2 derived run not present')


@pytest.fixture(scope='module')
def env(tmp_path_factory):
    root = tmp_path_factory.mktemp('runs')
    for name in (V2, V1):
        shutil.copytree(EXP/name, root/name, ignore=shutil.ignore_patterns('screenshots'))
    store = DecisionStore(tmp_path_factory.mktemp('store')/'d.sqlite3')
    return TestClient(create_app(catalog=Catalog([root]), store=store, session_actor='U006')), store, tmp_path_factory


def _cards(client, key):
    return {c['card']['card_id']: c for c in client.get(f'/api/runs/{key}/brief').json()['cards']}


def _named(cards, name):
    return next(c for c in cards.values() if c['card']['topic_name'] == name)


def test_counts_accounting_and_cost_record(env):
    client, _, _ = env
    cards = _cards(client, V2)
    in_brief = [c for c in cards.values() if c['presentation']['inventory'] == 'BRIEF' and c['card']['briefing']['status'] == 'IN_BRIEFING']
    lines = [c['card']['card_line'] for c in in_brief]
    assert len(in_brief) == 63 and (lines.count('NEEDS_REVIEW'), lines.count('RECOMMENDED_ACTION'), lines.count('OBSERVATION')) == (52, 8, 3)
    summary = json.loads((EXP/V2/'derivation.json').read_text(encoding='utf-8'))['summary']
    assert summary['accounting']['threads'] == 177 and summary['accounting']['review_items'] == 37
    assert summary['targeted_regrounding'] == {**summary['targeted_regrounding'], 'requests': 2, 'charged_usd': 0.094, 'rebuild_model_calls': 0}
    assert summary['supersedes']['unchanged_cards'] == 93 and len(summary['supersedes']['replaced']) == 2


def test_only_the_two_regrounded_cards_change_and_each_names_what_it_replaces(env):
    client, _, _ = env
    v1, v2 = _cards(client, V1), _cards(client, V2)
    changed = set(v2) - set(v1)
    assert sorted(v2[c]['card']['topic_name'] for c in changed) == ['Format compliance versus accuracy', 'Overlapping speech in transcription']
    for cid in changed:
        old = v2[cid]['presentation']['supersedes_card_id']
        assert old in v1 and v1[old]['card']['topic_name'] == v2[cid]['card']['topic_name']
    for cid in set(v2) & set(v1):
        assert v2[cid]['card'] == v1[cid]['card']


def test_overlap_action_is_visible_and_its_inherited_flag_stays_open(env):
    client, _, _ = env
    card = _named(_cards(client, V2), 'Overlapping speech in transcription')['card']
    assert card['recommended_action'] and card['checks']['grounding'] == 'PASSED'
    assert [r['code'] for r in card['needs_review_reasons']] == ['INHERITED_FLAG'] and card['inherited_flags']


def test_format_card_labels_human_edits_keeps_the_judged_draft_and_lists_the_suggestion(env):
    client, _, _ = env
    item = _named(_cards(client, V2), 'Format compliance versus accuracy')
    card, presentation = item['card'], item['presentation']
    assert card['card_line'] == 'RECOMMENDED_ACTION' and card['severity']['level'] == 'MEDIUM'
    edits = presentation['human_edits']
    assert len(edits) == 3 and {e['provenance'] for e in edits} == {'HUMAN_EDIT_VERIFIED_BY_LIVE_MODEL'}
    assert {e['verdict'] for e in edits} == {'SUPPORTED'}
    saved = json.loads((EXP/'agent3_reground_v1/format_compliance.json').read_text(encoding='utf-8'))['result']
    assert card['recommended_action']['draft_text'] == saved['drafts']['final']['proposed_action']['draft_text']
    assert 'prose' not in card['recommended_action']['draft_text']  # the model's draft, unchanged
    [suggestion] = presentation['tl_suggestions']
    assert suggestion['status'] == 'NOT_JUDGED' and 'JSON' in suggestion['text']
    text = (EXP/V2/'morning_brief.md').read_text(encoding='utf-8')
    assert 'Human edits verified by the live model' in text and 'Posting suggestions for the team lead (not judged' in text


def test_decisions_stay_isolated_by_run_and_export_with_their_run_binding(env):
    client, store, factory = env
    v1, v2 = _cards(client, V1), _cards(client, V2)
    shared = _named(v2, 'Overlapping speech in transcription')['card']['card_id']
    reused = next(cid for cid in set(v1) & set(v2) if v2[cid]['card']['card_line'] == 'NEEDS_REVIEW')
    for key, cid, idem in ((V2, shared, 'v2-iso-0001'), (V2, reused, 'v2-iso-0002')):
        saved = client.post(f'/api/runs/{key}/cards/{cid}/decisions', json={'kind': 'DISMISS', 'actor_id': 'U006', 'note': 'test'},
                            headers={'Idempotency-Key': idem})
        assert saved.status_code in (200, 201), saved.text
    assert client.get(f'/api/runs/{V1}/decisions').json()['decisions'] == []
    assert len(client.get(f'/api/runs/{V2}/decisions').json()['decisions']) == 2
    entries = store.all_card_decisions()
    run = next(r for r in client.get('/api/runs').json()['runs'] if r['run_key'] == V2)
    assert {(e['run_key'], e['run_instance']) for e in entries} == {(V2, run['run_instance'])}
    for e in entries:
        assert run['run_instance'] in decision_markdown(e) and ingest(e)
    assert export(entries, factory.mktemp('export'))['written'] == 2
