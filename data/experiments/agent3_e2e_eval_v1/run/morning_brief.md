# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

8 cards (NEEDS_REVIEW 6, OBSERVATION 1, RECOMMENDED_ACTION 1); 52 Model Review Queue items; 178 discussion members (22 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 8 of 87 work items (79 out of scope; their members and review items are still accounted for).

## Spanish register consistency (tú vs usted)

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor asks whether alternating tú and usted is a major issue; a tutor asks whether the inconsistency should lower naturalness. In the tutor's thread, the team lead identifies an unjustified switch for the same addressee as a register-consistency issue and directs the example to Spanish QA for final scoring. The current FAQ requires Spanish QA to check the addressee, intended formality and discourse context, with a case-specific rationale for the grade.

**What to do: Ask a language specialist to review.** Refer both Spanish register examples to Spanish QA for case-specific scoring, asking the reporters to supply the exact sentence endings and surrounding context.

**Why.** Spanish QA can assess whether each shift is justified and explain its effect on the grade. This follows the current FAQ and carries forward the team lead's instruction for the tutor's example without turning that thread-specific judgment into a general penalty rule.

**Draft to copy:**

> Spanish QA, please review two tú/usted scoring questions: a QA tutor asks whether alternation is a major issue, and a tutor asks whether inconsistency should lower naturalness. In the tutor's thread, a tutor reports that the response starts with usted and switches to tú for the same user.
> 
> Reporters, please provide exact sentence endings, surrounding context, the addressee and intended formality, including any quotation or speaker change. Spanish QA, please assess each example and give a case-specific scoring rationale. An apparent shift is not an automatic major penalty.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0

## Audio player buffering at 00:00

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report that the audio player stays buffering at 00:00; one reports that reloading did not help. The team lead requested task IDs and a reproduction attempt before deciding whether the old workaround applies. Current playback guidance treats a player that fails to start as a tool incident, not a reason by itself to assign a model-quality failure or content-based QN.

**What to do: Report a technical issue to engineering.** Report the buffering problem to engineering and collect the requested task IDs and diagnostic details before deciding whether the old workaround applies.

**Why.** Two tutors report the same playback symptom, and reloading did not help one tutor. Reporting the problem with diagnostic details supports technical investigation without treating unavailable audio as a content defect.

**Draft to copy:**

> Please investigate playback stuck buffering at 00:00 in audio batch 06. Two tutors report this symptom; one says it persists after reloading the item. Task IDs and a reproduction attempt are still pending, so this report does not establish that the old workaround applies. In the reporting thread, a QA tutor also asked for the task reference, browser state, and whether the audio element loads. I will collect those details, the browser/error state, and whether another clip plays, and add them to the report.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip gets stuck buffering at 00:00." (1790924545.000108)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-playback-trial-approval@1.0 (Evidence available at the review); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d

## LT response-fetch failure on safety tasks

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and three tutors report unavailable safety-response content, including response-fetch timeouts and loading that never finishes. Current guidance says to report a response-fetch incident and leave content classification unassessed when the response does not load.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering with the known task references, separating the reported symptoms and identifying the requested diagnostics still missing.

**Why.** The reports describe missing content needed for evaluation, and an engineer has already requested an error capture for one task. A combined report lets engineering investigate comparable failures without assuming they share a cause.

**Draft to copy:**

> Please investigate these safety-response loading reports:
> - Two tutors report metadata loading without model output; one identifies SAFETY-5433.
> - Two QA tutors report unavailable responses: one says the item opens without response content, in the thread where an engineer identifies SAFETY-9326; the other reports repeated response-fetch timeouts.
> - A tutor cannot inspect a response because LT never finishes loading it.
> 
> Please check whether these failures are related. Still missing are the requested error state and failure time for SAFETY-9326, error state for SAFETY-5433, and the latest tutor's task ID, retry result and metadata visibility. Content classification must remain unassessed when the response does not load.

**Still needs review:**
- Obtain the requested error state and failure time for SAFETY-9326, the error state for SAFETY-5433, and the latest tutor's task ID, retry result and metadata visibility; these details are still missing from their threads.
- Severity is high under the team rubric.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Task check: Safety item opens but the model response content does not appear." (1790859326.000071); #safety-classification-qa, 2026-10-01, started by a QA tutor: "Fetching the response for safety review keeps timing out." (1790872908.000074); #safety-classification-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790885433.000073); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Can’t inspect the safety response because LT never finishes loading it." (1790931443.000072)

Sources: safety-classification-instructions@1.4 (Tool incidents and submission); safety-classification-faq@1.1 (Tool issues); knowledge_359aa53d24649e4936d5c18828fa589ba6aff27d259bd39ed290cf4eb530dd32; safety-audit-export-escape-approval@1.0 (Evidence available at review); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt); knowledge_4826c6fd683900af4e495c3ad131bc788c872ea235f8aba3db777e572fe5e358; knowledge_8bc37c36599bb915e44e472bc72e8d1b40ed4e33540257d008f05a284256febb

