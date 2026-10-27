# Agent 2 uncertainty handoff and eight-group validation

Completed 2026-10-25. **Proceed toward Agent 3 input integration with provisional
limitations.** This applies the user's new acceptance policy: useful, plausible
interpretations may proceed with uncertainty and evidence. Historical findings and
HOLD decisions remain unchanged. This is a Codex-assisted source review, not human
approval, independent ground truth, an unbiased accuracy benchmark or a calibration study.

## Execution and integrity

- **8 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED; 0 unprocessed selected groups.**
  Eight attempts, eight HTTP responses and completed drafts, zero unknown completions
  or unmatched start markers. Every response returned the requested snapshot with `stop`.
- **23 unique identities, 61 messages, five inherited obligations** across four
  projects. Member statuses: 10 VERIFIED, 8 CORRECTED, 5 NEEDS_REVIEW. Exact source
  quotations, actual reaction users/targets, hashes, lineage and Agent 1 metadata retained.
- Ten exported topics: **one HIGH and nine UNKNOWN**. HIGH created a nonblocking
  obligation even with no inherited flags in that group. Five groups required review
  before assisted review and five afterward; two new findings are within an already
  provisional group. All findings remain visible through the mandatory loader.
- All frozen requests match executed bytes. All eight outputs passed the provider
  shape and application checks; this does not establish semantic correctness.
  Aggregate results, per-record results and queues match exactly.
- No original-six group or v5.3 control was selected. The repeatedly examined Audio
  group `cluster_6b59d13144282285` was used only in offline handoff regressions.
  The other 82 groups / 177 identities were outside this live scope.

Configuration: `openai/gpt-5.4-2026-03-05`, `reasoning_effort=low`,
`max_completion_tokens=8192`; temperature, top_p and logprobs absent from actual
requests. Prompt `agent2-inventory-v6`, strict response schema 6, unchanged
`provisional-operational-severity-v2` and `inventory-to-display-v3`. One attempt
per group, zero retries, repairs, fallbacks or extra verifier calls. No production
code changed after the freeze or during/after execution.

## Source review of every group

Coverage is members / messages / inherited obligations. Every row is CONSOLIDATED.
Source-bound details and exact affected fields are in `review_supplement.json`.

| Group | Coverage | Assisted source assessment | Severity | Detection before assisted review |
| --- | --- | --- | --- | --- |
| `cluster_aa0548b34bd2cbdc` — quieter room | 1 / 2 / 0 | Supported reported facts; no invented question or consequence. Social versus work-context severity boundary is benign. | UNKNOWN | Model states insufficient impact; N/A alternative was considered only during review. No new dispute required. |
| `cluster_6042d88a3d171626` — correspondence/silence | 4 / 9 / 1 | Recording/reference direction correct; silent-track question kept separate and open. Local TL-endorsed correspondence answer retained. Exact scoring-field allocation lacks a scope note; another note overstates “only” follow-up. | UNKNOWN × 2 | Open questions/notes and broad provisional routing existed. The **two specific concerns were discovered afterward**, not self-detected. |
| `cluster_db20d884110726af` — Japanese register | 3 / 9 / 2 | Penalty/scoring decisions remain open; boundary forms, discourse conditions and TL requests retained. | UNKNOWN | Model notes expose missing context and uncertain recurrence; automatic handoff keeps all three questions. |
| `cluster_6ac8dcc3e5d75776` — Vietnamese locale | 4 / 10 / 1 | North/south directions and conditional locale guidance preserved; no transferred answer or false thumbs-up authority. | UNKNOWN | Both unanswered acceptability questions and specific locale notes present before review. |
| `cluster_608d1e987c058c11` — submission blockage | 4 / 13 / 0 | Disabled/click/loop differences retained. Vague clarification request reasonably OPEN with cause-versus-handling note; do-not-count-complete guidance survives. | HIGH | Model surfaces question ambiguity and actual task blockage; automatic HIGH review exists before assisted review. |
| `cluster_7a710abcd893e0a6` — quoted warnings | 4 / 11 / 1 | Plausible indirect contextual answer retained with explicit missing-class-label note; another label decision remains partial. TL `this` and `eyes` scopes correct. | UNKNOWN | Model explicitly notes uncertainty for both ANSWERED and PARTIAL judgments; all questions retained automatically. |
| `cluster_098a12c005ecf00b` — announcements | 2 / 4 / 0 | Resource and deadline split appropriately; null representative questions, no invented completed action. | UNKNOWN × 2 | Model states no demonstrated operational consequence. No material concern found in review. |
| `cluster_e849ac33e11b49fe` — requested table | 1 / 3 / 0 | Useful TL instruction/factuality distinction recognized; unresolved major/minor choice remains explicit and PARTIAL. | UNKNOWN | Model difference and question note identify residual choice; automatic `research_required=true`, although this group is outside the ordinary review queue. |

Two separately registered findings concern correspondence:

1. **Plausible resolution with a missing scope note.** E004 asks “Should we score
   omissions in the audio or errors in the transcript field?” E006 gives local
   correspondence-error rather than playback-failure handling, endorsed by TL U006.
   That is a defensible practical answer, but it does not explicitly allocate a score
   to one field. The model chose ANSWERED at **0.95 with no note**. Agent 3 should
   preserve that narrower uncertainty while retaining the useful local guidance.
2. **Minor note error.** The M01 note says the “only follow-up” is a clarification
   request. E002 also explains that the text's sentence is absent from the recording
   and that the player need not be broken. The full fact and relevant difference are
   retained; no source or guidance is lost. The note should not substitute for the
   original inventory.

