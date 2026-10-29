---
authoring_schema: mock-knowledge-markdown-v1
document_id: multi-locale-announcement
document_type: announcement
record_kind: channel_announcement
project_id: multilingual_eval
scope: project
batch_id: multi_batch_11
version: '1.0'
effective_at: '2026-09-22T13:00:00Z'
last_updated: '2026-09-22T13:00:00Z'
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
  channel_id: C_MULTI_ANNOUNCEMENTS
  thread_id: '1790082000.700003'
  message_id: '1790082000.700003'
  author_id: U001
  message_text_sha256: ef4c5bb46d3d3efef78e3d03fe51d58d44108998b0b4dcbd17e7f4963a4bbe6c
  evidence_location: embedded:source-snapshot
  embedded_snapshot_sha256: 37de8452ca473de1e15dc71e65b2d300393ceb09f8f96e88ef53a621d3a934e9
synthetic: true
tags:
- locale
- vietnamese
- language-qa
- announcement
source_refs:
- document_id: multilingual-eval-instructions
  version: '1.2'
- document_id: multilingual-eval-faq
  version: '1.1'
event_series_id: multi-locale-announcement
---


# Locale and register routing announcement

## Posted channel message

Multilingual batch 11: confirm the requested audience or locale before penalizing regional wording. Natural Southern Vietnamese vocabulary is not an error solely because a reviewer prefers a Northern term. Provide the exact phrase and prompt context. Send Korean cases to Hana, Japanese cases to Yuki, Vietnamese cases to Linh and Spanish cases to Leo. For register shifts, include the addressee and any quotation; an apparent shift is not an automatic major penalty.

## Posting record

Posted by Alex (U001, TEAM_LEAD) to multilingual-eval-announcements on September 22, 2026, 09:00 America/New_York. The exact decimal Slack timestamp is 1790082000.700003. The archived payload contains the complete message; no reactions or replies are asserted.

Posting establishes that this message was communicated. It does not prove that every participant read it or that the underlying issue was resolved.


## Referenced records

- [multilingual-eval-instructions v1.2](../../instructions/multilingual_eval_instructions.md)
- [multilingual-eval-faq v1.1](../../faq/multilingual_eval_faq.md)

## Source snapshot

```json
{
  "channel": {
    "id": "C_MULTI_ANNOUNCEMENTS",
    "name": "multilingual-eval-announcements",
    "project_id": "multilingual_eval",
    "batch_id": "multi_batch_11",
    "channel_type": "ANNOUNCEMENTS"
  },
  "message": {
    "ts": "1790082000.700003",
    "user": "U001",
    "text": "Multilingual batch 11: confirm the requested audience or locale before penalizing regional wording. Natural Southern Vietnamese vocabulary is not an error solely because a reviewer prefers a Northern term. Provide the exact phrase and prompt context. Send Korean cases to Hana, Japanese cases to Yuki, Vietnamese cases to Linh and Spanish cases to Leo. For register shifts, include the addressee and any quotation; an apparent shift is not an automatic major penalty.",
    "source": "USER",
    "reactions": [],
    "reply_count": 0
  }
}
```
