# Refreshing the Agent 2 pilot after a code edit

Historical response-schema-v2 instructions. The [maintained Agent 2 run guide](agent2-offline-integration.md)
describes the current schema-v3 contract and new pilot. A code-only refresh does
not convert old model responses or schema-v2 selections into schema-v3 results.

For all 90 candidate groups, use the separate
[full-batch selection and commands](agent2-full-batch.md). The four-case selections
on this page remain available for pilot runs.

The pilot's `configuration_sha256` binds its selection to the model, inputs,
glossary, and execution code. Editing `topic_consolidation.py` invalidates the
original fingerprint even when only local export fields change. The runner must
keep rejecting that old selection rather than silently accepting different code.

The user's added `preliminary_severity`, `preliminary_severity_rationale`, and
`severity_is_provisional` fields are preserved. They are calculated locally after
parsing; model prompts and response schemas are unchanged. The new fingerprint
also includes `severity.py`, now an active dependency of the exporter.

This heuristic assigns MEDIUM when review flags or consolidation uncertainty
exist, or when at least three members share an open question. It does not establish
operational impact. Pending/failed groups with no topics receive N/A while their
review obligations remain intact. These are the user's current rules, not an
independently validated severity assessment or an Agent 3 implementation.

## Revised offline preparation

The refreshed selection is `docs/agent2-pilot-v3.json`; the version here identifies
the prepared pilot, while the Agent 2 payload schema remains version 2.
`data/processed/agent2_pilot_prepared_v3/` contains the four exact requests, pending
exports, manifest, and review queues. It retains the same four cases, 15 members,
five inherited review obligations, model, and four-request ceiling. All four model
requests match the original preparation byte for byte. No paid calls were made
for this refresh.

The revision records the previous pilot's hash, original preparation path,
review note, changed code hashes, and request comparison. The review is a
Codex-assisted inspection of local changes, not approval of model accuracy.
Both the old offline preparation and the existing four-request live run in
`data/processed/agent2_pilot_v2/` are preserved. The existing live manifest reports
one CONSOLIDATED and three FAILED groups; this refresh does not retry them.

Run this read-only check from the repository root:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-pilot-v3.json
```

`--dry-run` checks the four selected cases without requests or writes. To write
another offline preparation, use a **new** directory:

```powershell
uv run --locked python scripts/run_agent2_batch.py --prepare --pilot docs/agent2-pilot-v3.json --output-dir data/processed/agent2_pilot_prepared_v3_copy
```

Live execution remains separate and is not part of this fix. If explicitly
chosen later, this command permits at most four **new paid attempts**, with zero
retries, repairs, or fallback calls:

```powershell
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-pilot-v3.json --max-requests 4 --output-dir data/processed/agent2_pilot_v3
```

## Future inspected code changes

Use the explicit preparation helper after reviewing a further edit. It accepts
code changes while requiring the existing model, glossary, inputs, selection,
review obligations, and request limits to match. It rejects existing destination
paths, so historical artifacts remain intact. The helper has no live mode.

For example, after a future edit to the v3 code:

```powershell
uv run --locked python scripts/prepare_agent2_pilot.py `
  --source-pilot docs/agent2-pilot-v3.json `
  --source-preparation data/processed/agent2_pilot_prepared_v3 `
  --output-pilot docs/agent2-pilot-v4.json `
  --output-dir data/processed/agent2_pilot_prepared_v4 `
  --review-note 'Describe the code changes you inspected and their effect on the pilot.'
```

Do not edit the saved fingerprint manually. Source or model changes need a
separate selection/configuration review. Later code edits continue to invalidate
newly prepared pilots as intended.

## Validation of this refresh

The focused suite passed 41 tests. The complete offline suite passed **318 tests,
0 failures, 0 skips**, with 162 existing dependency warnings in 105.30 seconds:

```powershell
.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-pilot-refresh-full
```

The exact `uv run --locked` v3 dry-run command above also passed: four groups,
15 identities, five inherited review obligations, and zero calls. Hash checks
confirmed all 4,945 preexisting data files and protected pilot/code/environment
files were unchanged, including the user's edited `topic_consolidation.py` and
existing live results. New tests exercise source/configuration rejection, the
four-request bound, refusal to overwrite artifacts, absence of model/credential
calls, retention of flags with severity fields, and rejection of later changes
to the severity dependency.
