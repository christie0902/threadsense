---
authoring_schema: mock-knowledge-markdown-v1
document_id: multilingual-eval-instructions
document_type: instructions
project_id: multilingual_eval
scope: project
batch_id: null
version: '1.2'
effective_at: '2026-09-10T13:00:00Z'
last_updated: '2026-09-10T13:00:00Z'
status: approved
authority:
  approved_by: U001
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: multilingual-eval-instructions
synthetic: true
tags:
- language
- register
- locale
- naturalness
---

# Multilingual Evaluation — Instructions (v1.2)

## Project purpose
Evaluate language adherence, register consistency, naturalness and regional appropriateness against the intended audience. Distinguish linguistic defects from tool rendering failures.

## Language adherence
For a monolingual requirement, an unexplained paragraph in another language counts against adherence. Check the requested output language and context first. Ordinary loanwords are not automatically code-switching errors; a user mixing languages does not itself define the required output language.

## Register and honorifics
Check the addressee, discourse context, quotation and intended register. A speaker change or quotation can justify a shift. Provide exact sentence endings and route locale-specific scoring to the appropriate language QA. An apparent shift is not an automatic major penalty.

## Regional variation and naturalness
Assess wording against the specified locale or audience. Natural Southern Vietnamese vocabulary is not an error merely because a Northern reviewer prefers a different word. Reviewer preference or a majority vote alone does not establish a linguistic defect; identify the wording and its effect.

## Content-quality rubric
These grades concern task-quality defects. Language QA must establish context and impact for disputed locale-specific cases.

| Dimension | Major defect | Minor defect | Acceptable / no automatic penalty |
| --- | --- | --- | --- |
| Language adherence | Substantial unrequested language mismatch violating the requirement | Limited genuine mismatch with a stated requirement | Ordinary loanwords or switching permitted by the task |
| Register / honorifics | Unmotivated, materially disruptive inconsistency confirmed in context | Localized inappropriate shift with limited effect | Natural variation, quotation or a justified addressee change |
| Regional appropriateness | Clear material mismatch with the specified audience | Localized genuine mismatch with limited effect | Regional vocabulary natural for the intended audience |
| Naturalness | Demonstrable phrasing problems that materially impair meaning or appropriate use | Identifiable localized awkwardness | A reviewer preference without an identifiable error |

## Specialist routing
Use the language being evaluated to select appropriate expertise. Spanish expertise does not establish Korean or Japanese expertise. If the prompt does not establish a required locale, seek clarification rather than inventing one.

## Tool incidents and submission
Boxes, missing diacritics or broken characters in LT are tool-rendering incidents until the source text is checked. Compare outside the tool where possible. If unavailable, record the limitation rather than asserting that the model produced corrupt text.

Capture task IDs for rendering or submission failures. Treat tool impact under the operational incident rubric, separately from language-quality grades. A saved rating is not proof of a completed submission.
