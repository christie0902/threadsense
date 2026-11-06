# ThreadSense

Multi-agent pipeline that turns Slack threads from four annotation projects
(audio_multimodal, multilingual_eval, response_preference, safety_classification)
into a morning brief for team leads. Python 3.13, CrewAI + LiteLLM, Pydantic v2,
sentence-transformers/scikit-learn for grouping. Data is synthetic Slack fixtures.

Pipeline: **routing** (announcement channels → knowledge-source JSON; discussions → agents)
→ **Agent 1** interpret + verify (done, v3) → **grouping** → **Agent 2** taxonomy
(done, v7) → **Agent 3** research / severity / AdviceCards (CrewAI Advisor; LangGraph overnight workflow) → **dashboard** +
TL decision loop (FastAPI + React in `web/`).

## Commands

```sh
uv sync --locked --extra dev                                   # install (no activation needed)
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-<name>
uv run --locked --extra dev python -m pytest tests/test_x.py   # single file
```

- Always pass a **fresh** `--basetemp .cache/pytest-<name>`: pytest wipes it at start.
- Full suite: 1198 tests, ~15 min, all expected to pass. Intermittent `WinError 5` on `os.replace` is a Windows file lock (see Known issues), not a code failure.
- No linter/formatter configured. No build step beyond the editable install.
- UI tests: `npm --prefix web run build` then `npm --prefix web run test:ui` (Playwright, system Chrome; temp output
  in `TS_UI_TMP`, default `D:/tsb/ui-<time>`). Frontend deps are pinned in `web/package.json` + `package-lock.json`.
- Zero-call checks: `--dry-run`, `--inspect`, `--check-input` flags (list in README). Anything with `--run`, or Agent 1 without `--dry-run`/`--inspect`, makes **paid model calls** — never run those without asking.
- Dependency changes go in `pyproject.toml` and `uv.lock` together.

## Layout

- `src/threadsense/` — package. `routing.py`, `source_ingestion.py`, `knowledge_sources.py` (ingestion contract for Agent 3 retrieval), `adapters/mock_slack.py`, `topic_grouping.py`, `config.py` (.env + model selection).
- `src/threadsense/agents/` — current Agent 1 (`thread_interpreter`, `interpretation_*`, `verification_*`) and Agent 2 (`topic_taxonomy`, `topic_contracts`, `topic_pipeline`, `topic_effective`). See its README.
- Agent 3 (milestone 2): `agents/advice_contracts.py` (AdviceCard/DecisionRecord/AnnouncementRecord/ModelReviewItem v1), `agents/advice_inputs.py`, `severity_rubric.py` (loader for the TL rubric), `knowledge_markdown.py` + `knowledge_corpus.py` (Markdown ingestion via `knowledge_sources.iter_documents`). Check: `scripts/validate_agent3_inputs.py`.
- Agent 3 pilot (milestone 4): `agents/advisor_contracts.py` (model I/O: draft v2, grounding judgment v2, ToT v1), `advisor_evidence.py` (freshness check, evidence ledger + agent-facing serialization, budgeted `ResearchTools`), `advisor_checks.py` (structural checks, final statements, authorization, temporal/severity/resolution, routing), `advisor_tot.py`, `advisor_pilot.py` (orchestration; `CrewAIClient` + `RequestGuard`: one HTTP request per stage). Runner `scripts/run_agent3_pilot.py`: zero calls by default (prints model and limits); `--scripted` offline; `--run` is **paid**. Scenarios in `data/evaluation/agent3_pilot_scenarios.json`. Card text comes only from statements the final grounding call judged SUPPORTED; announcements are never current handling by type.
- Dashboard (milestone 6): `src/threadsense/dashboard/` (`runs.py` read-only run catalog/evidence/thread views,
  `decisions.py` decision contracts + SQLite store, `decision_sources.py` export via the Markdown ingestion path and
  later snapshots, `app.py` FastAPI), `web/` (React/Vite/Tailwind/Framer Motion; `web/tests/` Playwright). Runners
  `scripts/run_dashboard.py`, `scripts/build_decision_snapshot.py`. Decision store `.state/dashboard/` (ignored).
  Labelled fixture run `tests/fixtures/dashboard_runs/` (builder `tests/fixtures/make_dashboard_fixture_run.py`).
