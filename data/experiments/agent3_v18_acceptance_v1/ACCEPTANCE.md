# Milestone acceptance: concise summaries, expanded details, checked next steps (closed 2026-11-05)

Scope: local capstone/demo. Development evaluation by the developer; not independently validated.

## Acceptance statement

No blocking unsupported content was identified in the developer's inspection. One potentially misleading historical
phrase passed grounding and remains recorded as a wording defect (below). The saved card and its verdicts are unchanged;
no corrected wording was generated or judged.

## Final live run (`run/`)

- One run, 8 topics (same work items and member bindings as `agent3_e2e_eval_v1`), prompts v18, draft v11, AdviceCard v4.
- 16 requests, $0.86 (193,733 input / 47,597 output tokens), no request failures. No revision or ToT step triggered.
  ReAct and flag-impact assessment off.
- Accounting COMPLETE: 22 threads on cards, 156 out of scope, 52 review-queue items (41 + 8 + 3), 8 projection gaps
  preserved; the Submit projection gap kept its grouping flag and both Agent 1 obligations.
- Live demonstration of concise summaries, expanded "What happened" details and checked next-step states. Every card's
  grounding PASSED.
- Cosmetic ties reached Observation with a supported NO_ACTION decision and supported LOW severity.
- English->Spanish retained "No intervention proposed" because its NO_ACTION explanation was only partly supported.
- A decision on a v4 card (tú/usted, APPROVE_ACTION) saved once and replayed idempotently in a throwaway demo database
  outside the repository; never executed or posted.
- Actions matched the existing evaluator expectations in `agent3_e2e_eval_v1/expectations.json` (8/8). This is agreement
  with those proposed expectations, not independently validated ground truth or a general model accuracy score.

## Wording defect (passed grounding)

Submit, detail sentence 6: "An earlier batch-15 handoff records comparable disabled-control reports sent to engineering,
with no confirmed shared cause or repair at its September 28 close." The record states the incident remained open at
17:00 UTC on September 28; "close" can be read as the incident having been closed. The sentence passed the final
grounding check, so this is a limitation of the generated wording and of that check, not only a style preference.

## Dashboard correction after the run (offline)

The flagged-thread check said "the summary and recommendation passed the evidence check" on cards without a
recommendation (English->Spanish). It is now built from the saved statement verdicts (`dashboard.checks.checked_parts`):
the recommendation is named only for a displayed operational action with its own SUPPORTED verdict, the reason for no
action only when it was judged SUPPORTED and is displayed, the summary only when the displayed summary is exactly its
SUPPORTED sentences; otherwise the sentence is omitted. English->Spanish now reads: "The summary passed the evidence
check; the flags concern an earlier step's reading of this thread, not the summary."

## Test evidence (kept apart)

- Full suite: 1,072 passed, run once on the presentation implementation before the live run (not rerun since).
- Safeguard tests added afterwards: `tests/test_agent3_presentation_safeguards.py`, 9 passed (before the live run).
- Closeout checks after the dashboard correction: `tests/test_agent3_presentation.py` (35, including 2 new status-sentence
  tests), the safeguard tests, `tests/test_dashboard.py` and `tests/test_dashboard_review.py`: 82 passed together;
  frontend build; Playwright dashboard suite 13 passed.

## Non-blocking follow-ups

- Retrieval misses: the batch-05 playback trial outcome (buffering) and the open tie-tracking announcement (cosmetic ties).
- Severity variation between runs (quoted wording HIGH here, MEDIUM earlier; buffering HIGH from two reporters) and the
  unresolved rubric interpretation behind it.
- Residual awkward wording and repetition ("the retrieved conversations", "the supplied thread", "a tutor and another
  tutor"), plus the Submit phrase above.
- Experimental or not live-covered: flag-impact assessment (opt-in, shadow), adaptive ReAct research (off), a withheld
  detail sentence and RECOMMENDATION_WITHHELD / NO_RECOMMENDATION_AVAILABLE states (offline tests and prepared fixture
  only).
