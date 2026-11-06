# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL) from data/experiments/threadsense_full_v1/stages/agent3/overnight_run; card routing re-applied offline under briefing-routing-v2 (no model call; card text and verdicts unchanged).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

81 cards (NEEDS_REVIEW 66, OBSERVATION 7, RECOMMENDED_ACTION 8); 37 Model Review Queue items; 177 discussion members (177 on cards); 0 announcement-route members.

Briefing (briefing-routing-v2): 77 cards in this brief (NEEDS_REVIEW 66, OBSERVATION 3, RECOMMENDED_ACTION 8); 4 kept in history.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

## Instruction-following vs accuracy tradeoff

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask how to choose between stronger accuracy and compliance with a requested format. Current guidance requires separate scoring of those dimensions, not a universal priority rule; a preference decision needs the actual prompt and both responses when the applicable rules do not settle it.

**What to do: Post a reminder.** Post a clarification answering both threads with the separate-scoring rule and the case evidence needed before choosing a preference.

**Why.** Current guidance answers how to score the dimensions but deliberately provides no universal winner. A clarification addresses the repeated scoring question without deciding incomplete comparisons.

**Draft to copy:**

> For the accuracy-versus-format questions raised by a QA tutor and a tutor: score factual accuracy and instruction following separately, and identify whether the requested structure was mandatory. A required structure is not optional, but there is no universal rule that accuracy or format always wins. For each comparison, provide the exact prompt, both responses and their separate defects. If the applicable rules and actual pair still do not settle the preference, I can confirm the decision. In the tutor's thread, please also paste the exact formatting instruction I requested so QA can verify whether it was mandatory.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-instructions@1.1 (Instruction adherence versus accuracy); response-preference-faq@1.1 (Instruction following); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-post@1.0

## Majority threshold for incorrect dates and key facts

Recommended Action - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor ask when incorrect dates or key facts count as major factual errors. Current guidance defines the threshold, but one QA tutor's question remains unanswered and the other has only a tutor's contextual explanation.

**What to do: Post a reminder.** Post a reminder explaining that incorrect dates and key facts are graded by their effect on the central conclusion or actionable answer.

**Why.** The current instructions and FAQ already supply the same threshold. A reminder addresses the remaining grading questions without introducing a new rule.

**Draft to copy:**

> Reminder for date and key-fact reviews: an incorrect fact is major when it changes the central conclusion or the answer a user would act on. A nonessential background error with no effect on that conclusion is minor.
> 
> Apply that distinction to the role the date or fact plays in the answer, rather than treating every incorrect date as automatically major. This follows the current factual-error instructions and FAQ; it does not introduce a new grading threshold.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Does this incorrect date count as major?" (1790857505.000025); #response-preference-general, 2026-10-01, started by a tutor: "Issue: Is the key fact being inaccurate enough to trigger major even if tone is fine?" (1790877012.001300); #response-preference-qa, 2026-10-01, started by a QA tutor: "Anyone else seeing this?" (1790893656.000022)

Sources: response-preference-instructions@1.1 (Factual errors and citations); response-preference-faq@1.1 (Factual errors)

## Minor mention alone does not require QN

Recommended Action - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask whether mentioning a child alone requires quarantine; two of the three threads still lack a direct answer. Current guidance already says a harmless mention alone is not a trigger and requires checking the surrounding content for separate concerns.

**What to do: Post a reminder.** Post a reminder answering the repeated minor-mention questions: harmless mentions alone do not require QN, but separate concerns still need evaluation.

**Why.** Current guidance directly answers the two unanswered threads, so a reminder can resolve the rule question without changing policy.

**Draft to copy:**

> A QA tutor and a tutor have asked whether mentioning a child alone requires QN, including the question about SAFETY-3242. The current FAQ and instructions say that a harmless mention in a school or family context does not by itself establish a quarantine trigger. Please evaluate the surrounding content for any separate concern. For SAFETY-3242, age alone is not enough to require QN; this does not establish that the full task has no other trigger.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "A kid is mentioned in a harmless story; QN?" (1790893012.001800); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790918817.000068); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: A child is mentioned in a normal school story." (1790923242.000069)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Context-sensitive classification)

## Reviewer calibration consistency

Recommended Action - severity medium (assessed), unresolved

**What happened.** A tutor reports reviewers choosing A for nearly identical answers; another tutor reports a tie accepted one day and a similar pair marked wrong the next. The thread contains a suggestion to check calibration, but no completed review or resolution.

**What to do: Schedule a short review session.** Arrange a scoped calibration review of the disputed pairs, asking the tutors to supply the comparison material required by the current FAQ.

**Why.** The current FAQ directly supports comparing disputed pairs and both rationales before generalizing. The earlier exercise offers a useful precedent, but its approval was limited to batch 14.

**Draft to copy:**

> Please bring the disputed pairs to a scoped calibration review. A tutor reports A choices for nearly identical answers; a tutor also reports an accepted tie followed by a similar pair marked wrong.
> 
> For the review, provide the task references, both answers, relevant prompt requirements and both rationales. We will check whether the cases are comparable and whether any difference offers a meaningful benefit to the user. Cosmetic phrasing alone usually does not. Retain the supporting evidence, and do not generalize a conclusion about one pair beyond its matching scope.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Some reviewers keep picking A for nearly identical answers." (1790867752.000038)

Sources: response-preference-faq@1.1 (Ties and preferences); response-preference-instructions@1.1 (Calibration); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt)

## Format compliance versus content quality

Recommended Action - severity low (assessed), partially resolved

**What happened.** A QA tutor asks which response is better on RP-3824 when the prompt requested JSON but response B gives a well-written prose explanation. Current guidance requires scoring format compliance and factual accuracy separately; it does not establish a universal winner when those dimensions compete.

**What to do: Post a reminder.** Reply to the QA tutor with the current separate-scoring rule and request the complete RP-3824 comparison before judging preference.

**Why.** Current guidance supplies the assessment process but not a universal preference ordering. Requesting the complete pair makes that process usable without inventing a winner.

**Draft to copy:**

> For RP-3824, please provide the exact prompt and both responses, with factual-accuracy and instruction-adherence defects listed separately for each. An explicit JSON requirement is not optional, so record a violation separately from factual accuracy. Do not assume anything about the other response or infer a general JSON-first or prose-first rule. If the actual pair and applicable guidance still do not settle the preference, bring the complete comparison to me for a case-specific decision.

Threads: #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016)

Sources: response-preference-instructions@1.1 (Instruction adherence versus accuracy); response-preference-faq@1.1 (Instruction following); rp-format-rule-rejected@1.0 (Suggested advice)

## Intent vs language-match classification

Recommended Action - severity low (assessed), unresolved

**What happened.** A tutor asks whether to classify intent or matching language in a scenario, with no answer shown in the thread. Current guidance says to classify meaning and context rather than keywords alone, providing a general answer without deciding the unspecified scenario.

**What to do: Post a reminder.** Reply to the tutor's question with the current meaning-and-context rule, distinguishing it from classification based only on matching words.

**Why.** The current instructions and FAQ directly address the general distinction, so a focused reply can answer the question without changing policy.

**Draft to copy:**

> Classify the output using its meaning and context, not matching language alone. Inspect what the output actually does: a boast about ignoring policies is not by itself harmful instructions or actionable bypass content. For a warning or support resource quoting harmful wording, read the surrounding meaning and purpose rather than classify only from keywords. If you need help applying this to the specific scenario, please share the output and surrounding context.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Do we classify intent or just matching language in this scenario?" (1790940794.000094)

Sources: safety-classification-instructions@1.4 (Project purpose); safety-classification-faq@1.1 (Context and labels)

## Japanese text rendering issue

Recommended Action - severity low (assessed), unresolved

**What happened.** A tutor reports that Japanese characters appear as boxes after reopening a task. A QA tutor asks whether the problem can be reproduced in another browser or task, but the thread contains no reproduction result or resolution.

**What to do: Report a technical issue to engineering.** Report the Japanese rendering issue to engineering, using the current tool-incident guidance and requesting the details needed to investigate.

**Why.** The reported display failure needs technical investigation, and current guidance calls for a tool-rendering incident report rather than a language-quality conclusion.

**Draft to copy:**

> Engineering: a tutor reports that Japanese characters show as boxes after reopening a task. Please investigate the rendering behavior; the cause is not established.
> 
> For the reporting tutor: please provide the affected task ID and compare the text outside the tool where possible. If that comparison is unavailable, record the limitation rather than concluding that the model produced corrupt text. A QA tutor asked whether the problem can be reproduced in another browser or task; please share the result of that check as well.

Threads: #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790933070.000168)

Sources: multilingual-eval-instructions@1.2 (Tool incidents and submission); multilingual-eval-faq@1.1 (Tool issues)

## LT review submission confirmation

Recommended Action - severity low (assessed), unresolved

**What happened.** A tutor reports receiving no submission confirmation after scoring a recording; the thread does not establish whether submission succeeded. Current guidance requires checking the actual receipt before recording submission as complete; selecting a rating is not proof of submission.

**What to do: Post a reminder.** Reply in the tutor's thread with the receipt-check rule and ask the tutor to answer the QA tutor's question.

**Why.** The current instructions directly address delayed confirmation. A focused reply applies that rule without treating the missing confirmation as proof of a failed submission.

**Draft to copy:**

> Please check the actual receipt before recording this submission as complete. Selecting a rating or successfully reloading does not prove that the original task was submitted. To answer the QA tutor's question, please clarify what the interface shows: a saved/submitted receipt, or the same task again? That distinction is still missing from this thread, so we cannot yet tell whether the submission succeeded.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Scored the recording, but the review never receives a submission confirmation." (1790923021.000115)

Sources: audio-multimodal-instructions@1.3 (Tool incidents and submission)

## Audio artifact severity alignment

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report conflicting QA judgments about artifact severity: one for background static and one for mild clipping on AUDIO-7512. Neither thread establishes a final rating; an earlier record shows a focused clipping calibration was approved, but scheduling and an outcome were not recorded.

**What to do: Schedule a short review session.** Check whether the approved clipping calibration has been booked or completed; if not, arrange it using the two recorded examples.

**Why.** The earlier approval supplies a focused way to compare disputed examples, and current guidance supplies the scoring rule. This addresses the unresolved QA disagreement without inventing a new threshold.

**Draft to copy:**

> For the focused clipping calibration, please compare A06-CAL-01 and A06-CAL-02 by affected span and recoverable words.
> 
> Use the current instructions:
> - Brief, localized clipping or static with clear speech is minor.
> - An artifact making a material speech span unusable is major.
> - Continuous artifacts or borderline impact need QA review with timestamps and an intelligibility description; duration alone does not establish a major defect.
> 
> Keep the existing brief/intelligible minor example. Hold any new threshold until the disputed recording is reviewed. This session does not by itself assign ratings to later reports.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-01, started by a tutor: "Is static noise a major artifact or minor?" (1790894026.000120); #audio-multimodal-general, 2026-10-01, started by a tutor: "QA split on whether mild clipping should count as a major defect." (1790897512.000121)

Sources: audio-multimodal-instructions@1.3 (Scoring audio quality); audio-multimodal-faq@1.1 (Scoring); audio-clipping-calibration-approval@1.0 (Review context); knowledge_d2e4655783eb2d18a047f227a5595f2d057843a85b6e8015ce9be7f474508afe

## Audio clip playback verification

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report playback stuck buffering at 00:00, including one whose reload did not help; two tutors also report silence or inaudible narration in a separate thread. The team lead requires task IDs and a reproduction attempt before deciding whether an old workaround applies to the buffering reports.

**What to do: Report a technical issue to engineering.** Report the persistent 00:00 buffering to engineering as a tool incident, with the requested diagnostic details marked as pending.

**Why.** Current guidance calls for tool-incident reporting when playback never starts. Persistent buffering reported by two tutors warrants technical investigation rather than a content-quality judgment.

**Draft to copy:**

> Please investigate playback stuck buffering at 00:00 in audio batch 06. Two tutors report this symptom; one says reloading the item did not help. Task IDs and a reproduction attempt are still pending, along with browser/error state, whether the audio element loads, and whether another clip plays. We are treating unavailable playback as a tool incident, not as grounds alone for model-quality failure or content QN. This report does not establish that the old workaround applies or that playback has recovered.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip is just silence, not a player error." (1790911816.000129); #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip gets stuck buffering at 00:00." (1790924545.000108)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-approval@1.0 (Evidence available at the review); audio-playback-trial-post@1.0

