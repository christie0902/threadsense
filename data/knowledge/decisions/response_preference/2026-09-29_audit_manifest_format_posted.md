---
authoring_schema: mock-knowledge-markdown-v1
document_id: rp-audit-manifest-post
document_type: announcement
record_kind: channel_announcement
project_id: response_preference
scope: project
batch_id: rp_batch_15
version: '1.0'
effective_at: '2026-09-29T14:00:00Z'
last_updated: '2026-09-29T14:00:00Z'
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
  thread_id: '1790690400.810002'
  message_id: '1790690400.810002'
  author_id: U001
  message_text_sha256: e5e2ca3c5c3488d90cf96cbc059932fb35c43f2dd8dc2e77ffb68fb8077df1a6
  evidence_location: embedded:source-snapshot
  embedded_snapshot_sha256: b10996304da9e41c55c60da05fe81454de3212cb3a4fa8718881755ee155ab66
synthetic: true
tags:
- json
- required-format
- audit-export
- file-naming
source_refs:
- document_id: rp-audit-manifest-approval
  version: '1.0'
event_series_id: RP15-AUDIT-MANIFEST
applicability: RP batch 15 QA weekly audit manifests only; effective for exports prepared
  from September 29.
---

# Weekly audit manifest convention communicated

## Posted channel message

For RP batch 15 weekly QA audit exports prepared from today, the manifest must be JSON rather than a prose list. Use the fields batch_id, audit_date, and task_ids, and name the file rp15_audit_YYYY-MM-DD.json. This is an administrative handoff format for QA files. It does not change how we compare the model responses in a task or settle any accuracy-versus-format tradeoff in those responses.

## Posting record

Posted by Alex (U001, TEAM_LEAD) to response-preference-announcements on 2026-09-29 10:00 America/New_York. The archived message timestamp is 1790690400.810002. No reactions or replies are recorded.

## Execution and outcome

Alex posted the approved convention. No sample of converted manifests or downstream import results is recorded yet. The announced format governs QA administrative files; response evaluation still follows the prompt and applicable scoring guidance.

## Source snapshot

```json
{
  "channel": {
    "id": "C_RP_ANNOUNCEMENTS",
    "name": "response-preference-announcements",
    "project_id": "response_preference",
    "batch_id": "rp_batch_15",
    "channel_type": "ANNOUNCEMENTS"
  },
  "message": {
    "ts": "1790690400.810002",
    "user": "U001",
    "text": "For RP batch 15 weekly QA audit exports prepared from today, the manifest must be JSON rather than a prose list. Use the fields batch_id, audit_date, and task_ids, and name the file rp15_audit_YYYY-MM-DD.json. This is an administrative handoff format for QA files. It does not change how we compare the model responses in a task or settle any accuracy-versus-format tradeoff in those responses.",
    "source": "USER",
    "reactions": [],
    "reply_count": 0
  }
}
```

## Referenced records

- [rp-audit-manifest-approval v1.0](2026-09-25_audit_manifest_format_approved.md)
