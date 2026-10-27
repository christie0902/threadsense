# Agent 2 closure milestone — final v6 dataset

**Decision: ready with review for downstream integration through the mandatory
effective loader.** Processing is complete: 90 groups, 200 unique full identities,
516 original messages, all 49 inherited Agent 1 obligations, and zero unprocessed
groups. There are **88 CONSOLIDATED and 2 FAILED** records. Failed social-only
groups retain explicit placeholders, sources, raw drafts and actionable diagnostics.
This is processing coverage, not an accuracy percentage or semantic certification.

No producer model, prompt, schema, glossary, rubric, validator, grouping, Agent 1
candidate or source changed in this milestone. No Agent 3, retrieval, research
workflow or dashboard implementation was added. New code is an offline assembler
and six focused assembly regression tests.

## Responsibility and architecture

Agent 2 consolidates factual topics, retains relevant differences and original
questions, preserves scoped guidance and actual endorsements, and provides
preliminary operational severity. It does not decide global policy precedence,
research answers, actionability or interventions. Its severity remains provisional.

The existing local grouping supplies 90 candidates from the finalized Agent 1 v3
export. One independent request per group produces one source inventory plus cited
synthesis and impact observations. Strict transport/schema checks and deterministic
membership, evidence, answer-link and severity checks produce the export. Python
supplies exact quotations, full identities, author roles, eligible reaction users
and targets, counts, display projections and severity metadata. Valid evidence IDs
alone cannot prove semantic support.

The mandatory effective loader adds separately registered, exact source/raw/result
bound reviews. It retains automated outcomes and marks disputed claims provisional.
The existing `agent3-research-input-v1` contract remains unchanged: every exported
question, including ANSWERED, keeps its raw resolution judgment, uncalibrated
confidence, uncertainty note, linked answers, guidance, original sources and flags.
Failed groups retain sources even when no valid question inventory exists.

## Accepted configuration and execution

| Setting | Frozen value |
| --- | --- |
| Requested and returned snapshot | `openai/gpt-5.4-2026-03-05` / `gpt-5.4-2026-03-05` |
| Reasoning / output cap | `low`; `max_completion_tokens=8192`, shared with reasoning |
| Sampling | `temperature`, `top_p`, `logprobs` absent |
| Prompt / response contract | `agent2-inventory-v6`; strict schema 6 |
| Rubric / display adapter | `provisional-operational-severity-v2`; `inventory-to-display-v3` |
| Call bound | One attempt/group; zero retries, repairs, fallback or verifier calls |
| Acceptance | [Provisional acceptance v1](agent2-provisional-acceptance-v1.md): plausible interpretations may proceed with explicit confidence, uncertainty and evidence; unsupported decisions remain disputed |

The [freeze](../data/experiments/agent2_final_v6/freeze.json) and its receipt preserve
exact requests, source/configuration/code hashes and the pre-spend estimate. The
eight prior v6 groups matched their exact input/request/export and producer code.
Only the review-registry fingerprint had advanced after their completed review;
that provenance difference was documented, not bypassed. Original source-run
manifests remain unchanged. No baseline requests were repeated.

| Accounting | Reused v6 | New run | Combined |
| --- | ---: | ---: | ---: |
| Groups / full identities | 8 / 23 | 82 / 177 | 90 / 200 |
| Original messages | 61 | 455 | 516 |
| Inherited obligations | 5 | 44 | 49 |
| CONSOLIDATED / FAILED | 8 / 0 | 80 / 2 | 88 / 2 |
| Original attempts / saved responses | 8 / 8 | 82 / 82 | 90 / 90 |
| INTERRUPTED / unknown completion / unprocessed | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

All saved responses completed with HTTP 200 and `finish_reason=stop`; neither
failure is a provider rejection, refusal or truncation. The two failures are
`cluster_be4e3bac742eccb3` and `cluster_c9bdba359e6e7cd2`: accurately described
social greetings received context-only inventories, which the frozen requirement
for substantive representation of every member rejects. Their exported severity
is **UNKNOWN/unassessed**, not N/A. This conservative contract limitation is
contained by the explicit failed-record route. No validator was weakened or draft
edited to force acceptance.

## Mechanical and practical source audit

The [mechanical audit](../data/experiments/agent2_final_v6/final_mechanical_audit.json)
checks every record against canonical membership, original message coverage,
source files, exact requests, raw HTTP envelopes, replayed exports, lineage and
queues. It checks 4,544 projected evidence-reference occurrences, including actual
reaction targets, and confirms that copied record artifacts match original bytes.

There are **54 automated and 54 effective review groups**. Counts need not rise
when a new finding affects an already flagged group. Obligations remain separate:
49 inherited member obligations, 19 Agent 2 validation/coverage obligations,
10 HIGH review obligations and 10 assisted-content findings across nine groups.
These categories overlap and are not unique-record counts.