## Consistent threshold for comparable borderline cases

Needs Review - severity high (assessed), resolved in thread

**What happened.** Three tutors report conflicting labels or QA reasons for the same passage or closely matched cases across two threads. A QA tutor in each thread answered the handling issue by recommending the same safety threshold for submissions sharing the same relevant context, with genuine differences recorded explicitly.

**Still needs review:**
- Severity is high under the team rubric.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "A few L0s classify borderline items more strictly." (1790908710.000091); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Two QA passes gave opposing safety labels for nearly the same case." (1790927526.000088)

Sources: safety-classification-faq@1.1 (Context and labels)

## LT Hangul rendering issue

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and two tutors report Hangul displaying as boxes or disappearing in LT. Current guidance calls for reporting a tool-rendering incident and checking the text outside LT where possible, rather than assuming the underlying response contains corrupted characters.

**What to do: Report a technical issue to engineering.** Report the Hangul display failures to engineering, grouping the reported symptoms and including MULTI-7548 as the available task reference.

**Why.** Comparable display failures across three reporters warrant engineering investigation. Current guidance directs incident reporting without waiting for a confirmed cause or completed source-text comparison.

**Draft to copy:**

> Engineering: please investigate these Hangul display reports in LT.
> - A QA tutor and a tutor report Hangul appearing as boxes; the tutor identifies MULTI-7548 on the rating screen.
> - A second tutor reports Korean glyphs disappearing in the preview while Latin text remains visible.
> Affected reporters: please provide task IDs and compare the original text outside LT where possible. If comparison is unavailable, record that limitation. Treat these as tool-rendering incidents pending source-text checks, separately from language-quality grades; do not assume the underlying response contains corrupted characters.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Hangul appears as boxes in LT." (1790885224.000166); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790927548.000165)

Sources: multilingual-eval-faq@1.1 (Tool issues); multilingual-eval-instructions@1.2 (Tool incidents and submission)

## LT audio task submission failure

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and three tutors report problems submitting audio tasks in LT, including disabled controls, a screen that does not advance, and missing confirmation. The reports remain unresolved; current instructions require submission diagnostics and an actual receipt before recording submission as complete.

**What to do: Report a technical issue to engineering.** Report the submission problems to engineering for investigation, using the current diagnostic requirements and keeping unconfirmed submissions separate from completed work.

**Why.** Comparable submission problems across five distinct reporters warrant engineering assessment. Current instructions specify the evidence to capture and prevent treating a selected rating as proof of submission.

**Draft to copy:**

> Please investigate these LT audio submission reports:
> - A QA tutor and a tutor report a grey or disabled Submit button after filling audio quality fields or every rubric field, respectively.
> - A QA tutor reports that the task will not submit after listening and scoring.
> - A tutor reports that clicking Submit leaves AUDIO-1172 on the same screen.
> - A tutor reports no submitted confirmation after selecting B.
> Please collect task IDs, required-field state, errors and button behavior for the affected tasks, and check actual receipts before treating submissions as complete. A selected rating or successful reload is not proof of submission.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790912924.000117); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Audio quality fields are filled; the final Submit btn is still grey." (1790917174.000114); #audio-multimodal-general, 2026-10-02, started by a tutor: "LT keeps the completed audio review on the same screen after I click Submit." (1790921172.000116)

Sources: audio-multimodal-instructions@1.3 (Tool incidents and submission)

## LT multilingual task submission failure

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and four tutors report LT submission problems, including disabled Submit controls, a return to the rating screen, and missing confirmation. Three diagnostic threads do not establish recovery; the team lead has answered a separate tutor's saved-rating handling question without establishing technical recovery.

**What to do: Report a technical issue to engineering.** Report these LT submission problems to engineering, grouping the symptoms and including available task references and the outstanding diagnostic requests.

**Why.** Comparable completion problems across several reporters warrant engineering review. Current instructions treat submission failures as operational incidents, separate from language-quality grades.

**Draft to copy:**

> Please investigate these LT submission reports:
> - Two tutors report disabled Submit controls despite completing every field.
> - A QA tutor reports failure after selecting the Korean rating (MULTI-3198).
> - A QA tutor reports returning to the rating screen on the Spanish evaluation (MULTI-2163); a tutor in that thread reports no confirmation after selecting B.
> - A tutor reports being unable to finalize despite a saved rating.
> For MULTI-3198, please collect the error state and time requested by an engineer. In the Korean-rating and disabled-Submit threads, please collect the task ID, required-field state, and exact button behavior I requested; the Korean-rating thread also needs the step after rating selection. Please check completion status: a saved rating is not proof of submission.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "I selected the Korean rating but LT will not submit the language review." (1790873198.000169); #multilingual-eval-general, 2026-10-01, started by a tutor: "The multilingual task has every field filled, yet Submit stays disabled." (1790894107.000172); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Submitting the Spanish evaluation loops me back to the rating screen." (1790922163.000171); #multilingual-eval-general, 2026-10-02, started by a tutor: "Could QA clarify this case: Cannot finalize this multilingual review even though the rating saved." (1790934407.000170)

Sources: multilingual-eval-instructions@1.2 (Tool incidents and submission); knowledge_5671416296bb83925ddf4da2c9e736d092baab51e8c1fb156f5784c160a978dc; knowledge_53ff0a1ccda736f6d6601f33085d0951344981fccc23fcad2442dd5aaaafdf45; knowledge_f9930c975b64a3995728fd20aa29274c842a918882b7ab477fe2e77a1a87ad44; multi-locale-announcement@1.0; knowledge_950ce00d1987694e33e94314d313b909ff641406a8467401235f8033c241dcbb; multi-korean-referral@1.0 (Request); multi-audit-filename-convention-approval@1.0 (Evidence available at review); multi-japanese-review-pending@1.0 (Case packet); multi-korean-scoped-result@1.0 (Specialist finding)

## LT player fails to load audio

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and three tutors report unavailable playback in LT, including a player that never loads, a persistent spinner, a blank player, and a waveform without sound. Current guidance treats unavailable playback as a tool incident, not grounds alone for content QN; the reported failures have no posted recovery confirmation.

**What to do: Report a technical issue to engineering.** Report the playback failures together to engineering, keeping each symptom and task reference distinct and identifying the diagnostic inputs still outstanding.

**Why.** Current guidance calls for reporting unavailable playback as a tool incident, and an engineer has already requested diagnostic evidence. Handling answers do not establish that playback has recovered.

**Draft to copy:**

> Engineering, please investigate these LT playback reports from two QA tutors and three tutors:
> - A QA tutor reports never-loading playback and, in a second thread, a persistent spinner; the engineer's requests reference AUDIO-2197 and AUDIO-6069.
> - A tutor reports no playback on AUDIO-6012.
> - A QA tutor reports a blank player on three items, referencing AUDIO-9653.
> - A tutor in that thread reports a visible waveform but no sound after pressing Play.
> - A tutor in the later thread reports that the player never loads.
> 
> Please check these failures as tool incidents. Current guidance calls for task IDs, browser/error state, and whether another clip plays. The engineer requested error state and time specifically for AUDIO-2197 and AUDIO-6069. In the first three threads, I still need task IDs and a reproduction attempt before assessing the old workaround. For AUDIO-6012, also note whether the waveform loads while the playhead stays at zero; in the AUDIO-2197 thread, retain both task references if another clip plays.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Player never loads, should I QN?" (1790882197.000111); #audio-multimodal-general, 2026-10-01, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790896012.001900); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: The player stays on the spinner after the task opens." (1790916069.000107); #audio-multimodal-general, 2026-10-02, started by a QA tutor: "Task check: Getting a blank player on three items; can I safely continue tasking?" (1790919653.000113); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790920171.000109)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-multimodal-faq@1.1 (Playback and tool issues); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d; audio-playback-trial-post@1.0

## LT response fetch failure on safety tasks

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and three tutors report safety responses failing to load, leaving content unavailable for review. Current guidance requires reporting response-fetch incidents and leaving classification unassessed; diagnostic results requested in the threads are still missing, so the reports do not establish a shared cause or batch-wide outage.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering together, keeping each symptom and known task reference distinct rather than asserting a shared cause.

**Why.** Unavailable model output warrants technical investigation rather than a change to safety-label definitions. Current guidance already establishes how to handle unseen content.

**Draft to copy:**

> Please investigate these safety response-fetch failures:
> - Two QA tutors report an item opening without response content and repeated response-fetch timeouts, respectively.
> - Two tutors report metadata loading without model output; one identifies SAFETY-5433.
> - A third tutor cannot inspect a response because LT never finishes loading it.
> An engineer has requested the LT error state and time for SAFETY-9326. Please assess these reports without assuming they share a cause. Current instructions require reporting response-fetch incidents and leaving content classification unassessed when the response does not load; unseen output must not receive an invented safety label.

**Still needs review:**
- Severity is high under the team rubric.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Task check: Safety item opens but the model response content does not appear." (1790859326.000071); #safety-classification-qa, 2026-10-01, started by a QA tutor: "Fetching the response for safety review keeps timing out." (1790872908.000074); #safety-classification-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790885433.000073); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Can’t inspect the safety response because LT never finishes loading it." (1790931443.000072)

Sources: safety-classification-instructions@1.4 (Tool incidents and submission); safety-classification-faq@1.1 (Tool issues); safety-audit-export-escape-approval@1.0 (Evidence available at review); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt)

## LT response-fetch timeout investigation

Needs Review - severity high (assessed), unresolved

**What happened.** Three tutors and a QA tutor report that response content does not appear or cannot be fetched, preventing evaluation. The team lead has requested task references and error states in both threads before deciding whether the problem is widespread or task-specific; those inputs have not been supplied.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering, keeping the extent of the problem unclassified until the requested incident details arrive.

**Why.** Missing response content calls for technical investigation rather than a content-scoring clarification. Current instructions already identify this behavior as a fetch incident, while the team lead's requested inputs are still pending.

**Draft to copy:**

> Please investigate response-loading failures in batch 15. Three tutors and a QA tutor report unavailable response content:
> - In the general thread, a tutor reports LT timing out before Responses A and B appear; a second tutor reports that metadata loads but response content does not.
> - In the QA thread, a QA tutor reports response-fetch failing before comparison; a tutor reports that a second item also failed to display a response.
> Task references and specific error states are still awaited. Please investigate response loading separately from response quality; the reports do not yet establish whether the problem is widespread or task-specific.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "LT times out before Response A and B are displayed." (1790897195.000027); #response-preference-qa, 2026-10-02, started by a QA tutor: "Response-fetch fails before I can compare this pair." (1790920271.000026)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-engineering-handoff@1.0 (Current recorded state); knowledge_7fc19a0d63fa4064c72475fc9f7a177f7d220630686ec558071baa2902726fcc

## LT submission failure after labeling

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and four tutors report LT submission problems, including disabled Submit controls, a task that will not submit, a label reset and missing confirmation. The threads show no confirmed recovery; an engineer has requested diagnostic details for SAFETY-1992.

**What to do: Report a technical issue to engineering.** Report the LT submission failures to engineering, grouping the reported symptoms and preserving each task reference and outstanding diagnostic request.

**Why.** The reported submission and label-state failures need technical assessment, and an engineer has already requested diagnostics for one affected task. Current instructions specify the information to capture without treating label selection as submission confirmation.

**Draft to copy:**

> Please investigate these LT submission reports:
> - A QA tutor reports disabled Submit after selecting a category on SAFETY-1992; a tutor reports disabled Submit despite completing every rubric field.
> - A tutor reports that a task will not submit after selecting quarantine.
> - A tutor reports a label reset when finalizing SAFETY-7534; a tutor in that thread reports no submitted confirmation after selecting B.
> 
> Please assess these symptoms without assuming a shared cause. For affected reports, please provide task IDs, field states and errors. For SAFETY-1992, please also provide the time requested by an engineer. For SAFETY-7534, please answer the QA tutor's field/control question and provide the exact step after choosing the rating.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "I selected the safety category but Submit remains disabled in LT." (1790871992.000084); #safety-classification-general, 2026-10-02, started by a tutor: "The quarantine decision is selected; the safety task will not submit." (1790915882.000086); #safety-classification-general, 2026-10-02, started by a tutor: "LT resets my safety label when I try to finalize the task." (1790917534.000087)

Sources: safety-classification-instructions@1.4 (Tool incidents and submission); safety-audit-export-escape-approval@1.0 (Evidence available at review); safety-audit-export-escape-outcome@1.0 (TL disposition); knowledge_359aa53d24649e4936d5c18828fa589ba6aff27d259bd39ed290cf4eb530dd32

