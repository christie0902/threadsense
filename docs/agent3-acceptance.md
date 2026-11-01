# Agent 3 acceptance report (2026-11-01)

Scope: the Agent 3 Advisor, overnight workflow and dashboard on synthetic Slack fixtures. Acceptance is for a local
capstone/demo release, not a production deployment. This report reuses recorded results; it adds no model calls and
changes no behaviour. The full history and the reasoning behind each change are in
[agent3-plan.md](agent3-plan.md). The demo steps are in [agent3-demo-walkthrough.md](agent3-demo-walkthrough.md).

## 1. Tested checkout

| Item | Value |
| --- | --- |
| Implementation baseline | `agent3` at `d976eff` ("resolve blocker before demo"): the code, tests, prompts and saved runs this report evaluates. Documentation added afterwards is listed separately in section 7 and changes no behaviour |
| Advisor | pilot `agent3-advisor-pilot-v6`, prompts `agent3-advisor-prompts-v14`, draft `agent3-advisor-draft-v10` |
| Judging | grounding `agent3-grounding-judgment-v5`, ToT `agent3-tot-comparison-v3`, evidence view `agent3-evidence-view-v3` |
| Outputs | AdviceCard `agent3-advice-card-v3`, workflow `agent3-overnight-v1`, decisions `dashboard-tl-decision-v3` / `dashboard-model-review-action-v2` |
| Knowledge | chunking `knowledge-chunks-v2`, rubric `severity-rubric-v3-semantic-signals`, active index build `4da16f09…` (cutoff 2026-10-02T12:00:00Z) |
| Inputs | handoff `data/processed/agent2_handoff_v2_projection/`, Slack `data/fixtures/slack_generated_demo/` |
| Live model | `openai/gpt-6.1-sol`, reasoning medium, default tier, 24,000 input / 16,384 output tokens per request, zero retries |

**Regression suite.** 962 passed, 0 failed, on the first run (2026-11-01, 11 min 32 s, `--basetemp D:/tsb/pytest-full5`).
No file under `src/`, `tests/` or `scripts/` changed between that run and commit `d976eff`. Browser tests: 10 passed
(last run 2026-10-31); no frontend source has changed since `web/dist` was built. These counts show the code
behaves as specified on fixed inputs. They do not measure model accuracy.

## 2. Live result for prompts v14 (Submit only)

Run `data/experiments/agent3_recipient_routing_v1/` (LIVE, run once on 2026-11-01): 2 requests, 28,704 input / 7,942
output tokens, **$0.1368**. No research follow-ups, revision or ToT ran. Accounting COMPLETE. All 52 review queue items
were carried:
- 41 discussion-related Agent 1 obligations;
- 8 announcement-related Agent 1 obligations;
- 3 Agent 2 naming cautions (queue kind `assisted_content_review`, finding `TAXONOMY_NAMING_CAUTION`).

- Every judged statement was SUPPORTED, and the action was judged SUFFICIENT on seven essential premises. Card line:
  Needs Review (HIGH severity, inherited Agent 1 flags).
- Displayed action (Report a technical issue to engineering): "Collect the requested diagnostic details for these
  reports and report the submission problem to engineering." No route or shared cause is asserted.
- Displayed summary: "Two QA tutors and three tutors report submission problems, ranging from a grey or disabled Submit
  button to a click that does nothing. The team lead requested task IDs, required-field state and exact button
  behavior in all four threads, and said submission status was still unverified."

**Independent source review.** The draft message, scope note and rationale were checked against the 15 member
messages, the project instructions section "Tool incidents and submission" and the October 1 announcement:
- Each symptom is attributed to the reporter who stated it: grey button after choosing B (a QA tutor and a tutor),
  a click that does nothing (RP-1577), unable to submit after the rubric (RP-3325), and disabled after every field.
- The engineer's requests (LT error state and time, RP-3412 and RP-5337) and the team lead's four identical requests
  are reproduced accurately.
- "Without assuming a shared cause" follows the engineer's "the wider cause is not confirmed here".
- The announcement is described only as governing example collection.

Nothing in the displayed text goes beyond the sources.

Context: the four earlier Submit runs on prompts v10–v13 withheld this action, each for a different defect that has
since been fixed (see the plan). This is one run on one topic. The other eight scenarios have not run on v14.

## 3. Temporal benchmarks (two separate benchmarks)

| Benchmark | Cases | Result | Semantic inputs |
| --- | --- | --- | --- |
| Original `data/evaluation/temporal_golden.json` (labels unchanged) | 15 | **14/15** joint; decisive 11/12; abstention 3/3; 0 false overrides | prepared judgments |
| Policy-aligned `data/evaluation/temporal_golden_policy_v1.json` | 17 | **17/17** joint; decisive 13/13; abstention 4/4; policy fields 3/3; 0 false overrides | prepared judgments |

