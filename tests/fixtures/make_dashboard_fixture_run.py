"""Build the labelled dashboard test-fixture run (tests/fixtures/dashboard_runs/dashboard_states_fixture_v1).

TEST FIXTURE, NOT MODEL OUTPUT. It covers dashboard states that no saved run has: a RECOMMENDED_ACTION card (the
live smoke run has two Needs Review cards), an OBSERVATION card, a Needs Review card with a reminder draft and a
supported alternative, a failed topic and unprocessed (budget) work. Card text is hand-written and every topic name
starts with "[Test fixture]". Lineage, related threads, citations and evidence-ledger entries are copied unchanged
from the scripted offline run (agent3_overnight_offline_v2) so source and thread views have real saved evidence.

  uv run --locked python tests/fixtures/make_dashboard_fixture_run.py      # rewrites the fixture directory
"""
import json
from pathlib import Path
import shutil

from threadsense.agents.advice_contracts import ACTION_LABELS, AdviceCardV3, ModelReviewItem, stable_id
from threadsense.agents.overnight import BRIEF_VERSION, brief_card, report
from threadsense.dashboard.runs import Run
from threadsense.routing import ROOT

SOURCE = ROOT/'data/experiments/agent3_overnight_offline_v2'
OUT = ROOT/'tests/fixtures/dashboard_runs/dashboard_states_fixture_v1'
RUN_ID = 'fixture_dashboard_states_v1'
NOTE = ('Hand-built TEST FIXTURE for dashboard states absent from the live smoke run (Recommended Action, Observation, '
        'reminder draft with a supported alternative, failed and unprocessed work). Not model output: card text is '
        'hand-written; citations and evidence entries are copied from agent3_overnight_offline_v2 (scripted).')
RUBRIC = {'rubric_version': 'severity-rubric-v3-semantic-signals',
          'rubric_content_sha256': 'eccaa31a2ab84a0aa7c005216a92fc39681e1dd10107117344948235a76673f4',
          'rubric_scope': 'SHARED_DEFAULT'}
CARDS = [
    {'template': 'Fictional phone number quarantine handling', 'line': 'RECOMMENDED_ACTION', 'action': 'POST_ALIGNMENT',
     'summary': 'Test fixture: tutors ask whether a made-up phone number in a fictional story still needs quarantine. '
                'The current clarification answers this; the older help-page section is superseded.',
     'instruction': 'Post a short reminder in the batch channel that points tutors to the current clarification.',
     'rationale': 'Test fixture: the question repeats and the current clarification already answers it.',
     'draft': 'Reminder: a phone number that is clearly invented inside a fictional story follows the current '
              'clarification, not the older help-page section. If you are unsure whether a number is real, flag the task '
              'for review and keep the surrounding context.',
     'confidence': 0.9, 'severity': 'LOW'},
    {'template': 'Repeated final line in exported audio', 'line': 'OBSERVATION', 'action': 'NO_ACTION',
     'summary': 'Test fixture: one tutor mentions a repeated final line in an exported clip; the thread already records '
                'the check that was done. Nothing needs to be done now.',
     'confidence': 0.88, 'severity': 'LOW'},
    {'template': 'Format adherence vs factual accuracy', 'line': 'NEEDS_REVIEW', 'action': 'POST_ALIGNMENT',
     'summary': 'Test fixture: reviewers disagree on whether format adherence can outweigh a factual error. The team '
                'lead should confirm the wording before anything is posted.',
     'instruction': 'Post a reminder of the current priority between factual accuracy and format adherence.',
     'rationale': 'Test fixture: the same question appears in several threads.',
     'draft': 'Reminder: when a response is factually wrong, format adherence does not make it the better response. '
              'Rate factual accuracy first, then format.',
     'confidence': 0.55, 'severity': 'MEDIUM',
     'alternative': {'candidate_id': 'faq_entry', 'action_type': 'UPDATE_FAQ',
                     'instruction': 'Add a short FAQ entry on factual accuracy versus format adherence.',
                     'draft_text': 'Q: Can strict format adherence outweigh a factual error? A: No. Rate factual accuracy first.',
                     'rationale': 'Test fixture: a FAQ entry answers the repeated question in one place.'}},
]


