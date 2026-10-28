# ThreadSense

Multi-agent pipeline that turns Slack threads from four annotation projects
(audio_multimodal, multilingual_eval, response_preference, safety_classification)
into a morning brief for team leads. Python 3.13, CrewAI + LiteLLM, Pydantic v2,
sentence-transformers/scikit-learn for grouping. Data is synthetic Slack fixtures.

Pipeline: **routing** (announcement channels → knowledge-source JSON; discussions → agents)
→ **Agent 1** interpret + verify (done, v3) → **grouping** → **Agent 2** taxonomy
(done, v7) → **Agent 3** research / severity / AdviceCards (planned) → dashboard (planned).

## Commands

```sh
uv sync --locked --extra dev                                   # install (no activation needed)
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-<name>
uv run --locked --extra dev python -m pytest tests/test_x.py   # single file
```

- Always pass a **fresh** `--basetemp .cache/pytest-<name>`: pytest wipes it at start.
- Full suite: 614 tests, ~5 min. **25 fail on this Windows checkout before any change** (see Known issues); compare against that baseline, don't chase them blindly.
- No linter/formatter configured. No build step beyond the editable install.
- Zero-call checks: `--dry-run`, `--inspect`, `--check-input` flags (list in README). Anything with `--run`, or Agent 1 without `--dry-run`/`--inspect`, makes **paid model calls** — never run those without asking.
- Dependency changes go in `pyproject.toml` and `uv.lock` together.

## Layout

- `src/threadsense/` — package. `routing.py`, `source_ingestion.py`, `knowledge_sources.py` (ingestion contract for Agent 3 retrieval), `adapters/mock_slack.py`, `topic_grouping.py`, `config.py` (.env + model selection).
- `src/threadsense/agents/` — current Agent 1 (`thread_interpreter`, `interpretation_*`, `verification_*`) and Agent 2 (`topic_taxonomy`, `topic_contracts`, `topic_pipeline`, `topic_effective`). See its README.
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

## Environment quirks

- Windows + PowerShell primary; README also targets macOS. Don't copy `.venv` between machines.
- System Git sets `core.autocrlf=true` + repo `* text=auto` → JSON checked out as CRLF. This is the root cause of the 25 baseline failures.
- Long paths: `data/processed/*/records/<sha256>/…` exceed MAX_PATH in deep directories; create worktrees/temp copies at a short path (e.g. `D:\tsb`).
- `.cache/` holds old audit helpers and 32 access-denied pytest dirs; leave them.
- `.env` vars: `OPENAI_API_KEY`, `THREADSENSE_MODEL` (default `openai/gpt-4o-mini`), `THREADSENSE_VERIFIER_MODEL`, `OPENROUTER_API_KEY`. Terminal vars override `.env`. Frozen v3 preflight needs `gpt-4o-mini-2024-07-18` + verifier `gpt-4.1`.

## Current state (2026-10-28)

- Branch `agent3`. Agent 1 v3 and Agent 2 v7 closed. Announcement routing integrated (schema 8 / handoff v2 for new exports).
- **Next: Agent 3 milestone 1** — audit knowledge + fixtures against the 8–9 demo cases, produce a coverage matrix, no data edits yet. Full plan: [docs/agent3-plan.md](docs/agent3-plan.md).
- Agent 3 input: `data/processed/agent2_taxonomy_final_v7/` via `topic_effective.load_effective_output` (currently fails on Windows, see below).
- Planned stack not yet installed: Chroma/FAISS + BM25, LangGraph, FastAPI, React (Vite/Tailwind).
- 2026-10-28 cleanup archived superseded runs to `D:\Christie\2026_AgenticAI\threadsense-archive-20261028\` (also local tag `pre-cleanup-20261028`).

## Known issues

- **Mixed line-ending fingerprints.** Agent 2 review registries hash LF bytes; Agent 1 evidence/fixtures were hashed as CRLF. On this checkout 25 tests fail (`Registered review supplement changed`, `Pilot inputs changed`, hash mismatches) and README's `load_effective_output(...final_v7)` check raises. Fix needs a deliberate decision (e.g. `data/** -text` + re-recording registry hashes), not a silent rewrite.
- Frozen results are intact modulo EOL: hashing with CRLF→LF, `load_effective_output` gives v7 = 90 groups / 97 topics / 49 obligations / 3 cautions / 41 review groups, and Agent 1 v3 = 81 / 70 / 49 (verified 2026-10-28).
- Agent 1 v3 preflight (`run_agent1_verification.py --dry-run --output-dir data/processed/agent1_verified_v3`) refuses with "code ... changed": expected since the routing integration; never retarget frozen dirs.
- Intermittent `PermissionError: [WinError 5]` on `os.replace` in `topic_pipeline.write_bytes` during the full suite (AV/indexer lock on fresh temp files); a different test each run, passes on rerun.
- `scripts/validate_threadsense_dataset.py` fails: thread `1790941015.000132` is unresolved in the blueprint but has a TL reply/approval. Relevant to the Agent 3 milestone 1 data audit.
- `docs/repository-cleanup.md` (2026-10-22 section) links to deleted docs; `agent1-pilot-content-review.json` now lives in `data/metadata/historical/`.
- `severity_rubric.py`: `get_rubric_for_project` returns only the default; its LOW default conflicts with UNKNOWN when evidence is insufficient.
- `data/evaluation/domain_lexicon.json` duplicates `data/knowledge/domain_lexicon.json` (evaluation copy is not a model input).
- Agent 3 plan refers to `mock_knowledge/`; the repo uses `data/knowledge/`.
