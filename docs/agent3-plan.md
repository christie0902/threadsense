# Agent 3 — Plan

**Status:** Milestones 2, 3 and 4 implemented (2026-10-29): contracts, rubric binding and Markdown
ingestion; shared retrieval; a bounded Advisor pilot, hardened (final statement-level grounding,
announcement applicability, member-level resolution, request-boundary limits) and validated
offline with scripted semantic judgments (no live model run yet). Milestone 1 audit not yet written up. Agent 3 consumes the Agent 2
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
- **Chunks** (`knowledge-chunks-v2`): guideline/FAQ sections with the document title;
  decisions/announcements whole when they fit, otherwise consecutive sections under a
  header repeating record kind and decision/execution/outcome state; oversized units split
  at paragraph/line/sentence/word boundaries; each chunk is checked against the token
  limit and nothing is truncated. v2 (Milestone 4 setup) splits an oversized FAQ section
  at question/answer units, and an answer continuation repeats its exact question; lines
  repeated for context (continued heading or question) are listed in each chunk's
  `repeated_context`, so the preservation check can tell them from duplicated source text.
  This fixed v1's orphaned continuation (the SC-PII-2026-09-10 paragraph without its
  question). Currently 112 chunks (guidelines 29, FAQ 16, decisions 67); 21 documents split. Chunk IDs hash chunking version + document/version +
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

## Milestone 4 (implemented): bounded Advisor pilot

```powershell
uv run --locked python scripts/run_agent3_pilot.py                    # zero calls: freshness, topics, initial retrieval, request sizes, live configuration
uv run --locked python scripts/run_agent3_pilot.py --scripted tests/fixtures/agent3_pilot_scripted_judgments.json --write <new-dir>
uv run --locked python scripts/run_agent3_pilot.py --run --write <new-dir>   # PAID; not yet run (see "Live run" below)
```

Modules (`src/threadsense/agents/`): `advisor_contracts.py` (model I/O: `AdvisorDraft` v2,
`GroundingJudgment` v2, `ToTComparison` v1), `advisor_evidence.py` (freshness check, evidence
ledger, agent-facing serialization, `ResearchTools`, `Budget`), `advisor_checks.py`
(deterministic checks, final statements, authorization, card routing), `advisor_tot.py`
(conditional shallow ToT), `advisor_pilot.py` (orchestration, scripted and CrewAI clients,
request guard, outputs). AdviceCard v1 is unchanged; the pilot result record wraps it with the
trace, ledger, statement verdicts, withheld statements and alternatives.

**Retrieval setup (done first).**
- FAQ question context: chunking v2 above. Index rebuilt; real-embedding evaluation
  unchanged (main set RRF 1.00 / 9 full / 3 near-matches, RRF+MMR 0.9 1.00 / 9 / 4;
  holdout RRF 0.83, RRF+MMR 1.00). No retrieval regression; labels, settings and holdout
  untouched.
- Evidence the model receives (`evidence_item`): citation identity (document/version/chunk
  IDs, authoring ID, sections, source), `use`, applicability (state, replacement with its
  effective date, unverified supersession, supersedes links, other revisions), dates, scope,
  authority, recorded states and upstream review flags. `use` is `CURRENT_GUIDANCE`
  (guideline/FAQ), `ANNOUNCEMENT`, `PRIOR_DECISION`, `HISTORY_ONLY`, `UNRESOLVED_VERSION`;
  members are `MEMBER_REPORT`. Historical, unresolved, prior-decision and announcement
  excerpts start with a status line, so the status cannot be read apart from the text.
  Every payload also lists `withheld_by_version` and `version_diagnostics`. Tests parse the
  exact text the model receives (`task_description`), not the sidecar.
- Freshness: `open_retriever` runs `Retriever.staleness()` once before research and refuses
  a stale or incompatible index with the rebuild command; queries never re-check.

**Selected topics** (`data/evaluation/agent3_pilot_scenarios.json`, IDs and Agent 2 names
only; no expected sources or answers): audio playback `cluster_6b59d1…` "LT audio player
playback failure"; JSON vs prose `cluster_fb1dce…`; fictional PII `cluster_9378eb…`;
Korean register `cluster_3b950a…`; submit failure `routed_440e64c…`; repeated ending
`cluster_b7e523…`; plus the payroll negative control. The response-preference Submit threads
are a projection gap (no Agent 2 topic), so that card covers the group's 4 unassigned
members with `topic_id: null`, a mechanical label and a `projection_gap` inherited flag;
no taxonomy is invented. The payroll question has no handoff members and stays cardless (an
external negative control); a real handoff member is always on a card, even when its draft is
UNSUPPORTED or missing.

**Per-topic flow.** As-of is the index cutoff (`2026-10-02T12:00:00Z`) for every call,
including history mode.
1. Initial retrieval: current mode, all source types, top 5, RRF+MMR λ 0.9. The query is the
   topic name plus the earliest member's Agent 1 central question.
2. If the project has withheld (superseded) material, one history-mode supersession check
   with the same query (generic rule; on this corpus only safety triggers it).
3. Draft call. The model names gaps and optional follow-up queries; assesses each
   announcement it relies on (relevant? directive? verbatim directing sentence); gives each
   member a resolution state from that member's own messages; names documentation targets.
4. Up to 3 follow-up retrievals executed by `ResearchTools` (the model never calls tools
   itself), then at most one revision call.
5. Deterministic checks: structure (`structural_issues`, `action_issues`), severity binding
   to the unchanged rubric, temporal priority.