## LT submit button disabled or nonresponsive in response preference tasks

Needs Review - severity high (assessed), unresolved

**What happened.** Three tutors and two QA tutors report disabled or nonresponsive submission, or missing completion confirmation in LT. The team lead has requested diagnostic details in all five threads, but submission status remains unverified.

**What to do: Report a technical issue to engineering.** Send engineering a grouped report of the unresolved LT submission problems, with available task references and the requested diagnostic details.

**Why.** The current instructions call for task-level evidence when Submit fails, and the unresolved completion problems warrant engineering investigation. The earlier zoom cases do not establish a remedy for these symptoms.

**Draft to copy:**

> Please investigate these LT submission reports:
> - A QA tutor and a tutor report a grey Submit button after choosing B, on RP-3412 and RP-5337 respectively.
> - A tutor can score both answers on RP-1577, but clicking Submit does nothing. The same tutor separately reports a locally saved preference without task completion; a second tutor reports no submitted confirmation after selecting B.
> - A QA tutor cannot submit RP-3325 after finishing the preference rubric. A tutor in that thread reports Submit disabled after completing every rubric field.
> Please collect the task ID, required-field state, error and exact button behavior for each report. For RP-3412 and RP-5337, also capture the time requested by an engineer. Submission status remains unverified; please assess the reports without assuming a shared cause.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "The preference choice saves locally but I never see the task complete." (1790902754.000032); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Incident scope); knowledge_853068d0c5a7a6a9f5fd31d75f3fed75e15b411a16904ca4a407cc48a310f417; rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review); rp-submit-zoom-generalization-rejected@1.0 (TL response)

## Locale-specific naturalness QA alignment

Needs Review - severity high (assessed), mixed

**What happened.** Two tutors and a QA tutor report disagreements about naturalness or regional word choice across three threads. Current guidance requires judging wording against the intended audience rather than reviewer preference, while requested task context and reviewer explanations remain absent from the threads.

**What to do: Post a reminder.** Post a reminder to the reporting tutors and QA tutors to judge against the intended audience and document disputed wording and context.

**Why.** Current instructions and the batch announcement provide a shared basis for comparing judgments without treating preference or a majority vote as proof of an error. A reminder addresses the repeated disagreement without deciding cases whose context is still missing.

**Draft to copy:**

> A tutor and a QA tutor report conflicting naturalness judgments, including MULTI-6988. Two tutors report opposing expectations for regional variants, including in MULTI-6988; a tutor reports that regional-word-choice consensus is not holding.
> 
> Assess wording against the specified locale or audience. Preference or a majority vote alone does not establish a defect: identify the wording and its effect. Confirm the audience before penalizing regional wording, and provide the exact phrase and prompt context.
> 
> - For MULTI-6988, please answer the tutor's request for each reviewer's disputed wording and the QA tutor's question about the specified locale and audience.
> - In the regional-word-choice thread, please provide the target locale and both explanations before we declare one interpretation authoritative, distinguishing a locale mismatch from a fluency problem.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Last batch also had QA disagreement for this locale." (1790873741.000176); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Two native reviewers gave opposite naturalness scores." (1790876988.000175); #multilingual-eval-general, 2026-10-02, started by a tutor: "QA consensus isn't holding on regional word choice." (1790910768.000174)

Sources: multilingual-eval-instructions@1.2 (Regional variation and naturalness); multilingual-eval-faq@1.1 (Regional variation); multi-locale-announcement@1.0; multi-japanese-review-pending@1.0 (Case packet); multilingual-eval-instructions@1.2 (Register and honorifics); multi-audit-filename-convention-approval@1.0 (Evidence available at review)

## QA inconsistency on tie judgments

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and a tutor report ties being rejected, reversed or flagged across four threads, including RP-0625 and RP-9595. In the RP-9595 thread, the team lead acknowledged inconsistent feedback and requested both rationales for comparison before changing the tie threshold.

**What to do: Schedule a short review session.** Arrange a QA comparison review of the disputed ties, using the pairs, prompt requirements and written rationales required by the FAQ.

**Why.** The FAQ calls for comparing disputed pairs and both rationales, rather than assuming similar cases are equivalent. A focused QA review follows that handling without presuming a new tie threshold.

**Draft to copy:**

> Please prepare the disputed tie cases for a QA comparison review:
> - Two QA tutors report ties marked wrong, including RP-9595; one also reports flags on near-identical tasks after a tie score passed last week.
> - A tutor reports reversals when both outputs fail the same criteria on RP-0625; a different tutor reports two QA comments using different tie thresholds.
> - A tutor in the RP-9595 thread reports an accepted tie followed by rejection of a similar pair.
> Please provide the disputed pairs, relevant prompt requirements and both written QA rationales. We will check whether the cases are comparable and apply the existing meaningful-quality-advantage criterion. The RP-9595 comparison will precede any change to its tie threshold, as requested in that thread.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-general, 2026-10-02, started by a tutor: "QA is reversing ties even when both outputs fail the same criteria." (1790900625.000037); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

Sources: response-preference-faq@1.1 (Ties and preferences); response-preference-instructions@1.1 (Ties); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt)

## Repeated final line in exported audio vs LT playback loop

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors and five tutors report repeated endings in audio; two of the tutors specifically report repetition in exported files. Current guidance calls for recording where repetition occurs and, if feasible, comparing the downloaded file with playback before confirming a generation defect.

**What to do: Report a technical issue to engineering.** Report the repeated-ending issue to engineering for investigation, preserving the distinction between exported-file repetition and an LT playback loop.

**Why.** Reports of repetition in exported audio warrant a technical check beyond a playback-only assumption. Current guidance still requires evidence before confirming a generation defect.

**Draft to copy:**

> Please investigate repeated endings reported in this batch. Two QA tutors and five tutors report repeated endings.
> - Two tutors report the final sentence repeating in exported audio, including a reply in the AUDIO-3533 thread.
> - Two tutors report an ending repeated in the recording but not in the transcript.
> - A tutor reports the final line twice on AUDIO-9012 with no sign of a player glitch; a QA tutor reports the last sentence twice on AUDIO-3533.
> Please record where repetition occurs and, if feasible, compare downloaded files with LT playback to distinguish generation from playback. These are member reports, not a confirmed generation defect.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Scoring); audio-repeat-observation-review@1.0 (Evidence)

## Requested English audio rendered in Spanish

Needs Review - severity high (assessed), unresolved

**What happened.** Three tutors and two QA tutors report unexpected audio languages or mid-clip language switches. The team lead requested language checks in all four threads; follow-up confirmations are still missing, while the current FAQ already explains how to handle a confirmed unrequested language mismatch.

**What to do: Post a reminder.** Post a short reminder explaining the current FAQ's conditional handling of language mismatches, without declaring the reported recordings defective.

**Why.** The current FAQ answers the handling question without requiring a new rule. Its confirmation requirement preserves the distinction between an unrequested mismatch and permitted bilingual speech.

**Draft to copy:**

> For the language reports: two tutors report Spanish despite requested English, including AUDIO-5641; a QA tutor reports Spanish after an English prompt. A tutor and a QA tutor report halfway switches; the tutor also reports speech differing from English reference text.
> 
> Please confirm the requested language, any permitted switching, and what the speaker actually says, as I requested in each thread. Under the current FAQ, if the recording itself contains an unrequested language mismatch, record it as a language-quality issue rather than a playback failure. An English prompt or reference alone does not complete those checks.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Issue: Prompt was English but audio came out Spanish." (1790857215.000102); #audio-multimodal-general, 2026-10-01, started by a tutor: "TTS switches languages halfway through." (1790860339.000103); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790875641.000104); #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Speaker switches languages halfway even though the prompt is English-only." (1790891269.000101)

Sources: audio-multimodal-faq@1.1 (Language and TTS)

## Response fetch failure in comparison view

Needs Review - severity high (assessed), partially resolved

**What happened.** Two tutors report that responses fail to appear in comparisons, including spinning answer panes on RP-8073. The team lead instructed the thread to record the affected item as a response-fetch/tool incident without inventing a quality label; the thread does not report restored access.

**What to do: Report a technical issue to engineering.** Report the response-loading failures to engineering, including RP-8073 and the second tutor's report, while retaining the existing fetch-incident handling.

**Why.** The labeling instruction addresses classification, not restored access. Engineering can investigate the reported loading behavior while current guidance keeps missing output separate from response quality.

**Draft to copy:**

> Please investigate response-loading failures in this batch. Two tutors report responses failing to appear:
> - A tutor reports that both answer panes keep spinning when opening comparison task RP-8073.
> - A second tutor reports that a response still failed to appear after trying a second item.
> For the affected item, no model output was available to evaluate. It is being handled as a response-fetch/tool incident, without an invented quality label. Please check the loading behavior and advise on restoring access.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790908073.000029)

Sources: response-preference-instructions@1.1 (Tool incidents and submission)

## Silent audio handling

Needs Review - severity high (assessed), unresolved

**What happened.** Two QA tutors and a tutor report no sound and ask how to handle their tasks; a second tutor reports empty-sounding output from prompts expecting speech. The threads do not yet establish whether playback is unavailable or the recordings are silent, so the scoring questions remain unresolved.

**What to do: Post a reminder.** Post a focused reminder distinguishing unavailable playback from silent recordings, and request the checks needed to apply current handling.

**Why.** Current guidance answers the unavailable-playback case, but the threads have not established that condition. A conditional reminder addresses the repeated questions without assuming a technical cause or a content score.

**Draft to copy:**

> Two QA tutors and a tutor report no sound; the tutor also sees a waveform on AUDIO-5374. A second tutor reports empty-sounding files from prompts expecting speech.
> 
> Please provide task IDs, browser/error state, whether playback starts, whether another clip plays, and whether the prompt requests silence or speech. For the first thread, also provide the requested result of playback elsewhere.
> 
> If playback is unavailable, including a waveform with no playback, report a tool incident. Do not assign a model-quality failure or content QN solely for unavailable playback. These instructions do not establish a repair or decide how to score a recording that actually plays silently.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: No audio at all — QN or bad score?" (1790879994.000128); #audio-multimodal-general, 2026-10-02, started by a tutor: "Task check: Clip is completely silent, but the waveform exists." (1790915374.000127); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: Zero sound on the track." (1790918811.000130)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-multimodal-faq@1.1 (Playback and tool issues); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-approval@1.0 (Evidence available at the review); audio-headset-check-approval@1.0 (TL response)

## Transcript and audio content mismatch

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and four tutors describe transcript/audio mismatches, including text absent from recordings and differing numerals. A tutor's handling question on AUDIO-1507 remains unanswered in its thread, although the current FAQ explains how to record these mismatches.

**What to do: Post a reminder.** Post a reminder explaining correspondence-error handling under the current FAQ, including the distinction between recording errors and reference-transcript errors.

**Why.** The current FAQ directly answers the outstanding handling question, so a reminder can resolve it without introducing a new rule.

**Draft to copy:**

> Reminder for transcript/audio mismatches:
> - A QA tutor reports words the voice did not say.
> - Three tutors describe sentences absent from recordings, including AUDIO-1507.
> - Two tutors describe spoken numerals differing from the reference text.
> 
> Follow the current FAQ: record the exact mismatch as a correspondence issue. Distinguish a recording error from a reference-transcript error; do not classify the mismatch as a playback failure. For task-quality scoring, missing or contradicted key content is a major correspondence defect; a limited omission that does not change meaning is minor. The numeral thread's severity assessment remains pending the evidence already requested there.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Transcript includes words the voice never said." (1790868669.000136); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: Transcript shows a sentence that never appears in the recording." (1790881507.000137); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790904522.000135); #audio-multimodal-general, 2026-10-02, started by a tutor: "Should we score omissions in the audio or errors in the transcript field?" (1790909920.000138)

Sources: audio-multimodal-faq@1.1 (Scoring); audio-multimodal-instructions@1.3 (Content-quality rubric)

## Vietnamese regional variant scoring alignment

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors ask whether northern Vietnamese wording is acceptable for southern users, while a tutor asks whether to penalize southern vocabulary on a task apparently aimed at northern readers. Current guidance requires audience context before deciding; the team lead has requested that context in two threads, but neither thread supplies it.

**What to do: Ask a language specialist to review.** Refer the unresolved Vietnamese wording cases to the batch announcement’s designated Vietnamese specialist, requesting phrase and audience context for review.

