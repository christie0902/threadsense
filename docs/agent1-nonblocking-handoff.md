# Agent 1 workflow and downstream handoff

Version 3 is complete: **200 unique inputs, zero unprocessed, 81 VERIFIED,
70 CORRECTED, 49 NEEDS_REVIEW** after applicable source reviews. All records remain
available downstream. See [the full-batch report](agent1-full-batch-results.md)
for automated versus effective counts, all twelve reviewed cases, and limitations;
see [the README](../README.md) for setup and entry points.

## Verification contract

1. Analyze original Slack and the approved glossary once: root evidence, replies,
   decisions, coverage, and uncertainties.
2. Compare every current summary/question/rationale prose unit against Slack and
   the glossary in one separate request. Previous audit reasoning and evaluation
   labels are excluded. Validate exact candidate identity, quotes, and message IDs.
3. Apply deterministic schema, role, reaction, terminology, coverage, authority,
   and evidence checks. Non-SUPPORTED prose produces explicit findings.
4. If needed, make **one targeted revision maximum** and run one fresh prose
   comparison, reusing only the validated source analysis. A passing fresh check
   produces CORRECTED; first-pass findings stay in history without forcing review.

There are **at most four request attempts per thread, zero retries, and no fallback
calls**. Invalid source analysis stops that record at review. Remaining errors,
uncertainty, malformed evidence, or recoverable failures retain NEEDS_REVIEW and
later threads continue. Verification reliability is separate from Slack resolution:
an accurately summarized unanswered question can be VERIFIED.

QN means Quarantine; LT means Label Tool. Eyes is acknowledgment. Substantive
endorsement requires actual eligible reactor/author metadata and relevant answer
evidence. Diagnostic requests do not settle a decision. An announcement without a
question keeps `central_question: null`; the legacy resolution enum has no N/A.

The controller prefers a structurally usable candidate, then fewer disputed fields;
ties retain the original. An unusable original can retain an actual saved revision
or explicit provisional placeholder. Missing revision text is never reconstructed.
Confidence is not a calibrated score or a substitute for source evidence.

## Persistence and completion

Each thread retains its source snapshot, frozen original, available revision,
source analysis, candidate-specific passes/findings, effective candidate, and lineage.
Stages are `source_analysis`, `prose_1`, `revision_1`, and `prose_2`.

| Artifact suffix | Meaning |
| --- | --- |
| `.started.json` | Stage entered; does not prove a request reached the provider |
| `.request.json`, `.call.json` | Exact request body and single-attempt marker, without credentials |
| `.response.raw.bin`, `.response.json` | Available original HTTP bytes and response metadata |
| `.raw.txt`, `.failure.json` | Available model text or transport failure |
| `result.json` | Parsed candidates, checks, findings, outcome, and artifact checksums |

Started/interrupted records are terminal and never retried automatically. A marker
without a response has unknown provider completion. Subset/resume aggregation keeps
previously retained records; only genuinely unstarted inputs may make new calls.
Only one process may own an output directory. A stale lock requires checking for a
running process before removal.

Exit 0 means valid preflight or completed batch, including `complete_with_review`.
Exit 1 means interruption, fatal failure, or unprocessed inputs; invalid CLI/input/
cache checks use exit 2. Persistence failures can raise directly. NEEDS_REVIEW does
not stop the overnight pipeline; fatal configuration/persistence failures do.
Always inspect coverage and `unprocessed`, not just the exit code.

