# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

2 cards (NEEDS_REVIEW 2); 52 Model Review Queue items; 178 discussion members (7 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 2 of 87 work items (85 out of scope; their members and review items are still accounted for).

## QA calibration on disputed tie decisions

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors report that QA marked their ties wrong; one also reports that near-identical tasks were flagged after a tie score passed the previous week. In the RP-9595 thread, the team lead identified inconsistent QA feedback and requested both rationales for comparison before changing the tie threshold. The current FAQ calls for comparing disputed pairs, prompt requirements and both rationales, while checking whether the cases are actually comparable.

**What to do: Schedule a short review session.** Arrange a focused review with the QA reviewers of the disputed tie decisions once the pairs, relevant prompt requirements and both rationales are available.

**Why.** Comparing the decisions against the same criterion can show whether the cases are genuinely comparable before any threshold change is considered. The earlier batch's review improved agreement in its sample, but does not establish what the result will be here.

**Draft to copy:**

> Please prepare the disputed tie cases for a focused QA review. Two QA tutors report ties marked wrong, including RP-9595; one also reports flags on near-identical tasks after a tie score passed last week. A tutor reports acceptance one day and rejection of a similar pair the next.
> 
> Please provide:
> - The disputed pairs and relevant prompt requirements.
> - Both QA rationales, including those requested in the RP-9595 thread.
> 
> We will compare whether the cases match and whether a preference has a meaningful user-facing benefit. Keep conclusions specific to the reviewed pairs; this review does not announce a new tie threshold.

**Still needs review:**
- Check whether both rationales requested in the RP-9595 thread, together with the disputed pairs and relevant prompt requirements, have arrived before holding the review.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

Sources: response-preference-instructions@1.1 (Ties); response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment); rp-tie-calibration-post@1.0

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and three tutors report problems submitting tasks, including grey or disabled Submit buttons and a Submit click that does nothing. The team lead requested task IDs, required-field states and exact button behavior in all four threads, where submission status remains unverified. An earlier batch-15 handoff records similar disabled-button reports sent to engineering, but no confirmed shared cause or repair.

**What to do: Report a technical issue to engineering.** Report the five submission reports to engineering, distinguishing their symptoms and collecting the missing diagnostic details already requested in the four threads.

**Why.** The reports include inability to submit after completing rubric fields, which warrants technical assessment rather than a rubric reminder. An earlier engineering handoff provides useful comparison, but neither it nor the browser-zoom review establishes a cause or fix for these reports.

**Draft to copy:**

> Please assess these submission reports from batch 15:
> - A QA tutor and a tutor report Submit staying grey after choosing B; the corresponding threads identify RP-3412 and RP-5337.
> - A tutor can score both answers, but clicking Submit does nothing on RP-1577.
> - A QA tutor reports finishing the preference rubric but being unable to submit RP-3325.
> - A tutor in the RP-3325 thread reports completing every rubric field while Submit remains disabled; that tutor's task ID still needs confirmation.
> 
> Submission status remains unverified. I am collecting task IDs, required-field states, errors and exact button behavior from these threads, plus the LT error state and time an engineer requested for RP-3412 and RP-5337. Please compare these symptoms with the earlier batch-15 handoff without assuming a shared cause.

**Still needs review:**
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

Requests sent 4, blocked 0; input 54653, output 14391 tokens; charged $0.2532.

