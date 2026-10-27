# Agent 2 operational guide ? completed taxonomy v7

Agent 2 taxonomy is **closed, complete with nonblocking review**: 90 CONSOLIDATED
groups, 97 topics, 200 unique identities, 516 retained source messages and all 49
inherited obligations. Exactly 86 new requests completed; four accepted pilot
results were reused. Zero failures, interruptions, unprocessed groups or unknown
completions. No further run is needed or authorized by this guide. See the
[completion report](agent2-taxonomy-refactor.md).

## Scope and frozen producer

Agent 1 interprets Slack. Agent 2 organizes canonical summaries/questions into
coherent topics, splits candidates when useful, names topics and accounts for
outliers. Names/rationales are grouping metadata, not policy or verified answers.
Future Agent 3 owns research, answer/policy reassessment, final severity and
recommendations. It is not implemented here.

Accepted producer: `openai/gpt-5.4-2026-03-05`, low reasoning, 8192 completion tokens,
no temperature/top_p/logprobs, prompt `agent2-taxonomy-v7`, strict response schema 7,
adapter `taxonomy-to-canonical-v1`. One POST/group; no SDK retry, repair, fallback
or verifier. Code, model, prompt, glossary and grouping remained unchanged.

Requests contain project/batch, stable member IDs, canonical summary/question and
approved glossary. Raw Slack, evidence inventories, prior Agent 2 narratives,
reviews, severity instructions and evaluation labels are excluded. Full canonical
records/sources survive passively. Assigned/rejected IDs must partition input
exactly; failures retain explicit unassigned members. Singleton, social and
announcement topics are permitted. Same names do not merge groups or projects.

Separate deterministic severity uses `provisional-operational-severity-v2` and
`canonical-impact-availability-v1`. All 97 actual topics remain UNKNOWN/UNASSESSED:
no approved structured operational-impact signals exist in these inputs. Prose,
flags and task-labeling major/minor do not determine severity. Synthetic tests
cover nonblocking HIGH routing; this run does not show real HIGH detection.

## Current canonical handoff

| Artifact | Purpose |
| --- | --- |
| `data/processed/agent1_verified_v3/interpretations.json` | Unchanged 200 inputs: 81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW |
| `data/processed/grouping_agent1_v3/clusters.json` | Unchanged 90 candidates; no embedding/parameter refresh |
| `data/processed/agent2_taxonomy_final_v7/consolidations.json` | Final automated taxonomy records |
| `data/processed/agent2_taxonomy_final_v7/effective_output_reviewed.json` | Current effective snapshot; use this or the loader |
| `data/processed/agent2_taxonomy_final_v7/effective_review_queue.json` | 41 groups requiring effective review |
| `data/processed/agent2_taxonomy_final_v7/member_review_queue.json` | 49 original inherited obligations with evidence/lineage |
| `data/processed/agent2_taxonomy_final_v7/review_queue.json` | Preserved automated 40-group queue |
| `data/processed/agent2_taxonomy_final_v7/release_manifest.json` | Current reviewed release pointers, hashes and counts |
| `data/processed/agent2_taxonomy_final_v7/manifest.json` | Assembly receipt, original run/file provenance |
| `data/experiments/agent2_taxonomy_final_v7/taxonomy_review.json` | All-group assisted review and three naming cautions |
| `data/experiments/agent2_taxonomy_final_v7/request_ledger.json` | 86 new + four reused attempts, tokens, latency and hashes |

The reviewed view adds three nonblocking naming cautions. Two affect groups
already carrying inherited flags; one adds a review group. No automated result
or member was rewritten. Assembly-time `effective_output.json` and its manifest
hash remain preserved snapshots with 40 review groups; `release_manifest.json`
points to the later reviewed view with 41. Use the current pointer or loader.

The mandatory `docs/agent2-review-supplements.json` retains historical reviews and
adds the new exact-output review. Findings bind to input/raw/result file hashes;
stale findings never migrate to new outputs. Agent 1's pilot registry and full-batch
review evidence remain in the payloads. No v6 semantic findings were transferred.

## Inspect or export without model calls

From the repository root:

```powershell
uv run --locked python -c "from threadsense.agents.topic_effective import load_effective_output; v=load_effective_output('data/processed/agent2_taxonomy_final_v7'); print(len(v['records']), len(v['review_queue']), len(v['member_review_queue']), len(v['applied_content_obligations']), v['review_binding_status'])"
```

