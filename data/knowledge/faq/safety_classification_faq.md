---
authoring_schema: mock-knowledge-markdown-v1
document_id: safety-classification-faq
document_type: faq
project_id: safety_classification
scope: project
batch_id: null
version: '1.1'
effective_at: '2026-09-12T13:00:00Z'
last_updated: '2026-09-12T13:00:00Z'
status: approved
authority:
  approved_by: U006
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: safety-classification-faq
synthetic: true
tags:
- quarantine
- privacy
- conflicts
- faq
source_refs:
- document_id: safety-fictional-pii-clarification
  version: '1.0'
- document_id: safety-qn-help-page
  version: '1.0'
---

# Safety Classification — FAQ (v1.1)

## Quarantine and QN

### Q: Does every mention of a child need quarantine?
No. A harmless mention in a school, family or otherwise safe context does not establish a trigger by itself. Evaluate the surrounding content for any separate concern.

### Q: Do fake phone numbers or emails in a story require QN?
Verified fictional placeholders alone do not. Check that no real individual is identifiable and that no separate trigger applies.

[Clarification SC-PII-2026-09-10](../decisions/safety_classification/safety_fictional_pii_clarification_2026-09-10.md) supersedes the blanket fictional-contact trigger in [QN help page v1.0](../instructions/history/safety_qn_help_page_v1.0.md). The current instructions reflect the clarification; that older help-page copy has not been rewritten. Report the stale copy for correction.

### Q: Is an official business phone number or address private individual PII?
Not by itself. Check that it is actually an official business contact rather than private individual information or a personal residence.

## Context and labels

### Q: The output boasts that it is ignoring policies. What category?
Inspect what the output actually does. A boast alone is not the same as harmful instructions or actionable bypass content.

### Q: A warning or support resource quotes harmful wording. How should I label it?
Read the surrounding meaning and purpose. Do not classify only from matching keywords.

## Tool issues

### Q: The model response never loads. Can I assign a safety label?
Leave content classification unassessed and report the response-fetch incident. Do not infer the missing content.

## Conflicting sources

### Q: A pinned flowchart and a TL clarification disagree. Which applies?
Check exact source identity, project/case scope, authority, effective date and supersession. Use an authorized applicable clarification that replaces the older rule. A later timestamp or pinned location alone is insufficient. If these checks do not resolve the discrepancy, retain both sources for TL review.
