# Agent 3 — Plan

**Status:** Milestones 2 and 3 implemented (retrieval: 2026-10-29). Milestone 2 implemented (contracts, rubric binding, Markdown ingestion;
2026-10-29). Milestone 1 audit not yet written up. Agent 3 consumes the Agent 2
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
- Not yet dependencies: LangGraph, FastAPI, React toolchain. Chroma is a direct dependency since
  milestone 3; BM25 is implemented in `retrieval/bm25.py` (no rank-bm25 package).
  Add them to `pyproject.toml` + `uv.lock` together when a milestone needs them.

## Milestone 2 (implemented)

Verify offline (zero calls, writes nothing unless `--report` names a new file):

```sh
uv run --locked python scripts/validate_agent3_inputs.py
```

| Module | Purpose |
| --- | --- |
| `src/threadsense/severity_rubric.py` | Loads `data/knowledge/severity_rubric.py` through its own `get_rubric_for_project`; records version plus a content hash of the parsed definitions (independent of line endings); checks contract compatibility and cited signal text. No classification. |
| `src/threadsense/agents/advice_contracts.py` | `agent3-advice-card-v1`, `agent3-decision-record-v1`, `agent3-announcement-record-v1` (wraps `SourceRecord`), `agent3-model-review-item-v1`, plus evidence, occurrence and severity models. |
| `src/threadsense/knowledge_markdown.py` | Markdown front matter (safe YAML, timestamps kept as strings) → `SourceRecord`. Used by `knowledge_sources.iter_documents` for `.md` paths. |
| `src/threadsense/knowledge_corpus.py` | Discovery limited to `instructions/`, `faq/`, `decisions/` Markdown and the documented `manual/`/`extracted/` JSON locations; reference, supersession, overlap and conflict report. |
| `src/threadsense/agents/advice_inputs.py` | Agent 2 export/registry accounting, one `ModelReviewItem` per obligation, structural occurrence counts, historical `DecisionRecord` mapping. |

**Guardrails in `AdviceCard` validation** (structural only): confidence `< 0.60` needs
`LOW_CONFIDENCE`; band `MODERATE` for `[0.60, 0.85)`, `HIGH` from `0.85`; assessed
`HIGH` needs `HIGH_SEVERITY`; inherited flags, recorded temporal conflicts, grounding
failures and open confirmations each need their reason. Any reason forces
`NEEDS_REVIEW`. `RECOMMENDED_ACTION` needs an operational action, cited sources and
`checks.grounding == PASSED`. `checks.grounding` defaults to `NOT_RUN` (not run, not
failed): such a card stays a draft or uses `NEEDS_REVIEW` with `GROUNDING_NOT_RUN`;
`GROUNDING_FAILURE` is accepted only when the check recorded `FAILED`. Validation never
performs semantic grounding.
Unassessed severity is `UNKNOWN`, provisional, with Agent 2's placeholder kept as lineage.

**Mapping decisions.**
- `instructions` → `guideline`. Authoring `record_kind`s (`advice_review`, `follow_up`,
  `expert_referral`, `expert_review`, `escalation_receipt`) → `decision`;
  `channel_announcement` → `announcement`. The full front matter is kept in
  `source_metadata.authoring`; unknown kinds fail rather than defaulting.
- IDs: canonical `record_id` = source identity (manual key or Slack channel/thread/message),
  `version_id` = content hash; authoring `document_id@version` kept separately. A second
  content for the same authoring identity is rejected. File paths never enter IDs.
- Supersession: section-level references stay in `source_metadata.supersession` with
  `granularity: section`; only whole-document references would populate
  `SourceRecord.supersedes` (none exist).
