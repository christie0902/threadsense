# Evaluation and results

What each stage produced, how it was checked and what is still open. All data is synthetic: four annotation
projects, 200 Slack threads (516 messages), plus a demo snapshot with one extra announcement (201 / 517, cutoff
2026-10-02T12:00:00Z). Saved runs live in `data/processed/` and `data/experiments/`; they are frozen.

Evidence levels used below:

| Level | Meaning |
| --- | --- |
| Live | observed in a saved run with real model calls |
| Offline | exercised by tests, prepared judgments or replays only |
| Audited | a developer judgment standing in for a model judgment |
| Fixture | hand-written synthetic data |

## Agent 1: interpretation and verification (v3)

Agent 1 summarises each thread, states its central question and checks the summary against the source.

| | |
| --- | --- |
| Threads | 200 processed, 0 unprocessed |
| Outcome | 81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW |
| Requests | 593 of 800 authorised |
| Output | `data/processed/agent1_verified_v3/interpretations.json` |

Verification combines a source analysis, a separate prose comparison and deterministic checks (schema, roles,
reactions, evidence). It allows one revision per thread, with at most four requests, no retries and no fallbacks. A
thread that still fails goes to NEEDS_REVIEW and does not stop the batch.

What the 12-record source review found:
- False acceptance, such as a "failed workaround" claimed where no attempt was established.
- Announcements turned into questions with invented resolutions.
- Evidence that was present but reported as missing.
- Information requests framed as decisions.

Lessons:
- One automatic revision catches a lot, but not everything: two false acceptances got through the 12-record sample.
- Announcements without a question were a recurring failure, which is why announcement channels are now routed to the
  knowledge store before interpretation (see [announcement-routing.md](announcement-routing.md)).
- The effective status (after human review) is tracked separately from the automated status.

## Agent 2: topic taxonomy (v7)

Agent 2 groups related interpretations and names the topics.

| | |
| --- | --- |
| Groups / topics | 90 groups, 97 topics |
| Identities | all 200 kept, with all 49 inherited Agent 1 review obligations |
| Requests | 86 new + 4 reused pilot results; 0 failed, interrupted or unprocessed groups |
| Open items | 3 non-blocking naming cautions |
| Output | `data/processed/agent2_taxonomy_final_v7/` (`effective_output_reviewed.json`, 41 review groups) |

How the scope changed:

| Versions | Task given to the model | Result |
| --- | --- | --- |
| v2–v3 | full consolidation with evidence quotes and provisional severity | complex, high validation failure rate |
| v4–v6 | source inventory, question tracking, confidence notes | better structure, but still confused complete and partial question scope |
| v7 | coherence check and topic naming only | reliable membership partitions; severity left UNKNOWN for Agent 3 |

The main lesson: structural checks (membership partitions, evidence IDs) are reliable; asking a model to re-interpret
Slack in a second stage added cost without a clear benefit.

Agent 3's pilot input is a zero-call projection of v7 into the newer handoff format
(`data/processed/agent2_handoff_v2_projection/`: 81 groups, 79 topics, 161 assigned + 17 unassigned members,
41 + 8 obligations, 3 cautions). Eight projected groups have no reusable taxonomy, so their 17 members stay
unassigned, and still accounted for, until a new Agent 2 run.

## Agent 3: research, severity and advice cards

Agent 3 researches each topic in the knowledge store and earlier decisions, assesses severity with the team-lead
rubric, and writes an advice card. Card text is shown only when the final grounding call judges it SUPPORTED;
anything else goes to Needs Review.

### Development runs

