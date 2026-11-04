# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

2 cards (NEEDS_REVIEW 2); 52 Model Review Queue items; 178 discussion members (7 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 2 of 87 work items (85 out of scope; their members and review items are still accounted for).

## QA calibration on disputed tie decisions

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors report ties marked wrong; a tutor also reports that a similar pair received a different QA judgment from the previous day. The team lead acknowledged inconsistent QA feedback and asked for both rationales to calibrate before changing the tie threshold. The current FAQ calls for the pairs, relevant prompt constraints and both rationales, with a check that the cases are actually comparable.

**What to do: Schedule a short review session.** Arrange a QA calibration review of the disputed batch-15 pairs after collecting the pairs, relevant prompt constraints and both rationales, using the current tie criterion before considering any threshold change.

**Why.** Comparing the actual cases and rationales addresses the reported QA inconsistency without treating pair-specific replies as a blanket ruling. The earlier batch's review improved agreement in its sample, but it does not establish the outcome for this batch.

**Draft to copy:**

> Please prepare the disputed batch-15 pairs for a QA calibration review, including RP-9595. For each comparison, provide the pair, relevant prompt constraints and both written QA rationales. We will check whether the cases are actually comparable and apply the current criterion: choose a tie when neither response has a meaningful quality advantage; cosmetic phrasing alone does not justify a preference. Explain the user-facing benefit for any preference based on a small difference. For the RP-9595 discussion, this follows the team lead's request to calibrate before changing the tie threshold. Arrange the review once the case inputs are available.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

Sources: response-preference-faq@1.1 (Ties and preferences); response-preference-instructions@1.1 (Ties); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment); rp-tie-calibration-post@1.0

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and three tutors report problems submitting tasks. The team lead requested task IDs, required-field state and exact button behavior in all four threads; submission status remains unverified in those threads. An earlier batch handoff records disabled Submit reports sent to engineering, but its recorded outcome remained open without a confirmed shared cause or repair.

**What to do: Report a technical issue to engineering.** Collect the outstanding submission diagnostics from the affected reporters and send engineering one consolidated report, distinguishing disabled buttons from clicks that do nothing.

**Why.** The reports describe submission failures, and an engineer has already requested error state and time for two tasks. A consolidated report preserves the different symptoms without assuming that the earlier open incident explains them.

**Draft to copy:**

> Please investigate these submission reports:
> - A QA tutor and a tutor report that Submit stays grey after choosing B; the tasks referenced by an engineer in their respective threads are RP-3412 and RP-5337.
> - A tutor reports being able to score both answers, but clicking Submit does nothing on RP-1577.
> - A QA tutor reports finishing the preference rubric but being unable to submit the pair on RP-3325.
> - A tutor reports completing every rubric field while Submit remains disabled; that tutor's task reference is not supplied.
> 
> The requested diagnostic set is still outstanding: task ID, required-field state, error and exact button behavior, plus error time for RP-3412 and RP-5337. Submission status remains unverified. Please assess these reports without assuming a shared cause.

**Still needs review:**
- Obtain the diagnostics requested in all four threads, including the affected tutor's task reference in the final thread and the error state and time requested by an engineer for the two grey-button reports.
- Severity is high under the team rubric.
- 3 earlier review flags are still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-engineering-handoff@1.0 (Current recorded state); rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review); knowledge_853068d0c5a7a6a9f5fd31d75f3fed75e15b411a16904ca4a407cc48a310f417

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 4, blocked 0; input 54151, output 15089 tokens; charged $0.2592.

