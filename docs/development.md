# Development guide

How to work on ThreadSense without breaking saved results or spending money by accident.

## Setup and tests

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp D:/tsb/pytest-<name>
uv run --locked --extra dev python -m pytest tests/test_dashboard.py      # one file
```

- Use a new `--basetemp` each time: pytest deletes it at startup. A directory outside the repository avoids Windows
  file locks (see below).
- The full suite has about 1,270 tests and takes around 16 minutes. Tests are offline; model calls are mocked.
- Frontend: `npm --prefix web ci`, then `npm --prefix web run test:unit` (view model, no browser),
  `npm --prefix web run build && npm --prefix web run test:ui` (Playwright with system Chrome), and
  `npm --prefix web run build:demo && npm --prefix web run test:demo` (static demo).
- No linter or formatter is configured; match the style of the file you are editing.
- Dependency changes go in `pyproject.toml` and `uv.lock` together (`uv lock`, never by hand).

## Paid model calls

Scripts make no model calls and write nothing by default:
- writing needs `--write` (or `--prepare`), always to a **new** output directory;
- live calls need `--run`, and Agent 3 and full runs also need `--max-requests` / `--max-cost`.

Agent 1's original demo and baseline runners are the exception: they call the model unless given `--inspect` or
`--dry-run`. The zero-call checks are `--dry-run`, `--inspect`, `--check-input` and each runner's default plan mode.

Credentials live in `.env` (copy `.env.example`): `OPENAI_API_KEY`, `THREADSENSE_MODEL` (default
`openai/gpt-4o-mini`), `THREADSENSE_VERIFIER_MODEL`, `OPENROUTER_API_KEY`. Terminal variables take precedence. Never
commit `.env`.

## Frozen files

Saved runs are bound to the exact bytes of their inputs and code. Changing those bytes makes the runs fail their
integrity checks, so do not edit:

- `data/processed/**`, `data/experiments/**`, `data/metadata/**`: saved outputs and review registries. Never rewrite
  or re-hash them, and never bypass a fingerprint failure.
- `src/threadsense/legacy/**`: historical contracts kept for replay.
- Source files whose hashes are recorded in run manifests:
  - the `CODE_FILES` list in `src/threadsense/agents/topic_pipeline.py`;
  - the `code_files` list in `scripts/run_agent1_verification.py`;
  - `CONTROLLER_FILES` in `src/threadsense/agents/topic_continuation.py`;
  - `scripts/run_thread_grouping.py`, `scripts/run_agent1_batch.py`;
  - `src/threadsense/experiments/prose_comparison.py`;
  - the controller functions in `src/threadsense/agents/advisor_tot.py` and `src/threadsense/agents/tot_policy.py`.

  Even a comment change in these files invalidates historical preflights.
- `.gitattributes`: its per-path line-ending rules reproduce the bytes each fingerprint was recorded on. Never run
  `git add --renormalize` while working copies have stale line endings; refresh them with `git checkout-index -f`
  first.
- `data/knowledge/`: the hand-written knowledge store. Changing it changes the retrieval index, and the scripted
  evidence IDs in `tests/fixtures/agent3_pilot_scripted_judgments.json` would then need regenerating.
  `severity_rubric.py` is owned by the team leads.

## Conventions

- Contracts are versioned Pydantic models. Add a new version; don't change a released one.
- Model work is bounded: explicit request ceilings, zero retries, at most one revision. A failed item is recorded,
  never dropped.
- Every stage keeps all 200 thread identities and the 49 inherited Agent 1 review obligations.
- Severity stays `UNKNOWN` / `UNASSESSED` until Agent 3; Agent 2 must not assess it.
- Dashboard decisions are append-only, use an idempotency key and an expected head, and never execute anything.
  They reach retrieval only through a new snapshot at a later cutoff.

## Environment notes

- **Line endings.** Git uses `core.autocrlf=true` on Windows. Frozen data was hashed with mixed line endings, and the
  per-path `eol` rules in `.gitattributes` restore the exact bytes on any OS.
- **Long paths.** Some `data/processed/*/records/<sha256>/…` paths exceed Windows MAX_PATH. Put worktrees and temp
  copies at a short path such as `D:\tsb`.
- **Windows file locks.** pytest occasionally fails with `PermissionError: [WinError 5]` on `os.replace` when
  `--basetemp` is inside the repository (an indexer or antivirus lock). Rerun it, or keep `--basetemp` outside the repo.
- **Chroma.** HNSW queries in ChromaDB 1.5.9 fail intermittently, so dense ranking uses exact cosine over the stored
  embeddings. Always `close()` a Chroma client you create in-process; `tests/test_retrieval_client_lifetime.py` and
  `tests/repro_chroma_reopen.py` cover this.
- **Agent 1 v3 preflight** (`run_agent1_verification.py --dry-run --output-dir data/processed/agent1_verified_v3`)
  refuses with "code … changed". This is expected since announcement routing was added; never retarget frozen
  directories.
- **Checkout location.** `data/processed/agent2_final_v6/combined_review_supplement.json` records an absolute path,
  so a few legacy tests only pass in the original checkout location.
- **Frozen preflights.** The v3 preflight needs `gpt-4o-mini-2024-07-18` with verifier `gpt-4.1`.
- `.cache/` holds old local helper files and some locked pytest directories; it is ignored and can be left alone.
