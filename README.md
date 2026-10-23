# ThreadSense

ThreadSense interprets Slack discussions and groups related questions for topic
analysis. Agent 1's finalized v3 handoff contains all **200 records: 81 VERIFIED,
70 CORRECTED, and 49 NEEDS_REVIEW**. The next milestone connects the existing
Agent 2 implementation to this canonical export while preserving review metadata.
Agent 3 retrieval and the briefing interface remain planned work.

## Maintained documentation

- [Setup and commands](#setup-and-configuration): this page.
- [Agent 1 workflow and downstream contract](docs/agent1-nonblocking-handoff.md):
  current behavior, read-only preflight, evidence, and next milestone.
- [Final Agent 1 results](docs/agent1-full-batch-results.md): request accounting,
  all twelve source-review outcomes, limitations, and artifact links.
- [Prose benchmark](experiments/prose_comparison_v1/README.md): retained synthetic
  cases, request isolation, scoring, and saved-response regression evidence.
- [Repository cleanup record](docs/repository-cleanup.md): removals, recovery,
  preservation checks, and validation results.

## Current architecture

The Slack adapter loads message text, authors, roles, and actual reaction users
and targets. Runtime terminology comes from `data/knowledge/domain_lexicon.json`;
`data/evaluation/` contains separate evaluation material, not model-request inputs.

Agent 1 verification joins the frozen interpretations to original Slack, analyzes
the source once, compares the current candidate's prose, and applies deterministic
checks. It permits **one revision maximum**, followed by a fresh candidate check;
a successful revision becomes CORRECTED. The bound is **four request attempts per
thread, zero retries and no fallback calls**. NEEDS_REVIEW retains the candidate
and evidence and does not interrupt subsequent threads.

The baseline lives in `data/processed/agent1_authority_fix/`; the 91 frozen
groups live in `data/processed/grouping/`. Existing Agent 2 loaders still use
those historical groups. Their connection to the finalized canonical export is
not implemented yet. All 200 verified/provisional records are available for that
connection in `data/processed/agent1_verified_v3/interpretations.json`.

## Setup and configuration

From this checkout's root on Windows or macOS:

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-current
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed.
The project selects Python 3.13 and installs the locked dependencies plus the
editable local package. No environment activation or PYTHONPATH setting is needed.
Use a dedicated pytest temporary directory: pytest clears `--basetemp` at startup.
The offline tests mock model requests and isolate saved credentials.

Select `.venv\Scripts\python.exe` in a Windows editor, or `.venv/bin/python` on
macOS. After pulling on another computer, repeat `uv sync --locked --extra dev`.
Keep each computer's environment local; do not copy `.venv` or its executable
launchers between Windows and macOS. Dependency changes belong together in
`pyproject.toml` and `uv.lock`.

If using pip, create a Python 3.13 virtual environment and run its interpreter
with `-m pip install -r requirements.txt`. That installs the declared ranges;
uv provides the versions recorded in the lockfile.

Create a local `.env` from `.env.example` only if it does not already exist, then
fill in `OPENAI_API_KEY=` there. Both agent factories read this file; you do not
need to paste keys into the terminal. Existing terminal variables take precedence.
The ignored `.env` stays local to each computer; never commit real credentials.

`THREADSENSE_MODEL` selects the interpreter/analyst model.
`THREADSENSE_VERIFIER_MODEL` selects the verifier, falling back to that model when
unset. OpenRouter routes use `OPENROUTER_API_KEY`. The finalized v3 fingerprints
require the original pins shown below, regardless of local defaults.

## Safe inspection commands

These commands inspect existing inputs without paid model calls:

```sh
uv run --locked python scripts/run_agent1_demo.py --inspect
uv run --locked python scripts/run_agent1_batch.py --dry-run --limit 1
uv run --locked python scripts/run_thread_grouping.py --check-input
uv run --locked python scripts/run_agent2_sample.py
uv run --locked python scripts/run_agent2_batch.py --limit 1
```

Read-only verification of the completed handoff, in PowerShell:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --content-review data/processed/agent1_full_batch_review_v3/content_review.json --output-dir data/processed/agent1_verified_v3
```

On macOS, set the same two variables with `export NAME='value'` before running
the identical uv command. Expected state: **200 compatible caches, zero unstarted
records, zero remaining model tasks**. Every future export refresh must load
**both review files**, including the full-batch disputes.

The verification and Agent 2 runners require `--run` for live calls. The original
Agent 1 demo and baseline runner have different defaults: omit `--inspect` or
`--dry-run` only when intentionally requesting model work. Grouping without
`--check-input` can load/download an embedding model and write outputs. Preserve
the frozen baselines when preparing any future run.

## Retained entry points

| Purpose | Entry points |
| --- | --- |
| Inspect fixtures | `main.py`, `scripts/run_agent1_demo.py --inspect` |
| Baseline interpretation | `scripts/run_agent1_batch.py` |
| Verification / canonical handoff | `scripts/run_agent1_verification.py` |
| Historical offline reconciliation | `scripts/reconcile_agent1_handoff.py` |
| Grouping | `scripts/run_thread_grouping.py` |
| Existing Agent 2 | `scripts/prepare_agent2_input.py`, `scripts/run_agent2_sample.py`, `scripts/run_agent2_batch.py`, `scripts/repair_agent2_sample.py` |
| Retained benchmark | `scripts/run_prose_comparison_experiment.py` |
| Dataset authoring | `scripts/generate_thread_blueprint.py`, `scripts/generate_slack_fixtures.py` |
| Dataset checks | `scripts/validate_topic_catalog.py`, `scripts/validate_slack_fixtures.py`, `scripts/validate_threadsense_dataset.py` |

The preparation and authoring scripts write files; they are not read-only checks.
Their presence supports reproducibility, not regeneration of the frozen corpus.

## Troubleshooting

- Missing `crewai`, `pydantic`, or `threadsense`: run the locked sync and use
  `uv run --locked python ...` or this checkout's editor interpreter.
- Missing pip inside `.venv`: uv environments need not include pip; use uv sync.
- A copied/broken environment or `encodings` startup failure: use a local Python
  3.13 installation and recreate the environment with uv. Keep the old environment
  separately until the replacement works.
- Windows pytest temporary-directory access errors: choose a new dedicated
  `--basetemp .cache/pytest-...` directory. Do not put project evidence there.
- Unexpected model or credential choice: terminal variables override `.env`.
- Incompatible v3 preflight: inspect the original model pins and code/input/package
  fingerprints. Do not alter saved metadata to force compatibility.