## Read-only finalized-v3 preflight

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --content-review data/processed/agent1_full_batch_review_v3/content_review.json --output-dir data/processed/agent1_verified_v3
```

Expected: **200 compatible cached records, zero unstarted, zero remaining model
tasks; 16 valid review records, zero invalid**. This command makes no model calls
or output writes. Do not rerun the completed batch to refresh its interpretation.

The live-cache fingerprint includes fourteen code files listed by
`run_configuration()` in `scripts/run_agent1_verification.py`, original source and
baseline content, glossary bytes, model pins, pipeline version, and package
versions. Per-record checks also validate candidate, request/response, marker, and
result checksums. Changes can invalidate reuse even when interfaces look unchanged.
Never edit historical metadata to force compatibility or treat historical v2 or
offline-reconciliation outputs as a current live cache.

## Canonical export and reviews

Consume [interpretations.json](../data/processed/agent1_verified_v3/interpretations.json).
The nested `ThreadInterpretation` is accompanied by:

- Effective `verification_status`, original `automated_verification_status`,
  `review_required`, disputed `provisional_fields`, reasons, and findings.
- Full project/batch/channel/thread identity, original message IDs, exact review
  evidence quotes, source/candidate hashes, and baseline provenance.
- Revision count, effective attempt, original/revised/effective candidate lineage,
  source/result paths, and review provenance/application diagnostics.

[review_queue.json](../data/processed/agent1_verified_v3/review_queue.json) is exactly
the same complete records filtered by `review_required`: **49 of 200**. Lineage
source/result paths resolve relative to the export directory; review evidence paths
resolve relative to the repository. The manifest describes coverage and accounting.

Every future export refresh must explicitly load **both**
[the historical pilot registry](agent1-pilot-content-review.json) and
[the full-batch review file](../data/processed/agent1_full_batch_review_v3/content_review.json).
The runner's default includes only the historical registry; omitting the second
file can lose current disputes from an export. Use the existing v3 `write_reports()`
interface with validated cached results and model calls disabled, as recorded in
the [completed milestone report](agent1-full-batch-results.md). The historical
reconciler writes a separate derived directory, not the finalized live export.

Reviews bind to all four identity fields and exact source/candidate content in
their referenced results. Validate file checksums, IDs, quotes, and disputed fields.
Applicable unresolved disputes force effective NEEDS_REVIEW without editing prose,
automated outcomes, or raw evidence. A new candidate requires a new review;
historical hashes are not transferable. Positive reviews never erase a dispute or
imply human approval. Reports expose applied, matched, stale, unmatched, or invalid
bindings. Reviews and evaluation labels never enter model requests.

The twelve new reviews are **Codex-assisted source reviews, not human approval or
independent ground truth**: seven passes within scope, four errors, one uncertainty.
The selected sample cannot estimate full-batch accuracy. Historical reviews lacking
reviewer/timestamp metadata retain null values and explicitly computed bindings.

## Agent 2 connection and remaining downstream obligations

The [Agent 2 offline integration](agent2-offline-integration.md) now consumes all
200 finalized canonical records with 90 refreshed tentative groups. It preserves effective/automated
statuses, flags, disputed fields/reasons, exact evidence, full identity,
source/candidate hashes, and original/revised lineage through consolidation.
Its four-group live pilot is prepared but has not run. Group summaries must keep
constituent flags. Provisional claims can support
tentative grouping or question discovery, without becoming confirmed answers,
policy, authoritative decisions, or resolved conclusions.

Later Agent 3 retrieval should preserve citations, known publication/effective
dates, project scope, and authority. Unresolved temporal/authority conflicts remain
review cards. All flags must reach a future briefing's Needs Review section, even
without a recommendation. Retrieval and briefing remain planned; offline Agent 2
integration does not establish live semantic accuracy or implement Agent 3.

## Historical evidence retained

The early combined-audit workflow could incur CrewAI retries despite a stage cap;
the current transport makes one POST per stage. Old-schema responses remain raw
evidence and correctly fail the new required-prose parser. Pilot v5 falsely
accepted a recording/reference reversal. The v6 revised workaround summary still
claimed a failed workaround unsupported by the source, and its interrupted QN
request has unknown provider completion (12 attempts, 11 responses). The later
v3 run fixed some candidates but still falsely accepted that workaround claim and
a denial of a supplied example; their effective review flags remain visible.

- `data/processed/agent1_verified_pilot_v1/`: real old-schema parser regression.
- `data/processed/agent1_verified_pilot_v5/` and
  `experiments/prose_comparison_v1/`: saved sources and eight synthetic benchmark
  inputs; saved live experiment v2 responses support real-parser replay.
- `data/processed/agent1_verified_pilot_v6/`: exact historical review bindings and
  interrupted evidence. `data/processed/agent1_handoff_reconciled_v1/` contains
  separate offline replay/export evidence (1 VERIFIED, 1 CORRECTED, 2 NEEDS_REVIEW).
- `.cache/agent1_full_batch_20261022/`: original local audit tools and snapshot.
  Their closed-milestone preservation checks refer to the pre-cleanup tree; use
  Git commit `053d3144f735597c0d3976db3e830690dfcc3afc` to recover that tree.
- Earlier `.cache/agent1_*`, `prose_experiment_20261022`, and
  `prose_fixture_migration` snapshots retain uncommitted recovery/history evidence.

The historical integrity ledgers remain unchanged observations of their original
milestones. Documentation consolidation is tracked separately in the
[cleanup record](repository-cleanup.md); it does not rewrite those ledgers.
