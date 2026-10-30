# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

9 cards (NEEDS_REVIEW 9); 52 Model Review Queue items; 178 discussion members (30 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 9 of 87 work items (78 out of scope; their members and review items are still accounted for).

## Audio player buffering at 00:00

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report that the audio player stays buffering at 00:00; one reports that reloading did not help. The team lead requested task IDs and a reproduction attempt before deciding whether an old workaround applies.

**What to do: Post a reminder.** Post a reminder in the buffering thread to report the required diagnostic details and leave content quality unassessed while the old workaround's applicability remains undecided.

**Why.** The current instructions and batch announcement already explain how to handle unavailable playback. A reminder gives the affected tutors a next step without presenting the expired reload trial as a current fix.

**Draft to copy:**

> For this batch, report playback stuck buffering at 00:00 as a tool incident and leave content quality unassessed.
> - Provide the task ID, browser/error state, whether the audio element loads, and whether another clip plays.
> - Include the steps and result of a reproduction attempt, noting any reload already tried.
> - Do not choose content QN solely because playback is unavailable.
> This is handling guidance, not confirmation of a fix. The earlier reload trial expired and covered the previous batch only. In this thread, the team lead requested task IDs and a reproduction attempt before deciding whether that workaround applies.

**Still needs review:**
- Whether the old workaround applies still needs review of the requested diagnostic details and the earlier trial's outcome or extension decision, which the records retrieved for this run do not show. The reminder does not authorize that workaround.
- Severity is high under the team rubric.
- Some advisor statements were not supported by the evidence and are not shown.
- Open question: Does the earlier reload workaround apply to this batch after the requested task IDs and reproduction attempt are reviewed?
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip gets stuck buffering at 00:00." (1790924545.000108)

Sources: knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-approval@1.0 (Evidence available at the review); audio-playback-trial-post@1.0; audio-playback-trial-approval@1.0 (State at this record); audio-multimodal-instructions@1.3 (Tool incidents and submission)

## LT audio player playback failure

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and three tutors report LT playback failures and ask whether to use QN, recalling a possible earlier workaround. Current guidance says to report a technical issue rather than judge unavailable audio; the earlier reload trial did not establish a dependable workaround and was not extended to later queues.

**What to do: Report a technical issue to engineering.** Send an engineer one consolidated playback report with the known task references and request the missing error states, times, and reproduction details from the affected QA tutor and tutors.

**Why.** An engineer has requested error details, and current guidance calls for reporting playback failures as technical issues. The earlier trial's reviewed outcome does not support recommending reload as a dependable workaround for this batch.

**Draft to copy:**

> A QA tutor and three tutors report LT playback failures in Audio batch 06. Known references: AUDIO-2197, AUDIO-6012, AUDIO-4294; one tutor's task ID still needs collecting. A tutor also reports a visible waveform with no sound after pressing Play. Please investigate; the wider cause is not confirmed. We still need error states and times, reproduction attempts, and whether another clip plays, retaining both task references where available. Current guidance is to report the technical issue, not assign a model-quality failure or content QN solely from unavailable playback. The earlier one-reload trial restored playback in two of six attempts and was not extended to later queues.

**Still needs review:**
- Upstream review flags remain open for the QA tutor's failed-workaround interpretation and one tutor's resolution assessment. This draft does not infer a workaround attempt from recurrence or playback recovery from handling instructions.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Open question: What is causing the current playback failures, and what will restore playback on the affected tasks?

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Player never loads, should I QN?" (1790882197.000111); #audio-multimodal-general, 2026-10-01, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790896012.001900); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790920171.000109); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790934294.000106)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-multimodal-faq@1.1 (Playback and tool issues); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-approval@1.0 (Evidence available at the review); audio-playback-trial-post@1.0; audio-playback-trial-outcome@1.0 (Trial observation); knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d

## QA calibration on disputed tie decisions

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors report disputed tie judgments, and a tutor reports different QA outcomes on similar pairs. The team lead requested both rationales for calibration before changing the tie threshold.

**What to do: Schedule a short review session.** Arrange a batch-15 calibration review of the disputed pairs, collecting the relevant prompt constraints and both written QA rationales before considering any threshold change.

**Why.** This follows the current FAQ and the team lead's request in the latest thread. Earlier calibration improved agreement only in its reviewed sample, so this batch needs its own comparison rather than an assumed fix.

**Draft to copy:**

> For the disputed batch-15 ties, please share the pairs, relevant prompt constraints and both written QA rationales, including the materials for RP-9595. We will compare the rationales against the same meaningful-user-benefit criterion and check whether the cases are actually comparable before considering any change to the tie threshold. Cosmetic phrasing alone usually does not establish that benefit. Earlier replies justified ties for their specific pairs; they should not be applied to other pairs without matching the scope. Please bring the missing materials for a calibration review.

**Still needs review:**
- The upstream reviews for the two later threads remain open. Review the latest pair comparison when the requested materials arrive; do not treat the earlier pair-specific replies as proof that QA scores were corrected.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.
- Open question: Are the latest disputed pairs actually comparable once their prompt constraints and both written QA rationales are reviewed, and which judgments does that comparison support?

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

Sources: response-preference-faq@1.1 (Ties and preferences); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment)

