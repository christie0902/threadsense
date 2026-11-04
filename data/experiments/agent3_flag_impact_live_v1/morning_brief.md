# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

3 cards (NEEDS_REVIEW 3); 52 Model Review Queue items; 178 discussion members (11 on cards); 22 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 3 of 87 work items (84 out of scope; their members and review items are still accounted for).

## QA calibration on disputed tie decisions

Needs Review - severity high (assessed), mixed

**What happened.** Two QA tutors report ties marked wrong; one also reports that a tie score passed last week but was flagged on near-identical tasks today. In the RP-9595 thread, the team lead acknowledges inconsistent QA feedback and asks for both rationales before considering a change to the tie threshold. The current FAQ calls for comparing the pairs, prompt requirements and both rationales, without generalizing a decision beyond comparable cases.

**What to do: Schedule a short review session.** Arrange a review of the disputed tie decisions using the pairs, prompt requirements and both rationales once those inputs are collected.

**Why.** Comparing the same evidence against the current criterion can distinguish genuinely comparable cases from differences that justify different scores. The earlier batch's review improved agreement in its sample, but it does not establish the outcome for this batch.

**Draft to copy:**

> Please provide the disputed pairs, relevant prompt requirements and both QA rationales for a comparison of the decisions. Two QA tutors report ties marked wrong; one identifies RP-9595 and also reports a tie score passing last week but being flagged on near-identical tasks today. A tutor reports an accepted tie yesterday and a similar pair marked wrong today.
> 
> For each pair, explain any meaningful quality advantage and the user-facing benefit. Cosmetic phrasing alone does not justify a preference. We will check whether the cases are actually comparable rather than generalizing one pair's answer. For RP-9595, please provide both rationales as requested before we consider changing the tie threshold.

**Still needs review:**
- Check whether both rationales requested in the RP-9595 thread have arrived, together with the disputed pairs and relevant prompt requirements, before holding the comparison.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #response-preference-qa, 2026-10-01, started by a QA tutor: "QA marked my tie as wrong again." (1790866003.000036); #response-preference-qa, 2026-10-02, started by a QA tutor: "Anyone else seeing this?" (1790926534.000040); #response-preference-general, 2026-10-02, started by a QA tutor: "QA marked my tie as wrong again." (1790939595.000035)

Sources: response-preference-faq@1.1 (Ties and preferences); response-preference-instructions@1.1 (Ties); rp-tie-calibration-outcome@1.0 (Review receipt); rp-tie-calibration-outcome@1.0 (TL assessment); rp-tie-calibration-approval@1.0 (Context); rp-tie-calibration-post@1.0

## Repeated final line in exported audio

Needs Review - severity high (assessed), mixed

**What happened.** Five tutors and two QA tutors report repeated audio endings; two of the tutors explicitly report repetition in exported audio. Current instructions say to record where repetition occurs, compare the downloaded file with player output if feasible, and avoid calling it a confirmed generation defect before distinguishing generation from playback. An earlier review retained a similar report as an open observation because the diagnostic comparison was missing; that record shows no completed comparison or engineering escalation.

**What to do: Report a technical issue to engineering.** Report the repeated-ending problem to engineering for investigation, keeping exported-audio reports, transcript differences, and pending file-versus-player checks distinct.

**Why.** Several distinct reporters describe comparable repeated endings, including repetition in exported audio, so engineering can investigate beyond a player-only symptom. The earlier review lacked a diagnostic comparison; these reports support investigation, not a confirmed generation-defect announcement.

**Draft to copy:**

> Please investigate repeated endings in audio batch 06. Five tutors and two QA tutors report repeated audio endings, with overlapping details:
> - Two tutors explicitly report repetition in exported audio, not just playback.
> - Two tutors report doubled audio endings that are not doubled in the transcript.
> - A tutor reports the final line looping twice on AUDIO-9012, with no sign of a player glitch.
> - Two QA tutors report the last sentence spoken twice; one identifies AUDIO-3533.
> 
> Please assess whether these reports point to generation, playback, or another issue. Completed file-versus-player comparisons and exact repeated spans are not yet supplied in these threads. I am reporting symptoms for investigation, not a confirmed generation defect.

**Still needs review:**
- Collect the file-versus-player results requested in the first QA tutor's thread, the AUDIO-9012 thread, and the tutor's doubled-ending thread; also collect the repeated-word start point and transcript details requested in the AUDIO-3533 thread.
- Severity is high under the team rubric.
- 2 earlier review flags are still open on these threads.

Threads: #audio-multimodal-general, 2026-10-01, started by a QA tutor: "Issue: Model keeps saying the last sentence twice lol." (1790868894.000123); #audio-multimodal-general, 2026-10-01, started by a tutor: "Issue: TTS output repeats a line near the end." (1790889930.000126); #audio-multimodal-general, 2026-10-01, started by a tutor: "Anyone else seeing this?" (1790899012.002000); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio model keeps doubling the ending even though the transcript doesn't." (1790915994.000122); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Model keeps saying the last sentence twice lol." (1790923533.000125)

Sources: audio-multimodal-instructions@1.3 (Language and repeated audio); audio-multimodal-faq@1.1 (Scoring); audio-repeat-observation-review@1.0 (Evidence)

## Format adherence vs factual accuracy

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and a tutor ask how to weigh accuracy against output format; a second QA tutor asks whether prose is preferable when the prompt requested JSON on RP-3824. The current FAQ requires separate assessment of format violations and factual accuracy, without a universal rule for which wins. In the tutor's thread, the team lead requested the exact formatting instruction so QA can verify whether it was mandatory before weighing the responses.

**What to do: Post a reminder.** Post a reminder to assess format and factual accuracy separately and ask the thread starters to provide the prompt and both responses for any preference the actual pair and applicable guidance do not settle.

**Why.** The repeated questions concern choosing a winner, which separate dimension scores alone do not settle. The current FAQ gives a conditional review process; the earlier calibration outcome does not supply a general winner rule.

**Draft to copy:**

> For accuracy-versus-format questions, assess factual accuracy and instruction following separately, and identify whether the requested structure was mandatory. Required format is not optional, but there is no universal rule that accuracy or format always wins. If the actual pair and applicable guidance do not settle preference, please provide the prompt and both responses for my confirmation. This includes the JSON-versus-prose question on RP-3824. In the thread asking whether accuracy can outweigh output structure, please also provide the exact formatting instruction I requested so QA can verify whether it was mandatory before weighing the responses.

**Still needs review:**
- 1 earlier review flag is still open on these threads.

Threads: #response-preference-general, 2026-10-01, started by a QA tutor: "Could QA clarify this case: A follows format, B is more accurate." (1790856332.000018); #response-preference-qa, 2026-10-02, started by a QA tutor: "Prompt asked for a JSON object; B explains it beautifully in prose." (1790913824.000016); #response-preference-general, 2026-10-02, started by a tutor: "Can accuracy outweigh ignoring the user's requested output structure?" (1790932885.000015)

Sources: response-preference-faq@1.1 (Instruction following); rp-tie-calibration-outcome@1.0 (TL assessment)

## Model Review Queue

52 items (separate from the cards above):

- agent1 inherited_agent1_review: 41
- agent1 inherited_agent1_review_announcement_route: 8
- assisted_content_review assisted_content_review: 3

## Usage

Requests sent 6, blocked 0; input 81462, output 21109 tokens; charged $0.3740.

