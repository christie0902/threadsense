# Agent 2 v5.3 contrastive diagnostic — 2026-10-25

**Experiment completed; the main Audio scope error remains. Hold broader validation.**
Three authorized requests yielded **3 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED**;
three saved responses, zero unknown completions and zero unprocessed groups.
All **14 unique identities, 42 original messages and five inherited obligations**
are preserved. There were no retries, repairs, fallback calls, extra verifiers or
reasoning escalation. No eight-group validation was prepared or executed.

This is a **Codex-assisted source review**, not human approval, independent ground
truth or an accuracy benchmark. The controls were selected for diagnostic content
before execution, not sampled to estimate accuracy. Low reasoning remains a
configuration under evaluation, not a proven production winner.

The only production change is prompt `agent2-inventory-v5.2` →
`agent2-inventory-v5.3`, adding one compact synthetic contrast. The same instruction
to send a task ID and screenshot to tool support answers a reporting-location
question but leaves submission eligibility undecided. Existing inventory fields
illustrate both cases. The prompt briefly clarifies substantive PARTIAL answers,
complete ANSWERED scope, indirect unambiguous answers, and why guidance or authority
alone is insufficient. The synthetic `SYNTH_*` references are clearly excluded from
actual evidence; the real validator rejects their use as citations or answer links.

The model remains `openai/gpt-5.4-2026-03-05`, low reasoning, no temperature/top_p/
logprobs, and an 8,192-token shared reasoning/output limit. Rubric
`provisional-operational-severity-v2`, strict schema 5, glossary, inventory/export
semantics, factual/severity validators and provider adapter are unchanged. Removing
the new block and reverting the version reconstructs the exact previous production
file bytes. No production change occurred during or after the live run.

The canonical dataset remains **200 records in 90 groups**: 81 VERIFIED, 70 CORRECTED,
49 NEEDS_REVIEW. The selected members are 2 VERIFIED, 7 CORRECTED, 5 NEEDS_REVIEW.
Both controls are outside the original six repeatedly examined groups. Selection
used permitted original messages, replies and reactions, without hidden evaluation
labels or historical Agent 2 outputs for those controls. Exact identities and
pre-execution criteria are saved in the [pilot](../../../docs/agent2-contrastive-pilot-v5-3.json)
and [pre-run review](pre_run_review.json). Neutral case IDs are used in preparation;
control roles and evaluation judgments never enter runtime requests. Existing
Agent 1 reliability/flag/disputed-field metadata remains unchanged.

| Group | Coverage / inherited flags | Automated result | Assisted source-review result | Severity |
| --- | --- | --- | --- | --- |
| Audio `cluster_6b59d13144282285` | 6 members / 19 messages / 2 flags | CONSOLIDATED, factual/severity validation VALID | M05 still fully ANSWERED without deciding Quarantine. M06 playback handling assessed separately; all scoped guidance preserved. Diagnostic-only summary citations need scope caution. | Silence UNKNOWN, playback HIGH; both supported, HIGH nonblocking review retained. |
| Complete-answer control `cluster_f944891544b06f79` | 5 / 13 / 2 | CONSOLIDATED, factual/severity validation VALID | Target succeeds: M02's tie decision remains ANSWERED with its local conditions and TL endorsement. Separate E002 context-as-TENTATIVE-ANSWER error remains; M01 broad threshold versus local example is uncertain. | UNKNOWN supported; no invented rework, blockage or quality harm. |
| Procedural control `cluster_1f272d7fa384df0c` | 3 / 10 / 1 | CONSOLIDATED, factual/severity validation VALID | Target succeeds: M02 category decision OPEN, useful procedure retained. Announcement has null root question and no-final-decision condition. No material issue found in this assisted review. | UNKNOWN supported; safety vocabulary and an announcement do not establish impact or N/A. |

**Material findings and scope limitations.**

- Audio M05 E014 (`1790920171.000109`) asks “Player never loads, should I QN?”
  E015 (`1790920220.000113`) says the affected task cannot be evaluated, directs
  reporting with task ID and says not to mark a model-quality failure. It never
  decides Quarantine eligibility or makes reporting and Quarantine mutually
  exclusive. `topics[1].inventory[9]` / I10 still says ANSWERED through I11, excluding
  M05 from `open_questions`. This repeats the historical v5.2-low failure.
- Audio M06 asks “QN or a player issue?” Its E019 reply more directly answers
  playback-incident handling. That substantive answer should remain recognized;
  it must not become a general Quarantine prohibition or confirmed cause. This is
  recorded as a separate uncertainty, not a second demonstrated closure error.
