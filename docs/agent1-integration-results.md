# Agent 1 integration completion report — 2026-10-22

> Historical live results, preserved as observed. See the [current nonblocking
> handoff report](agent1-nonblocking-handoff.md) for effective review statuses
> and current commands. Its workflow replaces the blocking gate and separate
> content-review lookup described below. The false acceptance is still a known
> semantic failure. Version 3 cannot resume the version 2 cache as current work.

**Implementation and offline validation are complete. The live pilot failed the
readiness gate. The paid 200-thread run was not executed and must not proceed
on the strength of these results.** No prompt tuning or further paid cycle was
performed after discovering the failure.

## Changes and call flow

The active version 2 workflow is: one source-only analysis → one batched prose
comparison → deterministic verification → at most one existing Agent 1 revision
→ one fresh batched prose comparison using the same validated source analysis.
An accurate original takes two calls; a revised candidate takes at most four.
Invalid source analysis stops at review. Missing, stale, malformed, uncertain,
or unsupported candidate evidence cannot itself certify a pass.

| File | Change in this milestone |
| --- | --- |
| `src/threadsense/agents/contracts.py` | Added minimal `SourceEvidenceAnalysis` and `ProseComparison` contracts. Combined audit still requires candidate assessments. Interpreter and Agent 2 schemas unchanged. |
| `src/threadsense/agents/decision_evidence_audit.py` | Extracted shared source validation; retained real combined parser/prose validation and historical helper; reject duplicate prose citations and blank source explanations. |
| `src/threadsense/agents/prose_comparison.py` | New source-only and batched prose request builders/parsers. Adapted the successful focused experiment's instructions without labels, prior reasoning, or per-sentence fallbacks. |
| `src/threadsense/agents/verification_requests.py` | New single-POST transport: zero retries, exact request/raw response capture, stop on persistence failure or rejected configuration, reject truncated output. |
| `src/threadsense/agents/interpretation_revision.py` | Existing Agent 1 rules/model receive source analysis and specific findings through the single-attempt transport. |
| `src/threadsense/agents/verification_pipeline.py` | One source analysis reused across two candidate passes; one revision maximum; fresh prose evidence required; source/failure retention and passing-result consistency checks. |
| `src/threadsense/agents/interpretation_verifier.py` | Updated module description. Existing deterministic logic and the user's non-SUPPORTED-to-finding conversion are preserved. |
| `scripts/run_agent1_verification.py` | Version 2 cache/configuration, four-stage limit, request/response checksums, stronger cached-evidence validation, recorded attempt counts, and interrupted-record retention. |
| `tests/test_decision_evidence_audit.py`, `tests/test_verification_pipeline.py` | Migrated injected stages to source analysis plus prose comparison. Kept the eight targeted prose cases using real validators, verifier, and controller. |
| `tests/test_interpretation_revision.py`, `tests/test_agent1_verification_batch.py` | Updated provider mocks and stage artifacts; preserved revision, interruption, cache corruption, and 200-input retention purposes. |
| `tests/test_verification_integration.py` | New real-transport-boundary mocks, request isolation, complete coverage, evidence corruption, source reuse, call caps, persistence/configuration failure checks, and clearly labeled saved-response replay. |
| `README.md`, `docs/agent1-verification.md`, `docs/agent1-integration-readiness.md` | Current workflow, commands, budget, history distinction, cache behavior, and Agent 2 handoff. Historical validation record retained. |
| `docs/agent1-review-sample.json` | Fixed 12-record later review sample: pilot four plus two non-pilot threads per project across all four projects, selected before full-run outcomes. |
| `docs/agent1-pilot-content-review.json`, this report | Separate source-based review, including the known false acceptance; machine verdicts/raw evidence remain unchanged. |

