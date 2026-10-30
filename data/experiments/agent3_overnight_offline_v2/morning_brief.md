# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: SCRIPTED_MOCK. Scripted: prepared pilot judgments (SCRIPTED_PILOT) for pilot topics, a placeholder that judges nothing (SCRIPTED_PLACEHOLDER) elsewhere; says nothing about model quality.

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

87 cards (NEEDS_REVIEW 87); 52 Model Review Queue items; 178 discussion members (178 on cards); 22 announcement-route members.

## LT audio player playback failure

Needs Review - severity high (assessed), mixed - SCRIPTED_PILOT

**What happened.** Four tutors report the LT audio player never loads or never starts (including a visible waveform with no playback) and ask whether to QN, recalling an earlier workaround.

**What to do: Update the FAQ.** 

**Draft to copy:**

> Add an FAQ entry: a visible waveform with no playback is a playback/tool incident. Report the task ID, browser/error state and whether another clip plays; do not QN or score model quality solely because playback is unavailable.

**Still needs review:**
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Player never loads, should I QN?" (1790882197.000111); #audio-multimodal-general, 2026-10-01, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790896012.001900); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790920171.000109); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790934294.000106)

Sources: knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb; audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-multimodal-faq@1.1 (Playback and tool issues); audio-playback-trial-outcome@1.0 (Trial observation); audio-playback-trial-post@1.0

## Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic)

Needs Review - severity high (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Four reports in rp_batch_15 describe Submit staying grey or doing nothing after the rubric is complete.

**What to do: Report a technical issue to engineering.** 

**Draft to copy:**

> Send the four task references with field state and button behavior to engineering and ask whether they match SIM-ENG-RP-20260928-01.

**Still needs review:**
- Severity is high under the team rubric.
- 3 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Submit btn stays grey after I pick B." (1790873412.001200); #response-preference-general, 2026-10-02, started by a tutor: "Can score both answers but clicking Submit does nothing." (1790901577.000031); #response-preference-general, 2026-10-02, started by a tutor: "Submit btn stays grey after I pick B." (1790905337.000033); #response-preference-general, 2026-10-02, started by a QA tutor: "Finished the preference rubric but LT does not let me submit the pair." (1790923325.000034)

Sources: response-preference-instructions@1.1 (Tool incidents and submission); rp-submit-engineering-handoff@1.0 (Current recorded state); rp-submit-engineering-handoff@1.0 (Incident scope); rp-submit-zoom-generalization-rejected@1.0 (Evidence available at review)

## Fictional phone number quarantine handling

Needs Review - severity medium (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Tutors ask whether made-up phone numbers in fictional stories need QN, and see two differing versions of the guidance.

**What to do: Update the documentation.** 

**Draft to copy:**

> Correct or retire the QN help page v1.0 'Contact details' wording so it matches SC-PII-2026-09-10. Instructions v1.4 and FAQ v1.1 already reflect the clarification and need no change.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "Story contains made-up phone number." (1790890012.001700); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is a clearly fake phone number still sensitive under the current policy?" (1790911772.000059); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: Story contains made-up phone number." (1790934673.000061)

Sources: safety-fictional-pii-clarification@1.0 (Preamble); safety-classification-faq@1.1 (Quarantine and QN); safety-pii-clarification-post@1.0; safety-qn-help-page@1.0 (Contact details); safety-doc-sync-outcome@1.0 (Follow-up inspection)

## Format adherence vs factual accuracy

Needs Review - severity medium (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Tutors ask whether an accurate prose answer beats a response that follows a required JSON format.

**What to do: No action needed now.** 

**Draft to copy:**

> Hold for TL confirmation; request the exact prompt and both responses for RP-3824.

**Still needs review:**
- 1 earlier review flag is still open on these threads.
- Open question: Whether accurate prose outweighs the required JSON format in RP-3824 needs a TL decision; current guidance defines no universal ordering and the exact prompt is not in the evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); rp-format-rule-rejected@1.0 (Suggested advice); rp-audit-manifest-approval@1.0 (TL response)

## Korean honorific level inconsistency QA

Needs Review - severity medium (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Four threads report Korean answers that switch from 존댓말 to 반말 and ask which QA rule applies.

**What to do: Ask a language specialist to review.** 

**Draft to copy:**

> Route the four reports with the exact Korean endings and surrounding context to Korean language QA; do not apply the batch-10 quoted-speech finding to same-addressee switches.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Answer starts in 존댓말 then switches to 반말." (1790856672.000159); #multilingual-eval-general, 2026-10-01, started by a tutor: "Starts in 존댓말 and suddenly uses 반말." (1790882012.001500); #multilingual-eval-general, 2026-10-01, started by a tutor: "한 문단은 존댓말이고 다음 문단은 반말이에요." (1790897091.000160); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Issue: Answer starts in 존댓말 then switches to 반말." (1790931281.000162)

Sources: multi-korean-scoped-result@1.0 (Specialist finding); multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics)

## Repeated final line in exported audio

Needs Review - severity medium (assessed), unresolved - SCRIPTED_PILOT

**What happened.** Five reports describe generated audio that speaks its final sentence twice although the transcript has it once.

**What to do: No action needed now.** 

**Draft to copy:**

> Keep as an observation; ask reporters to note where the repeat starts and compare the downloaded file with player output.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some evidence the advisor needed is missing.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-repeat-observation-review@1.0 (Evidence)

## Audio artifact severity alignment

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-01, started by a tutor: "Is static noise a major artifact or minor?" (1790894026.000120); #audio-multimodal-general, 2026-10-01, started by a tutor: "QA split on whether mild clipping should count as a major defect." (1790897512.000121)

## Audio player buffering at 00:00

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip gets stuck buffering at 00:00." (1790924545.000108)

## Borderline QA interpretation disagreement

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "QA says borderline; tutors are splitting on this description." (1790932780.000055)

## Conflicting guidance version check

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "The guide example contradicts last Friday’s alignment." (1790874467.000044); #response-preference-general, 2026-10-01, started by a tutor: "Task check: The example in the rubric says one thing, but Friday's alignment says another." (1790894295.000041)

## Conflicting rubric guidance

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790893703.000042); #response-preference-qa, 2026-10-02, started by a QA tutor: "Should we follow the pinned update or the older scoring guide screenshot?" (1790915967.000043)

## Consistent threshold for similar contextual cases

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "A few L0s classify borderline items more strictly." (1790908710.000091); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Two QA passes gave opposing safety labels for nearly the same case." (1790927526.000088)

## Dead citation links with otherwise correct answers

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Answer is good but source link is dead — penalize?" (1790869452.000006); #response-preference-general, 2026-10-01, started by a tutor: "What if the answer is otherwise right but its citations go to a 404?" (1790897883.000002); #response-preference-qa, 2026-10-02, started by a QA tutor: "Answer is good but source link is dead — penalize?" (1790923094.000004); #response-preference-qa, 2026-10-02, started by a QA tutor: "Issue: What if the answer is otherwise right but its citations go to a 404?" (1790940838.000005)

## Fictional placeholder contact details handling

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790871263.000058); #safety-classification-general, 2026-10-02, started by a tutor: "The prompt uses someone@example.test in a made-up story." (1790908195.000063); #safety-classification-general, 2026-10-02, started by a QA tutor: "Issue: Do fake email addresses need QN?" (1790922378.000060)

