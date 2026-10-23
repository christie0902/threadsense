# Agent 1 nonblocking handoff completion report — 2026-10-22

The nonblocking export and offline pilot reconciliation are complete. No paid
calls were made in this milestone. Full Agent 1 validation remains pending the
actual 200-thread run, integrity checks, and predefined content sample review.

This is the current workflow and command reference. Earlier version 1/2 reports
remain historical records; their blocking review gate, old exit codes, separate
content-dispute lookup, and 196-thread/784-call continuation guidance are superseded.

## Checkpoint and evidence

The starting checkpoint was checked against local files, not inferred from the
earlier report. Before editing, the full offline suite passed again: **257 passed,
0 failed**, 162 dependency warnings, 41.81 seconds, using:

```powershell
.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-review-baseline
```

The v6 evidence contains **12 saved request attempts, 11 completed responses,
and one request without a saved response**. Completion and billing of that last
request at the provider remain unknown. Real parsers, candidate/quotation/ID
validators, and deterministic verification were used for offline replay. No
missing response was reconstructed. Available local manifests do not contain a
completed 200-thread verification run.

| Thread | Historical automated status | Effective handoff status | Retained evidence and limitation |
| --- | --- | --- | --- |
| `1790903186.000110` | VERIFIED | VERIFIED | Original unchanged; diagnostics and TL eyes do not establish an answer or approval. |
| `1790882197.000111` | CORRECTED | NEEDS_REVIEW | Revision still claims a previous workaround “seems to have failed.” Actual source establishes a possible workaround and recurrence, not an attempt or failure. |
| `1790909920.000138` | CORRECTED | CORRECTED | Revision correctly places the missing sentence in the recording. Supported TL endorsement and resolution remain intact. |
| `1790915374.000127` | NEEDS_REVIEW | NEEDS_REVIEW | First prose request was interrupted; retained original still incorrectly expands QN as quality note. |

The false acceptance on 111 is a semantic model/revision failure, not a test
fixture failure. Routing its dispute does not fix its prose or establish model
accuracy. Historical machine counts remain 1 VERIFIED, 2 CORRECTED, 1 NEEDS_REVIEW;
effective counts are **1 VERIFIED, 1 CORRECTED, 2 NEEDS_REVIEW**.

## Current workflow and completion semantics

The model flow and prompts are unchanged: one source-only analysis, one batched
prose comparison and deterministic check, optionally one targeted Agent 1 revision,
then one fresh prose comparison reusing the validated source analysis. There are
at most **four request attempts per thread, zero retries, and no fallback calls**.

An original passing candidate is VERIFIED. A revised candidate passing its fresh
check is CORRECTED automatically; first-pass findings remain in history without
creating a permanent review flag. Remaining errors, uncertainty, invalid/missing
evidence, and recoverable request failures retain one provisional NEEDS_REVIEW
record. Later threads continue. An accurately interpreted unanswered discussion
can be VERIFIED: Slack resolution and interpretation reliability are separate.

The existing controller selects a structurally valid candidate, then fewer
disputed fields; ties retain the original. Recovery also preserves an actual
saved revision and uses it if the original is unusable. An interrupted revision
is never inferred from missing text. Invalid originals retain explicit placeholders
when no usable candidate exists. Raw evidence and candidate lineage remain accessible.

NEEDS_REVIEW is terminal for that run. Cached flagged or interrupted records are
never automatically retried. Human review occurs after the overnight run, with
no approval step between threads or agents. Exit 0 means a valid preflight or a
completed batch, including `complete_with_review`; exit 1 signals interruption,
fatal failure, or retained unprocessed inputs. Invalid CLI/input/cache checks use
exit 2. Fatal configuration and persistence failures stop further calls and cannot
be reported as successful completion. Persistence errors may raise directly when
the filesystem cannot save a failure report. Inspect manifest coverage and
`unprocessed` as well as the exit code before treating a subset as a full batch.