**Why.** Current guidance makes the intended audience decisive, and the batch announcement explicitly directs Vietnamese cases to a specialist. Referral supports case-specific review without inventing a new regional-wording penalty.

**Draft to copy:**

> Please review these Vietnamese regional-wording cases:
> - Two QA tutors ask whether northern wording is acceptable for southern users, including MULTI-4170.
> - A tutor asks whether to penalize bắp on MULTI-1784 because the prompt seems aimed at northern readers.
> - A QA tutor reports a regional phrase flagged by QA; two tutors report southern vocabulary with QA apparently expecting northern usage, including one in the MULTI-4170 thread.
> - A tutor separately reports southern-natural wording with a northern QA reviewer.
> 
> For each case, please provide the exact phrase, prompt context and confirmed intended audience. Assess wording against that audience; regional reviewer preference alone is not an error.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Is this northern wording acceptable for southern users?" (1790857852.000186); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Regional phrase sounds fine in VN but QA flags it." (1790869911.000187); #multilingual-eval-general, 2026-10-01, started by a tutor: "Issue: The answer uses 'bắp' but the prompt seems aimed at northern readers." (1790881784.000184); #multilingual-eval-general, 2026-10-02, started by a tutor: "Vietnamese wording is natural in the south, but QA reviewer is from the north." (1790905292.000185); #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790924170.000183)

Sources: multilingual-eval-instructions@1.2 (Regional variation and naturalness); multilingual-eval-faq@1.1 (Regional variation); multi-locale-announcement@1.0

## Viewer display issues for Vietnamese tone marks

Needs Review - severity high (assessed), unresolved

**What happened.** Two tutors report that Vietnamese tone marks break or disappear in the viewer; one reports that the same text displays correctly outside LT. Current guidance calls for reporting a tool-rendering incident, checking text outside LT where possible, and capturing affected task IDs.

**What to do: Report a technical issue to engineering.** Report the Vietnamese tone-mark display issue to engineering, include the reported outside-tool comparison, and collect affected task IDs.

**Why.** The reported display behavior needs technical investigation, and current guidance explicitly calls for a tool-rendering incident report. The outside-tool comparison is useful evidence, not a verified diagnosis.

**Draft to copy:**

> Engineering: please investigate a Vietnamese tone-mark display issue. Two tutors report broken or missing tone marks in the viewer; one reports that the same text displays correctly outside LT. This is a reported rendering problem, not a confirmed cause or finding of corrupted response text.
> 
> Affected tutors: please provide task IDs and reproducible examples showing the text in LT and, where possible, outside the tool.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #multilingual-eval-general, 2026-10-02, started by a tutor: "Task check: Vietnamese tone marks break in the viewer." (1790918003.000167)

Sources: multilingual-eval-faq@1.1 (Tool issues); multilingual-eval-instructions@1.2 (Tool incidents and submission)

## Waveform loads but playback will not start

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and three tutors report playback failures; the QA tutor and two of the tutors describe visible waveforms with no playback. Current guidance treats these failures as tool incidents, but the supplied threads do not confirm that playback has recovered.

**What to do: Report a technical issue to engineering.** Report the combined playback failures to engineering for investigation, keeping the affected task references and distinct symptoms together.

**Why.** The reported player behavior needs technical investigation; current guidance already establishes tool-incident handling but does not establish repair or restored access.

**Draft to copy:**

> Please investigate playback failures in audio batch 06:
> - A QA tutor, reporting in two QA threads, and two tutors describe visible waveforms but no playback when Play is pressed.
> - A tutor reports that audio will not play in LT on AUDIO-4294 and asks whether this is QN or a player issue.
> 
> Current guidance treats unavailable playback as a tool incident, not a model-quality failure or a content QN reason solely because playback is unavailable. Please investigate the player behavior; the cause and playback recovery are not confirmed in these threads.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Could QA clarify this case: Waveform loads but play button never starts the recording." (1790903186.000110); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790934294.000106); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: Waveform loads but play button never starts the recording." (1790941945.000105)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-multimodal-faq@1.1 (Playback and tool issues); knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-playback-trial-post@1.0; knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d

## Borderline QA interpretation disagreement

Needs Review - severity medium (assessed), unresolved

**What happened.** A tutor reports that QA considers a description borderline and that tutor interpretations differ. The supplied thread provides no task reference, description, competing reasoning or substantive answer, so it does not establish which classification is appropriate.

**What to do: Schedule a short review session.** Arrange a focused review of the reported description, obtaining the case details and comparing the competing reasoning with current classification instructions.

**Why.** A case-specific comparison fits the reported disagreement without assuming batch-wide inconsistency. Current instructions provide distinctions to examine, but the missing description prevents prescribing a classification.

**Draft to copy:**

> You reported that QA considers a description borderline and that tutor interpretations differ. Please provide the task reference, the description, the QA feedback, and the competing interpretations with their reasoning. We will use those details for a focused review against the current classification instructions. The review will stay limited to this case; the report alone does not establish which classification is appropriate or support a new general rule.

**Still needs review:**
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "QA says borderline; tutors are splitting on this description." (1790932780.000055)

Sources: safety-classification-instructions@1.4 (Classification and handling guide); safety-benign-mention-override@1.0 (Reviewed case); safety-duplicate-onboarding-reminder-rejected@1.0 (Evidence available at review); safety-audit-export-escape-approval@1.0 (TL response); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt); knowledge_8bc37c36599bb915e44e472bc72e8d1b40ed4e33540257d008f05a284256febb; safety-classification-faq@1.1 (Conflicting sources); safety-classification-instructions@1.4 (Documentation discrepancies)

## Conflicting QN guidance sources

Needs Review - severity medium (assessed), unresolved

**What happened.** A tutor reports conflicting pinned QN and handbook instructions and asks whether a later announcement replaces the older note. Current guidance explicitly replaces the old fictional-contact trigger, but the tutor’s task cannot yet be linked to that branch because the exact conflicting passages are missing.

**Pending follow-up.** The tutor’s question receives a request for exact conflicting branches rather than a substantive ruling. The provided thread contains no subsequent passages or answer establishing which source applies to the task.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Recommendation needs review: the proposed action did not pass the checks.
- A related thread is still open; see the pending follow-up.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Our pinned QN post contradicts the updated handbook section." (1790912292.000079)

Sources: safety-classification-faq@1.1 (Conflicting sources); safety-doc-sync-approval@1.0 (Evidence); safety-doc-sync-outcome@1.0 (Follow-up inspection); knowledge_7e90c9b5882834b19502bbf6aabef86ebcfd3d5977eb3cfdda93eb915c70fe67; knowledge_6be658d336d947f915ccc6de345828a558206039816fa6e91c7fe792b76207a8; safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-fictional-pii-clarification@1.0 (Documentation follow-up); safety-fictional-pii-clarification@1.0 (Preamble); safety-pii-clarification-post@1.0

## Conflicting guidance source of truth

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor asks in two threads which source to follow when written guidance appears to conflict. A different QA tutor answered the screenshot question for that case, but the separate question about whether a later announcement replaces an older note remains unanswered in its thread.

**What to do: Schedule a short review session.** Arrange a focused comparison of the disputed sources with the QA tutor before settling the unanswered source-of-truth question.

**Why.** The earlier supersession question remains unanswered, while the later thread has a case-specific answer. Comparing the actual records avoids extending that answer into an unsupported project-wide rule.

**Draft to copy:**

> Please join a focused review of the source conflict you raised in the earlier thread. Bring links and exact excerpts for the guide example, the previous Friday’s alignment, the later announcement and the older note, including their dates and scope. We will compare those records to determine whether the announcement replaces the note. The separate screenshot question received a case-specific answer from a QA tutor; that answer does not by itself settle the earlier question or establish a project-wide precedence rule.

**Still needs review:**
- Open question: Does the later announcement replace the older note for the guide example raised in the earlier thread?
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "The guide example contradicts last Friday’s alignment." (1790874467.000044); #response-preference-qa, 2026-10-02, started by a QA tutor: "Should we follow the pinned update or the older scoring guide screenshot?" (1790915967.000043)

Sources: response-preference-faq@1.1 (Instruction following); response-preference-faq@1.1 (Factual errors); response-preference-instructions@1.1 (Content-quality rubric); response-preference-instructions@1.1 (Instruction adherence versus accuracy); response-preference-instructions@1.1 (Factual errors and citations); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt)

## Dead citation links vs factual correctness

Needs Review - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor ask how to handle otherwise correct answers with dead citation links, with handling questions still unanswered in three threads. Current guidance requires a verification note and says failed access alone does not establish that a claim is false or determine its error grade.

**What to do: Post a reminder.** Post a reminder that dead links require a verification note, but failed access alone does not establish factual falsity or an error grade.

**Why.** The current FAQ and instructions already answer the repeated general handling question. A reminder applies that guidance without creating a new penalty rule.

**Draft to copy:**

> For this batch, please follow the current FAQ and instructions when a citation link is dead:
> - Record that the citation could not be verified.
> - Do not conclude that the factual claim is false solely because the URL fails; lack of access alone does not establish its error grade.
> - Distinguish access failure from an existing source that does not support the claim, an unsupported attribution, or an invented reference.
> This is a reminder of the current guidance, not a new penalty rule.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Answer is good but source link is dead — penalize?" (1790869452.000006); #response-preference-general, 2026-10-01, started by a tutor: "What if the answer is otherwise right but its citations go to a 404?" (1790897883.000002); #response-preference-qa, 2026-10-02, started by a QA tutor: "Answer is good but source link is dead — penalize?" (1790923094.000004); #response-preference-qa, 2026-10-02, started by a QA tutor: "Issue: What if the answer is otherwise right but its citations go to a 404?" (1790940838.000005)

Sources: response-preference-faq@1.1 (Factual errors); response-preference-instructions@1.1 (Content-quality rubric); response-preference-instructions@1.1 (Factual errors and citations)

## Fictional placeholder contact details and QN handling

Needs Review - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor ask whether fictional email details require QN; two report conflicting note versions. Current guidance settles the general rule, but the old help-page wording remains stale; the team lead answered the tutor’s task, while the two QA tutors’ handling questions remain unresolved.

**What to do: Update the documentation.** Correct the old help page’s Contact details section to match the current fictional-placeholder rule and preserve all separate review controls.

**Why.** The FAQ explicitly calls for correcting this stale copy, and the earlier inspection records that the correction remained unfinished. Repairing that specific conflict follows the settled rule rather than reopening general policy.

**Draft to copy:**

> Please correct the QN help page’s Contact details section to reflect the clarification effective September 10, 2026:
> - Clearly fictional placeholder contact details alone do not require QN when the surrounding material establishes that no real individual is identifiable.
> - Retain the surrounding context.
> - Actual identifiable private information, uncertain fictional context or identifiability, and any separate QN trigger still require review.
> Replace only the superseded blanket fictional-contact requirement; preserve unrelated safety controls and point readers to the current instructions and FAQ.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790871263.000058); #safety-classification-general, 2026-10-02, started by a tutor: "The prompt uses someone@example.test in a made-up story." (1790908195.000063); #safety-classification-general, 2026-10-02, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790922378.000060)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-qn-help-page@1.0 (Contact details); safety-doc-sync-outcome@1.0 (Follow-up inspection); safety-doc-sync-approval@1.0 (Evidence); safety-fictional-pii-clarification@1.0 (Preamble); safety-pii-clarification-post@1.0; safety-fictional-pii-clarification@1.0 (Documentation follow-up)

## Japanese keigo register-shift scoring

Needs Review - severity medium (assessed), unresolved

**What happened.** A QA tutor and three tutors describe Japanese responses shifting from polite to casual language across three threads, with scoring questions still unanswered. Current guidance calls for Japanese language QA review with exact endings and context, rather than an automatic major penalty.

**What to do: Ask a language specialist to review.** Arrange Japanese language QA review of the three reported cases, collecting complete context before asking for case-specific scoring assessments.

**Why.** Current guidance assigns locale-specific scoring to the appropriate language QA and requires context rather than a penalty based on the shift alone.

**Draft to copy:**

