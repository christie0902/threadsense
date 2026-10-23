# Isolated prose-comparison experiment

This experiment tests one narrow task: compare one prose unit with the original
Slack conversation and approved glossary. It does not invoke or modify the
production verification pipeline. It uses the four completed
`data/processed/agent1_verified_pilot_v5` outputs to locate the exact saved source
conversations. Prior interpretations, verification statuses, audit judgments,
and revision reasoning are excluded from requests.

All eight candidate sentences below are **synthetic benchmark inputs** constructed
after reviewing those sources. They are not presented as saved model responses.
`cases.json` holds the neutral IDs and candidates; `expected.json` holds separate
reviewed verdicts, evidence quotations, and explanations. The answer key is used
only for offline validation and scoring.

## Reviewed cases

| Case | Thread | Synthetic candidate prose | Expected verdict |
| --- | --- | --- | --- |
| case_01 | 1790909920.000138 | Jordan says the reference text contains a sentence that is missing from the recording. | SUPPORTED |
| case_02 | 1790882197.000111 | Yuki reports that the previous workaround was attempted and failed. | UNSUPPORTED |
| case_03 | 1790915374.000127 | Avery asks whether the silent clip should receive a quality note (QN) or a quality score. | CONTRADICTED |
| case_04 | 1790903186.000110 | The Team Lead's eyes reaction acknowledges the thread, while Mina requests more evidence rather than providing an answer. | SUPPORTED |
| case_05 | 1790915374.000127 | Avery asks whether the silent clip should enter Quarantine (QN) or receive a quality score. | SUPPORTED |
| case_06 | 1790909920.000138 | Jordan says the recording contains a sentence that is missing from the reference text. | CONTRADICTED |
| case_07 | 1790903186.000110 | The Team Lead's eyes reaction approves Mina's guidance as the answer to the playback problem. | UNSUPPORTED |
| case_08 | 1790882197.000111 | Yuki thinks a workaround may have existed in the previous queue but reports that the loading problem is happening again. | SUPPORTED |

Review anchors in the actual saved messages:

- `1790909965.000113`: “The reference text has a sentence missing from the
  recording; that is a correspondence problem.” The v5 summary reverses this
  relationship despite being marked VERIFIED; that status is not a benchmark label.
- `1790882197.000111`: “I thought a workaround existed in the previous queue,
  but it is happening again.” `1790882343.000339` requests task IDs and reproduction
  before deciding whether the old workaround applies. Neither establishes an
  attempted/failed workaround.
- `1790903186.000110` carries an `eyes` reaction by U006 with TEAM_LEAD metadata.
  `1790903244.000113` asks: “Can you record the task reference, browser state, and
  whether the audio element loads?” Acknowledgment and evidence requests do not
  establish approval. The shared comparator instructions state the existing
  domain convention that `eyes` means acknowledgment.
- `1790915374.000127` asks “QN or quality score?” The approved glossary defines
  QN as Quarantine. That glossary definition is supplied equally to every case.

## Requests, validation, and call limits

The implementation is in `src/threadsense/experiments/prose_comparison.py`, with
the entry point `scripts/run_prose_comparison_experiment.py`. It reuses
`ProseEvidenceAssessment` and `get_auditor_model_settings()`; production modules
remain unchanged. `THREADSENSE_VERIFIER_MODEL` overrides `THREADSENSE_MODEL`
exactly as in the existing verifier configuration. Credentials come from the
existing local `.env` and are never saved in request files.

Each request has a fresh system/user message pair and a single neutral `unit_1`.
There is no conversation history, case label, paired candidate, or expectation.
The only user-message inputs are the original conversation (including metadata),
approved glossary, and candidate unit. No reply categorization, decision coverage,
or resolution classification task is included.

The comparator returns the existing `ProseEvidenceAssessment`. Validation requires
the exact unit ID and candidate text, a recognized verdict, nonblank explanation,
nonempty unique source IDs, and parallel exact quotations from those messages.
Quotation validation checks that evidence exists; the experiment measures the
model's factual judgment rather than assuming a valid quotation proves that judgment.

The live runner makes at most eight requests, one per case. It sends the saved
UTF-8 JSON bytes through a single-attempt standard-library HTTPS transport.
There are no CrewAI stages, automatic retries, fallback requests, or redirect
following. A rate limit, timeout, malformed response, or invalid citation is
retained as a failure; it does not cause another call for that case.

