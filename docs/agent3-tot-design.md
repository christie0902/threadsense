# Agent 3 Tree of Thought: design as implemented

Canonical description of the shallow Tree-of-Thought (ToT) option comparison inside the Agent 3 Advisor, as of
2026-11-08.

Code:
- `src/threadsense/agents/advisor_tot.py`: the production controller;
- `tot_policy.py`: the optional shadow policy;
- `advisor_contracts.py`: `CandidateAction`, `ToTComparison`;
- `advisor_pilot.py`: `advise`, `CrewAIClient`;
- `advisor_checks.py`: `statements`, `grounding_result`, `assemble_card`;
- `dashboard/runs.py`: `alternatives`, `action_candidate`;
- `dashboard/decisions.py`.

Status words used here:
- **Implemented** means present in code and covered by offline tests.
- **Observed live** means seen in a saved live run.
- **Proposed** means not implemented.

Versions: comparison contract `agent3-tot-comparison-v3`; prompt `advisor_tot.RULES` (fingerprinted as `tot_rules`);
controller `agent3-tot-controller-v2`; shadow policy `agent3-tot-shadow-partial-order-v1`; pilot
`agent3-advisor-pilot-v8`. Recorded v2 comparisons replay under their original `adopt` rule.

## 1. Where ToT runs

ToT is one step **inside one Advisor call** (`advisor_pilot.advise`). It is not a separate LangGraph node.

```
LangGraph (agents/overnight.py)                      Advisor, per work item (advisor_pilot.advise)
load_handoff -> extract_announcements ->             retrieval -> draft -> follow-up retrieval -> revision (<=1)
prepare_retrieval -> plan_work ->                    -> deterministic checks -> [ToT: compare -> validate -> select]
process_topic (loops once per work item) ----------> -> ONE final grounding call -> authorize -> fallback
-> validate_accounting -> aggregate -> persist       -> close-call check -> card assembly -> topic result JSON
                                                     -> [optional shadow ToT policy: record only]
```

The graph adds no model call of its own. It sequences work items, enforces the run budget, records failures without
dropping members or obligations, and persists. Earlier plans named an "optional ToT node"
([agent3-plan.md](agent3-plan.md), Milestone 5 row); the build kept ToT inside the Advisor so that it shares the
Advisor's evidence ledger, request budget and reserved grounding call.

**Triggers** (`advisor_tot.triggers`):
- TEMPORAL_CONFLICT: the pre-grounding temporal check is DETECTED.
- LOW_CONFIDENCE: draft confidence below `LOW_CONFIDENCE_BELOW` = 0.60.
- OPEN_CONFIRMATION.
- ACTION_CHOICE: a stated choice between at least two different action types, with evidence in the ledger, that
  includes the draft's own action.

Otherwise ToT records `NOT_TRIGGERED` and sends no request. ToT runs only if one model call stays reserved for the
final grounding (`reserve=1`; per-topic ceiling 4: draft, revision, ToT, grounding). If the call fails or would consume
the reserve, ToT records `UNAVAILABLE` and review reasons are unchanged.

## 2. Candidate tracking, stage by stage