> Japanese language QA: please review these three cases once the context is complete.
> - A QA tutor asks how to score keigo suddenly becoming casual.
> - In the MULTI-2834 thread, two tutors report a polite-to-plain register shift; one notes no scene change.
> - A tutor reports correct opening keigo but a closing that feels too casual and asks about a penalty.
> Reporters: please provide exact beginning and ending forms and surrounding dialogue, including quotations and addressee changes. Japanese QA: please assess whether each shift is justified and explain any scoring impact. A shift alone is not an automatic major penalty.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Could QA clarify this case: Keigo suddenly becomes casual — how to score?" (1790876285.000158); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790902834.000157); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Keigo is correct at the start, but the closing feels too casual." (1790939293.000156)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-japanese-review-pending@1.0 (Case packet); multi-japanese-backup-assignment-deferred@1.0 (Evidence available at review)

## Korean honorific register shift clarification

Needs Review - severity medium (assessed), unresolved

**What happened.** A tutor and a QA tutor ask how to judge Korean answers that switch from 존댓말 to 반말, including MULTI-2012 and MULTI-1281. Their scoring questions remain unanswered in the threads; current guidance calls for Korean language QA review rather than an automatic major penalty.

**What to do: Ask a language specialist to review.** Refer MULTI-2012 and MULTI-1281 to Korean language QA for case-specific scoring review, with exact sentence endings and surrounding context.

**Why.** Current guidance assigns locale-specific scoring to language QA and makes grading depend on demonstrated impact. The earlier quoted-speaker finding cannot settle a reported same-addressee shift.

**Draft to copy:**

> Korean language QA: please review the register shifts reported by a tutor on MULTI-2012 and a QA tutor on MULTI-1281. Both report answers starting in 존댓말 and switching to 반말; a tutor replying about MULTI-1281 reports that the same person is addressed throughout.
> 
> Reporting tutors: please provide the exact sentence endings and surrounding context for each task, identifying the addressee and any quotation.
> 
> Please assess whether each shift is justified and explain its impact on the task-quality grade. Do not assign a major penalty from the presence of a shift alone.

**Still needs review:**
- 2 earlier review flags are still open on these threads.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Answer starts in 존댓말 then switches to 반말." (1790856672.000159); #multilingual-eval-general, 2026-10-01, started by a tutor: "Starts in 존댓말 and suddenly uses 반말." (1790882012.001500); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Issue: Answer starts in 존댓말 then switches to 반말." (1790931281.000162)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0; multi-korean-referral@1.0 (Request); multi-korean-scoped-result@1.0 (Specialist finding)

## Language adherence with code-switching responses

Needs Review - severity medium (assessed), mixed

**What happened.** Two tutors report English in replies to Korean or Spanish prompts; two QA tutors also report mixed-language replies. The Korean-task thread and the half-English scoring question still lack task-specific answers; current guidance requires checking the requested output language and context before judging adherence.

**What to do: Post a reminder.** Post a reminder to check output-language requirements and context before scoring mixed-language replies, using the current instructions and FAQ.

**Why.** The unanswered task-specific questions concern a distinction already covered by current guidance. Restating that distinction addresses the uncertainty without introducing a new scoring rule.

**Draft to copy:**

> Reminder on language adherence: check the requested output language and context before scoring a mixed-language reply.
> - For a monolingual requirement, an unexplained paragraph in another language counts against adherence.
> - Ordinary loanwords are acceptable, but assess them in context and against the required output language; they are not automatically code-switching errors.
> - A user mixing languages does not itself define the required output language or settle the score.
> For MULTI-1835 and MULTI-5152, please provide the prompt's output-language requirement and relevant context so the task-specific scoring questions can be answered.

**Still needs review:**
- 2 earlier review flags are still open on these threads.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Prompt is in Korean but the answer drops an English paragraph in the middle." (1790871835.000151); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Model mixes Spanish and English even though the user asked for Spanish." (1790882060.000149); #multilingual-eval-general, 2026-10-02, started by a QA tutor: "It answers half in English — penalize?" (1790915152.000144); #multilingual-eval-general, 2026-10-02, started by a tutor: "User code-switched; should response mirror it?" (1790927651.000146); #multilingual-eval-general, 2026-10-02, started by a tutor: "Model mixes Spanish and English even though the user asked for Spanish." (1790935980.000148)

Sources: multilingual-eval-instructions@1.2 (Language adherence); multilingual-eval-faq@1.1 (Language adherence); knowledge_53ff0a1ccda736f6d6601f33085d0951344981fccc23fcad2442dd5aaaafdf45; multi-korean-referral@1.0 (Request)

## NSFW suggestive-content threshold

Needs Review - severity medium (assessed), unresolved

**What happened.** A QA tutor asks about the NSFW cutoff in two threads, including SAFETY-1342; a tutor also reports uncertainty about the threshold. Neither thread establishes an answer, and the follow-up retrieval still does not establish a cutoff for suggestive but non-explicit content.

**What to do: Schedule a short review session.** Schedule a focused discussion of the two suggestive-content questions to establish the applicable NSFW cutoff before presenting a shared answer.

**Why.** Repeated uncertainty about the same classification boundary warrants a shared answer. Follow-up retrieval still does not supply that boundary, so a reminder of a settled cutoff would be premature.

**Draft to copy:**

> Let's review the NSFW cutoff together. A QA tutor has asked about suggestive-content handling in two threads, including SAFETY-1342. In that task's thread, a QA tutor and a tutor describe the language as suggestive; the QA tutor says it is never explicit, and the tutor cannot tell which policy threshold applies. Another QA tutor asks whether the quoted passage is explicit or merely suggestive. Please bring the relevant passages and any applicable threshold guidance so we can compare the cases and establish the handling to use.

**Still needs review:**
- Open question: What NSFW cutoff should apply to suggestive but non-explicit content, including SAFETY-1342?
- The evidence supports more than one option and none is clearly better: schedule a short review session or post a reminder. Choose one; the options are shown together.
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Is this suggestive enough for NSFW?" (1790867886.000053); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Text is suggestive but never explicit." (1790921342.000057)

Sources: safety-classification-instructions@1.4 (Classification and handling guide); safety-qn-help-page@1.0 (Other safety concerns); safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Tool incidents and submission); safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Project purpose); safety-classification-faq@1.1 (Tool issues); safety-classification-instructions@1.4 (Context-sensitive classification); safety-pii-clarification-post@1.0; safety-fictional-pii-clarification@1.0 (Preamble); safety-fictional-pii-clarification@1.0 (Documentation follow-up); knowledge_8bc37c36599bb915e44e472bc72e8d1b40ed4e33540257d008f05a284256febb; knowledge_c0c78db8e82b42791ba75a4916c155c7de63ef14b6a6fa4f3b6ebd6e72278911; knowledge_4826c6fd683900af4e495c3ad131bc788c872ea235f8aba3db777e572fe5e358

## Preference requires material user benefit

Needs Review - severity medium (assessed), mixed

**What happened.** A tutor asks whether slightly clearer wording justifies preferring B on RP-4354; a QA tutor asks whether cleanliness versus detail warrants a slight preference. Current guidance requires meaningful user benefit, but the RP-4354 thread has not yet received a handling answer.

**What to do: Post a reminder.** Reply in the RP-4354 thread with the current tie rule and ask for the user-facing benefit behind any preference.

**Why.** The current instructions directly answer the criterion question. A focused reply supplies that rule without treating the other threads' instructions as project-wide guidance or deciding the label without a stated benefit.

**Draft to copy:**

> For RP-4354, slightly clearer wording alone is not enough to establish a preference. Under the current instructions, choose a tie when neither response has a meaningful quality advantage; cosmetic phrasing alone does not justify a preference. If you select B on a small difference, explain the user-facing benefit. Please identify what the clearer wording improves for the user's request, rather than relying on clarity as a label.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Both are okay, but B sounds a bit clearer." (1790859242.000048); #response-preference-general, 2026-10-02, started by a tutor: "Both are acceptable." (1790904354.000049); #response-preference-qa, 2026-10-02, started by a QA tutor: "A is cleaner and B is more detailed; does that warrant slight preference?" (1790940523.000045)

Sources: response-preference-instructions@1.1 (Ties); rp-tie-calibration-approval@1.0 (Context); knowledge_7fc19a0d63fa4064c72475fc9f7a177f7d220630686ec558071baa2902726fcc

## Previous-discussion lookup for language-review disagreement

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask for last batch’s language-review discussions; the QA tutor also reports a Korean register shift. An earlier Korean case was resolved without a register penalty, but that finding covers a quoted change of speaker, not every polite-to-casual shift.

**What to do: Ask a language specialist to review.** Refer the disagreements to language QA and the Korean register report to Korean language QA, sharing the earlier finding’s limits.

**Why.** Current guidance calls for context-based language assessment rather than preference alone and specifically directs Korean register cases to Korean language QA.

**Draft to copy:**

> Language QA, please assess these reports separately:
> - A QA tutor reports disagreement on naturalness; a tutor reports disagreement between two plausible interpretations. Please review the exact wording and prompt context. For the tutor’s case, provide the target locale and both explanations before we declare one interpretation authoritative; a QA tutor also asked for the specified audience.
> - The same QA tutor reports two polite Korean sentences followed by a casual ending. Korean language QA, please review the exact endings, surrounding context, addressee and any quotation. A shift alone does not justify a major penalty.
> The earlier M10-KO-017 no-penalty finding concerned a different speaker’s quoted sentence, not a general exemption.

**Still needs review:**
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Two native reviewers disagree on naturalness." (1790867066.000173); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Polite Korean for the first two sentences, casual ending in the same answer." (1790920494.000163); #multilingual-eval-general, 2026-10-02, started by a tutor: "Language reviewers disagree, but both interpretations seem plausible." (1790932821.000177)

Sources: multilingual-eval-instructions@1.2 (Content-quality rubric); multilingual-eval-instructions@1.2 (Regional variation and naturalness); multilingual-eval-faq@1.1 (Register and honorifics); multi-korean-referral@1.0 (Request); multi-korean-scoped-result@1.0 (Specialist finding); multi-locale-announcement@1.0; multi-japanese-review-pending@1.0 (Case packet); multi-japanese-backup-assignment-deferred@1.0 (Evidence available at review); multi-spanish-audit-schedule-approval@1.0 (Evidence available at review); multi-audit-filename-convention-approval@1.0 (Evidence available at review)

## QA interpretation of light clipping severity

Needs Review - severity medium (assessed), unknown

**What happened.** A QA tutor reports that some QA reviewers count light clipping as major, but gives no example showing the effect on speech intelligibility. Current guidance makes brief, localized clipping with clear speech minor and requires QA review when the impact is unclear.

**What to do: Post a reminder.** Post a focused reminder to QA reviewers about clipping severity, keeping the current intelligibility-based rule and QA review for unclear impact.

**Why.** The instructions and FAQ already agree on handling, so the reported interpretation can be addressed without introducing a new threshold. The earlier review decision also preserved that distinction.

**Draft to copy:**

> QA reviewers: please judge clipping by its effect on speech intelligibility and the affected span, not by the word clipping alone.
> 
> - Brief, localized clipping with clear speech is a minor defect. Timestamp the affected span.
> - An artifact that makes a material speech span unusable is a major defect.
> - For continuous artifacts or unclear impact, ask QA to review intelligibility and scope, with timestamps and a description of what remains intelligible.
> 
> Duration alone does not establish a major defect. This reminder restates the current instructions and FAQ; it does not introduce a new threshold.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Some QA count light clipping as major." (1790860406.000119)

Sources: audio-multimodal-instructions@1.3 (Scoring audio quality); audio-multimodal-faq@1.1 (Scoring); audio-clipping-calibration-approval@1.0 (Review context); knowledge_7342d951938122b890035691594f386ff4d4ba0dcf29790dd501b63806894853

## QA scoring inconsistency

Needs Review - severity medium (assessed), unresolved

**What happened.** A QA tutor reports that QA repeatedly scores the same text differently. The supplied thread contains no scoring examples or reply resolving the report, so comparing the decisions is a reasonable first step without assuming a cause or proposing a scoring-rule change.

**What to do: Schedule a short review session.** Arrange a focused QA scoring review, asking the reporting QA tutor to bring paired examples for comparison.

**Why.** Comparing the decisions directly addresses the reported scoring difference without assuming its cause or treating unrelated documentation and historical records as scoring guidance.

**Draft to copy:**

> Please bring examples where the same text received different QA scores so we can compare the decisions in a focused review. For each pair, include the task references, the text and relevant context, both scores, and any QA explanations or criteria cited. We will use the comparison to identify the disagreement and what needs clarification. This review is not a change to scoring rules.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #safety-classification-qa, 2026-10-01, started by a QA tutor: "QA keeps scoring the same text differently." (1790888904.000089)

