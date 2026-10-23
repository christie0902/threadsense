# Agent 1 full-batch evaluation and finalized handoff — version 3

For current commands and the downstream contract, see the
[handoff guide](agent1-nonblocking-handoff.md). This report records the completed
evaluation; earlier execution commands below are historical, not export-refresh
instructions. Any future refresh must load both review registries.

Subsequent milestone: [Agent 2 offline integration](agent2-offline-integration.md)
now connects this unchanged canonical handoff. The execution and review findings
below remain the original Agent 1 milestone record.

The authorized version 3 batch completed with exit code 0: **200 unique full
project/batch/channel/thread identities, exactly matching the frozen input set,
and zero unprocessed inputs**. Its state is `complete_with_review`. The predefined
12-candidate source review and offline export refresh are also complete. Existing
Agent 2 code was unchanged; its canonical-export connection and Agent 3 remain
future work.

This completes the requested execution, integrity, sample-review, and handoff
milestone. It does not establish that the model is fully accurate. The review
found definite errors in four sampled candidates and a framing uncertainty in
one more. All remain visible in the final handoff.

## Execution and request accounting

Preflight confirmed 200 input identities, no compatible preexisting version 3
records, and an 800-attempt maximum. The originally documented directory was
used. No fingerprint check was bypassed and no alternative paid run was started.
The same process continued through NEEDS_REVIEW outcomes and recoverable failures.

The paid run completed at **2026-10-22T23:55:25.450046+00:00**. Later review/export
timestamps are recorded separately in the review evidence and final manifest;
they do not represent additional live verification. The pre-review manifest is
preserved in the review artifact directory.

| Request accounting | Actual |
| --- | ---: |
| New request attempts / authorized maximum | 593 / 800 |
| Completed HTTP responses | 593, all HTTP 200 |
| Completed model responses (`finish_reason=stop`) | 593 |
| Requests with unknown provider completion | 0 |
| Started stages without a network-attempt marker | 0 |
| Maximum attempts for one thread | 4 |
| Maximum revisions for one thread | 1 |
| Automatic retries or fallback calls | 0 |
| Model calls during review, validation, or export | 0 |

The attempts comprise 200 source analyses, 193 first prose checks, 111 targeted
revisions, and 89 fresh second prose checks. The remaining 207 authorized attempts
were not used. A completed response does not mean its content passed validation.
The 47 automated NEEDS_REVIEW outcomes comprise seven unaccepted source analyses,
22 revision errors, and 18 unsuccessful or uncertain second checks. No fatal
configuration or persistence failure interrupted the batch.

The historical v6 request without a response remains unknown in its untouched
historical directory. The zero unknown-completion count above applies only to
this version 3 run; it does not retroactively certify that older request.