| Stage | Code | What is carried | Identity |
|---|---|---|---|
| Generation | `compare`: one `tot` request (CrewAI "alternatives analyst" Agent) | 2-3 `CandidateAction`s: `candidate_id`, `action_type`, `instruction`, `draft_text`, `rationale`, `evidence_ids`, `intervention_need`, categorical ratings, `unresolved_assumptions`, `incumbent`. Also `preferred_candidate_id`, `close_call`, `decision`, comparison `rationale` | Model-assigned `candidate_id`. The contract requires distinct IDs, a preferred ID among them, at most one incumbent, and `decision CLOSE_CALL` to imply `close_call` |
| Validation | `check_candidates` (deterministic) | Adds `recorded_applicability` (from the ledger's recorded use, not the model's claim), `unknown_evidence_ids`, `premise_ids` (draft claims sharing the candidate's evidence), `issues`, `valid` | unchanged |
| Selection | `select` (v3) / `adopt` (v2) | A replacing candidate moves as a unit: exact text, evidence, premises, intervention need. Sets `tot.selected_candidate_id` | `selected_candidate_id` |
| Final grounding | `statements(..., alternatives=advisor_tot.alternatives(tot))`, one request | Every valid candidate except the selected one becomes statement `alternative:<candidate_id>`, judged on its own, with `alternative_sufficiency` | `alternative:<candidate_id>` |
| Attach verdicts | `finalize` | Per candidate: `grounding` (`NOT_PRESENTED_INVALID` if invalid) and `sufficiency`. Also `preferred_candidate_id` (model preferred and SUPPORTED, never on a close call), `grounded_candidate_ids`, `presentation` | unchanged |
| Fallback | `fallback` | When the draft action is withheld, the model's preferred candidate may replace it if it is operational, valid and issue-free, with SUPPORTED exact text and a passing sufficiency check. Never the incumbent or an exact duplicate of the withheld action; not on a close call or NO_INTERVENTION_NEED | `model_preferred_candidate_id` |
| Close call | `choice_after_grounding` | `status` (NOT_COMPARED / NOT_A_CLOSE_CALL / RESOLVED_BY_GROUNDING / UNRESOLVED) and `viable`. The card action is listed first as `CARD_ACTION` (`candidate_id: null`) | IDs for `TOT_CANDIDATE` options |
| Card link | `card_action_candidate` | `tot.card_action = {candidate_id, basis}`, basis SELECTED / FALLBACK / INCUMBENT / NOT_A_CANDIDATE / NO_CARD_ACTION. `tot.controller` names the controller rules | New runs save it; `Run.action_candidate` derives it for saved runs |
| Card | `assemble_card` | `recommended_action.source` DRAFT / TOT / TOT_FALLBACK; review reason "Unresolved action choice" (UNRESOLVED only); review note on a fallback | unchanged |
| Topic result | `topics/<work item>.json` | The whole `tot` record, `action_source`, `action_notes`, `drafts.initial` / `drafts.final`, grounding statements, `evidence_ledger`; `tot.shadow_policy` when the shadow is on | complete |
| Dashboard | `Run.alternatives`, `Run.action_candidate`, card details API | Alternatives with `candidate_id`, `relation`, `preferred_by_comparison` (never on a close call), `closely_matched`; `details.action_candidate` | `candidate_id` |
| TL decision | `decisions.build_decision` | `alternative_id`, `grounded_source SUPPORTED_ALTERNATIVE`, `advice_id = card_id:alternative_id`; otherwise `CARD_DRAFT` | Bound to `run_key#run_instance` + card. A CARD_DRAFT decision resolves through `action_candidate` |

**What the saved records preserve:**
- the selected candidate;
- every alternative;
- each candidate's issues (rejection reasons), its own verdict and its sufficiency check;
- the comparison decision and the model rationale;
- the post-grounding close-call status;
- the reason a candidate was not adopted (`action_notes`).

`candidate_id` is unique within one comparison, which belongs to one topic result and one card. Anything that refers
to a candidate across runs goes through the card (`card_id` plus run instance).

## 3. Production selection policy (default)

**Ratings are categorical; nothing is scored or aggregated.**

| Field | Values |
|---|---|
| `evidence_support`, `need_strength` | STRONG / PARTIAL / WEAK / NONE |
| `applicability` | CURRENT / HISTORICAL_ONLY / MIXED / UNCLEAR (checked against the ledger's recorded use) |
| `severity_fit` | FITS / PARTIAL / POOR / UNKNOWN |
| `temporal_scope` | CONSISTENT / ISSUE / UNCLEAR |
| `proportionality` | FITS / EXCESSIVE / INSUFFICIENT / UNCLEAR |
| `unresolved_assumptions` | free text |

The comparison model states a decision (KEEP_INCUMBENT / REPLACE_INCUMBENT / CLOSE_CALL). Deterministic gates then
apply, in order (`select`, v3):

1. `close_call` or decision CLOSE_CALL: keep the incumbent; alternatives stay reviewable.
2. No decision: keep the incumbent. v3 requires a decision; the field is optional only so v2 records validate.
3. KEEP_INCUMBENT: keep the incumbent.
4. REPLACE_INCUMBENT naming no candidate, or naming the incumbent: keep the incumbent, with a note.
5. REPLACE_INCUMBENT naming another candidate: replace before grounding, but only if:
   - the candidate is `valid` (no unknown evidence, no support claimed without evidence);
   - it has **no issue**. The issues are `APPLICABILITY_OVERSTATED`, `HISTORICAL_ONLY_SUPPORT`,
     `NO_INTERVENTION_NEED_STATED`, `INCUMBENT_NOT_VERBATIM`, and prose or display issues;
   - it shares evidence with at least one draft claim;
   - it passes the action contract. Candidates carry no documentation targets, so a documentation action can never be
     selected or used as a fallback.

   Otherwise keep the incumbent, recording the reason.

**Final grounding decides eligibility.** Nothing reaches the card unless the final grounding call judged that exact
text:
- A selected action is judged as `action`, with its premises and sufficiency.
- Every remaining valid candidate, a displaced incumbent included, is judged as `alternative:<id>`.
- A candidate is preferred only if it is the model's preference, judged SUPPORTED, and not a close call.
- The dashboard lists an alternative only when its text was SUPPORTED, its sufficiency check passed, it has no issue,
  and it is not the card action.
- Selecting NO_ACTION removes the operational action but leaves routing unchanged.

**Review reasons.** ToT never clears a review reason or obligation: inherited flags, temporal conflicts, open questions
and severity reviews stay as they are. It can **add** one. When a close call survives the final grounding,
`choice_after_grounding` lists the viable options:
- the card action;
- candidates that are valid and issue-free, with SUPPORTED text and a passing sufficiency check (NO_ACTION needs none).

If at least two **different action types** remain, the choice is UNRESOLVED. The card gets the review reason
"Unresolved action choice" (code OTHER) and goes to Needs Review. The dashboard heads the options "Closely matched
options (none preferred)", and the team lead picks one; a decision can start from an alternative (`alternative_id`).

These are not review reasons:
- a close call that grounding narrows to one action type (RESOLVED_BY_GROUNDING);
- same-type wordings;
- clear comparisons;
- ACTION_CHOICE alone.

## 4. Shadow selection policy (optional, `agent3-tot-shadow-partial-order-v1`)

Enable it with `advise(tot_shadow=True)`, or `run_agent3_overnight.py --tot-shadow`. It records `tot.shadow_policy`
and a `TOT_INCUMBENT_ISSUE` diagnostic per incumbent issue. The run manifest records `tot_shadow_policy`, so a resume
with a different setting is refused.

The shadow makes no request, and changes no card, routing or production selection (tested). Because production is the
default, every saved and demo artifact is unchanged.

**Scope.** It assesses only an **explicit proposed replacement**: a v3 REPLACE_INCUMBENT naming a non-incumbent
candidate when an incumbent exists. Close calls, keeps, missing decisions, inconsistent replacements and v2 records are
recorded as `SAME_AS_PRODUCTION`. The shadow never invents a challenger, never turns a close call into a preference,
and never replaces anything. For information, it also records how every unproposed candidate's ratings relate to the
incumbent's.

**Partial order, per dimension** (CHALLENGER_BETTER / INCUMBENT_BETTER / EQUAL / UNRESOLVED):

| Dimension | Rule |
|---|---|
| `evidence_support` | STRONG > PARTIAL > WEAK > NONE |
| `need_strength` | the same order, between two operational candidates only. Intervening versus observing (NO_ACTION) is UNRESOLVED: the final grounding of the incumbent's intervention need (`action:need`) settles it |
| `severity_fit` | FITS > PARTIAL > POOR; UNKNOWN is unresolved |
| `temporal_scope` | CONSISTENT > ISSUE; UNCLEAR is unresolved |
| `proportionality` | FITS beats EXCESSIVE and INSUFFICIENT. EXCESSIVE versus INSUFFICIENT is unresolved (different problems); UNCLEAR is unresolved; equal ratings are EQUAL |
| applicability | an **eligibility gate**, not a preference. The existing checks already bar historical-only support for an operational action (`HISTORICAL_ONLY_SUPPORT`) and claimed-current applicability the ledger does not record (`APPLICABILITY_OVERSTATED`). MIXED is not ranked below CURRENT |
| any rating missing | unresolved: it cannot show that a candidate is at least as good |

**Assessment of an explicit proposed replacement:**

| Assessment | Condition |
|---|---|
| INELIGIBLE | the existing validity, issue, premise or action-contract gates reject the challenger (production keeps the incumbent too) |
| TRADE_OFF | each candidate is better on at least one dimension |
| INSUFFICIENT_COMPARISON | otherwise, any unresolved dimension |
| CLEAR_ADVANTAGE | challenger better on at least one dimension, worse on none, nothing unresolved |
| INCUMBENT_ADVANTAGE | incumbent better on at least one, worse on none, nothing unresolved |
| RATING_TIE | no difference on any dimension |

The record keeps the supporting, opposing and unresolved dimensions with their reasons. It also keeps the model's
decision, preferred ID and prose rationale, so the model's preference stays visible. When the assessment is not
CLEAR_ADVANTAGE, `agrees_with_model` is false and a note says the preference would not stand on its own.

**Shadow outcome after the final grounding.** It uses the saved verdicts and the existing viability rules:

| Outcome | When |
|---|---|
| REPLACEMENT_STANDS | CLEAR_ADVANTAGE, and the selected challenger passed the final grounding |
| TL_CHOICE | not a clear advantage, and both actions are eligible with different action types: show both, neither preferred |
| INCUMBENT_KEPT | not a clear advantage, and both eligible with the same action type: no unresolved choice is created |
| SINGLE_ELIGIBLE_ACTION | only one action passed the final grounding; it stands, with no unresolved choice. Example: a highly rated challenger that grounding rejects |
| NO_ELIGIBLE_ACTION | neither action passed |
| PRODUCTION_ALSO_KEEPS | the challenger is ineligible |

An option the final grounding did not support is never offered. NO_ACTION needs no sufficiency check, as in production.

## 5. Why there is no numerical margin

A margin needs a scale, and there is none. The ratings are categorical, nothing aggregates them, and the earlier 0.10
figure was illustrative.

The saved live comparisons show why a scale should not simply be invented:
- In 4 of the 10 distinct live comparisons, an alternative of a different operational action type has ratings equal to
  the incumbent's.
- The model still chose between those options on prose grounds that the labels do not capture, such as breadth of
  communication and scheduling burden.
- In one refresh close call, the labels favour the alternative on `need_strength`, while the model called it a close
  call because of a breadth trade-off.

Mapping the labels to numbers would add weights no one has defined. It would also give the labels a resolution they do
not have.

Future scoring would require:
1. anchored criteria for each point on each dimension;
2. explicit weights agreed with team leads;
3. a set of TL-labelled comparisons (which option a team lead prefers, and whether the choice was close);
4. evidence that the chosen margin separates meaningful preferences from close calls on held-out labelled cases;
5. a new ToT contract version, since recorded comparisons have no scores.

Until then, the partial order is the most the existing ratings support.

## 6. Replay boundaries and fingerprints

Controller behaviour changes derived selections without changing any request, so the prompt fingerprint alone cannot
detect it:
- `advisor_tot.controller_fingerprint()` = `CONTROLLER_VERSION` plus the SHA-256 of the controller functions' source
  (line endings normalized).
- The overnight run manifest records it as `tot_controller`, and `tot_shadow_policy` when the shadow is on. A resume
  under other controller rules or another shadow setting is refused, so recorded selections are never reused under
  new rules.
- The full-pipeline configuration records `agent3_tot_controller`. `run_threadsense_full.py resume` refuses a changed
  configuration, as before.
- `replay` and `branch` record `rules_vs_parent` (SAME_RULES, or CHANGED_RULES with the differing keys) and print a
  "Rebuild under changed rules" line. Runs recorded before controller v2 lack the key, so a replay of them is labelled
  a rebuild.
- `scripts/replay_overnight_topic.py` reports the recorded and current controller and both card-action links.
- Each new comparison saves `tot.controller`. Records without it were made under controller v1 (before 2026-11-08).

**What a replay of an older run does.** The v2 controller differs from v1 only on paths no saved live run takes:
- a missing decision;
- an inconsistent REPLACE;
- a fallback to the incumbent;
- a close call carrying a preferred ID. This occurs only in four old offline v1/v2 records ("Repeated final line"),
  where a replay now reports no preferred candidate.

Dashboard alternatives for all 687 saved cards are byte-identical under both controllers. The accepted demo
(`threadsense_full_v1_combined_v2`) and the saved live runs are not regenerated.

## 7. Incumbent issues (audit of the saved live cases)

Four saved live incumbents carry `APPLICABILITY_OVERSTATED`. The comparison model labelled them CURRENT while the
ledger records MIXED or UNCLEAR. They are the two kept QN documentation fixes in the full run, the incumbent of the
"Conflicting guidance" close call, and the kept QN fix in the refresh.

`tot_policy.incumbent_issues` checks each against its saved premises, evidence and final verdicts, with no new verdict
and no relabelling. **All four are `LABEL_OVERSTATEMENT`:**
- the action passed the final grounding and sufficiency check;
- every essential premise is SUPPORTED and rests on current guidance, verified announcements or member reports, or is a
  HISTORY claim describing the stale help-page section as history;
- the non-current items the candidate cites are the documentation target (the superseded help page the fix corrects) or
  comparison context (a prior decision record that no essential premise uses);
- "Conflicting guidance" cites only member reports (recorded UNCLEAR), and its meeting action rests on those reports.

No review requirement is added for citing history. A `MATERIAL_CONCERN` would arise only if:
- an essential premise is not SUPPORTED;
- a guidance-type essential premise rests only on non-current evidence;
- the action failed its grounding or sufficiency check.

The affected premise is then named. With the shadow on, each disposition is saved as a `TOT_INCUMBENT_ISSUE`
diagnostic; the issue itself stays on the candidate in every run.

## 8. Framework responsibilities

| Layer | What it does here | What it does not do |
|---|---|---|
| **CrewAI** (`CrewAIClient`) | Runs each model stage as one `Task` for a role-specific `Agent` in a one-task `Crew`: researcher (draft, revision), alternatives analyst (ToT), grounding verifier (grounding). Settings: `tools=[]`, `max_iter=1`, `max_retry_limit=0`, `allow_delegation=False`, no memory or planning, `crewai.LLM` over LiteLLM. `RequestGuard` allows one HTTP request per stage | No tool calls, no delegation, no CrewAI memory, no retries. Candidate state is not CrewAI state |
| **LangGraph** (`overnight.build_graph`) | Sequential workflow over work items, with run-wide request and cost ceilings and failure isolation | No ToT node, no model call, no checkpointer. Resume uses the run's own artifacts |
| **Python validation** | Pydantic contracts, `check_candidates` against the evidence ledger, the controller gates, final-grounding authorization, card routing, and the shadow policy | No semantic judgment of its own: verdicts come only from the final grounding call |
| **Run artifacts** | Topic result JSON (full `tot` record, grounding, ledger, card), `cards.json`, `review_queue.json`, the run manifest (`tot_rules`, `tot_controller`, cutoff, inputs), the budget ledger, and the request cache for replay | Not a knowledge store; TL decisions live in the separate SQLite decision store |

**LangChain.** No ThreadSense module imports it. `langchain-core` 1.7.2 is installed only as a dependency of
`langgraph` 1.2.18. CrewAI calls models through LiteLLM.

**Why the existing records suffice.** The ToT is one level deep: one call proposes 2-3 complete candidates, with no
expansion, backtracking or search. Everything it needs fits in the topic result:
- the candidates with IDs;
- the evidence ledger every citation must resolve against;
- each candidate's verdict from the same grounding call that judges the card;
- the persisted run, which replays offline.

**MCP.** `mcp` 1.28.1 is installed only as a CrewAI dependency; nothing uses it. If external tools or resources were
exposed through MCP, they would sit behind `ResearchTools`: their results enter the evidence ledger under the same
budget and freshness checks, and candidates cite them like any other evidence. Models would still not call tools
directly.

## 9. Evidence: live versus prepared

| Path | Live evidence | Prepared-test coverage |
|---|---|---|
| Triggers TEMPORAL_CONFLICT, OPEN_CONFIRMATION | yes (full run 5 + 3; refresh 2 temporal) | yes |
| Triggers LOW_CONFIDENCE, ACTION_CHOICE | no | yes |
| KEEP_INCUMBENT | 7 distinct comparisons | yes |
| Close call: RESOLVED_BY_GROUNDING / UNRESOLVED | 2 / 1 distinct ("NSFW" is UNRESOLVED) | yes |
| REPLACE_INCUMBENT selection | **none** | yes (`test_agent3_tot_v3.py`) |
| ToT fallback | **none** | yes (`test_agent3_corrections.py`, `test_agent3_tot_linkage.py`) |
| Shadow policy on an explicit replacement | **none** (0 of 10 distinct live comparisons proposed one) | yes (`test_agent3_tot_shadow.py`) |
| Incumbent-issue dispositions | 4 live cases, all LABEL_OVERSTATEMENT | yes |

**Offline shadow evaluation:** `scripts/evaluate_tot_shadow.py`, report
`data/experiments/agent3_tot_shadow_eval_v1/report.json`.
- Inputs: the full run, its replay (8 copies deduplicated) and the refresh, giving 10 distinct comparisons.
- Model decisions: 7 KEEP_INCUMBENT, 3 CLOSE_CALL. Every shadow outcome is SAME_AS_PRODUCTION.
- Informational relations of the 18 unproposed candidates to their incumbent:

| Relation | Count |
|---|---|
| RATING_TIE (all different-type operational options) | 4 |
| INSUFFICIENT_COMPARISON (6 NO_ACTION, 1 unresolved proportionality) | 7 |
| INELIGIBLE (existing issues) | 5 |
| INCUMBENT_ADVANTAGE | 1 |
| CLEAR_ADVANTAGE (the refresh close call above, left as a close call) | 1 |

The live sample contains no proposed replacement, so it cannot show how well the replacement rule works in practice.
Prepared cases show the controller's behaviour, not model accuracy.

## 10. Checks

```sh
uv run --locked --extra dev python -m pytest tests/test_agent3_tot_shadow.py tests/test_agent3_tot_linkage.py \
  tests/test_agent3_tot_v3.py tests/test_agent3_policy_routing.py tests/test_agent3_corrections.py -q --basetemp D:/tsb/pytest-tot
uv run --locked python scripts/evaluate_tot_shadow.py            # zero calls; --write NEW_DIR to save the report
```