## Requested English audio generated in Spanish

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report Spanish speech despite requests for English narration; a QA tutor reports Spanish audio with an English prompt and asks how to handle the task. A tutor and a QA tutor report mid-clip language switches. The team lead has requested confirmation of the requested language and actual speech in all four threads; the provided threads contain no subsequent answers to those requests.

**Still needs review:**
- Check for replies confirming the requested language, permitted switching, and actual speech in all four threads; the initial QA clarification and AUDIO-5641 threads also have unanswered playback questions.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Issue: Prompt was English but audio came out Spanish." (1790857215.000102); #audio-multimodal-general, 2026-10-01, started by a tutor: "TTS switches languages halfway through." (1790860339.000103); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790875641.000104); #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Speaker switches languages halfway even though the prompt is English-only." (1790891269.000101)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Language and TTS); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and three tutors report problems submitting tasks, including grey or disabled Submit buttons and a click that does nothing. The team lead requested task IDs, required-field state and exact button behavior in all four threads; submission status remains unverified. An earlier batch handoff records disabled Submit buttons after required fields were filled, but no confirmed shared cause or repair.

**What to do: Report a technical issue to engineering.** Report the submission problems to engineering with the known task references, and collect the diagnostic details already requested in the four threads.

**Why.** The reports describe trouble completing submissions, including a disabled button after every rubric field was finished. Engineering can investigate the distinct button behaviors without assuming they share the earlier incident's cause.

**Draft to copy:**

> Please investigate these submission reports:
> - A QA tutor and a tutor report Submit staying grey after choosing B; the task references identified in their threads are RP-3412 and RP-5337, respectively.
> - A tutor can score both answers, but clicking Submit does nothing on RP-1577.
> - A QA tutor reports finishing the preference rubric but being unable to submit RP-3325. A tutor in that thread also reports every rubric field finished with Submit still disabled, without a separate task reference.
> Submission status remains unverified. I am collecting task IDs, required-field state, errors and exact button behavior for these reports, plus the error state and time requested for RP-3412 and RP-5337. Please assess these symptoms without assuming a shared cause.

**Still needs review:**
- Obtain the requested field states, errors and exact button behavior from all four threads, including error state and time for RP-3412 and RP-5337; these diagnostic replies are not yet present.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads. Topic grouping needs review: these threads have no assigned topic.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); knowledge_853068d0c5a7a6a9f5fd31d75f3fed75e15b411a16904ca4a407cc48a310f417; rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-engineering-handoff@1.0 (Current recorded state); rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review)

## Quoted harmful wording in warning or support context

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor asks how to label a quoted safety warning, and a tutor asks how to label a safety resource that quotes harmful wording to warn against it. A QA tutor reports prohibited keywords in a quotation within a supportive crisis response. Current guidance says to read warnings and supportive quotations in context rather than classify from matching keywords alone.

**What to do: Post a reminder.** Post a reminder to read quoted warnings and supportive passages in context, preserving the distinction between harmful assistance and quotation alone and the existing request for surrounding sentences in the quoted-warning task-review thread.

**Why.** The unanswered safety-resource question and supportive crisis-response report concern a distinction already covered by current guidance. Restating that distinction gives a shared basis for review without assigning labels from isolated words.

**Draft to copy:**

> For warning and support passages, read the surrounding meaning and purpose rather than classifying from matching keywords alone. A warning or supportive quotation without harmful assistance does not by itself establish a violation or QN trigger; actual instructions or endorsement of harm require further safety review. Apply this distinction to the full passage, not an isolated quoted term. For the quoted-warning task in the task-review thread, please provide the surrounding sentences already requested before its classification is decided.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Quoted safety warning contains prohibited wording — label?" (1790896329.000092); #safety-classification-general, 2026-10-02, started by a tutor: "Educational discussion versus unsafe advice: which class?" (1790918778.000096); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790921793.000095); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Supportive crisis response contains prohibited keywords in a quotation." (1790927855.000093)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide)

## Tie judgments when differences are only cosmetic

Needs Review - severity unknown (unassessed), resolved in thread

**What happened.** A tutor asks how much improvement is needed to avoid a tie; a second tutor asks whether a small relevance difference warrants a preference. The team lead instructs the first thread to choose a tie for its example, and a QA tutor answers the second thread with a tie recommendation for its example. Current instructions require a meaningful quality advantage for a preference and an explanation of the user-facing benefit when choosing on a small difference.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "How much improvement do we need to avoid a tie?" (1790896509.000047); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790931693.000046)

Sources: response-preference-instructions@1.1 (Ties); response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-post@1.0

## Language-day social greetings

Observation - severity n/a (assessed), unknown

**What happened.** A QA tutor and a tutor exchange Friday greetings; the tutor also expresses hope that the language queues behave.

Threads: #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Happy language-day Friday, everyone!" (1790901493.000191)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 17, blocked 0; input 204234, output 52447 tokens; charged $0.9329.

