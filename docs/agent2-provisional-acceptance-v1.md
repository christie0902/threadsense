# Agent 2 provisional acceptance policy v1

Effective 2026-10-25, by the user's updated decision. Historical assisted findings
and HOLD decisions remain unchanged as evidence of their original acceptance policy.

Agent 2 may select a plausible, source-supported interpretation with appropriately
lower confidence and specific uncertainty for downstream research. Ordinary ambiguity,
inherited disputes and expected HIGH-review routing do not automatically fail a run.
Readiness depends on useful provisional analysis, preservation of evidence and review
obligations, and control of consequential errors. Unsupported decisions, false authority,
lost questions, invented impact and missing review routing remain serious problems.
Low confidence supplies no evidence and high confidence clears no dispute.

Response schema 6 adds exactly two required nullable fields to QuestionState:
`resolution_confidence` (0–1) and `uncertainty_note` (text plus evidence IDs from the
same member conversation). The existing status and answer links retain the chosen
resolution. Numeric confidence is an **uncalibrated model self-assessment of that
judgment**, independent of operational severity and Agent 1 reliability. Null means
unassessed, including historical responses. Scores are never inferred from flag counts.
Production parsing requires the new fields; saved v5 replay requires explicit
`response_schema_version=5` and does not upgrade or repair saved responses.

Prompt `agent2-inventory-v6` adds the uncertainty instructions to the existing scope
contract. The snapshot, low reasoning, omitted sampling parameters, 8192-token limit,
severity rubric and existing source inventory checks are unchanged. This is a contract
and handoff validation, not an isolated model or prompt-quality comparison.

The mandatory `load_effective_output()` view now includes
`records[].research_handoff`, contract `agent3-research-input-v1`. Consumers must use
this view and check `review_binding_status`, including stale/unapplied findings.
They must not consume `open_questions` alone. The research handoff exposes:

- Every exported QUESTION, including ANSWERED, its original exact message, raw
  chosen resolution, confidence and uncertainty note, linked answer items and
  same-conversation guidance with source identities and actual reactions.
- Effective dispute/reliability status and research reasons alongside the raw
  judgment; group-wide dispute routing does not assert that every question is wrong.
- All member records and original Slack threads, candidate/source hashes, lineage,
  topic inventory, inherited/automatic/HIGH/assisted obligations and processing status.
- Failed groups with their sources and obligations even when no valid question
  inventory exists. No automatic inference or repair of missing questions occurs.

The effective view is a derived input contract, not an Agent 3 implementation.
An exported complete inventory is not a guarantee that the model recognized every
implicit source question. Original messages remain available to inspect that risk.
Agent 3 must preserve uncertainties and obligations, distinguish reported resolution
from reliability, and record any researched conclusion separately with evidence.

Source reviews distinguish supported interpretations, plausible interpretations with
useful uncertainty, minor errors and consequential errors. Every uncertainty/error
must state whether the model or automatic handoff surfaced it before assisted review
or whether review discovered it afterward. Broad provisional routing alone is not
evidence that the model detected a particular semantic mistake. Reviews are Codex-assisted,
not human approval, independent ground truth or an unbiased accuracy benchmark.
