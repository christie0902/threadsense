"""Dashboard "What to review" view (dashboard.review) over the saved runs. Read-only; no model call."""
import json

import pytest

from threadsense.dashboard.review import EXTRA_NOTES, REASON_NOTES, matches, review_view
from threadsense.dashboard.runs import Catalog
from threadsense.handoff_inputs import ROOT

SUBMIT = ('agent3_recipient_routing_v1', 'Unassigned members of routed_440e64c7fbdcc49f')
PLAYBACK = ('agent3_final_eval_v1', 'LT audio player playback failure')


@pytest.fixture(scope='module')
def catalog():
    return Catalog([ROOT/'data/experiments', ROOT/'data/experiments/agent3_feedback_loop_offline_v2'], include_fixtures=True)


def card_of(catalog, key):
    run = catalog.get(key[0])
    return run, next(c for c in run.cards.values() if c['topic_name'].startswith(key[1]))


def links(value):
    if isinstance(value, dict):
        if value.get('kind') in ('evidence', 'thread', 'queue'):
            yield value
        for v in value.values():
            yield from links(v)
    elif isinstance(value, list):
        for v in value:
            yield from links(v)


def test_every_saved_card_has_one_entry_per_reason_and_every_link_resolves(catalog):
    for run in catalog.runs.values():
        queue = set(run.queue)
        for card_id, card in run.cards.items():
            view = run.review(card_id)
            assert [i['code'] for i in view['items']] == [r['code'] for r in card['needs_review_reasons']]
            threads = {(t['channel_id'], t['thread_id']) for t in card['related_threads']}
            for link in links(view):
                if link['kind'] == 'evidence':
                    assert link['available'] and link['id'] in run.ledger(card_id), (run.key, link)
                elif link['kind'] == 'thread':
                    assert (link['channel'], link['thread']) in threads
                else:
                    assert link['item_id'] in queue and card_id in run.queue[link['item_id']].related_card_ids
            # Every saved note is the advisor's own note, the plain-language form of a reason, or a known extra note;
            # only the hand-written fixture has free text.
            shown = {view['advisor_note']['text']} if view['advisor_note'] else set()
            for note in card['review_notes']:
                known = note in shown or matches(note, REASON_NOTES) or matches(note, EXTRA_NOTES)
                assert known or run.mode == 'TEST_FIXTURE', (run.key, note)


def test_submit_card_separates_mandatory_review_inherited_flags_and_the_advisor_note(catalog):
    run, card = card_of(catalog, SUBMIT)
    view = run.review(card['card_id'])
    severity, flags = view['items']
    assert (severity['code'], severity['category']) == ('HIGH_SEVERITY', 'MANDATORY') and len(severity['signals']) == 2
    assert 'always goes to a team lead' in severity['check'] and 'severity-rubric' not in severity['check']
    assert (flags['code'], flags['category'], len(flags['flags'])) == ('INHERITED_FLAG', 'INHERITED', 3)
    queue_links = [l for f in flags['flags'] for l in f['links'] if l['kind'] == 'queue']
    assert len(queue_links) == 2  # The two Agent 1 obligations; the projection gap is carried on the card only.
    gap = next(f for f in flags['flags'] if f['kind'] == 'projection_gap')
    assert gap['queue_note'] and len([l for l in gap['links'] if l['kind'] == 'thread']) == 4
    assert view['advisor_note']['text'] == card['review_notes'][0] and view['other_notes'] == []
    assert view['withheld'] == []  # Every statement on this card was SUPPORTED.


def test_playback_card_describes_withheld_content_by_field_and_never_shows_it(catalog):
    run, card = card_of(catalog, PLAYBACK)
    view = run.review(card['card_id'])
    disputed = next(i for i in view['items'] if i['code'] == 'GROUNDING_FAILURE')
    assert disputed['category'] == 'DISPUTED'
    [entry] = disputed['withheld']
    assert entry['field'] == 'How an announcement applies to this topic' and entry['verdict'] == 'UNSUPPORTED'
    assert entry['links'][0]['id'].startswith('k:slack:C_AUDIO_ANNOUNCEMENTS')
    alternative = next(w for w in view['withheld'] if w['statement_id'] == 'alternative:collect_before_escalating')
    assert alternative['field'] == 'Alternative option (no action)' and alternative['verdict'] == 'PARTIALLY_SUPPORTED'
    text = json.dumps(view)
    for statement in run.topics[card['card_id']]['result']['grounding']['statements']:
        if statement['verdict'] != 'SUPPORTED':
            assert statement['text'] not in text  # The rejected wording is not returned.
    assert {i['category'] for i in view['items']} == {'MANDATORY', 'INHERITED', 'DISPUTED', 'DECISION'}


def test_alternatives_state_only_the_relation_the_saved_comparison_records(catalog):
    run, card = card_of(catalog, PLAYBACK)
    relations = {a['candidate_id']: a['relation'] for a in run.alternatives(card['card_id'])}
    assert relations == {'engineering_report': 'SAME_ACTION_TYPE', 'handling_alignment': 'DIFFERENT_ACTION'}


