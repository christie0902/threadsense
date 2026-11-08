"""briefing-presentation-v1 on the demo baseline: display labels and attributed notes from saved records, zero model
calls. Card data, verdicts, routing and decision bindings stay unchanged."""
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest

from threadsense.dashboard.app import create_app
from threadsense.dashboard.decisions import DecisionStore
from threadsense.dashboard.runs import Catalog, Run
from threadsense.routing import ROOT

RUN = ROOT/'data/experiments/threadsense_full_v1_combined_v2'
pytestmark = pytest.mark.skipif(not (RUN/'presentation.json').is_file(), reason='presentation layer not built')
LAYER = json.loads((RUN/'presentation.json').read_text(encoding='utf-8')) if (RUN/'presentation.json').is_file() else {}
EXPORT = (RUN/'morning_brief.md').read_text(encoding='utf-8') if RUN.is_dir() else ''


def section(name):
    start = EXPORT.index(f'## {name}\n')
    return EXPORT[start:EXPORT.index('\n## ', start + 4)]


def test_the_layer_is_bound_to_the_unchanged_run_instance():
    from hashlib import sha256
    assert LAYER['model_calls'] == 0
    assert LAYER['built_from'] == {f: sha256((RUN/f).read_bytes()).hexdigest() for f in LAYER['built_from']}
    assert LAYER['run_instance'] == Run(RUN).instance
    assert (RUN/'exports'/'morning_brief.derivation.md').is_file()  # the original export is kept


def test_active_totals_lead_and_history_is_separate():
    t = LAYER['totals']
    assert (t['active_cards'], t['active_threads'], t['processing_history_threads'], t['review_queue_items']) == (63, 174, 3, 37)
    assert t['by_line'] == {'NEEDS_REVIEW': 52, 'RECOMMENDED_ACTION': 8, 'OBSERVATION': 3}
    assert t['card_records'] == {**t['card_records'], 'total': 95, 'active': 63, 'replaced_history': 29, 'processing_history': 3}
    head = EXPORT.split('\n## ', 1)[0]
    assert '**63 active cards covering 174 threads:** 52 Needs Review, 8 Recommended Action, 3 Observation.' in head
    assert '3 processing-history threads (not briefed); 37 Model Review Queue items' in head
    assert 'Card records in this directory: 95' in head and 'Not an active total' in head and '95 cards (' not in head


def test_usage_is_reported_by_stage():
    rows = {r['stage']: r for r in LAYER['stage_costs']}
    assert rows['Consolidated-issue refresh (14 issues, Agent 3)'] == {**rows['Consolidated-issue refresh (14 issues, Agent 3)'], 'requests': 32, 'charged_usd': 2.228}
    assert rows['Targeted grounding checks (2 cards)']['charged_usd'] == 0.094 and rows['Targeted grounding checks (2 cards)']['requests'] == 2
    assert rows['Offline assembly (combined briefings and this presentation)'] == {**rows['Offline assembly (combined briefings and this presentation)'], 'requests': 0, 'charged_usd': 0.0}
    assert rows['Full pipeline (Agent 1 to Agent 3, campaign ledger)']['charged_usd'] == 15.3173
    usage = EXPORT[EXPORT.index('## Usage by stage'):]
    assert '| 32 | $2.2280 |' in usage and '$0.094 (as reported' in usage and '| 0 | $0.000 |' in usage


def test_posting_suggestions_are_source_linked_and_outside_the_copyable_draft():
    text = section('Format compliance versus accuracy')
    draft = text[text.index('**Draft to copy:**'):text.index('**Human edits verified by the live model:**')]
    assert 'status note' not in draft and 'JSON object answered' not in draft
    suggestions = text[text.index('**Posting suggestions for the team lead (not judged; not part of the draft):**'):]
    assert 'October 2, 10:21 UTC batch status note' in suggestions and '1790936513.000019' in suggestions
    assert 'well-written prose is still a missing required format' in suggestions
    assert text.index('**Human edits verified by the live model:**') < text.index('**Posting suggestions')


def test_the_close_call_offers_both_saved_options_and_keeps_the_review():
    text = section('NSFW suggestive-content threshold')
    assert '**Choose a next step.**' in text and '**What to do:' not in text
    assert '1. **Schedule a short review session.**' in text and '2. **Post a reminder.**' in text
    assert 'Applies only as stated: Limit the discussion' in text
    assert 'Still open: What NSFW cutoff should apply' in text and '**Still needs review:**' in text


def test_review_notes_are_clarified_by_attributed_editorial_notes():
    qn = section('QN handling for fictional contact details')
    assert qn.index('**Confirm before editing** (editorial note, not judged)') > qn.index('**Draft to copy:**')
    assert 'refers to that same document is not established' in qn
    queue = section('Queue coverage and closure reminders')
    assert '“Today” is from the closure reminder posted 2026-10-01 18:40 UTC' in queue
    assert '“tomorrow” is from the coverage post posted 2026-10-02 01:14 UTC' in queue and 'unconfirmed' in queue


def test_dashboard_serves_the_layer_only_for_its_run_instance(tmp_path):
    root = tmp_path/'runs'
    shutil.copytree(RUN, root/RUN.name, ignore=shutil.ignore_patterns('screenshots'))
    run = Run(root/RUN.name)
    assert run.instance == LAYER['run_instance'] and run.display_layer is not None  # instance files unchanged by the layer
    client = TestClient(create_app(catalog=Catalog([root]), store=DecisionStore(tmp_path/'d.sqlite3'), session_actor='U006'))
    brief = client.get(f'/api/runs/{RUN.name}/brief').json()
    assert brief['run']['presentation']['totals']['active_cards'] == 63
    cards = {c['card']['topic_name']: c for c in brief['cards']}
    assert len(cards['NSFW suggestive-content threshold']['presentation']['choice']['options']) == 2
    assert cards['Format compliance versus accuracy']['presentation']['posting_suggestions'][0]['source']['thread_id'] == '1790936513.000019'
    status = client.get(f"/api/runs/{RUN.name}/evidence/k:slack:C_RP_ANNOUNCEMENTS:1790936513.000019:8237860f")
    assert status.status_code == 200
    stale = {**LAYER, 'run_instance': '0' * 64}
    (root/RUN.name/'presentation.json').write_text(json.dumps(stale), encoding='utf-8')
    assert Run(root/RUN.name).display_layer is None  # a layer built for other files is ignored