- Audio's “some threads only receive” diagnostics difference cites E017/E018 from
  M06, which also has E019 handling guidance. M02/M03 support the general statement,
  but the extra citations blur the exclusive scope. This is retained as citation-scope
  uncertainty rather than an assertion that all cited threads lack answers.
- In the complete-answer control, E002 (`1790896559.000113`) describes nicer wording
  with identical information/coverage. It supplies task context, not a threshold
  decision or tentative handling advice. I02 nevertheless marks it ANSWER/TENTATIVE;
  it appears in provisional answers. E003 supplies the actual scoped TL judgment.
  The automatic unlinked-answer warning mitigates exposure but does not validate
  that semantic classification. This is the second material finding.
- The same control's M01 asks how much improvement avoids a tie. E003 supplies
  a qualitative cosmetic-versus-meaningful distinction and a tie for this example,
  with the exact-user-task condition. Contextual completion is defensible, but a
  general or numeric threshold is not established. This uncertainty was anticipated
  in the frozen criteria; no predetermined OPEN/PARTIAL replacement is imposed.

The positive target M02 E004 (`1790931693.000046`) asks tie or preference. E005
explicitly says choose a tie for this example, with an actual U001 TEAM_LEAD `agree`
reaction. It remains ANSWERED. E011 `this` and E013 `white_check_mark` endorsements
also retain their original reply targets and scope. Tutor reactions are not promoted
to TL authority. Thus this run did not solve closure errors by making every question
OPEN, although the additional context classification defect prevents a clean result.

The procedural target M02 E004 (`1790889905.000065`) asks which safety category
applies. E005/E006 require inspecting actual output and distinguishing override
language before choosing a category; no category is selected. That decision stays
OPEN. M03's automatic-keyword question admits a procedural substantive component,
but final handling is still undetermined; the full question and useful guidance
remain visible without imposing a unique replacement status. M01's collection
announcement remains ANNOUNCEMENT + INSTRUCTION with null question; the exported
representative question comes from an actual task question, not invented announcement
content. Its inherited dispute remains intact.

All 42 messages are inventoried with no omissions or filler dispositions. Audio
retains intended-silence/other-playback checks, reproduction-before-old-workaround
guidance, the conditional both-task-ID instruction, and reporting/do-not-score
conditions. No attempted/failed historical workaround, policy precedence, cause
or unsupported queue-wide operational consequence is asserted. The tie group keeps
calibration-before-threshold-change and comparable-pair caveats. Both controls retain
all source roles and reactions. No `eyes` case occurs in this live selection.

Independent severity remains supported: Audio E015/E019 expressly report inability
to evaluate affected tasks, supporting HIGH at that scope; the other topics lack
sufficient impact evidence and retain UNKNOWN. Flags, task-labeling vocabulary and
open questions do not set severity. Agent 3 may later revise these provisional
assessments after research; it was not implemented here.

**The contract is adequate for these concrete failures.** It already permits an
OPEN question with separate INSTRUCTION/DIAGNOSTIC_REQUEST items, real partial
answers with links, scoped complete answers and FACT/CONTEXT. The negative control
demonstrates unresolved decisions plus retained guidance, and the positive target
demonstrates complete-answer retention. M05's full closure and E002's answer tag
are failures to apply those distinctions, not missing schema capabilities. There is
no dedicated residual-subquestion text field, so detailed PARTIAL scope depends on
the original question and synthesis/differences; that limitation does not justify
ANSWERED M05. No new schema, second pass or automatic relabeling was added.

Mechanical checks verify exact frozen HTTP requests, source-file equality, all
full identities, per-group/aggregate equality and both queues. All complete member
records and inherited obligations match preparation, including evidence, effective
and automated Agent 1 statuses, candidate/source hashes and lineage. All three
responses are HTTP 200, return the requested snapshot and finish `stop`, without
refusal or truncation. No started-without-call markers remain.

| Case | Input | Output including reasoning | Reasoning | Cached input | Latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Audio | 6,674 | 1,863 | 390 | 0 | 20.92s |
| Complete-answer control | 5,803 | 2,153 | 1,200 | 0 | 26.84s |
| Procedural control | 5,052 | 1,744 | 991 | 0 | 23.40s |
| Total | 17,529 | 5,760 | 2,581 | 0 | 71.16s |

