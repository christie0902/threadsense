# Current agent implementation

Agent 3 (research, severity, AdviceCards) and the overnight workflow:

| File | Responsibility |
| --- | --- |
| `advice_contracts.py` | AdviceCard v1-v3, DecisionRecord, AnnouncementRecord, ModelReviewItem |
| `advice_inputs.py` | Handoff loading/accounting, review items, historical DecisionRecord mapping |
| `advisor_contracts.py` | Model I/O contracts (draft, grounding judgment, ToT) |
| `advisor_evidence.py`, `advisor_checks.py`, `advisor_tot.py` | Evidence ledger and research tools; deterministic checks and routing; ToT |
| `advisor_pilot.py` | Advisor orchestration (CrewAI stages, request guard, cost ledger) |
| `overnight.py` | LangGraph overnight workflow over the whole handoff |

The dashboard and TL decision store live in `../dashboard/` (see `docs/agent3-plan.md`, Milestone 6).

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

`topic_taxonomy.py` and `topic_consolidation.py` serve different roles; they are
not duplicate versions. Shared canonical identity/hash validation lives in
`../topic_inputs.py`. Agent 1's interpreter and verification modules remain here.

Historical Agent 2 inventory contracts, consolidation logic, evidence helpers,
severity definitions and the retired comparison controller live in
[`../legacy/agent2/`](../legacy/agent2/README.md). They are loaded only when an
older contract is explicitly requested, not when importing the current workflow.
The frozen taxonomy v7 exporter remains in `../legacy/topic_taxonomy_v7.py`.

The unused v1 `topic_review.py` and `review_decisions.py` modules were removed.
Current review handling uses `topic_effective.py`; no review evidence was deleted.