The remaining mismatch on the original benchmark is T02. Its label expects an executed TL decision to override a
guideline, but the case records no enactment. Under the settled enactment policy (section 6), production abstains
for team-lead review. The label predates that policy and is kept unchanged, together with its reports.

The policy-aligned benchmark is a different dataset. It replaces T02 with a negative case (T02N) and two positive
variants (T02A, T02E), with labels written from the stated enactment policy before the run. Its 17/17 is therefore not
an improvement over 14/15 on the same labels, and the two scores are not comparable.

Both benchmarks exercise deterministic ingestion, version eligibility and temporal decision code with prepared
semantic judgments. They are not live model accuracy.

Reports: `agent3_temporal_golden_v1/` and `agent3_temporal_golden_v2/` (both 14/15), and `agent3_temporal_policy_v1/`
(17/17, with `changes.json` separating dataset, harness and production changes).

## 4. Scenario coverage

Per-run detail is in `data/experiments/agent3_scenario_coverage_v2/coverage.md`, produced by
`scripts/report_scenario_coverage.py` with one row per saved run (zero calls); the earlier report is
`agent3_scenario_coverage_v1/`. The results below come from different runs on different prompt versions and are not
one evaluation run.

Levels:
- **Live:** real model calls.
- **Scripted:** prepared pilot judgments (`agent3_overnight_offline_v2`, prompts v6.1).
- **Placeholder:** nothing judged.
- **Fixture:** the hand-written dashboard test run.

| Scenario | Latest live run (prompts) | Live result | Other levels | Remaining limitation |
| --- | --- | --- | --- | --- |
| Technical escalation (Submit) | `agent3_recipient_routing_v1` (v14) | Escalation shown; every statement SUPPORTED; 3/3 expected sources | scripted: escalation | Only v14 live run. Unsupported-route rejection tested offline only |
| TL confirmation (JSON vs prose) | `agent3_summary_eval_v1` (v10) | Reminder shown; both summary sentences shown; 2/3 sources | scripted: NO_ACTION | v11–v14 changes not live-verified here |
| FAQ edge case (audio playback) | `agent3_policy_eval_v1` (v9) | Escalation shown; 3/5 sources (5/5 in earlier runs); one announcement statement PARTIALLY_SUPPORTED | scripted: FAQ update | Recall depends on the model's follow-up queries |
| QA misalignment (ties) | `agent3_policy_eval_v1` (v9) | Review session; the judge found the current sources agree; 3/4 sources | placeholder | RP status note (rank 13) still not retrieved |
| Observation only (repeated ending) | `agent3_policy_eval_v1` (v9) | NO_ACTION, grounding passed, Needs Review only for the inherited flag | scripted: NO_ACTION; fixture: Observation line | Under v6.2 the model chose a reminder (outside the set). The dataset blueprint expects escalation per thread (conflict recorded) |
| Already announced | `agent3_repair_eval_v1` (v7) | Escalation (acceptable); 2/2 sources; one statement withheld | placeholder | No live run after v7 |
| Instruction conflict (fictional PII) | `agent3_final_eval_v1` (v6.2) | Documentation update; TEMPORAL_CONFLICT; some statements withheld (GROUNDING_FAILURE); 2/3 sources | scripted: documentation update | No live run after v6.2 |
| Language routing (Korean) | `agent3_final_eval_v1` (v6.2) | Language specialist; grounding passed; 3/3 | scripted: language specialist | No live run after v6.2 |
| Inherited flags (Japanese) | `agent3_final_eval_v1` (v6.2) | Language specialist; flags kept; grounding passed | placeholder | No live run after v6.2 |

All cards in the recorded live evaluations are Needs Review, with their required reasons, and no inherited flag was
dropped. Eight of the nine topics carry inherited flags. The Recommended Action and Observation card lines are
demonstrated with the clearly labelled fixture run (`dashboard_states_fixture_v1`, TEST_FIXTURE), not with model
results.

## 5. Remaining limitations

- **ToT selection is offline-tested only.** Candidate replacement before grounding, close calls kept after grounding,
  and the fallback have never occurred live: in the latest runs no draft stated an action choice, and in v6.2 every
  card kept its own action.
- **Unsupported-route rejection is offline-tested only.** The v14 rule's rejection of a named channel or thread
  asserted as the official intake route is covered by prepared-judge regressions. The live run contained no such
  claim.
- **Semantic grounding can be wrong.** The final grounding call is a model judgment. It has both falsely rejected
  (Submit under v11–v13) and correctly rejected (overgeneralized summaries) live. Deterministic checks catch structural
  errors but not every semantic one. Withheld text routes to Needs Review rather than being repaired.
- **Severity for rule-confusion topics is ambiguous.** It is recorded, not scored, pending a TL rubric decision. The
  same topic has received different levels across runs (observation only: HIGH under v6.2, LOW under v9; instruction
  conflict: HIGH or MEDIUM).
