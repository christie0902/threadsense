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

## Troubleshooting

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

