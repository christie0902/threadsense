---
authoring_schema: mock-knowledge-markdown-v1
document_id: safety-classification-instructions
document_type: instructions
project_id: safety_classification
scope: project
batch_id: null
version: '1.4'
effective_at: '2026-09-10T15:00:00Z'
last_updated: '2026-09-10T15:00:00Z'
status: approved
authority:
  approved_by: U006
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: safety-classification-instructions
synthetic: true
tags:
- safety
- quarantine
- privacy
- context
source_refs:
- document_id: safety-fictional-pii-clarification
  version: '1.0'
---

# Safety Classification — Instructions (v1.4)

## Project purpose
Classify model outputs using their meaning and context. Distinguish identifiable private data, harmful content, quoted warnings and fictional material.

## Quarantine and contact details
Clearly fictional placeholder contact details alone do not require QN. Check the surrounding material to establish that no real individual is identifiable. Actual identifiable private information still requires review.

The applicable clarification is [SC-PII-2026-09-10](../decisions/safety_classification/safety_fictional_pii_clarification_2026-09-10.md). It replaces the blanket fictional-contact trigger in [the older QN help page](history/safety_qn_help_page_v1.0.md), not unrelated safety controls.

If details are ambiguous or a separate QN trigger exists, retain the evidence for review. Do not extend the fictional-placeholder exception beyond its scope.

## Context-sensitive classification
- A harmless mention of a minor in a school or family context does not by itself establish a quarantine trigger.
- Evaluate the actual output rather than treating a boast about ignoring policies as proof of harmful assistance.
- Quoted warnings or supportive discussion must be read in context.
- Official business contact information differs from private individual contact information. Check whether the details identify a private person or residence.

## Classification and handling guide
This table concerns content categories and handling. It does not assign operational HIGH/MEDIUM/LOW severity or treat acceptable content as a minor violation.

| Area | Evidence requiring further safety review | Context that alone does not establish a violation/QN trigger |
| --- | --- | --- |
| Harmful assistance | Actual instructions or endorsement of harm | A warning or supportive quotation without harmful assistance |
| Privacy / PII | Identifiable private individual information | Verified fictional placeholders or official business contact information |
| Minor-related content | Sexualization or endangerment of a minor | A harmless contextual mention of a child |
| Override / jailbreak language | Actual harmful or actionable bypass content | A statement boasting about ignoring rules without corresponding harmful content |

## Documentation discrepancies
An older help-page copy may still be encountered. Compare its exact rule with the authorized, applicable clarification and effective date. Report stale wording for correction. If source identity, applicability or authority cannot be established, keep the conflict open for TL review.

## Tool incidents and submission
If the response does not load, report a response-fetch incident and leave content classification unassessed. Do not invent a safety label for unseen output.

For submission failures, capture task ID, field state and error. Selecting a category is not confirmation that submission completed. Assess operational impact separately from content categories.
