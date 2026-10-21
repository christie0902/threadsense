# threadsense

## Set up on Windows or macOS

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from the repository root on either computer:

```sh
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q
```

uv creates a local `.venv`, installs the project in editable mode, and installs
the versions recorded in `uv.lock`. It can download Python automatically if
needed. `.python-version` selects Python 3.13. CrewAI currently requires Python
below 3.14, so the project's supported version is 3.13.
No virtual environment activation or `PYTHONPATH` setting is needed.

For everyday testing, the shorter command is sufficient:

```sh
uv run --extra dev pytest -q
```

`--locked` is optional for local work. It checks that `uv.lock` agrees with
`pyproject.toml`; without it, uv can update the lockfile when dependencies change.

Run one test file with:

```sh
uv run --locked --extra dev python -m pytest -q tests/test_mock_slack_adapter.py
```

In your editor, select the interpreter inside this checkout's `.venv`:

- Windows: `.venv\Scripts\python.exe`
- macOS: `.venv/bin/python`

In a terminal with `.venv` activated, `python -m pytest` and `pytest` also work.
The pytest configuration adds `src` to the import path, discovers tests under
`tests`, and keeps its cache in `.cache/pytest`. Test fixture paths are resolved
from the test files, so running tests from an editor or the `tests` directory
does not depend on the current working directory.

## Moving between computers

Commit source changes together with `pyproject.toml`, `.python-version`, and
`uv.lock`. On the other computer, pull and run `uv sync --locked --extra dev`
again. Each checkout gets its own environment; never copy or commit `.venv`,
`venv`, `Lib`, executable launchers, or Python caches. Virtual environments
contain paths to a local interpreter and cannot be shared between Windows
and macOS.

When intentionally changing dependencies, update `pyproject.toml`, run
`uv lock`, and commit both files. `--locked` reports an outdated lockfile
instead of silently choosing different versions on another computer.

## Using pip instead

With a working Python 3.13 installation, create a new environment:

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

macOS:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

The pip setup reads dependency ranges from `pyproject.toml`; use uv for the
exact dependency versions in `uv.lock`.

## CrewAI

CrewAI is included in the project dependencies and installed by `uv sync`.
Verify the installation without calling a model:

```sh
uv run python -c "from crewai import Agent; print('CrewAI is ready')"
```

Use `uv add package-name` to add future dependencies so they are recorded in
`pyproject.toml` and `uv.lock` for both computers. Avoid a bare `pip install`,
which can target a different interpreter and does not update the shared lockfile.

### API keys for both agents

Create `.env` in the repository root by copying `.env.example`, then paste your
OpenAI API key after `OPENAI_API_KEY=`. Both the interpreter and topic analyst
automatically read this file, including when launched from another directory.

```dotenv
OPENAI_API_KEY=your-key-here
THREADSENSE_MODEL=openai/gpt-4o-mini
```

Save the file and run the interpreter as usual:

```sh
uv run python scripts/run_agent1_demo.py
```

The batch interpreter uses the same configuration:

```sh
uv run python scripts/run_agent1_batch.py
```

Check the analyst's input with `uv run python scripts/run_agent2_sample.py`.
Add `--run` to call the model. The analyst refuses to overwrite an existing
`data/processed/agent2_sample/topic_analysis.json`; review and move that result
before intentionally rerunning the sample.

You do not need `--env-file` or terminal key prompts. If the selected key is
missing, the runner stops with a message pointing to `.env`. Variables already
set in the terminal take precedence over `.env`; start a fresh terminal if
old settings are overriding your saved configuration.

`.env` is ignored by Git and stays on this computer. Create and fill in a local
`.env` on your Mac as well. Commit `.env.example` with blank key fields only.

To use OpenRouter instead, set `THREADSENSE_MODEL=openrouter/openrouter/free`
and fill in `OPENROUTER_API_KEY` in the same `.env` file. Both agents select the
key for the configured provider. The `crewai[litellm]` integration is already
included in this project's dependencies.

The demo uses LiteLLM with ordinary text completions. It asks for a JSON object
and validates the result locally with Pydantic, including the thread ID and
authority evidence references. It does not require a free provider to implement
OpenAI's strict JSON-schema response format. Provider errors report the HTTP
status and available error details without repeating a failed agent run.

To inspect the fixture without a key or model request:

```sh
uv run python scripts/run_agent1_demo.py --inspect
```

## Agent 1 verification and bounded correction

The active verification workflow checks saved Agent 1 interpretations against
their original Slack threads, makes at most one targeted revision, and checks
that revision once more. Results are `VERIFIED`, `CORRECTED`, or `NEEDS_REVIEW`;
every selected thread is retained, including provisional results.

Run the offline preflight from the project root:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
uv run python scripts/run_agent1_verification.py --dry-run --limit 1
```

No credentials, model calls, or output writes are needed for this preflight.
The separate `--run` flag authorizes paid calls. The original
`run_agent1_batch.py` remains the baseline interpretation runner.

See [Agent 1 verification](docs/agent1-verification.md) for the active modules,
one-thread paid pilot command, output format, resume behavior, tests, and
superseded experiments. The frozen 200-thread baseline and 91 clusters remain
historical inputs; Agent 2's current contracts and runners are still supported.

## Troubleshooting

- `No module named pip`: uv-created environments do not include pip by default.
  Use `uv add package-name` to install and record a project dependency, or
  `uv sync --locked --extra dev` to restore the checked-in dependencies.
- Rust compiler or wheel-build errors for `tiktoken` or `regex` while installing
  CrewAI: check the Python version and use this project's Python 3.13 environment.
  Python 3.14 is outside [CrewAI's supported range](https://pypi.org/project/crewai/).
  Older dependency versions may lack wheels for newer Python versions, causing
  an installer to attempt a source build.
- `ModuleNotFoundError: No module named 'threadsense'`: use the project
  environment and run pytest inside this checkout. The editable installation
  also makes `threadsense` available to other Python scripts.
- `Fatal Python error: Failed to import encodings module`: the underlying
  Python installation is incomplete or broken. Use the uv commands above to
  use a managed interpreter, or repair that Python installation before
  recreating any environments that depend on it.
- Tests from `Lib/site-packages` appearing in collection: use the checked-in
  pytest configuration, which limits default collection to `tests`.
- Errors accessing an old `.pytest_cache`: this project uses `.cache/pytest`;
  the old directory is no longer needed by these tests.
- An existing `.venv` points to another computer or an unavailable Python:
  rename it to `.venv-backup`, then run `uv sync --locked --extra dev` to create
  a fresh environment.

