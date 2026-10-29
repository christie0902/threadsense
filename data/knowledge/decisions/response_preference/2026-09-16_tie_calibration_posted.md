---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-tie-calibration-post
document_type: announcement
record_kind: channel_announcement
project_id: response_preference
scope: project
batch_id: rp_batch_14
version: '1.0'
effective_at: '2026-09-16T14:00:00Z'
last_updated: '2026-09-16T14:00:00Z'
status: tl_approved
decision_status: tl_approved
execution_status: posted
outcome_status: not_observed
authority:
  actor_id: U001
  role: TEAM_LEAD
  provenance: synthetic_slack_archive
source:
  system: slack
  channel_id: C_RP_ANNOUNCEMENTS
  thread_id: '1789567200.700002'
  message_id: '1789567200.700002'
  author_id: U001
  message_text_sha256: 859437b3abd88e4e4cbf785b440744d09ae92fa67657c4982369f32ac0bf29c9
  evidence_location: embedded:source-snapshot
  embedded_snapshot_sha256: 4533337888715a2766b06176a5c25fcccd4103c191027427ecaa63ab7c1e8b95
synthetic: true
tags:
- ties
- calibration
- announcement
source_refs:
- document_id: rp-tie-calibration-approval
  version: '1.0'
event_series_id: RP-B14-TIE-CALIBRATION
---


# Tie calibration announcement

## Posted channel message

Preference batch 14 calibration: choose a tie when neither answer offers a meaningful quality advantage. If choosing A or B, identify the user-facing benefit rather than saying only that it sounds nicer. Keep material factual or instruction-following defects separate. Bring both rationales for disputed pairs to the eight-pair calibration review. This message clarifies the existing criterion; it does not create a new numerical threshold.

## Posting record

Posted by Alex (U001, TEAM_LEAD) to response-preference-announcements on September 16, 2026, 10:00 America/New_York. The exact decimal Slack timestamp is 1789567200.700002. The archived payload contains the complete message; no reactions or replies are asserted.

Posting establishes that this message was communicated. It does not prove that every participant read it or that the underlying issue was resolved.


## Referenced records

- [rp-tie-calibration-approval v1.0](2026-09-16_tie_calibration_approved.md)

## Source snapshot

```json
{
  "channel": {
    "id": "C_RP_ANNOUNCEMENTS",
    "name": "response-preference-announcements",
    "project_id": "response_preference",
    "batch_id": "rp_batch_14",
    "channel_type": "ANNOUNCEMENTS"
  },
  "message": {
    "ts": "1789567200.700002",
    "user": "U001",
    "text": "Preference batch 14 calibration: choose a tie when neither answer offers a meaningful quality advantage. If choosing A or B, identify the user-facing benefit rather than saying only that it sounds nicer. Keep material factual or instruction-following defects separate. Bring both rationales for disputed pairs to the eight-pair calibration review. This message clarifies the existing criterion; it does not create a new numerical threshold.",
    "source": "USER",
    "reactions": [],
    "reply_count": 0
  }
}
```
