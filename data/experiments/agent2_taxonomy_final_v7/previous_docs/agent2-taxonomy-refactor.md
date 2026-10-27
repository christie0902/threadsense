# Agent 2 taxonomy v7 — offline change report

**Decision:** the corrected implementation and offline preparation are complete.
No paid calls were made. Live taxonomy quality remains unverified; historical v6
readiness does not validate this scope. No Agent 1 regeneration, grouping change,
model/dependency change, Agent 3 implementation or historical response rewrite occurred.

| Responsibility | Historical v6 | Active v7 |
| --- | --- | --- |
| Model input | Raw-source evidence catalog and semantic instructions | Canonical Agent 1 summary/question, stable member ID, project/batch and glossary |
| Model output | Inventory, synthesized issues, answers, resolution/confidence and impact proposals | Named topics, brief membership rationales, assigned IDs and group-level rejected IDs |
| Validation | Evidence, authority, answer/coverage, uncertainty and severity rules | Exact disjoint partition, nonempty topics/names/rationales, project/batch and copied-data integrity |
| Export | Semantic inventory/research narrative plus sources | Passive assignments plus complete canonical records, sources, lineage and obligations |
| Severity | Model-proposed impact, independently validated | Deterministic post-export UNKNOWN when canonical impact signals are absent |

## Changed files and retained infrastructure

- `topic_taxonomy.py` implements the small request projection, short RULES, partition
  validation and passive export. `topic_contracts.py` adds `TaxonomyTopic` and
  `TopicTaxonomy` without redefining legacy classes.
- `topic_consolidation.py` dispatches explicitly by response version; isolated
  `topic_consolidation_v6.py` retains the prior parser/validators/export and pins its
  strict request schema to v6. v2–v5 compatibility remains available. All 88 accepted
  saved final-v6 outputs replay exactly under their original contract.
- `topic_requests.py` selects the v7 strict provider schema; model parameters and
  one-POST/no-SDK-retry transport remain unchanged. `topic_pipeline.py` retains the
  runner/failure/evidence machinery and reports taxonomy validity/dispositions.
- `topic_effective.py` adds passive `taxonomy_handoff`, retaining the mandatory
  review registry and exact hash-binding checks. Old `research_handoff` remains
  available only for historical exports. Stale old-output findings do not migrate.
- `severity.py` retains the legacy enum/rubric and attaches a separate deterministic
  assessment with input provenance. No canonical operational-impact fields exist,
  so the actual dataset yields UNKNOWN/UNASSESSED, never inferred LOW or N/A.
  HIGH nonblocking routing remains covered by synthetic already-assessed test data;
  this is not evidence of real HIGH detection. All levels retain inherited flags.
- `topic_analyst.py` aligns the compatibility factory; `create_topic_task` now requires
  a canonical `payload=` and applies the same minimal projection. The supported
  runner remains the strict transport. `topic_comparison.py` gates off the historical
  semantic A/B launcher under v7.
- `run_agent2_batch.py` / `run_agent2_sample.py` use fresh v7 defaults.
  `prepare_agent2_pilot.py` permits an explicit reviewed v6→v7 contract transition;
  `assemble_agent2_dataset.py` uses producer-version dispatch.
- `tests/test_agent2_taxonomy.py` supplies 40 active-contract checks. `tests/conftest.py`
  and `tests/legacy_agent2.py` provide opt-in v6 runner bindings for historical tests.
  The 13 semantic test modules now explicitly select/import v6; the preparation
  tests use the active version. Historical assertions and raw responses are retained.
- README and the [operational guide](agent2-offline-integration.md) identify current
  scope, artifacts and compatibility changes. This is the single current change report.
  The full file list and preservation hashes are in the experiment receipts below.

The canonical loader, approved grouping, passive evidence-resolution utilities,
diagnostics, recoverable failure continuation and request accounting were retained.
No extra interpretation, self-check, repair, verifier or regrouping call was added.
Imports/references were checked before cleanup: historical modules remain referenced
by replay/tests; no historical files or unique evidence were deleted. Two unused
imports were removed. Temporary test outputs remain isolated under `.cache/`.

## Request, response and passive export

The [exact prepared social request](../data/processed/agent2_taxonomy_pilot_v7_prepared/records/cluster_be4e3bac742eccb3/request.json)
contains the current strict schema and this canonical member projection:

```json
{
  "member_id": "member_a797fa3de3e75b654a60160a",
  "summary": "The thread consists of friendly greetings for 'language-day Friday' from Linh and Bea, with no substantive questions or issues raised.",
  "central_question": null
}
```

The request also contains project `multilingual_eval`, batch `multi_batch_11`, the
candidate ID and approved runtime glossary. It contains no original transcript,
reaction inventory, review judgment, severity rubric or evaluation label. A
**synthetic illustration**, not a generated response, of the new response shape is:

```json
{
  "topics": [{
    "topic_name": "Team appreciation",
    "rationale": "This member is a social greeting.",
    "member_ids": ["member_a797fa3de3e75b654a60160a"]
  }],
  "rejected_member_ids": []
}
```