Only a new output directory is accepted. Runs cannot silently overwrite or resume
earlier paid work. An intentional new experiment requires a new directory.
Interruption retains all eight rows; unattempted cases remain `NOT_RUN`. Durable
stage markers identify initiated calls. If output persistence fails, execution
stops rather than starting another request.

## Commands

From the repository root, prepare exact requests without credentials or paid calls:

An initial offline preview is already saved in
`data/experiments/prose_comparison_preview_v1/`. Its eight request bodies were
checked for label/history exclusion and its report records zero model calls.
The command below creates a separate, new preview directory.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
uv run --locked python scripts/run_prose_comparison_experiment.py --dry-run --output-dir data/experiments/prose_comparison_dry_v1
```

The dry run writes requests and provenance for inspection. It does not claim any
acceptance/rejection rate. Omit both mode flags and the default is still dry run.
If this preview directory already exists, choose a new name such as `_dry_v2`.

To authorize the eight independent model requests later:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
uv run --locked python scripts/run_prose_comparison_experiment.py --run --output-dir data/experiments/prose_comparison_live_v1
```

The live command has **not** been executed during implementation. A completed
experiment may have failures or mismatches; all are included in its report.

Run offline tests:

```powershell
uv run --locked --extra dev python -m pytest -q --tb=short --basetemp .cache/pytest-prose-experiment-suite
```

## Output and scoring

```text
prose_comparison_live_v1/
    manifest.json             # model, endpoint, input/code/request hashes, retry count
    expected_verdicts.json    # separate answer key, never transmitted
    results.json              # exactly eight rows, including failures/unattempted cases
    report.json               # separate metrics and every exact-verdict mismatch
    case_01/                  # analogous directories for case_02 ... case_08
        request.json          # exact JSON body sent; authorization is not part of this file
        started.json          # written before this case's single HTTP attempt
        response.raw.bin      # unmodified HTTP response body, before parsing
        assessment.raw.txt    # exact returned content when available, before validation
```

The manifest identifies the endpoint; each result records its HTTP status.
A connection failure before any response leaves an empty raw-response file and
an explicit error. A truncated HTTP response retains the partial bytes and is
recorded as a request failure without retry. A dry run creates only requests, the answer key, manifest,
results marked NOT_RUN, and a report with `metrics: null`.

Metrics use the full reviewed denominators:

- **Faithful acceptance:** SUPPORTED on a faithful case, out of four.
- **Incorrect rejection:** CONTRADICTED or UNSUPPORTED on an incorrect case,
  out of four. UNCERTAIN, invalid evidence, and request failures do not count
  as successful rejection.
- **Exact verdict agreement:** agreement with the reviewed verdict, out of eight.
  CONTRADICTED versus UNSUPPORTED is listed as an exact-verdict mismatch even
  when it correctly rejects an incorrect candidate. This distinction is useful
  for the acknowledgment/approval case, where the unsupported-versus-contradicted
  boundary can depend on how the claim is read.

Every disagreement or failure is listed by case ID with expected/observed verdicts
and error details. `results.json` links that ID to the source thread and candidate.
Exit codes are 0 for dry run or exact agreement on all eight, 2 for mismatches or
invalid CLI/input, and 130 for keyboard interruption. Four cases per class form
a focused diagnostic benchmark, not a general accuracy estimate.

## Offline validation (2026-10-22)

The complete suite passed **218 tests, 0 failures**, including 39 new experiment
tests. The suite reported 191 existing dependency deprecation warnings. The exact
full-suite command is listed above. Tests cover independent requests, label
exclusion, candidate identity, exact evidence, both provider routes, separate
metrics, every mismatch, raw failure retention, partial responses, interruptions,
no overwrite/resume, and the eight-attempt/no-retry limit. HTTP calls are mocked.

SHA-256 comparisons confirmed that all 423 pre-existing files covered by the
preservation checkpoint remained unchanged, including production code, existing
tests, original Slack/frozen data, Agent 2, and every saved v5 pilot artifact.
No live comparator call or full-batch rerun was executed. Live faithful acceptance
and incorrect rejection rates remain unmeasured.