- Full run (2026-11-05): `src/threadsense/execution/` (`guard.py` transport guard + request cache, `ledger.py` SQLite
  budget ledger, `store.py` content-addressed objects, `pricing.py` verified prices, `pipeline.py` stages snapshot ->
  agent1_interpret -> agent1_verify -> grouping -> agent2 -> agent3 -> finalize). Runner `scripts/run_threadsense_full.py`
  (`preflight` zero calls; `live --run` **paid**; `resume --reason`; `replay`/`render` network disabled; `branch`).
- `src/threadsense/legacy/` — frozen historical contracts/engines kept only for replay and fingerprints.
- `scripts/` — CLI entry points (table in README). `tests/` — offline; model calls are mocked.
- `data/fixtures/slack_generated/` — pipeline input (12 channels). `data/fixtures/slack/` is the old seed set used only by `main.py` and the generator.
- `data/knowledge/` — knowledge store (instructions, faq, decisions/<project>, `domain_lexicon.json`, `severity_rubric.py`).
- `data/processed/`, `data/experiments/` — frozen run outputs. `data/metadata/` — hash-bound review registries.
- `docs/` — Agent1/Agent2 summaries, `announcement-routing.md` (current data flow), `agent3-plan.md`, `repository-cleanup.md`,
  `agent3-acceptance.md` (acceptance report, scenario coverage, limitations) and `agent3-demo-walkthrough.md` (zero-call dashboard demo).

## Conventions

- Match the surrounding file's style; it varies (no formatter). Newer modules are compact, single-quoted.
- Contracts are versioned Pydantic models; add a new version rather than mutating a frozen one.
- Bounded model work: explicit request ceilings, zero retries, at most one revision, non-blocking failures (a failed item is recorded, never drops identities).
- Never drop members or review obligations: all 200 identities and 49 inherited Agent 1 obligations must survive every stage.
- Scripts are read-only by default; writes need `--write`/`--prepare`, live calls need `--run`. New runs write to **new** output directories.
- Severity is `UNKNOWN`/`UNASSESSED` until Agent 3; Agent 2 must not assess it.

## Do not edit

- `data/processed/**`, `data/experiments/**`, `data/metadata/**` — frozen, fingerprinted evidence. Never rewrite, re-hash or bypass fingerprint failures.
- `src/threadsense/legacy/**` and the 14 fingerprinted runner files (changing bytes invalidates historical preflights). `legacy/grouping_v1.py` and `data/metadata/historical/*.json` are byte-exact (`-text` in .gitattributes).
- `.env` (real keys; never print or commit). `uv.lock` except via `uv`. `.venv/`.
- `.gitattributes` EOL rules for `data/`: they reproduce the exact bytes each fingerprint was recorded on. Don't simplify them, and never `git add --renormalize` while working copies have stale line endings (refresh with `git checkout-index -f` first).

## Environment quirks

- Windows + PowerShell primary; README also targets macOS. Don't copy `.venv` between machines.
- System Git sets `core.autocrlf=true`. Frozen data was hashed with mixed line endings (Agent 1/fixtures/evaluation CRLF; Agent 2/metadata/experiments LF); per-path `eol` rules in `.gitattributes` override autocrlf so checkouts reproduce exact bytes on any OS.
- Long paths: `data/processed/*/records/<sha256>/…` exceed MAX_PATH in deep directories; create worktrees/temp copies at a short path (e.g. `D:\tsb`).
- `.cache/` holds old audit helpers and 32 access-denied pytest dirs; leave them.
- `.env` vars: `OPENAI_API_KEY`, `THREADSENSE_MODEL` (default `openai/gpt-4o-mini`), `THREADSENSE_VERIFIER_MODEL`, `OPENROUTER_API_KEY`. Terminal vars override `.env`. Frozen v3 preflight needs `gpt-4o-mini-2024-07-18` + verifier `gpt-4.1`.

## Current state (2026-10-29)

