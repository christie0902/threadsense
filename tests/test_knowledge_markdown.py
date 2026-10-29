"""Markdown knowledge ingestion through the shared SourceRecord contract.

Real-corpus checks only read data/knowledge; synthetic variants live in tmp_path.
"""
import json
from pathlib import Path

import pytest

from threadsense.knowledge_corpus import discover, validate_corpus
from threadsense.knowledge_markdown import markdown_source, split_front_matter
from threadsense.knowledge_sources import iter_documents, normalize_document

KNOWLEDGE = Path(__file__).resolve().parents[1]/'data/knowledge'
DECISIONS = KNOWLEDGE/'decisions'
PII_POST = DECISIONS/'safety_classification/2026-09-11_fictional_pii_clarification_posted.md'
HELP_PAGE = KNOWLEDGE/'instructions/history/safety_qn_help_page_v1.0.md'
CLARIFICATION = DECISIONS/'safety_classification/safety_fictional_pii_clarification_2026-09-10.md'


def copy(path, tmp_path, name=None, replace=()):
    text = Path(path).read_text(encoding='utf-8')
    for old, new in replace:
        assert old in text
        text = text.replace(old, new)
    target = tmp_path/(name or Path(path).name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
    return target


@pytest.fixture(scope='module')
def corpus():
    return validate_corpus(KNOWLEDGE)


def test_real_corpus_normalizes_with_stable_ids(corpus):
    assert corpus['discovered'] == {'markdown': 40, 'json': 0}
    assert corpus['normalized_documents'] == corpus['shared_ingestion_documents'] == 40
    assert corpus['counts']['document_type'] == {'decision': 24, 'announcement': 7, 'faq': 4, 'guideline': 5}
    assert corpus['counts']['slack_snapshots_verified'] == 6
    assert corpus['stable_ids_on_repeat'] and not corpus['normalization_failures']
    assert not corpus['authoring_conflicts'] and not corpus['duplicate_representations']


def test_discovery_excludes_policy_lexicon_and_bookkeeping():
    found = discover(KNOWLEDGE)
    excluded = {item['file'] for item in found['excluded']}
    assert {'severity_rubric.py', 'domain_lexicon.json'} <= excluded
    assert all(p.name != 'README.md' for p in found['markdown'])
    assert not any(p.suffix == '.py' for p in [*found['markdown'], *found['json']])


def test_instructions_map_to_guideline_and_metadata_survives():
    r = markdown_source(KNOWLEDGE/'instructions/safety_classification_instructions.md')
    assert (r.document_type, r.record_kind, r.scope, r.source.system) == ('guideline', 'guideline', 'project', 'manual')
    meta = r.source_metadata
    assert meta['canonical_mapping']['authoring_document_type'] == 'instructions'
    assert meta['authoring']['document_id'] == 'safety-classification-instructions' and meta['authoring']['version'] == '1.4'
    assert r.authority['recorded_role'] == 'TEAM_LEAD' and r.authority['provenance'] == 'synthetic_manual_record'
    assert r.authority['approval_status'] == 'EXPLICIT_SOURCE_MARKER' and meta['authoring']['synthetic'] is True
    # effective_at is not a creation time; manual records have none.
    assert r.effective_at == '2026-09-10T15:00:00Z' and r.created_at is None
    assert meta['source_refs'][0]['document_id'] == 'safety-fictional-pii-clarification'


def test_rich_decision_kinds_and_tl_lifecycle_are_preserved():
    deferred = markdown_source(DECISIONS/'multilingual_eval/2026-09-28_japanese_backup_assignment_deferred.md')
    assert deferred.record_kind == 'decision'
    assert deferred.source_metadata['canonical_mapping']['authoring_record_kind'] == 'advice_review'
    life = deferred.source_metadata['lifecycle']
    assert life['original_advice']['proposed_action'] == 'ROUTE_TO_LANGUAGE_SPECIALIST'
    assert life['tl_response']['outcome'] == 'deferred' and life['execution_status'] == 'not_executed'
    assert deferred.authority['approval_status'] == 'NO_APPROVAL_MARKER'
    kinds = {markdown_source(p).source_metadata['authoring'].get('record_kind') for p in DECISIONS.rglob('*.md')
             if p.name != 'README.md'}
    assert {'advice_review', 'follow_up', 'expert_referral', 'escalation_receipt'} <= kinds
    override = markdown_source(DECISIONS/'safety_classification/2026-09-26_benign_mention_severity_overridden.md')
    assert override.source_metadata['lifecycle']['severity_override'] == {
        'proposed': 'HIGH', 'tl_selected': 'N/A', 'reason': 'No operational problem or required-control failure in the reviewed complete case.'}
    trial = markdown_source(DECISIONS/'audio_multimodal/2026-08-24_playback_trial_approved.md')
    assert trial.source_metadata['authoring']['valid_until'] == '2026-08-28T21:00:00Z'
    assert trial.source_metadata['authoring']['event_series_id'] == 'AUDIO-B05-PLAYBACK-TRIAL'
    assert trial.source.batch_id == 'audio_batch_05'


def test_section_level_supersession_is_not_widened(corpus):
    old, new = markdown_source(HELP_PAGE), markdown_source(CLARIFICATION)
    assert old.supersedes == [] and new.supersedes == []
    assert new.source_metadata['supersession']['supersedes'] == [
        {'document_id': 'safety-qn-help-page', 'version': '1.0', 'section': 'Contact details', 'granularity': 'section'}]
    assert old.source_metadata['supersession']['superseded_by'][0]['section'] == 'Contact details'
    assert 'Other safety concerns' in old.source_metadata['section_headings']
    assert corpus['supersession'] == [{'from': 'safety-fictional-pii-clarification@1.0', 'to': 'safety-qn-help-page@1.0',
                                       'section': 'Contact details', 'granularity': 'section'}]
    assert corpus['reference_issues'] == []


def test_folder_project_mismatch_is_reported_without_overriding(tmp_path):
    root = tmp_path/'knowledge'
    headset = DECISIONS/'audio_multimodal/2026-09-21_headset_output_check_approved.md'
    misplaced = copy(headset, root/'decisions/multilingual_eval')
    report = validate_corpus(root, fixture_root=None)
    [issue] = [i for i in report['reference_issues'] if i['kind'] == 'folder_project_mismatch']
    assert (issue['kind'], issue['folder'], issue['declared']) == ('folder_project_mismatch', 'multilingual_eval', 'audio_multimodal')
    assert 'Neither value is overridden' in issue['detail']
    record = markdown_source(misplaced)
    assert record.source.project_id == 'audio_multimodal'
    assert (record.record_id, record.version_id) == (markdown_source(headset).record_id, markdown_source(headset).version_id)


def test_slack_records_keep_identity_and_verified_snapshot():
    r = markdown_source(PII_POST)
    assert r.source.system == 'slack' and r.source.manual_key is None
    assert (r.source.channel_id, r.source.thread_id, r.source.message_id) == (
        'C_SAFETY_ANNOUNCEMENTS', '1789135200.700004', '1789135200.700004')
    assert r.created_at == '2026-09-11T14:00:00.700004+00:00' and r.effective_at == '2026-09-11T14:00:00Z'
    assert r.author == {'id': 'U006', 'name': None, 'recorded_role': 'TEAM_LEAD'}
    assert r.source_metadata['snapshot_verification']['embedded_snapshot_sha256'] == 'MATCH'
    assert r.source_metadata['root_message']['ts'] == '1789135200.700004'
    document = normalize_document(r)
    # Retrieval text is the Slack message; raw snapshot and link lists stay metadata.
    assert document['text'] == r.source_metadata['root_message']['text']
    assert '"channel_type"' not in document['text'] and 'Referenced records' not in document['text']


def test_tampered_snapshot_or_identity_fails(tmp_path):
    tampered = copy(PII_POST, tmp_path, replace=[('Retain the surrounding context. Ambiguous', 'Ambiguous')])
    with pytest.raises(ValueError, match='message_text_sha256'):
        markdown_source(tampered)
    moved = copy(PII_POST, tmp_path, 'moved.md', replace=[("message_id: '1789135200.700004'", "message_id: '1789135200.700005'")])
    with pytest.raises(ValueError, match='ts differs'):
        markdown_source(moved)


def test_manual_retrieval_text_drops_only_bookkeeping():
    r = markdown_source(DECISIONS/'safety_classification/2026-09-26_benign_mention_severity_overridden.md')
    assert r.original_text.startswith('# TL overrides') and '## TL override' in r.original_text
    assert 'Referenced records' not in r.original_text and 'severity_override' not in r.original_text


def test_ids_are_path_independent_and_changes_create_versions(tmp_path):
    original = markdown_source(CLARIFICATION)
    moved = markdown_source(copy(CLARIFICATION, tmp_path/'elsewhere'))
    assert (moved.record_id, moved.version_id) == (original.record_id, original.version_id)
    edited = markdown_source(copy(CLARIFICATION, tmp_path, 'edited.md',
                                  replace=[('Clearly fictional placeholder', 'Clearly fictional sample')]))
    assert edited.record_id == original.record_id and edited.version_id != original.version_id


def test_conflicting_authoring_identity_is_detected(tmp_path):
    root = tmp_path/'knowledge'
    copy(CLARIFICATION, root/'decisions/safety_classification')
    copy(CLARIFICATION, root/'decisions/safety_classification', 'copy.md',
         replace=[('Clearly fictional placeholder', 'Clearly fictional sample')])
    with pytest.raises(ValueError, match='authoring identity safety-fictional-pii-clarification@1.0'):
        list(iter_documents(sorted((root/'decisions').rglob('*.md'))))
    report = validate_corpus(root, fixture_root=None)
    assert report['authoring_conflicts'][0]['authoring_identity'] == 'safety-fictional-pii-clarification@1.0'
    assert report['shared_ingestion_error'] and report['overlap_scope'] == 'FIXTURES_NOT_AVAILABLE'


def test_identical_copy_is_reported_not_double_counted(tmp_path):
    root = tmp_path/'knowledge'
    copy(PII_POST, root/'decisions/safety_classification')
    copy(PII_POST, root/'decisions/safety_classification', 'again.md')
    report = validate_corpus(root, fixture_root=None)
    assert report['shared_ingestion_documents'] == 1 and report['duplicate_representations']
    assert {o['kind'] for o in report['overlapping_representations']} == {
        'same_slack_message_in_corpus', 'same_slack_text_in_corpus'}


def test_yaml_is_safe_and_timestamps_and_versions_stay_strings(tmp_path):
    front, _ = split_front_matter(CLARIFICATION.read_text(encoding='utf-8'))
    assert front['effective_at'] == '2026-09-10T13:00:00Z' and front['version'] == '1.0'
    unquoted = copy(CLARIFICATION, tmp_path, replace=[("version: '1.0'", 'version: 1.0')])
    with pytest.raises(ValueError, match='quoted string'):
        markdown_source(unquoted)
    unsafe = copy(CLARIFICATION, tmp_path, 'unsafe.md', replace=[('synthetic: true', 'synthetic: !!python/object/apply:os.getcwd []')])
    with pytest.raises(Exception, match='constructor'):
        markdown_source(unsafe)
    kind = copy(CLARIFICATION, tmp_path, 'kind.md', replace=[('decision_id:', 'record_kind: invented_kind\ndecision_id:')])
    with pytest.raises(ValueError, match='not mapped'):
        markdown_source(kind)


def test_json_and_markdown_share_one_ingestion_path(tmp_path):
    from tests.test_announcement_routing import source
    from threadsense.knowledge_sources import extract_announcement
    record = extract_announcement(source(), captured_at='1970-01-03T00:00:00Z')
    manual = tmp_path/'decisions/p1/manual/source-v1.json'
    manual.parent.mkdir(parents=True)
    manual.write_text(json.dumps(record.model_dump()), encoding='utf-8')
    documents = list(iter_documents([manual, CLARIFICATION]))
    by_id = {d['document_id']: d for d in documents}
    assert set(by_id) == {record.record_id, markdown_source(CLARIFICATION).record_id}
    assert by_id[record.record_id] == normalize_document(record)