def card_for(spec, template, ledger):
    keys = [k for k, e in ledger.items() if e.get('origin') == 'retrieved_source' and e.get('use') == 'CURRENT_GUIDANCE'][:2]
    sources = [{'kind': 'knowledge_source', 'project_id': ledger[k]['scope']['project_id'], 'scope': ledger[k]['scope']['scope'],
                'batch_id': ledger[k]['scope']['batch_id'], 'document_id': ledger[k]['citation']['document_id'],
                'version_id': ledger[k]['citation']['version_id'], 'chunk_id': ledger[k]['citation']['chunk_id'],
                'authoring_document_id': (ledger[k]['citation']['authoring'] or '@').split('@')[0] or None,
                'authoring_version': (ledger[k]['citation']['authoring'] or '@').split('@')[1] or None,
                'section': (ledger[k]['citation']['sections'] or [None])[0], 'note': f'{k} (test fixture citation)'}
               for k in keys]
    level = spec['severity']
    severity = {'level': level, 'assessment_status': 'ASSESSED', **RUBRIC, 'rationale': 'Test fixture severity.'}
    if level == 'MEDIUM':
        message = next(k for k, e in ledger.items() if e.get('origin') == 'member_message')
        e = ledger[message]
        severity['matched_signals'] = [{'level': 'MEDIUM', 'signal_index': 0, 'signal_text': 'Test fixture signal.',
                                        'support': 'Test fixture support.',
                                        'evidence': [{'kind': 'slack_message', 'project_id': template['project_id'],
                                                      'channel_id': e['channel_id'], 'thread_id': e['thread_id'],
                                                      'message_id': e['message_id'], 'note': message}]}]
    action = None
    if spec['action'] != 'NO_ACTION':
        action = {'action_type': spec['action'], 'label': ACTION_LABELS[spec['action']], 'instruction': spec['instruction'],
                  'rationale': spec['rationale'], 'draft_text': spec['draft'], 'scope_note': None}
    elif spec['line'] == 'OBSERVATION':
        action = {'action_type': 'NO_ACTION', 'label': ACTION_LABELS['NO_ACTION']}
    review = spec['line'] == 'NEEDS_REVIEW'
    lineage = {**template['lineage'], 'agent3_run_id': RUN_ID}
    body = {'project_id': template['project_id'], 'topic_name': f"[Test fixture] {spec['template']}",
            'card_line': spec['line'], 'summary': spec['summary'], 'severity': severity, 'severity_is_provisional': False,
            'resolution_status': 'UNRESOLVED' if spec['line'] != 'OBSERVATION' else 'RESOLVED_IN_THREAD',
            'recommended_action': action,
            'reasoning': 'Test fixture: hand-written card for dashboard states; not produced by the Advisor.',
            'supporting_sources': sources, 'related_threads': template['related_threads'], 'confidence': spec['confidence'],
            'needs_review_reasons': [{'code': 'LOW_CONFIDENCE', 'detail': 'Test fixture: confidence below 0.60.'}] if review else [],
            'inherited_flags': [], 'review_notes': ['Test fixture: confirm the reminder wording before it is posted.'] if review else [],
            'checks': {'grounding': 'PASSED', 'temporal_conflict': 'NONE_FOUND', 'open_confirmation': 'NONE'},
            'lineage': lineage}
    return AdviceCardV3.model_validate({**body, 'card_id': stable_id('card', body)}).model_dump(mode='json')


