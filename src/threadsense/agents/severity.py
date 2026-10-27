
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NOT_APPLICABLE = "N/A"


SEVERITY_RUBRIC = {
    SeverityLevel.LOW: {
        "definition": (
            "Localized issue with limited impact on labeling quality or "
            "workflow. Work continues normally, and any correction is "
            "straightforward."
        ),
        "examples": (
            "One-off clarification, minor LT inconvenience, isolated "
            "inconsistency with no meaningful downstream impact."
        ),
    },
    SeverityLevel.MEDIUM: {
        "definition": (
            "Issue that may affect labeling accuracy, QA consistency, or "
            "operational efficiency, requiring clarification or intervention. "
            "Impact is meaningful but appears contained or manageable."
        ),
        "examples": (
            "Recurring rubric ambiguity, conflicting QA interpretations, "
            "intermittent LT failures affecting task completion, unclear "
            "QN handling for a specific edge case."
        ),
    },
    SeverityLevel.HIGH: {
        "definition": (
            "Issue creating a serious risk to data integrity, labeling "
            "quality, operational continuity, or required safety procedures. "
            "May affect many tasks, cause difficult-to-reverse errors, "
            "or require prompt escalation."
        ),
        "examples": (
            "Widespread incorrect labeling caused by conflicting instructions, "
            "lost labels, required QN/safety controls being bypassed, major "
            "LT outage, systemic QA misalignment affecting an entire batch."
        ),
    },
    SeverityLevel.NOT_APPLICABLE: {
        "definition": (
            "No identifiable operational problem or risk requiring "
            "severity assessment."
        ),
        "examples": (
            "Routine announcements, informational updates, acknowledgments, "
            "administrative messages, general discussion without an "
            "actionable issue."
        ),
    },
}


# Historical enum/rubric above remain unchanged. Active taxonomy uses the versioned
# operational rubric without semantic extraction from topic names or prose.
from copy import deepcopy
from threadsense.agents.operational_severity import RUBRIC_V2

DETERMINISTIC_RULE_VERSION = 'canonical-impact-availability-v1'


def assess_canonical_impact(members):
    """The current Agent 1 contract has no structured operational-impact signals.

    A summary, resolution label or review flag is not an impact measurement.
    Keep UNKNOWN until a separately approved canonical impact contract exists;
    do not invent fields, parse prose, scan Slack or recycle old Agent 2 severity.
    """
    return {'level':'UNKNOWN', 'assessment_status':'UNASSESSED',
        'rubric_version':RUBRIC_V2['version'], 'severity_is_provisional':True,
        'assessor':'deterministic_post_export', 'rule_version':DETERMINISTIC_RULE_VERSION,
        'basis':'INSUFFICIENT_EVIDENCE',
        'reason':'Canonical Agent 1 inputs contain no approved structured operational-impact signals; no new interpretation performed.',
        'input_provenance':[{'member_id':m['member_id'],'candidate_sha256':m['agent1_record']['candidate_sha256'],
                             'source_sha256':m['agent1_record']['input_sha256']} for m in members]}


def attach_preliminary_severity(record):
    """Attach independent metadata after taxonomy export; never invalidate a partition."""
    row=deepcopy(record); members={m['member_id']:m for m in row['members']}
    for topic in row['topics']:
        selected=[members[mid] for mid in topic['member_ids']]
        assessment=assess_canonical_impact(selected)
        topic['preliminary_severity']=assessment
        high=assessment['level']=='HIGH'
        topic['morning_review_required']=high
        if high:
            topic['review_required']=row['review_required']=True
            row['morning_review_obligations'].append({'topic_id':topic['topic_id'],
                'reason':'HIGH preliminary severity; nonblocking review.', 'assessment':deepcopy(assessment)})
            row['review_reasons'].append('HIGH preliminary severity requires nonblocking review.')
    row['unassigned_preliminary_severity']=assess_canonical_impact(
        [members[mid] for mid in row['rejected_member_ids']+row['unassigned_member_ids']]) if row['rejected_member_ids'] or row['unassigned_member_ids'] else None
    return row