def test_missing_saved_details_are_reported_as_unavailable(catalog):
    run, card = card_of(catalog, PLAYBACK)
    view = review_view(card, None, [])  # As for a run that saved no topic result.
    assert not view['saved_result'] and view['withheld'] is None and view['advisor_note'] is None
    disputed = next(i for i in view['items'] if i['code'] == 'GROUNDING_FAILURE')
    assert disputed['unavailable'] and disputed['withheld'] == []
    severity = next(i for i in view['items'] if i['code'] == 'HIGH_SEVERITY')
    assert severity['signals'] and all(not l['available'] for s in severity['signals'] for l in s['links'])
    no_signals = review_view({**card, 'severity': {**card['severity'], 'matched_signals': []}}, None, [])
    assert next(i for i in no_signals['items'] if i['code'] == 'HIGH_SEVERITY')['unavailable']


def test_run_provenance_comes_from_the_manifest(catalog):
    live = catalog.get('agent3_recipient_routing_v1').summary()['provenance']
    assert live == {'prompt_version': 'agent3-advisor-prompts-v14', 'pilot_version': 'agent3-advisor-pilot-v6',
                    'semantic_client': 'LIVE_MODEL', 'model': live['model']} and live['model']
    scripted = catalog.get('agent3_overnight_offline_v2').summary()['provenance']
    assert scripted['semantic_client'] == 'SCRIPTED_MOCK' and scripted['model'] is None
    assert catalog.get('dashboard_states_fixture_v1').summary()['provenance']['prompt_version'] is None


SMOKE_PLAYBACK = ('agent3_overnight_smoke_v1', 'card_bd0a25b5720e9f5c55945f96f92f4783')
FLAG_ONLY = ('agent3_summary_eval_v1', 'Format adherence vs factual accuracy')


def test_saved_check_text_is_verbatim_and_ui_copy_has_no_boilerplate(catalog):
    for run in catalog.runs.values():
        for card_id, card in run.cards.items():
            for check in run.review(card_id)['checks']:
                saved = json.dumps(card, ensure_ascii=False)
                if check['text_origin'] == 'SAVED':
                    for part in check['text'].split('  '):
                        assert part in saved or part in json.dumps(run.review(card_id), ensure_ascii=False), (run.key, part)
                for text in [check['text'], check['heading'], *check.get('related', [])]:
                    for boilerplate in ('Concerns:', 'from the final checks', 'severity-rubric', 'review this card'):
                        assert boilerplate not in text


def test_reload_trial_question_leads_once_with_its_research_gap_and_note(catalog):
    run = catalog.get(SMOKE_PLAYBACK[0])
    view = run.review(SMOKE_PLAYBACK[1])
    question = view['checks'][0]
    assert question['kind'] == 'QUESTION' and question['text'].startswith('Does the earlier reload trial apply')
    assert question['related'] and question['note'] == view['advisor_note']['text']
    assert [c['kind'] for c in view['checks']].count('QUESTION') == 1 and 'GAP' not in [c['kind'] for c in view['checks']]
    assert [c['kind'] for c in view['checks']] == ['QUESTION', 'WITHHELD', 'FLAG', 'SEVERITY']
    assert any(l['label'] == 'View the record' and 'playback trial' in l['detail'] for l in question['links'])
    assert len(view['items']) == 5  # Every original reason is kept for the secondary view.


def test_flag_only_card_leads_with_the_flag_and_does_not_imply_the_recommendation_failed(catalog):
    run, card = card_of(catalog, FLAG_ONLY)
    [check] = run.review(card['card_id'])['checks']
    assert check['kind'] == 'FLAG' and check['heading'] == 'Flagged thread'
    assert card['checks']['grounding'] == 'PASSED' and 'passed the evidence check' in check['related'][0]
    assert [l['label'] for l in check['links']] == ['Open flagged thread', 'Open its Model Review Queue item']


def test_high_severity_alone_leads_and_links_its_evidence(catalog):
    run, card = card_of(catalog, SUBMIT)
    only = {**card, 'needs_review_reasons': [r for r in card['needs_review_reasons'] if r['code'] == 'HIGH_SEVERITY']}
    checks = review_view(only, run.topics[card['card_id']]['result'], [])['checks']
    assert [c['kind'] for c in checks] == ['SEVERITY', 'NOTE'] and checks[0]['links'][0]['label'] == 'Open a report behind it'


def test_projection_gap_cards_display_a_fallback_title_and_keep_the_saved_label(catalog):
    run, card = card_of(catalog, SUBMIT)
    assert run.topics[card['card_id']]['work_item']['kind'] == 'PROJECTION_GAP'
    assert run.display_title(card['card_id']) == 'Threads awaiting a topic'
    assert card['topic_name'].startswith('Unassigned members of routed_440e64c7fbdcc49f')  # Saved card unchanged.
    assert any(c['kind'] == 'FLAG' and c['heading'] == 'Topic grouping needs review' for c in run.review(card['card_id'])['checks'])
    for run in catalog.runs.values():  # The normal topic path keeps the saved topic name.
        for card_id, card in run.cards.items():
            if card['lineage'].get('topic_id'):
                assert run.display_title(card_id) == card['topic_name']
