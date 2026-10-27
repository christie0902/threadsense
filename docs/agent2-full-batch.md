# Agent 2 full-batch selection

Historical response-schema-v2 instructions. For current code and the prepared
schema-v3 pilot, use the [maintained Agent 2 run guide](agent2-offline-integration.md).
The old selection remains evidence of its original run and is not upgraded.

If a run was interrupted, use the [continuation command](agent2-continuation.md)
to process only never-started groups and retain the previous results. The command
below starts a fresh full batch and does not resume an existing directory.

The current runner requires `--pilot` for every live run. This option names an
explicit, fingerprinted selection; it is not limited to four cases.
`--max-requests` sets a bound and does not select the batch on its own.

`docs/agent2-full-v1.json` selects **all 90 groups, 200 members, and 49 inherited
review obligations**, bound to the current code and `openai/gpt-4o-mini`.
The current code also matches the four-case v3 pilot's fingerprint. No production
code, prompts, grouping, severity rules, or existing artifacts were changed for
this full selection. The preparation checks coverage and configuration; it does
not establish semantic accuracy or imply review of all model outputs.

From the repository root, inspect the full selection without calls or writes:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-full-v1.json
```

To execute the full batch yourself:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-full-v1.json --max-requests 90 --output-dir data/processed/agent2_full_v1
```

This permits up to **90 new paid requests**, one per group, with zero retries,
repairs, or fallback calls. It includes the four pilot groups as part of the full
batch; existing pilot responses are not reused. The live output directory must
not already exist. Recoverable failures and review flags continue through the
batch; fatal configuration/persistence failures still stop execution.

No live call was executed during this preparation. The 90 exact offline requests,
pending results, review queues, and manifest are in
`data/processed/agent2_full_prepared_v1/`. All requests match the original full
offline preparation byte for byte, and all 4,995 checked preexisting data and
protected code/configuration files are unchanged. See `offline_validation.json`
in the new preparation directory for the receipt.

The exact `uv` dry run above passed with 90 groups, 200 identities, and 49 review
obligations. The Agent 2 integration tests also passed: **31 passed, 0 failed**.
They use mocked responses and do not measure live semantic accuracy.

If code changes later, the saved selection will deliberately fail its fingerprint
check. Use `scripts/prepare_agent2_pilot.py` with this full selection and its
preparation directory as the source, and new output paths, following the
[code refresh instructions](agent2-pilot-refresh.md). Do not bypass the check or
overwrite prior results.