def main():
    source = Run(SOURCE)
    by_name = {c['topic_name']: c for c in source.cards.values()}
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT/'topics').mkdir(parents=True)
    cards, topics = [], {}
    for spec in CARDS:
        template = by_name[spec['template']]
        topic = source.topics[template['card_id']]
        ledger = topic['result']['evidence_ledger']
        card = card_for(spec, template, ledger)
        cards.append(card)
        alt = spec.get('alternative')
        result = {'evidence_ledger': ledger, 'diagnostics': [], 'coverage_issues': [], 'action_notes': [],
                  'tot': {'status': 'COMPARED' if alt else 'NOT_TRIGGERED', 'candidates': [alt] if alt else [],
                          'preferred_candidate_id': None},
                  'grounding': {'statements': [{'statement_id': f"alternative:{alt['candidate_id']}", 'kind': 'ALTERNATIVE',
                                                'verdict': 'SUPPORTED'}] if alt else [],
                                'alternative_sufficiency': {f"alternative:{alt['candidate_id']}": {
                                    'verdict': 'SUFFICIENT', 'check': 'SUPPORTED'}} if alt else {}},
                  'card': card}
        work = {**topic['work_item'], 'topic_name': card['topic_name']}
        topics[work['work_id']] = {'work_item': work, 'workflow': {'outcome': 'CARD', 'card_id': card['card_id'],
                                                                   'card_line': card['card_line'], 'semantic_source': 'TEST_FIXTURE'},
                                   'result': result}
    incomplete = [
        {'work_id': 'topic:fixture_failed/topic_1', 'kind': 'TOPIC', 'candidate_group_id': 'fixture_failed', 'topic_id': 'fixture_failed/topic_1',
         'topic_name': '[Test fixture] Topic that failed', 'member_ids': ['member_fixture_failed_1'], 'obligations': [],
         'outcome': 'TOPIC_FAILED', 'failure_class': 'PIPELINE', 'error': 'Test fixture: simulated pipeline failure.'},
        {'work_id': 'topic:fixture_budget/topic_1', 'kind': 'TOPIC', 'candidate_group_id': 'fixture_budget', 'topic_id': 'fixture_budget/topic_1',
         'topic_name': '[Test fixture] Topic not processed (budget)', 'member_ids': ['member_fixture_budget_1', 'member_fixture_budget_2'],
         'obligations': [], 'outcome': 'UNPROCESSED_BUDGET', 'detail': 'Test fixture: the run budget was exhausted before this topic.'}]
    groups = {c['lineage']['candidate_group_id']: c['card_id'] for c in cards}
    queue = [ModelReviewItem.model_validate({**i.model_dump(mode='json'), 'related_card_ids': [groups[i.candidate_group_id]]})
             .model_dump(mode='json') for i in source.queue.values() if i.candidate_group_id in groups]
    members = [{'member_id': m, 'project_id': c['project_id'], 'work_id': w, 'outcome': 'CARD', 'card_id': c['card_id']}
               for w, t in topics.items() for c in [t['result']['card']] for m in c['lineage']['member_ids']]
    members += [{'member_id': m, 'project_id': 'response_preference', 'work_id': w['work_id'], 'outcome': w['outcome'], 'card_id': None}
                for w in incomplete for m in w['member_ids']]
    lines = {}
    for c in cards:
        lines[c['card_line']] = lines.get(c['card_line'], 0) + 1
    counts = {'discussion_members': len(members), 'members_on_cards': sum(m['outcome'] == 'CARD' for m in members),
              'announcement_route_members': 0, 'announcement_route_obligations': 0, 'inherited_agent1_obligations': 0,
              'naming_cautions': 0, 'work_items': len(topics) + len(incomplete), 'cards': len(cards), 'cards_by_line': lines,
              'review_queue_items': len(queue), 'window_announcements': 0, 'window_announcements_in_snapshot': 0}
    brief = {'brief_version': BRIEF_VERSION, 'run_id': RUN_ID, 'status': 'INCOMPLETE', 'cutoff': '2026-10-02T12:00:00Z',
             'window': {'start': '2026-10-01T12:00:00+00:00', 'cutoff': '2026-10-02T12:00:00+00:00', 'interval': '[start, cutoff)'},
             'semantic_judgments': 'TEST_FIXTURE', 'semantic_note': NOTE, 'validation_baseline': {}, 'counts': counts,
             'cards': [brief_card(c, 'TEST_FIXTURE') for c in cards],
             'scope': {'only': None, 'work_items_in_scope': counts['work_items'], 'work_items': counts['work_items'], 'out_of_scope_work': []},
             'model_review_queue': queue, 'incomplete_work': incomplete, 'projection_gaps': [], 'announcements_in_window': [],
             'usage': {'totals': {}}, 'accounting': {'status': 'COMPLETE', 'issues': []}}
    write = lambda name, value: (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    write('run_manifest.json', {'workflow_version': 'agent3-overnight-v1', 'run_id': RUN_ID, 'test_fixture': True,
                                'test_fixture_note': NOTE, 'built_from': 'data/experiments/agent3_overnight_offline_v2'})
    write('morning_brief.json', brief)
    (OUT/'morning_brief.md').write_text(report(brief), encoding='utf-8')
    write('cards.json', cards)
    write('review_queue.json', queue)
    write('accounting.json', {'status': 'COMPLETE', 'issues': [], 'counts': counts, 'members': members,
                              'incomplete_work': incomplete, 'out_of_scope_work': [], 'projection_gaps': []})
    for work_id, topic in topics.items():
        write(f"topics/{work_id.replace(':', '__').replace('/', '__')}.json", topic)
    print(f'Wrote {OUT.relative_to(ROOT)}: {len(cards)} cards, {len(incomplete)} incomplete work items, {len(queue)} review items.')


if __name__ == '__main__':
    main()