The 88 consolidated groups contain 94 topics: 79 UNKNOWN, 10 HIGH, 2 MEDIUM,
2 LOW and 1 N/A. All HIGH topics remain nonblocking and reviewable. One LOW
assessment is explicitly disputed below; the automated level is preserved.
There are 122 exported questions: 73 OPEN, 21 PARTIAL and 28 ANSWERED; 100 have
notes, including 16 ANSWERED questions. Twenty-two ANSWERED questions require
research/review in the effective view. Consume **all records**, not only a queue:
an unresolved question can exist without a group-level review obligation, and a
flagged announcement can require review without an ordinary question.

This was a **Codex-assisted source review**, not human approval, independent ground
truth or an unbiased accuracy benchmark. The pre-run rule selected all HIGH
groups, all ANSWERED judgments at confidence >=0.90 without a note, historical
failure cases and a seeded two-per-project sample plus source-based additions.
Both failures were also reviewed. Thresholds selected audit work only; no runtime
threshold changed and no review labels entered requests.

**32 new groups / 80 identities / 211 messages received new semantic review.**
The eight reused groups retain their original exact-candidate reviews covering
23 identities/61 messages. Thus the final dataset has reviewed candidates in
40 groups/103 identities/272 messages; **50 groups/97 identities/244 messages were
checked mechanically, not newly certified semantically**. The
[review table](../data/experiments/agent2_final_v6/source_review_table.md) identifies
every reviewed group and its provenance; the
[new supplement](../data/experiments/agent2_final_v6/review_supplement.json) includes
exact affected field values, source quotations, roles/reactions and hash bindings.

| New finding | Group | Consequence retained for review |
| --- | --- | --- |
| Invented preference decision | `cluster_fff2a52a6010f8e7` | Summary claims choosing A; source only says B adds nothing substantive. No actual A-choice is established. |
| Understated work blockage | `cluster_dc219b33a3be1a2e` | LOW conflicts with explicit inability to evaluate/compare affected tasks. Scoped HIGH is a stronger reading; original LOW remains visible with dispute. |
| Diagnostic alternative promoted to observation | `cluster_4a8809dfc56fd3f9` | Same-task recurrence was asked about, not reported. Other evidence independently supports submission blockage/HIGH. |
| Overexclusive, weakened-scope synthesis | `cluster_ab4fa9e9a46e0a07` | Another thread also gives guidance; dropping “as a content decision” risks a blanket Quarantine prohibition. |
| Tentative context labeled DIRECT answer | `cluster_0df9e215dec4e314` | A borrowed-word comparison is not an established handling decision; an automatic unlinked-answer warning already surfaced it. |
| Missing penalty-scope note | `cluster_2d814c8e21470de9` | Dead-link guidance is useful but does not decide every citation penalty; confident ANSWERED must not imply a blanket no-penalty rule. |
| Minor exclusive wording | `cluster_6b59d13144282285` | “Only replies” omits a factual report, which still survives in inventory. |
| Minor incomplete citation | `cluster_11ce3cfce9431006` | Genuine task ID is in E002, not the sentence's sole citation E001. |

Two earlier correspondence findings remain attached to unchanged reused
`cluster_6042d88a3d171626`: a missing field-allocation scope note and an overly
exclusive reply description. All ten findings apply successfully; zero stale
bindings. Most specific errors were discovered by this review, not by model
confidence or automatic self-checks. Existing provisional flags are containment,
not evidence that the system identified each semantic error itself.

Reviewed successes include retained Alignment supersession questions and dates/
versions guidance, Audio question-specific Quarantine uncertainty, actual scoped
TL endorsements, announcements without invented questions, a tentative avatar
answer with N/A impact, and legitimate complete answers that remain ANSWERED.
Multilingual cases include regional Vietnamese and Korean/Spanish/Japanese issues,
mostly discussed in English; this is not broad multilingual language validation.

## What the experiments taught us

| Historical stage | Lesson retained in the final design |
| --- | --- |
| Early v3 / inventory v4 | Repeated prose and cross-thread links could fail validation or lose questions/guidance; one inventory and Python-derived projections reduce duplication. |
| [v5 A/B review](../data/experiments/agent2_comparison_v5_review/milestone_report.json) | Actual completed responses made the comparison valid: A had six application failures, B five accepted/one rejected. Acceptance did not establish semantic accuracy; B retained severity/scope concerns. |
| v5.1 / v5.2 focused corrections | Single-level impact evidence and full question-scope instructions helped, but structural checks cannot decide entailment. |
| [v5.2 low reasoning](../data/experiments/agent2_reasoning_low_v5_2/milestone_report.md) | Alignment improved while Audio scope concerns remained; temperature omission and historical comparison prevent a clean reasoning-only causal claim. |
| [v5.3 contrastive diagnostic](../data/experiments/agent2_contrastive_v5_3/milestone_report.md) | Contrastive guidance did not eliminate scope ambiguity; repeatedly tuned cases are not a general accuracy benchmark. |
| [v6 uncertainty handoff](../data/experiments/agent2_uncertainty_v6/milestone_report.md) | Eight accepted groups demonstrated confidence/notes and complete exported-question handoffs under the new provisional policy. Confidence still missed specific errors. |
| Final v6 closure | Same producer handled all remaining inputs once. Failed placeholders and evidence-bound review contain known limitations without retries or another tuning loop. |

