---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-submit-zoom-generalization-rejected
document_type: decision
record_kind: advice_review
project_id: response_preference
scope: project
batch_id: rp_batch_14
version: '1.0'
effective_at: '2026-09-08T16:00:00Z'
last_updated: '2026-09-08T16:00:00Z'
status: tl_rejected
decision_status: tl_rejected
execution_status: not_executed
outcome_status: resolved_in_checked_tasks
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: rp-submit-zoom-generalization-rejected
synthetic: true
tags:
- submit-button
- browser-zoom
- workaround
source_refs:
- document_id: response-preference-instructions
  version: '1.1'
event_series_id: rp-submit-zoom-generalization-rejected
applicability: 'RP14-Z011/Z012: controls below the viewport at 200% zoom, with successful
  submission at 100%.'
originating_advice:
  advice_id: SIM-ADV-RP-0908-ZOOM
  provenance: simulated_prior_agent3_output
  proposed_action: UPDATE_FAQ
  proposed_text: Add a standard FAQ answer telling every tutor with a Submit problem
    to reset browser zoom to 100% before reporting the issue.
tl_response:
  actor_id: U001
  reviewed_at: '2026-09-08T16:00:00Z'
  outcome: rejected
  text: Reject the general FAQ rule. These two reports concern a control outside the
    viewport, and their receipts establish only those two submissions. Keep the workaround
    in the case notes. A visible disabled button, a failed request, or a missing receipt
    needs its own evidence; do not close such reports based on this outcome.
---

# Reject a universal browser-zoom remedy for Submit reports

## Evidence available at review

The September 7 support notes cover RP14-Z011 and RP14-Z012 on a training workstation. At 200% browser zoom, the bottom of the form, including Submit, lay below the visible area. The button was not observed to be disabled. Returning the browser to 100% exposed the button, and both tasks produced a submission receipt: SIM-SUB-RP14-Z011 and SIM-SUB-RP14-Z012.

No network error or server rejection was recorded. These two cases were already resolved before this advice review; no action in response to the rejected recommendation has been executed.

## Prior ThreadSense advice

Add a standard FAQ answer telling every tutor with a Submit problem to reset browser zoom to 100% before reporting the issue.

## TL response

Reject the general FAQ rule. These two reports concern a control outside the viewport, and their receipts establish only those two submissions. Keep the workaround in the case notes. A visible disabled button, a failed request, or a missing receipt needs its own evidence; do not close such reports based on this outcome.

## Referenced records

- [response-preference-instructions v1.1](../../instructions/response_preference_instructions.md)
