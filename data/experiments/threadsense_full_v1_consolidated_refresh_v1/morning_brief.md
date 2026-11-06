# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

14 cards (NEEDS_REVIEW 11, RECOMMENDED_ACTION 3); 37 Model Review Queue items; 174 discussion members (64 on cards); 0 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 14 of 63 work items (49 out of scope; their members and review items are still accounted for).

## Benign mention of a minor and QN

Recommended Action - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor ask whether benign mentions of minors require quarantine or flagging, across four threads. Current guidance says a harmless mention alone is not a quarantine trigger, but three threads still lack a handling answer.

**What to do: Post a reminder.** Post a reminder that harmless mentions of minors alone do not require quarantine, while separate concerns still need checking.

**Why.** Current guidance directly answers the shared rule question, while three threads still lack a handling answer. A reminder addresses that uncertainty without changing the rule.

**Draft to copy:**

> Reminder on minor-related QN questions: a harmless mention of a child in a school, family or otherwise safe context does not by itself establish a quarantine trigger. Evaluate the surrounding content for any separate concern rather than treating the mention alone as sufficient. This is the distinction in the current FAQ and instructions; it does not mean every task mentioning a child is automatically safe or exempt from quarantine.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "A kid is mentioned in a harmless story; QN?" (1790893012.001800); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790918817.000068); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: A child is mentioned in a normal school story." (1790923242.000069); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Safe family context, but a minor's age is explicit." (1790923902.000070)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Context-sensitive classification)

## Spanish tú/usted register switching

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask how to grade Spanish tú/usted switching; the QA tutor also asks whether formal address should always be preferred. Current guidance calls for Spanish QA review and a case-specific grading rationale, not an automatic major penalty.

**What to do: Ask a language specialist to review.** Refer the unresolved Spanish register questions to Spanish QA for contextual review and case-specific scoring, retaining the separate thread requests.

**Why.** Current guidance assigns Spanish register assessment to Spanish QA and requires a case-specific grading rationale. Specialist review fits the remaining questions without turning a reported pronoun change into an automatic penalty.

**Draft to copy:**

> Spanish QA, please review these register questions:
> - Two tutors report responses beginning with usted and then using tú for the same user, in the formal-address and task-review threads.
> - A tutor separately reports register changes without requested informality.
> - A QA tutor asks whether alternation is major and whether formal address should always be preferred; a tutor asks whether inconsistency lowers naturalness.
> Please check addressee, intended formality, discourse context and quotations, and give a case-specific scoring rationale. An apparent shift is not an automatic major penalty.
> For the formal-address case, please provide the exact before/after sentences and target audience I requested, retain the full exchange, and clarify whether formal address was explicitly requested. Check possible addressee changes in that case and the unrequested-informality case. Final scoring for the task-review example remains with Spanish QA.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Should formal address always be preferred in ES?" (1790896116.000178); #multilingual-eval-general, 2026-10-02, started by a tutor: "Spanish register changes without the user requesting informality." (1790910015.000180); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0; multi-korean-referral@1.0 (Request)

## Which QN rule applies: old help page versus later announcement

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor and two tutors ask which QN rule applies or whether later guidance replaces older material. Current instructions and the FAQ establish that the fictional-contact trigger is superseded, but the exception does not replace unrelated safety controls.

**What to do: Post a reminder.** Post a scoped reminder explaining which fictional-contact rule applies and distinguishing that settled rule from the unresolved SAFETY-2292 document comparison.

**Why.** The current instructions and FAQ explicitly settle the fictional-contact branch, so that clarification need not wait for a general document reconciliation. Repeated questions justify restating the rule without deciding unidentified branches.

**Draft to copy:**

