---
authoring_schema: mock-knowledge-markdown-v1
document_id: multi-korean-scoped-result
document_type: decision
record_kind: expert_review
project_id: multilingual_eval
scope: project
batch_id: multi_batch_10
version: '1.0'
effective_at: '2026-09-14T15:00:00Z'
last_updated: '2026-09-14T15:00:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: assessment_recorded
outcome_status: resolved_for_scoped_case
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: multi-korean-scoped-result
synthetic: true
tags:
- korean
- quotation
- scoped-confirmation
source_refs:
- document_id: multi-korean-referral
  version: '1.0'
- document_id: multilingual-eval-instructions
  version: '1.2'
expert:
  user_id: U008
  language: ko
  role: QA_TUTOR
approved_action: NO_ACTION
event_series_id: M10-KO-017
---


# Scoped Korean finding confirmed by the TL

## Specialist finding
Hana reviewed the complete paragraph for M10-KO-017. The casual sentence was a quoted utterance from a different speaker, and the surrounding narration retained its polite register. She found no unsupported shift by the narrator.

## TL confirmation
Alex confirmed no register-consistency penalty for this exact quoted-speaker case. The finding does not authorize a casual switch while addressing the same person without a discourse reason.

## Result and limits
The batch-10 question for M10-KO-017 is resolved. Later same-addressee cases require their own context; an older favorable ruling cannot be transferred merely because both texts contain polite and casual endings.

## Referenced records

- [multi-korean-referral v1.0](2026-09-12_korean_register_referred.md)
- [multilingual-eval-instructions v1.2](../../instructions/multilingual_eval_instructions.md)
