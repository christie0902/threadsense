# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

8 cards (NEEDS_REVIEW 5, OBSERVATION 2, RECOMMENDED_ACTION 1); 52 Model Review Queue items; 178 discussion members (22 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 8 of 87 work items (79 out of scope; their members and review items are still accounted for).

## Spanish register consistency (tú vs usted)

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask how Spanish tú/usted inconsistency should affect scoring, including whether it merits a major penalty or lowers naturalness. Current guidance calls for Spanish QA review and a case-specific rationale; neither thread shows a final scoring assessment.

**What to do: Ask a language specialist to review.** Refer both Spanish register-scoring questions to Spanish QA for case-specific assessment, following the existing guidance and the tutor-thread instruction.

**Why.** Current guidance assigns this assessment to Spanish QA and requires context rather than an automatic major penalty. The referral follows the existing handling without creating a new scoring rule.

**Draft to copy:**

> Spanish QA, please assess the scoring impact of these two register questions:
> - A QA tutor reports alternating tú and usted and asks whether this is a major issue.
> - A tutor asks whether tú/usted inconsistency lowers naturalness; a second tutor reports usted followed by tú for the same user in that response.
> For each example, please obtain the exact sentence endings and surrounding prompt and response context, then check the addressee, intended formality and any quotation or speaker change. Please give a case-specific scoring rationale; an apparent shift is not an automatic major penalty.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0

## Audio player buffering at 00:00

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report audio stuck buffering at 00:00; one says reloading the item did not help. The team lead requires task IDs and a reproduction attempt before deciding whether the old workaround applies; those inputs are not present in the thread.

**What to do: Report a technical issue to engineering.** Report the persistent buffering issue to engineering, noting the missing diagnostic inputs and keeping any old-workaround decision separate.

**Why.** Current instructions classify failure to start playback as a tool incident. Engineering assessment fits the reported player behavior without assuming a cause or reviving an expired trial.

**Draft to copy:**

> Please investigate a playback issue in audio batch 06. Two tutors report the player stuck buffering at 00:00; one reports that reloading the item did not help. No recovery is recorded in the thread. Task IDs and a reproduction attempt are still being collected before any decision about the old workaround. Please assess the playback failure without assuming that the reload trial applies or that handling guidance establishes a repair.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip gets stuck buffering at 00:00." (1790924545.000108)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-approval@1.0 (Evidence available at the review); audio-playback-trial-post@1.0; knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d

## LT response-fetch failure on safety tasks

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and three tutors report safety responses that time out, fail to appear, or never finish loading, leaving output unavailable for review. Current guidance says to report response-fetch incidents and leave classification unassessed; the reports do not yet establish whether the problem is widespread or task-specific.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering, keeping the reported symptoms separate and preserving the current rule to leave unseen content unassessed.

**Why.** Unavailable responses need technical investigation rather than a new labeling rule. Current guidance already separates response-fetch incidents from content classification.

**Draft to copy:**

> Please investigate response loading in safety classification. Reports from October 1–2:
> - A QA tutor reports an item opens without response content; an engineer identifies SAFETY-9326 in that thread.
> - A QA tutor reports repeated response-fetch timeouts.
> - Two tutors report metadata loading without response content; one identifies SAFETY-5433.
> - A tutor reports LT never finishes loading the safety response, preventing inspection.
> The wider cause is not confirmed. Please assess these loading failures. Under current guidance, missing responses are reported as response-fetch incidents and content classification remains unassessed; unseen output must not receive an invented safety label.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Task check: Safety item opens but the model response content does not appear." (1790859326.000071); #safety-classification-qa, 2026-10-01, started by a QA tutor: "Fetching the response for safety review keeps timing out." (1790872908.000074); #safety-classification-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790885433.000073); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Can’t inspect the safety response because LT never finishes loading it." (1790931443.000072)

Sources: safety-classification-instructions@1.4 (Tool incidents and submission); safety-classification-faq@1.1 (Tool issues); knowledge_359aa53d24649e4936d5c18828fa589ba6aff27d259bd39ed290cf4eb530dd32; safety-audit-export-escape-approval@1.0 (Evidence available at review); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt)

## Quoted harmful wording in warning or support context

Needs Review - severity high (assessed), mixed

