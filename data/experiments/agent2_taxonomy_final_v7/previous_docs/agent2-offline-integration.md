# Agent 2 operational guide ? taxonomy v7

The corrected Agent 2 scope is **taxonomy and cluster hygiene**. The offline
implementation is complete; live grouping behavior remains unverified. Historical
v6 readiness is superseded. Its [results](agent2-milestone-results.md) and
[archived guide](agent2-run-guide-history-through-v6.md) remain historical evidence.
See the [current change report](agent2-taxonomy-refactor.md) for validation and limits.
This milestone authorized zero paid calls; the pilot below is prepared only.

## Responsibilities and contract

Agent 1 interprets Slack. Agent 2 groups those canonical interpretations: coherence,
splits, concise reusable names, brief grouping rationales and explicit outliers.
Agent 3 will own research, answer/policy reassessment, final severity and recommendations.
Agent 2 neither reinterprets Slack nor judges answers, quotations or endorsements.

Each model request contains project/batch context, stable member IDs, Agent 1
summaries/central questions and the approved glossary. Raw Slack, evidence
inventories, prior Agent 2 text, reviews, severity instructions and evaluation labels
are excluded. No runtime taxonomy is currently available. Identical names do not
merge groups or projects. Unresolved, flagged, social and announcement members are eligible.

Prompt `agent2-taxonomy-v7`, strict response schema **7**:

```json
{
  "topics": [
    {"topic_name": "Audio playback failures", "rationale": "These members concern playback failures.", "member_ids": ["member_example"]}
  ],
  "rejected_member_ids": []
}
```

The example ID is synthetic. Assigned and rejected IDs must partition the input
exactly once. Singleton topics and all-rejected groups are valid; empty emitted
topics, unknown/duplicate/missing IDs and blank names/rationales fail without repair.

The passive export adapter is `taxonomy-to-canonical-v1`. Every canonical member,
original source, full identity, automated/effective status, dispute, evidence reference,
hash and lineage survives. Rejected and failed members remain explicit and reviewable;
there are no automatic regrouping calls. Agent 1's 49 obligations cannot be cleared
by taxonomy. Slack resolution remains separate from interpretation reliability.

`severity.py` attaches independent deterministic metadata after export. The current
canonical contract has **no structured operational-impact signals**, so all actual
topics receive `UNKNOWN`/`UNASSESSED`, with provenance and rule
`canonical-impact-availability-v1`, rubric `provisional-operational-severity-v2`.
It does not infer impact from prose, names, flags or raw Slack. Supported HIGH routing
remains nonblocking; other levels never clear flags. Actual HIGH assessment is not
available from these inputs; its routing is tested using explicitly synthetic assessments.

## Current artifacts for downstream discussion

- Canonical input: `data/processed/agent1_verified_v3/interpretations.json`
  (200 records: 81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW).
- Unchanged candidate grouping: `data/processed/grouping_agent1_v3/clusters.json`
  (90 groups). No embeddings or grouping parameters were changed.
- New **pending** passive preview: `data/processed/agent2_taxonomy_v7_offline/`.
  Its `effective_output.json` retains all 200 members/49 obligations, but all
  90 groups are NOT_RUN. This is not a completed taxonomy dataset.
- Per-record `taxonomy_handoff` (`agent2-taxonomy-handoff-v1`) contains assignments,
  canonical members, dispositions, provenance and obligations. There is no new
  `research_handoff`, generated question inventory or duplicate issue/answer synthesis.
- `data/experiments/agent2_taxonomy_v7/synthetic_exports/` exercises success,
  rejection and failure with **synthetic responses only**. Never treat these
  assignments as model results or a production taxonomy.
- `docs/agent2-review-supplements.json` retains all historical output-bound reviews.
  Agent 1's pilot registry and full-batch review evidence remain in every payload.
  Historical Agent 2 disputes stay on their original outputs. New findings require
  exact new input/raw/result hashes; additional supplements extend the mandatory registry.

Later Agent 3 work should use the v7 handoff contract and canonical input above.
There is currently no live v7 assignment dataset. The v6 dataset and old
`agent3-research-input-v1` narrative contract do not validate or define this new scope.
Preserve rejected/unassigned members and review obligations even without a topic,
question or ordinary recommendation. No Agent 3 implementation is included here.