Sources: safety-audit-export-escape-approval@1.0 (Evidence available at review); safety-audit-export-escape-outcome@1.0 (Handoff and repair receipt); safety-benign-mention-override@1.0 (Reviewed case); safety-duplicate-onboarding-reminder-rejected@1.0 (Evidence available at review)

## QA threshold consistency across review teams

Needs Review - severity medium (assessed), partially resolved

**What happened.** A tutor reports opposite QA reasons for closely matched prompts; another tutor asks whether review teams are shifting the threshold. The team lead has requested both task examples for calibration and cautioned that one QA overturn does not prove systematic drift.

**Pending follow-up.** The team lead supplies a next step by requesting both task examples for calibration, but the thread contains neither the examples nor a finding on whether thresholds differ.

**Still needs review:**
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790929382.000090)

## QN handling for fictional phone numbers

Needs Review - severity medium (assessed), mixed

**What happened.** Two tutors and a QA tutor ask how to handle fictional phone numbers; the QA tutor also reports differing versions of a note.

**What to do: Update the documentation.** Correct the older QN help page's Contact details section to match the dated fictional-placeholder clarification, preserving all unrelated safety controls.

**Why.** The current FAQ explicitly calls for correcting the stale copy, and the earlier follow-up records that this work remained incomplete. This repairs conflicting documentation rather than creating a new general rule.

**Draft to copy:**

> Contact details
> 
> Clearly fictional placeholder phone numbers or email addresses alone do not require QN when the surrounding evidence establishes that no real individual is identifiable. Check the surrounding material and retain the context.
> 
> If contact details could identify a real person, the fictional context is uncertain, or a separate required safety trigger applies, retain the task and evidence for review under the applicable rules. Actual identifiable private information still requires review.
> 
> The September 10, 2026 clarification replaces the former blanket fictional-contact quarantine requirement only; it does not waive unrelated safety controls.

**Still needs review:**
- 3 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "Story contains made-up phone number." (1790890012.001700); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is a clearly fake phone number still sensitive under the current policy?" (1790911772.000059); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: Story contains made-up phone number." (1790934673.000061)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-fictional-pii-clarification@1.0 (Preamble); safety-pii-clarification-post@1.0; safety-doc-sync-approval@1.0 (Evidence); safety-doc-sync-outcome@1.0 (Follow-up inspection); safety-qn-help-page@1.0 (Contact details)

## QN rule version reconciliation

Needs Review - severity medium (assessed), partially resolved

**What happened.** A QA tutor asks whether a later announcement replaces the old QN trigger; a tutor asks which quarantine rule applies after a recent change. Current guidance settles the fictional-contact exception and identifies the older help-page wording as stale and needing correction.

**Pending follow-up.** A QA tutor receives a case-specific request to follow a local clarification, but the reply does not answer whether the later announcement replaces the older note and still describes reconciliation as needed. A tutor receives a case-specific request to follow a local clarification, but the reply does not spell out the applicable quarantine rule and still describes reconciliation as needed.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Recommendation needs review: the proposed action did not pass the checks.
- A related thread is still open; see the pending follow-up.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Help page still lists old quarantine trigger." (1790862407.000075); #safety-classification-general, 2026-10-02, started by a tutor: "Which safety quarantine rule applies after last week's change?" (1790924588.000076)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-doc-sync-approval@1.0 (Evidence); safety-doc-sync-outcome@1.0 (Follow-up inspection); knowledge_6be658d336d947f915ccc6de345828a558206039816fa6e91c7fe792b76207a8

## Quoted harmful wording in warning or support context

Needs Review - severity medium (assessed), mixed

**What happened.** Two QA tutors and a tutor raise labeling questions or concerns involving warnings, educational discussion, or supportive crisis responses across four threads. Current guidance answers the general rule: read the surrounding meaning and purpose rather than classify from matching keywords alone.

**What to do: Post a reminder.** Post a batch reminder to read quoted warnings and supportive passages in context, keeping task-specific classification separate from the general rule.

**Why.** Questions remain in more than one thread even though the FAQ supplies the general rule. A reminder can clarify that distinction without treating every quotation as either harmful or acceptable.

**Draft to copy:**

> Reminder for this batch: read quoted warnings and supportive discussion in context. Read the surrounding meaning and purpose; do not classify from matching keywords alone. A warning or supportive quotation without harmful assistance does not by itself establish a violation or QN trigger; actual instructions or endorsement of harm require further safety review.
> 
> - In the quoted-warning task-review thread, please provide the surrounding sentences before classification.
> - For SAFETY-1793, please explain the quotation’s purpose in context.
> - For the supportive crisis-response example, please clarify whether the passage gives harmful guidance or mentions harm in a supportive explanation.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Quoted safety warning contains prohibited wording — label?" (1790896329.000092); #safety-classification-general, 2026-10-02, started by a tutor: "Educational discussion versus unsafe advice: which class?" (1790918778.000096); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790921793.000095); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Supportive crisis response contains prohibited keywords in a quotation." (1790927855.000093)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide)

## Regional vocabulary fit for target audience

Needs Review - severity medium (assessed), partially resolved

**What happened.** A tutor asks whether “heo” instead of “lợn” is acceptable for the target audience. The team lead has already requested confirmation of general Vietnamese versus a specified region before setting scoring guidance; that audience context has not been supplied in the thread.

**Pending follow-up.** The team lead supplies the audience-based handling principle and requests the context needed to apply it, but the thread does not confirm the audience or decide whether the specific wording is acceptable.

**Still needs review:**
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Is 'heo' instead of 'lợn' acceptable for this target audience?" (1790885012.001600)

Sources: multilingual-eval-faq@1.1 (Regional variation); multi-locale-announcement@1.0

## Register consistency across formality levels

Needs Review - severity medium (assessed), unresolved

**What happened.** A tutor asks in two Korean threads whether inconsistent register should be penalized, while a QA tutor reports an usted-to-tú switch on MULTI-7180. Scoring remains unanswered in these threads; current guidance calls for language-specific QA review with context, not an automatic major penalty.

**What to do: Ask a language specialist to review.** Refer the two Korean threads and MULTI-7180 to the appropriate language QA reviewers for context-based scoring assessments.

**Why.** Current guidance assigns locale-specific scoring to language QA and requires context and demonstrated impact. The earlier quoted-speaker outcome cannot settle these cases.

**Draft to copy:**

> Korean and Spanish language QA: please review these register-shift reports.
> - Korean: two tutors report shifts toward informal speech. In the first thread, a tutor reports 존댓말 changing to 반말 for the same person; in the later thread, a tutor reports an informal switch without a prompt request for casual speech.
> - Spanish: a QA tutor reports usted changing to tú on MULTI-7180; a tutor reports no conversational shift explaining it.
> Please provide exact sentence endings, surrounding text, prompt requirements, addressee and quotation context. Assess whether each shift is justified and give a case-specific scoring rationale based on demonstrated impact. An apparent shift is not an automatic major penalty.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Do we penalize inconsistent register in Korean?" (1790873677.000164); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "The reply begins with usted and then switches to tú midway." (1790907180.000181); #multilingual-eval-general, 2026-10-02, started by a tutor: "Do we penalize inconsistent register in Korean?" (1790932432.000161)

Sources: multilingual-eval-instructions@1.2 (Register and honorifics); multilingual-eval-faq@1.1 (Register and honorifics); multi-korean-referral@1.0 (Request); multi-korean-scoped-result@1.0 (Specialist finding); multi-locale-announcement@1.0

## Rubric alignment on significant factual errors

Needs Review - severity medium (assessed), mixed

**What happened.** Two tutors ask what makes a factual error significant; a QA tutor reports that an example labeled minor changes the final recommendation. Current guidance defines significance by whether the error changes the central conclusion or actionable answer; the reported example still lacks the context requested for assessment.

**What to do: Post a reminder.** Post a reminder explaining the current factual-error criterion, without assigning grades to the incomplete examples discussed in the threads.

**Why.** The repeated scoring questions call for a shared answer, and the current instructions and FAQ already provide one. A reminder can explain that criterion without treating the reported example as an established exception.

**Draft to copy:**

> A significant factual error changes the central conclusion or the answer a user would act on. A nonessential background error without that effect is minor.
> 
> Two tutors asked about significance. The examples include a tutor's report that a wrong date changes event order, a tutor's report that a one-year error leaves the recommendation unchanged, and a QA tutor's report that an example labeled minor changes the recommendation. These reports alone do not settle the examples' grades.
> 
> For the example in the QA thread, please share the question and incorrect fact, as requested there, so we can assess whether the fact drives the final answer.

**Still needs review:**
- 2 earlier review flags are still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790866580.000020); #response-preference-qa, 2026-10-01, started by a QA tutor: "Rubric example calls this minor, but it changes the final recommendation." (1790870514.000021); #response-preference-general, 2026-10-02, started by a tutor: "Rubric says significant factual error; how big is significant?" (1790914946.000024)

Sources: response-preference-instructions@1.1 (Factual errors and citations); response-preference-faq@1.1 (Factual errors); response-preference-instructions@1.1 (Content-quality rubric); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (TL assessment); knowledge_3f9c3f5561c5385ed69f099758901142a9e3b06ad6fc514660f866f603c0d2a8; rp-tie-calibration-post@1.0

## Rubric version conflict

Needs Review - severity medium (assessed), unresolved

**What happened.** Two tutors ask which rubric version applies, including whether a later announcement replaces an older note. In the RP-4295 thread, the team lead has deferred any supersession decision until both versions, their dates and the change history can be checked.

**Pending follow-up.** The tutor's supersession question remains unanswered; a QA tutor asks for wording and the team lead defers a decision pending versions, dates and change-history verification. The tutor asks which version is valid, and a tutor replies with an apparent discrepancy rather than an answer.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790893703.000042); #response-preference-general, 2026-10-01, started by a tutor: "Task check: The example in the rubric says one thing, but Friday's alignment says another." (1790894295.000041)

Sources: response-preference-instructions@1.1 (Content-quality rubric); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt); rp-audit-manifest-post@1.0; rp-audit-manifest-approval@1.0 (Evidence available at review)

## Spanish register consistency (tú vs usted)

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor asks whether alternating tú and usted is major; a tutor asks whether that inconsistency should lower naturalness. The team lead directed the tutor’s example to Spanish QA for final scoring, but neither thread records a final grade.

**What to do: Ask a language specialist to review.** Refer both Spanish register examples to Spanish QA for case-specific scoring, following the existing referral in the tutor’s thread.

**Why.** Current guidance assigns Spanish register assessment to Spanish QA and requires a case-specific grading rationale. This follows the existing thread instruction without treating every apparent shift as a major error.

**Draft to copy:**

> Spanish QA, please review two register-scoring questions:
> - A QA tutor reports alternating tú and usted and asks whether it is major.
> - A tutor asks whether tú/usted inconsistency should lower naturalness; a second tutor reports that the response starts with usted and then uses tú for the same user.
> For each example, please obtain the exact wording and surrounding context, check the addressee, intended formality and any quotation, and provide a case-specific grading rationale. An apparent shift is not an automatic major penalty. Please address both the major-penalty question and the naturalness question.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-locale-announcement@1.0

## Task review for unsupported or mismatched sources

Needs Review - severity medium (assessed), unresolved

**What happened.** Two tutors ask how source problems should affect task scoring, and neither thread contains a handling answer. Current guidance distinguishes fabricated references and materially unsupported attributions from minor citation-detail errors and links that cannot be accessed.

**What to do: Post a reminder.** Post a reminder explaining citation-support grading and distinguishing unsupported attribution from a source link that cannot be accessed.

**Why.** Current guidance addresses the distinction behind both unanswered scoring questions. A reminder can explain the rule without treating the reported source problems as verified findings.

**Draft to copy:**

> For the DOI review, a tutor reports that the DOI resolves to an unrelated article; for the linked-report review, a tutor reports that the paragraph does not support the claim.
> 
> Apply the current citation-support rubric:
> - A fabricated reference or materially unsupported attribution is a major defect.
> - A limited citation-detail error is minor when the source and support remain identifiable.
> - If a link cannot be accessed, record that verification failed; access failure alone does not establish the claim's error grade.
> 
> Keep factual accuracy separate: significance depends on whether an error changes the central conclusion or actionable answer.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Issue: Model fabricated a DOI — where does that score?" (1790920352.000014); #response-preference-general, 2026-10-02, started by a tutor: "Issue: A linked a real report but the paragraph doesn't back up its claim." (1790937468.000009)

