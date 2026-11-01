# Agent 3 dashboard walkthrough (saved outputs only)

Every step reads saved run directories. No model call, API key or network access is needed during the presentation.
Each run's banner shows its mode (LIVE, SCRIPTED or TEST_FIXTURE), and each card has a badge naming its semantic
source. Say which run you are on at every step. Implementation baseline: commit `d976eff`. Documentation changes after
it are listed in section 7 of [agent3-acceptance.md](agent3-acceptance.md).

## Setup (once, before the session)

```sh
uv sync --locked --extra dev
npm --prefix web ci && npm --prefix web run build      # web/dist is already current; rebuild if web/ changed
```

## Start

Use a new decision store file, outside the repository, for every rehearsal and presentation: pick a name you have not
used before (for example `D:/tsb/demo-20261101-r2.sqlite3`). Keep earlier store files as they are; don't delete or
reuse them. A reused store would show earlier decisions as already resolved. Always keep `--decision-origin
DEMO_SCRIPT`: it puts rehearsal decisions in the `demo` namespace, so default operational snapshots never ingest them.

```sh
uv run --locked python scripts/run_dashboard.py --include-test-fixtures \
  --runs data/experiments --runs data/experiments/agent3_feedback_loop_offline_v2 \
  --decision-db D:/tsb/demo-<YYYYMMDD>-r<N>.sqlite3 --decision-origin DEMO_SCRIPT
# open http://127.0.0.1:8000 ; the session is locked to Priya (U006, team lead); --team-lead picks another TL at startup
```

