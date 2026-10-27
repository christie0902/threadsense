"""Provisional operational-severity rubric v1; not approved organizational policy.

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
