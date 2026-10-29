# ThreadSense

ThreadSense interprets Slack discussions and organizes canonical interpretations into
related topics. Agent 1's finalized v3 handoff contains **200 records: 81 VERIFIED,
70 CORRECTED and 49 NEEDS_REVIEW**, in 90 candidate groups.

Agent 2's corrected **v7 scope is taxonomy and cluster hygiene**: coherence,
splitting, concise reusable topic names and explicit outliers. It consumes Agent 1
summaries/questions, preserves full canonical records and all 49 inherited review
obligations passively, and uses one strict request per group without retries.
Prospective exports leave severity UNKNOWN/UNASSESSED and defer assessment to Agent 3.
The frozen v7 release retains its historical deterministic metadata. Agent 3 will own research, answer/policy
reassessment, final severity and recommendations.

Agent 2 v7 is **complete with nonblocking review**: 90 CONSOLIDATED groups,
97 topics and all 200 identities/49 inherited obligations retained. The accepted
four-group pilot was reused; 86 new requests completed, with no failed, interrupted
or unprocessed groups. Three naming cautions remain in the reviewed effective view.
See the [Agent 2 summary](docs/Agent2_Summary.md) and the
[current routing and knowledge-source guide](docs/announcement-routing.md).
Historical v6/v7 outputs remain preserved. Agent 3 and the dashboard remain planned.

## Maintained documentation

- [Agent source layout](src/threadsense/agents/README.md): current files and isolated historical compatibility.
- [Setup and commands](#setup-and-configuration): this page.
- [Agent 1 summary](docs/Agent1_Summary.md): historical workflow and results.
- [Agent 2 summary](docs/Agent2_Summary.md): completed taxonomy milestone.
- [Agent 3 plan](docs/agent3-plan.md): milestones for research, AdviceCards and dashboard.
- [Announcement routing and knowledge sources](docs/announcement-routing.md):
  current input boundary, daily commands, manual source format and severity migration.
- [Source JSON Schema](docs/knowledge-source.schema.json).
- [Prose benchmark](experiments/prose_comparison_v1/README.md).
- [Repository cleanup record](docs/repository-cleanup.md).

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
groups live in `data/processed/grouping/` as historical evidence. The historical Agent 2 release read
`data/processed/agent1_verified_v3/interpretations.json` directly and used the
90 candidates in `data/processed/grouping_agent1_v3/`. It preserves all 49 inherited
review obligations through taxonomy assignments, rejection and recoverable failure.
Agent 2's model sees canonical summaries/questions and the approved glossary; original
Slack and evidence remain in the passive export. It does not generate another
interpretation, question inventory, answer judgment or research narrative.
The finalized dataset is `data/processed/agent2_taxonomy_final_v7/`. Use its
`release_manifest.json` and `effective_output_reviewed.json`, or the mandatory
effective loader. Per-record `taxonomy_handoff` replaces the historical semantic
`research_handoff`. All 49 inherited obligations and three naming cautions remain
visible across 41 effective review groups. Preserve future unassigned/rejected
members for later work as well.

Prospective ingestion now routes announcement channels into durable knowledge
sources before interpretation. Discussions keep the existing path. The canonical
200 records partition into **178 discussions with 41 review obligations** and
**22 announcements with eight obligations**, all preserved. Projecting historical
groups yields 81 discussion candidates without computing embeddings. The prompt
and model response schema remain taxonomy v7; new unassessed-severity exports use
schema 8 / handoff v2. Historical release bytes and handoff v1 are unchanged.

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
uv run --locked python scripts/validate_agent3_inputs.py
```

The last command validates the Agent 3 inputs: knowledge corpus (Markdown and JSON),
severity rubric binding, demo Slack snapshot counts and the schema-8 Agent 2 handoff
projection (`scripts/project_agent2_handoff.py`, zero calls). See the
[Agent 3 plan](docs/agent3-plan.md#milestone-2-implemented).

Shared retrieval (local embeddings and Chroma, no paid calls; index in ignored `.index/`):

```sh
uv run --locked python scripts/build_retrieval_index.py
uv run --locked python scripts/evaluate_retrieval.py
```

The build is offline and needs the pinned `all-MiniLM-L6-v2` revision in the local
Hugging Face cache; add `--allow-download` once to fetch it. See
[Milestone 3](docs/agent3-plan.md#milestone-3-implemented-shared-hybrid-retrieval).

Agent 3 Advisor pilot (six handoff topics plus a negative control):

```sh
uv run --locked python scripts/run_agent3_pilot.py      # zero calls: freshness check, topics, initial retrieval, budget
uv run --locked python scripts/run_agent3_pilot.py --scripted tests/fixtures/agent3_pilot_scripted_judgments.json --write <new-dir>
```

`--scripted` is offline: prepared semantic judgments exercise the deterministic checks and
routing. `--run --write <new-dir>` makes **paid** model calls through CrewAI (bounded: at
most 4 per topic, 28 per run, one HTTP request per call with no retries; the zero-call default
prints the model and limits). See
[Milestone 4](docs/agent3-plan.md#milestone-4-implemented-bounded-advisor-pilot).

Inspect the historical effective handoff without regenerating it:

```powershell
uv run --locked python -c "from threadsense.agents.topic_effective import load_effective_output; v=load_effective_output('data/processed/agent2_taxonomy_final_v7'); print(len(v['records']), len(v['member_review_queue']), len(v['applied_content_obligations']))"
```

Expected: **90 groups, 49 inherited obligations, three naming cautions**. The new
routing code intentionally changes prospective input/configuration fingerprints.
Do not run a new producer against the frozen v3/v7 output directories or bypass
fingerprint failures. Historical metadata registries resolve through the verified
archive described in the current guide.

The verification and Agent 2 runners require `--run` for live calls. Agent 2's
batch runner additionally requires the prepared pilot and explicit request ceiling;
each group gets one request, zero retries, and zero repairs. The original
Agent 1 demo and baseline runner have different defaults: omit `--inspect` or
`--dry-run` only when intentionally requesting model work, and supply an explicit
timezone-aware `--cutoff`. Announcement-only extraction is always zero-call. Grouping without
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