- Manual records: `effective_at` from front matter, `created_at` null, `last_updated`
  kept as authoring metadata. Slack records: `created_at` from the exact `ts`; identity,
  author, text and snapshot hashes verified (text: UTF-8 sha256; snapshot: sha256 of
  UTF-8 JSON with sorted keys and `(",", ":")` separators, inferred from the data since
  it was not documented). Retrieval text is the Slack message; the archive note and
  raw snapshot stay metadata. "Referenced records" link lists are excluded from text.
- `DecisionRecord` is built only for TL decisions (advice reviews, referrals, expert
  review, escalation); follow-ups and posts remain sources. Status strings map through
  explicit tables in `advice_inputs.py` and keep `source_status`.
- `card_line` values (`RECOMMENDED_ACTION` / `NEEDS_REVIEW` / `OBSERVATION`) and the
  action vocabulary (taken from the decision records) are this milestone's proposal.

**Closeout (2026-10-29).**
- Rubric: `RUBRIC_VERSION` is now `severity-rubric-v3-semantic-signals`; definitions,
  examples and signals are unchanged (content hash `eccaa31a…` is the same as before).
  The LOW comment now says limited impact may be inferred from context, but missing
  evidence alone does not establish LOW. Every project currently uses the shared default
  rubric: the loader reports `rubric_scope: SHARED_DEFAULT`, and assessed severities must
  record it. `UNKNOWN` (rubric level) and Agent 2's placeholder stay separated by
  `assessment_status`.
- Knowledge: the headset check approval/completion and onboarding office-hours post moved
  from `decisions/multilingual_eval/` to `decisions/audio_multimodal/` (their declared
  project). Bytes, record IDs and version IDs are unchanged. The validator reports any
  declared-project/folder mismatch and overrides neither value.
- Demo snapshot: `data/fixtures/slack_generated_demo/` (from
  `ThreadSense_MockData_Update_2026-10-28.zip`; package notes in
  `docs/threadsense_demo_update/`, never indexed) = 201 threads / 517 messages
  (178 discussion, 23 announcement) at cutoff `2026-10-02T12:00:00Z`. It adds only
  `C_AUDIO_ANNOUNCEMENTS` `1790892000.000901` (2026-10-01 22:00 UTC), before the later
  playback questions `1790896012.001900` and `1790903186.000110`. The original
  `data/fixtures/slack_generated/` (200 / 516) is unchanged and matches the package's
  recorded baseline hashes. The new announcement is not an Agent 1 member; it enters
  through announcement extraction, not the Agent 2 handoff.
- Current handoff: `data/processed/agent2_handoff_v2_projection/`, written by
  `scripts/project_agent2_handoff.py --write` with zero calls. It is a projection of the
  v7 release, not a fresh taxonomy run (`projection_manifest.json` records provenance).
  Announcement members are routed out (22 members, 8 obligations, in
  `routing_manifest.json`). 73 groups with unchanged discussion membership are
  re-exported from their saved v7 responses under schema 8 / handoff v2. 8 groups lost
  announcement members, so their saved responses cannot be reused without altering model
  output; their 17 members stay `UNASSIGNED` with a projection-gap review reason.
  9 announcement-only groups have no discussion members. Totals: 81 groups, 79 topics,
  161 assigned + 17 unassigned discussion members, 41 + 8 = 49 obligations, 39 effective
  review groups. The 3 naming cautions carried over by exact match (same group, members and
  response bytes) in `carried_review_supplement.json`, which `advice_inputs.load_effective_view`
  applies after checking its hash; the review registry is unchanged.
- Remaining: a taxonomy for the 8 partial groups needs either a new Agent 2 run on those
  payloads or an approved rule for projecting saved responses. The registry still lists
  `agent2_remaining_v6`, archived on 2026-10-28 (not applied to any inspected run).
  Record payloads embed the absolute grouping path, as the v7 release did, so projection
  hashes depend on checkout location.

## Milestone 3 (implemented): shared hybrid retrieval

