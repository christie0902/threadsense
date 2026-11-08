# Combined briefing v2 (combined-briefing-v2) — demo baseline

Supersedes `threadsense_full_v1_combined_v1` (unchanged). Built with the existing rebuild path, zero model calls:

```sh
uv run --locked python scripts/derive_combined_brief.py \
  --reground data/experiments/agent3_reground_v1/overlapping_speech.json \
  --reground data/experiments/agent3_reground_v1/format_compliance.json \
  --previous data/experiments/threadsense_full_v1_combined_v1 --write data/experiments/threadsense_full_v1_combined_v2
```

## Cost

| Step | Requests | Cost |
|---|---|---|
| Targeted live re-grounding (`data/experiments/agent3_reground_v1/`, run before this build) | 2 | **$0.094** ($0.051 + $0.043) |
| This offline rebuild | 0 | $0 |

Earlier paid steps behind the parents: the full live run ($15.32) and the consolidated refresh ($2.23).

## What changed from v1

Only two cards were replaced; the other 93 cards are byte-identical to v1 (checked by the build).

| Card | v1 card | v2 card | Change |
|---|---|---|---|
| Overlapping speech in transcription | `card_68f4f5db81d4133a9faffb72f7704e92` | `card_17101d4c0b58aa89d8d7d2228fec185f` | 35/35 statements SUPPORTED; the withheld sentence is shown; Needs Review only for its open inherited flag; action shown |
| Format compliance versus accuracy | `card_a342d58f26ef48f521c0a73bc3d78956` | `card_f80a23755fb93b9ae1fcc23cb0f7f880` | 26/26 SUPPORTED; Recommended Action, severity MEDIUM, reminder shown |

Verification before either card was accepted: the card was rebuilt from the refresh run's recorded generations (plus the
recorded wording edits) and the saved live grounding response, and matched byte for byte. Grounding is PASSED with
nothing unjudged. Every summary and detail sentence is on the card exactly when it was judged SUPPORTED. All cited
evidence is in the saved ledger. The displayed reminder is the model's judged draft.

## Labels on the format card

- **Human edits, verified by the live model** (three statements: summary sentence 1, the reason to intervene, the
  severity signal). Each was written by the developer (`data/evaluation/agent3_format_card_wording_v1.json`) and judged
  SUPPORTED by the live model. Shown on the card and in `morning_brief.md`, with the text each replaced in `derivation.json`.
- **Reminder draft:** the model's original draft, exactly as judged.
- **Suggestion for the team lead (not judged):** an optional line on the JSON-versus-prose case
  (`data/evaluation/agent3_tl_suggestions_v1.json`).

## Counts and accounting

63 briefing items: **52 Needs Review, 8 Recommended Action, 3 Observation**. 177 threads exactly once (174 on briefing
cards, 3 in processing history); 37 review items. 29 replaced cards only as lineage. Decisions bind to this run
instance: a decision saved here does not appear on v1, and its export carries this run's instance.

## Demo walkthrough

Observations: use the three live cards here ("Suggestive vs explicit content boundary", "Queue coverage and closure
reminders", "Work environment and background noise"). The two synthetic examples stay in their labelled fixture run,
`observation_demo_fixture_v1` (TEST_FIXTURE, hand-written).

## Agent 1 exclusions in future runs

A proposed model exclusion (social, routine admin or expired notice) gets one Agent 1 verifier request per proposed
exclusion; only SUPPORTED excludes, anything else keeps the thread eligible. This has been exercised with prepared
verifier responses only (`tests/test_thread_relevance.py`), not live. This run's three processing-history threads come
from audited labels.

## Screenshots

`screenshots/`: overview, observations, overlapping speech, format card; `observation-demo.png` is the separate fixture run.

## Presentation layer (briefing-presentation-v1, zero calls)

`presentation.json` (built by `scripts/build_presentation.py --write`, bound to this run instance; the four instance
files are unchanged, so decisions stay bound). `morning_brief.md` was regenerated from it; the original export is kept as
`exports/morning_brief.derivation.md`.

- Totals: 63 active cards covering 174 threads (52/8/3); 3 processing-history threads and 37 review items stated
  separately; 95 card records in this directory = 63 active + 29 replaced (history) + 3 processing history.
- Usage by stage: full pipeline 937 requests, $15.3173 (campaign ledger); refresh 32 requests, $2.2280; targeted checks
  2 requests, $0.094 as reported ($0.094422 exact); offline assembly 0 requests, $0.
- Format card: posting suggestions (not judged) apart from the judged draft: reply in the October 2, 10:21 UTC status note
  thread (`k:slack:C_RP_ANNOUNCEMENTS:1790936513.000019:8237860f`), and the optional JSON-versus-prose line.
- NSFW card: "Choose a next step" with both saved, eligible options (review session with its scope condition; written
  request); the cutoff question stays open and the card stays in review.
- Editorial notes (developer, not judged, with sources): fictional-contact "Confirm before editing"; queue-coverage
  "Timing unconfirmed".
