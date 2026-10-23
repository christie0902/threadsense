# Agent 1 integration and readiness — 2026-10-22

> Historical version 2 guidance. The [version 3 nonblocking handoff report](agent1-nonblocking-handoff.md)
> supersedes the blocking pilot gate, review exit codes, separate-document
> handoff, and 196-thread/784-call continuation commands below. Historical
> findings remain unchanged. The current task made no paid calls; the next
> paid run requires authorization, after which individual flags never pause it.

**Current gate: FAILED.** Offline validation passed (257 tests), but the live
pilot falsely accepted the retained failed-workaround claim on thread 111.
Paid work stopped at 12 attempts (11 completed responses); thread 127 was
interrupted and retained for review. See [the completion report](agent1-integration-results.md)
and `agent1-pilot-content-review.json`. Do not execute the prepared paid batch.

## Active call flow (pipeline version 2)

The runner starts from the frozen 200-record Agent 1 baseline. It does not
regenerate interpretations, Slack fixtures, or the grouping baseline.

1. **Source analysis — one call:** original Slack and approved glossary only.
   Validate root evidence, every reply, requested decisions, decision coverage,
   and interpretation uncertainties. Save and reuse this analysis unchanged.
2. **Prose comparison — one call:** original Slack, glossary, and every current
   summary/question/rationale unit. Return one `ProseEvidenceAssessment` per unit.
   No source classifications, previous audit reasoning, or expected labels enter.
3. **Python verification:** combine validated source analysis and fresh prose
   assessments for the existing verifier. Preserve ID, role, reaction, authority,
   glossary, coverage, and exact-quote checks. Convert every non-SUPPORTED unit
   into a specific finding. A clearly unanswered question is not itself ambiguity.
4. **Optional Agent 1 revision — one call:** original Slack, glossary, previous
   interpretation, source analysis, and findings, using the existing interpreter
   rules and model. Preserve correct fields. Then perform one fresh batched prose
   comparison and deterministic check using the same source analysis.

An accurate original takes two calls. A revision takes at most four calls total.
There are no per-sentence fallbacks, adjudication calls, automatic retries,
alternate models, or conversation history. Invalid source analysis stops at
`NEEDS_REVIEW`; invalid prose may receive the single revision and fresh comparison.
Ambiguity or remaining discrepancies after that become `NEEDS_REVIEW`.

`SourceEvidenceAnalysis` and `ProseComparison` are the only new contracts.
`DecisionEvidenceAudit` remains the combined validated evidence view consumed by
the deterministic verifier. Its required prose assessments and legacy explicit
finding validation remain intact. The historical combined `audit_thread_decisions`
helper is not invoked by the version 2 runner/controller.

The new verification transport issues one HTTPS POST per stage, with no SDK or
CrewAI retry layer. This fixes the old workflow's misleading request bound:
CrewAI could retry rate-limit failures despite task retries being disabled.
The baseline interpreter and Agent 2 transports are unchanged.

## Persistence and resumability

Each record retains its original source, frozen baseline hash, original and
revised candidates, source analysis, both passes, findings, and effective attempt.
Each attempted stage (`source_analysis`, `prose_1`, `revision_1`, `prose_2`) records:

- `*.started.json` before entering the stage.
- `*.request.json`: exact UTF-8 HTTP request body, saved before sending.
- `*.call.json`: endpoint and single-attempt marker; no credentials.
- `*.response.raw.bin`: exact HTTP response bytes, including HTTP error bodies.
- `*.response.json`: HTTP status and incomplete-body failure information.
- `*.raw.txt`: model content saved before parsing/validation.
- `*.failure.json` for transport exceptions; validation errors in `result.json`.

Persistence failure stops all further model work. Stage/call markers are
conservative attempt counts if a process dies at the network boundary. Partial
responses, malformed JSON, non-success HTTP responses, and truncated completions
cannot pass. No retry occurs within an attempt or when a started record resumes.

Configuration version 2 fingerprints source, baseline candidate, glossary,
model settings, prompts/schemas/code, and dependency versions. Per-record checksums
cover exact requests, candidate-specific response artifacts, markers, and results.
Fresh prose validation also requires exact current candidate text and complete
unit coverage. Changed inputs/configuration or altered evidence reject cache reuse.
Historical pilot and experiment directories remain unchanged and are never
silently imported into this contract.

