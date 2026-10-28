"""Test-only schema builders. Membership stubs make no semantic-quality claim."""
from threadsense.legacy.agent2.topic_evidence import evidence_catalog
from threadsense.legacy.agent2.operational_severity import RUBRIC_VERSION


def cited(text, ids):
    return {'text': text, 'evidence_ids': list(ids)}


def severity(ids, level='UNKNOWN', criterion='insufficient_impact_evidence', rationale='Synthetic test: no operational impact assessment.'):
    return {'level': level, 'rubric_version': RUBRIC_VERSION, 'matched_criteria': [criterion],
            'rationale': cited(rationale, ids), 'work_blockage': None, 'affected_scope': None,
            'quality_or_safety_consequences': None,
            'evidence_basis': 'INSUFFICIENT_EVIDENCE' if level == 'UNKNOWN' else 'REPORTED_RISK',
            'severity_is_provisional': True}


def membership_only_draft(payload):
    """Explicitly synthetic wiring stub; never a reviewed factual summary."""
    aliases, catalog = evidence_catalog(payload)
    roots = [eid for eid, e in catalog.items() if not e['is_reply']]
    return {'schema_version': 3, 'candidate_group_id': payload['candidate_group_id'],
            'project_id': payload['project_id'], 'batch_id': payload['batch_id'],
            'is_coherent': True, 'coherence_rationale': 'Synthetic membership-only fixture.',
            'needs_review': False, 'review_reasons': [], 'topics': [{
                'topic_name': 'Synthetic structure-only fixture', 'member_ids': list(aliases),
                'conversation_kind': 'DISCUSSION',
                'shared_issue': cited('Synthetic structure-only result; not a factual conclusion.', roots),
                'representative_question': None, 'relevant_differences': [], 'open_questions': [],
                'supported_answers': [], 'guidance': [], 'uncertainties': [],
                'source_assessments': [{'evidence_id': eid, 'question_status': 'NONE', 'guidance_status': 'NONE'} for eid in catalog],
                'preliminary_severity': severity(roots[:1]),
            }]}


def guidance(text, ids, *, scope, limitations=(), kind='SCOPED_ANSWER', authority='SOURCE_REPLY'):
    return {**cited(text, ids), 'kind': kind, 'authority': authority,
            'scope': cited(scope, ids), 'limitations': [cited(limit, ids) for limit in limitations]}