> QN clarification: under Instructions v1.4 and FAQ v1.1, clearly fictional placeholder contact details alone do not require QN. Check the surrounding material to establish that no real individual is identifiable and that no separate QN trigger applies.
> 
> This replaces the older help page's blanket fictional-contact trigger only—not unrelated safety controls. Actual identifiable private information still requires review. If details are ambiguous or another QN trigger exists, retain the evidence for review.
> 
> This reminder does not decide the unidentified conflicting branches raised for SAFETY-2292.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Help page still lists old quarantine trigger." (1790862407.000075); #safety-classification-general, 2026-10-02, started by a tutor: "Our pinned QN post contradicts the updated handbook section." (1790912292.000079); #safety-classification-general, 2026-10-02, started by a tutor: "Which safety quarantine rule applies after last week's change?" (1790924588.000076)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-doc-sync-approval@1.0 (Evidence); safety-doc-sync-outcome@1.0 (Follow-up inspection); knowledge_6be658d336d947f915ccc6de345828a558206039816fa6e91c7fe792b76207a8

## LT response content fails to load in comparison view

Needs Review - severity high (assessed), mixed

**What happened.** Four tutors and a QA tutor report that response content fails to appear for comparison. The team lead requested task references and error states in two threads; those inputs remain missing there, so whether the failures are widespread or task-specific is not settled.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering using the known symptoms and RP-8073, with the remaining diagnostics marked as pending.

**Why.** The reports describe a failure to obtain the content needed for comparison, which warrants engineering investigation. Current guidance already separates fetch incidents from response-quality judgments.

**Draft to copy:**

> Please investigate response-loading failures reported by four tutors and a QA tutor:
> - Two tutors in one thread report a timeout before Response A/B display and metadata loading without response content, respectively.
> - A tutor reports both panes spinning on RP-8073.
> - A tutor reports a second item also failing in two threads; a QA tutor reports fetch failure before comparison.
> The task references and error states requested in the first timeout and QA threads are pending. Please investigate the loading failure; these reports do not establish batch-wide impact. Current guidance treats panes that never load as fetch incidents, not evidence of response quality.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "LT times out before Response A and B are displayed." (1790897195.000027); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790908073.000029); #response-preference-qa, 2026-10-02, started by a QA tutor: "Response-fetch fails before I can compare this pair." (1790920271.000026)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); knowledge_7fc19a0d63fa4064c72475fc9f7a177f7d220630686ec558071baa2902726fcc

## QN handling for fictional contact details

Needs Review - severity high (assessed), mixed

**What happened.** Three QA tutors and two tutors ask how to handle fictional contact details across six threads; two QA tutors and one tutor report differing versions of a note.

**What to do: Update the documentation.** Correct the old QN help page's Contact details section to match the dated fictional-placeholder clarification, preserving all separate review controls.

**Why.** The FAQ explicitly calls for correcting the stale copy, and the earlier follow-up identifies that section as unfinished work. The general rule is already established; the supported change is to the conflicting help-page wording, not the current instructions or FAQ.

**Draft to copy:**

> Contact details
> 
> Clearly fictional placeholder phone numbers or email addresses alone do not require QN when the surrounding material establishes that no real individual is identifiable. Check and retain the surrounding context.
> 
> If the details could identify a real person, the fictional context is uncertain, or another required safety trigger applies, retain the task and evidence for review under the applicable rules. Actual identifiable private information still requires review.
> 
> The September 10, 2026 clarification replaces this section's former blanket initial-quarantine requirement for fictional contact details only. It does not waive unrelated safety controls.

**Still needs review:**
- Severity is high under the team rubric.
- 4 earlier review flags are still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790871263.000058); #safety-classification-general, 2026-10-01, started by a tutor: "Story contains made-up phone number." (1790890012.001700); #safety-classification-general, 2026-10-02, started by a tutor: "The prompt uses someone@example.test in a made-up story." (1790908195.000063); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is a clearly fake phone number still sensitive under the current policy?" (1790911772.000059); #safety-classification-general, 2026-10-02, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790922378.000060); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: Story contains made-up phone number." (1790934673.000061)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-fictional-pii-clarification@1.0 (Preamble); safety-pii-clarification-post@1.0; safety-doc-sync-outcome@1.0 (Follow-up inspection); safety-doc-sync-approval@1.0 (Evidence); knowledge_9006e0ce278e04204201b84be24e200621c3c8afdb8dfcab8f086380c614013c; safety-qn-help-page@1.0 (Contact details)