- **Coverage gaps.**
  - 8 projected Agent 2 groups have no reusable taxonomy. Their 17 discussion members are unassigned but remain
    accounted for in every run. The Submit case is one of these projection-gap work items.
  - No full live run of all 87 work items has been done. It needs a cost cap; the estimate is in Milestone 5 of the
    plan.
  - Live coverage is nine topics at most.
- **Local-demo authentication.** The dashboard has no authentication. "Acting as" a team lead (U001, U006) is trusted,
  and the server runs on localhost only. Decision namespaces follow the run mode and the `--decision-origin` flag, not
  a user role. Approvals record intent only; nothing is posted, sent or executed.
- **Retrieval recall.**
  - A bounded related-record expansion is enabled during prior-decision research (history mode, decision records
    requested). It adds at most 2 decision records per topic that are linked to a returned record by recorded
    `source_refs` (either direction) or a shared `event_series_id`, under the same project, scope, batch, date and
    version filters. A type-coverage addition (at most 2 guideline or FAQ chunks) is enabled in the initial guidance
    search. Both are off when replaying runs that did not use them.
  - The earlier, broader recorded-link lookup experiment (Milestone 7, `agent3_related_lookup_eval_v1`) was evaluated
    but not enabled in that form.
  - Recall still depends on the model's own follow-up queries (for example, the RP status note is not retrieved).
- **Other open items.**
  - The decision-to-retrieval loop has been demonstrated offline with a scripted overnight run only.
  - Thread views read the current fixture, not a frozen copy.

## 6. Handoff

- **State:** Milestones 2–7 and repair passes 1–3, plus the v10–v14 corrections, are implemented. Frozen runs, corpus,
  rubric, labels, obligations and the active index are unchanged.
- **Paid calls:** any `--run` is paid and needs approval with `--max-requests`/`--max-cost`. Everything else in this
  report is zero-call.

**Settled policy** (implemented and tested; not open questions):
- **Enactment.** A TL decision supports current handling only when it is enacted. That means:
  - approved by an authorized role, in scope and effective;
  - a recorded policy change;
  - linked by a later TL announcement or current guideline, or marked `policy_enacted`.

  An approved or executed decision without that is a prior record. An older guideline under an unverified replacement
  stays eligible evidence but is not a provisional decided baseline: the case abstains for team-lead confirmation.
  T02 is a recorded label mismatch under this policy, not a pending decision.
- **Advisory status.** Approval is never execution. TL decisions reach retrieval only through a new snapshot at a later
  cutoff, and demo or test decisions never enter operational snapshots.
- **Claims and routes.** A request from anyone but a team lead is a reported fact with no authority. A functional
  recipient needs incident evidence, not an intake route. A concrete or mandatory route needs its own support (v14).

**Pending TL policy decision:**
- **Severity for rule-confusion topics** (TL rubric decision; recorded, not scored until then).

**Engineering and data follow-ups** (not policy decisions; neither is done in this release):
- **The 8 projection-gap groups.** Their 17 discussion members remain accounted for. Completing their taxonomy needs a
  new Agent 2 run or an explicitly approved projection approach.
- **Full 87-item live run.** It needs a separately authorized cost cap.

**Recorded discrepancy (not blocking acceptance):** the observation-only topic's per-thread dataset blueprint expects
escalation, while the scenario matrix also accepts NO_ACTION. Both are kept unchanged. Reconciling them is optional
dataset maintenance.

**Optional future evaluations** (none is required for acceptance; each is a separately authorized paid experiment
with its own caps):
- one v14 run over the eight non-Submit scenarios;
- a topic whose draft states an action choice (live ToT selection);
- a case containing an unsupported route claim.

## 7. Documentation changes after the baseline

Made on 2026-11-01 after `d976eff`. They are prose and zero-call report output only: no implementation, test, prompt,
frozen evidence or saved run changed, and no test rerun is needed.

| Change | Path |
| --- | --- |
| This acceptance report (new) | `docs/agent3-acceptance.md` |
| Dashboard walkthrough (new) | `docs/agent3-demo-walkthrough.md` |
| Docs line lists the two documents | `CLAUDE.md` |
| Per-run scenario coverage report (new; reads saved runs, one row per run, merges nothing; not an evaluation run) | `data/experiments/agent3_scenario_coverage_v2/` |
| Corrections: baseline wording, settled policy versus pending decisions, optional live checks, this section | `docs/agent3-acceptance.md`, `docs/agent3-demo-walkthrough.md` |
| Corrections: release scope (local demo); related-record expansion is enabled and distinguished from the Milestone 7 experiment; exact review queue breakdown (41 / 8 / 3 naming cautions); projection gaps reclassified as an engineering/data follow-up; card-line claims limited to the recorded live evaluations; walkthrough provenance per step, fresh rehearsal database, approval does not establish an outcome | `docs/agent3-acceptance.md`, `docs/agent3-demo-walkthrough.md` |
