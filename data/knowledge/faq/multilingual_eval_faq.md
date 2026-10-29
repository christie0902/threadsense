---
authoring_schema: mock-knowledge-markdown-v1
document_id: multilingual-eval-faq
document_type: faq
project_id: multilingual_eval
scope: project
batch_id: null
version: '1.1'
effective_at: '2026-09-18T13:00:00Z'
last_updated: '2026-09-18T13:00:00Z'
status: approved
authority:
  approved_by: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: multilingual-eval-faq
synthetic: true
tags:
- loanwords
- register
- regional-variation
- faq
---

# Multilingual Evaluation — FAQ (v1.1)

## Language adherence

### Q: Does a single English word in a Korean or Japanese answer count as code-switching?
Not automatically. Ordinary loanwords are acceptable. Assess the word in context and against the required output language; an unrequested full paragraph in another language is a different issue.

### Q: The user code-switched. Should the response mirror it?
Check the explicit output-language requirement and context. User code-switching alone does not settle the score.

## Register and honorifics

### Q: Who scores Korean or Japanese register shifts?
Route the case to appropriate Korean or Japanese language QA with exact sentence endings and surrounding context. Check quotations and addressee changes. The task-quality grade depends on demonstrated impact; do not assign a major penalty from the presence of a shift alone.

### Q: Spanish tú versus usted inconsistency — major or minor?
Ask Spanish QA to check addressee, intended formality and discourse context. An unjustified shift can be an error, but its grade needs a case-specific rationale.

## Regional variation

### Q: Are Vietnamese regional words always penalized?
No. Confirm the intended locale or audience. Vocabulary natural for that audience is acceptable even when another reviewer would use a different regional term. If the required locale is unclear, obtain that context before deciding.

## Tool issues

### Q: Characters or tone marks appear as boxes or become unreadable in LT.
Report a tool-rendering incident and check the text outside LT where possible. Until that comparison is available, do not claim the underlying response itself has corrupted characters.