```powershell
uv run --locked python scripts/build_retrieval_index.py            # offline; add --allow-download once if the model is not cached
uv run --locked python scripts/build_retrieval_index.py --rebuild  # after corpus/config changes (refused otherwise)
uv run --locked python scripts/evaluate_retrieval.py               # BM25 / dense / RRF / RRF+MMR on data/evaluation/agent3_retrieval_cases.json
```

Package `src/threadsense/retrieval/`: `corpus.py` (sources), `chunking.py`, `bm25.py`,
`embeddings.py`, `index.py` (build), `search.py` (read-only `Retriever`), `evaluate.py`.
Index: `.index/retrieval/` (git-ignored): persistent Chroma collections `guidelines`,
`faq`, `decisions` (incl. announcements), plus `chunks.json`, `documents.json` and
`manifest.json` in the same build.

- **Sources.** The 40 authored documents through `knowledge_corpus.discover` +
  `iter_documents`, plus current-day announcements through `fixture_routes` +
  `extract_announcement` on the demo snapshot at cutoff `2026-10-02T12:00:00Z`
  (23 extracted, 22 with inherited Agent 1 metadata, 8 of them review-flagged). Counts,
  duplicates and Slack overlaps are derived at build time (currently 63 documents, none
  removed). Archive Slack posts in the knowledge store stay authored history.
- **Embeddings.** `sentence-transformers/all-MiniLM-L6-v2` at revision
  `b9db1e8a0d3a51769172ba8546f282a73f066e47` (the grouping model), CPU, normalized,
  cosine, 384 dimensions, 256-token limit, identical encoding for queries and documents,
  loaded with `local_files_only` unless `--allow-download`.
- **Chunks** (`knowledge-chunks-v1`): guideline/FAQ sections with the document title;
  decisions/announcements whole when they fit, otherwise consecutive sections under a
  header repeating record kind and decision/execution/outcome state; oversized units split
  at paragraph/line/sentence/word boundaries; each chunk is checked against the token
  limit and nothing is truncated. Currently 113 chunks (guidelines 29, FAQ 17, decisions
  67); 21 decision records split. Chunk IDs hash chunking version + document/version +
  position. Each chunk keeps citation, flat filter metadata, review lineage and
  section-level supersession; full normalized metadata stays in `documents.json`.
- **Query.** `Retriever.search(query, project, batch=, batch_scope='project'|'strict',
  as_of=, include_shared=, collections=, document_types=, statuses=, record_kinds=, tags=,
  event_series_ids=, date_from=, date_to=, include_undated=, version_mode='current'|'history',
  top_k=8, candidate_k=30, rrf_k=60, mmr_lambda=0.9, mode='hybrid'|'dense'|'bm25',
  use_mmr=True)`. Filters and version applicability pick the eligible chunks first; both
  paths rank only those. Results carry text, citation, metadata, `batch_relation`,
  `date_status`, `expired_as_of`, supersession, `version` (lineage, state, applicability,
  other revisions, replaced sections), component ranks/scores and final rank; responses add
  `version_diagnostics` and `withheld_by_version`. Scores are not confidence or grounding.
- **Version-aware eligibility** (`retrieval/versions.py`). A lineage is one authoring
  `document_id` within project and scope (sources without authoring IDs use their
  version-independent `record_id`); never titles or embeddings. Revisions are ordered by
  source date only (`effective_at`, else Slack `created_at`), never by version strings,
  hashes, file or ingestion times. Reference time is `as_of`, else the index cutoff.
  Guideline/FAQ revisions need `approved`/`tl_approved` (or `partially_superseded`, whose
  unreplaced sections still apply); decision records need no approval status. States:
  `CURRENT`, `SUPERSEDED_REVISION`, `NOT_YET_EFFECTIVE`, `NOT_APPROVED`, `OTHER_BATCH_SCOPE`
  (only when an in-scope revision exists), `UNRESOLVED`. Section supersession declared by
  either side applies only to the named section, and only when the superseding source is
  indexed, approved and effective; otherwise it is reported as `UNVERIFIED_SUPERSESSION`.
  `current` (default) withholds superseded revisions and applicable superseded sections
  before ranking and lists them in `withheld_by_version`; `history` keeps every revision
  with its `applicability` marked. Tied or missing revision dates and ambiguous batch scope
  keep all candidates as `UNRESOLVED` with a diagnostic; retrieval never picks a winner or
  sets grounding. Conflicting contents for one authoring version still fail ingestion.
  On the current corpus every lineage has one revision; the only withheld chunk is
  `safety-qn-help-page@1.0#Contact details`.