Historical configurations and HOLD decisions remain historical; they are not
rewritten as outcomes of this final configuration. The exact former long guide is
retained in [the historical guide archive](agent2-run-guide-history-through-v6.md).

## Tokens, estimated cost and latency

The pre-spend cap estimate was **$11.44313**, using estimated input plus all
82 x 8,192 possible output/reasoning tokens, with no cache discount assumed.
Usage-based estimates use $2.50/M input, $0.25/M cached input and $15/M output,
checked against [OpenAI GPT-5.4 pricing](https://developers.openai.com/api/docs/models/gpt-5.4)
on 2026-10-25. These are token estimates, not an invoice; cached tokens are a
subset of input and reasoning tokens are a subset of output.

| Usage | Eight reused | 82 new | Combined original requests |
| --- | ---: | ---: | ---: |
| Input / cached input | 40,925 / 19,712 | 390,225 / 225,280 | 431,150 / 244,992 |
| Output including reasoning / reasoning | 11,345 / 5,557 | 86,281 / 39,466 | 97,626 / 45,023 |
| Estimated USD | 0.228136 | 1.762898 | 1.991033 |
| Request latency sum / mean, seconds | 130.279 / 16.285 | 1,029.192 / 12.551 | 1,159.471 / 12.883 |

New request latency ranged 3.439–32.643 seconds. This measures request latency,
not total milestone wall time. No new calls occurred during assembly/review/export.

## Handoff, commands, cleanup and validation

- Authoritative [dataset manifest](../data/processed/agent2_final_v6/manifest.json):
  per-group reused/new provenance and exact original source manifests/file hashes.
- Immutable [canonical records](../data/processed/agent2_final_v6/consolidations.json)
  and original record folders; [effective view](../data/processed/agent2_final_v6/effective_output.json)
  supplies the maintained records, effective review queue, member queue and research handoffs.
- [Combined review supplement](../data/processed/agent2_final_v6/combined_review_supplement.json)
  retains original review provenance; [registry](agent2-review-supplements.json)
  keeps all historical supplements plus the new and combined entries.
- [Operational guide](agent2-offline-integration.md): current inspection/export
  commands, completed execution record and the unchanged downstream contract.
- [Cleanup receipt](../data/experiments/agent2_final_v6/cleanup_receipt.json):
  11 inspected pytest trees removed, 95,354 reconstructible files and 2,792,778,228
  bytes (2.79 GB), with no deletion failures. The dependency scan covered 8,840
  text files including code, tests, configuration, manifests, registries and
  historical helper references. Unique XML receipts remain outside deleted trees.
  Source data, environments, historical preparations/utilities/decoders and all
  audit evidence were retained where referenced, unique or uncertain.

After cleanup, the full offline suite passed: **530 passed, zero failures/errors/
skips**, 162 warnings, 278.08 seconds. The exact command was:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-closure-full --junitxml data/experiments/agent2_final_v6/full-tests.xml
```

The [JUnit receipt](../data/experiments/agent2_final_v6/full-tests.xml) includes all
six new assembly regressions. Preflight separately passed 24 focused tests and
reused the completed 524-test producer validation because producer code was
unchanged. Final mechanical audit, Slack fixture validation, catalog validation,
the all-input dry run and the zero-call effective exporter passed after cleanup.
The [closure checks](../data/experiments/agent2_final_v6/closure_checks.json) record
documentation and loader checks; the
[preservation receipt](../data/experiments/agent2_final_v6/preservation_receipt.json)
distinguishes intentional documentation/registry changes and cache removals from
unchanged historical data and evidence.

Remaining limitations are the two context-only failures, source-review findings,
uncalibrated confidence, possible unrecognized implicit questions and the 50
groups without semantic review. No uncontained severe defect was found in the
reviewed scope after applicable disputes were exposed. Consumers must retain
failed records, flags, exact lineage, original scopes and all question judgments;
they must not treat “CONSOLIDATED,” ANSWERED, low severity or absence of an assisted
finding as independent factual approval. HIGH and group-only obligations remain
accessible even without a recommendation or question. Agent 2 is closed under
that ready-with-review contract; no further live run is authorized here.