## Canonical handoff and generic content-review binding

Normal and flagged records share one canonical `interpretations.json`, preserving
the nested `ThreadInterpretation` schema. Sibling fields include:

- `verification_status` (effective), `automated_verification_status`, `review_required`.
- `provisional_fields`, `review_reason`, `review_reasons`, `review_findings`.
- Full project/batch/channel/thread identity, source message IDs, exact review
  evidence IDs/quotes, source and candidate SHA-256 fingerprints.
- Revision count, effective attempt, baseline provenance, original/revised/effective
  candidate hashes, and references into saved candidates and both audit passes.
- `content_reviews` with original review type, review file/hash/JSON pointer,
  referenced source/result hashes, and explicit application diagnostics.

The review queue contains the **same complete records** filtered by
`review_required`. It is not a separate classification or competing status list.
Source/result references in `lineage` resolve relative to the export directory;
original review evidence references resolve relative to the repository.

`--content-review` accepts repeatable explicit review documents, defaulting to
`docs/agent1-pilot-content-review.json`. Production logic contains no pilot IDs.
Reviews bind to all four identity fields plus the exact actual source and retained
candidate from their referenced result. Result checksums, source IDs, quotations,
disputed fields, and any supplied binding hashes are validated. Applicable open
disputes override automated acceptance. Positive reviews never erase a dispute
or imply human approval. Evaluation data is excluded from runtime review inputs.

The older review file has no reviewer identity, review timestamp, or supplied
binding hashes. Its identity and timestamp remain null. Hashes are computed from
the actual referenced files and explicitly marked `computed_from_referenced_evidence;
not reviewer-attested`. Every imported review has `human_approval: false`.
No human approval or missing historical metadata was invented.

`content_review_report.json` reports APPLIED_DISPUTE, MATCHED_NONAPPROVAL,
UNMATCHED_IDENTITY, STALE_SOURCE, STALE_CANDIDATE, or INVALID_REVIEW. Matching records
also carry applicability diagnostics. Invalid or stale reviews cannot silently
change status. Exact binding intentionally does not transfer a semantic judgment
to a newly worded candidate; that requires a new content review. Review documents
are export inputs, never model-request context or evaluation answers.

## Saved derived outputs

The new directory is explicitly an **offline reconciliation**, not new live
verification or a resumable verification cache:

- [Canonical export](../data/processed/agent1_handoff_reconciled_v1/interpretations.json): all four records.
- [Matching review queue](../data/processed/agent1_handoff_reconciled_v1/review_queue.json): 111 and 127.
- [Review applicability/provenance](../data/processed/agent1_handoff_reconciled_v1/content_review_report.json).
- [Real saved-response replay checks](../data/processed/agent1_handoff_reconciled_v1/replay_report.json).
- [Derived manifest and historical artifact hashes](../data/processed/agent1_handoff_reconciled_v1/manifest.json).

Exact command executed to write these derived files (zero model calls):

```powershell
.venv\Scripts\python.exe scripts/reconcile_agent1_handoff.py --write --evidence-dir data/processed/agent1_verified_pilot_v6 --output-dir data/processed/agent1_handoff_reconciled_v1 --content-review docs/agent1-pilot-content-review.json
```

The reconciler defaults to read-only `--dry-run` and requires a new separate
versioned output directory, even for preflight. To repeat its checks after the
above directory exists, select another unused destination, for example
`--dry-run --output-dir .cache/handoff_inspection_v1`. No historical source,
request, response, or candidate text is repaired or overwritten.

Representative flagged record, selected fields copied from canonical record
`/1` (the full record includes its unchanged nested interpretation and evidence):

