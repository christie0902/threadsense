---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-tie-calibration-approval
document_type: decision
record_kind: advice_review
project_id: response_preference
scope: project
batch_id: rp_batch_14
version: '1.0'
effective_at: '2026-09-16T13:30:00Z'
last_updated: '2026-09-16T13:30:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: pending_post
outcome_status: not_observed
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: rp-tie-calibration-approval
synthetic: true
tags:
- ties
- qa-alignment
- calibration
source_refs:
- document_id: response-preference-instructions
  version: '1.1'
- document_id: response-preference-faq
  version: '1.1'
originating_advice:
  advice_id: SIM-ADV-RP-0916
  provenance: simulated_prior_agent3_output
  proposed_action: POST_ALIGNMENT
  proposed_text: Calibrate ties against meaningful quality differences using sampled pairs.
approved_action: POST_ALIGNMENT
event_series_id: RP-B14-TIE-CALIBRATION
---


# RP-20260916-01 — Approve tie calibration advice

## Context
The prior batch's calibration packet contained one pair differing only in wording and another in which one response omitted a fact needed for the user's request. Reviewers were using “slightly clearer” without explaining whether it changed usefulness.

## Suggested advice
The simulated Advisor proposed a brief alignment announcement and a review of eight sampled pairs, using the existing meaningful-quality-difference criterion.

## TL approval
Alex approved the proposal. Ask reviewers to identify the actual user-facing benefit; a cosmetic wording preference alone is not sufficient. Keep material accuracy or instruction defects visible rather than forcing ties.

This is a calibration of the existing criterion, not a new numerical preference threshold. The approval covers the batch-14 exercise.

## State
Posting and the review exercise are authorized but not recorded as completed in this approval.

## Referenced records

- [response-preference-instructions v1.1](../../instructions/response_preference_instructions.md)
- [response-preference-faq v1.1](../../faq/response_preference_faq.md)
