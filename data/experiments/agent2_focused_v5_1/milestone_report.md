# Agent 2 focused v5.1 correction and revalidation

Completed the authorized four-request experiment. **Broader validation remains on
hold** because the accepted alignment output still lacks sufficient evidence for
MEDIUM operational impact. Audio has a summary count error and unresolved question-
scope uncertainty. All original automated outcomes remain unchanged.

This is a **Codex-assisted source review, not human approval, independent ground
truth or an unbiased accuracy benchmark**. The four cases were deliberately selected
and repeatedly examined. No accuracy percentage is justified.

## Execution and preservation

- CONSOLIDATED **4**, FAILED **0**, INTERRUPTED **0**, unprocessed **0**.
- New request attempts **4**, saved HTTP/model responses **4**, unknown completions
  **0**. Every response is HTTP 200, normal `stop`, no refusal. One request per
  group; no automatic retries, repairs, fallback or extra verifier calls.
- Exact coverage: **12 unique full project/batch/channel/thread identities** and
  **32/32 original messages**. Member statuses: 4 VERIFIED, 6 CORRECTED, 2 NEEDS_REVIEW.
- Both inherited obligations retain the complete original Agent 1 record, disputed
  fields/reasons, source/candidate hashes, review evidence and lineage. Aggregate
  outputs equal per-group records; canonical review/member queues match exactly.
- The canonical dataset remains 200 records: 81 VERIFIED, 70 CORRECTED,
  49 NEEDS_REVIEW, in the existing 90 groups. No Agent 1 or grouping rerun occurred.
- Safety started first and was HIGH with a morning-review obligation. All three
  subsequent groups completed, demonstrating nonblocking HIGH handling in this run.
- All executed input/request hashes equal the prepared freeze. Provider model
  identity matches the requested snapshot. Frozen code hashes matched at the end
  of execution, before adding post-run review metadata. All raw requests, HTTP
  bodies, model drafts, outcomes, severity and historical artifacts are preserved.

Model: `openai/gpt-5.4-2026-03-05`; temperature 0; `reasoning_effort=none`;
`max_completion_tokens=8192`. Prompt `agent2-inventory-v5.1`; response/export schema
5; rubric `provisional-operational-severity-v1`. These are Arm B's frozen settings.
The strict schema hash, glossary and source inputs are unchanged. Only general
system instructions and the prompt version changed before the run; there are no
pilot answers, evaluation labels or prior review judgments in those instructions.

## Before/after source review

All rows compare the actual new candidate against original Slack roots/replies,
author roles, reaction users/targets, approved glossary and current rubric.

| Group ID / case | Members; messages; inherited obligations | Prior B → new processing | Severity before → after | Findings |
| --- | --- | --- | --- | --- |
| `cluster_06c08cf4143f2022` Safety announcement | 1; 2/2; 0 | CONSOLIDATED → CONSOLIDATED | MEDIUM → HIGH | E001 explicitly reports inability to complete labeled tasks across projects. Actual scope and unknown volume retained, no invented safety consequence. Announcement question remains null; E002 receipt diagnostic and confirmation condition retained. U013 tutor eyes is not endorsement. HIGH routes to review and later groups continue. No material issue found. |
| `cluster_6b59d13144282285` Audio | 6; 19/19; 2/2 | FAILED → CONSOLIDATED | UNASSESSED, mixed raw levels → HIGH | Two answer links now target substantive ANSWER items in their own conversations, with four other questions OPEN. Full conditional TL guidance, playback diagnostics and possible-workaround uncertainty retained. E015 supports affected-task blockage without invented cause/scope or harm. The differences sentence says **one** thread received guidance although M05/E015 and M06/E019 both did. M05's full ANSWERED status may overstate resolution of whether to Quarantine; useful reporting guidance does not explicitly settle that choice. Both inherited disputes and HIGH review remain. |
| `cluster_a6dfe8374217a497` Quarantine | 3; 7/7; 0 | CONSOLIDATED → CONSOLIDATED | MEDIUM → UNKNOWN | Benign school-context mention, on-its-own limit and independent-flags condition retained verbatim. Actual U006 TL agree on QA reply E002 derives TL_ENDORSED. M01 answered within that scope; M02/M03 OPEN. School/family context is not promoted to an answer; E007 remains diagnostic. QN means Quarantine. UNKNOWN is supported by missing operational-impact evidence. No material issue found. |
| `cluster_1ba596334ad5cde7` Alignment | 2; 4/4; 0 | CONSOLIDATED → CONSOLIDATED | MEDIUM → MEDIUM, disputed | Both precedence questions stay OPEN; pinned/archive wording request, version/date instruction and TL refusal to declare supersession retained. No precedence invented. MEDIUM still cites only document disagreement and clarification/verification requests, without establishing an operational consequence. E004 also remains an unlinked DIRECT ANSWER; existing diagnostics keep it provisional, but procedural guidance versus answer classification needs review. |