## Repeated final line in generated audio

Needs Review - severity high (assessed), mixed

**What happened.** Six tutors and two QA tutors report repeated endings in audio; two of those tutors specifically report repetition in exported audio. The team lead has requested file-versus-player checks in two threads, but those threads do not yet contain the results.

**What to do: Report a technical issue to engineering.** Report the repeated-ending examples to engineering for assessment, keeping exported-audio reports separate from cases still awaiting file-versus-player checks.

**Why.** Reports of repetition in exported audio warrant technical assessment without assuming a generation defect. Current guidance requires distinguishing generation from playback before calling the defect confirmed.

**Draft to copy:**

> Please assess these repeated-ending reports for generation versus playback problems. Six tutors and two QA tutors report repeated endings, including AUDIO-9012 (a tutor: final line twice, no apparent player glitch) and AUDIO-3533 (a QA tutor: last sentence twice).
> 
> - Two tutors report repetition in exported audio, not just playback.
> - Two tutors report doubled endings that are not reflected in the transcript.
> 
> For each example, record where repetition occurs and, if feasible, compare the downloaded file with player output. Keep those results separate from the initial symptom reports. These reports do not yet establish a confirmed generation defect.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Last phrase repeats verbatim in the generated answer." (1790913477.000124); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Scoring); audio-repeat-observation-review@1.0 (Evidence)

## Transcript and audio content mismatch

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and two tutors report differences between spoken content and reference text across four threads. A tutor's handling question for AUDIO-1507 remains unanswered, although the current FAQ explains how to record transcript/audio mismatches.

**What to do: Post a reminder.** Answer the tutor's AUDIO-1507 handling question with the current correspondence rule, keeping task-quality severity separate from playback classification.

**Why.** The current FAQ directly answers the tutor's unanswered handling question. The scoring rubric supplies criteria without requiring an unsupported task-specific severity judgment.

**Draft to copy:**

> For AUDIO-1507, record the exact transcript/audio mismatch as a correspondence issue, not a playback failure. Distinguish words missing from the audio from mistakes in the reference transcript.
> 
> For task-quality scoring:
> - Missing or contradicted key content is a major correspondence defect.
> - A limited omission that does not change meaning is minor.
> 
> Apply these criteria to the actual differing content. These major/minor labels describe task-quality defects, not operational incident severity.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Transcript includes words the voice never said." (1790868669.000136); #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Voice says thirteen but subtitle says thirty." (1790875184.000139); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: Transcript shows a sentence that never appears in the recording." (1790881507.000137); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790904522.000135); #audio-multimodal-general, 2026-10-02, started by a tutor: "Should we score omissions in the audio or errors in the transcript field?" (1790909920.000138)

Sources: audio-multimodal-faq@1.1 (Scoring); audio-multimodal-instructions@1.3 (Content-quality rubric); audio-multimodal-instructions@1.3 (Overlap and transcript correspondence)

## Vietnamese regional vocabulary and target locale

Needs Review - severity high (assessed), mixed

**What happened.** Vietnamese regional-wording questions remain unanswered in three threads, including whether to penalize bắp on MULTI-1784. In three other threads, the team lead requested confirmation of the target audience before setting scoring guidance; the provided threads contain no subsequent audience confirmation.

**What to do: Post a reminder.** Post a targeted reminder to tutors and QA tutors to confirm the intended audience before penalizing Vietnamese regional vocabulary.

**Why.** Current guidance already supplies the handling rule, but repeated questions remain unanswered. A targeted reminder applies that rule without inventing case-specific penalties.

**Draft to copy:**