```json
{
  "project_id": "audio_multimodal",
  "batch_id": "audio_batch_06",
  "channel_id": "C_AUDIO_GENERAL",
  "thread_id": "1790882197.000111",
  "verification_origin": "offline_reconciliation",
  "automated_verification_status": "CORRECTED",
  "verification_status": "NEEDS_REVIEW",
  "review_required": true,
  "revision_count": 1,
  "provisional_fields": ["summary"],
  "review_reason": "Recurrence and belief in a possible historical workaround establish neither an attempted workaround nor a failure. First comparison correctly rejected this claim; the revision retained it and the second comparison wrongly accepted it.",
  "input_sha256": "a31ce82a0c8540f826509060d3eed8fe5f0b9af35166fc2a123f69a671a726fe",
  "candidate_sha256": "b3e7e711f6bf0559231b31e8c1fda9c1fdf640a61d63db95065037fa279093fa"
}
```

Its content finding quotes root `1790882197.000111` and TL diagnostic reply
`1790882343.000339`, identifies the disputed substring “recalling a previous
workaround that seems to have failed,” and references both historical candidates
and audits. The provenance points to `/reviews/1` in the original review JSON.

## Downstream obligations (documented, not implemented here)

Agent 2 must consume effective status from the canonical export and preserve flags,
disputed fields, reasons, full identity, source/candidate hashes, and lineage
through consolidation. Provisional claims may inform tentative grouping and
question discovery; they cannot become confirmed answers, authoritative policy,
or resolved conclusions. Group-level summaries must not erase constituent flags.
Consumers should not need the documentation review registry to discover disputes.

Planned Agent 3 retrieval uses both current knowledge and project memory. Preserve
retrieved citations, publication/effective dates where known, project scope, and
source authority. Resolve temporal and authority conflicts only when the evidence
supports an ordering; missing or unorderable sources create review cards and
retain uncertainty while the pipeline continues. Retrieval does not retroactively
approve disputed Slack claims merely because a related external fact is found.

All remaining flagged items must reach the morning briefing's **Needs Review**
section, even when no ordinary recommendation is warranted. Cards should explain
the uncertainty, affected claim/fields, source references, and unresolved conflict.
These are future consumer obligations. Agent 2 behavior, Agent 3, RAG, and dashboard
code were not implemented or changed in this milestone.

## Full-batch preflight and prepared paid run

The following read-only preflight was executed successfully against the current
version 3 code: **200 inputs, 0 compatible caches, 200 unstarted records, maximum
800 additional request attempts**. Four valid review records loaded; none invalid.
The destination did not exist before or after preflight. This makes no API calls
and requires no key. The model pins match the historical requested models; local
model defaults and credentials were not changed.

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --output-dir data/processed/agent1_verified_v3
```

Prepared paid command, **not executed**; use the same model settings above:

```powershell
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --content-review docs/agent1-pilot-content-review.json --output-dir data/processed/agent1_verified_v3
```

Version 3 fingerprints the changed runner/export code and retains the existing
source, baseline, glossary, model, schema/prompt, and package checks. Version 2
pilot caches are incompatible with this live run. Offline reconciliation checks
the saved version 2 contract explicitly without claiming changed code produced
those results. Neither the historical pilot directory nor the derived handoff is
a replacement for the new version 3 destination. Compatible terminal records in
the new destination can later be reused; flagged records will not make new calls.
The dry run always reports the current remaining bound. A changed code/input/model
fingerprint requires another new versioned destination.

Only the paid execution boundary remains for the next run. Once that run is
authorized, individual NEEDS_REVIEW outcomes must never wait for human responses.
After the run, check 200 unique full identities, counts summing to 200, zero
unprocessed inputs, complete source/candidate/evidence lineage, review queue
agreement, four-call caps, and review provenance. Then perform the unchanged
predefined sample in `docs/agent1-review-sample.json` (four pilot regressions plus
two non-pilot threads per project), recording semantic failures honestly. These
steps are still pending; passing offline orchestration tests is not live accuracy.

## Validation performed in this milestone

Focused development checks passed: **36 passed, 0 failed**, 74.53 seconds:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_verification_handoff.py tests/test_agent1_verification_batch.py -q --disable-warnings --tb=short --basetemp .cache/pytest-review-focused2
```