## Inspect and prepare offline

From the repository root in PowerShell, retain the last completed run's model settings
(the local `.env` default may differ; do not change it to force a fingerprint match):

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
$env:THREADSENSE_AGENT2_REASONING_EFFORT = 'low'
uv run --locked python scripts/run_agent2_batch.py --dry-run --limit 0
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-taxonomy-pilot-v7.json
```

The first command must show 90 groups/200 identities/49 obligations; the second
shows four groups/11 identities/three obligations. Both are read-only and zero-call.
Exact pilot requests and pending exports are already saved in
`data/processed/agent2_taxonomy_pilot_v7_prepared/`; freeze, cost estimate, empty
request ledger and selection notes are in `data/experiments/agent2_taxonomy_v7/`.
Do not rerun its one-off preparation script over those artifacts.

The model snapshot remains `openai/gpt-5.4-2026-03-05`, low reasoning, 8192 completion
tokens shared between reasoning and visible output, no temperature/top_p/logprobs.
The transport makes one POST/group, with zero retries, repairs, fallbacks or verifiers.
Schema rejection/refusal/incompletion remains visible; recoverable failures continue.
Configuration/persistence failures remain fatal; unknown completions are never retried.

## Prepared next pilot ? do not execute without new authorization

| Group | Members / inherited obligations | Selection characteristic |
| --- | --- | --- |
| `cluster_bc1ccc03c19a64cf` | 2 / 0 | Related overlapping-speaker interpretations |
| `cluster_b3bfce178039d7d4` | 2 / 1 | Distinct calibration and queue announcements; split/outlier opportunity |
| `cluster_6b59d13144282285` | 6 / 2 | Mixed playback/silence interpretations with retained disputes |
| `cluster_be4e3bac742eccb3` | 1 / 0 | Social-only singleton |

Selection notes and review expectations stay outside model requests. The split/outlier
case is an opportunity to assess membership, not a forced expected answer.

Only after separate authorization, using the same environment settings above:

```powershell
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-taxonomy-pilot-v7.json --max-requests 4 --output-dir data/processed/agent2_taxonomy_pilot_v7
```

**Maximum four new attempts**, one/group. The live destination does not yet exist.
Approximate cost: **$0.077** with 1,000 total completion tokens/group, or **$0.5085**
at four 8192-token output limits and estimated input; no cache discount assumed.
Input estimate: 6,789 tokens including tokenizer/serialization overhead allowance.
Prices are $2.50/M input and $15/M output, checked 2026-10-26 in
[official OpenAI documentation](https://developers.openai.com/api/docs/models/gpt-5.4).
This is an estimate, not a billing cap or account-access test.

Stop on fingerprint mismatches; inspect and prepare a new reviewed pilot with new
paths. `prepare_agent2_pilot.py` supports explicit reviewed v6?v7 refreshes retaining
the original selection/model; it does not silently authorize changed inputs.
The historical A/B comparison launcher is gated off under v7.

## Offline validation and compatibility

```powershell
uv run --locked --extra dev python -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-taxonomy-v7
```

Use a dedicated pytest temporary directory, never an evidence directory. Historical
semantic tests explicitly select v6; v7 has separate structural/minimal-request tests.
Old schema classes remain importable; parsing/export/assembly dispatch by explicit
response version. Historical accepted v6 results replay unchanged. New callers must
not rely on old active `derive_severity`/inventory fields. The compatibility
`create_topic_task` now requires `payload=` to prevent arbitrary raw-group interpolation;
the supported execution route remains the strict batch runner.

The hidden-label catalog/fixture authoring checks are outside this refactor: no
evaluation labels are consumed for taxonomy. The full offline suite retains its
existing opaque preservation-hash checks. See the change report for actual results.

Current results: **294 Agent 2-related tests passed** (254 historical + 40 taxonomy).
The full suite in the workspace returned 569 passed / 1 Windows atomic-file-replace
error in an unchanged Agent 1 stress test. A full run in Windows' C: temporary
directory returned 568 passed / 2 legacy cross-drive reconciliation errors; that
stress test passed there. The two reconciliation tests passed again with D: output.
All 570 tests passed across these runs, but no single green full-suite run is claimed.
Keep historical reconciliation output on the evidence drive. See the report and
validation receipt for exact commands; Agent 1 was not changed for these issues.
