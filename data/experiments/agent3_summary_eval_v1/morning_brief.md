# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

2 cards (NEEDS_REVIEW 2); 52 Model Review Queue items; 178 discussion members (7 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 2 of 87 work items (85 out of scope; their members and review items are still accounted for).

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and three tutors report submission problems: a grey or disabled Submit button, a click that does nothing, or LT not allowing submission after completing the rubric.

**Still needs review:**
- Upstream review flags remain open for two member-thread interpretations and the announcement. This draft uses the underlying messages rather than the earlier interpretations and relies only on the team lead's directing sentence in the announcement, not its tutor reply. Requested diagnostic inputs are still missing.
- Severity is high under the team rubric.
- 3 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- The revision step did not complete (a request limit was reached); details are in the diagnostics.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review)

## Format adherence vs factual accuracy

Needs Review - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor ask how to compare responses when requested format and other response strengths differ. The current FAQ requires separate scoring and case evidence rather than a universal tie-break rule; in one thread, the team lead has requested the exact formatting instruction before weighing the responses.

**What to do: Post a reminder.** Post a reminder across the three threads to score format and accuracy separately and collect the prompt and both responses for any preference the applicable guidance does not settle.

**Why.** The repeated questions concern the same comparison process, which the current FAQ already describes without setting a universal winner. Collecting the actual pairs also addresses the missing instruction requested by the team lead in one thread.

**Draft to copy:**

> For this batch, compare format compliance and factual accuracy separately; neither automatically wins every pair.
> - Check the exact prompt to establish whether the requested structure was mandatory. A missing explicit required format is a major instruction-adherence defect, separate from factual accuracy.
> - Judge the actual pair using the applicable guidance; do not infer a general priority rule from one example.
> - If preference remains unsettled, provide the prompt, both responses, and the separate defect assessments for team lead confirmation.
> For the thread awaiting the exact formatting instruction, please supply that wording before the responses are weighed.

**Still needs review:**
- The inherited review flag on the JSON-versus-prose thread remains open: the tutor's suggestion must not be treated as authoritative guidance. Case-specific preference review still awaits the prompts and both responses, including the exact instruction requested by the team lead.
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); rp-tie-calibration-outcome@1.0 (TL assessment); response-preference-instructions@1.1 (Content-quality rubric)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 4, blocked 0; input 60497, output 12719 tokens; charged $0.2482.

