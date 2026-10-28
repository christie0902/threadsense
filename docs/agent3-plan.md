# Agent 3 — Plan

**Status:** Not started (branch `agent3`, 2026-10-28). Agent 3 consumes the Agent 2
taxonomy handoff plus last-24h announcements and produces reviewable AdviceCards:
research, final severity and recommendations.

| # | Milestone | Work | Technologies / details | Done when |
| --- | --- | --- | --- | --- |
| 1 | Audit data against demo scenarios | Compare instructions, FAQs, historical decisions and last-24h announcements against the relevant Slack threads. Check authority, scope, chronology, contradictions and intentional gaps. | Manual review + simple scripts over the knowledge store and Slack fixtures. Map to the 8–9 demo cases: TL confirmation, FAQ edge case, temporal conflict, language routing, escalation, already-announced re-ask, QA misalignment, observation-only, upstream flags. | Coverage matrix (supported / partial / missing / contradicted) per demo case, plus proposed data edits. **No data changes yet.** |
| 2 | Apply approved edits, finalize contracts | Make agreed corrections to mock knowledge. Confirm Agent 2 handoff schema, announcement extraction format, AdviceCard fields, review records, severity rubric (with required evidence triggers), confidence bands (≥0.85 / 0.60–0.84 / <0.60). | Pydantic models: AdviceCard, DecisionRecord, AnnouncementRecord. Severity rubric loader. Explicit `card_line` enum and `needs_review_reason` values. | Validated source snapshot and explicit contracts (AdviceCard, Decision, Announcement, ModelReviewItem). Each edit has a reason and identified downstream impact. |
| 3 | Shared retrieval | Ingest guidelines, FAQ, historical decisions. Dense + BM25 hybrid, MMR re-ranking, metadata filters (project_id, date, tags, status). Read-only for Agent 3. Preserve citations, versions, authority, scope. | Chroma (or FAISS), three collections. MMR λ ≈ 0.6–0.7. Chunking: section-level for instructions/FAQ; whole-record for decisions. | Relevant sources returned, out-of-scope sources filtered, missing evidence stays visible. |
| 4 | Small Agent 3 pilot | CrewAI agent for 4–6 cases: current guidance, history, conflict, insufficient evidence, NO_ACTION/observation. Bounded research, severity assessment, grounding check, temporal priority verifier, card-line routing, shallow manual Tree-of-Thought. | Tools: guideline / FAQ / decision retrievers, temporal verifier, severity assessor, grounding checker. Manual ToT (plain Python or one structured call) only on conflict, low-confidence or open-confirmation paths: 2–3 candidate actions scored on grounding / temporal consistency / severity fit; pick best or surface both if close. Finite call budget. | Reviewable AdviceCards with traceable evidence, correct `card_line`, confidence scores, visible ToT options on flagged cases. No unbounded loops. |
| 5 | Overnight workflow | Agent 2 handoff + last-24h announcement extraction → Agent 3 research (conditional ToT) → guardrail routing → output. One topic failure does not stop the rest. | LangGraph: load handoff → extract announcements → per-topic CrewAI node → optional ToT node → guardrail/routing node → aggregate. Error isolation, non-blocking. | Complete run with no lost members or inherited review obligations. ToT only on intended paths. Failures logged and skipped. |
| 6 | Dashboard + TL decision loop | Single-page morning brief: overview, briefing, topic summary, AdviceCards, Model Review Queue. Approve writes decision + shows draft. Structured resolution on Needs Review (incl. ToT options). Accept/Reject/Defer on Agent 1/2 flags. New TL decisions feed back into the decisions collection. | FastAPI + React (Vite, Tailwind, Framer Motion). Endpoints: briefing, cards, approve, resolve, model-review actions. | A TL decision is saved once and retrievable by a later run. ToT alternatives visible on Needs Review cards. Approval distinct from execution. |
| 7 | Validate, prepare demo | All demo scenarios plus negative cases, temporal ambiguity, repeated TL actions, at least one ToT-triggering case. Confirm ToT does not run on normal high-confidence paths. | Scenario runner against LangGraph flow + dashboard. Check expected vs actual `card_line`, sources, `needs_review_reason`, ToT presence/absence. | Reproducible demo, results summary, known limitations, final handoff. Intentionally open cases stay open; ToT only where specified. |

## Notes for implementation

- The plan says `mock_knowledge/`; in this repo the knowledge store is
  `data/knowledge/` (`instructions/`, `faq/`, `decisions/<project>/`). See
  [announcement-routing.md](announcement-routing.md) for the source format and the
  shared ingestion contract (`knowledge_sources.iter_documents` / `normalize_document`).
- Agent 3 input: `data/processed/agent2_taxonomy_final_v7/` via
  `threadsense.agents.topic_effective.load_effective_output` (historical, handoff v1),
  or new schema-8 / `agent2-taxonomy-handoff-v2` exports with severity
  `UNKNOWN`/`UNASSESSED` deferred to Agent 3.
- Must carry all 49 inherited Agent 1 obligations and 3 naming cautions; Needs
  Review items appear even without a recommendation.
- Severity rubric: `data/knowledge/severity_rubric.py` (`severity-rubric-v2-with-signals`).
  Open: per-project rubrics (`get_rubric_for_project` returns default only) and
  LOW-default vs UNKNOWN when evidence is insufficient.
- Not yet dependencies: Chroma/FAISS, rank-bm25, LangGraph, FastAPI, React toolchain.
  Add them to `pyproject.toml` + `uv.lock` together when a milestone needs them.
