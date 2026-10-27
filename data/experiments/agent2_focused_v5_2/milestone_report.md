# Agent 2 v5.2 bounded impact/scope correction and revalidation

The authorized two-request milestone is complete. **Broader validation remains on
hold.** Severity evidence and the audio summary count improved, but the new audio
output still overstates full question resolution and alignment still tags procedural
guidance as an answer. No additional correction or call followed the run.

This is a **Codex-assisted source review**, not human approval, independent ground
truth or an unbiased accuracy benchmark. These repeatedly examined cases are
regression checks. Valid schema/evidence IDs alone cannot establish semantic support.

## Changes made before execution

- `src/threadsense/agents/topic_consolidation.py`: prompt `agent2-inventory-v5.2`
  requires an evidenced consequence or risk mechanism and criterion explanation in
  existing impact observations, complete-question coverage for ANSWERED, and a
  distinction between useful procedure and substantive resolution. Same-thread
  ANSWER links remain strict. Generated synthesis/differences should omit unnecessary
  exact guidance counts; Python adds distinct-member `inventory_counts` in export
  adapter `inventory-to-display-v3`. No response repair or semantic validator shortcut.
- `src/threadsense/agents/operational_severity.py`: explicit rubric v2, changing only
  the MEDIUM definition. Clarification/coordination must concern an established
  consequence or source-supported prospective risk. Harm need not already have
  occurred. All v1 objects remain available and unchanged for historical decoding;
  HIGH, LOW, UNKNOWN, N/A and criterion IDs retain their definitions/levels.
- `src/threadsense/agents/topic_pipeline.py` and `topic_comparison.py`: record active
  rubric/export versions instead of mislabeling future freezes with a fixed v1.
- `scripts/prepare_agent2_pilot.py`: an explicitly authorized legacy v3/v4-to-v5
  contract migration records and permits the new version metadata. The ordinary
  code-refresh path still rejects non-code changes; source/model/budget checks remain.
- `tests/test_agent2_impact_scope.py`: ten focused synthetic/wire tests cover missing
  impact versus reported consequences, prospective risk, known blockage with unknown
  extent, OPEN reporting guidance, PARTIAL and genuinely complete endorsed answers,
  and counts with several roles/messages from the same member. Existing A/B and
  v5.1 checks distinguish new metadata from historical semantics; historical responses
  and outcomes remain unchanged. The legacy migration test covers the metadata fix.
- Current run guide, README and mandatory review registry updated. New pilot,
  preparation, freeze, execution and assisted-review artifacts use fresh paths.

No Agent 1, grouping, dependency, model, strict Structured Outputs schema, independent
factual/severity validation, effective-loader logic or retry behavior changed.
There were no production changes during or after live execution.

## Exact scope and execution

Order: Alignment `cluster_1ba596334ad5cde7`, then Audio `cluster_6b59d13144282285`.
Model `openai/gpt-5.4-2026-03-05`; temperature 0; reasoning effort `none`;
`max_completion_tokens=8192`. Response schema 5. The same settings and provider
schema as frozen Arm B were used. Semantic-input changes were only the shared
general system instructions and explicitly versioned MEDIUM rubric clarification.
No pilot answers, prior findings or evaluation labels entered requests.

| Measure | Actual result |
| --- | --- |
| Processing | 2 CONSOLIDATED; 0 FAILED; 0 INTERRUPTED; 0 unprocessed |
| Requests | 2 attempts; 2 saved HTTP/model responses; 0 unknown completions |
| Provider completion | Both HTTP 200, `stop`, no refusal or partial response; requested/returned model snapshots match |
| Coverage | 8 unique full identities; 23/23 original messages |
| Member statuses | 2 VERIFIED; 4 CORRECTED; 2 NEEDS_REVIEW |
| Inherited obligations | 2/2, with exact complete Agent 1 records, hashes, evidence and lineage |
| Review groups | Automated 2; effective 2; 2 new content obligations; 0 stale findings |
| Tokens | 10,010 input; 1,586 output; 11,596 total; cached input 0; reasoning 0 |
| Recorded latency | Alignment 6.91 s; Audio 9.73 s; mean 8.32 s |
| Extra requests | 0 retries, repairs, fallbacks or extra model verifiers |

Input/candidate hashes, request hashes, code fingerprints, model/schema/settings,
aggregate/per-record equality, review queues, source links and all member metadata
passed the post-run audit. The current canonical dataset remains 200 records
(81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW) in 90 groups. All original executed
files remain unchanged after source review. Final file-preservation counts are in
`milestone_report.json`.

## Before/after assisted source review

| Case | v5.1 → v5.2 automated outcome | Severity and summary | Remaining source finding |
| --- | --- | --- | --- |
| Alignment: 2 members, 4 messages, 0 inherited obligations | CONSOLIDATED → CONSOLIDATED | MEDIUM → UNKNOWN with supported insufficient-impact rationale. Both questions OPEN, exact diagnostic and conditional instruction retained. | E004 asks for both versions/dates and withholds a supersession decision. It remains tagged INSTRUCTION **and unlinked DIRECT ANSWER I007**. This is procedure/status, not an answer to which guidance supersedes which. Existing warnings keep it provisional; new review records the incorrect answer classification and derived answer count. |
| Audio: 6 members, 19 messages, 2 inherited obligations | CONSOLIDATED → CONSOLIDATED | Supported HIGH retained. Wrong one-thread contrast removed; export correctly counts two distinct members with ANSWER items and six with guidance, despite repeated items. | M05/E014 explicitly asks whether to Quarantine. Linked E015 gives reporting/do-not-score guidance without settling Quarantine eligibility or saying reporting replaces Quarantine. **ANSWERED I016** still removes this unresolved decision from open_questions. Useful guidance and a valid link do not establish complete resolution. |