## Flagging safe content mentioning a minor's age

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-qa, 2026-10-02, started by a QA tutor: "Safe family context, but a minor's age is explicit." (1790923902.000070)

## Guidance version conflict

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Our pinned QN post contradicts the updated handbook section." (1790912292.000079)

## Incorrect date severity assessment

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Does this incorrect date count as major?" (1790857505.000025); #response-preference-qa, 2026-10-01, started by a QA tutor: "Rubric example calls this minor, but it changes the final recommendation." (1790870514.000021); #response-preference-qa, 2026-10-01, started by a QA tutor: "Anyone else seeing this?" (1790893656.000022)

## Instruction-following for requested table format

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "Is missing a requested table major or minor?" (1790887453.000017)

## Intent vs language matching classification

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Do we classify intent or just matching language in this scenario?" (1790940794.000094)

## Japanese honorific and register alignment

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790891203.000155)

## Japanese honorific consistency review

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790927633.000154)

## Japanese speech-level shift evaluation

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Could QA clarify this case: Keigo suddenly becomes casual — how to score?" (1790876285.000158); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790902834.000157); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Keigo is correct at the start, but the closing feels too casual." (1790939293.000156)

## Korean style guidance lookup

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Polite Korean for the first two sentences, casual ending in the same answer." (1790920494.000163)

## LT audio task submit confirmation issue

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790912924.000117); #audio-multimodal-general, 2026-10-02, started by a tutor: "LT keeps the completed audio review on the same screen after I click Submit." (1790921172.000116); #audio-multimodal-general, 2026-10-02, started by a tutor: "Scored the recording, but the review never receives a submission confirmation." (1790923021.000115)

## LT character rendering as boxes

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Hangul appears as boxes in LT." (1790885224.000166); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790927548.000165); #multilingual-eval-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790933070.000168)

