---
authoring_schema: mock-knowledge-markdown-v1
document_id: safety-audit-export-escape-approval
document_type: decision
record_kind: advice_review
project_id: safety_classification
scope: project
batch_id: safety_batch_08
version: '1.0'
effective_at: '2026-09-23T14:00:00Z'
last_updated: '2026-09-23T14:00:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: not_executed
outcome_status: not_observed
authority:
  actor_id: U006
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: safety-audit-export-escape-approval
synthetic: true
tags:
- json
- format
- audit-export
- engineering
source_refs:
- document_id: safety-classification-instructions
  version: '1.4'
event_series_id: S08-AUDIT-EXPORT-ESCAPING
applicability: Safety batch 08 audit-export serializer; not output-format scoring
  or content classification.
originating_advice:
  advice_id: SIM-ADV-SAFETY-0923-EXPORT
  provenance: simulated_prior_agent3_output
  proposed_action: ESCALATE_ENGINEERING
  proposed_text: Escalate the audit-export serializer with the two failing note examples,
    request correctly escaped JSON, and preserve the source ratings while the export
    is repaired.
tl_response:
  actor_id: U006
  reviewed_at: '2026-09-23T14:00:00Z'
  outcome: approved
  text: Approved for the export component. Send Tariq the two reproduction rows and
    require round-trip checks of the note text plus unchanged labels. Do not ask tutors
    to rewrite their notes or change safety classifications to accommodate the exporter.
approved_action: ESCALATE_ENGINEERING
---

# Approve an escalation for invalid JSON in audit exports

## Evidence available at review

Two archived audit rows failed JSON parsing: S08-EXP-004 contained a quotation mark inside a reviewer note, and S08-EXP-009 contained a line break. In each failed export the note had been inserted without the required JSON escaping. Both saved LT task records could still be opened, with their existing labels intact.

The export failure blocked a two-row audit transfer. No production task submission failure, lost rating, or incorrect safety label was established. The proposed engineering handoff includes these two synthetic rows; it has not yet been sent.

## Prior ThreadSense advice

Escalate the audit-export serializer with the two failing note examples, request correctly escaped JSON, and preserve the source ratings while the export is repaired.

## TL response

Approved for the export component. Send Tariq the two reproduction rows and require round-trip checks of the note text plus unchanged labels. Do not ask tutors to rewrite their notes or change safety classifications to accommodate the exporter.

## Referenced records

- [safety-classification-instructions v1.4](../../instructions/safety_classification_instructions.md)
