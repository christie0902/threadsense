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

## Retained comparator and evidence

This focused benchmark remains in use by offline tests and saved-response replay.
Its comparator is `src/threadsense/experiments/prose_comparison.py`, with entry
point `scripts/run_prose_comparison_experiment.py`. It uses the existing verifier
model configuration and `ProseEvidenceAssessment` contract. Production v3's
batched comparison is a separate workflow; see the
[current handoff guide](../../docs/agent1-nonblocking-handoff.md).

Each case has an independent system/user request containing only the conversation,
approved glossary, and one neutral `unit_1`. Expected verdicts, paired candidates,
prior reasoning, reply classifications, and resolution tasks are excluded.
Validation requires exact candidate identity/text, nonblank explanation, unique
source message IDs, and corresponding exact quotations. Valid quotes alone do
not prove the model's factual verdict is correct.

The runner accepts only a new output directory, at most eight requests (one per
case), zero automatic retries, and no fallback calls. It retains failures and
raw responses. Persistence failure stops further calls; interrupted/unattempted
cases remain visible. Credentials come from the local environment and are not
saved in request files.

## Saved results and scoring

The completed eight-call experiment is preserved in
[data/experiments/prose_comparison_live_v2/](../../data/experiments/prose_comparison_live_v2/).
Its [report](../../data/experiments/prose_comparison_live_v2/report.json) records:

- Faithful acceptance: **4/4**, using SUPPORTED on faithful cases.
- Incorrect rejection: **4/4**, using CONTRADICTED or UNSUPPORTED on incorrect cases.
- Exact verdict agreement: **6/8**. Cases 02 and 07 returned CONTRADICTED against
  the reviewed UNSUPPORTED labels; both still rejected incorrect prose.

UNCERTAIN, invalid evidence, and request failures do not count as successful
rejection. Reports list every mismatch/failure by case ID. Four cases per class
are a diagnostic benchmark, not a general accuracy estimate. Replay tests adapt
only the envelope/unit ID in memory; saved requests, raw responses, and labels
remain unchanged. Replay does not establish the accuracy of production batching.

`manifest.json` retains configuration, inputs, and request hashes;
`expected_verdicts.json` is a separate answer key never transmitted to the model.
`results.json` keeps all eight cases. Each case directory retains `request.json`,
its started marker, available `response.raw.bin`, and extracted
`assessment.raw.txt`. Earlier dry/preview outputs are historical provenance.

## Commands

Offline checks (mocked model responses):

```sh
uv run --locked --extra dev python -m pytest tests/test_prose_comparison_experiment.py tests/test_verification_integration.py -q --tb=short --basetemp .cache/pytest-benchmark-current
```

Prepare requests in a new directory without credentials or model calls:

```sh
uv run --locked python scripts/run_prose_comparison_experiment.py --dry-run --output-dir data/experiments/prose_comparison_preview_v3
```

The dry run writes requests and NOT_RUN results with no measured accuracy.
The explicit `--run` flag makes paid calls; any separately authorized future
experiment must choose an unused directory and keep expected labels outside
requests. No new experiment was executed during repository cleanup.

The initial implementation had 218 passing offline tests, including 39 benchmark
checks. Current full-suite validation is in the
[cleanup report](../../docs/repository-cleanup.md). The tests retain label/history
exclusion, candidate/evidence validation, separate scoring, raw failures, partial
responses, interruptions, overwrite protection, and strict call limits.