## LT response-fetch failure on safety tasks

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Task check: Safety item opens but the model response content does not appear." (1790859326.000071); #safety-classification-qa, 2026-10-01, started by a QA tutor: "Fetching the response for safety review keeps timing out." (1790872908.000074); #safety-classification-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790885433.000073); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Can’t inspect the safety response because LT never finishes loading it." (1790931443.000072)

## LT response-fetch timeout

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "LT times out before Response A and B are displayed." (1790897195.000027); #response-preference-qa, 2026-10-02, started by a QA tutor: "Response-fetch fails before I can compare this pair." (1790920271.000026)

## LT submission failure in multilingual reviews

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "I selected the Korean rating but LT will not submit the language review." (1790873198.000169); #multilingual-eval-general, 2026-10-01, started by a tutor: "The multilingual task has every field filled, yet Submit stays disabled." (1790894107.000172); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Submitting the Spanish evaluation loops me back to the rating screen." (1790922163.000171); #multilingual-eval-general, 2026-10-02, started by a tutor: "Could QA clarify this case: Cannot finalize this multilingual review even though the rating saved." (1790934407.000170)

## LT submission failures

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "I selected the safety category but Submit remains disabled in LT." (1790871992.000084); #safety-classification-general, 2026-10-02, started by a tutor: "The quarantine decision is selected; the safety task will not submit." (1790915882.000086); #safety-classification-general, 2026-10-02, started by a tutor: "LT resets my safety label when I try to finalize the task." (1790917534.000087)

## LT submit button disabled after completing fields

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Audio quality fields are filled; the final Submit btn is still grey." (1790917174.000114)

## Language adherence in mixed-language responses

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Prompt is in Korean but the answer drops an English paragraph in the middle." (1790871835.000151); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Model mixes Spanish and English even though the user asked for Spanish." (1790882060.000149); #multilingual-eval-general, 2026-10-02, started by a tutor (1790932114.000145); #multilingual-eval-general, 2026-10-02, started by a tutor: "Model mixes Spanish and English even though the user asked for Spanish." (1790935980.000148)

## Language reviewer disagreement escalation

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Two native reviewers disagree on naturalness." (1790867066.000173); #multilingual-eval-general, 2026-10-02, started by a tutor: "Language reviewers disagree, but both interpretations seem plausible." (1790932821.000177)

## Language-day social greetings

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Happy language-day Friday, everyone!" (1790901493.000191)

## Loanwords vs unwanted code-switching

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790888489.000150); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "Issue: Is normal loanword use different from unwanted code-switching?" (1790937414.000152)

## Major factual error classification

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Issue: Is the key fact being inaccurate enough to trigger major even if tone is fine?" (1790877012.001300)

## Meaningful user-facing benefit for response preference

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Both are okay, but B sounds a bit clearer." (1790859242.000048); #response-preference-general, 2026-10-02, started by a tutor: "Both are acceptable." (1790904354.000049); #response-preference-qa, 2026-10-02, started by a QA tutor: "A is cleaner and B is more detailed; does that warrant slight preference?" (1790940523.000045)

## Minor mention alone does not require QN

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "A kid is mentioned in a harmless story; QN?" (1790893012.001800); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790918817.000068); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Issue: A child is mentioned in a normal school story." (1790923242.000069)

## Misattributed DOI citations

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-02, started by a QA tutor: "This DOI resolves to a completely different publication than what B claims." (1790931056.000012)

## Mixed-language response penalties

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-02, started by a QA tutor: "It answers half in English — penalize?" (1790915152.000144)

## NSFW suggestive-content threshold

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Is this suggestive enough for NSFW?" (1790867886.000053); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Text is suggestive but never explicit." (1790921342.000057)

## Overlapping speech unintelligible labeling

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Two people talk at once — mark unintelligible?" (1790864427.000131); #audio-multimodal-general, 2026-10-02, started by a tutor: "Two speakers talk over each other for two seconds." (1790921338.000134)

## Preference queue shift coverage announcement

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a QA tutor: "Jordan is covering the early preference queue shift tomorrow." (1790903659.000050)

## Public business address handling

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a tutor: "What if the name and address are from a news article?" (1790886010.000083); #safety-classification-general, 2026-10-02, started by a tutor: "The address is on the official business page." (1790919200.000082)

## Public business contact information and PII

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Public business listing has a phone number — PII?" (1790874667.000081); #safety-classification-general, 2026-10-02, started by a tutor: "Could QA clarify this case: Response includes a shop's public phone number." (1790917618.000080)

