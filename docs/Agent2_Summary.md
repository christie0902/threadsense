# Agent 2 — Compact Summary

**Final Status:** Closed with nonblocking review (Taxonomy v7, 2026-10-27)

## Results
- **90** groups → **97** topics
- **200** unique identities preserved | **516** source messages
- **49** inherited Agent 1 obligations retained
- **0** failed, interrupted, or unprocessed groups
- 86 new requests + 4 reused pilot results

## Development Map
| Phase | What Was Done | What Improved |
|-------|---------------|---------------|
| **1. Early Consolidation (v2–v3)** | Full factual consolidation with evidence quotes and provisional severity | Membership accounting and flag preservation established |
| **2. Inventory Experiments (v4–v6)** | Source inventory, question tracking, confidence/notes, low-reasoning and contrastive tests | Better structure and provisional handoffs; models still struggled with complete vs. partial scope |
| **3. Taxonomy Refocus (v7)** | Model task reduced to coherence check + topic naming only | Reliable membership partitions, simpler prompts, all severities correctly UNKNOWN |

## Evolution
| Stage | Focus | Outcome |
|-------|-------|---------|
| Early pilots (v2–v3) | Full consolidation + verification | Complex, high validation failure rate |
| Inventory versions (v4–v6) | Source inventory + question tracking | Improved structure, still interpretation-heavy |
| Taxonomy v7 | Coherence + topic naming only | Simplified, reliable membership partitions |

## Developer Notes from Experiments
- Inventory style (v4–v6) improved structure and question tracking, but models still struggled with complete vs. partial question scope, invented preference decisions, and treating diagnostic requests as answers. Structural checks could not decide entailment.
- Low-reasoning comparison (v5.2) improved some alignment cases but did not eliminate scope issues on the Audio cluster.
- Contrastive diagnostic (v5.3) and uncertainty notes (v6) helped surface provisional judgments, yet confidence scores still missed specific errors that source review later found.
- Taxonomy v7 was the successful refocus: the model only names topics and checks coherence. Membership partitions became reliable, and all 97 topics received UNKNOWN severity because the inputs lack structured impact signals.
- Provisional acceptance policy (v6) allowed plausible interpretations with explicit uncertainty to proceed, reducing unnecessary failures while keeping review flags intact.

## Key Lessons
- Re-interpreting Slack in Agent 2 added complexity without clear benefit
- Structural checks (membership partitions, evidence IDs) are reliable; semantic entailment is not
- Provisional severity was removed from the model task; all topics are currently **UNKNOWN/UNASSESSED**
- Naming cautions (3 found) are nonblocking and do not invalidate membership
- Failed/social groups retain explicit placeholders rather than being dropped

## Downstream Obligations (Agent 3)
- Topics are an index, not a single answer — preserve member-level questions
- Carry all 49 inherited obligations + 3 naming cautions independently
- Severity remains provisional until researched with evidence
- Needs Review items must appear even without a recommendation
- Original Slack and Agent 1 lineage remain available

## Key Artifacts
- Final dataset: `data/processed/agent2_taxonomy_final_v7/`
- Effective view: `effective_output_reviewed.json` (41 review groups)
- Handoff contract: `agent2-taxonomy-handoff-v1`


## Prospective routing update (2026-10-27)

The results above describe preserved historical releases. New source windows route announcement channels to durable knowledge-source JSON before interpretation. The canonical input partition is 178 discussions / 41 inherited obligations and 22 announcements / eight obligations. All 200 identities and 49 obligations remain accounted for. New Agent 2 exports use schema 8 with UNKNOWN/UNASSESSED severity deferred to Agent 3; the taxonomy prompt/response schema stays v7. Historical v7 loading keeps its original metadata. See [the current routing and knowledge-source guide](announcement-routing.md) for configuration, zero-call commands, schemas, manual file locations and actual validation results.
