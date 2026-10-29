---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-tie-calibration-outcome
document_type: decision
record_kind: follow_up
project_id: response_preference
scope: project
batch_id: rp_batch_14
version: '1.0'
effective_at: '2026-09-20T15:00:00Z'
last_updated: '2026-09-20T15:00:00Z'
status: reported
decision_status: reported
execution_status: calibration_completed
outcome_status: improved_in_sample
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: rp-tie-calibration-outcome
synthetic: true
tags:
- ties
- calibration
- outcome
source_refs:
- document_id: rp-tie-calibration-approval
  version: '1.0'
- document_id: rp-tie-calibration-post
  version: '1.0'
sample_summary:
  pairs: 8
  agreement_before: 2
  agreement_after: 7
  still_disputed: 1
event_series_id: RP-B14-TIE-CALIBRATION
---


# Tie calibration follow-up — improvement in the reviewed sample

## Review receipt
Alex recorded the two reviewers' decisions before and after the calibration discussion. The labels below describe the same sampled pairs, not new production judgments.

| Pair | Before: reviewer 1 / reviewer 2 | After: reviewer 1 / reviewer 2 |
| --- | --- | --- |
| RP14-C01 | Tie / A | Tie / Tie |
| RP14-C02 | A / Tie | Tie / Tie |
| RP14-C03 | Tie / B | B / B |
| RP14-C04 | A / A | A / A |
| RP14-C05 | B / Tie | B / B |
| RP14-C06 | Tie / Tie | Tie / Tie |
| RP14-C07 | A / B | Tie / Tie |
| RP14-C08 | Tie / A | Tie / A |

## TL assessment
Agreement increased from two to seven of these eight pairs. RP14-C08 remained disputed because the packet did not establish whether an output-format constraint was mandatory; that pair was retained for confirmation.

## Limit
This supports a limited calibration benefit in the reviewed sample. It does not establish independent accuracy, eliminate future disagreements, or define a universal accuracy-versus-format preference rule. A new batch needs its own evidence.

## Referenced records

- [rp-tie-calibration-approval v1.0](2026-09-16_tie_calibration_approved.md)
- [rp-tie-calibration-post v1.0](2026-09-16_tie_calibration_posted.md)
