"""Versioned provisional operational-severity rubrics; not organizational policy.

Historical severity.py describes impact but has no approval/version record.
It remains unchanged for historical decoding.
"""
RUBRIC_VERSION = 'provisional-operational-severity-v1'
CRITERIA = {
    'substantial_blockage': {'level': 'HIGH', 'definition': 'Evidence indicates substantial inability to perform or submit work; retain actual affected scope.'},
    'material_quality_risk': {'level': 'HIGH', 'definition': 'Evidence indicates material risk to labeling/data quality; distinguish reported risk from observed harm.'},
    'material_safety_risk': {'level': 'HIGH', 'definition': 'Evidence indicates material operational safety risk, beyond safety-related task vocabulary.'},
    'bounded_operational_issue': {'level': 'MEDIUM', 'definition': 'Meaningful but limited operational issue requiring clarification or coordination.'},
    'limited_demonstrated_consequence': {'level': 'LOW', 'definition': 'An operational issue with limited demonstrated consequences.'},
    'non_operational': {'level': 'N/A', 'definition': 'Clearly non-operational content such as routine social chatter; announcements are not automatically non-operational.'},
    'insufficient_impact_evidence': {'level': 'UNKNOWN', 'definition': 'Insufficient evidence of operational impact. Missing information is not evidence of low impact.'},
}
RUBRIC = {'version': RUBRIC_VERSION, 'status': 'provisional_not_approved_organizational_policy',
          'criteria': CRITERIA,
          'rules': [
              'Assess work blockage, affected scope, and potential quality/safety consequences from Slack evidence.',
              'Do not derive severity from review flags, member count, safety vocabulary, or an unanswered question alone.',
              'Task labeling categories minor/major are not operational severity.',
              'Distinguish reported risks from confirmed outcomes. Announcements can describe serious incidents.',
              'UNKNOWN is required when impact cannot be assessed; unsuccessful processing remains unassessed.',
              'No retrieval, policy-precedence decisions, or intervention recommendations. Agent 3 may separately revise this assessment.',
          ]}

# Keep v1 objects unchanged for historical v3/v4 decoding and saved experiments.
# V2 clarifies only the MEDIUM evidence threshold; levels and criterion IDs remain
# unchanged. Semantic support must still be assessed from the original messages.
from copy import deepcopy

RUBRIC_VERSION_V2 = 'provisional-operational-severity-v2'
CRITERIA_V2 = deepcopy(CRITERIA)
CRITERIA_V2['bounded_operational_issue']['definition'] = (
    'Meaningful but limited operational consequence, or prospective operational risk '
    'with a source-supported mechanism, requiring clarification or coordination. '
    'Identify the consequence or risk and explain why its evidenced scope meets this '
    'criterion. Document disagreement, an open question, or a request to check versions '
    'alone does not establish delay, rework, incorrect labeling or blocked work. '
    'Without sufficient impact evidence use insufficient_impact_evidence. '
    'Reported risk does not require harm to have already occurred.'
)
RUBRIC_V2 = {**deepcopy(RUBRIC), 'version': RUBRIC_VERSION_V2, 'criteria': CRITERIA_V2}