Audio's M06 asks a broader Quarantine-versus-player-issue alternative, so the scoped
playback-incident reply is a more defensible answer. This review does not require
both conversations to receive the same label. For M05, OPEN or PARTIAL could be
defensible depending on which substantive component is considered answered; the
finding concerns unsupported full settlement, not a predetermined replacement.
No saved status or response was edited.

Both outputs retain all original messages and members. Audio preserves the E007
condition to keep both task references if another clip plays, E010 reproduction/
waveform checks, and E015/E019 incident-reporting and do-not-mark-model-quality
guidance. No attempted/failed workaround, broader cause, operational harm or policy
precedence was invented. QN remains Quarantine. U018's audio thumbsup is a tutor's
reaction, not TL endorsement; actual U006 TL guidance retains its original scope.

Alignment UNKNOWN follows the absence of concrete operational impact. Audio HIGH
uses explicit reported inability to evaluate, with scope supported by E015/E019;
unknown wider extent does not erase that blockage. Its morning-review obligation
remains nonblocking. Review flags did not determine either severity.

The residual common cause is **confusing a useful procedural response with a
substantive answer or full settlement of the question**. Deterministic counting is
correct for the inventory but cannot prove that the inventory's roles are correct.
The primary audio defect can hide an unresolved decision; the alignment tag can
mislead answer-oriented consumers despite its provisional flag. These are semantic
findings, separate from both responses' automated VALID/CONSOLIDATED outcomes.

## Evidence and effective handoff

`review_supplement.json` contains both findings, exact affected raw/export fields,
original quotations/identities/author roles/reactions and exact input/raw/output
hash bindings. `reviewed_sources.json` retains all 23 original messages;
`source_file_bindings.json` adds actual source file hashes. Prior assisted findings
were rechecked, not transplanted; historical hashes cannot bind to new candidates.

The mandatory registry preserves all five previous supplements and adds this run.
The unchanged effective loader exposes both new findings, both inherited obligations
and the HIGH obligation, without clearing or rewriting candidates/statuses. There
are no stale bindings. Use this directory's `effective_output.json`, or call the
loader; the original run-local effective snapshot intentionally predates this review.

Safe fresh export, **zero model calls**:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_focused_v5_2 --output data/experiments/agent2_focused_v5_2/effective_refresh.json
```

## Offline checks and exact commands

Final focused suite: **136 passed**. Final full suite: **502 passed, 0 failed,
0 skipped**, 162 warnings, 227.32 seconds. Catalog and Slack-fixture validation
passed: 200 identities, 12 channels, 316 replies; `git diff --check` passed.

The first full run had 501 passes and one failure in explicit legacy contract
preparation because the new version metadata was outside its migration whitelist.
The narrow fix above was applied and both focused and full checks passed before
either paid request. The frozen runtime requests/code stayed unchanged during this
preparation-utility fix; its final hash is recorded in `offline_validation.json`.
Tests validate implementation behavior, not model semantic accuracy.

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent2_impact_scope.py tests/test_agent2_focused_revision.py tests/test_agent2_ab_review.py tests/test_agent2_structured.py tests/test_agent2_inventory.py tests/test_agent2_pilot_preparation.py -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-impact-scope-final2 --junitxml .cache/agent2_focused_v5_2/focused-final.xml
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-impact-scope-full-final --junitxml .cache/agent2_focused_v5_2/full-final.xml
.venv\Scripts\python.exe -X utf8 scripts/validate_topic_catalog.py
.venv\Scripts\python.exe -X utf8 scripts/validate_slack_fixtures.py
git diff --check
```

The following live command has **already executed and consumed all two authorized
attempts**. It is an execution record, not a recommendation to rerun:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
.venv\Scripts\python.exe -u -X utf8 scripts/run_agent2_batch.py --run --pilot docs/agent2-focused-pilot-v5-2.json --max-requests 2 --output-dir data/processed/agent2_focused_v5_2
```

## Readiness and limits

**Hold broader validation.** The condition for preparing the outside-sample
eight-group validation did not pass, so no eight-group pilot, live command, freeze
or cost estimate was prepared and no broader run occurred. No further correction
loop or paid request is authorized by this completed milestone. The next action is
to resolve these evidence-bound question-scope findings before another experiment.

This run does not establish behavior on multilingual or non-operational material,
announcements, new projects or live refusal/interruption/transport failures. The
rubric and this assisted review remain provisional. Agent 3 may later research and
revise severity while preserving lineage and every review obligation. Agent 3, RAG
and dashboard implementation remain outside scope.

Artifacts are in this directory: `freeze.json`, `freeze_receipt.json`, `prompt-v5.2.txt`,
`offline_validation.json`, test XML, `pre_run_review.json`, `execution_audit.json`,
`reviewed_sources.json`, `source_file_bindings.json`, `review_supplement.json`,
`effective_output.json`, `readiness.json` and `milestone_report.json`. Executed
records/manifest/queues/ledgers/raw responses are in
`data/processed/agent2_focused_v5_2/`; preparation is in its `_prepared` sibling.
