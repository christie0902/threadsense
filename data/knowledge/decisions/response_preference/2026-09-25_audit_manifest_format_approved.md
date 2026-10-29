---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-audit-manifest-approval
document_type: decision
record_kind: advice_review
project_id: response_preference
scope: project
batch_id: rp_batch_15
version: '1.0'
effective_at: '2026-09-25T15:00:00Z'
last_updated: '2026-09-25T15:00:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: not_executed
outcome_status: not_observed
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: rp-audit-manifest-approval
synthetic: true
tags:
- json
- format
- audit-export
- file-naming
source_refs:
- document_id: response-preference-instructions
  version: '1.1'
event_series_id: RP15-AUDIT-MANIFEST
applicability: RP batch 15 weekly audit manifest files produced by QA; excludes the
  model responses being evaluated.
originating_advice:
  advice_id: SIM-ADV-RP-0925-MANIFEST
  provenance: simulated_prior_agent3_output
  proposed_action: POST_ALIGNMENT
  proposed_text: Publish one naming and JSON structure convention for QA weekly audit
    manifests so the handoff files can be combined without manual interpretation.
tl_response:
  actor_id: U001
  reviewed_at: '2026-09-25T15:00:00Z'
  outcome: approved
  text: Approved for QA audit manifest files in rp_batch_15. Use batch_id, audit_date,
    and task_ids with the filename rp15_audit_YYYY-MM-DD.json. This decision concerns
    the export artifact; it creates no preference rule for JSON versus prose in the
    responses tutors score.
approved_action: POST_ALIGNMENT
---

# Approve a JSON format for weekly audit manifests

## Evidence available at review

The September 24 QA handoff contained two audit manifests, RP15-AUD-01 and RP15-AUD-02, with filenames that omitted the batch. One used a prose list of task IDs; the other used a JSON array. Alex needed to combine the audit packets, not compare model answers.

The proposed administrative convention is a JSON object containing batch_id, audit_date, and task_ids, saved as rp15_audit_YYYY-MM-DD.json. Existing task ratings and rationales remain unchanged.

The review approves the convention and a short channel draft. At this cutoff the draft is not posted and no converted export has been checked.

## Prior ThreadSense advice

Publish one naming and JSON structure convention for QA weekly audit manifests so the handoff files can be combined without manual interpretation.

## TL response

Approved for QA audit manifest files in rp_batch_15. Use batch_id, audit_date, and task_ids with the filename rp15_audit_YYYY-MM-DD.json. This decision concerns the export artifact; it creates no preference rule for JSON versus prose in the responses tutors score.

## Referenced records

- [response-preference-instructions v1.1](../../instructions/response_preference_instructions.md)
