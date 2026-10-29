---
authoring_schema: mock-knowledge-markdown-v1
document_id: response-preference-faq
document_type: faq
project_id: response_preference
scope: project
batch_id: null
version: '1.1'
effective_at: '2026-09-05T13:00:00Z'
last_updated: '2026-09-05T13:00:00Z'
status: approved
authority:
  approved_by: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: response-preference-faq
synthetic: true
tags:
- ties
- format
- factuality
- faq
---

# Response Preference — FAQ (v1.1)

## Ties and preferences

### Q: How much improvement is needed to avoid a tie?
The difference must offer a meaningful benefit to the user. Cosmetic phrasing alone usually does not. Explain that benefit; otherwise a tie can be appropriate.

### Q: QA is reversing ties on similar pairs. What should I do?
Share the pairs, relevant prompt constraints and both rationales for calibration. Check whether the cases are actually comparable. An answer to one pair should not be generalized without matching its scope.

## Factual errors

### Q: What counts as a significant factual error?
An error that changes the central conclusion or the answer the user would act on. A nonessential background detail with no effect on the recommendation is minor.

### Q: The source link is dead. Should I penalize the factual claim?
Record that the citation could not be verified. A failed URL alone does not prove the claim is false. Distinguish access failure from an unsupported attribution or fabricated reference.

## Instruction following

### Q: The prompt required JSON, but one response is well-written prose. Which response wins?
The required format is not optional: record its violation separately from factual accuracy. No universal tie-break rule is established for competing accuracy and instruction-following defects. If the actual pair and applicable guidance do not settle the preference, provide the prompt and both responses for TL confirmation.

### Q: Can accuracy outweigh ignoring a requested output structure?
Score the dimensions separately and identify whether the requested structure was mandatory. Do not infer a general priority rule from one example or decide without the other response's evidence.
