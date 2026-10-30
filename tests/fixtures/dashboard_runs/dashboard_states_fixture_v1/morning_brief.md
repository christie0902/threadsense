# Morning brief - 2026-10-02T12:00:00Z

Status: **INCOMPLETE**. Semantic judgments: TEST_FIXTURE. Hand-built TEST FIXTURE for dashboard states absent from the live smoke run (Recommended Action, Observation, reminder draft with a supported alternative, failed and unprocessed work). Not model output: card text is hand-written; citations and evidence entries are copied from agent3_overnight_offline_v2 (scripted).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 0 announcements (0 in the retrieval snapshot).

3 cards (NEEDS_REVIEW 1, OBSERVATION 1, RECOMMENDED_ACTION 1); 4 Model Review Queue items; 14 discussion members (11 on cards); 0 announcement-route members.

## Incomplete work

- [Test fixture] Topic that failed (TOPIC): **TOPIC_FAILED** - Test fixture: simulated pipeline failure. (1 members, 0 review items kept)
- [Test fixture] Topic not processed (budget) (TOPIC): **UNPROCESSED_BUDGET** - Test fixture: the run budget was exhausted before this topic. (2 members, 0 review items kept)

## [Test fixture] Fictional phone number quarantine handling

Recommended Action - severity low (assessed), unresolved - TEST_FIXTURE

**What happened.** Test fixture: tutors ask whether a made-up phone number in a fictional story still needs quarantine. The current clarification answers this; the older help-page section is superseded.

**What to do: Post a reminder.** Post a short reminder in the batch channel that points tutors to the current clarification.

**Why.** Test fixture: the question repeats and the current clarification already answers it.

**Draft to copy:**

> Reminder: a phone number that is clearly invented inside a fictional story follows the current clarification, not the older help-page section. If you are unsure whether a number is real, flag the task for review and keep the surrounding context.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "Story contains made-up phone number." (1790890012.001700); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is a clearly fake phone number still sensitive under the current policy?" (1790911772.000059); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: Story contains made-up phone number." (1790934673.000061)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-faq@1.1 (Quarantine and QN)

## [Test fixture] Repeated final line in exported audio

Observation - severity low (assessed), resolved in thread - TEST_FIXTURE

**What happened.** Test fixture: one tutor mentions a repeated final line in an exported clip; the thread already records the check that was done. Nothing needs to be done now.

**What to do: No action needed now.**

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Scoring)

## [Test fixture] Format adherence vs factual accuracy

Needs Review - severity medium (assessed), unresolved - TEST_FIXTURE

**What happened.** Test fixture: reviewers disagree on whether format adherence can outweigh a factual error. The team lead should confirm the wording before anything is posted.

**What to do: Post a reminder.** Post a reminder of the current priority between factual accuracy and format adherence.

**Why.** Test fixture: the same question appears in several threads.

**Draft to copy:**

> Reminder: when a response is factually wrong, format adherence does not make it the better response. Rate factual accuracy first, then format.

**Still needs review:**
- Test fixture: confirm the reminder wording before it is posted.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); response-preference-instructions@1.1 (Content-quality rubric)

## Model Review Queue

4 items (separate from the cards above):

- agent1 inherited_agent1_review: 3
- assisted_content_review assisted_content_review: 1

## Usage

Requests sent 0, blocked 0; input 0, output 0 tokens; charged $0.0000.