**What happened.** A tutor and two QA tutors raise classification concerns about harmful wording quoted in warnings or supportive responses. Current guidance requires reading the surrounding meaning rather than matching keywords, but several threads still lack a task-specific classification answer.

**What to do: Post a reminder.** Post a reminder to tutors and QA tutors explaining how current guidance distinguishes quoted warnings and supportive context from harmful assistance.

**Why.** Repeated classification concerns warrant a shared reminder of the directly applicable rule. The existing guidance supports clarification without changing policy or assigning labels from isolated keywords.

**Draft to copy:**

> Reminder for tutors and QA tutors: when a warning or support resource quotes harmful wording, read the surrounding meaning and purpose rather than classifying from matching keywords alone.
> 
> - A warning or supportive quotation without harmful assistance does not, by itself, establish a violation or QN trigger.
> - Actual instructions or endorsement of harm require further safety review.
> 
> For the quoted-warning task review, please provide the surrounding sentences requested before classification. This reminder explains the current rule; it does not assign a label to an individual passage without reviewing its context.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Quoted safety warning contains prohibited wording — label?" (1790896329.000092); #safety-classification-general, 2026-10-02, started by a tutor: "Educational discussion versus unsafe advice: which class?" (1790918778.000096); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790921793.000095); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Supportive crisis response contains prohibited keywords in a quotation." (1790927855.000093)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide)

## Requested English audio generated in Spanish

Needs Review - severity high (assessed), unresolved

**What happened.** Three tutors and two QA tutors report speech in a different language or a mid-clip language switch. The team lead has requested confirmation of the requested language and actual speech in all four threads; the retrieved conversations do not include replies completing those checks.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Issue: Prompt was English but audio came out Spanish." (1790857215.000102); #audio-multimodal-general, 2026-10-01, started by a tutor: "TTS switches languages halfway through." (1790860339.000103); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790875641.000104); #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Speaker switches languages halfway even though the prompt is English-only." (1790891269.000101)

Sources: audio-multimodal-faq@1.1 (Language and TTS); audio-multimodal-instructions@1.3 (Language and repeated audio); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** Three tutors and two QA tutors report problems submitting work, including disabled controls and a Submit click that does nothing. The team lead requested diagnostic details in all four threads and said submission status remains unverified.

**What to do: Report a technical issue to engineering.** Report the submission problems to engineering, keeping the distinct symptoms separate and marking the outstanding diagnostic details as pending.

**Why.** Engineering assessment fits the reported control failures, and current guidance specifies the evidence needed to investigate them. The earlier handoff does not establish a shared cause for these reports.

**Draft to copy:**

> Please investigate these submission reports:
> - A QA tutor on RP-3412 and a tutor on RP-5337 report that Submit stays grey after choosing B.
> - A tutor on RP-1577 can score both answers, but clicking Submit does nothing.
> - A QA tutor on RP-3325 reports finishing the preference rubric but being unable to submit; a tutor in that thread reports a disabled button after completing every rubric field.
> Diagnostic responses are pending. Please assess these symptoms separately before linking them to the earlier incident. Submission remains unverified; selecting a label alone does not confirm completion.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads. Topic grouping needs review: these threads have no assigned topic.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-engineering-handoff@1.0 (Current recorded state); knowledge_853068d0c5a7a6a9f5fd31d75f3fed75e15b411a16904ca4a407cc48a310f417; rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review)

## Tie judgments when differences are only cosmetic

Observation - severity low (assessed), resolved in thread

**What happened.** Two tutors ask when a small response difference warrants a preference rather than a tie. The team lead answers one example and a QA tutor answers the other with a tie; neither reply establishes a new project-wide threshold.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "How much improvement do we need to avoid a tie?" (1790896509.000047); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790931693.000046)

Sources: response-preference-instructions@1.1 (Ties); response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt)

## Language-day social greetings

Observation - severity n/a (assessed), unknown

**What happened.** A QA tutor posts a language-day Friday greeting, and a tutor replies with a Friday greeting and a hope that the language queues behave. Neither message reports a specific problem or asks a handling question.

Threads: #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Happy language-day Friday, everyone!" (1790901493.000191)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 16, blocked 0; input 193733, output 47597 tokens; charged $0.8634.

