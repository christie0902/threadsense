---
authoring_schema: mock-knowledge-markdown-v1
document_id: multi-japanese-backup-assignment-deferred
document_type: decision
record_kind: advice_review
project_id: multilingual_eval
scope: project
batch_id: multi_batch_11
version: '1.0'
effective_at: '2026-09-28T15:00:00Z'
last_updated: '2026-09-28T15:00:00Z'
status: tl_deferred
decision_status: tl_deferred
execution_status: not_executed
outcome_status: open
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: multi-japanese-backup-assignment-deferred
synthetic: true
tags:
- japanese
- coverage
- availability
- expert-routing
source_refs:
- document_id: multilingual-eval-instructions
  version: '1.2'
event_series_id: multi-japanese-backup-assignment-deferred
applicability: Japanese QA coverage planning for September 30; does not change the
  language-specialty roster.
originating_advice:
  advice_id: SIM-ADV-MULTI-0928-JA-COVER
  provenance: simulated_prior_agent3_output
  proposed_action: ROUTE_TO_LANGUAGE_SPECIALIST
  proposed_text: Assign Leo as the September 30 backup for the Japanese QA queue because
    his calendar shows an available slot.
tl_response:
  actor_id: U001
  reviewed_at: '2026-09-28T15:00:00Z'
  outcome: deferred
  text: Defer this assignment. Availability does not establish Japanese expertise.
    Keep Yuki as the named Japanese reviewer and confirm her slot; if she is unavailable,
    bring me an appropriately qualified alternative. Do not route Japanese scoring
    decisions to Leo based only on this calendar opening.
---

# Defer a proposed Japanese QA backup assignment

## Evidence available at review

Yuki (U019, Japanese QA) had not confirmed availability for the September 30 morning review slot. Leo (U007) had an open calendar slot, but the project roster records Spanish expertise for Leo, not Japanese. No alternate Japanese specialist or reviewed Japanese case was supplied with this request.

The staffing question remains open. No reassignment, specialist opinion, or resolution of a register question is recorded here.

## Prior ThreadSense advice

Assign Leo as the September 30 backup for the Japanese QA queue because his calendar shows an available slot.

## TL response

Defer this assignment. Availability does not establish Japanese expertise. Keep Yuki as the named Japanese reviewer and confirm her slot; if she is unavailable, bring me an appropriately qualified alternative. Do not route Japanese scoring decisions to Leo based only on this calendar opening.

## Referenced records

- [multilingual-eval-instructions v1.2](../../instructions/multilingual_eval_instructions.md)