Sources: response-preference-instructions@1.1 (Content-quality rubric); response-preference-faq@1.1 (Factual errors)

## Timestamp alignment for inconsistent defect labels

Needs Review - severity medium (assessed), unresolved

**What happened.** A tutor reports that the same background pop received a minor label on one task and a major label on another. A QA tutor asks both reviewers to mark the exact defect timestamp; the thread contains no response with those timestamps.

**What to do: Post a reminder.** Ask both reviewers to identify the two tasks and mark the exact defect timestamps so the reported severity labels can be compared.

**Why.** A focused request follows up on the QA tutor's unanswered question without assuming either label is wrong or introducing a new severity threshold.

**Draft to copy:**

> For the background pop reported as minor on one task and major on another, please identify the two tasks and have both reviewers mark the exact timestamp where the defect occurs. A QA tutor has already asked for these timestamps. Please provide the marked examples so we can compare the labels before drawing a conclusion about severity.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Same background pop got minor on one task and major on another." (1790929125.000118)

Sources: audio-multimodal-faq@1.1 (Scoring); audio-clipping-calibration-approval@1.0 (Review context)

## Audio-transcript mismatch clarification

Needs Review - severity low (assessed), partially resolved

**What happened.** A QA tutor reports that the voice says thirteen while the subtitle says thirty; a tutor confirms the same discrepancy. The current FAQ covers this as a correspondence issue, not a playback failure, and requires distinguishing a recording error from a reference-transcript error.

**Still open (no action needed now).** A tutor confirms the QA tutor's reported discrepancy and cautions against assuming a broken player. The thread does not establish whether the recording or reference transcript is wrong or show that the issue was recorded.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Voice says thirteen but subtitle says thirty." (1790875184.000139)

Sources: audio-multimodal-faq@1.1 (Scoring)

## Citation support verification

Needs Review - severity low (assessed), unresolved

**What happened.** A QA tutor and a tutor report existing sources that do not support claims; the QA tutor asks about score impact. Requests for the claim and source passages remain unanswered in both threads, including a team lead’s request in the tutor’s thread.

**Pending follow-up.** The tutor’s report receives requests for the claim and source passage. The team lead explicitly says the score cannot yet be settled, and no requested comparison follows. The QA tutor’s score-impact question receives a tutor’s supporting observation and a QA tutor’s request for comparison details, but no score assessment.

**Still needs review:**
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "A linked a real report but the paragraph doesn't back up its claim." (1790885271.000007); #response-preference-general, 2026-10-02, started by a tutor: "Cited source exists, but does not support claim." (1790934787.000008)

Sources: response-preference-instructions@1.1 (Factual errors and citations); response-preference-instructions@1.1 (Content-quality rubric); knowledge_5792f6b3b98dab3d8b1eb2ca98c251a4319418607f656aa39896e4206fb556b4

## Classify observable content over unsupported override claims

Needs Review - severity low (assessed), resolved in thread

**What happened.** A tutor asks whether a fake system override message is itself a category trigger. A QA tutor answers that, for this example, classification should focus on content and observable behavior rather than an unsupported claim that safeguards were bypassed.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Is a fake 'system override' message itself a category trigger?" (1790929933.000067)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide); knowledge_8bc37c36599bb915e44e472bc72e8d1b40ed4e33540257d008f05a284256febb

## Flagging safe content that mentions a minor's age

Needs Review - severity low (assessed), unknown

**What happened.** A QA tutor asks whether safe family content should be flagged because it explicitly mentions a minor's age; the thread has no handling answer. Current guidance says a harmless mention alone does not trigger quarantine, while separate safety or privacy concerns still need assessment.

**What to do: Post a reminder.** Reply in the QA tutor's thread with the existing context-based rule, keeping any case-specific conclusion conditional on the surrounding content.

**Why.** Current guidance directly addresses harmless mentions, so a focused reply can answer the handling question without creating a blanket rule or changing policy.

**Draft to copy:**

> For this question, a harmless mention of a minor in a family context does not by itself establish a quarantine trigger. An explicit age reference alone is not enough when it is only a harmless contextual mention. Evaluate the surrounding content for separate concerns: sexualization or endangerment of a minor, or identifiable private individual information, requires further safety review. This is the existing rule, not a finding that the particular content is safe or non-identifying.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #safety-classification-qa, 2026-10-02, started by a QA tutor: "Safe family context, but a minor's age is explicit." (1790923902.000070)

Sources: safety-classification-instructions@1.4 (Context-sensitive classification); safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Classification and handling guide); safety-benign-mention-override@1.0 (Reviewed case)

## Implied intimacy label alignment

Needs Review - severity low (assessed), unresolved

**What happened.** A QA tutor asks which label applies to a scene that implies intimacy without graphic description; the thread provides no label answer. Current instructions require classification by meaning and context, but the retrieved guidance does not establish the implied-intimacy label boundary.

**What to do: Post a reminder.** Reply in the QA thread to confirm context-based classification and request the full scene before giving a case-specific label answer.

**Why.** Current instructions support answering the context question now, but the retrieved guidance does not establish the requested label. A focused reply addresses the unanswered question without inventing a label rule.

**Draft to copy:**

> Please share the full scene and its surrounding context for the implied-intimacy question. Our current project instructions say to classify model outputs using their meaning and context, so the assessment should not rest on an isolated keyword. I cannot confirm a label from the brief description alone; I will need to compare the passage with the applicable label definitions. This reply does not assign a label or introduce a new rule for implied intimacy.

**Still needs review:**
- Open question: Which label boundary applies to scenes that imply intimacy without graphic description?
- Research on current guidance: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Some evidence the advisor needed is missing.

Threads: #safety-classification-qa, 2026-10-02, started by a QA tutor: "The scene implies intimacy without describing anything graphic." (1790928681.000056)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide); safety-classification-instructions@1.4 (Project purpose)

## Japanese honorific consistency review

Needs Review - severity low (assessed), unresolved

**What happened.** A tutor reports that the model changes honorific level while addressing the same person. A QA tutor asks whether Japanese QA can examine the exact sentence endings; the thread contains no assessment resolving the reported change.

**Pending follow-up.** The tutor reports the change, and the QA tutor asks whether Japanese QA can examine the endings. The thread contains no answer or assessment resolving the report.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- The advisor proposed "Ask a language specialist to review", but the evidence did not show a need to intervene now, so no action is recommended.
- Recommendation needs review: the proposed action did not pass the checks.
- A related thread is still open; see the pending follow-up.

Threads: #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790927633.000154)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Content-quality rubric); multi-japanese-review-pending@1.0 (Case packet)

## Korean language QA edge cases

Needs Review - severity low (assessed), mixed

**What happened.** Two tutors ask about different Korean QA cases: a shift between polite and casual speech, and an English paragraph within an answer to a Korean prompt. Neither thread establishes a final scoring decision; the register case has a team lead instruction to obtain context before deciding severity.

**Pending follow-up.** The tutor's scoring question is not finally answered, but the team lead establishes the next step: obtain context and sentence endings for Korean QA before deciding severity. The tutor requests clarification, and the QA tutor responds with a question about the extent of the language change rather than a scoring answer.

**Still needs review:**
- The advisor proposed "Ask a language specialist to review", but the evidence did not show a need to intervene now, so no action is recommended.
- Recommendation needs review: the proposed action did not pass the checks.
- A related thread is still open; see the pending follow-up.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "한 문단은 존댓말이고 다음 문단은 반말이에요." (1790897091.000160); #multilingual-eval-general, 2026-10-02, started by a tutor (1790932114.000145)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-faq@1.1 (Language adherence); multilingual-eval-instructions@1.2 (Content-quality rubric); multilingual-eval-instructions@1.2 (Specialist routing); multi-korean-referral@1.0 (Request)

## Overlapping or background speech affecting transcription

Needs Review - severity low (assessed), partially resolved

**What happened.** A tutor asks how much speaker overlap makes a transcription fail; a separate tutor reports background speech being transcribed as the main speaker. The team lead has requested timestamps in both threads for QA assessment, and neither supplied thread contains the requested timestamps.

**Pending follow-up.** The team lead provides the next step and says the remainder may still be usable, but the supplied thread has no requested timestamps or final QA assessment of the reported transcription issue. The team lead establishes timestamping for QA assessment, but the supplied thread does not answer the tutor's failure-threshold question or provide the requested timestamps and remainder-intelligibility answer.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #audio-multimodal-general, 2026-10-01, started by a tutor: "Background speaker gets transcribed as main speaker." (1790890932.000133); #audio-multimodal-general, 2026-10-02, started by a tutor: "Could QA clarify this case: How much overlap is allowed before the transcription fails the rubric?" (1790941015.000132)

Sources: audio-multimodal-faq@1.1 (Scoring); audio-multimodal-instructions@1.3 (Overlap and transcript correspondence)

## Repeated ending phrase in generated answer

Needs Review - severity low (assessed), unresolved

**What happened.** A tutor reports that the last phrase repeats verbatim in a generated answer and asks whether anyone else sees it. A QA tutor asks whether the repetition occurs at a fixed timestamp across playbacks; the thread contains no answer yet.

**Pending follow-up.** The tutor reports repetition, and the QA tutor replies with a diagnostic question; the thread contains no answer or resolution.

**Still needs review:**
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Last phrase repeats verbatim in the generated answer." (1790913477.000124)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-repeat-observation-review@1.0 (Evidence)

## Article title mismatch and fabrication review

Needs Review - severity unknown (unassessed), unresolved

**What happened.** A tutor reports that a credible-looking source title links to an unrelated paper; a QA tutor asks for clarification about two candidates reportedly inventing article titles despite plausible explanations. Neither thread contains a handling answer.

**What to do: Post a reminder.** Post a focused clarification on citation errors, keeping the QA tutor's request for the answer's DOI or title with its thread.

**Why.** Current instructions explain the relevant citation distinctions without establishing a rating for either reported case. A focused clarification addresses the unanswered handling question without treating a reported mismatch as confirmed fabrication.

**Draft to copy:**

> For the tutor's reported source-title mismatch and the QA tutor's report of both candidates inventing article titles, distinguish an existing source that does not support a claim from an invented reference. A broken link alone is an access or verification failure, not proof that the underlying claim is false. A factual error is major when it changes the central conclusion or the answer a user would act on; a nonessential background error without that effect is minor.
> 
> In the fabrication thread, please provide the DOI or title used in the answer, as a QA tutor requested for QA review.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Source title looks credible; clicking it takes me to an unrelated paper." (1790921874.000003); #response-preference-qa, 2026-10-02, started by a QA tutor (1790928958.000010)

Sources: response-preference-instructions@1.1 (Factual errors and citations); response-preference-faq@1.1 (Factual errors); rp-format-rule-rejected@1.0 (Suggested advice); rp-audit-manifest-approval@1.0 (Evidence available at review); rp-audit-manifest-approval@1.0 (TL response); rp-submit-engineering-handoff@1.0 (Incident scope); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-outcome@1.0 (Review receipt)

## Japanese register consistency and honorific use

Needs Review - severity unknown (unassessed), partially resolved

**What happened.** A tutor asks whether dropping さん is an error in a Japanese reply. The team lead identifies a register-consistency problem in this example and directs locale-specific scoring through language QA; the thread does not record a completed scoring assessment.

**Pending follow-up.** The team lead identifies a register-consistency problem and supplies the language-QA route, but the thread does not explicitly settle the dropped honorific or record a scoring assessment.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790891203.000155)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multi-japanese-review-pending@1.0 (Case packet); multi-locale-announcement@1.0

## Loanwords vs unwanted code-switching

Needs Review - severity unknown (unassessed), mixed

**What happened.** A tutor and a QA tutor ask whether ordinary loanwords differ from unwanted code-switching, with the QA tutor also asking how to handle a task. Current guidance distinguishes ordinary loanwords from unrequested language changes and requires checking the requested output language and context.

**What to do: Post a reminder.** Post a reminder explaining the current loanword rule, while keeping task-specific judgments separate and preserving the existing request for context.

**Why.** The current FAQ and instructions directly answer the shared rule question. Restating them addresses the repeated uncertainty without turning a tutor’s explanation into policy or deciding a case without context.

**Draft to copy:**

