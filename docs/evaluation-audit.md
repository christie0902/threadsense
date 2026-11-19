# Evaluation audit

An audit of ThreadSense's evaluation evidence. First pass 2026-11-15; reviewed, corrected and extended 2026-11-16. **No
paid model calls** were made. Every figure was recomputed from saved artifacts or rerun offline; commands and results
are at the end.

**Revisions.** The historical results describe commit `a3fc977` (tree `50d6ab6c`, pushed). The fixes in this audit are
uncommitted changes on top of it (14 files, listed under [Fixes](#fixes-verified-in-this-audit)). All results were
produced in the original checkout (Windows 10, Python 3.13, `D:\Christie\…\threadsense`):

- *after fix*: the first fixed working tree (before the count assertions and the scope test); its full-suite result is
  1,284 passed, original checkout.
- *final*: **tested tree `0895083e`** (`a3fc977` plus all 14 changed files, this report excluded). The final working
  tree, `77d953ba`, differs from it only in two README lines (the guardrail count, 66 → 67), changed after the tests ran.

No fresh-clone run was made after the fix; the clean-clone breakdown below is for `a3fc977`.

| Label | Meaning |
| --- | --- |
| Automated regression test | a pytest or Playwright test in this repository; offline, model calls mocked |
| Offline benchmark | a scored evaluation over fixed cases, rerun locally with no model calls |
| Live model run | a saved run made with real model calls; re-read here, not re-run |
| Prepared decision | a judgment a developer wrote into a run in place of a model call (`PREPARED_AUDIT`) |
| Developer review | a developer's hand reading of the source threads for this audit; not confirmed by a Team Lead |

Workflow counts (how much moved through the system) and accuracy metrics (how often it was right) are in separate
tables. Several accuracy figures compare against the dataset generator's labels (`data/evaluation/thread_blueprint_200.json`),
which record design intent, not human-validated truth.

## Fixes verified in this audit

| Fix | Scenario | Before | After | Evidence |
| --- | --- | --- | --- | --- |
| Withheld statement text no longer served | fictional-contact card `card_a03615c8…` and every card of the accepted briefing | The card-detail API (`details.diagnostics[*].text`, printed raw by the *Technical* tab) and the feedback targets (`targets.statements[*].text`) returned every withheld statement verbatim: 46 withheld statements on 26 cards; the static demo bundle, built from the same API, held all 27 distinct withheld-only texts, as does the hosted demo today | The API returns a withheld statement's ID, kind, verdict, recorded reason and `withheld_because`, with `text: null, text_withheld: true`. Feedback history, the feedback POST response and the stale-head error response drop a withheld target's `earlier_text`. 0 of 26 cards serve withheld text; the rebuilt bundle and `dist-demo` hold 0 of 27. The stored feedback report and the saved run files keep the text (audit, replay, later reviewer context) | `src/threadsense/dashboard/disclosure.py` (shared boundary used by `app.py` and `feedback.py`); `tests/test_withheld_disclosure.py` (4 of its 6 tests fail with the `a3fc977` API, all pass after); `web/demo-tests/demo.spec.js` ("withheld statements stay off the page") |
| Regression checks assert both counts | the two disclosure counts below | the per-card API test checked every withheld statement but did not assert how many; no test checked the 27 withheld-only texts against the bundle (only 3 snippets in Playwright and the fictional-contact card in pytest) | the per-card test asserts 26 cards and 46 (card, statement) pairs with 0 served; a new bundle test asserts 37 distinct texts, 10 shown elsewhere, 27 withheld-only, 0 in the bundle. It fails on the `a3fc977` bundle and passes on the rebuilt one | `tests/test_withheld_disclosure.py` (`test_no_card_of_the_accepted_briefing_serves_a_withheld_statement`, `test_static_demo_bundle_holds_none_of_the_27_withheld_only_texts`) |
| Audit correction: escalation scope on a mixed topic | `card_6f0643a3c9edc5ff136705387a4615b1` | the first version of this audit said the card's engineering escalation "fits only the buffering thread", implying it was over-applied | verified from the saved card: the action is scoped to the buffering thread in a judged scope clause; no correction is needed and none was made. A regression test now pins the scope (details under [Mixed clusters](#seven-mixed-clusters-agent-2-left-together)) | `tests/test_accepted_briefing_guardrails.py::test_a_mixed_topic_escalation_is_scoped_to_the_thread_it_fits` |
| Review panel names the real reason | `summary:s2` on the same card: SUPPORTED, withheld because it depends on `claim:c5` | "Summary, sentence 2: not shown, because supported." | "… because it depends on another withheld statement (finding (source fact))" | `src/threadsense/dashboard/review.py` (`_depends`); asserted in `tests/test_withheld_disclosure.py` |

Unchanged on purpose: the frozen run files, and the stored feedback rows (a false-rejection correction needs the
original text in a later run's reviewer context, which is model input, not a reviewer view). The Feedback form now
lists a withheld statement as "text withheld from the card", which the local demo store mirrors.

### What the two disclosure counts mean

| Count | Definition | Value | Checked by |
| --- | --- | --- | --- |
| Withheld statements | (card, statement) pairs kept off a card: verdict other than SUPPORTED, or recorded as depending on a withheld statement. Every one also appears in the advisor's diagnostics | 46 on 26 cards: 24 PARTIALLY_SUPPORTED, 15 UNSUPPORTED, 2 NO_INTERVENTION_NEED, 2 SUPPORTED but dependent, 3 deterministic rejections | per-card API test (all 46, each in its own card's detail and feedback responses); `audit_evaluation_evidence.py disclosure` |
| Distinct withheld texts | the 46 statements' texts, deduplicated (5 texts repeat across cards) | 37 | bundle test |
| Withheld-only texts | distinct withheld texts that are not also a shown, supported statement on some card. The other 10 are templated sentences such as "U008 reports, in their own cited message, being affected by this problem", shown on other cards as supported claims about those cards | 27 | bundle test (whole `web/demo/briefing.json`); `audit_evaluation_evidence.py disclosure [--bundle=<path>]`; Playwright checks 3 of them on the rendered page |

The per-card test cannot use the bundle-wide rule (a templated sentence legitimately appears on another card), and the
bundle test cannot use the per-card rule (the bundle is one file), so both are needed.

**Hosted demo: not redeployed.** A signed-out read of `https://threadsense-snowy.vercel.app` on 2026-11-16, after the
fix, still found the pre-fix build: `assets/index-Dp2h-4yv.js`, `demoApi-BNEm7p0C.js` and `briefing-C3I1lpQv.json`
(sha256 `aa66a5e8974190ff`, identical to `web/demo/briefing.json` at `a3fc977`), holding 27 of 27 withheld-only
texts. The post-redeploy check could therefore not be run. After a redeploy from the fixed commit: download the served
`briefing-*.json` (named in the served `demoApi-*.js`), run `scripts/audit_evaluation_evidence.py disclosure
--bundle=<file>` (expect 0) and compare its sha256 with `web/demo/briefing.json` (`5c26be86d424caa9`); then open the
fictional-contact card's *Technical* tab and confirm it shows `"text_withheld": true` and none of the withheld text.
(Since the 2026-11-19 QA fixes the bundle has been regenerated, so compare with the current file's sha256, and the
*Technical* tab appears only after switching on Developer details in the footer.)

## Priority checks

| # | Scenario | Run or fixture | n | Expected | Observed | Evidence | Label |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1a | Top-five retrieval, development set | `data/evaluation/agent3_retrieval_cases.json`, index `.index/retrieval` (cutoff 2026-10-02) | 10 cases: 9 answerable (19 relevant sources), 1 unanswerable | every relevant source in the top 5; no must-exclude source | production ranking (hybrid + MMR): recall 1.0 (19/19), 9/9 cases fully recalled, must-exclude 0/1, near-match distractors in the top 5: 4 results in 3 cases (13 labelled). BM25 alone 0.796, dense alone 0.926 | `scripts/evaluate_retrieval.py`; `tests/test_retrieval_integration.py` | offline benchmark + automated regression test |
| 1b | Top-five retrieval, holdout set | `data/evaluation/agent3_retrieval_holdout.json` | 2 answerable cases (6 relevant sources) | same | recall 1.0 (6/6), 0 near-matches (3 labelled). No must-exclude source is labelled, so that check is empty here | same, `--holdout` | offline benchmark |
| 2 | Six-thread audio split | live run, Agent 2, `cluster_4460290131b816bb` | 6 threads | split by underlying issue; no thread lost; flags carried | "Transcript and audio content mismatch" (`C_AUDIO_GENERAL` 1790881507.000137, 1790904522.000135, 1790909920.000138; `C_AUDIO_QA` 1790868669.000136) and "Overlapping or background speech affecting transcription" (`C_AUDIO_GENERAL` 1790890932.000133, 1790941015.000132): 4 + 2, matching the generator's labels 6/6. Exact partition, 0 rejected or unassigned. Both flagged threads (1790890932.000133, 1790904522.000135) keep their flags on active cards and are in the review queue | `data/experiments/threadsense_full_v1/stages/agent2/agent2_v1/records/cluster_4460290131b816bb/result.json` | live model run (re-read) |
| 2b | Silent clip versus player failure (the presentation example) | Agent 2 and the consolidation stage of the accepted briefing | 3 Agent 2 clusters, 2 consolidation decisions | — | **A different case from row 2.** Clustering had already put the threads apart: "LT player fails to load audio" (5 threads) and "Waveform loads but playback will not start" (3) from `cluster_3a9de1cf4cf6b8d4`, "Silent audio handling" (3) from `cluster_7b875e31f162f4f3`, and the mixed "Audio clip playback verification" (2: 1790911816.000129 silent, 1790924545.000108 buffering) from `cluster_e6a79dfad226e738`. At consolidation, sets `cand_d173932bd13d` and `cand_674e589e8b59` were judged DISTINCT ("tool failure versus output content") by **prepared decisions**, not by the model | `data/experiments/threadsense_full_v1_combined_v2/consolidation.json` | live model run (Agent 2) + prepared decision |
| 3 | Fictional-contact grounding | `card_a03615c8bc678a84c906d5831a4ba1b0`, accepted briefing, from the live refresh | 41 statements in the final grounding | unsupported text kept off the card; card stays in review | The live grounding request judged **40** statements (39 SUPPORTED, 1 UNSUPPORTED: the "observe" alternative). The 41st, `claim:c5`, was rejected **before the request** by a deterministic check (`REJECTED_SOURCE_FACT_PRESENTS_HISTORY_AS_CURRENT`). Withheld from the card: those 2 plus `summary:s2` (SUPPORTED, but depends on `claim:c5`) = 3. Card: Needs Review, reasons HIGH_SEVERITY, INHERITED_FLAG, TEMPORAL_CONFLICT, GROUNDING_FAILURE, confidence 0.94 | `data/experiments/threadsense_full_v1_combined_v2/topics/consolidated__consolidated_1eef9f984ee99bde.json` (identical statement list in `…_consolidated_refresh_v1`) | live model run + automated check |
| 3b | Zero-call replay of that card | `…_consolidated_refresh_v1`, work `consolidated:consolidated_1eef9f984ee99bde` | 41 statements | same verdicts, same card | 0 model calls; the deterministic check rejected `claim:c5` again; the other 40 recorded model verdicts were reused (40 = every statement the model judged), 0 changed, 0 pending; grounding FAILED as recorded; same action `UPDATE_DOCUMENTATION` and 4 reasons. Limits: this replays the recorded model outputs under today's checks, it does not re-judge; the ToT controller differs (v1 not recorded, v2 now) and still picks the incumbent action; it runs only in the original checkout | `scripts/replay_overnight_topic.py` | offline replay |
| 4a | Observation with a supported no-action reason | accepted briefing | 3 Observation cards | Observation needs `action:no_action` SUPPORTED | 3/3 SUPPORTED, no review reasons ("Suggestive vs explicit content boundary", "Queue coverage and closure reminders", "Work environment and background noise") | `tests/test_briefing_policy.py`, `tests/test_accepted_briefing_guardrails.py` | automated regression test over saved live cards |
| 4b | Withheld recommendation keeps its follow-up | accepted briefing | 2 cards | no action; Needs Review; open step kept | 2/2: "Japanese honorific consistency review" (THREAD_STILL_OPEN), "Korean language QA edge cases" (WAITING_ON_REQUESTED_STEP), both from supported statements | same tests | automated regression test over saved live cards |
| 5 | Unavailable audit | live run, Agent 1 verification | 177 threads | an unavailable or invalid audit never passes; the thread is kept | 12 threads: 12/12 NEEDS_REVIEW, 12/12 in the briefing's review queue. The one Agent 1 rejection (1790866887.000147, `AUTHORITY_INELIGIBLE`) is recorded as unfinished work | `…/agent1_verify/agent1_verified_v2/interpretations.json`, `…/threadsense_full_v1/final/run_summary.json`; `tests/guardrails.txt` | live model run (re-read) + automated regression test |
| 6 | Request limits | live run ledger and per-item budgets | 947 ledger rows | no item over its limit; no charge over its reservation; run under its ceiling | see [Cost and request scope](#cost-and-request-scope): 0 errors, all HTTP 200, 0 charges above reservation; Agent 1 max 4 verification calls per thread (limit 4); Agent 3 max 4 model calls (limit 4) and 5 retrievals (limit 6) per topic; 0 topics over a limit | `data/experiments/threadsense_full_v1/ledger.sqlite3`, `…/stages/agent3/overnight_run/topics/*.json` | live model run (re-read) + automated regression test |

`claim:c5` is itself a **deterministic false rejection**: the sentence calls the help-page section "superseded", but
the present-tense pattern (`PRESENT_HANDLING` in `agents/advisor_checks.py`) matched "the **current** FAQ". It errs
towards withholding. Changing the check would change how every recorded run replays, so it is recorded here, not fixed.

## Metric definitions

| Metric | Numerator | Denominator | Labels from |
| --- | --- | --- | --- |
| Topic purity | threads whose label is the most common label in their Agent 2 topic | all threads Agent 2 placed in a topic (177) | generator `latent_topic` |
| Fully pure topics | topics whose threads all share one label | Agent 2 topics (81) | same |
| Full separation of mixed clusters | clusters with 2+ labels where every resulting topic has one label | clusters with 2+ labels (10) | same |
| Exact resolution agreement | threads where Agent 1's `resolution_state` equals the label | threads Agent 1 verified (177) | generator `resolution_state` |
| Recall@5 | labelled relevant sources in the top 5, averaged over answerable cases | answerable cases (9 dev, 2 holdout) | hand-written retrieval cases |
| Must-exclude violation | a source the case says must never appear (for example a superseded rule before its replacement) is in the top 5 | labelled must-exclude sources (1 dev, 0 holdout) | same |
| Near-match distractor | a labelled plausible-but-wrong source in the top 5 (counted, not a failure) | labelled distractors (13 dev, 3 holdout) | same |

Purity does not penalise over-splitting: two single-label clusters were split by Agent 2 (`cluster_3a9de1cf4cf6b8d4`
into the two player topics above; `cluster_839fecb69ec3fa12` into "Unfindable or non-existent references" and
"Misattributed DOI citations"). Neither split has been reviewed.

## Accuracy metrics

| Metric | Result | n | Compared against | Label |
| --- | --- | --- | --- | --- |
| Retrieval recall@5, production ranking | dev 1.0 (9/9 cases); holdout 1.0 (2/2) | 9 + 2 answerable cases | hand-labelled sources | offline benchmark |
| Agent 2 topic purity | 170/177 threads (0.96); 74/81 topics fully pure; clustering alone 165/177 | 177 threads | generator labels | live model run vs generator labels |
| Agent 2 full separation of mixed clusters | 3/10 | 10 clusters | generator labels | same |
| Agent 2 mixed clusters, developer review | of the 7 left together: 3 need separate investigations, 2 can share a topic, 2 ambiguous | 7 clusters | source threads | developer review |
| Agent 1 exact resolution agreement | 122/177 (0.69); 45 more open than the label, 10 more resolved | 177 threads | generator labels | live model run vs generator labels |
| Agent 1 over-resolution, developer review | of the 10: 3 supported by the source, 5 over-resolved (4 flagged NEEDS_REVIEW and queued), 2 ambiguous | 10 threads | source threads | developer review |
| Temporal reasoning (policy-aligned) | 17/17 joint, 0 false overrides | 17 cases | written expected outcomes | offline benchmark (prepared judgments) |
| Temporal reasoning (original labels) | 14/15 joint, 0 false overrides | 15 cases | written expected outcomes | offline benchmark (prepared judgments) |
| End-to-end card check | action in the proposed set 8/8; required review reasons 8/8; 0 unsupported claims displayed; 1 unnecessary review | 8 work items | expectations frozen before the run | live model run + manual audit (`data/experiments/agent3_e2e_eval_v1/evaluation.json`) |

The temporal benchmarks use prepared judgments, so they test the version and enactment rules, not the model; the two
sets are different datasets and not comparable.

## Workflow counts (not accuracy)

| Count | Value | Evidence |
| --- | --- | --- |
| Accepted briefing | 63 active cards: 52 Needs Review, 8 Recommended, 3 Observation; 37 review-queue items; 177 threads (174 on active cards, 3 in processing history) | `data/experiments/threadsense_full_v1_combined_v2/presentation.json` |
| Live run | 177 of 178 threads accepted; 76 groups, 81 topics, 81 cards before the offline briefing steps | `data/experiments/threadsense_full_v1/ACCEPTANCE.md` |
| Scripted offline run | 87 work items of the earlier pilot handoff, 87 cards, 52 queue items | `data/experiments/agent3_overnight_offline_v2/` |
| Withheld statements, accepted briefing | 46 statements on 26 cards (27 distinct texts not shown anywhere as a supported statement) | `scripts/audit_evaluation_evidence.py disclosure` |

### Cost and request scope

| Run | Requests | Charged | Notes |
| --- | --- | --- | --- |
| `threadsense_full_v1` (live run) | 937 settled fresh requests + 10 reused rows = 947 ledger rows | $15.317308 of a $39 ceiling | the 10 reused rows are Agent 1 verification responses from an earlier run, $0. By stage: Agent 1 interpretation 178 ($0.055), verification 496 + 10 reused ($3.671), Agent 2 76 ($0.307), Agent 3 187 ($11.284). The 506 Agent 1 verification call files (8 threads × 1, 79 × 2, 20 × 3, 70 × 4) equal 496 + 10 |
| `threadsense_full_v1_consolidated_refresh_v1` | 32 | $2.228018 of a $4.00 cap | the 14 consolidated issues; the fictional-contact card took 3 requests, $0.227092 |
| `agent3_reground_v1` | 2 | $0.094422 ($0.043068 + $0.051354) | two cards re-grounded after wording edits |

The $15.32 figure covers the live run only. The accepted briefing also depends on the refresh and the re-ground:
$17.64 of live calls in total. The $39 ceiling applies to the live run alone; the refresh ran under its own recorded cap
(`cost_limit_usd` 4.00 in its manifest) and the re-ground under $0.42 reserved.

## Developer reviews

### Ten threads Agent 1 marked more resolved than the label

Method: each thread was read from `data/fixtures/slack_generated_demo/channels/` and judged before opening the model's
result or the label (only the fact that three were marked "resolved in thread" was known). Authority follows the
pipeline's rule: a Team Lead message, or a tutor or QA tutor reply endorsed by a Team Lead `this`, `agree` or
`white_check_mark` reaction; an evidence request is not an answer.

| Thread | What carries authority | Evidence supports | Agent 1 | Label | Result | Downstream |
| --- | --- | --- | --- | --- | --- | --- |
| `C_RP_GENERAL` 1790869452.000006 | TL reply .000113 (U001): "For this example … record that the citation cannot be verified" | resolved for this case | RESOLVED | PARTIAL | supported (case scope; the label counts the open general FAQ) | VERIFIED; card in Needs Review |
| `C_RP_QA` 1790915967.000043 | QA tutor reply 1790916012.000113, TL `this`: follow "the clarification stated in this thread" while documents are reconciled | partial: rules out the old screenshot; the clarification it points to is not in the thread | RESOLVED | UNRESOLVED | over-resolved | VERIFIED, not queued; its card (`card_2b05a096`) is Needs Review and says the decision is withheld |
| `C_AUDIO_GENERAL` 1790909920.000138 | QA tutor reply 1790910023.000226, TL `this`: "For this item, record a transcript/audio correspondence error" | resolved for this item | RESOLVED | PARTIAL | supported (case scope) | CORRECTED; card in Needs Review |
| `C_SAFETY_GENERAL` 1790862407.000075 | QA tutor reply 1790862465.000113, TL `agree`: "follow the clarification posted in this thread"; documents still need reconciliation | the question (does the later announcement replace the older note?) is not answered | PARTIAL | UNRESOLVED | ambiguous | VERIFIED, not queued; Recommended card `card_7664fdc9`, which treats the question as open |
| `C_AUDIO_QA` 1790875184.000139 | none (tutor diagnosis .000113, no endorsement) | unresolved | PARTIAL | UNRESOLVED | over-resolved | NEEDS_REVIEW, queued |
| `C_SAFETY_QA` 1790934673.000061 | none (tutor opinion .000113; QA tutor evidence request .000226) | unresolved | PARTIAL | UNRESOLVED | over-resolved | NEEDS_REVIEW, queued |
| `C_MULTI_GENERAL` 1790891203.000155 | TL reply 1790891295.000226: register-consistency problem; scoring to language QA | partial | PARTIAL | UNRESOLVED | supported | VERIFIED; card in Needs Review |
| `C_MULTI_GENERAL` 1790924170.000183 | TL 1790924313.000339 asks which locale is targeted (an evidence request) | unresolved | PARTIAL, citing the TL request | UNRESOLVED | over-resolved | the verifier caught it: NEEDS_REVIEW, queued |
| `C_SAFETY_GENERAL` 1790917618.000080 | none (tutor claim .000113; QA tutor question .000226) | unresolved | PARTIAL | UNRESOLVED | over-resolved | NEEDS_REVIEW, queued |
| `C_SAFETY_GENERAL` 1790924588.000076 | QA tutor reply 1790924634.000113, TL `white_check_mark`: same deferral wording as above | "which rule applies" is not answered | PARTIAL | UNRESOLVED | ambiguous | VERIFIED, not queued; same Recommended card, which treats it as open |

Result: 3 supported, 5 over-resolved, 2 ambiguous. Four of the five over-resolutions were already flagged and queued;
the fifth sits on a Needs Review card whose text does not claim resolution. The two ambiguous threads share a pattern:
a Team Lead endorses a reply that defers to a "clarification posted in this thread" which the thread does not contain.
That is a semantic judgment, not a deterministic rule failure (the evidence-request rule worked on 1790924170.000183),
so no code was changed; it is kept for Team Lead validation. No card text in the briefing was found to depend on these
over-resolutions.

### Seven mixed clusters Agent 2 left together

| Cluster | Threads and labels | Agent 2 topic | Handling questions | Verdict |
| --- | --- | --- | --- | --- |
| `cluster_0368415e9aeeb3b5` | Korean register: `C_MULTI_GENERAL` 1790873677.000164, 1790932432.000161; Spanish usted/tú: `C_MULTI_QA` 1790907180.000181 | Register consistency across formality levels | same principle, but different language QA and different FAQ entries | separate investigations |
| `cluster_15fc8dea47088788` | queue-closure reminder `C_RP_GENERAL` 1790880012.001400; shift coverage 1790903659.000050 | Queue coverage and closure reminders | none; both routine notices (card is an Observation) | can share |
| `cluster_1dfb4570cf7196dc` | native-reviewer disagreement `C_MULTI_GENERAL` 1790867066.000173, 1790932821.000177; Korean register `C_MULTI_QA` 1790920494.000163 | Previous-discussion lookup for language-review disagreement | grouped by the shared phrase "can someone locate that discussion?"; locale choice versus register | separate investigations |
| `cluster_2667878314b97e76` | credible title linking to an unrelated paper `C_RP_GENERAL` 1790921874.000003; invented titles `C_RP_QA` 1790928958.000010 | Article title mismatch and fabrication review | whether the first is fabricated or mislinked is not established | ambiguous |
| `cluster_7e30e869d7c995fa` | Korean register `C_MULTI_GENERAL` 1790897091.000160; English paragraph in a Korean answer 1790932114.000145 | Korean language QA edge cases | same reviewer (Korean QA), different rules; the card keeps the two questions separate | can share |
| `cluster_95365133d3b8146a` | "fabricated" DOI that resolves to an unrelated article 1790920352.000014; real report not supporting the claim 1790937468.000009 (`C_RP_GENERAL`) | Task review for unsupported or mismatched sources | both "cited source does not support the claim"; the generator's split is debatable | ambiguous |
| `cluster_e6a79dfad226e738` | silent clip `C_AUDIO_GENERAL` 1790911816.000129; player stuck buffering 1790924545.000108 | Audio clip playback verification | output content versus tool failure | separate investigations; the card handles this correctly (below) |

**The escalation on `card_6f0643a3c9edc5ff136705387a4615b1` is correctly scoped** (checked against the saved card,
its grounding and the source thread). Its ESCALATE_ENGINEERING action covers the buffering thread only. Its evidence is
the four buffering-thread messages (1790924545.000108, .000113, .000226, .000339), two current sources and nothing from
the silent thread. Its `scope_note`, "This referral covers the buffering thread only, not the separate silence report",
is part of the judged `action` statement (SUPPORTED, sufficiency SUFFICIENT), and the dashboard shows it as "Applies
only as stated". The silent thread is described (claims c1 and c2, `detail:d1`) and stated as UNRESOLVED
(`resolution:member_97c81f2e6e5454c2f2a5ee4b`, SUPPORTED), with no action of its own. The card is Needs Review because
it is HIGH severity. It has no review-queue item, and the HIGH severity rests on the buffering reports. Since the
existing scoping already limits the action, the saved evidence supports no correction. The remaining gap is coverage:
the silent clip's own handling (verify a non-zero duration, then apply silent-audio handling) is not proposed by any
card. That needs Team Lead attention, not a change to this card.

The "7 of 10 unsplit" figure is therefore not an error rate: 3 of the 7 should split by this review. All seven cards
are Needs Review except the routine Observation.

### Unanswerable questions

Retrieval has no abstention: the unanswerable dev case still returns 5 results. Agent 3's handling was checked in the
saved negative control (`control_unsupported_payroll`, "What is the payroll deadline for contractors this month?") in
two live runs, `agent3_pilot_live_v1` and `agent3_acceptance_v1`: 5 nearest-neighbour results, one draft request, the
draft declared evidence UNSUPPORTED with 0 claims and no action, grounding was not run, and no card was produced. That
is n = 1 question, judged twice. A ranking cutoff or abstention redesign needs a broader held-out set first.

## Open findings

1. **Hosted demo still exposes withheld text** until it is redeployed (see [Fixes](#fixes-verified-in-this-audit)).
2. **Deterministic false rejection** of `claim:c5` (the `PRESENT_HANDLING` pattern); errs towards withholding.
3. **TL-endorsed deferrals** read as partial resolution (two ambiguous threads above); for Team Lead validation.
4. **Mixed topics** that should split: 3 clusters by developer review. On the silent-clip/buffering card the action is
   correctly scoped to one thread, but the silent clip gets no proposed next step.
5. **Retrieval has no "no answer" signal**; abstention is left to Agent 3 and measured on one question.
6. **Reproducibility limits**: a full replay with today's code stops at Agent 3, the fictional-contact replay runs only
   in the original checkout, and 10 tests depend on the checkout path.

## What we can claim in the presentation

- On synthetic data, ThreadSense turned 178 discussion threads into a 63-card briefing (52 Needs Review, 8
  Recommended, 3 Observation), with every thread and inherited review flag accounted for.
- The routing guardrails hold on the accepted briefing: all 21 HIGH-severity cards stay in review (even at confidence
  0.94); all 3 Observations rest on a supported no-action reason; both withheld recommendations keep their follow-up;
  all 12 unavailable audits went to review.
- Unsupported text stays off the card. On the fictional-contact card, the model judged 40 statements and a
  deterministic check rejected one more; 3 statements were withheld. After this audit's fix, withheld text is not
  served anywhere in the dashboard or the static demo (tested).
- Model use is bounded and audited: the live run spent $15.32 of a $39 ceiling with no item over its request limit;
  the accepted briefing used $17.64 of live calls in total.
- Retrieval found every labelled source in the top five on 9 development and 2 holdout queries, a small hand-made set.
- Agent 2 split the six-thread audio cluster along its two underlying issues; its topics agree with the generator's
  design labels for 96% of threads.

Avoid claiming: real-world accuracy; Team Lead validation; that the briefing is one untouched live run; that the
silent-clip versus player-failure separation was a model decision (it was prepared); that Agent 1's resolution states
are right beyond 69% agreement with generator labels; that retrieval can tell when nothing answers.

## Evaluation still needed

| Gap | Why it matters | What would establish it |
| --- | --- | --- |
| Human-labelled accuracy | every accuracy figure uses generator labels, small hand-made sets or developer review | a Team Lead labels a sample of cards (severity, action, resolution) blind to model output |
| Team Lead validation of the developer reviews | 2 ambiguous resolutions, 2 ambiguous clusters, 3 clusters judged to need splitting | a Team Lead reads the listed source IDs and confirms or overturns each verdict |
| Live accuracy at scale | live card checks cover 8–9 topics per evaluation | a capped live run over all work items, scored against frozen expectations |
| Retrieval and abstention at scale | 11 answerable queries; 1 must-exclude source; 1 unanswerable question | a larger held-out set with must-exclude and unanswerable queries and an abstention metric |
| Over-splitting | purity cannot see it; 2 single-label clusters were split | human review of those splits |
| Deterministic false rejections | `claim:c5` | a sample of deterministic rejections reviewed by hand; then a versioned fix with replay impact measured |
| Offline-only behaviour | Tree of Thought replacement, relevance verification and consolidation stages, unsupported-route rejection | a targeted live run with cases that trigger each one |

## Commands run and results

From the repository root of the original checkout; no `.env` needed; no model calls. *After fix* = `a3fc977` plus the
uncommitted changes listed above, 2026-11-16.

| Command | Revision | Result |
| --- | --- | --- |
| `uv run --locked python scripts/audit_evaluation_evidence.py` | final | all sections in about 5 s; reproduces rows 2–6, the metric tables, cost scope, disclosure counts (0 cards serving withheld text; bundle 0/27) and the negative control. Not reproduced by the script: the retrieval and temporal benchmarks (commands below) and the two developer reviews |
| `uv run --locked python scripts/evaluate_retrieval.py --summary-only` | after fix (index unchanged) | hybrid + MMR 1.0, 9/9 full recall, 0 must-exclude, 4 distractors; hybrid 1.0 (3 distractors); BM25 0.796; dense 0.926 |
| `uv run --locked python scripts/evaluate_retrieval.py --summary-only --holdout` | after fix | hybrid + MMR 1.0 (2/2), 0 distractors; hybrid 0.833; BM25 0.833; dense 0.667 |
| `uv run --locked python scripts/replay_overnight_topic.py --run data/experiments/threadsense_full_v1_consolidated_refresh_v1 --work consolidated:consolidated_1eef9f984ee99bde --write D:/tsb/replay_fc.json` | after fix | 0 model calls; 40 reused, 0 changed, 0 pending; grounding FAILED; `UPDATE_DOCUMENTATION`; same 4 reasons |
| `uv run --locked python scripts/evaluate_temporal.py --golden data/evaluation/temporal_golden_policy_v1.json` | `a3fc977` (2026-11-15) | 17/17 joint, 0 false overrides |
| `uv run --locked python scripts/evaluate_temporal.py --golden data/evaluation/temporal_golden.json` | `a3fc977` (2026-11-15) | 14/15 joint (T02), 0 false overrides |
| `uv run --locked --extra dev python -m pytest -q --basetemp <new dir> tests/test_withheld_disclosure.py` | new tests with `app.py` and `feedback.py` reverted to `a3fc977` | 4 failed, 2 passed (the leak) |
| same | after fix, before the bundle rebuild | 5 passed, 1 failed (stale bundle) |
| `uv run --locked python scripts/build_web_demo_data.py --write web/demo/briefing.json` | after fix | 991 responses (985 × 200, 6 × 404); sha256 `5c26be86d424caa9` (was `aa66a5e8974190ff`) |
| `uv run --locked --extra dev python -m pytest -q --basetemp <new dir> tests/test_withheld_disclosure.py tests/test_web_demo_data.py tests/test_dashboard_review.py tests/test_dashboard.py tests/test_reviewer_feedback.py tests/test_accepted_briefing_guardrails.py` | after fix | 67 passed |
| `uv run --locked --extra dev python -m pytest -q -p no:cacheprovider --basetemp <new dir> @tests/guardrails.txt` | after fix (list now includes 3 disclosure tests) | 66 passed (63 passed at `a3fc977`) |
| same | final (the list includes the whole `test_accepted_briefing_guardrails.py` module, so the new scope test is in it) | 67 passed |
| `uv run --locked --extra dev python -m pytest -q -p no:cacheprovider --basetemp <new dir> tests/test_withheld_disclosure.py tests/test_accepted_briefing_guardrails.py tests/test_web_demo_data.py tests/test_reviewer_feedback.py tests/test_dashboard_review.py` | final | 39 passed |
| `test_static_demo_bundle_holds_none_of_the_27_withheld_only_texts` against the `a3fc977` bundle / the rebuilt bundle | final | fails / passes |
| `scripts/audit_evaluation_evidence.py disclosure --bundle=<hosted briefing-C3I1lpQv.json>` | hosted demo, 2026-11-16 | 27 withheld-only texts served (not redeployed) |
| `npm --prefix web run test:unit` | after fix | 11 passed |
| `npm --prefix web run build` then `npm --prefix web run test:ui` | after fix | 25 passed |
| `npm --prefix web run build:demo` then `npm --prefix web run test:demo` | after fix | 4 passed (new: withheld statements stay off the page, Technical tab included) |
| same | final | first run, made while the full pytest suite ran alongside: 3 passed, 1 failed (the existing "review changes persist … fresh browser starts clean"). Three reruns: 4 passed each. Recorded as a load-related flake; `dist-demo` 0 of 27; bundle sha256 `5c26be86d424caa9` unchanged |
| scan of `web/dist-demo` and of the hosted bundle for the 27 withheld-only texts | after fix / hosted | `dist-demo` 0 of 27; hosted demo 27 of 27 |
| `uv run --locked --extra dev python -m pytest -q --basetemp <new dir>` (full suite) | `a3fc977`, original checkout (2026-11-15) | 1,278 passed |
| same | `a3fc977`, fresh clone at another path (2026-11-15) | 1,268 passed, 8 failed, 2 errors (location-dependent) |
| same | after fix, **original checkout** (2026-11-16) | 1,284 passed (1,278 + the 6 new disclosure tests), 18 min |
| same | final tree `0895083e`, original checkout (2026-11-16) | 1,286 passed (adds the bundle-count test and the scope test), 16 min |

In a fresh clone at another path, build the index first with `scripts/build_retrieval_index.py --allow-download`; the
retrieval benchmark then gives the same result. The fictional-contact replay refuses there ("The recorded snapshot is
no longer the one at that path"), because announcement evidence IDs depend on the checkout path.