Audio's link-type/cross-member and mixed-severity validation failures are resolved
in this new response. This does not change the old FAILED outcome. The safety
announcement's missed HIGH routing is resolved. Quarantine no longer invents a
MEDIUM consequence. Alignment's evidence-sufficiency problem remains.

The audio count error is minor because both answers/members remain in the
inventory and export. M05's resolution is recorded as uncertainty: reporting the
incident could be read as an implicit handling answer, but the source never
explicitly settles Quarantine. M06's broader player-issue alternative makes its
ANSWERED reading more defensible. No automatic state edit was made.

Alignment's broad provisional MEDIUM criterion allows judgment, so this review
does not claim an incontrovertible ground-truth level. The output still fails to
explain meaningful operational impact beyond the clarification itself, despite
the revised instruction. UNKNOWN is defensible. That unresolved accepted-output
dispute is enough to withhold readiness for a broader experiment.

Two audio directive-cue diagnostics arise from root "should I QN" wording, not
missing TL instructions. Alignment has an unlinked-answer diagnostic. These are
nonblocking review cues; all four factual/severity validators returned VALID.
Mechanical validity is separate from these semantic findings.

## Effective review handoff

`review_supplement.json` binds each review to exact input, raw draft and exported
result hashes. Findings include exact affected raw/export fields and original
quotations with full identities, author roles and reactions. `reviewed_sources.json`
retains all original messages and source file/hash references.

The mandatory registry `docs/agent2-review-supplements.json` preserves its four
previous entries and adds this run. The existing effective loader applies **four
new content obligations across audio and alignment**, with **zero stale bindings**.
Automated review groups: **3**. Effective review groups: **3**. Inherited obligations:
**2**, unchanged. Safety/audio also keep their HIGH morning-review obligations.
Quarantine remains unflagged. Findings keep claims provisional without modifying
the original candidate, severity or automated CONSOLIDATED outcome.

Use `effective_output.json` in this experiment directory for the refreshed view;
the run directory's original effective snapshot predates the new review. A separate
fresh export can be generated with **zero model calls**:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_focused_v5_1 --output data/experiments/agent2_focused_v5_1/effective_refresh.json
```

## Validation and exact executed commands

Before spending: **68 focused tests passed**, followed by **492 passed, 0 failed,
0 skipped** in the complete offline suite (162 warnings; 225.44 seconds). The
regressions cover wrong-type/cross-conversation links, diagnostics alongside valid
partial answers, blockage with unknown cause/extent, consistent controlling
severity, UNKNOWN when impact is insufficient, and actual outgoing instructions.
Catalog and Slack-fixture checks passed for 200 identities, 12 channels and 316
replies; `git diff --check` passed. Mocked tests establish behavior, not live accuracy.

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent2_focused_revision.py tests/test_agent2_ab_review.py tests/test_agent2_structured.py -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-focused-v5-1-final --junitxml .cache/agent2_focused_v5_1/focused-final.xml
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-focused-v5-1-full --junitxml .cache/agent2_focused_v5_1/full.xml
```

Historical execution command below already consumed the four authorized requests;
**do not rerun it** or bypass the changed review-registry fingerprint:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
.venv\Scripts\python.exe -u -X utf8 scripts/run_agent2_batch.py --run --pilot docs/agent2-focused-pilot-v5-1.json --max-requests 4 --output-dir data/processed/agent2_focused_v5_1
```

Post-execution offline audit passed exact request/model/schema checks, normal HTTP
completion, all source/member accounting, answer-link type/scope, aggregate/record/
queue equality, complete inherited metadata, independent validation replay equality
and unchanged execution files. The new effective-review loader checks passed for
all four findings and both inherited obligations. No response was repaired or
reclassified by replay; all original automated outcomes already were CONSOLIDATED.

## Readiness and limits

**Hold broader validation.** The conditional eight-group selection/command was not
prepared or executed. The next focused work should resolve the evidence-sufficiency
boundary: procedural clarification alone is not established operational impact,
and useful reporting guidance may leave part of a handling question unanswered.
No further prompt edit, code correction loop, new verifier or request was made.

The sample does not test N/A/social content, multilingual behavior or live refusal,
transport failure and interruption handling. Coverage alone does not establish
semantic completeness. Severity remains provisional and revisable by Agent 3;
downstream consumers must retain inherited, assisted-content and HIGH obligations.
No Agent 3, RAG or dashboard work was implemented.

Artifacts: `freeze.json`, `freeze_receipt.json`, `prompt-v5.1.txt`,
`offline_validation.json`, test XML, `execution_audit.json`, `reviewed_sources.json`,
`review_supplement.json`, `effective_output.json`, `readiness.json`, and
`milestone_report.json` in this directory. Canonical outputs, manifest, request
ledgers and raw responses: `data/processed/agent2_focused_v5_1/`.