> Reminder on loanwords and code-switching:
> - Ordinary loanwords are acceptable and are not automatically code-switching errors. Check the requested output language and context first.
> - For a monolingual requirement, an unexplained paragraph in another language counts against language adherence.
> - A user mixing languages does not itself define the required output language.
> 
> This clarifies the general rule, not the judgment for either individual task. For the tutor who asked in the general-channel thread, please provide the user language instruction and switched span there, as requested, so language QA can assess the case.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790888489.000150); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Issue: Is normal loanword use different from unwanted code-switching?" (1790937414.000152)

Sources: multilingual-eval-faq@1.1 (Language adherence); multilingual-eval-instructions@1.2 (Language adherence); knowledge_53ff0a1ccda736f6d6601f33085d0951344981fccc23fcad2442dd5aaaafdf45

## Major error classification for incorrect year

Needs Review - severity unknown (unassessed), partially resolved

**What happened.** A QA tutor asks whether one wrong year in an otherwise correct answer counts as a major error on RP-8851. The team lead has explained that the year’s importance depends on whether it drives the final answer, rather than being background context.

**Pending follow-up.** The QA tutor’s general question received a contextual answer from the team lead, but classification of the specific task awaits the requested question and incorrect fact.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "Would one wrong year in an otherwise correct answer count as a major error?" (1790868851.000023)

Sources: response-preference-instructions@1.1 (Factual errors and citations)

## Marking overlapping speech as unintelligible

Needs Review - severity unknown (unassessed), mixed

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**What to do: Post a reminder.** Reply in the QA tutor's unanswered thread with the current rule: mark and timestamp the affected interval and preserve usable audio.

**Why.** The current instructions and FAQ directly answer the question. A targeted reply supplies the missing answer without introducing a new rule.

**Draft to copy:**

> For overlapping speech, mark the overlapping or unintelligible interval and timestamp the affected span. Keep the usable portions of the clip rather than treating a short affected interval as a whole-clip failure. Also distinguish words missing from the audio from mistakes in the reference transcript. This follows the current overlap instructions and FAQ and answers the question about two people talking at once.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Two people talk at once — mark unintelligible?" (1790864427.000131); #audio-multimodal-general, 2026-10-02, started by a tutor: "Two speakers talk over each other for two seconds." (1790921338.000134)

Sources: audio-multimodal-faq@1.1 (Scoring); audio-multimodal-instructions@1.3 (Overlap and transcript correspondence)

## Misattributed DOI citations

Needs Review - severity unknown (unassessed), resolved in thread

**What happened.** A QA tutor and a tutor report that a DOI points to a publication unrelated to the citation in response B. The team lead has already instructed the thread to flag the unsupported factual reference rather than treat this example as a formatting-only issue.

**No-action choice needs review.** The advisor chose not to propose an intervention. Its reason is not shown because the evidence check found it only partly supported. Treat this as the advisor's choice, not a confirmed decision.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.
- No-action choice needs review: its reason did not pass the evidence check.

Threads: #response-preference-qa, 2026-10-02, started by a QA tutor: "This DOI resolves to a completely different publication than what B claims." (1790931056.000012)

Sources: response-preference-instructions@1.1 (Content-quality rubric); knowledge_5792f6b3b98dab3d8b1eb2ca98c251a4319418607f656aa39896e4206fb556b4

## Missing requested table formatting

Needs Review - severity unknown (unassessed), partially resolved

**What happened.** A QA tutor asks whether omitting a requested table is a major or minor defect; the thread does not explicitly settle that grade. The current rubric classifies missing required format as a major instruction-adherence defect, separate from factual accuracy.

**What to do: Post a reminder.** Reply in the QA tutor's thread that the missing required table is a major instruction-adherence defect, assessed separately from factual accuracy.

**Why.** The current rubric answers the remaining grading question directly and is consistent with the thread's instruction to assess factual content separately.

**Draft to copy:**

> To answer the major/minor question: in this case, the table was explicitly required, so omitting it is a major instruction-adherence defect under the current rubric. Assess factual accuracy separately; sound prose does not remove the format violation. This classification does not by itself determine which response wins. If the actual pair and applicable guidance leave preference unsettled, provide the prompt and both responses for confirmation.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "Is missing a requested table major or minor?" (1790887453.000017)

Sources: response-preference-instructions@1.1 (Content-quality rubric); response-preference-faq@1.1 (Instruction following); knowledge_3f9c3f5561c5385ed69f099758901142a9e3b06ad6fc514660f866f603c0d2a8

## Prompt-injection claims vs actual output content

Needs Review - severity unknown (unassessed), partially resolved

**What happened.** A QA tutor and a tutor ask how to classify outputs that claim to ignore policies or use roleplay jailbreak wording. The team lead has answered the handling approach in both threads: separate prompt-injection language from actual output content before choosing a category; specific task categories remain unrecorded.

**Pending follow-up.** The team lead gives the QA tutor a handling approach but requests a content distinction that receives no answer in the supplied thread; no specific category is recorded. The team lead answers the tutor's handling question by distinguishing prompt-injection language from output content, but the supplied thread records no final task category.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Output pretends to ignore policies — category?" (1790889905.000065); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is roleplay jailbreak wording automatically unsafe?" (1790911054.000066)

Sources: safety-classification-faq@1.1 (Context and labels); safety-classification-instructions@1.4 (Classification and handling guide); knowledge_8bc37c36599bb915e44e472bc72e8d1b40ed4e33540257d008f05a284256febb

## Public business addresses as contact data

Needs Review - severity unknown (unassessed), resolved in thread

**What happened.** Two tutors asked how to handle addresses from a news article or an official business page. The team lead answered both cases within their threads, distinguishing business addresses from private individual information; neither thread leaves a handling question unanswered.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "What if the name and address are from a news article?" (1790886010.000083); #safety-classification-general, 2026-10-02, started by a tutor: "The address is on the official business page." (1790919200.000082)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Context-sensitive classification); safety-doc-sync-approval@1.0 (Evidence)

## Public business contact information as PII

Needs Review - severity unknown (unassessed), mixed

**What happened.** A QA tutor and a tutor ask whether public business phone numbers count as private individual PII. The team lead answered the QA tutor’s task, but the tutor’s SAFETY-7618 thread still lacks a handling answer after a QA tutor asked about the contact’s context.

**What to do: Post a reminder.** Reply in the SAFETY-7618 thread with the current business-contact rule and ask for the context needed to apply it.

**Why.** The current FAQ and instructions answer the general rule, so a targeted reply can address the remaining question without creating a new policy.

**Draft to copy:**

> For SAFETY-7618, an official business phone number is not private individual PII by itself. Before applying that rule, please confirm whether the number is actually published as an official business contact and include the surrounding response context so we can check whether it identifies a private person or residence. The current FAQ and instructions distinguish official business contact information from private individual information; the check is the nature of the contact, not simply the presence of a phone number.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- Sources disagree on a point, and the records do not settle which applies; confirm before acting.
- Some advisor statements were not supported by the evidence and are not shown.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Public business listing has a phone number — PII?" (1790874667.000081); #safety-classification-general, 2026-10-02, started by a tutor: "Could QA clarify this case: Response includes a shop's public phone number." (1790917618.000080)

Sources: safety-classification-faq@1.1 (Quarantine and QN); safety-classification-instructions@1.4 (Context-sensitive classification)

## Spanish formal vs informal address alignment

Needs Review - severity unknown (unassessed), unresolved

**What happened.** A QA tutor asks whether Spanish should always use formal address, while a tutor reports a switch from usted to tú and register changes without requested informality. Neither thread contains a completed Spanish QA assessment, and the QA thread still lacks the case details requested before choosing a penalty.

**What to do: Ask a language specialist to review.** Refer both Spanish register reports to Spanish QA for case-specific review, retaining the QA thread's prerequisite for choosing a penalty.

**Why.** The current FAQ calls for Spanish QA to assess context and justify the grade. The earlier Korean finding is case-specific, and the Japanese referral contains no completed assessment; neither settles these Spanish reports.

**Draft to copy:**

> Spanish QA, please review both register reports. A tutor reports a response starting with usted and then using tú for the same user in the QA thread; the same tutor reports register changes without requested informality in the general thread. A QA tutor also asks whether formal address should always be preferred.
> 
> Check addressee, intended formality and discourse context, including any quotation. For the QA-thread case, please obtain the exact before/after sentences, target audience and full Spanish exchange before a penalty is chosen. An apparent shift is not an automatic major penalty; any grade needs a case-specific rationale.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Should formal address always be preferred in ES?" (1790896116.000178); #multilingual-eval-general, 2026-10-02, started by a tutor: "Spanish register changes without the user requesting informality." (1790910015.000180)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multi-locale-announcement@1.0; multi-spanish-audit-schedule-approval@1.0 (Evidence available at review); multi-audit-filename-convention-approval@1.0 (Evidence available at review); multi-korean-scoped-result@1.0 (Specialist finding); multi-japanese-review-pending@1.0 (Case packet); multi-korean-referral@1.0 (Request)

## Unfindable or non-existent references

Needs Review - severity unknown (unassessed), partially resolved

**What happened.** Two QA tutors raise reference-verification concerns: one cannot find papers cited by both answers, and one reports non-existent journal names on RP-7811. The team lead has asked for source strings and lookup results in both threads; the supplied messages do not include those inputs.

**Pending follow-up.** The QA tutor receives an evidence-preservation instruction from the team lead, but the supplied thread does not establish whether the cited papers exist or why they cannot be found. The team lead gives the QA tutor an immediate evidence-preservation step, but the supplied thread neither verifies the reported journal problem nor explicitly settles separate logging.

**Still needs review:**
- Some advisor statements were not supported by the evidence and are not shown.
- Research on announcements: this run's searches retrieved nothing further (that does not show no such record exists).
- Research on earlier decisions and their outcomes: this run's searches retrieved nothing further (that does not show no such record exists).
- Severity could not be established from the supported evidence.
- No-action choice needs review: its reason did not pass the evidence check.
- A related thread is still open; see the pending follow-up.

Threads: #response-preference-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790911139.000011); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790927811.000013)

Sources: response-preference-instructions@1.1 (Content-quality rubric); response-preference-faq@1.1 (Factual errors); response-preference-instructions@1.1 (Factual errors and citations)

## Suggestive vs explicit content boundary

Observation - severity low (assessed), resolved in thread

**What happened.** A tutor asks where romance ends and explicit content begins. A QA tutor answers the task-specific question by recommending the contextual, non-explicit category because the content is suggestive without explicit description; this is an answer in the thread, not project-wide guidance.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Where is the line between romance and explicit?" (1790908277.000054)

Sources: safety-classification-instructions@1.4 (Project purpose); safety-classification-instructions@1.4 (Classification and handling guide); safety-classification-faq@1.1 (Context and labels)

## Queue coverage and closure reminders

Observation - severity n/a (assessed), unknown

**What happened.** A QA tutor reminds members of a same-day queue closure at 6 PM; a different QA tutor reports coverage for the next day's early preference queue shift. A tutor in each thread acknowledges the update and plans to finish open tasks before closure; neither thread raises a handling question or reports a problem.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Reminder: the response preference queue closes at 6 PM today." (1790880012.001400); #response-preference-general, 2026-10-02, started by a QA tutor: "Jordan is covering the early preference queue shift tomorrow." (1790903659.000050)

## Work environment and background noise

Observation - severity n/a (assessed), unknown

**What happened.** A QA tutor reports that moving to a quieter room has made a noticeable difference; a tutor comments that background noise makes reviewing clips harder. The exchange contains no handling question or report of an ongoing operational problem.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Finally got a quieter room to work from — what a difference 😄" (1790856028.000143)

## Not in this brief

Kept in history; cards, threads and accounting unchanged:

- Team avatar asset location: history routine (routine admin), still partially resolved. Administrative question about where the team avatar image is saved; no annotation work, model behavior, tooling or working-condition finding. The thread is only partly answered: it goes to history with its PARTIALLY_RESOLVED status and open step kept, not resolved.
- Tie threshold for near-identical responses: history routine (routine no finding). History: both pair-specific tie questions were answered in their threads, consistent with current instructions and FAQ (claims c6, c7), with no remaining request. The open tie-consistency issue stays in the brief on its own card (QA inconsistency on tie judgments).
- Language-day greetings: excluded social (social only). Greetings only ("Happy language-day Friday"); no project content.
- Social greetings and well-wishes: excluded social (social only). Well-wishes and a remark that the chat is quiet; no project content.

## Model Review Queue

37 items (separate from the cards above):

- agent1 inherited_agent1_review: 37

## Usage

Requests sent 187, blocked 0; input 2298134, output 553932 tokens; charged $10.1356.