> Reminder for Vietnamese regional-wording reviews: confirm the requested audience or locale before penalizing regional vocabulary. Vocabulary natural for that audience is acceptable even when a reviewer prefers a different regional term; preference alone does not establish an error.
> 
> Please provide the exact phrase, prompt context and intended audience for unresolved cases. If the required locale is unclear, obtain that context before deciding. In the flagged-phrase and MULTI-1784 discussions, please also answer the tutors' requests for both reviewers' locale assumptions behind their scores. This reminder does not decide any individual case's penalty.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Is this northern wording acceptable for southern users?" (1790857852.000186); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Regional phrase sounds fine in VN but QA flags it." (1790869911.000187); #multilingual-eval-general, 2026-10-01, started by a tutor: "Issue: The answer uses 'bắp' but the prompt seems aimed at northern readers." (1790881784.000184); #multilingual-eval-general, 2026-10-01, started by a tutor: "Is 'heo' instead of 'lợn' acceptable for this target audience?" (1790885012.001600); #multilingual-eval-general, 2026-10-02, started by a tutor: "Vietnamese wording is natural in the south, but QA reviewer is from the north." (1790905292.000185); #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790924170.000183)

Sources: multilingual-eval-instructions@1.2 (Regional variation and naturalness); multilingual-eval-faq@1.1 (Regional variation); multi-locale-announcement@1.0; multi-japanese-review-pending@1.0 (Case packet)

## Cosmetic differences: tie versus preference

Needs Review - severity medium (assessed), mixed

**What happened.** A tutor asks whether slightly clearer wording warrants choosing B on RP-4354, and the thread has no final answer. Current instructions require a meaningful quality advantage, not cosmetic phrasing alone; the team lead has requested task-specific user benefits in two other threads.

**What to do: Post a reminder.** Post a focused reminder that small-difference preferences require an explained user benefit, keeping individual pair decisions tied to their task requirements.

**Why.** The current instructions directly address the unresolved distinction between cosmetic wording and a meaningful quality advantage. A focused reminder can answer that general question without extending example-specific tie answers to other pairs.

**Draft to copy:**

> Reminder for this batch: choose a tie when neither response has a meaningful quality advantage. Cosmetic phrasing alone does not justify a preference. When selecting a response on a small difference, explain the user-facing benefit rather than only saying it sounds clearer or nicer.
> 
> For RP-4354, please provide the task requirements and explain what benefit the clearer wording adds. For the two threads where I requested an explanation before calling a slight preference, please provide that explanation. Keep each answer specific to its pair; do not generalize another pair's tie decision without matching its scope.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Both are okay, but B sounds a bit clearer." (1790859242.000048); #response-preference-general, 2026-10-01, started by a tutor: "How much improvement do we need to avoid a tie?" (1790896509.000047); #response-preference-general, 2026-10-02, started by a tutor: "Both are acceptable." (1790904354.000049); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790931693.000046); #response-preference-qa, 2026-10-02, started by a QA tutor: "A is cleaner and B is more detailed; does that warrant slight preference?" (1790940523.000045)

Sources: response-preference-instructions@1.1 (Ties); response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment); rp-tie-calibration-post@1.0

## Older scoring guide screenshot versus newer pinned note

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and two tutors ask which scoring document applies; a further tutor reports that the older screenshot disagrees with the newer pinned note. For RP-4295, the team lead has requested both dated versions and withheld any supersession decision until the change history is verified.

**Still needs review:**
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "The guide example contradicts last Friday’s alignment." (1790874467.000044); #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790893703.000042); #response-preference-general, 2026-10-01, started by a tutor: "Task check: The example in the rubric says one thing, but Friday's alignment says another." (1790894295.000041); #response-preference-qa, 2026-10-02, started by a QA tutor: "Should we follow the pinned update or the older scoring guide screenshot?" (1790915967.000043)