Existing uncommitted work was preserved in a local snapshot before editing.
All **448 pre-existing data/experiment artifacts** and three Agent 2 modules
checked against the initial snapshot remain unchanged. Raw Slack, frozen interpretations, grouping,
evaluation labels, historical pilot responses, and live experiment labels were
not changed. AST comparisons confirm unchanged `ThreadInterpretation`,
`TopicRollup`, and `TopicAnalysis` definitions. No Agent 2 behavior changed.

## Offline validation

Exact final command:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent1-integration-final
```

**257 passed, 0 failed, 0 skipped; 162 dependency warnings; 41.46 seconds.**
The full suite passed before the live pilot. The first sandboxed uv invocation
could not access its existing Windows cache; the final command ran with the
required cache access. `git diff --check` also passed.

Coverage includes the real parser/validator/verifier/controller, source reuse,
fresh revised-candidate checks, missing/duplicate/stale/fabricated assessments,
exact quotes, actual TL reactor and target, substantive answers versus eyes or
diagnostics, uncertainty, interruption, incompatible caches, persistence failure,
configuration rejection, strict call caps, exclusion of expected/evaluation data,
and all 200 original inputs retained exactly once under mocked model failures.

Historical single-unit experiment replay retains **4/4 faithful acceptances,
4/4 incorrect rejections, and 6/8 exact verdict agreement**. Cases `case_02` and
`case_07` still returned CONTRADICTED against expected UNSUPPORTED. The replay
adapts only the envelope/unit ID in memory; saved raw responses and labels are
unchanged. These tests establish compatibility, not new live accuracy.

## One bounded live pilot

The requested models were explicitly pinned for the run; no saved key was
printed or changed:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --thread-id 1790882197.000111 --thread-id 1790909920.000138 --thread-id 1790915374.000127 --thread-id 1790903186.000110 --output-dir data/processed/agent1_verified_pilot_v6
```

The runner processes selected records in frozen-baseline order: 110, 111, 138,
127. Source review discovered the false acceptance on 111 while the process was
advancing through the remaining records. The run was interrupted as soon as that
failure was identified. When the halt took effect, three records had completed
and 127's first prose call was in flight.

**12 request attempts were recorded, with 11 completed HTTP responses.** The
interrupted twelfth attempt has a saved exact request/call marker but no completed
response; its provider-side completion/billing is unknown. There were no retries,
fallbacks, or further paid calls. This remains below the authorized 16-call cap.

After confirming that the process was no longer running, its stale lock was
removed. Offline recovery explicitly disabled both credential access and the
model entry point, then retained the incomplete record as `NEEDS_REVIEW`.
Recovery made zero new calls. All four records now have lineage and terminal
cache records. Machine counts are **VERIFIED 1, CORRECTED 2, NEEDS_REVIEW 1**.
Those counts are not the content-review outcome.

| Thread | Source establishes | Actual retained output | Source review | Attempts / responses |
| --- | --- | --- | --- | --- |
| `1790882197.000111` | Root recalls only a possible old workaround and a recurring problem. Three replies gather diagnostics. QN means Quarantine; no quarantine decision or authoritative answer is supplied. | Revision fixes QN, sets UNRESOLVED, and removes authority. Summary still says “recalling a previous workaround that seems to have failed.” Model labels it CORRECTED. | **FAIL: false acceptance.** The source establishes neither an attempted workaround nor its failure. `summary` requires review despite the machine status. | 4 / 4 |
| `1790909920.000138` | Jordan: “The reference text has a sentence missing from the recording.” Hana supplies correspondence-error guidance; actual TL U006 endorses Hana's reply with `this`. | Revision changes “missing sentence in the reference text” to “missing sentence in the recording.” RESOLVED_IN_THREAD and authority evidence `1790910023.000226` remain intact. Other interpretation fields are preserved. | **PASS** for the stated pilot criteria. | 4 / 4 |
| `1790915374.000127` | Silent clip versus waveform; root asks QN or quality score. Glossary defines QN as Quarantine. Replies offer context and diagnostics. | Run stopped during its first prose comparison, before revision. Original “QN (quality note)” remains explicitly provisional under NEEDS_REVIEW. | **INCOMPLETE.** Terminology correction criterion was not demonstrated; original summary still needs correction. No retry was made. | 2 / 1 |
| `1790903186.000110` | Waveform loads without playback; Mina asks for diagnostics. TL's eyes is on the root and does not approve an answer. | Original retained unchanged: UNRESOLVED, authority false, no authority IDs; summary describes requests for evidence. | **PASS** for the stated pilot criteria. | 2 / 2 |