On PowerShell, write the command on one line (drop the `\`).

The runner refuses hosts other than localhost. Checked on 2026-11-01 through the app's API with a throwaway store:
- 12 runs were listed, and every run below loaded.
- Saving one decision twice with the same key gave 201 and then a replayed 200, leaving one row.
- The run files were byte-identical afterwards.

## 1. Current Submit card and its evidence

**Run:** `agent3_recipient_routing_v1` (LIVE, prompts v14, cutoff 2026-10-02T12:00:00Z). Card: the projection gap
`routed_440e64c7fbdcc49f`, response_preference, batch 15.

Show:
- **Summary:** two sentences, both judged SUPPORTED and shown unchanged.
- **Action:** "Report a technical issue to engineering".
  - Instruction: "Collect the requested diagnostic details for these reports and report the submission problem to
    engineering."
  - Also show the copyable draft, the scope note and the rationale.
- **Needs Review reasons:** HIGH severity and inherited Agent 1 flags. Point out that the action is shown but the card
  still needs a team lead. No statement was withheld on this card.
- **Evidence:** 21 items, 16 cited. Click **Details & evidence**: the draft is on the "Action & draft" tab, the cited
  sources and threads on "Sources & threads", and every item on "All evidence". Open:
  - the project instructions section "Tool incidents and submission" (current guidance);
  - the October 1 announcement (governs example collection only; described as a source fact, not as a route);
  - the September 28 engineering handoff (prior record: history, not current handling);
  - one member thread in the thread view.

Optional contrast: `agent3_source_fact_v1` (prompts v13), where the same action was withheld because the judge demanded
an established intake route. This is the defect v14 fixed.

## 2. Observation-only behaviour

**Run:** `agent3_policy_eval_v1` (LIVE, prompts v9). Card: "Repeated final line in exported audio".

Show:
- No action is displayed (the draft proposed NO_ACTION; grounding passed).
- The only review reason is the inherited flag.
- The summary keeps the observation open: the team lead's file-versus-player checks have not come back.

Then switch to `dashboard_states_fixture_v1` (TEST_FIXTURE) and show "[Test fixture] Repeated final line in exported
audio" on the **Observation** line. This shows how an unflagged observation is displayed. It is hand-written test data,
not a model result. Observation cards accept no decision.

Be candid: under prompts v6.2 (`agent3_final_eval_v1`) the model proposed a reminder for this topic.

## 3. Temporal conflict handling

**Run:** `agent3_final_eval_v1` (LIVE, prompts v6.2). Card: "Fictional phone number quarantine handling"
(safety_classification).

Show:
- **Review reasons:** INHERITED_FLAG, TEMPORAL_CONFLICT, GROUNDING_FAILURE.
- **Evidence:** the QN help page's "Contact details" section is labelled superseded (HISTORY_ONLY), replaced by the
  fictional-PII clarification effective 2026-09-10. The FAQ and the clarification announcements are current.
- **Action:** update documentation (the stale help-page section).
- **Grounding failure:** some statements were withheld. Show that withheld text is absent, not repaired.

Supporting offline evidence, if asked (these are not live accuracy):
- original temporal benchmark 14/15;
- separate policy-aligned benchmark 17/17 with prepared judgments.

## 4. A TL decision saved once (not executed)

On the Submit card from step 1 (LIVE run `agent3_recipient_routing_v1`), as Priya (U006, the session's team lead), click **Resolve…** and choose **Route to an
expert → Engineering** and save. The card's judgment is live (`judgment_provenance LIVE_MODEL`), but the decision is a
rehearsal recorded in the `demo` namespace (`DEMO_SCRIPT`), not operational history.

Show:
- **Saved state:** the success state appears only after the save is persisted. The card moves to Resolved with its
  text, reasons and evidence unchanged.
- **Labels:** the text is model-grounded, and approval is not execution.
- **No duplicate:** refresh, or click again. There is still exactly one decision; a repeat with the same key is
  replayed, not duplicated.
- **Stored record:** `tl_response APPROVED`, execution `not_executed`, outcome `not_observed`, namespace `demo`,
  origin `DEMO_SCRIPT`.
- **Copy draft:** copies to the clipboard only ("Nothing was posted").

Approval only saves the decision. Nothing is posted to Slack or sent to engineering, nothing is executed, and no
outcome is established: the record stays `not_executed` / `not_observed`.

## 5. Decision to retrieval (offline, labelled)

**Saved demonstration:** `data/experiments/agent3_feedback_loop_offline_v2/` (zero model calls; demo namespace;
scripted overnight run). Read from `summary.json`:
- **Decision:** at 2026-10-30T20:09:30Z, route the live smoke audio card to engineering (`DEMO_SCRIPT`, demo
  namespace).
- **Snapshot:** a new snapshot `.index/retrieval_feedback_20261030T200929Z` was built at that cutoff with 1 decision.
  The active `.index/retrieval` was not modified.
- **Later overnight run:** the run in `overnight_run/` (SCRIPTED_PILOT; brief labelled "replay of an earlier handoff")
  retrieved the decision as a PRIOR_DECISION: `tl_approved`, `not_executed`, `not_observed`, "history, not a standing
  rule".

In the dashboard, select the run `overnight_run` (SCRIPTED banner) and open its audio card's evidence to show that
record.

The decision saved in step 4 does not reach retrieval during the session. A team lead's decisions enter only through
a new snapshot built at a later cutoff. Optional, zero calls, needs the local embedding model, writes a new index
directory:

```sh
uv run --locked python scripts/build_decision_snapshot.py --decision-db D:/tsb/demo-<YYYYMMDD>-r<N>.sqlite3 \
  --namespace demo --cutoff <ISO time after the save, not in the future> --index-dir .index/retrieval_demo_20261101          # plan only
#   add --build to export and build
```

`agent3_feedback_loop_offline_v1` is superseded: it recorded its simulated approval as operational. Do not use it.

## Do not claim

- That prompts v14 was verified live on anything other than Submit.
- That 962 tests or 17/17 measure model accuracy.
- That ToT replacement or close-call handling, or rejection of an unsupported route, has been observed live.
- That any approval was executed or produced an outcome.
- That Recommended Action or Observation cards came from a live evaluation (they are shown on the labelled fixture).
- That the dashboard authenticates users.
