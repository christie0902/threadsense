# ThreadSense

ThreadSense interprets Slack discussions and organizes canonical interpretations into
related topics. Agent 1's finalized v3 handoff contains **200 records: 81 VERIFIED,
70 CORRECTED and 49 NEEDS_REVIEW**, in 90 candidate groups.

Agent 2's corrected **v7 scope is taxonomy and cluster hygiene**: coherence,
splitting, concise reusable topic names and explicit outliers. It consumes Agent 1
summaries/questions, preserves full canonical records and all 49 inherited review
obligations passively, and uses one strict request per group without retries.
Independent deterministic severity is UNKNOWN because the canonical inputs lack
structured operational-impact signals. Agent 3 will own research, answer/policy
reassessment, final severity and recommendations.

The v7 offline refactor is complete; live taxonomy behavior remains unverified.
The prepared four-request pilot has **not** been executed. Historical v6 outputs
remain preserved, but their readiness conclusion is superseded by this scope change.
See the [current change report](docs/agent2-taxonomy-refactor.md) and
[operational guide](docs/agent2-offline-integration.md). Agent 3 and the dashboard
remain planned work.

## Maintained documentation

- [Setup and commands](#setup-and-configuration): this page.
- [Agent 1 workflow and downstream contract](docs/agent1-nonblocking-handoff.md):
  current behavior, read-only preflight, evidence, and next milestone.
- [Final Agent 1 results](docs/agent1-full-batch-results.md): request accounting,
  all twelve source-review outcomes, limitations, and artifact links.
- [Agent 2 taxonomy refactor](docs/agent2-taxonomy-refactor.md): current contract,
  offline checks, retained obligations and prepared pilot.
- [Historical Agent 2 v6 results](docs/agent2-milestone-results.md): preserved prior
  dataset and review evidence; superseded readiness conclusion.
- [Agent 2 run guide](docs/agent2-offline-integration.md): current inspection,
  passive effective export, retained obligations and bounded pilot preparation.
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
groups live in `data/processed/grouping/` as historical evidence. Agent 2 reads
`data/processed/agent1_verified_v3/interpretations.json` directly and uses the new
90 candidates in `data/processed/grouping_agent1_v3/`. It preserves all 49 inherited
review obligations through taxonomy assignments, rejection and recoverable failure.
Agent 2's model sees canonical summaries/questions and the approved glossary; original
Slack and evidence remain in the passive export. It does not generate another
interpretation, question inventory, answer judgment or research narrative.
The v7 pending preview is `data/processed/agent2_taxonomy_v7_offline/`; it contains no
live taxonomy assignments. Its effective view exposes `taxonomy_handoff`, not the
historical `research_handoff`. Preserve unassigned/rejected members for later work.

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
uv run --locked python scripts/prepare_agent2_grouping.py
uv run --locked python scripts/run_agent2_sample.py
uv run --locked python scripts/run_agent2_batch.py --dry-run --limit 0
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

The verification and Agent 2 runners require `--run` for live calls. Agent 2's
batch runner additionally requires the prepared pilot and explicit request ceiling;
each group gets one request, zero retries, and zero repairs. The original
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
| Historical grouping / canonical refresh | `scripts/run_thread_grouping.py`, `scripts/prepare_agent2_grouping.py` |
| Taxonomy Agent 2 | `scripts/prepare_agent2_input.py`, `scripts/run_agent2_sample.py`, `scripts/run_agent2_batch.py` |
| Retired compatibility command | `scripts/repair_agent2_sample.py` explains the v1-to-v2 migration and makes no calls |
| Retained benchmark | `scripts/run_prose_comparison_experiment.py` |
| Dataset authoring | `scripts/generate_thread_blueprint.py`, `scripts/generate_slack_fixtures.py` |
| Dataset checks | `scripts/validate_topic_catalog.py`, `scripts/validate_slack_fixtures.py`, `scripts/validate_threadsense_dataset.py` |

Agent 2 preparation is read-only unless `--write` or `--prepare` is supplied.
Dataset authoring writes files; it supports reproducibility, not regeneration of
the frozen corpus. New output directories keep historical results untouched.

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