The [representative synthetic passive export](../data/experiments/agent2_taxonomy_v7/synthetic_exports/records/cluster_b3bfce178039d7d4/result.json)
retains both complete canonical announcement members, their source messages,
identities, hashes and lineage, plus the existing obligation on
`member_79e604ff554222eab0ad146a`. Its synthetic topic references those stable IDs,
has `review_required=true`, and gets deterministic UNKNOWN severity. Neither its
canonical candidate nor its disputed question is silently corrected or cleared.
The full objects are copied, not generated. Rejected IDs and failed/unassigned IDs
remain in the same member list and in explicit `member_dispositions`.

## Accounting and checks

The zero-call CLI preflight confirmed **90 groups / 200 unique full identities /
49 inherited obligations**: 81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW. The complete
pending preview has 90 NOT_RUN groups and all 200 members explicitly UNASSIGNED.

The clearly labeled synthetic export deliberately includes one invalid partition
and one all-rejected group. It produces 89 CONSOLIDATED / 1 FAILED, zero pending,
**189 assigned + 5 rejected + 6 unassigned = 200**. Its obligations are
**46 assigned + 1 rejected + 2 unassigned = 49**. All original canonical records,
metadata and source/candidate lineage compare equal. These numbers exercise
integration behavior, not model grouping quality. There are zero call markers,
provider responses or unknown completions in the new prepared/synthetic artifacts.

Actual test results (exact commands and JUnit receipts in
[validation.json](../data/experiments/agent2_taxonomy_v7/validation.json)):

| Check | Result |
| --- | --- |
| Historical Agent 2 migration tests | 254 passed, 0 failed |
| New active taxonomy tests | 40 passed, 0 failed |
| Complete suite, workspace temporary directory (final 570-test collection) | 569 passed, 1 failed, 164 warnings |
| Complete suite, Windows temporary directory on C: | 568 passed, 2 failed, 164 warnings |
| Isolated unchanged Agent 1 stress test, fresh directory | 1 passed |
| Two unchanged reconciliation tests rerun on D: | 2 passed |

**All 294 Agent 2-related checks pass. There was no single entirely green full-suite
run.** Every one of the 570 unique tests passed across the complete runs, without
skips or weakened assertions. The workspace failure was `WinError 5` during atomic
file replacement in the unchanged Agent 1 200-record stress test; it reproduced on
two different temporary report files. That test passed alone and in Windows' temporary
directory. The external locking cause remains unconfirmed. Moving temporary output
to C: exposed a separate pre-existing Agent 1 limitation: `os.path.relpath` cannot
reference D: evidence from C: output. Both affected reconciliation tests passed on
D:. Agent 1 code was preserved; these Windows suite limitations remain documented,
not hidden by retries inside production code or by disabling tests.

Coverage includes all partition cases/invalid IDs, raw-source/semantic-field exclusion
on the actual captured HTTP body, strict schema, one attempt per group, refusal/
incompletion/unknown completion retention, recoverable failure continuation, all
200 records/49 flags, deterministic severity, historical replay, stale review
isolation, minimized compatibility tasks and explicit pilot contract refresh.

The full offline suite retains existing opaque preservation-hash checks. We did
not consume hidden evaluation labels or rerun the separate hidden-label dataset
authoring validators, which are outside this taxonomy task. Historical data, Agent 1,
grouping, glossary, dependencies, local configuration and reviews are covered by the
[preservation receipt](../data/experiments/agent2_taxonomy_v7/preservation.json).

## Prepared next step and downstream artifacts

The [four-group selection](agent2-taxonomy-pilot-v7.json) covers related speaker
overlap, distinct announcements (split/outlier opportunity), flagged playback/silence
and a social singleton: **11 identities / three inherited obligations**. Selection
uses canonical summaries, with notes outside model requests. The
[freeze](../data/experiments/agent2_taxonomy_v7/freeze.json) records code/input/request
hashes, unchanged GPT-5.4 snapshot/low reasoning/8192-token configuration, new prompt
and schema, and zero retries/repairs/verifiers. Four attempts is the exact future bound.

No execution is authorized by this report. The [guide](agent2-offline-integration.md)
contains exact dry-run and future live commands, fresh destination, cost calculation
and source. Estimated cost is $0.077 for 1,000 completion tokens/group or $0.5085 at
all four output limits, including estimated input and no cache discount. These are
approximate standard USD costs using [official pricing](https://developers.openai.com/api/docs/models/gpt-5.4).

For a later Agent 3 discussion, use the canonical Agent 1 input, unchanged grouping,
and `data/processed/agent2_taxonomy_v7_offline/effective_output.json` as a **pending
contract preview**. The per-record `taxonomy_handoff` carries assignments, canonical
records, dispositions and obligations. Synthetic exports demonstrate wiring only;
there is no live v7 taxonomy dataset yet. Retain flagged/rejected/failed members even
without a question, topic or recommendation. The bounded pilot is the next proposed
validation step, not semantic readiness or authorization for a broader run.