## Repeated final line in exported audio

Needs Review - severity high (assessed), unresolved

**What happened.** A QA tutor and a tutor asked how to handle repeated endings; three other tutors report repetition in exported audio or the recording. The cause remains unconfirmed.

**What to do: Post a reminder.** Post a reminder for audio batch 06 to record repeated spans, compare the downloaded file with player output where feasible, and document transcript mismatches without treating the cause as confirmed.

**Why.** The questions and reports warrant a shared reminder of current handling. This collects the evidence needed to distinguish repetition in the recording from playback behavior without announcing an unverified generation defect.

**Draft to copy:**

> Reminder for audio batch 06: when an ending or phrase repeats, record where the repetition occurs.
> - If feasible, compare the downloaded file with the LT player output and record what happens in each.
> - If the transcript and recording disagree, record the exact mismatch as a correspondence issue. Distinguish a recording error from a reference-transcript error; do not classify the mismatch as a playback failure.
> - Do not call repetition a confirmed generation defect until the available evidence distinguishes generation from playback.
> The reported repetition is not yet a confirmed technical cause; these steps follow the current instructions and FAQ.

**Still needs review:**
- The tutor's transcript comparison still needs review; treat it as a report, not verification of a generation defect.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Open question: For AUDIO-9012 and AUDIO-3533, does a downloaded-file versus LT-player comparison establish whether the repetition exists in the file itself?

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Scoring); audio-repeat-observation-review@1.0 (Evidence)

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**What to do: Report a technical issue to engineering.** Collect the missing field states, errors, times and exact button behavior for the reported tasks, then send engineering one report asking it to compare these examples with the earlier batch handoff.

**Why.** Two QA tutors and three tutors report submission problems, and an engineer has already requested diagnostic details. A combined report follows current instructions without assuming that the earlier incident explains these reports or that any reported task was submitted.

**Draft to copy:**

> Please investigate these batch-15 Submit reports:
> - RP-3412 and RP-5337: a QA tutor and a tutor respectively report a grey button after selecting B.
> - RP-1577: a tutor reports that clicking Submit does nothing after scoring both answers.
> - RP-3325: a QA tutor reports blocked submission after finishing the rubric; a tutor in that thread separately reports a disabled button after completing every field.
> We are collecting required-field states, errors, times and exact button behavior. Submission status remains unverified. Please compare these examples with the September 28 handoff without assuming the same cause, and confirm whether LT recorded submissions.

**Still needs review:**
- Review the unassigned grouping before sending: the projection-gap flag, two upstream member-interpretation review flags and the announcement's authority-review flag remain open. The draft relies on member messages and current instructions, not those interpretations or the announcement's context reply.
- Severity is high under the team rubric.
- 3 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Open question: Do these new task reports match the earlier engineering incident, and did LT record successful submissions for any of the reported tasks?

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-engineering-handoff@1.0 (Current recorded state); rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review); rp-tie-calibration-approval@1.0 (Context)

## Fictional phone number quarantine handling

Needs Review - severity medium (assessed), unresolved

**What happened.** Two tutors and a QA tutor asked how to handle fictional phone numbers; the QA tutor reports that two versions of the note seem to differ. Current guidance identifies the older help-page wording as stale and gives the rule and its effective date.

**What to do: Update the documentation.** Correct the older QN help page’s Contact details section to reflect the September 10 fictional-placeholder clarification while preserving unrelated safety controls.

**Why.** The two tutors’ questions and the QA tutor’s report show uncertainty about task handling. The current FAQ identifies the stale section, and the dated clarification supplies the rule and change date requested in the team lead’s thread instructions.

**Draft to copy:**

> Please correct the Contact details section of QN help page v1.0 using the clarification effective September 10, 2026, at 13:00 UTC:
> - Verified fictional placeholder phone numbers or email addresses alone do not require QN when the surrounding evidence establishes that no real individual is identifiable.
> - If real-person identification is possible, the fictional context is uncertain, or another required safety trigger applies, retain the task for review under the applicable rules.
> - Retain the surrounding context with flagged tasks.
> Replace only the blanket initial-quarantine requirement for fictional contact details; preserve unrelated safety and privacy controls.

**Still needs review:**
- The QA thread’s upstream review flag remains open. Its tutor reply is not authority for the rule; the proposed correction relies on the current FAQ and dated clarification.
- 1 earlier review flag is still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "Story contains made-up phone number." (1790890012.001700); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is a clearly fake phone number still sensitive under the current policy?" (1790911772.000059); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: Story contains made-up phone number." (1790934673.000061)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-fictional-pii-clarification@1.0 (Preamble); safety-qn-help-page@1.0 (Contact details); safety-pii-clarification-post@1.0

## Format adherence vs factual accuracy

Needs Review - severity medium (assessed), unresolved

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**What to do: Post a reminder.** Post a reminder in the batch channel to score format adherence and factual accuracy separately and supply the exact prompt and both responses when the preference remains unsettled.

**Why.** The current FAQ answers the repeated scoring questions without declaring that accuracy or format always wins. Requesting complete pairs also follows the team lead's request in the tutor's thread and allows case-specific review.