6. Conditional ToT (one call), only on conflict, low-confidence or open-confirmation paths and
   only when no structural check failed.
7. **One final semantic grounding call** over every statement that can reach the card or a
   reviewer (below), then authorization and deterministic card routing. Nothing after this
   call can add or change a statement.

**Final grounding and authorization (hardening pass, 2026-10-29).** Before this pass the
grounding call judged only the draft's claims and action, and ToT ran afterwards; the summary,
severity rationale, affected reporters and ToT alternatives were never judged, and resolution
came from Agent 1. Now `statements()` builds one list:

| Statement | Cites | Blocking |
| --- | --- | --- |
| `claim:<id>` (incident fact, guidance, history, inference) | the claim's evidence | if material |
| `summary` | all material claims' evidence | yes |
| `action` (text, scope and documentation targets) | support claims' evidence + targets | yes |
| `announcement:<id>` (relevant directive, quoted) | the announcement | yes |
| `resolution:<member>` (state other than UNKNOWN) | that member's messages (+ current sources) | yes |
| `severity:rationale`, `severity:signal:<LEVEL>[i]` | signals, reporters, incident facts | yes, when binding succeeded |
| `reporter:<author>` | the reporter's own message | yes |
| `alternative:<candidate>` (valid ToT candidates) | the candidate's evidence | no (never card content) |

The judgment returns one verdict per statement ID. Dependencies are applied deterministically
(`_effective`): a guidance claim resting only on announcements needs a SUPPORTED announcement
statement; an action needs every support claim SUPPORTED. No statement borrows another's
verdict. Grounding is PASSED only when every blocking statement is SUPPORTED; statements citing
nothing are never sent (NO_EVIDENCE). `authorize()` then builds the card only from SUPPORTED
statements: card reasoning is composed from supported claims (the model's free-text reasoning
stays in the result record), an unsupported summary is replaced by a withheld notice, an
unsupported action is not carried, an unsupported severity rationale or signal leaves severity
UNASSESSED, unsupported reporters are dropped from the lower-bound count, and an unsupported
member resolution becomes UNKNOWN. Every withheld statement stays in `diagnostics`
(`WITHHELD_STATEMENT` / `ALTERNATIVE_NOT_GROUNDED`) with its text and verdict; the card's
GROUNDING_FAILURE reason names it by ID only. A ToT candidate is preferred only if it is valid
and its own statement is SUPPORTED.

**Announcement applicability.** The 31 announcements carry no metadata separating a directive
from a routine note (all are `TEAM_LEAD` announcements; the 22:00 playback directive has the
same empty status as "Reminder to use headphones"). So no announcement is current handling by
type. An announcement becomes current handling for a topic only when the draft assesses it as
relevant and directive with a verbatim directing sentence (deterministic quote check) **and** the
final grounding judges that `announcement:` statement SUPPORTED. Recorded supersession resolves
a conflict only in favour of current guidance or a verified announcement. Identity, dates,
authority and scope are kept either way.

**Documentation targets.** `UPDATE_DOCUMENTATION`/`UPDATE_FAQ` must name targets
(`evidence_id`, section, `ADD`/`CORRECT`/`REMOVE`). Deterministic checks: the target is a
retrieved source of the right type; a named section is in the cited chunk; `CORRECT`/`REMOVE` of
current guidance is flagged `ACTION_TARGET_ALREADY_CURRENT` unless the draft reports a conflict
involving it. The card's scope note lists the targets and their state (e.g. "CORRECT
safety-qn-help-page@1.0 section 'Contact details' (superseded section, stale copy)").

**Resolution.** Agent 1 resolution labels travel as attributed inputs (with Agent 1's
verification status) and are never evidence. Each member's state must cite that member's own
thread (current sources may add support; history may not). The topic state is computed from
grounded member states: all equal → that state; known states differ → MIXED; any member without
a supported state → UNKNOWN. One resolved member never resolves the topic. The card reasoning
shows the grounded per-member counts and the attributed Agent 1 counts, including how many were
unverified.

**Budgets and request limits.** 4 model calls per topic (draft, revision, ToT, final
grounding), 28 per run; 6 retrieval calls per topic, 42 per run. Draft, revision and ToT run
only if a call stays reserved for the final grounding (`SKIPPED_RESERVED_FOR_GROUNDING`).
Request boundary, measured offline at the httpx transport (`tests/test_agent3_request_boundary.py`):

