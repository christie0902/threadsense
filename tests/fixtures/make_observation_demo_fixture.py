"""Build the Observation demo fixture: two hand-written OBSERVATION cards (one model-behavior, one tool-performance)
with realistic fixture evidence, a supported reason to monitor and no unresolved handling request.

TEST FIXTURE, not model output and not live evaluation: card text, evidence and verdicts are hand-written (each
verdict rationale starts with PREPARED); the run manifest sets test_fixture, so the dashboard serves it in the test
namespace and its counts stay apart from live runs. The cards are validated under AdviceCard v5 (an OBSERVATION needs
a supported NO_ACTION_NEEDED reason) and routed by the briefing policy like any other card.

    uv run --locked python tests/fixtures/make_observation_demo_fixture.py
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from threadsense.agents.advice_contracts import AdviceCardV5  # noqa: E402
from threadsense.agents.overnight import BRIEF_VERSION, brief_card, report  # noqa: E402

OUT = ROOT/'tests/fixtures/observation_demo_runs/observation_demo_fixture_v1'
RUN_ID = 'fixture_observation_demo_v1'
NOTE = ('Hand-built TEST FIXTURE: two Observation cards (model behavior, tool performance) for the dashboard demo. Not model '
        'output and not a live evaluation; card text, evidence and verdicts are hand-written (PREPARED).')
RUBRIC = {'rubric_version': 'severity-rubric-v3-semantic-signals',
          'rubric_content_sha256': 'eccaa31a2ab84a0aa7c005216a92fc39681e1dd10107117344948235a76673f4',
          'rubric_project_id': None, 'rubric_scope': 'SHARED_DEFAULT'}

DEMOS = [
    {'key': 'model_behavior', 'project_id': 'response_preference', 'batch_id': 'rp_batch_demo', 'channel_id': 'C_DEMO_RP',
     'channel_name': '#response-preference-demo', 'topic_name': 'Unrequested markdown headers in plain-text answers',
     'messages': [
         ('1790950000.000101', 'U_DEMO_T1', 'TUTOR', 'Seeing more B responses add markdown headers when the prompt asked for '
          'plain text, three in this morning\'s queue so far.'),
         ('1790950060.000102', 'U_DEMO_Q1', 'QA_TUTOR', 'Same pattern on my side. The rubric already covers it: unrequested '
          'formatting is a minor instruction-adherence issue, and I scored my three that way.'),
         ('1790950120.000103', 'U_DEMO_T1', 'TUTOR', 'Thanks, scored mine the same way. Just flagging the uptick in case it '
          'keeps growing.')],
     'summary': 'A tutor and a QA tutor each report responses that add markdown headers to plain-text answers. Both scored '
                'them under the existing rule for unrequested formatting; no handling question remains.',
     'details': ['A tutor reports three responses in one morning queue that added markdown headers when the prompt asked for '
                 'plain text.',
                 'A QA tutor reports the same pattern and states that unrequested formatting is scored as a minor '
                 'instruction-adherence issue.',
                 'The tutor confirms scoring the same way and flags the increase in case it continues.'],
     'rationale': 'Both reporters applied the established scoring rule, and nothing in the thread is waiting on a decision; '
                  'the reported increase in this model behavior is worth watching in later batches.',
     'severity': 'Two reporters describe a recurring formatting behavior that the rubric already handles; no conflicting '
                 'scores, blocked work or wider disruption.'},
    {'key': 'tool_performance', 'project_id': 'audio_multimodal', 'batch_id': 'audio_batch_demo', 'channel_id': 'C_DEMO_AUDIO',
     'channel_name': '#audio-multimodal-demo', 'topic_name': 'Slow waveform rendering on long clips (recovered)',
     'messages': [
         ('1790951000.000201', 'U_DEMO_T2', 'TUTOR', 'The waveform takes about 20 seconds to render on long clips this '
          'morning. Playback works once it loads.'),
         ('1790951090.000202', 'U_DEMO_Q2', 'QA_TUTOR', 'Seeing the same, roughly 15 to 20 seconds on clips over three '
          'minutes. Nothing fails, it is just slow.'),
         ('1790951900.000203', 'U_DEMO_T2', 'TUTOR', 'Back to normal for me since about 11:00, waveforms load in a couple of '
          'seconds again.')],
     'summary': 'A tutor and a QA tutor report slow waveform rendering on long clips without failures; the tutor later reports '
                'normal load times again.',
     'details': ['A tutor reports waveforms taking about 20 seconds to render on long clips, with playback working once loaded.',
                 'A QA tutor reports 15 to 20 seconds on clips over three minutes and states that nothing fails.',
                 'The tutor later reports load times back to a couple of seconds.'],
     'rationale': 'The slowdown caused no failures and the reporter says load times recovered, so no intervention is needed; '
                  'a recurrence on long clips would be worth tracking as tool performance.',
     'severity': 'Two reporters describe a temporary slowdown with no failed tasks; the reporter states it recovered.'},
]


def stable_id(prefix, value):
    return f"{prefix}_{sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:32]}"


def message_ref(demo, ts, member):
    return {'kind': 'slack_message', 'project_id': demo['project_id'], 'batch_id': demo['batch_id'], 'scope': 'project',
            'channel_id': demo['channel_id'], 'thread_id': demo['messages'][0][0], 'message_id': ts, 'document_id': None,
            'version_id': None, 'authoring_document_id': None, 'authoring_version': None, 'section': None, 'chunk_id': None,
            'candidate_group_id': None, 'member_id': member, 'artifact': None, 'artifact_sha256': None, 'quote': None,
            'note': f"m:{demo['channel_id']}:{ts}"}


def build(demo):
    thread = demo['messages'][0][0]
    group, member = f"fixture_obs_{demo['key']}", f"member_fixture_obs_{demo['key']}"
    refs = [message_ref(demo, ts, member) for ts, *_ in demo['messages']]
    reporters = sorted({m[1] for m in demo['messages'][:2]})
    ledger = {f"m:{demo['channel_id']}:{ts}": {
        'evidence_id': f"m:{demo['channel_id']}:{ts}", 'origin': 'member_message', 'use': 'MEMBER_REPORT', 'member_id': member,
        'channel_id': demo['channel_id'], 'thread_id': thread, 'message_id': ts, 'author_id': user, 'author_role': role,
        'thread_starter_id': demo['messages'][0][1], 'excerpt': text, 'citation': {'source': {}}} for ts, user, role, text in demo['messages']}
    related = {'project_id': demo['project_id'], 'batch_id': demo['batch_id'], 'channel_id': demo['channel_id'], 'thread_id': thread,
               'member_id': member}
    body = {
        'contract_version': 'agent3-advice-card-v5', 'record_type': 'ADVICE_CARD', 'project_id': demo['project_id'],
        'topic_name': demo['topic_name'], 'card_line': 'OBSERVATION', 'summary': demo['summary'],
        'severity': {'level': 'LOW', 'assessment_status': 'ASSESSED', **RUBRIC, 'rationale': demo['severity'], 'matched_signals': [],
                     'evidence': [], 'occurrence': {
                         'affected_reporters': {'status': 'LOWER_BOUND', 'count': len(reporters), 'ids': reporters,
                                                'basis': 'Distinct authors whose own cited message reports the problem.', 'evidence': refs[:2]},
                         'affected_tasks': {'status': 'UNKNOWN', 'count': None, 'ids': [], 'basis': None, 'evidence': []},
                         'relevant_threads': [related], 'reporting_window': None,
                         'historical_recurrence': {'status': 'NOT_CHECKED', 'sources': [], 'event_series_ids': []},
                         'known_denominator': None,
                         'structural': {'threads': 1, 'messages': len(demo['messages']), 'distinct_participants': len(reporters),
                                        'duplicate_threads_ignored': 0, 'duplicate_messages_ignored': 0,
                                        'computed_from': 'fixture thread (hand-written)', 'participants_are_not_affected_reporters': True},
                         'semantic_identification': 'ASSESSED'},
                     'inherited_from': {'level': 'UNKNOWN', 'assessment_status': 'UNASSESSED', 'assessment_deferred_to': 'AGENT3',
                                        'reason': 'Agent 2 performs taxonomy only.'}},
        'severity_is_provisional': False, 'resolution_status': 'RESOLVED_IN_THREAD', 'recommended_action': None,
        'reasoning': 'What the evidence shows: ' + ' '.join(demo['details']) + ' [Test fixture: hand-written, not model output.]',
        'supporting_sources': refs,
        'related_threads': [{**related, 'permalink': None, 'display_reference': thread,
                             'label': f"{demo['channel_name']}, test fixture, started by a {demo['messages'][0][2].lower().replace('_', ' ')}: "
                                      f"\"{demo['messages'][0][3][:70]}\"", 'opening_text': demo['messages'][0][3]}],
        'confidence': 0.9, 'confidence_band': 'HIGH', 'needs_review_reasons': [], 'inherited_flags': [],
        'checks': {'grounding': 'PASSED', 'temporal_conflict': 'NONE_FOUND', 'open_confirmation': 'NONE'},
        'lineage': {'agent3_run_id': RUN_ID, 'handoff_contract': 'agent2-taxonomy-handoff-v2', 'agent2_export_sha256': '0' * 64,
                    'agent2_schema_version': 8, 'candidate_group_id': group, 'topic_id': f'{group}/topic_1', 'member_ids': [member],
                    'project_id': demo['project_id'], 'batch_id': demo['batch_id']},
        'review_notes': [], 'details': demo['details'],
        'next_step': {'status': 'NO_ACTION_NEEDED', 'rationale': demo['rationale'], 'explanation': None},
        'briefing': {'status': 'IN_BRIEFING', 'relevance': 'PROJECT', 'label_id': None, 'label_source': None, 'kept_because': [],
                     'basis': None, 'evidence_statement_ids': []},
        'outstanding_step': None, 'derivation': None}
    card = AdviceCardV5.model_validate({**body, 'card_id': stable_id('card', body)}).model_dump(mode='json')
    statements = ([{'statement_id': f'summary:s{i}', 'kind': 'SUMMARY', 'text': t, 'verdict': 'SUPPORTED', 'blocking': True,
                    'evidence_ids': list(ledger), 'rationale': 'PREPARED: hand-set verdict for the test fixture.'}
                   for i, t in enumerate([demo['summary']], 1)]
                  + [{'statement_id': f'detail:d{i}', 'kind': 'DETAIL', 'text': t, 'verdict': 'SUPPORTED', 'blocking': False,
                      'evidence_ids': [list(ledger)[i - 1]], 'rationale': 'PREPARED: hand-set verdict for the test fixture.'}
                     for i, t in enumerate(demo['details'], 1)]
                  + [{'statement_id': 'action:no_action', 'kind': 'NO_ACTION_RATIONALE', 'text': demo['rationale'], 'verdict': 'SUPPORTED',
                      'blocking': False, 'evidence_ids': list(ledger), 'rationale': 'PREPARED: hand-set verdict for the test fixture.'}])
    result = {'evidence_ledger': ledger, 'diagnostics': [], 'coverage_issues': [], 'action_notes': [],
              'tot': {'status': 'NOT_TRIGGERED', 'candidates': [], 'preferred_candidate_id': None},
              'grounding': {'status': 'PASSED', 'statements': statements, 'alternative_sufficiency': {}}, 'card': card}
    work = {'work_id': f'topic:{group}/topic_1', 'kind': 'TOPIC', 'candidate_group_id': group, 'topic_id': f'{group}/topic_1',
            'topic_name': demo['topic_name'], 'member_ids': [member], 'obligations': []}
    topic = {'work_item': work, 'workflow': {'outcome': 'CARD', 'card_id': card['card_id'], 'card_line': 'OBSERVATION',
                                             'semantic_source': 'TEST_FIXTURE'}, 'result': result}
    return card, topic


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT/'topics').mkdir(parents=True)
    cards, members = [], []
    for demo in DEMOS:
        card, topic = build(demo)
        cards.append(card)
        (OUT/'topics'/f"{topic['work_item']['candidate_group_id']}.json").write_text(
            json.dumps(topic, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        members += [{'member_id': m, 'project_id': card['project_id'], 'work_id': topic['work_item']['work_id'], 'outcome': 'CARD',
                     'card_id': card['card_id']} for m in card['lineage']['member_ids']]
    counts = {'discussion_members': len(members), 'members_on_cards': len(members), 'announcement_route_members': 0,
              'announcement_route_obligations': 0, 'inherited_agent1_obligations': 0, 'naming_cautions': 0,
              'work_items': len(cards), 'cards': len(cards), 'cards_by_line': {'OBSERVATION': len(cards)}, 'review_queue_items': 0,
              'window_announcements': 0, 'window_announcements_in_snapshot': 0}
    brief = {'brief_version': BRIEF_VERSION, 'run_id': RUN_ID, 'status': 'COMPLETE', 'cutoff': '2026-10-02T12:00:00Z',
             'window': {'start': '2026-10-01T12:00:00+00:00', 'cutoff': '2026-10-02T12:00:00+00:00', 'interval': '[start, cutoff)'},
             'semantic_judgments': 'TEST_FIXTURE', 'semantic_note': NOTE, 'validation_baseline': {}, 'counts': counts,
             'cards': [brief_card(c, 'TEST_FIXTURE') for c in cards],
             'scope': {'only': None, 'work_items_in_scope': len(cards), 'work_items': len(cards), 'out_of_scope_work': []},
             'model_review_queue': [], 'incomplete_work': [], 'projection_gaps': [], 'announcements_in_window': [],
             'usage': {'totals': {}}, 'accounting': {'status': 'COMPLETE', 'issues': []},
             'briefing': {'policy_version': 'briefing-routing-v2', 'in_briefing': len(cards), 'in_briefing_by_line': {'OBSERVATION': len(cards)},
                          'not_in_briefing': [], 'cutoff': '2026-10-02T12:00:00Z'}}
    write = lambda name, value: (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    write('run_manifest.json', {'workflow_version': 'agent3-overnight-v1', 'run_id': RUN_ID, 'test_fixture': True,
                                'test_fixture_note': NOTE, 'built_from': 'hand-written (tests/fixtures/make_observation_demo_fixture.py)'})
    write('morning_brief.json', brief)
    (OUT/'morning_brief.md').write_text(report(brief), encoding='utf-8')
    write('cards.json', cards)
    write('review_queue.json', [])
    write('accounting.json', {'status': 'COMPLETE', 'issues': [], 'counts': counts, 'members': members, 'incomplete_work': [],
                              'out_of_scope_work': [], 'projection_gaps': []})
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
