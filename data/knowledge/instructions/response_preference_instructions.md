---
authoring_schema: mock-knowledge-markdown-v1
document_id: response-preference-instructions
document_type: instructions
project_id: response_preference
scope: project
batch_id: null
version: '1.1'
effective_at: '2026-08-30T13:00:00Z'
last_updated: '2026-08-30T13:00:00Z'
status: approved
authority:
  approved_by: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: response-preference-instructions
synthetic: true
tags:
- preference
- factuality
- format
- citations
---

# Response Preference — Instructions (v1.1)

## Project purpose
Compare two responses against the user's prompt. Record meaningful differences in factual accuracy, instruction adherence, citation support and usefulness.

## Ties
Choose a tie when neither response has a meaningful quality advantage. Cosmetic phrasing alone does not justify a preference. Explain the user-facing benefit when selecting a response on a small difference.

## Factual errors and citations
- A factual error is major when it changes the central conclusion or the answer a user would act on.
- A nonessential background error with no effect on that conclusion is minor.
- A broken link is an access/verification failure, not proof that the underlying factual claim is false.
- Distinguish an existing source that does not support the claim from an invented reference.

## Instruction adherence versus accuracy
Score these dimensions separately. An explicit required output structure, such as JSON, is not optional.

This guidance does not define a universal preference ordering for a response that is stronger on accuracy but weaker on a required format. When the applicable rules and actual pair do not settle the comparison, provide the exact prompt, both responses and their separate defects for a TL decision. Do not assume facts about the other response.

## Content-quality rubric
Major/minor describe task-quality defects and do not determine operational incident severity.

| Dimension | Major defect | Minor defect | Acceptable / no automatic penalty |
| --- | --- | --- | --- |
| Factual accuracy | Error changes the central conclusion or actionable answer | Nonessential background error without that effect | Accurate paraphrase or an immaterial stylistic difference |
| Instruction adherence | Explicit required format/structure is missing | Limited violation of an actual secondary requirement | A stylistic choice that violates no requirement |
| Citation support | Fabricated reference or materially unsupported attribution | A limited citation-detail error where the source and support remain identifiable | A valid source that supports the claim |
| Preference | Identify a meaningful benefit; grade underlying defects separately | Do not manufacture a defect to break a tie | No meaningful quality difference supports a tie |

An inaccessible link needs a verification note; lack of access alone does not establish the error grade of the claim.

## Calibration
For comparable pairs receiving different judgments, retain both rationales and the relevant evidence. A scoped answer about one pair does not automatically become a new universal preference rule.

## Tool incidents and submission
If response panes never load, record a fetch incident and do not infer response quality. If Submit fails, capture the task ID, required-field state, error and exact button behavior. A selected label is not a completed submission until LT confirms it. Assess tool impact separately from the content rubric.