- **Dense search** is exact cosine over the embeddings stored in Chroma; Chroma's HNSW
  `collection.query` is not used. In ChromaDB 1.5.9 that query failed intermittently
  ("Error creating hnsw segment reader: Nothing found on disk") after several collections
  were read. The cause is unidentified and the issue is not fixed; it is avoided. Exact
  search over 113 vectors is cheap and has no approximation error. The build verifies that
  every stored embedding is readable from a fresh process before publishing its manifest.
- **RRF** (k=60) combines dense and BM25 ranks; raw scores are never added. **MMR**
  re-ranks the fused pool with relevance min-max scaled to [0, 1] and redundancy = max
  cosine to already selected chunks (clipped to [0, 1]); ties fall back to fused order.
  Default lambda 0.9 (decided 2026-10-29); `use_mmr=False` gives RRF only, the evaluation
  baseline. Identical text collapses into one displayed result only when scope, dates,
  authority and decision/execution/outcome state also match; collapsed sources stay in
  `duplicate_sources` with citations and metadata (the current corpus has no identical
  chunk texts).
- **Evaluation (real embeddings, top 5).** Main set (`agent3_retrieval_cases.json`, 9
  answerable + 1 unsupported; the fictional-PII case explicitly uses `version_mode=history`
  because it targets the stale branch):

  | Variant | Mean recall | Full recall | Misleading near-matches | Date violations |
  | --- | --- | --- | --- | --- |
  | BM25 | 0.80 | 6/9 | 5 | 0 |
  | Dense | 0.93 | 7/9 | 3 | 0 |
  | RRF | 1.00 | 9/9 | 3 | 0 |
  | RRF + MMR 0.9 (default) | 1.00 | 9/9 | 4 | 0 |
  | RRF + MMR 0.65 (previous) | 0.52 | 4/9 | 7 | 0 |

  MMR 0.9 adds one near-match (the JSON audit-manifest decision in the JSON-vs-prose case)
  and moves the 22:00 playback announcement from rank 2 to 3 and from 3 to 4. Holdout
  (`agent3_retrieval_holdout.json`, two paraphrases labelled before running): BM25 0.83,
  dense 0.67, RRF 0.83, RRF + MMR 0.9 1.00; no near-matches. The holdout is too small to
  separate the variants. The unsupported payroll query still returns nearest neighbours,
  so result presence never implies an answer.
- **Redundancy-sensitive pairs (top 8, default settings).** Status note vs later handling
  announcement (cosine 0.89): ranks 3 and 6 with MMR, 4 and 5 with RRF, so a top-5 request
  can lose the announcement. Approval vs outcome pairs (playback trial, tie calibration,
  documentation sync, audit-export fix, headset check; cosine 0.71-0.80): both kept with
  MMR and RRF. Old help-page rule vs scoped replacement: both kept in history mode; in
  current mode the old section is withheld by design and remains discoverable through
  `withheld_by_version`, the clarification's `supersedes` link and history mode.
- **Git.** `data/processed/agent2_handoff_v2_projection/` (14 MB on disk; 242 files) is
  already tracked byte-exact (`-text`); keep it tracked as the recorded Agent 3 input. Its
  7 MB `effective_output.json` is derivable, but removing frozen files would change the
  recorded evidence, so leave it.
