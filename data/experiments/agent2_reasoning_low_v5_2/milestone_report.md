# Agent 2 v5.2 low-reasoning regression experiment — 2026-10-25

**Completed within the two-request budget; hold broader validation.** Alignment's
procedural-answer classification improved. Audio M05 still overstates complete
Quarantine resolution. No eight-group validation was prepared or executed, and no
further prompt change, reasoning increase or call followed these results.

This is a **Codex-assisted source review**, not human approval, independent ground
truth or an accuracy benchmark. Two repeatedly examined groups and one response
per case cannot establish a causal effect. The comparison uses historical v5.2
responses, and enabling low reasoning also requires temperature omission.

The snapshot stayed `openai/gpt-5.4-2026-03-05`, prompt
`agent2-inventory-v5.2`, rubric `provisional-operational-severity-v2`, schema 5,
export adapter `inventory-to-display-v3`. Glossary, source inputs, strict schema,
messages, validators, export semantics, grouping and Agent 1 were unchanged.
Every actual request equals its historical request after only changing
`reasoning_effort` from `none` to `low` and removing `temperature: 0`. `top_p` and
`logprobs` are absent. The single-POST transport adds no defaults or SDK retries.
The compatibility requirement is documented in the
[GPT-5.4 parameter guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.4#gpt-54-parameter-compatibility).

`max_completion_tokens=8192` remains unchanged and includes reasoning and visible
output. The offline length-response regression confirms that truncation stays
FAILED, with raw evidence and no retry. Neither live response was truncated.

| Group | Historical none → low processing | Coverage and source review | Severity and review |
| --- | --- | --- | --- |
| Alignment `cluster_1ba596334ad5cde7` | CONSOLIDATED → CONSOLIDATED; no new validation failure | 2/2 members, 4/4 messages. Both precedence questions OPEN. E004's version/date request and withheld decision now INSTRUCTION + FACT, with zero ANSWER items. Exact condition and diagnostic E003 retained. No material issue found in this assisted review. | UNKNOWN → UNKNOWN, supported by insufficient impact evidence. Zero inherited flags. Automatic/effective review true → false for the new candidate; old review remains bound to old hashes. |
| Audio `cluster_6b59d13144282285` | CONSOLIDATED → CONSOLIDATED; no new validation failure | 6/6 members, 19/19 messages. Meaningful split: silence M01/M04; player failure M02/M03/M05/M06. M01–M04 handling questions remain OPEN. M05 and M06 remain ANSWERED, but their question scopes require separate judgments below. All scoped guidance retained. | Historical HIGH → silence UNKNOWN and playback HIGH, both supported. Two inherited obligations (M02, M05), HIGH review and two conservative coverage warnings remain. One new material finding plus one scope uncertainty; effective review true. |

The source questions were assessed before execution in [pre_run_review.json](pre_run_review.json).
All 23 original messages, roles and reaction users/targets were inspected, then
all new summaries, differences, inventory tags, links and severity evidence were
compared. [reviewed_sources.json](reviewed_sources.json) retains exact quotations;
[source_file_bindings.json](source_file_bindings.json) verifies them against the
canonical source files. No experiment review findings, evaluation labels,
expectations or prior Agent 2 source-review judgments entered the requests.
The existing member-level Agent 1 reliability/flag/disputed-field metadata remains
unchanged as required by the baseline contract.

**The remaining material error.** Audio M05 source `1790920171.000109` (E014) asks
“Player never loads, should I QN?” and also asks whether others see it. TL reply
`1790920220.000113` (E015) establishes that the affected task cannot be evaluated,
instructs incident reporting with task ID, and says not to mark the recording as a
model-quality failure. It never decides Quarantine eligibility or says reporting
replaces Quarantine. Yet `topics[1].inventory[12]` / `T2_I13` marks the whole question
ANSWERED through `T2_I14`. M05 therefore disappears from `open_questions`.
This is a semantic scope failure after successful provider/schema/application
validation. It is not an ID, transport or parser defect. Useful handling guidance
must remain; OPEN or PARTIAL depends on the substantive subquestion assessed.
No saved response was edited or automatically relabeled.

**M06 is different.** Its source `1790934294.000106` (E016) asks whether this is QN
or a player issue. TL E019 explicitly directs playback-incident handling and
rejects model-quality-failure scoring, so a substantive answer to that handling
alternative is defensible. It should not be forced OPEN just to match M05.
The source still supplies no general Quarantine prohibition or confirmed cause.
That limitation is separately recorded as uncertainty, not a second demonstrated
material error. Both exact question/reply pairs are available in effective review.

Alignment E004 explicitly withholds supersession until change history is verified.
The new output correctly retains that fact and the attach-both-versions-with-dates
instruction without treating them as a precedence answer. Its distinct answer-member
count falls from one to zero; its guidance-member count remains one.

Audio retains E007's reproduction prerequisite and conditional keep-both-task-IDs
instruction, E010's waveform/playhead diagnostic, E003's intended-silence/other-player
checks, and E015/E019's exact reporting/do-not-score conditions. E005's thumbsup was
from tutor U018, not a TL endorsement. QN remains Quarantine. No attempted/failed
historical workaround, precedence decision, root cause or unsupported queue-wide
impact is invented. The new singular “one reply” description cites two
cause-unconfirmed replies; it is not an exhaustive count and no message is lost.
The deterministic inventory retains both. Genuine TL-reaction endorsement and
eyes behavior do not occur in these sources and remain untested here.

The new split permits UNKNOWN for apparent silence without demonstrated impact,
while explicit inability to evaluate E015/E019 supports HIGH for playback failure
at affected-task scope. HIGH creates a nonblocking review obligation. It does not
derive from inherited flags; UNKNOWN does not clear them. Severity remains
provisional and available for Agent 3 to reassess after research.

Mechanical results: **2 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED, 0 unprocessed**;
**2 attempts, 2 saved HTTP responses, 0 unknown completions**, zero started-without-call
markers. Both responses are HTTP 200, return `gpt-5.4-2026-03-05`, finish `stop`, and
contain no refusal. Eight unique full identities match the selected inputs.
Canonical/per-group outputs and queues agree. Full member records and both inherited
obligations are equal to the saved source payloads and baseline, including all
evidence, effective/automated Agent 1 statuses, candidate/source hashes and lineage.

| Case | Input none → low | Output none → low | Reasoning none → low | Cached input | Latency none → low |
| --- | ---: | ---: | ---: | ---: | ---: |
| Alignment | 3,707 → 3,707 | 480 → 958 | 0 → 495 | 0 → 0 | 6.91s → 13.49s |
| Audio | 6,303 → 6,303 | 1,106 → 2,418 | 0 → 748 | 0 → 0 | 9.73s → 26.37s |
| Total | 10,010 → 10,010 | 1,586 → 3,376 | 0 → 1,243 | 0 → 0 | 16.64s → 39.87s |

Reported output includes reasoning; do not add reasoning tokens again. New
non-reasoning output is 2,133 tokens, versus 1,586 historically. Total new usage is
13,386 tokens. The new response also makes three topics rather than two, so visible
output length differs. Mean recorded request latency increases from 8.32s to 19.93s;
single observations and historical timing cannot support performance guarantees.

At the checked standard rates of $2.50 input / $0.25 cached input / $15 output per
million tokens, the estimate from returned usage is **$0.075665**, versus historical
**$0.048815**. The preflight estimate at both full output budgets was $0.270785,
using historical prompt tokens and no cache discount. These are token-based
estimates, not billing receipts. See [pricing](https://developers.openai.com/api/docs/models/gpt-5.4)
and [cost_estimate.json](cost_estimate.json).

**Offline checks:** 53 focused tests passed; **510 passed, 0 failed, 0 skipped** in
the full suite (162 warnings, 241.84s). Topic catalog and Slack fixture validation
passed for 200 identities; `git diff --check` passed. Exact commands:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent2_reasoning_configuration.py tests/test_agent2_structured.py tests/test_agent2_impact_scope.py -q --tb=short --basetemp .cache/pytest-reasoning-low-focused --junitxml .cache/agent2_reasoning_low_v5_2/focused-tests.xml
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-reasoning-low-full --junitxml .cache/agent2_reasoning_low_v5_2/full-tests.xml
.venv\Scripts\python.exe -X utf8 scripts/validate_topic_catalog.py
.venv\Scripts\python.exe -X utf8 scripts/validate_slack_fixtures.py
git diff --check
```

The initial sandboxed uv preflight could not access its existing cache; the same
offline command succeeded with cache access. This was before any request attempt.
The authorized execution used these settings and commands **once**; they are an
execution record, not an instruction to rerun the completed pilot:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-5.4-2026-03-05'
$env:THREADSENSE_AGENT2_REASONING_EFFORT = 'low'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-reasoning-low-v5-2.json --max-requests 2 --output-dir data/processed/agent2_reasoning_low_v5_2
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-reasoning-low-v5-2.json --max-requests 2 --output-dir data/processed/agent2_reasoning_low_v5_2
```

Production change: only `src/threadsense/agents/topic_requests.py` adds the explicit
Agent 2 none/low configuration and strips incompatible sampling defaults. Unreviewed
efforts or low with another model fail before a request; the default remains none.
`tests/test_agent2_reasoning_configuration.py` adds eight offline cases for exact
historical semantic equality, rejection of unreviewed settings, actual wire bytes,
and truncation retention without retry. README and the maintained run guide describe
the result. The review registry appends this experiment without replacing prior
entries. New experiment/prepared/run files and the pilot selection retain all
metadata and evidence. No dependencies, `.env`, semantic modules or historical
artifacts changed. No production code changed during or after execution.

Artifacts:

- [Freeze](freeze.json), [preflight](offline_validation.json), and [request ledger](request_ledger.json).
- [Mechanical audit](execution_audit.json), including all executed-file hashes.
- [Canonical export](../../processed/agent2_reasoning_low_v5_2/consolidations.json), [manifest](../../processed/agent2_reasoning_low_v5_2/manifest.json), [automated review queue](../../processed/agent2_reasoning_low_v5_2/review_queue.json), and [member review queue](../../processed/agent2_reasoning_low_v5_2/member_review_queue.json).
- [Source-bound supplement](review_supplement.json), [refreshed effective output and queue](effective_output.json), [effective checks](effective_review_check.json), and [readiness](readiness.json).
- The seven-entry [mandatory registry](../../../docs/agent2-review-supplements.json) preserves all earlier reviews. The run-local effective snapshot remains unchanged; downstream consumers should use the maintained loader or refreshed experiment view.

The effective view retains one material M05 finding and one M06 scope limitation,
two inherited obligations and HIGH review, with **zero stale bindings**. One group
requires review. The unresolved M05 question is exposed in its evidence-bound
obligation even though the original model output still says ANSWERED; the original
outcome and text remain inspectable. Existing group-level review conservatively
makes all Audio topics provisional. It does not delete members, clear obligations
or require human approval to continue nonblocking processing.

**Next decision:** hold broader validation because M05 remains a material scope
failure. A narrowly justified next intervention is one contrasting synthetic
example of a reporting-only question and a separate disposition decision. It should
show when reporting guidance is a complete answer and when it leaves the requested
decision open, without importing these pilot answers. This recommendation is not
implemented. It would require separate authorization and validation; do not
increase reasoning automatically or launch another call loop. The two cases do not
test multilingual, non-operational, announcement or broad generalization behavior.