- Branch `agent3`. Agent 1 v3 and Agent 2 v7 closed. Announcement routing integrated (schema 8 / handoff v2 for new exports).
- Agent 3 milestones 2 and 3 done 2026-10-29: contracts, rubric binding, Markdown ingestion (40 files in `data/knowledge`, user-authored mock data; don't rewrite), and shared hybrid retrieval (`src/threadsense/retrieval/`, index in ignored `.index/retrieval/`, build with `scripts/build_retrieval_index.py`). Retrieval defaults: MMR lambda 0.9, `version_mode='current'` (superseded revisions/sections withheld before ranking; `history` for conflict research). Chunking `knowledge-chunks-v2` (FAQ question/answer units; 112 chunks).
- Milestone 4 (Advisor pilot) done 2026-10-29 and validated **offline only**: semantic stages are scripted (`tests/fixtures/agent3_pilot_scripted_judgments.json`); hardened the same day (final statement-level grounding, announcement applicability, member-level resolution, one HTTP request per stage); current output `data/experiments/agent3_pilot_offline_v2/` (`SCRIPTED_MOCK`; `offline_v1` is the pre-hardening run). Live command and limits: Milestone 4 "Live run" in the plan. One live run done (`data/experiments/agent3_pilot_live_v1/`, 15 requests, findings in the plan); further `--run`s are paid (ask first). The scripted evidence IDs are tied to the current index: a chunking/corpus change requires regenerating them (the real-embedding integration test fails when they drift). Correction pass (pilot v3) and a small paid model comparison (`data/experiments/agent3_model_comparison_v1/`, `scripts/run_agent3_model_comparison.py`, $0.40) done; findings in the plan. Completion pass (pilot v4: action sufficiency, scoped thread instructions, recurrence split, CrewAI Agent/Task stages) and the Sol acceptance run (`data/experiments/agent3_acceptance_v1/`, 21 requests, $1.07) done; findings in the plan. Closeout patch 2026-10-30 (pilot v5: role-based card prose with canonical-ID attributions, AdviceCard v2 with labelled related threads, premise dependency order, ToT fallback, agreeing current sources): zero-call replay `data/experiments/agent3_acceptance_replay_v1/`, live run `data/experiments/agent3_closeout_v1/` (`scripts/run_agent3_closeout.py`, 18 requests, $0.95). Readability pass 2026-10-30 (pilot v6, AdviceCard v3: TL-facing summary/instruction/rationale/draft/review notes, IDs and enums structured only; writing guide + STYLE ONLY examples, prompts v6.1; input cap 24k; review reasons from validated results): replays `agent3_closeout_replay_v1/`, `agent3_readability_replay_v1/`, live `agent3_readability_v1/` (`scripts/run_agent3_readability.py`, audio + Submit, 6 requests, $0.37). Milestone 5 done 2026-10-30: LangGraph overnight workflow `agents/overnight.py`, runner `scripts/run_agent3_overnight.py` (zero calls by default; `--scripted`, paid `--run` with `--max-requests`/`--max-cost`, `--resume`), offline full handoff `data/experiments/agent3_overnight_offline_v2/` (87 work items, accounting COMPLETE), live smoke `agent3_overnight_smoke_v1/` (audio + Submit, 8 requests, $0.53). Run state lives in the run directory (manifest fingerprints, budget/ledger, in-flight markers); it is not a knowledge store. Milestone 6 done 2026-10-30 (offline-validated): dashboard + TL decision loop (see Layout); decisions are
append-only SQLite rows wrapping DecisionRecord / ReviewAction (contracts `dashboard-tl-decision-v1`,
`dashboard-model-review-action-v1`), idempotency key + expected head on every save, approval never executes;
decisions reach retrieval only via a NEW snapshot at a later cutoff (`retrieval.index.plan(decision_root=...)`;
the active `.index/retrieval` is never modified). Open evaluation case (audio trial-outcome follow-up miss):
`data/evaluation/agent3_open_evaluation_cases.json`. **Next: Milestone 7 (demo validation) not started; a full live
overnight run needs a cost cap (estimate in the plan).** Milestone 7 done 2026-10-30: decisions bound to the immutable
run instance (`run_key#run_instance`; contracts v2 with `namespace` operational/demo/test and `judgment_provenance`;
default snapshots ingest operational = live-run decisions only); one decision record per decision (shared
`event_series_id`, history kept); `run_agent3_overnight.py --index-dir` selects an immutable snapshot checked against
its own manifest sources (`retrieval.index.snapshot_sources`), recorded in the run manifest with `fixture_sha256`;
snapshots carry earlier announcements as `prior_announcement` (same ANNOUNCEMENT use as when current; Oct 2 index unchanged); prompts v6.2
(absence wording + `ABSENCE_OVERCLAIM`); recorded-link lookup `retrieval/related.py` evaluated, not enabled. Outputs:
`agent3_feedback_loop_offline_v1` (decision -> later overnight retrieval), `agent3_scenario_coverage_v1` (matrix
`data/evaluation/agent3_demo_scenarios.json`), `agent3_related_lookup_eval_v1`, live `agent3_final_eval_v1` (nine
scenarios, 30 requests, $1.56). Repair pass 2026-10-30: prompts v7 / draft v7 (`intervention_need` judged as
`action:need` in the final grounding; NO_INTERVENTION_NEED withholds the action without failing grounding; recorded v6
drafts replay under `LEGACY_LABELS`), bounded retrieval expansion in `ResearchTools` (type coverage + recorded-link
related records, `retrieved_as`; off in replays), decision contract v3 `decision_origin` (DEMO_SCRIPT/TEST never
operational), partitive-plural checker fix; live comparison `agent3_repair_eval_v1` (6 cases, 16 requests, $0.97).
Repair pass 2 (offline): prompts v8 / draft v8 (`action_choice` ToT trigger), ToT v3 (`advisor_tot.select`: incumbent,
pre-grounding replacement, close calls kept), `temporal_decision` + non-competing recorded states in `temporal_check`,
member disagreement is not a source conflict, temporal golden set `data/evaluation/temporal_golden.json` with
`scripts/evaluate_temporal.py` (14/15; T02 policy gap). Repair pass 3: enacted-decision eligibility in
`retrieval/versions.py` (`ENACTED_DECISION` use; unenacted supersession stays flagged; WITHDRAWN states), close calls
surviving grounding go to Needs Review (`advisor_tot.choice_after_grounding`), grounding v5 source consistency (prompts
v9); golden v2 14/15 (T02 lacks enactment evidence); live `agent3_policy_eval_v1` (4 cases, 8 requests, $0.46).
Cleanup 2026-10-31 (offline): policy-aligned temporal benchmark `data/evaluation/temporal_golden_policy_v1.json` (17
cases; T02 split into negative T02N + positive T02A/T02E; v1 file and its 14/15 reports unchanged; report
`agent3_temporal_policy_v1`, 17/17, not comparable to v1); sentence-level summary judgment (draft v9 `summary_sentences`,
prompts v10: each sentence condenses named claims, is judged as `summary:sN` and shown only if SUPPORTED); `Retriever`
closes its Chroma client inside its constructor.
Live summary check `agent3_summary_eval_v1` (JSON-versus-prose + Submit, 4 requests, $0.25): group sentences accurate;
one Submit sentence withheld while the other was shown; Submit action withheld this run; revision blocked by the input cap.
Submit repair (prompts v11, evidence view v2): compact model-facing evidence (revision request 24,405 -> 20,344 tokens,
`scripts/measure_revision_request.py`, `agent3_revision_payload_v1`), authorship separate from authority, destination rules,
stricter replay reuse; live `agent3_submit_repair_v1` (2 requests, $0.13): summary 3/3 shown, action still withheld
(engineer request mislabelled THREAD_INSTRUCTION).
Request classification (prompts v12, evidence view v3): non-team-lead requests are INCIDENT_FACT; recorded pre-grounding
relabel for category-only mismatches; live `agent3_request_kind_v1` (3 requests, $0.22): request SUPPORTED, summary 3/3,
action still withheld (announcement description filed as GUIDANCE listed as a premise).
Source facts (prompts v13, draft v10): SOURCE_FACT claims, announcements govern only what they direct, action
context_claim_ids; live `agent3_source_fact_v1` (2 requests, $0.14): description accepted, summary 3/3, action withheld
because the judge treated "report to engineering" as an unestablished destination (v11 grounding wording gap).
Recipient/route rule (prompts v14, one `ROUTING_RULE` in draft and grounding): a functional recipient needs incident
evidence, not an intake route; concrete or mandatory routes need their own premise; live `agent3_recipient_routing_v1`
(2 requests, $0.14): every statement SUPPORTED, escalation to engineering displayed.
Refinement 2026-11-04 (offline): dashboard "What to review" panel (`dashboard/review.py`), complete instruction + Copy
draft in the overview, provenance per card; prompts v15 (writing guide only, not validated live); opt-in adaptive
research `agents/advisor_research.py` (`advise(research_mode='react')`, off by default) with offline comparison
`agent3_react_comparison_v1` (recorded-link expansion already recovers the audio outcome).
Flag provenance (2026-11-04, offline): `agents/flag_provenance.py` (FlagProvenance / CardDependencies v1, derived from
each run's own handoff binding; card bytes unchanged), projection gaps shown as "Topic grouping needs review" (no queue
item), human labels `data/evaluation/agent3_flag_dependence_labels_v1.json`, report `scripts/report_flag_dependence.py`.
Production routing unchanged; code never records a flag as independent.
Flag-impact assessment (offline shadow): opt-in `advise(flag_impact=True)` adds `flag_impacts` to the one grounding request
(GroundingJudgmentV6), validated by `agents/flag_impact.py` into a bound FlagImpactRecord; routing ignores it. New runs save
the exact Agent 1 context sent to drafting (`agent1_context`, boundary-checked). Largest grounding request with it: 20,627 / 24,000.
Live shadow `agent3_flag_impact_live_v1` (`run_agent3_overnight.py --flag-impact`; JSON-versus-prose, tie, repeated ending;
6 requests, $0.37): 5 flags, 4 AFFECTS agreed with the source check; the tie central-question INDEPENDENT became UNKNOWN
because `action:context` was not catalogued. Reliability pass (offline, closeout): one element catalogue
(`flag_impact.catalogue`), discarded-attempt findings kept as PriorFinding (FlagProvenance v2: OPEN / CORRECTED / SUPERSEDED /
UNCERTAIN), FlagImpactAssessment/Record v2 with finding_ids and deterministic references, grounding v7; recorded live flag
judgments need a new judgment (statement verdicts stay reusable). Report and corrections to the live review:
`data/experiments/agent3_flag_impact_reliability_v1/`. **Feature status: experimental, opt-in, shadow only; routing unchanged.**
Flag-impact milestone closed (commit `4df65ef`). End-to-end evaluation run once (live `data/experiments/agent3_e2e_eval_v1/`, 8 items, 17 requests, $0.93; expectations frozen before the run, inspection in `evaluation.json`).
Presentation pass (2026-11-05, offline): draft v11 `detail_sentences` (opened card "What happened", each judged as DETAIL, non-blocking), judged NO_ACTION reason (`action:no_action`, NO_ACTION_RATIONALE, non-blocking), AdviceCard v4 (`details`, `next_step`: ACTION_RECOMMENDED / NO_ACTION_NEEDED / NO_INTERVENTION_PROPOSED / RECOMMENDATION_WITHHELD / NO_RECOMMENDATION_AVAILABLE; review status unchanged), prompts v18 (grounding rules changed, so earlier recorded verdicts are not reused in replay), pilot v7. v3 cards load unchanged; the dashboard derives their state from the saved result (`runs.presentation`). Prepared demo run `data/experiments/agent3_presentation_prepared_v1/` (PREPARED fixture, not model output). Live acceptance `data/experiments/agent3_v18_acceptance_v1/` (same 8 items, 16 requests, $0.86, accounting COMPLETE, queue 52; development evaluation in `evaluation.json`): no blocking unsupported content identified in the developer's inspection; one potentially misleading historical phrase (Submit, "at its September 28 close") passed grounding and is recorded as a wording defect; both NO_ACTION_NEEDED states judged SUPPORTED. Flagged-thread status sentence now built from saved verdicts (`dashboard.checks.checked_parts`). **Milestone closed for the local capstone/demo scope** (`ACCEPTANCE.md` in that run directory).
Further `--run`s are paid (ask first). Full plan: [docs/agent3-plan.md](docs/agent3-plan.md).
Full live run 2026-11-05 `data/experiments/threadsense_full_v1/` (fresh Agent 1 -> Agent 3 over `slack_generated_demo`,
937 requests, $15.32 of a $39 ceiling): 177/178 accepted by Agent 1 (1 AUTHORITY_INELIGIBLE rejection recorded as
unfinished), 76 groups, 81 cards (61/8/12), 37 queue items, accounting COMPLETE; network-disabled replay
`threadsense_full_v1_replay/` (0 calls, 89/89 artifacts semantically identical). Report `ACCEPTANCE.md` in the run dir.
Briefing repair 2026-11-05 (offline): briefing-routing-v1 (`agents/briefing_policy.py`, AdviceCard v5) separates
briefing relevance from recommendation availability; OBSERVATION needs a supported no-action reason (root cause:
`assemble_card` used Observation as the fallthrough, now fixed for new runs); derived run
`data/experiments/threadsense_full_v1_briefing_v1/` (`scripts/derive_briefing_repair.py`; 5 Observation -> Needs Review,
2 greetings out of the brief, 79 in the brief; relevance labels `data/evaluation/briefing_relevance_labels_v1.json`,
developer audit, unconfirmed). The parent run is unchanged.
Closeout 2026-11-06 (offline): briefing-routing-v2 (labels `briefing_relevance_labels_v2.json`: audited, input-bound,
no automatic relevance classifier; ROUTINE_ADMIN keeps an open status in history, ROUTINE_NOTICE checked against the saved
cutoff, audit evidence must be SUPPORTED); derived run `threadsense_full_v1_briefing_v2/` (77 in the brief 66/8/3, 4 in
history: 2 greetings, avatar, tie threshold); "Pending follow-up" UI wording. v1 labels and run kept unchanged.
Relevance + consolidation (2026-11-06, offline; pipeline `threadsense-full-run-v2` for new runs, v1 runs replay unchanged):
Agent 1 judges relevance in its interpretation request (`agents/thread_relevance.py`, agent1-relevance-v1; runner flag
`--relevance`; the 14 fingerprinted Agent 1 files are unchanged), zero-call stage `agent1_relevance` verifies it and writes
the clustering input + `processing_history.json` (identities and obligations kept; Agent 3 queues them as
`inherited_agent1_review_processing_history`); `agent2_consolidate` (`agents/topic_merge.py`, agent2-consolidation-v1,
handoff v3, bounded sets, whole-group validation) merges the same issue across candidate groups; Agent 3 advises a
consolidated topic as one work item (CardLineage v3 fields). Shared actions: `agents/action_coordination.py` (exact
target match only, never a shared cause). Cached rebuild `scripts/derive_consolidated_run.py` ->
`data/experiments/threadsense_full_v1_consolidated_v1/` (audited thread labels `agent1_thread_relevance_labels_v1.json`,
prepared decisions `agent2_consolidation_decisions_v1.json`; 63 briefing items = 49 reused cards + 14 consolidated issues
pending fresh grounding over 29 original cards; 3 threads in processing history; 1 shared action). Targeted Agent 3
refresh (paid, not run): command in that run's `REVIEW.md`, 56 requests max, --max-cost 4.00.
Combined briefing + repairs (2026-11-06, offline after the paid refresh `threadsense_full_v1_consolidated_refresh_v1`,
14 consolidated issues, 32 requests, $2.23): `scripts/derive_combined_brief.py` -> `data/experiments/threadsense_full_v1_combined_v1/`
(63 items 53/7/3 = 49 reused + 14 refreshed; 29 replaced cards only as lineage, not served as cards; 177 threads, 37 review
items; `REVIEW.md`). Pilot v8 checks: author counts only for claims about authors/reporters (`advisor_checks.about_authors`),
agreeing current sources + out-of-running items resolve a declared conflict, UNDETERMINED with agreeing rule sources is
`DOCUMENTATION_STATUS_UNRESOLVED`, partially pending grounding withholds only the unjudged statements. Same-rules replay in
`ReplayClient` (current grounding contract and inputs: premises, sufficiency and source consistency reused as recorded;
a rejected-then-pending premise leaves a SUPPORTED verdict). `scripts/replay_overnight_topic.py` replays consolidated items;
`scripts/reground_topic.py` plans/sends one grounding request (format-card candidate wording
`data/evaluation/agent3_format_card_wording_v1.json`, pending grounding). Relevance stage v2: model exclusions need the
semantic verifier (`thread_relevance.assess_exclusion`, agent1-relevance-verification-v1). Observation demo fixture (hand-written,
test namespace): `tests/fixtures/observation_demo_runs/` (builder `tests/fixtures/make_observation_demo_fixture.py`).
Demo baseline (2026-11-06): `data/experiments/threadsense_full_v1_combined_v2` (combined-briefing-v2: 63 items 52/8/3; the
overlap and format cards replaced by targeted live re-groundings `data/experiments/agent3_reground_v1/`, 2 requests, $0.094,
reproduced offline before use; format card has 3 human edits verified by the live model + one TL suggestion not judged
`data/evaluation/agent3_tl_suggestions_v1.json`; other 93 cards byte-identical to v1). Walkthrough section 0 in
`docs/agent3-demo-walkthrough.md`. Agent 1 exclusion checks: one verifier request per proposed exclusion, exercised only with
prepared responses.
Agent 1 verification of a new run receives a derived discussion view (`pipeline.discussion_view`) through the runner's
module constants; Agent 2 `execute_batch` refuses existing dirs, so its resume uses a new attempt dir with cache hits.
- Agent 3 input: `data/processed/agent2_handoff_v2_projection/` (schema 8 / handoff v2, a zero-call projection of the v7 release; load with `advice_inputs.load_effective_view`): 81 groups / 79 topics / 161 assigned + 17 unassigned / 41 + 8 announcement-route obligations / 3 carried cautions. The frozen v7 release (handoff v1: 90 / 97 / 49 / 3 / 41) is unchanged.
- Demo Slack input: `data/fixtures/slack_generated_demo/` (201 threads / 517 messages, cutoff `2026-10-02T12:00:00Z`); the original `slack_generated/` (200 / 516) stays unchanged.
- LangGraph 1.2.18 (Milestone 5) and FastAPI 0.162.0 (Milestone 6) installed; frontend toolchain in `web/` (npm). Chroma is a direct dependency; BM25 is in-house.
- 2026-10-28 cleanup archived superseded runs to `D:\Christie\2026_AgenticAI\threadsense-archive-20261028\` (also local tag `pre-cleanup-20261028`).

## Known issues

- Frozen results verified 2026-10-28 with real loaders: Agent 2 v7 = 90 / 97 / 49 / 3 / 41; v6 = 90 groups, 10 applied obligations; Agent 1 v3 effective 81 VERIFIED / 70 CORRECTED / 49 NEEDS_REVIEW (automated 82 / 71 / 47).
- `data/processed/agent2_final_v6/combined_review_supplement.json` records its run as an absolute `D:/Christie/...` path, so v6 review findings only apply in this exact checkout location. Several legacy tests likewise fail in a clone at another path.
- Agent 1 v3 preflight (`run_agent1_verification.py --dry-run --output-dir data/processed/agent1_verified_v3`) refuses with "code ... changed": expected since the routing integration; never retarget frozen dirs.
- Intermittent `PermissionError: [WinError 5]` on `os.replace` (atomic writes in `topic_pipeline` / Agent 1 verification) when pytest's `--basetemp` is inside this VS Code-watched repo: an AV/indexer/watcher lock on fresh temp files. Worst after mass file changes. Verify by rerunning, or with `--basetemp` outside the repo. Measured 2026-10-29 on `test_200_mixed_mocked_outcomes…` (about 800 replaces per test): 3/20 failures inside the repo (all WinError 5 on `content_review_report.json`), 0/20 outside; the locking process is not identified.
- `scripts/validate_threadsense_dataset.py` fails: thread `1790941015.000132` is unresolved in the blueprint but has a TL reply/approval. Relevant to the Agent 3 milestone 1 data audit.
- `docs/repository-cleanup.md` (2026-10-22 section) links to deleted docs; `agent1-pilot-content-review.json` now lives in `data/metadata/historical/`.
- `data/knowledge/severity_rubric.py` (TL-owned; don't edit policy text): `severity-rubric-v3-semantic-signals`. `get_rubric_for_project` returns the shared default for every project (`rubric_scope: SHARED_DEFAULT`).
- `data/evaluation/domain_lexicon.json` duplicates `data/knowledge/domain_lexicon.json` (evaluation copy is not a model input).
- Agent 3 plan refers to `mock_knowledge/`; the repo uses `data/knowledge/`.
- ChromaDB 1.5.9 HNSW queries intermittently fail ("Nothing found on disk"); retrieval ranks dense results by exact cosine over Chroma-stored embeddings instead. Don't switch back to `collection.query` without retesting. The same error on `collection.get()` when opening an index right after a same-process build was traced (2026-10-29) to `build_index` leaving its client in Chroma's per-path system cache (`del` does not close it); fixed with `client.close()`. Reproducer `tests/repro_chroma_reopen.py`: unclosed 10/320 failures, closed 0/260. Always `close()` Chroma clients you create in-process. A second recurrence (2026-10-31) was different: a second `Retriever` on the same path while the first was alive shared its cached Chroma system and failed the same way (`second_open` 3/40, 6/120; closed first 0/120); `Retriever` now reads the embeddings and closes its client before its constructor returns or raises (0/120 after). `tests/test_retrieval_client_lifetime.py` checks that no system stays cached.
- 8 projected Agent 2 groups have no reusable taxonomy (their saved v7 responses also covered announcement members); their 17 members stay unassigned until a new run or an approved projection rule.