Exact commands used for the preflight and the one paid run:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --output-dir data/processed/agent1_verified_v3
uv run --locked python scripts/run_agent1_verification.py --run --limit 0 --content-review docs/agent1-pilot-content-review.json --output-dir data/processed/agent1_verified_v3
```

The existing Windows uv cache and API access required execution outside the
filesystem/network sandbox. Credentials were read through the existing local
configuration; none was printed or written into request artifacts. No models,
prompts, dependencies, source data, or production verification code were changed.

## Automated versus effective outcomes

| Status | Original automated | Final effective handoff |
| --- | ---: | ---: |
| VERIFIED | 82 | 81 |
| CORRECTED | 71 | 70 |
| NEEDS_REVIEW | 47 | 49 |
| Total | 200 | 200 |

Thread `1790882197.000111` is automated CORRECTED but retains the unsupported
failed-workaround claim. Its unchanged wording matched the existing historical
dispute, so it was already effectively flagged before the new review. A fresh
source review was nevertheless bound to its actual version 3 files.

Thread `1790871613.000001` is automated VERIFIED but incorrectly says no examples
were provided. Avery supplies an example of a citation supporting a different
claim. Its `resolution_rationale` is now disputed, adding one record to the
pre-review queue (48 to 49). The original automated outcomes, candidate text,
source snapshots, and all raw evidence remain unchanged.

Successful corrections remain CORRECTED unless a matching unresolved content
dispute exists. First-pass findings do not themselves impose permanent human
review. There are 122 retained original candidates and 78 retained revisions;
no provisional placeholder was necessary. Seven retained revisions remain
automatically NEEDS_REVIEW, while 71 passed their automated second checks.

## Fixed twelve-record source review

The selection in `docs/agent1-review-sample.json` was not changed. All twelve
actual new candidates were compared with original Slack text, actual authors and
roles, reaction users and targets, and the approved glossary. Judgments were
recorded separately from model status and were not sent to any model.

This is **Codex-assisted source review**, not human approval or independent
ground truth: seven candidates have no identified discrepancy within this
review's scope, four contain definite errors, and one retains a framing ambiguity.

| Thread | Automated → effective | Source-review outcome and limitation |
| --- | --- | --- |
| `1790903186.000110` | VERIFIED → VERIFIED | Pass: diagnostic request is preserved; TL U006 eyes on the root is not approval of Mina's reply. Cause and handling remain unknown. |
| `1790882197.000111` | CORRECTED → NEEDS_REVIEW | Error in `summary`: a possible historical workaround becomes one that “seems to have failed.” Neither an attempt nor failure is established. QN, resolution, and authority handling are otherwise supported. |
| `1790909920.000138` | CORRECTED → CORRECTED | Pass: the sentence is missing from the recording; Hana's item-specific guidance has actual TL U006 `this` endorsement on reply `1790910023.000226`. No general scoring penalty is established. |
| `1790915374.000127` | CORRECTED → CORRECTED | Pass: QN means Quarantine. Silence and diagnostic questions do not settle quarantine versus quality scoring or establish the cause. |
| `1790857839.000141` | NEEDS_REVIEW → NEEDS_REVIEW | Error in `central_question` and `resolution_rationale`: a calendar announcement is converted into a scheduling inquiry and its answer. The legacy resolution label alone is not counted as an error. |
| `1790868080.000142` | NEEDS_REVIEW → NEEDS_REVIEW | Error in `central_question` and `resolution_rationale`: the queue-closure announcement becomes an invented yes/no inquiry and a claimed resolution. Acknowledgment remains accurately summarized. |
| `1790861853.000153` | CORRECTED → CORRECTED | Pass: the candidate preserves no policy change and the monolingual-prompt scope/loanword exception. That limited guidance does not settle all invited code switching or supply affected task references. |
| `1790862733.000190` | CORRECTED → CORRECTED | Pass: reopening follows the deployment window; no question or authority is invented. No exact reopening time is supplied, and the legacy resolution enum is not an operational incident claim. |
| `1790871613.000001` | VERIFIED → NEEDS_REVIEW | Error in `resolution_rationale`: it denies examples despite Avery's citation-mismatch example. The scoring method remains unresolved and no authoritative answer is supplied. |
| `1790883558.000028` | NEEDS_REVIEW → NEEDS_REVIEW | Uncertainty in `central_question` and `resolution_rationale`: an instruction to collect affected references is framed as a decision about which references to add. This may be a paraphrase of an information request, so it is not classified as a definite contradiction. |
| `1790869444.000077` | CORRECTED → CORRECTED | Pass: the reported old-QN/help-page versus revised-TL/document conflict stays unresolved. The referenced documents and their precedence were not retrieved or certified. |
| `1790882550.000099` | CORRECTED → CORRECTED | Pass: pinned-schedule reminder and acknowledgment are preserved without an invented question. The actual schedule/staffing coverage was not independently inspected. |

Two automatically accepted sampled candidates have definite source discrepancies
(111 and 001). The other two definite errors and the framing uncertainty were
already automatically flagged. This small, deliberately selected sample includes
eight announcement-channel records and cannot establish a full-batch accuracy rate.
Confidence values are uncalibrated, and the frozen interpretation schema has no
N/A resolution value for announcements. External policies and incident outcomes
were outside this source review.

Every sampled finding, including the uncertainty, is recorded with affected
fields, the exact candidate substring, exact source quotes/IDs, source/result
file references and hashes, and the reviewed candidate in
[content_review.json](../data/processed/agent1_full_batch_review_v3/content_review.json).
Positive review rows also retain the complete source messages, reaction metadata,
review notes, and limitations. All imported reviews are explicitly nonapproval.

## Offline application and integrity checks

The existing `scripts/run_agent1_verification.py::write_reports()` interface was
used with validated version 3 cached results and both review registries. The v2
historical reconciler was not used. During this export, model entry points,
credential access, and socket connections were guarded to fail if called.
No additional revision, retry, model request, or text repair was performed.

Twelve new reviews have valid bindings to actual version 3 source and candidate
files. Historical review 110 still matches, historical dispute 111 still applies,
and historical reviews 138 and 127 are explicitly STALE_CANDIDATE. They were not
transplanted onto changed candidates. The fresh reviewed versions of 138 and 127
remain CORRECTED. Reviewer identity is recorded as Codex assistant, with an actual
review-finalization timestamp; `human_approval` is false.

The final offline evidence checks passed:

- Exactly 200 unique full identities match the input set; counts sum to 200 and
  `unprocessed` is zero. Every record contains a validated interpretation.
- Source, original/revised/effective candidate fingerprints and file references
  resolve. Available stage requests, raw responses, parsed text, checks, findings,
  and revision lineage are retained.
- The 49-record queue exactly equals the full canonical records with
  `review_required=true`; all 200 records remain available downstream.
- All 593 exact requests match the frozen production request builders, including
  their candidate-specific prose and revision inputs. Neither review labels nor
  evaluation answers were added to requests. Stage names are unique per thread.
- Request markers, responses, one-revision bounds, and four-attempt bounds agree
  with the manifest. No started request or partial response is hidden.
- Raw Slack authors, roles, reaction users, and targets were checked for all 200
  source snapshots against the original fixture files.
- All 606 snapshotted preexisting files remain byte-identical, including frozen
  sources, interpretations, grouping, evaluation data, historical pilot and
  experiment artifacts, original review evidence, sample selection, code, and
  dependency files. The version 3 source/candidate/request/response files also
  remain unchanged across the offline export refresh.

The previous **277-passing-test offline validation** was reused as instructed;
the suite was not rerun or changed during this execution-only milestone. Current
checks validate the new actual evidence rather than substituting mocked outcomes.

The local, model-disabled evaluation commands were:

```powershell
.venv\Scripts\python.exe .cache/agent1_full_batch_20261022/audit_handoff.py
.venv\Scripts\python.exe .cache/agent1_full_batch_20261022/write_content_review.py
.venv\Scripts\python.exe .cache/agent1_full_batch_20261022/audit_handoff.py --apply-review
```

These helpers are retained task-local audit tools, not changes to the production verifier.
The commands above record the original milestone, not a repeatable refresh recipe:
the review file already exists and the preservation checks expect the original
pre-cleanup tree (Git commit `053d3144f735597c0d3976db3e830690dfcc3afc`).
Use the read-only preflight below for current cache validation. Cleanup checks
are recorded separately in [the cleanup report](repository-cleanup.md).
The durable check results and request/file hash ledger are saved in
[integrity_report.json](../data/processed/agent1_full_batch_review_v3/integrity_report.json).

A final read-only preflight after review application also passed: **200 compatible
cached records, zero unstarted records, 16 valid imported reviews, and zero
remaining model tasks**. With the same model environment settings, its exact
command was:

```powershell
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --content-review data/processed/agent1_full_batch_review_v3/content_review.json --output-dir data/processed/agent1_verified_v3
```

## Final artifacts and downstream handoff

- [Canonical export: all 200 records](../data/processed/agent1_verified_v3/interpretations.json).
- [Matching review queue: 49 complete records](../data/processed/agent1_verified_v3/review_queue.json).
- [Final manifest](../data/processed/agent1_verified_v3/manifest.json).
- [Review applicability and provenance](../data/processed/agent1_verified_v3/content_review_report.json).
- [Twelve-case review evidence](../data/processed/agent1_full_batch_review_v3/content_review.json).
- [Final integrity and attempt ledger](../data/processed/agent1_full_batch_review_v3/integrity_report.json).
- [Execution and final-preflight receipt](../data/processed/agent1_full_batch_review_v3/run_receipt.json).
- [Original completed-run manifest before the new review](../data/processed/agent1_full_batch_review_v3/pre_content_review_manifest.json).
- Original per-thread evidence: `data/processed/agent1_verified_v3/records/` and
  `data/processed/agent1_verified_v3/sources/`.

The next milestone is to connect Agent 2 to this finalized canonical export.
Its existing loader/behavior has not yet been changed to meet these obligations:

- Consume all 200 records using full project/batch/channel/thread identity and
  preserve effective status separately from original automated status.
- Carry review flags, disputed fields/reasons, exact evidence, source/candidate
  fingerprints, and original/revised lineage through grouping and consolidation.
- Allow provisional claims to support tentative grouping or question discovery,
  without promoting them to confirmed answers, policies, or authoritative decisions.
- Preserve member-level flags when merging threads. Route every remaining flagged
  item to the eventual Needs Review briefing, even without an ordinary recommendation.
- Keep Slack resolution separate from verification reliability, and respect
  announcement/null-question limitations. Positive assisted review is not human approval.

Future export refreshes must load **both** the original pilot review registry and
the new version 3 review file. Reusing an old command with only the pilot registry
would omit the new sampled disputes. Read the finalized export directly for the
Agent 2 connection; do not rerun verification or silently drop its sibling metadata.
Agent 3 retrieval, external-document conflict ordering, and briefing implementation
remain future work.
