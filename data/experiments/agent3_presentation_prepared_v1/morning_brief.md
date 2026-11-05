# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: SCRIPTED_MOCK. Scripted: prepared pilot judgments (SCRIPTED_PILOT) for pilot topics, a placeholder that judges nothing (SCRIPTED_PLACEHOLDER) elsewhere; says nothing about model quality.

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

5 cards (NEEDS_REVIEW 3, OBSERVATION 1, RECOMMENDED_ACTION 1); 52 Model Review Queue items; 178 discussion members (13 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 5 of 87 work items (82 out of scope; their members and review items are still accounted for).

## Spanish register consistency (tú vs usted)

Recommended Action - severity medium (assessed), mixed - SCRIPTED_PILOT

**What happened.** A QA tutor asks whether alternating tú and usted is a major issue; a tutor asks whether the inconsistency should lower naturalness. In the tutor's thread, the team lead identifies an unjustified switch for the same addressee as a register-consistency issue and directs the example to Spanish QA for final scoring.

**What to do: Ask a language specialist to review.** Refer both Spanish register examples to Spanish QA for case-specific scoring, asking the reporters to supply the exact sentence endings and surrounding context.

**Why.** Spanish QA can assess whether each shift is justified and explain its effect on the grade. This follows the current FAQ and carries forward the team lead's instruction for the tutor's example without turning that thread-specific judgment into a general penalty rule.

**Draft to copy:**

> Spanish QA, please review two tú/usted scoring questions: a QA tutor asks whether alternation is a major issue, and a tutor asks whether inconsistency should lower naturalness. In the tutor's thread, a tutor reports that the response starts with usted and switches to tú for the same user.
> 
> Reporters, please provide exact sentence endings, surrounding context, the addressee and intended formality, including any quotation or speaker change. Spanish QA, please assess each example and give a case-specific scoring rationale. An apparent shift is not an automatic major penalty.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Five people report trouble submitting tasks, including grey or disabled Submit buttons and a click that does nothing. The team lead asked for task IDs, required-field state and exact button behavior in all four threads; submission status is still unverified.

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

Needs Review - severity medium (assessed), mixed - SCRIPTED_PILOT

**What happened.** A QA tutor and a tutor ask how to label safety text that quotes harmful wording to warn against it; a QA tutor reports a similar quotation in a supportive crisis response. Current guidance already answers this: read the passage's meaning and purpose, not matching keywords.

**What to do: Post a reminder.** Post a reminder to read quoted warnings and supportive passages in context, preserving the distinction between harmful assistance and quotation alone and the existing request for surrounding sentences in the quoted-warning task-review thread.

**Why.** The unanswered safety-resource question and supportive crisis-response report concern a distinction already covered by current guidance. Restating that distinction gives a shared basis for review without assigning labels from isolated words.

**Draft to copy:**

> For warning and support passages, read the surrounding meaning and purpose rather than classifying from matching keywords alone. A warning or supportive quotation without harmful assistance does not by itself establish a violation or QN trigger; actual instructions or endorsement of harm require further safety review. Apply this distinction to the full passage, not an isolated quoted term. For the quoted-warning task in the task-review thread, please provide the surrounding sentences already requested before its classification is decided.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Quoted safety warning contains prohibited wording — label?" (1790896329.000092); #safety-classification-general, 2026-10-02, started by a tutor: "Educational discussion versus unsafe advice: which class?" (1790918778.000096); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790921793.000095); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Supportive crisis response contains prohibited keywords in a quotation." (1790927855.000093)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide)

## Tie judgments when differences are only cosmetic

Needs Review - severity unknown (unassessed), resolved in thread - SCRIPTED_PILOT

**What happened.** A tutor asks how much improvement is needed to avoid a tie; a second tutor asks whether a small relevance difference warrants a preference. Both threads were answered with a tie for their own examples, consistent with current guidance.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "How much improvement do we need to avoid a tie?" (1790896509.000047); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790931693.000046)

Sources: response-preference-instructions@1.1 (Ties); response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-post@1.0

## Language-day social greetings

Observation - severity n/a (assessed), unknown - SCRIPTED_PILOT

**What happened.** A QA tutor and a tutor exchange Friday greetings; the tutor also expresses hope that the language queues behave.

Threads: #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Happy language-day Friday, everyone!" (1790901493.000191)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 0, blocked 0; input 0, output 0 tokens; charged $0.0000.

