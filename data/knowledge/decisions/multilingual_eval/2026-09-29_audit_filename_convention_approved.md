---
authoring_schema: mock-knowledge-markdown-v1
document_id: multi-audit-filename-convention-approval
document_type: decision
record_kind: advice_review
project_id: multilingual_eval
scope: project
batch_id: multi_batch_11
version: '1.0'
effective_at: '2026-09-29T16:00:00Z'
last_updated: '2026-09-29T16:00:00Z'
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
  manual_key: multi-audit-filename-convention-approval
synthetic: true
tags:
- english
- language
- audit-export
- filenames
source_refs:
- document_id: multilingual-eval-instructions
  version: '1.2'
event_series_id: multi-audit-filename-convention-approval
applicability: Internal audit-index keys and attachment filenames only; excludes evaluated
  responses and quoted language evidence.
originating_advice:
  advice_id: SIM-ADV-MULTI-0929-INDEX
  provenance: simulated_prior_agent3_output
  proposed_action: UPDATE_DOCUMENTATION
  proposed_text: Use English throughout audit packets so cross-language reviewers
    can navigate them consistently.
tl_response:
  actor_id: U001
  reviewed_at: '2026-09-29T16:00:00Z'
  outcome: approved_with_edits
  text: 'Approve a narrower documentation edit: English keys and predictable filenames
    for the internal audit index. Preserve original-language prompts, responses, and
    quoted evidence. Do not translate the evaluated content or treat an English index
    field as evidence that a model switched languages.'
approved_action: UPDATE_DOCUMENTATION
---

# Approve English field names for the audit index

## Evidence available at review

The September 28 audit packet used mixed headings for the same metadata field: task_id, ID de tarea, and タスクID. The review coordinator manually matched three equivalent columns. The packet also included original Spanish and Japanese text excerpts; no defect in those excerpts was alleged.

The proposed index convention uses English metadata keys task_id, locale, and reviewer_id, with attachment names multi11_<locale>_<task_id>.txt. Only the administrative labels and filenames would change. No index revision has been published yet.

## Prior ThreadSense advice

Use English throughout audit packets so cross-language reviewers can navigate them consistently.

## TL response

Approve a narrower documentation edit: English keys and predictable filenames for the internal audit index. Preserve original-language prompts, responses, and quoted evidence. Do not translate the evaluated content or treat an English index field as evidence that a model switched languages.

## Referenced records

- [multilingual-eval-instructions v1.2](../../instructions/multilingual_eval_instructions.md)