Sources: response-preference-instructions@1.1 (Content-quality rubric); response-preference-instructions@1.1 (Factual errors and citations); response-preference-instructions@1.1 (Tool incidents and submission); knowledge_ccd188f235fa1da9e1f0079f64889a4ba5934c753e5e9c6492251743cc837815; knowledge_7fc19a0d63fa4064c72475fc9f7a177f7d220630686ec558071baa2902726fcc; rp-audit-manifest-approval@1.0 (Evidence available at review); rp-audit-manifest-post@1.0; rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment)

## Overlapping speech in transcription

Needs Review - severity medium (assessed), mixed

**What happened.** Current guidance says to mark and timestamp the affected interval and preserve usable audio, rather than infer whole-clip failure from a short interval.

**What to do: Post a reminder.** Post a reminder explaining how to mark and timestamp overlapping speech while keeping usable audio and avoiding automatic whole-clip failure.

**Why.** Repeated questions concern interval marking and whole-clip failure, which the current instructions and FAQ address. A reminder can answer the remaining general handling question without replacing the team lead's case-specific timestamp requests.

**Draft to copy:**

> Overlap reminder for this batch:
> - Mark the overlapping or unintelligible interval and timestamp the affected span.
> - Keep the usable portions of the clip; do not infer a whole-clip failure from a short affected interval.
> - Distinguish words missing from the audio from mistakes in the reference transcript.
> These are the current instructions and FAQ: a short affected interval is not, by itself, a reason to discard the whole recording.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Two people talk at once — mark unintelligible?" (1790864427.000131); #audio-multimodal-general, 2026-10-01, started by a tutor: "Background speaker gets transcribed as main speaker." (1790890932.000133); #audio-multimodal-general, 2026-10-02, started by a tutor: "Two speakers talk over each other for two seconds." (1790921338.000134); #audio-multimodal-general, 2026-10-02, started by a tutor: "Could QA clarify this case: How much overlap is allowed before the transcription fails the rubric?" (1790941015.000132)

Sources: audio-multimodal-instructions@1.3 (Overlap and transcript correspondence); audio-multimodal-faq@1.1 (Scoring)

## Public business contact details are not private PII

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and three tutors ask about PII handling for a business listing, a news article, a shop phone number and an official-page address. The team lead answered three threads; the shop-phone thread still has an unanswered QA check about business versus private contact.

**What to do: Post a reminder.** Post a focused reminder of the business-contact rule and ask the tutor on SAFETY-7618 to answer the QA tutor's check.

**Why.** The current FAQ and instructions already supply the rule, so no policy change is needed. A reminder can address the remaining question without treating a tutor's description as a completed review.

**Draft to copy:**

> Official business phone numbers and addresses are not private individual PII by themselves. Check that the details really are official business contacts, rather than private individual information or a personal residence. Official business contact information alone does not establish a QN trigger; identifiable private individual information still requires safety review.
> 
> For the tutor reviewing SAFETY-7618: please answer the QA tutor's question in that task's thread, with the relevant source context showing whether the number is explicitly published for business contact or tied to a private individual.

**Still needs review:**
- 2 earlier review flags are still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Public business listing has a phone number — PII?" (1790874667.000081); #safety-classification-general, 2026-10-01, started by a tutor: "What if the name and address are from a news article?" (1790886010.000083); #safety-classification-general, 2026-10-02, started by a tutor: "Could QA clarify this case: Response includes a shop's public phone number." (1790917618.000080); #safety-classification-general, 2026-10-02, started by a tutor: "The address is on the official business page." (1790919200.000082)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Context-sensitive classification); safety-classification-instructions@1.4 (Classification and handling guide); safety-qn-help-page@1.0 (Contact details); safety-doc-sync-approval@1.0 (Evidence)

## When a wrong date or year is a major factual error

Needs Review - severity medium (assessed), mixed

**What happened.** Three QA tutors and three tutors raise questions or concerns about grading factual errors, including wrong dates and years. Current guidance already bases major versus minor on whether the error changes the central conclusion or the answer a user would act on.