Exact false-acceptance sequence for 111:

1. First prose comparison correctly returns **UNSUPPORTED** for `summary:1`,
   explaining that recurrence does not establish a failed workaround.
2. Agent 1's single revision fixes terminology/resolution/authority but retains
   the same failed-workaround claim.
3. The fresh second comparison returns **SUPPORTED**, calling “seems to have
   failed” a reasonable paraphrase of recurrence. Exact IDs and quotations are
   valid, so structural validation cannot expose that semantic mistake.

Evidence is preserved in
`data/processed/agent1_verified_pilot_v6/records/64b1fa303985b0aabec75d2d73bceb1e3b77e0fe222b4ed395a0496c67428024/`
(`prose_1.raw.txt`, `revision_1.raw.txt`, `prose_2.raw.txt`, and exact requests/HTTP
responses). The root evidence is message `1790882197.000111`; Priya's request for
reproduction is `1790882343.000339`.

This is a live semantic integration failure, **not a fixture-migration failure**.
It demonstrates an incomplete revision and inconsistent model comparison. It
does not establish that batching alone caused the error. Separately, the fixed
transport defect was the old CrewAI layer's potential hidden rate-limit retries.

## Later 200-thread commands and readiness

The following full offline preflight was executed successfully: **200 inputs,
4 cached, 196 new; maximum 784 additional calls; no model calls or output writes.**

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --output-dir data/processed/agent1_verified_pilot_v6
```

Prepared paid continuation syntax, **not executed and currently blocked by the
failed pilot criterion**:

```powershell
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --output-dir data/processed/agent1_verified_pilot_v6
```

This exact configuration reuses all four terminal records, including the false
CORRECTED and interrupted NEEDS_REVIEW records. It will not repair or retry them.
Only 196 unstarted records can make calls (at most 784). Source, glossary,
candidate/baseline, code/prompt/schema, models, and package fingerprints must
match. A future code/prompt fix requires a new versioned directory; the current
cache cannot silently certify the new implementation. A fresh 200-thread run
would have an 800-call ceiling and needs separate authorization. No new paid
pilot or prompt-tuning cycle is authorized by this report.

Still unmet: all pilot criteria, the full 200-record run, and the fixed
four-project content review in `agent1-review-sample.json`. Future completion
requires 200 unique records, outcome counts summing to 200, intact lineage,
explicit review reasons/disputed fields, a passing pilot, and honest reporting of
sampled semantic errors. NEEDS_REVIEW is an acceptable retained outcome.

## Agent 2 handoff

The nested `interpretation` schema is unchanged. Preserve sibling
`verification_status`, `provisional_fields`, `review_reason`, `revision_count`,
and `lineage`; do not infer truth from status or confidence alone. Join on the
full project/batch/channel/thread identity. Source/baseline hashes and evidence
paths trace every output to original Slack, the frozen candidate, and model
requests/responses. `review_queue.json` supplies automated review findings.

For this pilot, also consume the separate source-review findings in
`agent1-pilot-content-review.json`: **111's summary is disputed despite its
CORRECTED label**, and 127 remains provisional. The machine artifacts were
preserved as observed evidence rather than rewritten to hide the false pass.
Provisional interpretations may support tentative grouping or question discovery
with review flags carried forward. Disputed claims must not become established
answers, policies, authoritative decisions, or resolved conclusions without
source review. Agent 2's existing behavior and loaders remain unchanged.
