# ThreadSense

Multi-agent pipeline that turns Slack threads from four annotation projects
(audio_multimodal, multilingual_eval, response_preference, safety_classification)
into a morning brief for team leads. Python 3.13, CrewAI + LiteLLM, Pydantic v2,
sentence-transformers/scikit-learn for grouping. Data is synthetic Slack fixtures.

Pipeline: **routing** (announcement channels → knowledge-source JSON; discussions → agents)
→ **Agent 1** interpret + verify (done, v3) → **grouping** → **Agent 2** taxonomy
(done, v7) → **Agent 3** research / severity / AdviceCards (pilot built, offline-validated) → dashboard (planned).

## Commands

```sh
uv sync --locked --extra dev                                   # install (no activation needed)
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-<name>
uv run --locked --extra dev python -m pytest tests/test_x.py   # single file
```

- Always pass a **fresh** `--basetemp .cache/pytest-<name>`: pytest wipes it at start.
- Full suite: 732 tests, ~7 min, all expected to pass. Intermittent `WinError 5` on `os.replace` is a Windows file lock (see Known issues), not a code failure.
- No linter/formatter configured. No build step beyond the editable install.
- Zero-call checks: `--dry-run`, `--inspect`, `--check-input` flags (list in README). Anything with `--run`, or Agent 1 without `--dry-run`/`--inspect`, makes **paid model calls** — never run those without asking.
- Dependency changes go in `pyproject.toml` and `uv.lock` together.

## Layout

- `src/threadsense/` — package. `routing.py`, `source_ingestion.py`, `knowledge_sources.py` (ingestion contract for Agent 3 retrieval), `adapters/mock_slack.py`, `topic_grouping.py`, `config.py` (.env + model selection).
- `src/threadsense/agents/` — current Agent 1 (`thread_interpreter`, `interpretation_*`, `verification_*`) and Agent 2 (`topic_taxonomy`, `topic_contracts`, `topic_pipeline`, `topic_effective`). See its README.
- Agent 3 (milestone 2): `agents/advice_contracts.py` (AdviceCard/DecisionRecord/AnnouncementRecord/ModelReviewItem v1), `agents/advice_inputs.py`, `severity_rubric.py` (loader for the TL rubric), `knowledge_markdown.py` + `knowledge_corpus.py` (Markdown ingestion via `knowledge_sources.iter_documents`). Check: `scripts/validate_agent3_inputs.py`.
- Agent 3 pilot (milestone 4): `agents/advisor_contracts.py` (model I/O: draft v2, grounding judgment v2, ToT v1), `advisor_evidence.py` (freshness check, evidence ledger + agent-facing serialization, budgeted `ResearchTools`), `advisor_checks.py` (structural checks, final statements, authorization, temporal/severity/resolution, routing), `advisor_tot.py`, `advisor_pilot.py` (orchestration; `CrewAIClient` + `RequestGuard`: one HTTP request per stage). Runner `scripts/run_agent3_pilot.py`: zero calls by default (prints model and limits); `--scripted` offline; `--run` is **paid**. Scenarios in `data/evaluation/agent3_pilot_scenarios.json`. Card text comes only from statements the final grounding call judged SUPPORTED; announcements are never current handling by type.
- `src/threadsense/legacy/` — frozen historical contracts/engines kept only for replay and fingerprints.
- `scripts/` — CLI entry points (table in README). `tests/` — offline; model calls are mocked.
- `data/fixtures/slack_generated/` — pipeline input (12 channels). `data/fixtures/slack/` is the old seed set used only by `main.py` and the generator.
- `data/knowledge/` — knowledge store (instructions, faq, decisions/<project>, `domain_lexicon.json`, `severity_rubric.py`).
- `data/processed/`, `data/experiments/` — frozen run outputs. `data/metadata/` — hash-bound review registries.
- `docs/` — Agent1/Agent2 summaries, `announcement-routing.md` (current data flow), `agent3-plan.md`, `repository-cleanup.md`.

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
- Milestone 4 (Advisor pilot) done 2026-10-29 and validated **offline only**: semantic stages are scripted (`tests/fixtures/agent3_pilot_scripted_judgments.json`); hardened the same day (final statement-level grounding, announcement applicability, member-level resolution, one HTTP request per stage); current output `data/experiments/agent3_pilot_offline_v2/` (`SCRIPTED_MOCK`; `offline_v1` is the pre-hardening run). Live command and limits: Milestone 4 "Live run" in the plan. One live run done (`data/experiments/agent3_pilot_live_v1/`, 15 requests, findings in the plan); further `--run`s are paid (ask first). The scripted evidence IDs are tied to the current index: a chunking/corpus change requires regenerating them (the real-embedding integration test fails when they drift). Correction pass (pilot v3) and a small paid model comparison (`data/experiments/agent3_model_comparison_v1/`, `scripts/run_agent3_model_comparison.py`, $0.40) done; findings in the plan. **Next: decide on the comparison findings (premise-dependency rule, recurrence voiding severity, model choice) before milestone 5 (LangGraph workflow).** Full plan: [docs/agent3-plan.md](docs/agent3-plan.md).
- Agent 3 input: `data/processed/agent2_handoff_v2_projection/` (schema 8 / handoff v2, a zero-call projection of the v7 release; load with `advice_inputs.load_effective_view`): 81 groups / 79 topics / 161 assigned + 17 unassigned / 41 + 8 announcement-route obligations / 3 carried cautions. The frozen v7 release (handoff v1: 90 / 97 / 49 / 3 / 41) is unchanged.
- Demo Slack input: `data/fixtures/slack_generated_demo/` (201 threads / 517 messages, cutoff `2026-10-02T12:00:00Z`); the original `slack_generated/` (200 / 516) stays unchanged.
- Planned stack not yet installed: LangGraph, FastAPI, React (Vite/Tailwind). Chroma is a direct dependency; BM25 is in-house.
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
- ChromaDB 1.5.9 HNSW queries intermittently fail ("Nothing found on disk"); retrieval ranks dense results by exact cosine over Chroma-stored embeddings instead. Don't switch back to `collection.query` without retesting. The same error on `collection.get()` when opening an index right after a same-process build was traced (2026-10-29) to `build_index` leaving its client in Chroma's per-path system cache (`del` does not close it); fixed with `client.close()`. Reproducer `tests/repro_chroma_reopen.py`: unclosed 10/320 failures, closed 0/260. Always `close()` Chroma clients you create in-process.
- 8 projected Agent 2 groups have no reusable taxonomy (their saved v7 responses also covered announcement members); their 17 members stay unassigned until a new run or an approved projection rule.