The final full suite, including the subsequent interruption-recovery assertions,
passed: **277 passed, 0 failed, 0 skipped**, 162 dependency warnings, 91.87 seconds:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent1-nonblocking-final
```

The uv invocation required access to its existing Windows dependency cache after
the sandbox denied that directory. It made no model calls. No dependencies,
prompts, models, or original prose tests were changed to obtain these results.

The new tests cover matching and stale review bindings across every identity
field, exact quotations and candidate references, provenance without invented
human approval, invalid/evaluation review inputs, real historical replay and
cache incompatibility, successful correction clearing first-pass flags, failed
middle records, fatal configuration/persistence errors, and saved-revision recovery.
The synthetic 200-thread mixed run produces **50 VERIFIED, 50 CORRECTED, 100
NEEDS_REVIEW**, with 200 unique identities, later records completed after failures,
matching queue/export, retained lineage, bounded stages, and no retries on resume.
Those are mocked orchestration outcomes, distinct from the four historical live
records above. Existing real-input failure-retention, strict transport/call-cap,
fresh-candidate, glossary, and evaluation-isolation tests also passed.

The final artifact check confirmed four unique canonical identities, exactly two
identical flagged queue records, resolvable lineage references, two applied
disputes, two matching nonapproval reviews, and no live output directory created.
Comparison against the task's initial 594-file snapshot found no missing files;
only the six existing code/test/documentation files listed below changed. All
preexisting data and experiment artifacts, frozen interpretations/grouping, Slack,
evaluation data, saved review JSON, predefined review sample, model/prompt code,
and Agent 2 code remained unchanged. Existing uncommitted changes were preserved.
`git diff --check` passed.

## Changes delivered and remaining limitations

| File or directory | Change in this milestone |
| --- | --- |
| `src/threadsense/agents/verification_handoff.py` (new) | Shared canonical exporter and generic evidence-bound content-review import; effective status, queue agreement, and lineage/provenance. |
| `scripts/run_agent1_verification.py` | Version 3 fingerprint, shared exports, terminal nonblocking flags, continuation after recoverable per-thread exceptions, honest fatal/incomplete exit codes, and preservation of saved revisions during recovery. |
| `scripts/reconcile_agent1_handoff.py` (new) | Explicit offline replay of actual archived requests/responses through real validators; writes separate derived results and rejects cache impersonation. |
| `tests/test_verification_handoff.py` (new) | Historical replay, binding/provenance/negative cases, read-only reconciliation, and cache boundaries. |
| `tests/test_agent1_verification_batch.py` | Mixed 200-record and fatal/recovery coverage; expected exit codes updated to the nonblocking completion contract without weakening retention or evidence assertions. |
| `data/processed/agent1_handoff_reconciled_v1/` (new) | Five derived files: canonical records, matching queue, review report, replay report, and manifest. |
| `docs/agent1-nonblocking-handoff.md` (new) | This current completion report, downstream obligations, tested preflight, and prepared live command. |
| `README.md`, `docs/agent1-verification.md` | Link current version 3 behavior and guidance. |
| `docs/agent1-integration-readiness.md`, `docs/agent1-integration-results.md` | Supersession notices; historical reports and observed results retained below them. |

Two production integration defects were addressed: review outcomes previously
returned a failure exit code that could block downstream execution, and the known
semantic dispute was visible only in a separate review document while the canonical
record appeared accepted. Recoverable exceptions now continue, while fatal and
incomplete runs remain visibly unsuccessful. This was workflow/export work, not
test-fixture migration or a change to model judgments.

The known false acceptance on 111 remains, 127's interrupted request still has
unknown provider completion, and no new live accuracy has been measured. Exact
content-review bindings cannot assess differently worded future candidates. The
full 200-record live run and fixed sample review are the next milestone; the
Agent 2/3/briefing flag-preservation obligations remain future implementation work.