Completed records, including `NEEDS_REVIEW`, are terminal within their directory.
An incomplete started record is retained for review without repeating calls.
Only unstarted records are processed on resume. Aggregation retains earlier
subsets and unprocessed rows; narrower selections never silently drop records.
One process may use an output directory. After an abrupt kill, confirm that no
process is running before removing its stale `.running.lock`.

## Commands

From the repository root in PowerShell, pin the requested models. Keys are read
from the existing local `.env`; these commands contain no credentials.

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
```

Complete offline suite:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent1-integration-final
```

The one authorized integrated pilot uses four frozen baseline candidates in a
new directory, with a maximum of 16 calls. This is a record of the command, not
authorization to repeat a failed pilot in a different directory:

```powershell
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --thread-id 1790882197.000111 --thread-id 1790909920.000138 --thread-id 1790915374.000127 --thread-id 1790903186.000110 --output-dir data/processed/agent1_verified_pilot_v6
```

Later 200-thread preflight and paid continuation (the paid command is prepared,
not executed as part of this milestone):

```powershell
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --output-dir data/processed/agent1_verified_pilot_v6
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --output-dir data/processed/agent1_verified_pilot_v6
```

With four terminal pilot records, continuation can add at most **784 calls**
(196 unstarted threads × 4). It reuses those four records without new model
requests only if all fingerprints match. A completely new directory has a maximum
of 800 calls. An interrupted run retains started failures for review and resumes
only unstarted threads; dry run prints the current maximum. Do not proceed with
the paid continuation if the pilot's content criteria failed.

Exit codes: 0 for a valid preflight or all passing results; 1 for interruption;
2 for retained review outcomes or invalid input/cache. A nonzero result does not
authorize retrying a terminal record or changing models.

## Agent 2 handoff

Consume `interpretations.json` as records with the unchanged `ThreadInterpretation`
under `interpretation`. Do not strip sibling `verification_status`,
`provisional_fields`, `review_reason`, `revision_count`, or `lineage`.

- `VERIFIED` retains the original candidate; `CORRECTED` selects the single
  revision after a passing recheck. These statuses describe checks, not guaranteed
  factual truth or calibrated confidence.
- `NEEDS_REVIEW` retains the best available candidate or an explicit placeholder.
  Its disputed fields are provisional, including resolution/authority when listed.
  It may be used for provisional grouping and question discovery with the review
  flag carried forward. Do not turn disputed claims into established answers,
  policies, authoritative decisions, or resolved conclusions without source review.
- Join using project, batch, channel, and thread identity. `input_sha256` and
  `lineage.source_file` identify the original Slack snapshot. Baseline model/run
  hashes, `baseline_record_sha256`, `effective_attempt`, and `verification_file`
  identify how the selected interpretation was produced. Reviewers can trace
  findings to exact message IDs/quotes and requests/responses.
- `review_queue.json` provides reasons, disputed fields, findings, and evidence
  paths. `manifest.json` reports cumulative coverage, outcome counts, configuration,
  unprocessed rows, and recorded model attempts. Agent 2's current loaders/runners
  are unchanged; they are not automatically redirected to this output.

## Readiness criteria and limits

The later run is complete only when it has 200 unique records; outcome counts sum
to 200; no lost lineage or silently discarded failures; explicit review reasons
and provisional fields; passing pilot content criteria; and a fixed source-based
review sample across all four projects. Use the pilot four plus the first two
non-pilot threads per project sorted by full identity, selected before looking at
their statuses. Record every observed semantic error. `NEEDS_REVIEW` is a valid
retained outcome; do not force an all-pass result.

The saved single-unit experiment is replay evidence on eight known cases: 4/4
faithful accepted, 4/4 incorrect rejected, 6/8 exact verdict agreement. Cases 02
and 07 remain CONTRADICTED versus expected UNSUPPORTED. Replay tests wrap responses
in memory to exercise the batch parser; they do not establish batched accuracy.
Mocked orchestration tests establish control flow, persistence, and retention,
not model accuracy. The four-thread integrated pilot separately tests batching
and revision on known regressions, not general accuracy on 200 threads.

The milestone's measured offline results and live source-versus-output review are
recorded in `agent1-integration-results.md`.
