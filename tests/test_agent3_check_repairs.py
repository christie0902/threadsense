"""Offline regressions for pilot v8 check repairs: author-count scope and temporal eligibility. No model calls."""
from types import SimpleNamespace

from threadsense.agents.advisor_checks import prose_issues, temporal_check


def _message(eid, author, role='QA_TUTOR'):
    return {'evidence_id': eid, 'origin': 'member_message', 'author_id': author, 'thread_starter_id': author,
            'author_role': role, 'use': 'MEMBER_REPORT'}


ONE = {'m:1': _message('m:1', 'U019')}


def plural(text, ledger=ONE):
    return [code for code, _ in prose_issues(text, list(ledger.values()), ledger)
            if code == 'PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS']


def test_people_described_inside_the_task_content_are_not_counted_as_authors():
    # The reported sentence: two speakers in the audio, one QA tutor writing.
    assert plural('A QA tutor asks whether simultaneous speech by two people should be marked unintelligible.') == []
    assert plural('The clip has two users talking over each other, a QA tutor reports.') == []


def test_an_unsupported_count_of_reporters_is_still_rejected():
    assert plural('Two people report that the overlap makes the clip unusable.')
    assert plural('The question was raised by two people in the audio channel.')
    assert plural('Three tutors ask whether the overlap is unintelligible.')
    assert plural("Two users' threads describe the same overlap.")


def test_a_supported_count_is_accepted():
    two = {'m:1': _message('m:1', 'U019'), 'm:2': _message('m:2', 'U008')}
    assert plural('Two people report that the overlap makes the clip unusable.', two) == []


def test_an_ambiguous_generic_plural_is_left_to_the_semantic_judgment():
    # Not clearly about the message authors (no reporting verb or agent): the deterministic count does not decide it;
    # the final grounding judges the claim against the cited messages.
    assert plural('Two people find the overlap confusing.') == []


def _source(eid, use, *, state='CURRENT', authoring=None, replaced_by=(), missing=()):
    return {'evidence_id': eid, 'origin': 'retrieved_source', 'use': use, 'citation': {'authoring': authoring},
            'applicability': {'state': state, 'replaced_by': [{'replaced_by': r} for r in replaced_by],
                              'unverified_supersession': [], 'supersedes': [],
                              **({'enactment': {'status': 'NOT_ENACTED', 'missing': list(missing)}} if missing else {})},
            'recorded_states': {}, 'dates': {}, 'scope': {}}


HELP = _source('k:help@1.0:a', 'HISTORY_ONLY', state='SECTION_SUPERSEDED', authoring='help@1.0', replaced_by=['clarification@1.0'])
FAQ = _source('k:faq@1.1:b', 'CURRENT_GUIDANCE', authoring='faq@1.1')
GUIDE = _source('k:guide@1.4:c', 'CURRENT_GUIDANCE', authoring='guide@1.4')
NOTE = _source('k:slack:note', 'ANNOUNCEMENT')
SYNC = _source('k:sync@1.0:d', 'PRIOR_DECISION', authoring='sync@1.0', missing=['NO_TL_APPROVAL'])
LEDGER = {s['evidence_id']: s for s in (HELP, FAQ, GUIDE, NOTE, SYNC)}


def _draft(*ids):
    return SimpleNamespace(source_conflicts=[SimpleNamespace(evidence_ids=list(ids), description='Declared conflict.')], claims=[])


def _consistency(*relations, verdict='CONFIRMED'):
    return {'relations': [{'evidence_ids': list(ids), 'relation': kind, 'point': 'p', 'disagreement_scope': 's' if kind == 'CONFLICT' else None,
                           'rationale': 'r'} for kind, ids in relations],
            'declared_conflict_checks': [{'conflict_index': 0, 'verdict': verdict, 'rationale': 'r'}]}


def _finding(draft, consistency, handling=()):
    return temporal_check(draft, LEDGER, handling=list(handling), consistency=consistency)['findings'][0]


def test_a_superseded_section_against_agreeing_current_sources_is_a_documentation_target_not_a_conflict():
    found = _finding(_draft(HELP['evidence_id'], FAQ['evidence_id'], GUIDE['evidence_id']),
                     _consistency(('AGREE', [FAQ['evidence_id'], GUIDE['evidence_id']])))
    assert found['status'] == 'RESOLVED_BY_RECORDED_STATE' and found['agreement'] == 'FINAL_GROUNDING'
    assert found['not_competing'] == {HELP['evidence_id']: 'SECTION_SUPERSEDED'}
    assert found['documentation_targets'] == [HELP['evidence_id']]


def test_current_sources_that_conflict_or_were_not_judged_to_agree_stay_detected():
    ids = HELP['evidence_id'], FAQ['evidence_id'], GUIDE['evidence_id']
    assert _finding(_draft(*ids), _consistency(('CONFLICT', [FAQ['evidence_id'], GUIDE['evidence_id']])))['status'] == 'DETECTED'
    assert _finding(_draft(*ids), None)['status'] == 'DETECTED'
    # Agreement must cover every current source in the conflict.
    assert _finding(_draft(*ids), _consistency(('AGREE', [FAQ['evidence_id'], 'k:other']))) ['status'] == 'DETECTED'


def test_an_undetermined_status_note_with_agreeing_rule_sources_is_a_documentation_question():
    draft = _draft(NOTE['evidence_id'], GUIDE['evidence_id'], SYNC['evidence_id'])
    found = _finding(draft, _consistency(('AGREE', [FAQ['evidence_id'], GUIDE['evidence_id']]), verdict='UNDETERMINED'),
                     handling=[NOTE['evidence_id']])
    assert found['status'] == 'DETECTED' and found['code'] == 'DOCUMENTATION_STATUS_UNRESOLVED'
    assert found['agreeing'] == [GUIDE['evidence_id']] and found['unsettled'] == [NOTE['evidence_id']]
    assert found['not_competing'] == {SYNC['evidence_id']: 'DECISION_NOT_APPROVED'} and found['governing_rule'] == 'AGREED'


def test_a_confirmed_rule_difference_between_current_sources_stays_an_unexplained_conflict():
    draft = _draft(NOTE['evidence_id'], GUIDE['evidence_id'], SYNC['evidence_id'])
    found = _finding(draft, _consistency(('AGREE', [FAQ['evidence_id'], GUIDE['evidence_id']]), verdict='CONFIRMED'),
                     handling=[NOTE['evidence_id']])
    assert found['code'] == 'UNEXPLAINED_SOURCE_CONFLICT'
    found = _finding(draft, _consistency(('AGREE', [GUIDE['evidence_id']]), ('CONFLICT', [NOTE['evidence_id'], GUIDE['evidence_id']]),
                                         verdict='UNDETERMINED'), handling=[NOTE['evidence_id']])
    assert found['code'] == 'UNEXPLAINED_SOURCE_CONFLICT'