Neither concern was specifically detected by the model or automatic handoff.
Existing inherited/coverage flags already made the first topic provisional and
kept its questions researchable; that general containment is **not** self-detection.
The new supplement preserves the raw 0.95 score, status and original answers alongside
effective DISPUTED status. Under the updated policy these bounded concerns do not
block downstream research. No uncontained consequential error was found in this sample.

## Contract and confidence behavior

Schema 6 adds only two required nullable question fields: `resolution_confidence`
and source-bound `uncertainty_note`. Existing status/links encode the chosen resolution.
The parser rejects missing new fields; explicit saved-v5 replay uses the preserved
v5 contract. No historical score is fabricated and no raw response is upgraded.

The effective loader exposes `records[].research_handoff` with every exported question,
its original message, raw judgment/score, source-bound note, linked answers, same-member
guidance, full member/source records, topic inventory and review obligations.
Historical missing confidence is null. Existing Audio M05's Quarantine decision and
the disputed context-as-answer remain inspectable without rerunning or clearing them.

All **13 questions** are research-accessible: 9 OPEN, 2 PARTIAL, 2 ANSWERED. All have
numeric scores (**0.41–0.95**); 12 have specific notes, including one ANSWERED question.
High confidence in OPEN may reflect confidence that a question remains unresolved.
These are uncalibrated self-assessments, not probabilities; the 0.95 scope limitation
shows they cannot safely filter out source inspection. Scores remain independent of
severity and inherited flags. Low confidence never supplies missing evidence.

Agent 3 must consume **all effective records**, not only `open_questions` or
`review_queue`. In particular, the table case needs research despite having no inherited
or ordinary group-level flag. The handoff guarantees access to every exported question,
not perfect recognition of every implicit source question. Failed groups retain original
sources and obligations even when no valid question inventory exists.

## Offline checks, usage and commands

**158 focused tests passed; 524 full-suite tests passed, 0 failed, 0 skipped**
(162 warnings). Full-suite time: 279.93 seconds. Catalog and Slack checks passed
for 200 identities, 12 channels and 316 replies; `git diff --check` passed.
Saved Audio/context regressions, strict request fields, citation scope, historical-null
confidence, dispute preservation and failed-group source retention are covered.

Usage: **40,925 input tokens** (19,712 cached), **11,345 output tokens** including
5,557 reasoning tokens; total 52,270. Summed request latency 130.28 seconds,
mean 16.28 seconds, range 9.23–26.35 seconds. Estimated standard token cost
**$0.2281**, against a frozen full-output budget estimate of **$1.1250**.
Rates were checked against the [official GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4):
$2.50/M input, $0.25/M cached input, $15/M output. This is an estimate, not an invoice.

Exact full-suite command used:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-uncertainty-full --junitxml .cache/agent2_uncertainty_v6/full-tests.xml
```

Exact dry-run and live commands used, after the offline gate passed:

```powershell
$env:THREADSENSE_MODEL='openai/gpt-5.4-2026-03-05'
$env:THREADSENSE_AGENT2_REASONING_EFFORT='low'
.venv\Scripts\python.exe -X utf8 scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-uncertainty-pilot-v6.json --max-requests 8 --output-dir data/processed/agent2_uncertainty_v6
.venv\Scripts\python.exe -X utf8 scripts/run_agent2_batch.py --run --pilot docs/agent2-uncertainty-pilot-v6.json --max-requests 8 --output-dir data/processed/agent2_uncertainty_v6
```

These record the completed execution, not permission to rerun it. All eight authorized
attempts are consumed. The post-run review-registry update intentionally differs from
the execution fingerprint. Do not bypass it or reuse the completed destination.

Fresh **offline-only** effective export, if needed:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_uncertainty_v6 --output data/experiments/agent2_uncertainty_v6/effective_refresh.json
```

## Handoff and next decision

Proceed toward a separately authorized Agent 3 input-integration milestone using the
mandatory complete effective view. Carry both new findings and all historical disputes,
retain raw judgments alongside researched conclusions, and keep research nonblocking.
No further Agent 2 calls, prompt changes or full-dataset run were performed or prepared.

Remaining limitations: deliberate small selection; mostly English discussion of
multilingual tasks; no live N/A/LOW/MEDIUM, refusal, truncation, interruption or failure
case. Those operational failure paths have offline test evidence only. This run does
not demonstrate that old Audio semantics are corrected, establish calibration, or
certify the other 82 groups. Continue source inspection for implicit questions and
exact answer scope; preserve the model's specific notes without treating them as evidence.

Artifacts:

- Canonical results, manifest, raw evidence and original automated queues:
  `data/processed/agent2_uncertainty_v6/`.
- Freeze, prepared-request hashes, source bindings, pre-run criteria, cost estimate,
  request ledger, execution audit, XML test receipts and this report: this directory.
- New exact-candidate review: `review_supplement.json`; mandatory registry:
  `docs/agent2-review-supplements.json` (all eight earlier entries retained).
- Refreshed handoff: `effective_output.json` (includes effective review queue and
  all research inputs); validation: `effective_check.json`.
- Policy and input contract: `docs/agent2-provisional-acceptance-v1.md`.
- Final preservation receipt: `final_preservation.json`.

Implementation changes: `topic_contracts.py` adds the two fields; `topic_contracts_v5.py`
preserves historical decoding; `topic_consolidation.py` delivers the instructions,
checks same-member note references and supports explicit v5 replay. `topic_requests.py`
and `topic_pipeline.py` version/fingerprint the schema. `topic_effective.py` derives
the complete research input; `prepare_agent2_pilot.py` recognizes reviewed v6 upgrades.
Focused tests and existing synthetic fixtures were migrated without changing saved
responses or weakening their original assertions. No Agent 3 implementation was added.