| Reply to one stage | Earlier Agent/Crew client | Now |
| --- | --- | --- |
| valid JSON | 1 request | 1 |
| non-final-answer text | 2 (CrewAI forced-final-answer call) | 1 (stage FAILED) |
| HTTP 500 / connection error | 3 (OpenAI SDK `max_retries=2`) | 1 |
| HTTP 429 | 9 (SDK retries × CrewAI's fixed 3-attempt rate-limit retry) | 1 sent, retry refused unsent |

The live client calls `crewai.LLM.call` directly (no Agent/Crew executor, no tools,
`max_retries=0`, `response_format=json_object`, temperature 0, `max_tokens` 4096, timeout
120 s) inside `RequestGuard`, which counts requests at the transport and refuses any second
request in a stage before it is sent. A reply that arrives without a request through the
guarded transport stops the run (`BoundaryNotObserved`). `QUIET_ENV` disables CrewAI telemetry
and LiteLLM's remote price-map download. An end-to-end test runs the whole pilot through the
live client against a fake provider: requests = stage calls ≤ 28, and cards match the scripted
run.

**Deterministic vs semantic.**

| Check | How |
| --- | --- |
| Citation IDs exist; incident facts cite member messages only; guidance cites current guidance or an established announcement, never a historical/unresolved item; history cites retrieved records; quotes verbatim (status lines excluded); announcement assessments quote verbatim; resolution cites the member's own thread | Deterministic (`structural_issues`); any failure = grounding FAILED without a semantic call (and no ToT) |
| Operational action supported by a guidance or prior-decision claim; documentation targets real, of the right type and not already current | Deterministic (`action_issues`) |
| Each statement supported by the excerpts it cites | Final semantic grounding call; PASSED only if every blocking statement is SUPPORTED after dependencies. Citation existence alone never passes; a missing judgment is NOT_RUN and nothing is authorized |
| Temporal priority | Deterministic: a model-reported conflict is RESOLVED only when recorded supersession links the historical item to the one current item (current guidance or a verified announcement); otherwise DETECTED. Unresolved versions or unverified supersession cited → DETECTED. Future and draft revisions never compete |
| Severity | Semantic proposal, deterministic binding (rubric text by level/index, member-message evidence per signal, reporters from their own messages, recurrence from retrieved records), then semantic grounding of rationale, signals and reporters. Any failure leaves severity UNASSESSED with an OTHER reason |
| Resolution | Semantic per-member proposal from thread messages, grounded per member; deterministic topic aggregation |
| Card line | Deterministic: contract review codes + GROUNDING_NOT_RUN + OTHER (insufficient/unsupported evidence, severity not established, stage failures) → NEEDS_REVIEW; otherwise an authorized operational action → RECOMMENDED_ACTION; else OBSERVATION |
| ToT | Triggered only by TEMPORAL_CONFLICT, confidence < 0.60 or OPEN confirmation; one call, 2–3 candidates, before the final grounding. Invalid candidates (unknown evidence) are not presented; valid ones are judged as their own statements. Never changes the card action or review reasons |

**Offline pilot output** (`data/experiments/agent3_pilot_offline_v2/`, `SCRIPTED_MOCK`;
`agent3_pilot_offline_v1/` is the pre-hardening run, kept for comparison): manifest,
per-scenario results (retrieval trace, evidence ledger, model-call log with raw responses,
drafts, follow-ups, statement verdicts, withheld statements, temporal, severity, resolution,
ToT, card, review items, coverage, budget), `cards.json`, `review_items.json`, `report.md`.
The prepared responses (`tests/fixtures/agent3_pilot_scripted_judgments.json`, regenerated by
`tests/fixtures/make_agent3_pilot_scripted_judgments.py` when evidence IDs move) exercise the
checks; they are not model output. Consumed: 18/28 model calls, 11/42 retrievals.

| Topic | Card; action | Grounding | Severity | Resolution (grounded vs Agent 1) | ToT | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| audio_playback | NEEDS_REVIEW (HIGH, flags); UPDATE_FAQ, ADD to FAQ "Playback and tool issues" | PASSED | HIGH: 4 affected reporters; recurrence FOUND (batch-05 trial) | MIXED (2 partial: TL interim handling; 2 unresolved) vs Agent 1 3 UNRESOLVED + 1 PARTIALLY_RESOLVED (2 unverified) | — | 22:00 announcement verified as handling |
| json_vs_prose | NEEDS_REVIEW (open confirmation, flag); NO_ACTION (hold for TL) | PASSED | MEDIUM[0] | UNRESOLVED | A SUPPORTED (preferred); B (rejected JSON-first rule) UNSUPPORTED; C PARTIALLY_SUPPORTED | |
| fictional_pii | NEEDS_REVIEW (flag); UPDATE_DOCUMENTATION, CORRECT help page v1.0 "Contact details" only | PASSED | MEDIUM[1] | UNRESOLVED vs Agent 1 2 PARTIALLY_RESOLVED | — | Clarification and batch-08 post verified; conflict RESOLVED_BY_RECORDED_SUPERSESSION; instructions v1.4 and FAQ v1.1 stated as already updated |
| korean_register | NEEDS_REVIEW (flag); ROUTE_TO_LANGUAGE_SPECIALIST | PASSED | MEDIUM[0] | UNRESOLVED | — | Batch-10 precedent kept as scoped history |
| submit_failure | NEEDS_REVIEW (HIGH, GROUNDING_FAILURE, projection gap + flags); ESCALATE_ENGINEERING (ask whether reports match the open handoff) | FAILED: `claim:c5` ("share the cause…") withheld | HIGH: 5 reporters | UNRESOLVED | — | c5 text only in diagnostics, never on the card |
| repeated_ending | NEEDS_REVIEW (low confidence, insufficient evidence, flags); NO_ACTION | PASSED | MEDIUM[0] | UNRESOLVED | A and B SUPPORTED (close call); C ("confirmed loop", no evidence) not presented | No cause asserted |
| payroll control | no card | — | — | — | — | UNSUPPORTED although 5 nearest neighbours were retrieved |

**Tests.**
- `tests/test_agent3_advisor.py` (28, test-double index): each test's docstring says DETERMINISTIC or MOCKED SEMANTIC. Covers, among others: final grounding covering every card statement and running last; a ToT candidate whose unsupported claim cannot borrow the draft's verdicts; the routine-reminder negative case; documentation targets; member-level resolution. One test removes the upstream obligations from a copy of one record to reach RECOMMENDED_ACTION and OBSERVATION.
- `tests/test_agent3_request_boundary.py` (7, fake provider, network refused): one request per stage for each reply type; budget equals requests; an unobserved reply stops the run.
- `tests/test_agent3_pilot_integration.py` (3, real embeddings, offline):
  - the full scripted pilot, which also detects scripted evidence IDs drifting from the index;
  - recovery of the 22:00 announcement when the real top five for the member question
    "Was the previous playback workaround approved and did it work?" omit it;
  - the whole pilot through the live client against a fake provider (request accounting).
- The recovery test with the test encoder uses "Did the earlier reload trial restore playback?", for the same reason.

**Live run (prepared, not run).**

```powershell
$env:PYTHONIOENCODING = 'utf-8'
uv run --locked python scripts/run_agent3_pilot.py                                  # zero calls: check the printed live_configuration
uv run --locked python scripts/run_agent3_pilot.py --run --write data/experiments/agent3_pilot_live_v1
```

- Model: `THREADSENSE_MODEL` (currently `openai/gpt-4o-mini`), key `OPENAI_API_KEY` from `.env`.
- Limits: ≤ 4 calls per topic, ≤ 28 per run, 1 HTTP request per call (≤ 28 requests), no
  retries, ≤ 4,096 completion tokens per call, 120 s timeout.
- Size (measured on the scripted path, o200k tokenizer): draft requests 8–12k input tokens,
  revision up to 17k, grounding up to 9k, ToT up to 10k; 18 requests ≈ 186k input tokens. A
  live run that uses every call stays under 28 × 17k ≈ 480k input and 28 × 4,096 ≈ 115k
  output tokens.
- A failed stage is recorded, not retried; the topic still gets a card. Results are labelled
  `LIVE_MODEL`.

**Live evaluation v1 (2026-10-29, `data/experiments/agent3_pilot_live_v1/`, `LIVE_MODEL`).** One run, no
prompt or model changes, failures kept. `gpt-4o-mini` (returned `gpt-4o-mini-2024-07-18`); 15 stage calls =
15 HTTP requests, none blocked or retried; all HTTP 200, `finish_reason: stop`, all schema-valid;
120,207 input / 10,437 output tokens; 110.6 s model time, 136 s wall. The request guard now also
records provider usage, returned model and latency per request (instrumentation only).
Findings, checked against the cited passages:
- **No research loop.** No draft named a follow-up gap, so 0 follow-ups and 0 revisions; relevant
  records retrieved in the first pass (Korean batch-10 precedent, Submit engineering handoff, repeated-ending
  observation review, rejected JSON-first rule not retrieved at all) were not cited.
- **No actions.** No draft proposed an action; every draft (including the payroll control) set
  `open_confirmation` OPEN, even where current guidance answers the question (audio: no QN solely
  because playback fails). ToT therefore ran on 4 of 6 topics; it surfaced grounded options (audio
  POST_ALIGNMENT, Submit ESCALATE_ENGINEERING) that never reach the card.
- **Structural checks caught real defects.** PII: a paraphrased FAQ quote and a TL Slack message cited
  as GUIDANCE; Korean: a paraphrased FAQ quote; repeated ending: an affected reporter (U017) cited
  with U013's message; JSON: MEDIUM with no rubric signal. In PII and Korean one bad quote voided the
  whole draft (nothing authorized), withholding accurate claims too.
- **Grounding judge is lenient.** (Corrected 2026-10-29: the names in claims, e.g. "Yuki" for U019 and
  "Leo" for U007, were the right authors per the user directory; the defect was that v1 evidence carried
  author IDs only, so neither the judge nor any check could verify names. Directory names and a
  deterministic author check were added.) It passed audio HIGH[0] although the cited tutor messages
  do not state the work cannot be evaluated (the uncited TL reply does); passed a ToT option to
  "update documentation" on the strength of an instruction that does not call for it; and
  rationales often restate the statement. Resolution: the model may cite part of a thread, and the
  judge sees only what is cited (audio member 894091 marked UNRESOLVED and passed, though the
  uncited TL reply gives the same interim handling as member e76f89, whose PARTIALLY_RESOLVED was
  withheld).
- **Cards stay safe but thin.** All six are NEEDS_REVIEW with no action; useful content is the
  grounded incident summary, member threads and inherited flags; severity survives on audio and
  Submit (HIGH) only. The payroll control stayed UNSUPPORTED with no card.

**Correction pass (2026-10-29; pilot v3, draft contract v3).** Responses to live v1, with tests in
`tests/test_agent3_corrections.py` (recorded live-v1 failures replayed from
`tests/fixtures/agent3_live_v1_failures.json`) and `tests/test_agent3_request_boundary.py`:
- Open confirmation needs a specific `open_question` and the evidence that leaves it open; it is
  judged as an `open_question` statement and its flag is never cleared. A NEEDS_REVIEW card can carry
  a supported action; approval by a team lead is not an open question.
- The draft fills `coverage` (current guidance, announcements, prior decisions/outcomes, member
  questions); MISSING ties to a follow-up gap. Unassessed or unresearched needs become an OTHER reason.
- Validation is per statement: a quote marked VERBATIM must match; PARAPHRASE is judged semantically;
  a structural failure rejects only that statement and its dependents (an action resting on it), and
  everything else still goes to the judge. A mis-attributed reporter is dropped, not fatal.
- The judge sees every message of every member thread (directory names, roles, reactions) and every
  retrieved source. Names in claims must belong to a cited message's author; CAUSE claims need a
  record or a team lead/engineer message. Recommendations are judged on premises, applicability and
  rationale, not literal prescription (the deterministic "applicable source" rule was removed).
- A clearly preferred, valid ToT candidate becomes the action when the draft has none (`adopt`), then
  goes through final grounding; flags are untouched.
- Live client: per-arm settings (reasoning models get no temperature, `max_completion_tokens`,
  `reasoning_effort`, `service_tier`), a `CostLedger` reserving each request's maximum cost before
  sending (unknown usage charged in full), a 20,000-token input cap checked before sending, and
  RESOURCE / SCHEMA / PROVIDER failure classes. Verified offline against the installed LiteLLM 1.105.0.

**Model comparison v1 (2026-10-29, `data/experiments/agent3_model_comparison_v1/`).** A small
configuration comparison, not a benchmark: 3 cases × 2 arms, one run, no tuning or reruns.
`scripts/run_agent3_model_comparison.py` (zero calls by default). Same prompts (v3 fingerprints in
`experiment.json`), schemas, index `4da16f09…`, corpus `c72edb46…`, rubric and initial retrieval
(verified identical).

| | gpt-4o-mini (temp 0, 4,096 out) | gpt-6.1-sol (medium reasoning, standard tier, 16,384 out) |
| --- | --- | --- |
| Requests | 6 (draft + grounding ×3) | 9 (draft, revision or ToT, grounding ×3) |
| Input / output / reasoning tokens | 57,803 / 4,996 / 0 | 102,026 / 18,621 / 925 |
| Model time | 44 s | 222 s |
| Cost (settled at reported usage) | $0.0117 | $0.3902 |
| Schema / resource failures | 0 / 0 | 0 / 0 |
| Follow-up research | none | 1 (audio: recovered batch-05 trial approval and outcome) |
| Actions proposed / reaching a card | 0 / 0 | 3 / 1 (audio POST_ALIGNMENT) |
| Open confirmation | never set | 2, both specific and judged supported |

Experiment total: 15 requests (cap 24), $0.4019 of $3.00, every HTTP 200 / `finish_reason: stop`.

Reviewed against the cited passages (neither model's grounding verdict is the reference):
- **Baseline:** no actions, no follow-ups; JSON-vs-prose omitted coverage; audio marked prior decisions
  NOT_APPLICABLE although members ask about the earlier workaround; repeated ending proposed MEDIUM
  with no signal. Its judge passed "QN" glossed as "quality notification" (the lexicon defines QN as
  Quarantine).
- **Sol:** claims checked against sources were accurate (names, trial figures, calibration outcome
  2→7 of 8 pairs). Audio: correct four reporters, MIXED resolution matching the threads (both team-lead
  interim-handling threads PARTIALLY_RESOLVED), useful supported action on a NEEDS_REVIEW card. It
  wrongly treated an example-collection note as a directive; the judge rejected it.
- **Supported actions wrongly withheld (pipeline):** in JSON vs prose and repeated ending Sol's
  POST_ALIGNMENT was rejected only because one premise was a team-lead Slack instruction labelled
  GUIDANCE (correctly rejected); the all-premises dependency rule then dropped the action although
  its FAQ/instruction premises were supported.
- **Severity voided in 5 of 6 cases:** both models cited member "happening again" messages as historical
  recurrence; the deterministic rule (records only) is right about the evidence but voids the whole
  assessment instead of setting recurrence to NOT_CHECKED.
- **ToT:** ran on Sol's two open-confirmation cases; never adopted (the drafts already had actions);
  repeated-ending options were all PARTIALLY_SUPPORTED, so none was presented as grounded.

**Completion pass (2026-10-29; pilot v4, draft v4, grounding judgment v3).**
- Action sufficiency: the blanket "every premise must pass" rule is gone. The ACTION statement shows
  each premise with its status (SENT or the rejection code); the judge returns `action_sufficiency`
  (SUFFICIENT/INSUFFICIENT plus the essential premise IDs). The action stands only if SUFFICIENT, the
  essential IDs are premises of this action, and every one of them passed after dependencies.
- Role labels: GUIDANCE resting only on thread messages that include a team lead's is relabelled to the
  scoped `THREAD_INSTRUCTION` kind (recorded as ROLE_LABEL_CORRECTED) and judged for in-thread
  applicability; tutor text labelled guidance still fails.
- Recurrence: historical recurrence (FOUND) must cite retrieved records and is judged as its own
  statement; members' "happening again" messages are reported recurrence. Severity is rebound to the
  unchanged rubric from what passed: unsupported recurrence, signals and reporters are removed, an
  unsupported rationale is replaced by the supported signals' wording, and a level that loses its
  support is UNASSESSED (never lowered or defaulted).
- CrewAI: each stage runs as a Task for a role-specific Agent (researcher, alternatives analyst,
  grounding verifier) in a one-task Crew (max_iter 1, max_retry_limit 0, no tools, memory or planning).
  Verified offline at the transport: one request per stage; CrewAI's forced-final-answer and
  rate-limit retries are refused unsent; Sol requests carry no `stop`; CrewAI 1.15's
  `cache_breakpoint` message marker (left in by its LiteLLM path) is stripped by a subclass; the
  20,000-token input cap is checked on the exact request body; a 4xx configuration rejection or an
  exhausted budget halts further requests while every topic still gets its card.
- Offline replay of the six comparison outputs (`scripts/replay_agent3_comparison.py`,
  `data/experiments/agent3_comparison_replay_v1/`): gpt-4o-mini 21 recorded verdicts reused, 6 PENDING;
  Sol 42 reused, 27 PENDING (severity statements never judged in the original run, action sufficiency,
  two relabelled thread instructions). Pending judgments are never invented and leave content off the card.

**Acceptance pilot (2026-10-29, `data/experiments/agent3_acceptance_v1/`, gpt-6.1-sol, medium reasoning,
standard tier).** One run, no tuning or reruns. `scripts/run_agent3_acceptance.py`.
21 requests (cap 28), all HTTP 200 / `finish_reason: stop`, schema-valid, none blocked; no resource or
configuration failure. 261,299 input / 54,336 output (3,761 reasoning) tokens; largest input 19,118;
650 s model time, 677 s wall. $1.0660 of $6.00 (settled at reported usage; per scenario $0.12–0.26,
payroll control $0.03).

Reviewed against the cited sources (the pipeline's verdicts are not the reference):

| Scenario | Action on card | Severity | Resolution | Notes |
| --- | --- | --- | --- | --- |
| audio_playback | none (withheld) | HIGH[3], 4 correct reporters, recurrence FOUND (batch-05 trial records) | MIXED | Follow-up recovered the trial approval/outcome. Action withheld because the judge named Omar's report essential and that claim was falsely rejected by the name check |
| json_vs_prose | POST_ALIGNMENT | MEDIUM[0]; U018 (a question, not affected) correctly dropped | UNKNOWN | Optional premise rejected, action stood on the remaining premises |
| fictional_pii | UPDATE_DOCUMENTATION: correct only help page v1.0 "Contact details" | HIGH[3] | MIXED | Example-collection note correctly rejected as a directive; a false TEMPORAL_CONFLICT (see below) |
| korean_register | ROUTE_TO_LANGUAGE_SPECIALIST | HIGH[3], recurrence FOUND (batch-10 record) | UNKNOWN | |
| submit_failure | none (withheld) | HIGH[0]+[3], 5 reporters | UNRESOLVED | No "same cause" claim; the open question asks whether the reports match the earlier incident. Escalation withheld (essential premise rested on a rejected announcement) |
| repeated_ending | POST_ALIGNMENT | HIGH[3], 7 reporters | UNKNOWN | No cause asserted |
| payroll control | no card | — | — | UNSUPPORTED |

Pipeline defects found (not fixed in this pass; the run used the code as is):
- **Name check too strict:** 3 claims rejected for naming the owner of a cited message's thread ("In
  Omar's thread, Alex asks…"). All names were correct. Rule should also accept participants of the cited
  messages' threads.
- **Dependency timing:** the judge sees a premise as SENT even when its own announcement verdict will
  void it (Submit C13), so its sufficiency can name a premise that later fails.
- **Temporal rule too strict:** a superseded section against two agreeing current sources is reported
  as an unexplained conflict (`len(current) == 1`).
- **Severity level choice:** HIGH[3] ("multiple distinct people reporting a comparable problem") was
  used for rule-confusion topics (PII, Korean) where MEDIUM[0] ("recurring confusion about the same
  rule") fits more closely; the rubric's wording allows both, and the judge passed both.
- **ToT:** ran on all six topics (five open questions, one conflict); never adopted, as every draft had
  an action. Where the draft action was withheld (audio, Submit) the grounded preferred option exists only
  in the result record.

**Closeout patch (2026-10-30; pilot v5, draft v5, grounding judgment v4, AdviceCard v2).** Replaces the
name-specific presentation work above.
- Presentation: generated prose (summary, claims, rationales, actions, ToT candidates) refers to people by
  role, never by name; models see canonical IDs, roles and thread starters, not display names. Claims carry
  canonical-ID `attributions` (AUTHOR wrote the cited message, THREAD_STARTER started its thread,
  PARTICIPANT posted in it, for participation claims only), checked against the ledger and the user
  directory. A directory name still found in prose is checked the same way (code `NAME_RELATION_INVALID`
  if the relation fails) and then rejected as `PERSONAL_NAME_IN_PROSE`: the card uses roles and nothing is
  rewritten. Role wording ("the team lead instructs") must match a cited author's role; plural wording needs
  that many distinct cited authors (or topic reporters when no member message is cited). Quotations are
  not checked or changed. The final grounding judges the role-based text and the attributions. Card v2
  lists related threads with a short label and the stored permalink, or the thread ID (the fixtures store
  no permalinks). A guard reports any name left in card text (for example an Agent 2 topic title).
- Dependency order: premises are shown to the judge as `PENDING_YOUR_VERDICT` with `depends_on` (the
  announcement a guidance premise rests on), never as final; the rules order announcement applicability →
  final premise status → sufficiency; essential premises are validated against the final supported set
  (`ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY` when the judge supported a premise its dependency voided).
- ToT fallback: the judge also returns `alternative_sufficiency` for each operational alternative. When the
  draft action does not reach the card, the model's preferred candidate replaces it only if it was not a close
  call, is valid with no issue (presentation checks included), its exact text was judged SUPPORTED, and its
  sufficiency check passed. Review reasons are unchanged.
- Temporal: one current source still explains a superseded section by record; several applicable current
  sources do so only if a non-blocking `SOURCE_AGREEMENT` statement is judged SUPPORTED. Uncertain
  applicability (unresolved/unverified revisions, upstream review, an unverified announcement) or a real
  disagreement stays DETECTED.
- Regressions (`tests/test_agent3_corrections.py`, recorded items in
  `tests/fixtures/agent3_acceptance_v1_cases.json`): the three observed false name rejections (the
  relations hold), wrongly attributed participants, the Submit dependency inconsistency (recorded Sol
  judgment → `ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY`), a valid ToT fallback and four refusals, agreeing
  versus disagreeing or uncertain current sources. 764 offline tests pass.

Zero-call replay of the acceptance responses (`data/experiments/agent3_acceptance_replay_v1/`): 115
recorded verdicts reused, 19 pending (18 action/alternative verdicts, whose premises are now shown
differently, and one source agreement). All 30 recorded statements that name people are valid relations by
canonical ID (no `NAME_RELATION_INVALID`); as v5 prose they are rejected as names. The replay cannot verify
v5, so one live run followed.

**Closeout live run (2026-10-30, `data/experiments/agent3_closeout_v1/`, same Sol arm, six topic scenarios,
`scripts/run_agent3_closeout.py`, $3 ledger).** One run, no tuning or reruns. 18 requests sent (all HTTP 200,
`finish_reason: stop`, schema-valid); 2 refused unsent by the input cap (audio revision 20,477 tokens,
Submit revision 20,887). 230,556 input / 48,599 output (4,731 reasoning) tokens; 662 s model time;
$0.9471. Reviewed against the threads:
- No personal name in any draft or card; 57 attributions, none rejected; every role and count statement was
  correct (for example "two QA tutors and three tutors" for Submit's five reporters; repeated ending notes one
  tutor posting in two threads).
- Actions on the card: audio POST_ALIGNMENT (withheld in acceptance), JSON vs prose POST_ALIGNMENT, PII
  UPDATE_DOCUMENTATION (Contact details only), Korean ROUTE_TO_LANGUAGE_SPECIALIST, repeated ending
  POST_ALIGNMENT. Submit: withheld; the judge itself applied the dependency order (the action's use of the
  announcement thread rests on c7, whose announcement fails) and found it INSUFFICIENT; the ToT fallback was
  correctly refused (preferred candidate PARTIALLY_SUPPORTED).
- PII: the superseded help-page section against the FAQ and the verified clarification is now resolved by
  judged agreement; the status-note conflict (no superseded material) stays DETECTED.
- Severity: audio HIGH[0]+[3], Submit HIGH[0]+[3], repeated ending HIGH[3]; JSON vs prose MEDIUM[0] (U018
  dropped again); PII MEDIUM[1] and Korean MEDIUM[0] (HIGH[3] in acceptance). The rubric is unchanged, so the
  level choice for rule-confusion topics varies between runs; the wording remains a team-lead decision.

Remaining defects after the closeout:
- **Input cap blocks revisions:** v5 payloads (attributions, thread starters, longer rules) pushed the audio
  and Submit revisions over 20,000 tokens. Their follow-up evidence was retrieved but never used; audio's open
  question ("did the trial establish anything?") was judged unsupported because the trial outcome it asks
  about was in that evidence. Needs a decision: raise the cap or slim the revision payload.
- **ToT fallback not exercised live** (the one candidate it needed was correctly refused); covered offline only.
- **Prose checks are heuristic:** directory-name, role-verb and plural patterns (English, double quotes only);
  the final grounding remains the semantic check.
- **Severity level choice** for rule-confusion topics (above); per-member resolution withheld for one member
  in three scenarios (judged PARTIALLY_SUPPORTED); Korean ToT candidates overstated applicability.

**Readability and state pass (2026-10-30; pilot v6, draft v6, ToT v2, AdviceCard v3, prompts v6 then v6.1).**
- Card v3 answers what happened (`summary`), what the team lead should do (`recommended_action.label`, a fixed
  familiar label such as "Post a reminder" or "Report a technical issue to engineering"; `instruction`, one
  sentence), why (`rationale`) and what still needs review (`review_notes`, plain language). `draft_text` is the
  copyable draft, separate from the instruction. Enums, claim and evidence IDs, essential premises
  (`essential_premise_ids`), documentation targets (`targets`, by title and section) and processing errors are
  structured fields; `needs_review_reasons` keeps the internal codes. The final grounding judges exactly the
  displayed action text (label, instruction, draft, scope, changes), a separate non-blocking ACTION_RATIONALE and
  REVIEW_NOTE; an unsupported rationale or note is withheld without dropping the action.
- Display-text checks: no raw evidence/claim/user/member IDs, enum names or premise lists (`RAW_ID_IN_PROSE`); a
  double-quoted passage of five or more words must match a cited source exactly (`QUOTE_NOT_IN_SOURCE`). Quotations
  stay exempt from role rules and are never changed. A guard reports any ID or name left in card text.
- Prompts: a writing guide (writing targets, not limits: summary 1-2 sentences, one-sentence instruction, 1-2
  sentence rationale, announcement about 60-120 words) and two fictional STYLE ONLY, NOT EVIDENCE examples
  (an image-captioning reminder, a video-timestamp escalation) in the draft and revision rules.
  `PROMPT_VERSION` and fingerprints of the guide and examples are recorded in every manifest.
- Truncation trace: stored card text was complete; the cuts in the shared sample came from the display script.
  Real cuts were in storage (review-reason details at 300/900 characters, inherited Agent 1 review text at 600,
  thread labels at 70) and in the model input (Agent 1 rationale/review reason at 400/600); serialization cut
  nothing and every live response ended with `stop`. All of these are removed. A thread label quotes the opening
  message's first sentence only if it is complete and at most 100 characters; `opening_text` stores the full message.
- State: review reasons come from the final validated results. An open question the final grounding did not
  support is no longer an OPEN_CONFIRMATION reason (it stays a withheld statement; the check reads NONE). Coverage
  distinguishes not researched, follow-up not run, nothing new found, still missing after revision, and records
  retrieved but not incorporated because the revision did not run. Replay reproduces a recorded stage failure with
  its recorded class.
- Input cap 24,000 tokens (reservation $0.212 per Sol request; acceptance worst case $5.93 of $6, other limits
  unchanged). The rules were sent twice per request (task text and JSON body); now once.

Offline first: zero-call replay of the closeout responses (`data/experiments/agent3_closeout_replay_v1/`): 128
verdicts reused, 22 pending (changed display text). Every recorded v5 summary carried bracketed evidence IDs and
is rejected as `RAW_ID_IN_PROSE`; audio's unsupported open question is no longer a review reason; audio's coverage
reads "follow-up retrieved 3 item(s) but they were not incorporated (revision FAILED (RESOURCE))".

Live (`data/experiments/agent3_readability_v1/`, `scripts/run_agent3_readability.py`, audio and Submit, prompts v6,
same Sol arm): 6 requests (cap 8), all HTTP 200 / `stop`; 85,907 input / 19,596 output (1,160 reasoning) tokens;
228 s model time; $0.3678 of $2.00. Audio's revision ran (19,009 input tokens) and used the trial records.
- Both cards now carry an action: audio "Post a reminder" (103-word draft) and Submit "Report a technical issue to
  engineering" (115-word draft listing the four threads by task, no shared cause asserted); Submit was withheld in
  the acceptance and closeout runs. No name or internal ID in either card; summaries are two sentences; reporter
  counts and roles match the threads. Submit keeps its supported open question; audio has none.
- Found and fixed offline after the run (not rerun live): (1) "In two tutors' threads, the team lead says ..." was
  rejected because the plural check counted the cited authors (one team lead); a possessive plural now counts the
  threads' starters. This also withheld audio's HIGH[0] signal (severity rested on HIGH[3]). (2) A record
  attributed to the team lead as AUTHOR was rejected; AUTHOR now holds for a record whose authority actor is that
  user. (3) Audio's review note about open upstream flags was judged unsupported because the judge did not see the
  flags; grounding now receives `open_review_flags` (prompts v6.1). The zero-call replay
  (`data/experiments/agent3_readability_replay_v1/`) shows the three statements no longer rejected and pending a
  judgment the run did not make.

Remaining after this pass: the three fixes above are verified only offline; the ToT fallback is still not exercised
live; prose and display checks are pattern-based; the severity level choice for rule-confusion topics remains a
team-lead rubric decision.

**Needs a real model evaluation (not shown by these tests):**
- whether the Advisor names the right gaps and follow-up queries unprompted;
- whether it keeps incident facts and guidance apart and cites precisely;
- whether it avoids inventing causes, approvals or counts;
- its announcement assessments (relevance and directive content) and documentation targets;
- its per-member resolution states;
- its severity proposals against the rubric, and affected-reporter identification;
- whether its open-confirmation and conflict judgments are right;
- statement-level grounding accuracy, including false PASS/FAIL rates on the larger statement set;
- the quality and diversity of ToT candidates;
- JSON validity rates with one attempt (each invalid output costs a stage);
- whether 4 calls per topic is enough.

**Remaining limitations.**
- Every pilot topic carries upstream obligations, so every card is NEEDS_REVIEW; RECOMMENDED_ACTION and OBSERVATION routing is covered only by tests.
- Initial-query construction is a fixed rule; in the real index the playback announcement already ranks in the top 5, so recovery runs only in tests.
- ToT triggers are computed before the final grounding (from the draft and the pre-grounding temporal check). The card's temporal result is recomputed after grounding with verified announcements only.
- Resolution has no state for "answered by current guidance but not in the thread"; such members are UNRESOLVED with that basis.
- On HTTP 429, CrewAI's rate-limit wrapper still waits its backoff (1–8 s, or Retry-After) before the guard refuses the retry. `RequestGuard` patches the httpx transport class for the duration of one call, so the client is single-threaded.
- Group members outside the selected topic are reported as outside this card. They are not dropped, but this pilot does not process them.

**Test reliability (investigated 2026-10-29).**
- ChromaDB "Nothing found on disk": reproduced with `tests/repro_chroma_reopen.py` (isolated temp
  directories outside the repo). Cause: `build_index` released its client with `del`, which
  leaves the Chroma system cached per path; the in-process `Retriever` then reused that cached
  system and intermittently failed to read the HNSW segment. The subprocess readability check is
  not the cause: a single-process variant failed too. Unclosed: 10 failures in 320 build→open
  cycles; closed: 0 in 260. Fix: `client.close()` after the build (regression test
  `test_build_releases_its_chroma_client`). No sleeps or retries.
- Agent 1 `test_200_mixed_mocked_outcomes_continue_after_flagged_and_failed_middle_records`: the
  full-suite failure's traceback was not captured, so its cause is not known. Repeated alone with
  full logs (`.cache/test-logs/agent1-*.log`): with `--basetemp` inside the repo it failed 3 of 20
  runs, each with `PermissionError [WinError 5]` from `os.replace` overwriting
  `verified_v1/content_review_report.json` (`scripts/run_agent1_verification.py:50`; the runner
  rewrites four report files after each of 200 records, about 800 replaces per test, and closes every
  handle it opens). With `--basetemp` outside the repo: 0 of 20. That points to another process briefly
  holding the freshly written file in the repo tree, but the comparison is not conclusive (one-sided
  Fisher p about 0.12) and the process was not identified. The runner is fingerprinted, so it is
  unchanged; use a `--basetemp` outside the repo.
