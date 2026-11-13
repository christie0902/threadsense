# Current agent implementation

Agent 3 (research, severity, AdviceCards) and the overnight workflow:

| File | Responsibility |
| --- | --- |
| `advice_contracts.py` | AdviceCard v1-v4 (v4: `details`, `next_step`; `validate_card` reads v3 and v4), DecisionRecord, AnnouncementRecord, ModelReviewItem |
| `advice_inputs.py` | Handoff loading/accounting, review items, historical DecisionRecord mapping |
| `advisor_contracts.py` | Model I/O contracts (draft v11 with `detail_sentences`, grounding judgment, ToT) |
| `advisor_evidence.py`, `advisor_checks.py`, `advisor_tot.py` | Evidence ledger and research tools; deterministic checks and routing; ToT (design, candidate tracking and selection rules: `docs/agent3-tot-design.md`) |
| `tot_policy.py` | Optional shadow ToT policy (partial order over the comparison's ratings; records, never routes) and incumbent-issue dispositions |
| `advisor_pilot.py` | Advisor orchestration (CrewAI stages, request guard, cost ledger) |
| `overnight.py` | LangGraph overnight workflow over the whole handoff (consolidated topics, processing history) |
| `action_coordination.py` | Shared actions: one briefing action for distinct topics whose verified proposals match exactly |
| `review_lessons.py` | Optional: lessons from human review for Agents 1 and 2 (snapshot, deterministic selection, at most 5 per request; Agent 1 request wrapper) |
| `reviewer_context.py` | Optional: confirmed reviewer corrections from a feedback snapshot, matched by project + shared thread and sent as labelled advisory context (`docs/human-feedback-loop.md`) |

The dashboard and TL decision store live in `../dashboard/`.

For current Agent 2 work, start with:

| File | Responsibility |
| --- | --- |
| `topic_contracts.py` | Current taxonomy response schema (v7) only |
| `topic_taxonomy.py` | Current prompt, membership validation and passive export (schema 8) |
| `topic_consolidation.py` | Stable public entry point; explicit version dispatch for historical replay |
| `topic_pipeline.py`, `topic_requests.py` | Bounded runner and request transport |
| `topic_effective.py` | Canonical output plus evidence-bound review obligations |
| `topic_continuation.py` | Continue only groups with no prior attempt |
| `topic_analyst.py` | Current CrewAI compatibility entry point |
| `topic_merge.py` | Consolidation across candidate groups (agent2-consolidation-v1, handoff v3) |

Agent 1 relevance (`thread_relevance.py`, judgment agent1-relevance-v1, stage v2) extends the interpretation request without changing the
fingerprinted Agent 1 modules; its stage decides what is clustered and what goes to processing history. A proposed model
exclusion also needs the semantic verifier: one prose-comparison request under the verifier's own rules and schema
(agent1-relevance-verification-v1); only SUPPORTED excludes, anything else keeps the thread eligible.

`topic_taxonomy.py` and `topic_consolidation.py` serve different roles; they are
not duplicate versions. Shared canonical identity/hash validation lives in
`../topic_inputs.py`. Agent 1's interpreter and verification modules remain here.

Historical Agent 2 inventory contracts, consolidation logic, evidence helpers,
severity definitions and the retired comparison controller live in
[`../legacy/agent2/`](../legacy/agent2/README.md). They are loaded only when an
older contract is explicitly requested, not when importing the current workflow.
The frozen taxonomy v7 exporter remains in `../legacy/topic_taxonomy_v7.py`.
Review handling uses `topic_effective.py`.
