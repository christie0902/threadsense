---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-format-rule-rejected
document_type: decision
record_kind: advice_review
project_id: response_preference
scope: project
batch_id: rp_batch_15
version: '1.0'
effective_at: '2026-09-23T16:00:00Z'
last_updated: '2026-09-23T16:00:00Z'
status: tl_rejected
decision_status: tl_rejected
execution_status: not_executed
outcome_status: no_policy_change
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: rp-format-rule-rejected
synthetic: true
tags:
- json
- format-versus-accuracy
- confirmation
source_refs:
- document_id: response-preference-instructions
  version: '1.1'
- document_id: response-preference-faq
  version: '1.1'
originating_advice:
  advice_id: SIM-ADV-RP-0923
  provenance: simulated_prior_agent3_output
  proposed_action: UPDATE_DOCUMENTATION
  proposed_text: Always prefer the JSON-formatted response when JSON is required.
approved_action: null
event_series_id: rp-format-rule-rejected
---


# TL rejects a universal JSON-first preference rule

## Suggested advice
A simulated prior Advisor card proposed: “Whenever the prompt requires JSON, prefer the JSON-formatted response over prose.”

## TL response
Alex rejected this as a universal rule. A required format violation is a real instruction-adherence defect, but format compliance alone does not establish the better response when the other candidate has a different factual defect.

The review packet lacked the complete prompt and both responses. Request those materials and score the dimensions separately. A case-specific decision may be possible once they are available; this review makes no such decision.

## Consequence
No general JSON-first rule was approved, posted or added to the FAQ. Rejection also does not create a prose-first rule. Keep genuinely unresolved trade-offs open for TL confirmation.

## Referenced records

- [response-preference-instructions v1.1](../../instructions/response_preference_instructions.md)
- [response-preference-faq v1.1](../../faq/response_preference_faq.md)
