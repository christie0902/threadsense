---
authoring_schema: mock-knowledge-markdown-v1
document_id: multi-korean-referral
document_type: decision
record_kind: expert_referral
project_id: multilingual_eval
scope: project
batch_id: multi_batch_10
version: '1.0'
effective_at: '2026-09-12T14:00:00Z'
last_updated: '2026-09-12T14:00:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: routed
outcome_status: pending_expert_review
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: multi-korean-referral
synthetic: true
tags:
- korean
- register
- specialist
source_refs:
- document_id: multilingual-eval-instructions
  version: '1.2'
assigned_specialist:
  user_id: U008
  language: ko
event_series_id: M10-KO-017
---


# Korean register case referred to language QA

## Request
M10-KO-017 contains a polite narrative followed by a casual sentence inside quotation marks. The packet did not identify whether the quoted speaker and addressee changed.

## TL decision
Alex routed the case to Hana (U008), whose recorded specialty is Korean, with the exact endings and surrounding paragraph. Do not assign a major register penalty from the ending change alone.

## Requested assessment
Establish who is speaking, whether the quote is intentional, and whether the language remains appropriate for the intended audience. The original scoring question stays open until that context is reviewed.

## Scope
This referral concerns M10-KO-017 in batch 10. It is not a general exemption for Korean register shifts.

## Referenced records

- [multilingual-eval-instructions v1.2](../../instructions/multilingual_eval_instructions.md)
