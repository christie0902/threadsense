# Demo scenario coverage: expected versus observed

Levels: live = real model calls; scripted = prepared judgments; placeholder = judges nothing. Severity is recorded, not scored (pending TL rubric decision for rule-confusion topics). Source columns count expected sources retrieved into the evidence ledger; a relation violation means the source was retrieved but used differently than expected.

| Scenario | Run | Level | Card line | Action | Action OK | Required reasons | Sources | Relation violations | ToT | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| faq_edge_case | agent3_final_eval_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 5/5 | - | COMPARED | HIGH (ASSESSED) |
| faq_edge_case | agent3_repair_eval_v1 | live | NEEDS_REVIEW | none shown | - | yes | 5/5 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| faq_edge_case | agent3_policy_eval_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 3/5 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| faq_edge_case | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | UPDATE_FAQ | yes | yes | 5/5 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| tl_confirmation | agent3_final_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | yes | yes | 2/3 | - | COMPARED | MEDIUM (ASSESSED) |
| tl_confirmation | agent3_repair_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | yes | yes | 2/3 | - | COMPARED | MEDIUM (ASSESSED) |
| tl_confirmation | agent3_policy_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | yes | yes | 2/3 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| tl_confirmation | agent3_summary_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | yes | yes | 2/3 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| tl_confirmation | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | NO_ACTION | yes | yes | 3/3 | - | COMPARED | MEDIUM (ASSESSED) |
| instruction_conflict | agent3_final_eval_v1 | live | NEEDS_REVIEW | UPDATE_DOCUMENTATION | yes | yes | 2/3 | - | COMPARED | MEDIUM (ASSESSED) |
| instruction_conflict | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | UPDATE_DOCUMENTATION | yes | yes | 2/3 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| language_routing | agent3_final_eval_v1 | live | NEEDS_REVIEW | ROUTE_TO_LANGUAGE_SPECIALIST | yes | yes | 3/3 | - | COMPARED | MEDIUM (ASSESSED) |
| language_routing | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | ROUTE_TO_LANGUAGE_SPECIALIST | yes | yes | 3/3 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| technical_escalation | agent3_final_eval_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 3/3 | - | COMPARED | HIGH (ASSESSED) |
| technical_escalation | agent3_repair_eval_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_summary_eval_v1 | live | NEEDS_REVIEW | none shown | - | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_submit_repair_v1 | live | NEEDS_REVIEW | none shown | - | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_request_kind_v1 | live | NEEDS_REVIEW | none shown | - | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_source_fact_v1 | live | NEEDS_REVIEW | none shown | - | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_recipient_routing_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| technical_escalation | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 3/3 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| already_announced | agent3_final_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | yes | yes | 1/2 | - | COMPARED | HIGH (ASSESSED) |
| already_announced | agent3_repair_eval_v1 | live | NEEDS_REVIEW | ESCALATE_ENGINEERING | yes | yes | 2/2 | - | NOT_TRIGGERED | HIGH (ASSESSED) |
| already_announced | agent3_overnight_offline_v2 | placeholder | NEEDS_REVIEW | none shown | - | yes | 1/2 | - | COMPARED | UNKNOWN (UNASSESSED) |
| qa_misalignment | agent3_final_eval_v1 | live | NEEDS_REVIEW | SCHEDULE_ALIGNMENT | yes | yes | 2/4 | - | COMPARED | HIGH (ASSESSED) |
| qa_misalignment | agent3_repair_eval_v1 | live | NEEDS_REVIEW | SCHEDULE_ALIGNMENT | yes | yes | 3/4 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| qa_misalignment | agent3_policy_eval_v1 | live | NEEDS_REVIEW | SCHEDULE_ALIGNMENT | yes | yes | 3/4 | - | NOT_TRIGGERED | MEDIUM (ASSESSED) |
| qa_misalignment | agent3_overnight_offline_v2 | placeholder | NEEDS_REVIEW | none shown | - | yes | 2/4 | - | COMPARED | UNKNOWN (UNASSESSED) |
| observation_only | agent3_final_eval_v1 | live | NEEDS_REVIEW | POST_ALIGNMENT | NO | yes | 2/2 | - | COMPARED | HIGH (ASSESSED) |
| observation_only | agent3_repair_eval_v1 | live | NEEDS_REVIEW | none shown | - | yes | 2/2 | - | NOT_TRIGGERED | LOW (ASSESSED) |
| observation_only | agent3_policy_eval_v1 | live | NEEDS_REVIEW | none shown | - | yes | 2/2 | - | NOT_TRIGGERED | LOW (ASSESSED) |
| observation_only | agent3_overnight_offline_v2 | scripted | NEEDS_REVIEW | NO_ACTION | yes | yes | 2/2 | - | COMPARED | MEDIUM (ASSESSED) |
| upstream_flags | agent3_final_eval_v1 | live | NEEDS_REVIEW | ROUTE_TO_LANGUAGE_SPECIALIST | yes | yes | 2/2 | - | COMPARED | MEDIUM (ASSESSED) |
| upstream_flags | agent3_overnight_offline_v2 | placeholder | NEEDS_REVIEW | none shown | - | yes | 2/2 | - | COMPARED | UNKNOWN (UNASSESSED) |