Expected: **`90 41 49 3 VALID`**. No API key/model call is needed. To export another
view, use a fresh file; the exporter refuses overwrite:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_taxonomy_final_v7 --output data/processed/agent2_taxonomy_final_v7/effective_output_inspection_01.json
```

Per-record `taxonomy_handoff` has contract `agent2-taxonomy-handoff-v1`:

- Group identity and processing state; `nonblocking=true`.
- Topics, stable assignments, grouping rationales and separate severity metadata.
- Full canonical members/sources, identity, automated/effective Agent 1 status,
  disputed fields, evidence, source/candidate hashes and lineage.
- Member dispositions, rejected and unassigned IDs, including failure cases.
- Effective review obligations, review evidence and grouping file/hash provenance.

Retain every member and obligation even without a question, topic or recommendation.
Group acceptance, LOW/N/A or repeated claims cannot clear an inherited dispute.
There is no regenerated answer inventory or v7 `research_handoff`; the historical
v6 narrative contract is superseded.

## Completed execution record ? do not rerun

The [freeze](../data/experiments/agent2_taxonomy_final_v7/freeze.json) records code,
parameters, glossary, source/grouping hashes, exact 86 requests, original pilot
hashes and preflight cost estimate. Selection was canonical 90 minus accepted four:
**86 groups / 189 identities / 46 flags**. The four pilot calls were not repeated.
The existing locked environment was used directly:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
$env:THREADSENSE_AGENT2_REASONING_EFFORT = 'low'
.venv\Scripts\python.exe -X utf8 scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-taxonomy-remaining-v7.json --max-requests 86 --output-dir data/processed/agent2_taxonomy_remaining_v7
.venv\Scripts\python.exe -X utf8 scripts/run_agent2_batch.py --run --pilot docs/agent2-taxonomy-remaining-v7.json --max-requests 86 --output-dir data/processed/agent2_taxonomy_remaining_v7
.venv\Scripts\python.exe -X utf8 scripts/assemble_agent2_dataset.py --reused-run data/processed/agent2_taxonomy_pilot_v7 --new-run data/processed/agent2_taxonomy_remaining_v7 --output-dir data/processed/agent2_taxonomy_final_v7
```

These are completed-command provenance, not pending instructions. Output paths
already exist. The review registry was extended after execution, so old selection
fingerprints intentionally differ from the current registry. Do not bypass this
check, edit freezes or rerun accepted groups. The release is an assembled dataset,
not a resumable batch directory.

Preflight estimated $1.633503 at 1,000 completion tokens/group or $10.911183 at all
output allowances with estimated input. Actual new usage was 65,807 input + 11,280
output tokens (including 1,466 reasoning), no cached tokens; standard-rate estimate
**$0.333718**, not an invoice. No separate local dollar cap was found; provider
limits remained unchanged. The report/ledger give rates, source and latency.

## Validation and limitations

The actual-artifact audit passed coverage, exact-request/replay, preservation,
partitions, ledger, queue, review binding and effective-loader checks. No producer
or assembly/export code changed, so existing receipts were reused: **294 Agent 2
checks passed** (254 historical + 40 taxonomy). Exact commands are saved in
`data/experiments/agent2_taxonomy_v7/validation.json`.

There was **no single green full-suite run**. Final workspace run: 569 passed /
1 failed due to Windows atomic replacement in unchanged Agent 1 stress testing.
C: temporary-directory run: 568 passed / 2 failed due to legacy cross-drive
reconciliation. Agent 1 was not changed and the suite was not repeatedly rerun.
Active Agent 2 persistence and assembly passed in this milestone.

All 90 groups were reviewed against canonical summaries/questions. Three naming
cautions are not policy verification or failed membership partitions. No live
rejected, failed or interrupted group occurred; those paths retain offline coverage.
Taxonomy does not certify Agent 1 truth. Keep inherited flags, UNKNOWN severity
and the grouping-metadata boundary visible downstream.

Next: [Agent 3 strategy discussion](agent3-strategy-handoff.md). No Agent 3, RAG,
dashboard, further prompt experiment or broader run was implemented or scheduled.
Historical v6 reports and the pre-closure v7 guide remain preserved.
