# Agent 3 dashboard walkthrough (saved outputs only)

Every step reads saved run directories. No model call, API key or network access is needed during the presentation.
Each run's banner shows its mode (LIVE, SCRIPTED or TEST_FIXTURE), and each card has a badge naming its semantic
source. Say which run you are on at every step. Current demo baseline: section 0 (architecture and evidence status:
[architecture/THREADSENSE_END_TO_END.md](architecture/THREADSENSE_END_TO_END.md)). Sections 1-5 were written against
implementation baseline commit `d976eff`. Documentation changes after
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
  --decision-db D:/tsb/demo-20261106-r1.sqlite3 --decision-origin DEMO_SCRIPT
# open http://127.0.0.1:8000 ; the session is locked to Priya (U006, team lead); --team-lead picks another TL at startup
```

On PowerShell, write the command on one line (drop the `\`).

The runner refuses hosts other than localhost. Checked on 2026-11-01 through the app's API with a throwaway store:
- 12 runs were listed, and every run below loaded.
- Saving one decision twice with the same key gave 201 and then a replayed 200, leaving one row.
- The run files were byte-identical afterwards.

## 0. Demo baseline: the combined briefing (2026-11-06)

**Run:** `threadsense_full_v1_combined_v2` (LIVE model judgments, combined offline; `REVIEW.md` in the run directory).
Launch (zero calls). Use a new store file name for each rehearsal (r1, r2, ...); the folder is created if missing.
PowerShell, one line:

```powershell
uv run --locked python scripts/run_dashboard.py --include-test-fixtures --runs data/experiments --runs tests/fixtures/observation_demo_runs --decision-db D:/tsb/demo-20261106-r1.sqlite3 --decision-origin DEMO_SCRIPT
```

Then open http://127.0.0.1:8000/#run=threadsense_full_v1_combined_v2.

Show:
- **Overview:** 63 active cards covering 174 threads (52 Needs Review, 8 Recommended Action, 3 Observation); separately
  3 processing-history threads and 37 review-queue items. "Card records in this run 95" includes the 29 replaced cards
  (history) and is not an active total. Open "Usage by stage" for each stage's own cost. Agent 3 advice is live model output; relevance labels and merge decisions are developer audits.
- **Observations:** the three live cards ("Suggestive vs explicit content boundary", "Queue coverage and closure
  reminders", "Work environment and background noise"), each with its supported no-action reason.
- **Combined issue:** "QN handling for fictional contact details": open "Earlier cards this issue replaces (2)" (the
  replaced cards are history, not briefed). What to check: "A documentation question is unresolved" with the October
  status note, the instructions and the follow-up record.
- **Targeted re-grounding ($0.094 for both cards, run separately; this build made no calls):** "Overlapping speech in
  transcription" shows its reminder and stays in review only for its open inherited flag. "Format compliance versus
  accuracy" is a Recommended Action: point out "Human edits, verified by the live model (3)", the unchanged model draft,
  and the posting suggestions marked "not judged" (reply in the October 2 status note's thread; optional JSON-versus-prose
  line), kept apart from the copyable draft.
- **Close call:** "NSFW suggestive-content threshold" asks you to choose a next step between two saved options; the
  cutoff question stays open.
- **Editorial notes** (labelled, not judged): "Confirm before editing" on the fictional-contact edit; "Timing
  unconfirmed" on the queue-coverage observation.

Synthetic Observation examples (model behavior, tool performance) are only in `observation_demo_fixture_v1`
(TEST_FIXTURE, hand-written); switch runs and say so if you show them.

## 1. Current Submit card and its evidence

**Run:** `agent3_recipient_routing_v1` (LIVE, prompts v14, cutoff 2026-10-02T12:00:00Z). Card: the projection gap
`routed_440e64c7fbdcc49f`, response_preference, batch 15.

Show:
- **Summary:** two sentences, both judged SUPPORTED and shown unchanged.
- **Action:** "Report a technical issue to engineering".
  - Instruction: "Collect the requested diagnostic details for these reports and report the submission problem to
    engineering."
  - Also show the copyable draft, the scope note and the rationale.
- **Overview:** the complete instruction, with **Copy draft** in the same box (one click; nothing is posted).
- **What to review** (on the card, no expanding): the high severity is a *mandatory* review (open its two rubric
  signals and their messages); three inherited flags, each linked to its thread, two of them to their Model Review
  Queue items (the projection gap has no queue item); and the advisor's own note, which the final evidence check
  supported. Point out that the action is shown but the card still needs a team lead. No statement was withheld on
  this card. The line under the title names the run, prompts v14 and the model.
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
uv run --locked python scripts/build_decision_snapshot.py --decision-db D:/tsb/demo-20261106-r1.sqlite3 \
  --namespace demo --cutoff <ISO time after the save, not in the future> --index-dir .index/retrieval_demo_20261101          # plan only
#   add --build to export and build
```

`agent3_feedback_loop_offline_v1` is superseded: it recorded its simulated approval as operational. Do not use it.

## Do not claim

- That prompts v14 was verified live on anything other than Submit.
- That any test count or 17/17 measures model accuracy.
- That ToT replacement or a ToT fallback, or rejection of an unsupported route, has been observed live. (A close call
  *has*: the NSFW card in the demo baseline is a live, unresolved close call with two viable options, none preferred.)
- That any approval was executed or produced an outcome.
- That the demo baseline is one untouched live run. Its 8 Recommended Action and 3 Observation cards come from live
  Advisor judgments (campaign, refresh, targeted re-groundings), combined offline. Relevance exclusions and cross-group
  merges are developer-audited labels and prepared decisions, not live Agent 1/2 judgments.
- That the baseline has 95 active cards: it has 63 active cards (174 threads); the 95 records include 29 replaced and
  3 processing-history cards.
- That every discussion was processed: 177 of 178 were; Agent 1 rejected 1 (`AUTHORITY_INELIGIBLE`), recorded as
  unfinished in the campaign's `final/run_summary.json`. "Accounting COMPLETE" is disposition accounting, not
  processing success.
- That every word on a card was checked by the model. Statements shown as established were; fixed UI text, quoted
  sources, topic names and the labelled editorial suggestions were not.
- That the dashboard authenticates users.
- That the format card's three edited statements are model-written (they are human edits the live model judged SUPPORTED).
- That Agent 1's semantic exclusion check or the live Agent 2 merge judge has run live (both are exercised offline only).
- That the synthetic Observation examples are live results.