**Draft to copy:**

> Reminder for this batch: score factual accuracy and instruction adherence separately, and check the exact prompt to establish whether the requested structure was mandatory.
> - Missing an explicit required format is a major instruction-adherence defect; assess factual errors independently.
> - Neither accuracy nor format automatically wins every comparison. Consider the actual pair and applicable guidance, not just how polished one response sounds.
> - If the preference remains unclear, provide the exact prompt and both responses for team lead confirmation. For the reported JSON-versus-prose case, please include the full pair before asking for a final choice.

**Still needs review:**
- The upstream review flag for the JSON-versus-prose thread remains open: a tutor's reply must not be treated as authoritative guidance. Review the exact prompt and both responses before confirming that pair's preference.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Open question: For RP-3824, which response should be preferred once the exact prompt, both responses, and the separate factual-accuracy and instruction-adherence defects have been reviewed?

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); response-preference-instructions@1.1 (Content-quality rubric); rp-tie-calibration-outcome@1.0 (TL assessment)

## Japanese speech-level shift evaluation

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and two tutors raise Japanese responses that shift from polite to casual language. Their threads do not settle whether the shifts are justified or what penalty, if any, applies.

**What to do: Ask a language specialist to review.** Collect the exact beginning and ending forms and surrounding dialogue for the three reported cases, then route them to Japanese language QA for case-specific scoring.

**Why.** Current guidance calls for language QA to assess context and demonstrated impact rather than treating a shift as an automatic major penalty. The thread replies request context but do not settle the scoring.

**Draft to copy:**

> Japanese QA: please assess the reported polite-to-casual shifts in this batch. A QA tutor asks how to score a sudden keigo change; a tutor reports an abrupt です/ます-to-plain shift in MULTI-2834; another tutor asks whether a casual closing warrants a penalty. Please obtain the exact beginning and ending forms and surrounding dialogue for each case, checking quotations, speaker changes and the addressee. Determine whether each shift is justified and explain any scoring impact. Current guidance does not support a major penalty from the shift alone. The supplied threads do not yet contain case-specific scoring decisions.

**Still needs review:**
- The reported shifts still need Japanese QA's case-specific assessment before any penalty is decided.
- 2 earlier review flags are still open on these threads.
- Open question: For each current case, does the complete dialogue justify the speech-level shift, and what demonstrated impact, if any, warrants a penalty?

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Could QA clarify this case: Keigo suddenly becomes casual — how to score?" (1790876285.000158); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790902834.000157); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Keigo is correct at the start, but the closing feels too casual." (1790939293.000156)

Sources: multilingual-eval-instructions@1.2 (Register and honorifics); multilingual-eval-faq@1.1 (Register and honorifics); multi-japanese-review-pending@1.0 (Case packet)

## Korean honorific level inconsistency QA

Needs Review - severity medium (assessed), unresolved

**What happened.** A QA tutor and two tutors report Korean responses switching from 존댓말 to 반말 and ask about earlier discussion, scoring or handling. Current guidance calls for Korean language QA review with exact endings and context, not an automatic major penalty.

**What to do: Ask a language specialist to review.** Route the reported Korean register cases to Korean language QA with exact sentence endings and surrounding context, and include the earlier ruling only as a scoped comparison.

**Why.** Current guidance requires context-based language QA review rather than an automatic major penalty. The earlier favorable ruling concerned a different quoted speaker and does not settle a reported same-addressee shift.

**Draft to copy:**

> Korean language QA: please review the reported 존댓말-to-반말 shifts, including MULTI-2012 and MULTI-1281. Please collect the exact Korean sentences and endings, the prompt and surrounding paragraph, and identify who is speaking and being addressed. A tutor reports that MULTI-1281 continues addressing the same person after the shift; this needs context-based assessment. Please check quotations, addressee changes, intended register and demonstrated impact before assigning a grade. The earlier batch-10 case received no register-consistency penalty because the casual sentence was a quotation from a different speaker; that ruling does not settle these cases.

**Still needs review:**
- The upstream review flag on the tutor's severity-question thread remains open: a tutor's reply was previously treated as authority. This draft treats that reply only as discussion and uses current instructions and the FAQ for guidance.
- 1 earlier review flag is still open on these threads.
- Open question: For the current reported cases, does Korean language QA find an unjustified register shift, and what task-quality grade is supported by its impact in context?

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Answer starts in 존댓말 then switches to 반말." (1790856672.000159); #multilingual-eval-general, 2026-10-01, started by a tutor: "Starts in 존댓말 and suddenly uses 반말." (1790882012.001500); #multilingual-eval-general, 2026-10-01, started by a tutor: "한 문단은 존댓말이고 다음 문단은 반말이에요." (1790897091.000160); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Issue: Answer starts in 존댓말 then switches to 반말." (1790931281.000162)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multilingual-eval-instructions@1.2 (Content-quality rubric); multi-korean-referral@1.0 (Request); multi-korean-scoped-result@1.0 (Specialist finding)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 30, blocked 0; input 375338, output 80701 tokens; charged $1.5577.

