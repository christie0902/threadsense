"""Zero-call Agent 3 input accounting against frozen Agent 2 v7 and the knowledge corpus."""
from copy import deepcopy
from pathlib import Path

import pytest

from threadsense.agents.advice_inputs import (
    DECISION_KINDS, HISTORICAL_V7, accounting_issues, code_contract, coverage, decision_record_from_source,
    inspect_handoff, review_items_from_view, structural_occurrence,
)
from threadsense.agents.topic_effective import load_effective_output
from threadsense.knowledge_markdown import markdown_source

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT/'data/knowledge/decisions'
PROJECTION = ROOT/'data/processed/agent2_handoff_v2_projection'


def script(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f'agent3_{name}', ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def view():
    return load_effective_output(HISTORICAL_V7)


def test_code_contract_matches_documented_agent2_boundary():
    assert code_contract() == {'response_schema_version': 7, 'export_schema_version': 8,
                               'export_adapter_version': 'taxonomy-to-canonical-v2', 'prompt_version': 'agent2-taxonomy-v7',
                               'rubric_version': 'DEFERRED_TO_AGENT3', 'handoff_contract': 'agent2-taxonomy-handoff-v2'}


def test_historical_v7_is_inspected_but_not_treated_as_current():
    report = inspect_handoff(HISTORICAL_V7)
    run = report['inspected_run']
    assert report['active_schema8_exports'] == ['data/processed/agent2_handoff_v2_projection']
    assert run['handoff_contracts'] == ['agent2-taxonomy-handoff-v1'] and not run['matches_current_code_contract']
    assert (run['groups'], run['topics'], run['members'], run['inherited_agent1_obligations'],
            run['applied_content_obligations'], run['effective_review_groups']) == (90, 97, 200, 49, 3, 41)
    assert run['review_binding_status'] == 'VALID' and run['accounting_issues'] == []
    assert all(e['exists'] and e['sha256_matches'] for e in run['registry']['entries_for_run'])
    assert inspect_handoff(Path('missing-run')).get('inspected_run', {}).get('error')


def test_every_obligation_becomes_one_review_item_and_losses_are_visible(view):
    items = review_items_from_view(view)
    assert len(items) == len({i.item_id for i in items}) == 52
    assert sum(i.origin == 'agent1' for i in items) == 49 and sum(i.origin == 'assisted_content_review' for i in items) == 3
    assert all(i.source_obligation for i in items)
    assert coverage(view, (), items)['missing_obligations'] == []
    assert coverage(view, (), items[1:])['missing_obligations']
    assert len(coverage(view, (), items)['missing_members']) == 200 - 49


def test_accounting_detects_dropped_or_moved_members(view):
    broken = deepcopy(view)
    row = next(r for r in broken['records'] if r['inherited_review_obligations'])
    row['member_dispositions'].pop()
    row['inherited_review_obligations'].pop()
    issues, _ = accounting_issues(broken)
    assert any('dispositions' in i for i in issues) and any('inherited obligations' in i for i in issues)


def test_structural_occurrence_counts_mechanically_and_leaves_affected_unknown():
    thread = {'project_id': 'p', 'batch_id': 'b', 'channel_id': 'C1', 'thread_id': '1790000000.000100',
              'messages': [{'ts': '1790000000.000100', 'user': 'U1'}, {'ts': '1790000100.000200', 'user': 'U2'},
                           {'message_id': '1790000200.000300', 'author_id': 'U2'}]}
    duplicate = deepcopy(thread)
    occurrence = structural_occurrence([thread, duplicate], computed_from='synthetic')
    s = occurrence.structural
    assert (s.threads, s.messages, s.distinct_participants, s.duplicate_threads_ignored) == (1, 3, 2, 1)
    assert occurrence.affected_reporters.count is None and occurrence.affected_tasks.status == 'UNKNOWN'
    assert occurrence.semantic_identification == 'PENDING'
    assert occurrence.reporting_window == {'start': '2026-09-21T14:13:20.000100+00:00', 'end': '2026-09-21T14:16:40.000300+00:00'}


def test_historical_decisions_map_without_conflating_stages():
    records = {}
    for path in DECISIONS.rglob('*.md'):
        if path.name == 'README.md':
            continue
        source = markdown_source(path)
        if source.source_metadata['authoring'].get('record_kind') in DECISION_KINDS:
            records[source.source_metadata['authoring']['document_id']] = decision_record_from_source(source)
    assert len(records) == 19
    trial = records['audio-playback-trial-approval']
    assert (trial.tl_response.outcome, trial.execution.state, trial.outcome.state) == ('APPROVED', 'NOT_EXECUTED', 'NOT_OBSERVED')
    edited = records['multi-audit-filename-convention-approval']
    assert edited.tl_response.outcome == 'APPROVED_WITH_EDITS' and 'narrower' in edited.tl_response.text
    override = records['safety-benign-mention-override']
    assert override.tl_response.severity_override.tl_selected == 'N/A' and override.original_advice.proposed_severity == 'HIGH'
    rejected = records['rp-submit-zoom-workaround-rejected'] if 'rp-submit-zoom-workaround-rejected' in records else next(
        r for r in records.values() if r.tl_response.outcome == 'REJECTED' and r.outcome.state == 'RESOLVED')
    assert rejected.execution.state == 'NOT_EXECUTED' and rejected.outcome.source_status == 'resolved_in_checked_tasks'
    assert records['multi-japanese-backup-assignment-deferred'].tl_response.outcome == 'DEFERRED'
    follow_up = markdown_source(DECISIONS/'response_preference/2026-09-20_tie_calibration_follow_up.md')
    with pytest.raises(ValueError, match='follow-ups'):
        decision_record_from_source(follow_up)


def test_validation_command_is_read_only_and_passes(tmp_path):
    import json
    main = script('validate_agent3_inputs').main
    watched = [*DECISIONS.parent.rglob('*'), *PROJECTION.rglob('*'), *(ROOT/'data/fixtures').rglob('*')]
    before = {p: p.stat().st_mtime_ns for p in watched if p.is_file()}
    assert main(['--report', str(tmp_path/'report.json')]) == 0
    report = json.loads((tmp_path/'report.json').read_text(encoding='utf-8'))
    assert {p: p.stat().st_mtime_ns for p in watched if p.is_file()} == before
    assert report['fixture_snapshots']['active'] == {
        'path': 'data/fixtures/slack_generated_demo', 'cutoff': '2026-10-02T12:00:00Z', 'threads': 201, 'messages': 517,
        'discussion_threads': 178, 'announcement_threads': 23}
    assert (report['fixture_snapshots']['original']['threads'], report['fixture_snapshots']['original']['messages']) == (200, 516)
    assert report['rubric']['version'] == 'severity-rubric-v3-semantic-signals'
    assert set(report['rubric']['project_scopes'].values()) == {'SHARED_DEFAULT'}
    assert report['review_items'] == {'model_review_items': 52, 'from_agent2_groups': 44, 'from_announcement_route': 8,
                                      'distinct_item_ids': 52, 'obligations_without_item': 0}
    with pytest.raises(SystemExit):
        main(['--report', str(tmp_path/'report.json')])


def test_demo_snapshot_adds_one_announcement_before_later_questions():
    import json
    from threadsense.routing import slack_datetime
    demo, original = ROOT/'data/fixtures/slack_generated_demo', ROOT/'data/fixtures/slack_generated'

    def messages(root):
        found = {}
        for path in (root/'channels').glob('*.json'):
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            for m in [*data['history'], *(r for rs in data['replies'].values() for r in rs)]:
                found[(data['channel']['id'], m['ts'])] = m
        return found
    new, old = messages(demo), messages(original)
    assert all(new[key] == value for key, value in old.items())
    assert set(new) - set(old) == {('C_AUDIO_ANNOUNCEMENTS', '1790892000.000901')}
    posted = slack_datetime('1790892000.000901')
    assert all(posted < slack_datetime(ts) for ts in ('1790896012.001900', '1790903186.000110'))
    assert ('C_AUDIO_GENERAL', '1790896012.001900') in new and ('C_AUDIO_QA', '1790903186.000110') in new


def test_projection_is_schema8_and_accounts_for_both_routes():
    report = inspect_handoff(PROJECTION)
    run = report['inspected_run']
    assert run['handoff_contracts'] == ['agent2-taxonomy-handoff-v2'] and run['matches_current_code_contract']
    assert run['schema_versions'] == [8] and run['accounting_issues'] == []
    assert run['projection']['fresh_taxonomy_run'] is False
    assert run['projection']['group_methods'] == {'REEXPORTED_SAVED_V7_RESPONSE': 73, 'NOT_REUSABLE_PARTIAL_GROUP': 8}
    assert (run['groups'], run['topics'], run['members']) == (81, 79, 178)
    assert run['member_dispositions'] == {'ASSIGNED': 161, 'UNASSIGNED': 17}
    assert run['announcement_route'] == {'members': 22, 'inherited_agent1_obligations': 8}
    assert run['inherited_agent1_obligations'] + run['announcement_route']['inherited_agent1_obligations'] == 49
    assert run['applied_content_obligations'] == 3 and run['review_binding_status'] == 'VALID'
    # Without its carried supplement the projection applies no cautions: nothing transfers implicitly.
    assert load_effective_output(PROJECTION)['applied_content_obligations'] == []


def test_projection_reproduces_and_refuses_existing_output(tmp_path):
    from threadsense.handoff_inputs import file_hash
    project = script('project_agent2_handoff').project
    manifest = project(HISTORICAL_V7, tmp_path/'projection')
    assert file_hash(tmp_path/'projection/consolidations.json') == file_hash(PROJECTION/'consolidations.json')
    assert manifest['model_calls'] == 0 and manifest['unresolved_naming_cautions'] == 0
    partial = [r for r in load_effective_output(PROJECTION)['records'] if r['processing_state'] == 'NOT_RUN']
    assert len(partial) == 8 and all(r['review_required'] and not r['topics'] for r in partial)
    assert all('Projection gap' in r['review_reasons'][0] for r in partial)
    with pytest.raises(ValueError, match='new output directory'):
        project(HISTORICAL_V7, tmp_path/'projection')