**What to do: Post a reminder.** Post a reminder that date errors are graded by their effect on the central conclusion or actionable answer, not merely by being wrong.

**Why.** The current instructions and FAQ answer the recurring threshold question, while several threads still lack a settled answer. A reminder can address that uncertainty without inventing a new threshold or assigning unsupported task grades.

**Draft to copy:**

> Reminder for this batch: judge a wrong date or year by its effect on the answer.
> - Major: the error changes the central conclusion or the answer a user would act on.
> - Minor: it is a nonessential background error with no effect on that conclusion or recommendation.
> A date being wrong does not, by itself, settle the grade. This restates the current instructions and FAQ; it does not assign a grade to any individual example discussed so far.

**Still needs review:**
- 2 earlier review flags are still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Does this incorrect date count as major?" (1790857505.000025); #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790866580.000020); #response-preference-qa, 2026-10-01, started by a QA tutor: "Would one wrong year in an otherwise correct answer count as a major error?" (1790868851.000023); #response-preference-qa, 2026-10-01, started by a QA tutor: "Rubric example calls this minor, but it changes the final recommendation." (1790870514.000021); #response-preference-general, 2026-10-01, started by a tutor: "Issue: Is the key fact being inaccurate enough to trigger major even if tone is fine?" (1790877012.001300); #response-preference-qa, 2026-10-01, started by a QA tutor: "Anyone else seeing this?" (1790893656.000022); #response-preference-general, 2026-10-02, started by a tutor: "Rubric says significant factual error; how big is significant?" (1790914946.000024)

Sources: response-preference-instructions@1.1 (Factual errors and citations); response-preference-instructions@1.1 (Content-quality rubric); response-preference-faq@1.1 (Factual errors)

## Format compliance versus accuracy

Needs Review - severity unknown (unassessed), mixed

**What happened.** The current FAQ requires separate scoring and provides conditional team lead confirmation, not a universal priority rule; the reported comparisons remain undecided.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.
- The advisor proposed "Post a reminder", but the evidence did not show a need to intervene now, so no action is recommended.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); response-preference-instructions@1.1 (Content-quality rubric); rp-tie-calibration-outcome@1.0 (TL assessment)

## Consolidated topics

14 consolidated issues from 29 Agent 2 topics (PREPARED_AUDIT).

- **QN handling for fictional contact details** (2 topics)
- **Spanish tú/usted register switching** (2 topics)
- **When a wrong date or year is a major factual error** (3 topics)
- **Cosmetic differences: tie versus preference** (2 topics)
- **Older scoring guide screenshot versus newer pinned note** (2 topics)
- **Public business contact details are not private PII** (2 topics)
- **Overlapping speech in transcription** (2 topics)
- **Which QN rule applies: old help page versus later announcement** (2 topics)
- **Transcript and audio content mismatch** (2 topics)
- **Format compliance versus accuracy** (2 topics)
- **Benign mention of a minor and QN** (2 topics)
- **Repeated final line in generated audio** (2 topics)
- **Vietnamese regional vocabulary and target locale** (2 topics)
- **LT response content fails to load in comparison view** (2 topics)

## Processing history

Kept out of issue clustering by Agent 1 relevance; identities and review obligations kept:

- C_SAFETY_GENERAL 1790894591.000100: PROCESSING_HISTORY (ROUTINE_ADMIN; not clustered). Where the team avatar image is saved: administrative, no bearing on annotation work, model behavior, tools or working conditions.
- C_MULTI_GENERAL 1790901493.000191: PROCESSING_HISTORY (SOCIAL_ONLY; not clustered). Language-day greetings only; no project content.
- C_RP_GENERAL 1790911349.000052: PROCESSING_HISTORY (SOCIAL_ONLY; not clustered). Well-wishes and a remark that the chat is quiet; no project content.

## Model Review Queue

37 items (separate from the cards above):

- agent1 inherited_agent1_review: 37

## Usage

Requests sent 32, blocked 0; input 471824, output 128437 tokens; charged $2.2280.