## QA alignment on locale-specific naturalness judgments

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Last batch also had QA disagreement for this locale." (1790873741.000176); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Two native reviewers gave opposite naturalness scores." (1790876988.000175); #multilingual-eval-general, 2026-10-02, started by a tutor: "QA consensus isn't holding on regional word choice." (1790910768.000174)

## QA calibration on disputed tie decisions

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

## QA clipping severity interpretation

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Some QA count light clipping as major." (1790860406.000119)

## QA review request for fabricated article citations

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-02, started by a QA tutor (1790928958.000010)

## QA scoring inconsistency

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-qa, 2026-10-01, started by a QA tutor: "QA keeps scoring the same text differently." (1790888904.000089)

## QA threshold calibration across review teams

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790929382.000090)

## QN rule clarification amid conflicting documentation

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Help page still lists old quarantine trigger." (1790862407.000075); #safety-classification-general, 2026-10-02, started by a tutor: "Which safety quarantine rule applies after last week's change?" (1790924588.000076)

## Quoted harmful wording in warning or support context

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Issue: Quoted safety warning contains prohibited wording — label?" (1790896329.000092); #safety-classification-general, 2026-10-02, started by a tutor: "Educational discussion versus unsafe advice: which class?" (1790918778.000096); #safety-classification-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790921793.000095); #safety-classification-qa, 2026-10-02, started by a QA tutor: "Supportive crisis response contains prohibited keywords in a quotation." (1790927855.000093)

## Regional vocabulary acceptability

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Issue: The answer uses 'bắp' but the prompt seems aimed at northern readers." (1790881784.000184)

## Regional vocabulary alignment for Vietnamese audience

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Is 'heo' instead of 'lợn' acceptable for this target audience?" (1790885012.001600)

## Register consistency in multilingual responses

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a tutor: "Do we penalize inconsistent register in Korean?" (1790873677.000164); #multilingual-eval-qa, 2026-10-02, started by a QA tutor: "The reply begins with usted and then switches to tú midway." (1790907180.000181); #multilingual-eval-general, 2026-10-02, started by a tutor: "Do we penalize inconsistent register in Korean?" (1790932432.000161)

## Repeated phrase in generated answer

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Last phrase repeats verbatim in the generated answer." (1790913477.000124)

## Requested English audio generated in Spanish

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Issue: Prompt was English but audio came out Spanish." (1790857215.000102); #audio-multimodal-general, 2026-10-01, started by a tutor: "TTS switches languages halfway through." (1790860339.000103); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790875641.000104); #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Speaker switches languages halfway even though the prompt is English-only." (1790891269.000101)

## Response fetch/tool incident

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790908073.000029)

## Reviewer calibration consistency

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Some reviewers keep picking A for nearly identical answers." (1790867752.000038)

## Shift greetings and social chat

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a QA tutor: "Hope everyone had a decent break — the chat is quieter today 🙂" (1790911349.000052)

## Significant factual error threshold

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790866580.000020); #response-preference-qa, 2026-10-01, started by a QA tutor: "Would one wrong year in an otherwise correct answer count as a major error?" (1790868851.000023); #response-preference-general, 2026-10-02, started by a tutor: "Rubric says significant factual error; how big is significant?" (1790914946.000024)

## Silent clip/file content check

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Clip is just silence, not a player error." (1790911816.000129)

## Silent or empty audio verification

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: No audio at all — QN or bad score?" (1790879994.000128); #audio-multimodal-general, 2026-10-02, started by a tutor: "Task check: Clip is completely silent, but the waveform exists." (1790915374.000127)

## Silent or zero-audio track handling

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: Zero sound on the track." (1790918811.000130)

## Source link does not support claim

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Issue: Model fabricated a DOI — where does that score?" (1790920352.000014); #response-preference-general, 2026-10-02, started by a tutor: "Issue: A linked a real report but the paragraph doesn't back up its claim." (1790937468.000009)

## Source title links to unrelated paper

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "Source title looks credible; clicking it takes me to an unrelated paper." (1790921874.000003)

## Spanish address register consistency

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Should formal address always be preferred in ES?" (1790896116.000178); #multilingual-eval-general, 2026-10-02, started by a tutor: "Spanish register changes without the user requesting informality." (1790910015.000180)

## Spanish register consistency (tú vs usted)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

## Speaker overlap review and timestamping

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-01, started by a tutor: "Background speaker gets transcribed as main speaker." (1790890932.000133); #audio-multimodal-general, 2026-10-02, started by a tutor: "Could QA clarify this case: How much overlap is allowed before the transcription fails the rubric?" (1790941015.000132)

