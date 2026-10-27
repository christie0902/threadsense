# Continue an interrupted Agent 2 batch

This records the historical schema-v2 continuation. Current schema-v3 preparation
and compatibility rules are in the [maintained Agent 2 run guide](agent2-offline-integration.md).
The historical interrupted request remains unknown; new code does not retry it.

The original batch runner refuses an existing output directory to avoid
overwriting evidence or repeating requests. Do not delete the interrupted run
or start the entire 90-group selection again to work around that check.

Use `scripts/continue_agent2_batch.py`. It validates the original selection,
code/model fingerprints, saved inputs/requests, members, and review obligations.
It copies retained results and evidence into a new output directory, calls the
unchanged execution pipeline only for never-started groups, then creates a
combined export and review queues. A saved start, call, response, or result is
enough to exclude a group from further requests. Failed or unknown-completion
attempts are retained for review without retries.

## Current interrupted run

`data/processed/agent2_full_v1_run/` has 90 groups and 200 threads:

- 8 saved attempts, with 7 responses.
- 1 CONSOLIDATED, 6 FAILED validations, 1 INTERRUPTED, 82 NOT_RUN.
- The interrupted group is `cluster_128dab46288ce554`; provider completion is
  unknown because no response was saved. Its original evidence remains available.
- All 49 inherited Agent 1 review obligations remain attached.

Read-only inspection:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/continue_agent2_batch.py --dry-run --source-dir data/processed/agent2_full_v1_run --pilot docs/agent2-full-v1.json
```

Continue the 82 never-started groups:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/continue_agent2_batch.py --run --source-dir data/processed/agent2_full_v1_run --pilot docs/agent2-full-v1.json --max-requests 82 --output-dir data/processed/agent2_full_v1_continued
```

This permits at most 82 new paid attempts: 8 retained plus 82 new is at most
90 for this run. It does not use or retry other historical full-batch/pilot runs.
The new output directory must not exist. The source process must be stopped;
source files are checked for changes during snapshot creation. New requests have
zero retries, repairs, or fallback calls. No model, prompt, severity rule, or
existing fingerprinted pipeline file was changed to add continuation.

## Evidence and another interruption

The new directory contains combined `consolidations.json`, `review_queue.json`,
`member_review_queue.json`, `manifest.json`, and per-group `records/` covering all
200 members. Original results and raw evidence are preserved. The manifest
reports cumulative attempts and `continued_request_attempts` separately;
unknown completion remains explicit and is not treated as provider success.

`new_requests/` is the isolated execution journal for this continuation. While
the run is in progress, its manifest shows new-request progress. The combined
reports are refreshed when the continuation returns or handles an interruption
or fatal failure. A hard process kill can leave them stale; the next inspection
also reads per-group evidence in this journal and never relies solely on the
aggregate NOT_RUN status. A start without a call marker is conservatively
excluded and remains visible as `started_without_call_marker`.

If interrupted again, run the same dry-run command with `--source-dir` pointing
to `data/processed/agent2_full_v1_continued`. Use its reported remaining count for
`--max-requests`, and a new output directory, for the next continuation. Keep the
original full selection `docs/agent2-full-v1.json`. Do not reuse the old source
directory after a newer continuation has begun.

Completed handling may still include FAILED/INTERRUPTED records requiring review.
Preserving these records does not establish semantic accuracy or resolve an
unknown provider outcome. Fatal configuration/persistence failures still stop
further requests and retain later inputs as NOT_RUN.

## Offline checks

Ten mocked tests passed, covering all 90 groups/200 identities/49 obligations,
preservation of failures and unknown completion, no repeated attempts, a second
interruption, hard-stop recovery from stale reports, start-only markers, source
corruption, exact budgets, offline preparation without credentials, and fatal
failure handling:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_agent2_continuation.py -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-continuation
```

The real interrupted run also passed the read-only inspection with 82 remaining
groups. `data/processed/agent2_full_v1_continuation_prepared/` is a separate offline
snapshot with all 200 members, 49 obligations, eight retained attempts, and zero
new attempts. It is not the live destination in the command above. Original run
files were not changed and no paid calls were made during this implementation.
