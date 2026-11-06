# Combined briefing: review notes (combined-briefing-v1)

Derived offline from `threadsense_full_v1_consolidated_v1` (49 reused cards, processing history, consolidation record,
review queue) and `threadsense_full_v1_consolidated_refresh_v1` (14 consolidated issues advised live). Zero model calls;
both parents are unchanged. Builder: `scripts/derive_combined_brief.py`. Full record: `derivation.json`.

## Provenance

| Part | Source |
|---|---|
| Agent 3 advice (63 briefing cards) | Live model output (`gpt-6.1-sol`): 49 cards from `threadsense_full_v1`, 14 from the refresh run, revalidated offline |
| Agent 1 relevance (3 threads in processing history) | Developer audit (`data/evaluation/agent1_thread_relevance_labels_v1.json`); no live relevance judgment recorded |
| Agent 2 consolidation (14 merges) | Prepared audit (`data/evaluation/agent2_consolidation_decisions_v1.json`); no live consolidation judgment recorded |
| Briefing routing | `briefing-routing-v2`, applied to the refreshed cards as to every other card |

## Counts

63 briefing items: 53 Needs Review, 7 Recommended Action, 3 Observation (49 reused + 14 refreshed: 11 Needs Review,
3 Recommended Action). 29 replaced cards are history, reachable only through the lineage of the issue that replaced
them (not served as cards in this run). 3 threads and 3 cards in processing history. 177 threads exactly once
(174 on briefing cards + 3 in processing history); the replaced cards cover exactly the refreshed issues' 64 threads;
37 review items, unchanged. Shared actions: 0 (the duplicate Contact details edit is now one card's action).

## Revalidation (pilot v8 checks, recorded verdicts, zero calls)

Same-rules replay reproduced all 14 refreshed cards byte for byte under the pilot v7 checks; under v8, 11 are
unchanged and 3 were corrected:

- **Overlapping speech in transcription.** `claim:c1` ("A QA tutor asks whether simultaneous speech by two people
  should be marked unintelligible") was rejected because "two people" was counted as authors. It describes the
  speakers in the clip, so the corrected check no longer rejects it. It never reached the grounding judge, so it is
  now withheld as not yet checked (PENDING), not restored. The action's recorded SUPPORTED verdict stands: it was
  judged with `claim:c1` rejected, and its sufficiency did not rely on it.
- **Public business contact details are not private PII.** The conflict cited a superseded help-page section
  (`SECTION_SUPERSEDED`) against the FAQ and instructions, which the final grounding recorded as agreeing. It now
  resolves by recorded state, with the help page listed as a documentation target. TEMPORAL_CONFLICT is removed and
  the inherited flags keep the card in Needs Review.
- **QN handling for fictional contact details.** The superseded-help-page finding was already resolved. The October
  status note is established handling but states no competing rule, and the four rule-stating sources agree. What
  stays open is which guide the note means, so the conflict is now a documentation question (still reviewable) and
  the card shows the disputed point and its three sources.

## Format compliance versus accuracy (diagnosis, membership kept)

All 11 claims are SUPPORTED. One grouped description, reused in `summary:s1`, `action:need` and the MEDIUM severity
signal, says all three starters ask about format versus accuracy. The RP-3824 starter (a QA tutor) asks about a
required JSON object answered in well-written prose. Accuracy is raised in that thread by another QA tutor (claim c5).
The judge marked all three statements PARTIALLY_SUPPORTED, so the action was withheld (NO_INTERVENTION_NEED) and
severity stayed UNKNOWN. Both subquestions share one handling rule (score required-format compliance separately, no
universal priority, collect the pair), so the topic is not split. Candidate wording, labelled
`DEVELOPER_CANDIDATE_PENDING_GROUNDING`: `data/evaluation/agent3_format_card_wording_v1.json`.

## Older scoring guide screenshot versus newer pinned note

The card shows the supported pending step through the briefing policy (`WAITING_ON_REQUESTED_STEP`, "Pending
follow-up"): the team lead requests both dated versions and leaves supersession undecided pending verification of the
change history.

## Remaining targeted model judgments (paid, not run)

| Card | Requests | Hard cost | Expected |
|---|---|---|---|
| Overlapping speech: judge `claim:c1` | 1 grounding | $0.21 | about $0.05 |
| Format compliance: judge the candidate wording | 1 grounding | $0.21 | about $0.05 |

Hard cost: one request at the 24,000-token input limit and 16,384-token output cap. Measured requests: 12,935 and 11,657
input tokens. Expected: mean recorded grounding charge of the refreshed items. Commands are in
`derivation.json` (`remaining_judgments`); without `--run` each prints the exact request plan with zero calls.

## Screenshots

`screenshots/`: overview, observations, and the fictional-contact, business-contact, overlapping-speech, format and
older-scoring cards; `observation-demo.png` is the separate test fixture
(`tests/fixtures/observation_demo_runs/observation_demo_fixture_v1`, hand-written, not live).