| Step | What changed | Evidence | Cost |
| --- | --- | --- | --- |
| Pilot | bounded CrewAI Advisor, six topics + negative control | offline (`agent3_pilot_offline_v2`), live (`agent3_pilot_live_v1`, 15 requests) | — |
| Model comparison | two models on the same topics | live (`agent3_model_comparison_v1`) | $0.40 |
| Acceptance | full pilot on the chosen model | live (`agent3_acceptance_v1`, 21 requests) | $1.07 |
| Closeout / readability | role-based card prose, team-lead-facing wording | live (`agent3_closeout_v1`, `agent3_readability_v1`) | $0.95 + $0.37 |
| Overnight workflow | LangGraph run over the whole handoff (87 items) | offline (`agent3_overnight_offline_v2`), live smoke (`agent3_overnight_smoke_v1`) | $0.53 |
| Decision loop | dashboard decisions reach later runs via a new snapshot | offline (`agent3_feedback_loop_offline_v1`) | — |
| Scenario evaluation | nine demo scenarios | live (`agent3_final_eval_v1`, 30 requests) | $1.56 |
| Policy repairs | enactment rules, close calls, source consistency, request kinds, routing rule | live (`agent3_repair_eval_v1` … `agent3_recipient_routing_v1`) | ≈ $2.31 total |
| Flag impact (opt-in shadow) | does a card depend on an inherited flag? | live (`agent3_flag_impact_live_v1`), routing unchanged | $0.37 |
| End-to-end check | eight items, expectations frozen before the run | live (`agent3_e2e_eval_v1`) | $0.93 |
| Presentation | "What happened" details, judged no-action reasons | live (`agent3_v18_acceptance_v1`, 16 requests) | $0.86 |

"—" means offline, or a cost not recorded in the run summary.

### Temporal benchmarks

| Benchmark | Cases | Result |
| --- | --- | --- |
| `data/evaluation/temporal_golden.json` | 15 | 14/15 (T02 expects an enacted decision the case does not record) |
| `data/evaluation/temporal_golden_policy_v1.json` | 17 | 17/17 (T02 split into one negative and two positive cases) |

These are different datasets; the scores are not comparable. Both use prepared judgments, so they test the
deterministic version and enactment logic, not model accuracy.

## Full pipeline run and demo baseline

`data/experiments/threadsense_full_v1/` is one live run from Slack to cards (2026-11-05): 937 requests, $15.32 of a
$39 ceiling. Agent 1 accepted 177 of 178 discussion threads, with one rejection recorded. The run produced 76 groups,
81 cards and 37 review-queue items, with complete accounting. A network-disabled replay reproduced all 89 artifacts.

The dashboard's default briefing, `threadsense_full_v1_combined_v2`, is built from that run in offline steps:

1. Briefing routing re-applied with audited relevance labels (`threadsense_full_v1_briefing_v2`).
2. Agent 1 relevance and Agent 2 consolidation rebuilt from audited labels and prepared merge decisions
   (`threadsense_full_v1_consolidated_v1`).
3. The 14 merged issues re-advised live (`threadsense_full_v1_consolidated_refresh_v1`, 32 requests, $2.23).
4. Two cards re-grounded live after wording edits (`agent3_reground_v1`, 2 requests, $0.09).
5. Everything combined, plus a presentation layer (`presentation.json`).

Result: 63 briefing items (52 Needs Review, 8 Recommended, 3 Observation), 177 threads and 37 review items. It is a
combination of live and audited steps, not a single untouched live run. See
[architecture/THREADSENSE_END_TO_END.md](architecture/THREADSENSE_END_TO_END.md) for the full lineage.

## Synthetic data notes

- The knowledge store (`data/knowledge/`, 40 Markdown files) is hand-written mock data. It deliberately includes a
  stale help page: the fictional-PII rule from August 20 is narrowed by a team-lead clarification on September 10, which
  the current instructions (v1.4) and FAQ (v1.1) reflect. This tests whether Agent 3 can tell a stale copy from current
  policy.
- The demo snapshot adds one audio announcement (October 1, 22:00 UTC) about unavailable playback. The original
  `data/fixtures/slack_generated/` is unchanged.
- No engineering tickets or completed interventions are invented: "recommend escalation" and "already escalated" stay
  different claims.

## Known limitations

- **Grounding is a model judgment.** It has both falsely and correctly rejected statements in live runs. Withheld text
  goes to Needs Review instead of being repaired.
- **Some behaviour has only offline evidence.** ToT replacement and fallback, the shadow ToT policy, the pipeline-v2
  live stages (relevance verification, consolidation) and rejection of unsupported routes have never run live.
- **Severity for rule-confusion topics is unsettled.** The same topic has received different levels across runs;
  this needs a rubric decision from the team leads.
- **Retrieval recall** still depends on the model's follow-up queries.
- **The dashboard has no authentication.** It runs on localhost, each session is fixed to one team lead, and approving
  a card records intent only; nothing is posted or executed.
- **Dataset check:** `scripts/validate_threadsense_dataset.py` reports thread `1790941015.000132` as unresolved in the
  blueprint although it has a team-lead approval. This is a fixture inconsistency, not a code failure.