Output already includes reasoning; total usage is 23,289 tokens. Non-reasoning output
is 3,179 tokens. Historical Audio v5.2-low used 6,303 input / 2,418 output, including
748 reasoning tokens, in 26.37s. The new prompt adds 371 measured input tokens for
Audio, but the main semantic result is unchanged. There is no historical v5.2-low
comparison run for these controls, and no baseline request was rerun. One observation
per case does not establish latency, accuracy or causal gains.

The preflight budget estimate was **$0.4281025** at all three output caps, using
local tokenization plus input-framing allowance and no cache discount. Returned
usage estimates **$0.1302225** at the checked standard rates of $2.50 input and
$15 output per million tokens. These are estimates, not billing receipts.
[Pricing source](https://developers.openai.com/api/docs/models/gpt-5.4);
[frozen estimate](cost_estimate.json).

**Checks:** 57 focused tests passed; **514 passed, 0 failed, 0 skipped** in the full
suite (162 warnings, 238.83s). Catalog and Slack-fixture checks passed for all 200
identities; `git diff --check` passed. Exact test commands:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent2_contrastive_scope.py tests/test_agent2_reasoning_configuration.py tests/test_agent2_structured.py tests/test_agent2_impact_scope.py -q --tb=short --basetemp .cache/pytest-contrastive-focused --junitxml .cache/agent2_contrastive_v5_3/focused-tests.xml
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-contrastive-full --junitxml .cache/agent2_contrastive_v5_3/full-tests.xml
.venv\Scripts\python.exe -X utf8 scripts/validate_topic_catalog.py
.venv\Scripts\python.exe -X utf8 scripts/validate_slack_fixtures.py
git diff --check
```

The existing tiktoken installation needed its public vocabulary downloaded into
the workspace cache for offline estimation. No dependency or model request was
involved. Preparation and tests made zero paid requests. Executed commands below
are historical receipts, **not instructions to rerun the completed pilot**:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
$env:THREADSENSE_AGENT2_REASONING_EFFORT = 'low'
.venv\Scripts\python.exe -X utf8 scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-contrastive-pilot-v5-3.json --max-requests 3 --output-dir data/processed/agent2_contrastive_v5_3
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-contrastive-pilot-v5-3.json --max-requests 3 --output-dir data/processed/agent2_contrastive_v5_3
```

Changes: `topic_consolidation.py` only adds the prompt block and version;
`test_agent2_contrastive_scope.py` adds four request/citation regressions;
`test_agent2_reasoning_configuration.py` continues testing the exact historical
v5.2 adapter requests while separately checking current source/schema equality.
README and the maintained guide report the result. The review registry appends
this experiment while preserving its seven prior entries. New prepared/run/experiment
files retain the selection, freezes and evidence. Agent 1, grouping, dependencies,
`.env`, source data, prior outputs and prior freezes remain unchanged.

Artifacts:

- [Freeze](freeze.json), [offline checks](offline_validation.json), [ledger](request_ledger.json), [mechanical audit](execution_audit.json).
- [Original source evidence](reviewed_sources.json), [source-file bindings](source_file_bindings.json), [new review supplement](review_supplement.json).
- [Canonical output](../../processed/agent2_contrastive_v5_3/consolidations.json), [manifest](../../processed/agent2_contrastive_v5_3/manifest.json), [automated review queue](../../processed/agent2_contrastive_v5_3/review_queue.json), [member queue](../../processed/agent2_contrastive_v5_3/member_review_queue.json).
- [Refreshed effective output/queue](effective_output.json), [effective checks](effective_review_check.json), [readiness](readiness.json), [mandatory registry](../../../docs/agent2-review-supplements.json).

The effective loader applies **two material findings and three scope uncertainties**
with zero stale bindings. All three groups remain available, with all five inherited
obligations and HIGH review intact. M05's unresolved Quarantine question is exposed
in its evidence-bound obligation even though the unchanged original output says
ANSWERED. Existing group-level review conservatively makes disputed topics provisional;
it does not delete records or require approval to continue nonblocking processing.
The original run-local effective snapshot is preserved; downstream consumers should
use the maintained loader or the refreshed experiment view.

**Stop here.** The focused contrast did not remove the main blocker, and an additional
context-as-answer error remains. Keep broader validation on hold and use the saved
failures for separately authorized offline diagnosis before choosing another
intervention. No further prompt/call loop, automatic reasoning increase or eight-group
preparation occurred. Multilingual, non-operational, `eyes`, and failure/interruption
behavior remain untested by this live sample.