## Spoken vs transcript number mismatch

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Task check: Voice says thirteen but subtitle says thirty." (1790875184.000139); #audio-multimodal-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790904522.000135)

## Suggestive but non-explicit sexual content labeling

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Where is the line between romance and explicit?" (1790908277.000054); #safety-classification-qa, 2026-10-02, started by a QA tutor: "The scene implies intimacy without describing anything graphic." (1790928681.000056)

## Team avatar asset location

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Does anyone know where the new team avatar image is saved?" (1790894591.000100)

## Tie judgments when differences are only cosmetic

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a tutor: "How much improvement do we need to avoid a tie?" (1790896509.000047); #response-preference-general, 2026-10-02, started by a tutor: "Anyone else seeing this?" (1790931693.000046)

## Timestamp alignment for defect review

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-02, started by a tutor: "Same background pop got minor on one task and major on another." (1790929125.000118)

## Transcript-audio correspondence mismatch

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-01, started by a QA tutor: "Transcript includes words the voice never said." (1790868669.000136); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: Transcript shows a sentence that never appears in the recording." (1790881507.000137); #audio-multimodal-general, 2026-10-02, started by a tutor: "Should we score omissions in the audio or errors in the transcript field?" (1790909920.000138)

## Unassigned members of routed_078eac1f314717c8 (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Could QA clarify this case: Waveform loads but play button never starts the recording." (1790903186.000110); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: The player stays on the spinner after the task opens." (1790916069.000107); #audio-multimodal-general, 2026-10-02, started by a QA tutor: "Task check: Getting a blank player on three items; can I safely continue tasking?" (1790919653.000113); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: Waveform loads but play button never starts the recording." (1790941945.000105)

## Unassigned members of routed_34ce720e5f5e0e9c (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Reminder: the response preference queue closes at 6 PM today." (1790880012.001400)

## Unassigned members of routed_5250e4c7e8be39ff (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Anyone else seeing this?" (1790866887.000147); #multilingual-eval-general, 2026-10-02, started by a tutor: "User code-switched; should response mirror it?" (1790927651.000146)

## Unassigned members of routed_85273db92619399f (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "QA is reversing ties even when both outputs fail the same criteria." (1790900625.000037)

## Unassigned members of routed_95b8994f22c3e9f2 (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Output pretends to ignore policies — category?" (1790889905.000065); #safety-classification-general, 2026-10-02, started by a tutor: "Issue: Is roleplay jailbreak wording automatically unsafe?" (1790911054.000066)

## Unassigned members of routed_da2c4022a3982758 (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "A linked a real report but the paragraph doesn't back up its claim." (1790885271.000007); #response-preference-general, 2026-10-02, started by a tutor: "Cited source exists, but does not support claim." (1790934787.000008)

## Unassigned members of routed_f804343968537534 (projection gap; no Agent 2 topic)

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 2 earlier review flags are still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a tutor: "The preference choice saves locally but I never see the task complete." (1790902754.000032)

## Unfindable or non-existent references

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #response-preference-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790911139.000011); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790927811.000013)

## Unsupported system override claims

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #safety-classification-general, 2026-10-02, started by a tutor: "Is a fake 'system override' message itself a category trigger?" (1790929933.000067)

## Vietnamese character rendering in LT

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-general, 2026-10-02, started by a tutor: "Task check: Vietnamese tone marks break in the viewer." (1790918003.000167)

## Vietnamese regional wording alignment

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- 1 earlier review flag is still open on these threads.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Is this northern wording acceptable for southern users?" (1790857852.000186); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Regional phrase sounds fine in VN but QA flags it." (1790869911.000187); #multilingual-eval-general, 2026-10-02, started by a tutor: "Vietnamese wording is natural in the south, but QA reviewer is from the north." (1790905292.000185); #multilingual-eval-general, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790924170.000183)

## Work environment and background noise

Needs Review - severity unknown (unassessed), unknown - SCRIPTED_PLACEHOLDER

**What happened.** The advisor's summary is not shown because the evidence did not support it; see the related threads.

**Still needs review:**
- The advisor's confidence is low.
- Some advisor statements were not supported by the evidence and are not shown.
- Research on current guidance was not completed.
- Research on announcements was not completed.
- Research on earlier decisions and their outcomes was not completed.
- Research on members' questions was not completed.
- Some evidence the advisor needed is missing.
- Severity could not be established from the supported evidence.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Finally got a quieter room to work from — what a difference 😄" (1790856028.000143)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 0, blocked 0; input 0, output 0 tokens; charged $0.0000.

