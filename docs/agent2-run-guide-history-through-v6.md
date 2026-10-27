# Agent 2 run guide — response schema v6

## Current milestone: completed uncertainty handoff and eight-group validation (2026-10-25)

**Decision: proceed toward Agent 3 input integration with provisional limitations.**
The [new user acceptance policy](agent2-provisional-acceptance-v1.md) permits plausible
interpretations with useful uncertainty; it preserves historical findings and decisions.
It prioritizes consequential errors and review containment rather than zero flags.

Eight new groups outside the original six and two v5.3 controls produced **8 CONSOLIDATED,
0 FAILED, 0 INTERRUPTED**, eight attempts/responses, zero unknown completions and zero
unprocessed selected groups. All **23 identities, 61 messages and five inherited
obligations** remain, plus one nonblocking HIGH obligation. The repeatedly examined
Audio case was not rerun. No remaining full-dataset processing is authorized.

Schema 6 adds only required nullable question-level `resolution_confidence` and
source-bound `uncertainty_note`. Prompt `agent2-inventory-v6` explains them in actual
requests. Snapshot `openai/gpt-5.4-2026-03-05`, low reasoning, sampling omission,
8192-token limit, severity rubric v2, inventory and existing checks remain fixed.
Explicit historical v5 replay preserves missing confidence as unknown; it cannot
silently satisfy the new production parser.

The mandatory effective loader now exposes `records[].research_handoff`, contract
`agent3-research-input-v1`. Read **all records and every question**, including ANSWERED,
with original sources, judgments, raw scores, notes, guidance and review obligations.
Neither `open_questions` nor `review_queue` alone is a complete research input. A
PARTIAL table-scoring question requires research even though its group has no inherited
or ordinary review flag. Historical Audio/context disputes remain visible offline.

All 13 questions have scores; 12 have notes, including one ANSWERED question. Scores
are uncalibrated self-assessments, not probabilities or permission to clear disputes.
Assisted source review found no uncontained consequential error in this sample. It
added two bounded correspondence findings: the 0.95 ANSWERED judgment omits a narrower
scoring-field uncertainty, and another note incorrectly says there was only one type
of follow-up. General provisional routing existed before review; these specific
concerns were **not** self-detected. Raw outcomes and scores remain unchanged.

Validation: **158 focused / 524 full-suite tests passed, zero failures or skips**,
plus catalog, Slack and preservation checks. Usage: 40,925 input tokens (19,712 cached),
11,345 output tokens including 5,557 reasoning; estimated cost $0.2281. Eight requests
are exhausted. The new review entry intentionally changes the registry fingerprint;
do not rerun the completed selection or bypass that check.

See the [eight-group report, findings, limits and exact executed commands](../data/experiments/agent2_uncertainty_v6/milestone_report.md).
Canonical artifacts: `data/processed/agent2_uncertainty_v6/`. Source-bound review,
request ledger and refreshed effective handoff: `data/experiments/agent2_uncertainty_v6/`.
To make another offline-only effective view, use a fresh output filename:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_uncertainty_v6 --output data/experiments/agent2_uncertainty_v6/effective_refresh.json
```

Next: integrate Agent 3's input in a separately authorized milestone. Carry the full
question inventory, original Slack and every obligation into research; store researched
conclusions separately. No Agent 3, retrieval or dashboard implementation was added.
The small selected sample does not certify the other 82 groups or confidence calibration.
N/A/LOW/MEDIUM and live failure paths remain unvalidated by this run.

## Historical milestone: completed v5.3 contrastive diagnostic (2026-10-25)

**Decision: hold broader validation.** One bounded experiment used all three
authorized requests: **3 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED**, three saved
responses, zero unknown completions and zero unprocessed groups. All **14 identities,
42 messages and five inherited obligations** remain. No retries, repairs, fallback
models, additional verifiers or reasoning escalation occurred.

Prompt `agent2-inventory-v5.3` adds one compact synthetic contrast: reporting-location
guidance can completely answer a reporting question while leaving submission
eligibility undecided. Illustrative `SYNTH_*` references are explicitly excluded from
actual citations and fail the existing validator. The example also distinguishes
substantive partial answers, complete decisions, indirect unambiguous answers and
authority alone. No pilot text, IDs, control labels or review judgments were added.

Model `openai/gpt-5.4-2026-03-05`, `reasoning_effort=low`, omitted sampling parameters,
`max_completion_tokens=8192`, rubric `provisional-operational-severity-v2`, strict
schema 5, single inventory, validators and export semantics stayed fixed. Low
reasoning remains under evaluation. No production code changed after execution began.

| Group | Coverage / inherited obligations | Automated outcome and assisted source review |
| --- | --- | --- |
| Audio `cluster_6b59d13144282285` | 6 members / 19 messages / 2 obligations | CONSOLIDATED. M05 remains fully ANSWERED without settling Quarantine. M06's different playback-handling question is judged separately, with a scope limitation. Conditions retained; silence UNKNOWN and playback HIGH remain supported. |
| Complete-answer control `cluster_f944891544b06f79` | 5 / 13 / 2 | CONSOLIDATED. M02's scoped tie answer and actual TL endorsement remain recognized. A separate task description E002 is incorrectly labeled TENTATIVE ANSWER. M01's qualitative threshold/local-example scope remains uncertain. UNKNOWN severity supported. |
| Procedural control `cluster_1f272d7fa384df0c` | 3 / 10 / 1 | CONSOLIDATED. M02 category decision remains OPEN with useful procedure retained. Collection announcement keeps a null root question and no-final-decision condition. UNKNOWN severity supported. No material finding in this assisted review. |

Controls were selected from original Slack sources outside the original six cases;
their criteria were frozen before any new response. Hidden evaluation labels and
historical Agent 2 control outputs were not used for selection. These diagnostic
cases test premature closure and unnecessary reopening; they are not an unbiased
accuracy sample, and this review is not human approval or independent ground truth.

The existing contract can represent these distinctions with OPEN/PARTIAL questions,
separate guidance, FACT/CONTEXT and scoped ANSWER items. The model did not reliably
apply it. A dedicated residual-subquestion text field is absent, but that does not
require or justify fully closing M05. No schema expansion or automatic relabeling
was introduced. Stop this experiment; use its retained failures for separately
authorized offline diagnosis before choosing another intervention. The conditional
eight-group validation was **not prepared or executed**.

Validation: **57 focused tests and 514 full-suite tests passed; zero failures or
skips**, plus catalog/Slack and preservation checks. Usage: **17,529 input + 5,760
output tokens**, including 2,581 reasoning tokens, zero cached input. All responses
returned the requested snapshot with finish reason `stop`. Latencies: Audio 20.92s,
complete-answer control 26.84s, procedural control 23.40s. Audio's historical
low-reasoning latency was 26.37s; one sample is not a performance guarantee.

Two material findings and three scope uncertainties are bound to the actual new
source/raw/export hashes. The mandatory registry retains its seven earlier entries
and adds this experiment. The refreshed effective view exposes all five inherited
obligations, HIGH review and new findings, with zero stale bindings. All three
groups remain available for nonblocking processing; original outcomes and raw
artifacts are unchanged.

See the [v5.3 report and exact commands](../data/experiments/agent2_contrastive_v5_3/milestone_report.md).
Canonical artifacts: `data/processed/agent2_contrastive_v5_3/`.
Freeze, ledger, source review and refreshed effective view:
`data/experiments/agent2_contrastive_v5_3/`. For a fresh offline export:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_contrastive_v5_3 --output data/experiments/agent2_contrastive_v5_3/effective_refresh.json
```

Do not rerun the completed pilot or bypass its fingerprint. The post-run review
registry update intentionally differs from its execution freeze. No further live
request is authorized for this milestone.

## Historical milestone: v5.2 low-reasoning comparison (2026-10-25)

**Decision: hold broader validation.** Two authorized requests produced **2
CONSOLIDATED, 0 FAILED, 0 INTERRUPTED**, two saved responses, zero unknown completions
and zero unprocessed groups. All **8 identities, 23 messages and 2 inherited
obligations** are retained. There were no retries, repairs, fallback models or
additional verifiers. The two-request authorization is exhausted.

Model `openai/gpt-5.4-2026-03-05`, prompt `agent2-inventory-v5.2`, rubric
`provisional-operational-severity-v2`, schema 5, glossary, inputs, validators and
export semantics stayed fixed. The opt-in configuration
`THREADSENSE_AGENT2_REASONING_EFFORT=low` removes temperature, top_p and logprobs
from the actual HTTP body and retains `max_completion_tokens=8192`, shared by
reasoning and visible output. The default remains `none`; no `.env` change was made.
The saved baseline used `none` and temperature 0. This is a historical configuration
comparison, including required temperature omission, not a causal ablation.

| Group | v5.2 none → low | Assisted source review and retained obligations |
| --- | --- | --- |
| Alignment `cluster_1ba596334ad5cde7` (2 members / 4 messages) | CONSOLIDATED → CONSOLIDATED; UNKNOWN → UNKNOWN | Improved: version/date request and explicitly withheld supersession decision remain guidance/FACT, no DIRECT ANSWER. Both precedence questions remain OPEN. Zero inherited obligations; the new candidate has no applicable content finding. Historical findings stay attached to the old output. |
| Audio `cluster_6b59d13144282285` (6 members / 19 messages) | CONSOLIDATED → CONSOLIDATED; one HIGH topic → silence UNKNOWN / playback HIGH | All members, conditions and two inherited obligations retained. M05 still incorrectly ANSWERED although reporting/do-not-score guidance does not settle Quarantine. M06's player-issue alternative is more directly addressed; preserve its substantive handling answer with an explicit Quarantine-policy limitation. HIGH routes nonblocking review. |

One material M05 finding and one separate M06 scope uncertainty are bound to the
new source/raw/export hashes. The mandatory registry now contains seven entries,
preserving all six previous entries. Its refreshed effective view exposes both new
review obligations, the two inherited obligations and HIGH review; zero stale
bindings. One group requires review. Original outcomes, texts, ledgers, freezes and
run-local effective snapshots remain unchanged.

Validation: **53 focused tests and 510 full-suite tests passed; zero failures or
skips**. Catalog/Slack checks, frozen-request equality, all-source accounting and
post-run preservation checks passed. Usage was **10,010 input + 3,376 output tokens**,
including **1,243 reasoning tokens**, zero cached input. Request latencies were
13.49s and 26.37s, versus 6.91s and 9.73s historically. Both responses returned the
requested snapshot with finish reason `stop`; neither exhausted the token budget.

The remaining problem is complete-versus-partial question scope, despite improved
procedural classification. Recommended next intervention, requiring separate
authorization: one synthetic contrasting example of a reporting-only question
versus a separate disposition decision, preserving genuine complete handling
answers. Do not automatically raise reasoning, relabel responses, weaken validators
or begin another prompt/call loop. The conditional eight-group validation was
**not prepared or executed** because the material blocker remains. Multilingual,
non-operational, announcement and genuine reaction-endorsement behavior remain
untested by this two-group live experiment.

Full evidence, exact executed commands and cost comparison:
[low-reasoning report](../data/experiments/agent2_reasoning_low_v5_2/milestone_report.md).
Canonical results: `data/processed/agent2_reasoning_low_v5_2/consolidations.json`.
Freeze, ledger, review and refreshed effective view:
`data/experiments/agent2_reasoning_low_v5_2/`. For a fresh offline downstream export:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_reasoning_low_v5_2 --output data/experiments/agent2_reasoning_low_v5_2/effective_refresh.json
```

Do not rerun the completed pilot or bypass its fingerprint. The post-run review
registry update intentionally differs from the execution freeze. This assisted
source review is not human approval, independent ground truth or an accuracy benchmark.

## Historical milestone: focused v5.2 impact/scope correction and two-request revalidation

Completed the authorized run: **2 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED; 2 attempts,
2 saved responses, 0 unknown completions, 0 unprocessed groups**. Both HTTP 200
responses completed normally. All **8 identities, 23 source messages and two
inherited obligations** remain, with exact candidate/source hashes, evidence and
lineage. Canonical inputs remain 200 records in 90 groups. No Agent 1, grouping,
model, dependency, transport or strict-schema change occurred.

Prompt `agent2-inventory-v5.2` clarifies evidenced operational consequences/risks
and full versus partial question resolution. Rubric
`provisional-operational-severity-v2` changes only MEDIUM's definition: clarification
requires an evidenced consequence or a risk with a source-supported mechanism;
clarification alone is insufficient. V1 objects and historical artifacts remain
unchanged. Export adapter `inventory-to-display-v3` adds `inventory_counts` for
distinct original members with ANSWER items and with guidance (ANSWER, INSTRUCTION
or DIAGNOSTIC_REQUEST). Counts describe returned classifications, not proven answers
or reliability. Schema 5 and existing validators remain unchanged; no prose repair
or automatic semantic relabeling was added.

| Case | Automated outcome, v5.1 → v5.2 | Source-review comparison |
| --- | --- | --- |
| Alignment `cluster_1ba596334ad5cde7`, 2 members / 4 messages | CONSOLIDATED → CONSOLIDATED | MEDIUM → supported UNKNOWN. Both precedence questions OPEN; exact version/date and withholding conditions retained. The procedural withholding reply is still also an unlinked DIRECT ANSWER. This classification remains disputed; its one-answer-member count is mechanically correct for an incorrect semantic tag. |
| Audio `cluster_6b59d13144282285`, 6 members / 19 messages / 2 inherited obligations | CONSOLIDATED → CONSOLIDATED | HIGH retained at supported affected-task scope; previous one-thread summary error removed. Export counts two answer members and six guidance members without counting repeated items twice. M05 is still ANSWERED although the reply does not settle its explicit Quarantine decision. Scope finding remains; all conditional TL guidance and inherited obligations survive. |

**Readiness: hold broader validation.** These are material scope/classification
findings against actual new candidates, not objections to UNKNOWN, HIGH or review
flags. Useful procedural responses still become answers or complete resolution.
The conditional eight-group validation was **not prepared or executed**. No second
correction loop, prompt edit or paid call followed the results. All two authorized
attempts are consumed. These repeatedly examined cases are regression checks;
the Codex-assisted source review is not human approval, independent ground truth
or an accuracy benchmark.

Final validation: **136 focused tests passed; 502 passed, 0 failed, 0 skipped** in
the full suite. An earlier full pass attempt found one compatibility failure:
explicit legacy v3/v4-to-v5 preparation needed to record/permit the new rubric and
export version metadata. It was fixed before execution; the final full suite passed.
Source/catalog validation and post-run integrity checks passed. The exact commands,
file changes, source evidence, limitations and request usage are in the
[v5.2 milestone report](../data/experiments/agent2_focused_v5_2/milestone_report.md).

Usage: **10,010 input + 1,586 output = 11,596 tokens**, zero reported cached/reasoning
tokens. Both requested and returned models are `gpt-5.4-2026-03-05`, temperature 0,
`reasoning_effort=none`, `max_completion_tokens=8192`. No retry, repair, fallback or
additional verifier was used. Mean recorded request latency: 8.32 seconds.

Original canonical exports, raw responses, ledgers and manifest remain in
`data/processed/agent2_focused_v5_2/`. The freeze, checks, exact source-bound supplement
and **refreshed effective view** are in `data/experiments/agent2_focused_v5_2/`.
The mandatory review registry preserves all five earlier entries and adds this run.
The effective loader exposes two new content findings, both inherited obligations
and the HIGH obligation; both groups require review, with no stale bindings.
The run-local effective snapshot predates the new review. Use the maintained loader
or the separate refreshed file for downstream consumers. To export another view
with no model calls and a fresh output file:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_focused_v5_2 --output data/experiments/agent2_focused_v5_2/effective_refresh.json
```

Do not rerun the completed pilot or bypass its fingerprint: it records the registry
at execution time. Post-run review metadata intentionally changes the current
registry. Agent 3, RAG and dashboard implementation remain outside this milestone.

## Historical milestone: completed focused v5.1 correction and four-request revalidation

The authorized experiment is complete: **4 CONSOLIDATED, 0 FAILED, 0 INTERRUPTED,
4 attempts, 4 saved responses, 0 unknown completions, 0 unprocessed groups**.
All **12 identities, 32 source messages and two inherited review obligations**
are retained. Safety ran first; its HIGH morning-review obligation did not stop
audio, Quarantine or alignment. All four HTTP responses completed normally and
match the frozen model, requests, inputs, strict schema and code.

One general instruction revision, `agent2-inventory-v5.1`, clarifies same-conversation
substantive answer links and evidence-based operational severity. Schema v5,
validators, inventory architecture, transport, rubric, dependencies and Arm B's
`openai/gpt-5.4-2026-03-05` settings remain unchanged. No case answers or review labels
were added to requests. All **492 offline tests passed before execution**; no
production code or prompt changed during or after it. No retries or repairs occurred.

| Group | Prior B → v5.1 outcome | New severity | Assisted source review |
| --- | --- | --- | --- |
| Safety announcement, 1 member | CONSOLIDATED → CONSOLIDATED | HIGH, previously MEDIUM | Reported inability to submit supports HIGH; null announcement question and actual eyes reaction retained. No material issue found. |
| Audio, 6 members / 2 inherited obligations | FAILED → CONSOLIDATED | HIGH; prior raw criteria conflicted | Correct same-member ANSWER links and scoped guidance; prose incorrectly says one thread received the answer when two did. Full resolution of the explicit Quarantine question remains uncertain. |
| Quarantine, 3 members | CONSOLIDATED → CONSOLIDATED | UNKNOWN, previously MEDIUM | Scoped TL-endorsed answer and independent-flags condition retained; two other questions OPEN. No material issue found. |
| Alignment, 2 members | CONSOLIDATED → CONSOLIDATED | MEDIUM remains disputed | Both questions OPEN and TL withholding-supersession guidance intact; impact still rests only on document disagreement/clarification. Unlinked DIRECT ANSWER classification remains uncertain and provisional. |

**Readiness: hold broader validation.** This is a Codex-assisted source review,
not human approval, independent ground truth or an accuracy benchmark. The accepted
alignment output's impact evidence remains insufficient; audio has additional
count/resolution concerns. UNKNOWN and legitimate review obligations are acceptable.
The conditional eight-group validation was **not prepared or executed**. The four
authorized requests are exhausted; no further prompt change or correction loop was
started. The next work should resolve these specific evidence-sufficiency concerns
before authorizing another experiment.

The [full milestone report](../data/experiments/agent2_focused_v5_1/milestone_report.md)
contains exact test/execution commands, full group IDs, before/after findings and
limitations. Frozen configuration, request hashes, offline test XML, execution
audit, original-source review, new supplement and refreshed effective view are in
`data/experiments/agent2_focused_v5_1/`. Immutable executed records and ledgers are in
`data/processed/agent2_focused_v5_1/`; the original run-local effective view predates
this new review. The mandatory registry now applies four new findings across two
groups. Automated and effective review queues both contain three groups; both
inherited obligations remain byte-for-byte equivalent as structured data, with
hashes, lineage and evidence. There are no stale findings.

To materialize another current view, without model calls, use a fresh output file:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_focused_v5_1 --output data/experiments/agent2_focused_v5_1/effective_refresh.json
```

Do not rerun the completed pilot or refresh it as an implicit authorization for
more calls. Its fingerprint intentionally describes the pre-execution review
registry; adding post-execution findings changes current review metadata. Preserve
the original freeze and use the effective loader for downstream consumers.

## Historical milestone: completed v5 A/B evaluation, offline source review

The A/B experiment has executed. Its preparation report and `freeze.json` state
describe preparation, not the final execution outcome. This review milestone made
**zero paid calls** and changed **no production code, prompts, models, schemas,
rubric, dependencies or raw results**. The only existing configuration edit adds
mandatory evidence-bound review supplements. Focused regressions protect the
existing validation boundaries; there is no automatic repair or permissive default.

### Execution integrity and comparison validity

The comparison is valid for these deliberately selected cases. Both manifests and
all exact requests match the original freeze and prepared files. Code fingerprints
matched before adding the new review registry entries. All 12 responses are HTTP
200 with one normal `stop` completion, no refusal, no partial HTTP body and no
unknown completion. All 12 drafts satisfy the actual provider JSON schema.
Application checks, including conditional fields and coverage, reject six A drafts
and one B draft. **None of these failures is a transport/API/schema incompatibility.**

| Measure | Arm A | Arm B |
| --- | --- | --- |
| Requested and returned model | `gpt-4o-mini-2024-07-18` | `gpt-5.4-2026-03-05` |
| CONSOLIDATED / FAILED / INTERRUPTED | 0 / 6 / 0 | 5 / 1 / 0 |
| Attempts / responses / unknown / unprocessed | 6 / 6 / 0 / 0 | 6 / 6 / 0 / 0 |
| Retained identities / inherited obligations | 18 / 5 | 18 / 5 |
| Inventoried messages in raw drafts | 37/51 | 51/51 |
| Input / output tokens | 21,912 / 2,200 | 21,870 / 3,829 |
| Cached input / reasoning tokens | 5,120 / 0 | 0 / 0 |
| Mean recorded latency | 3.78 seconds | 6.61 seconds |
| Automated / effective review groups after this review | 6 / 6 | 3 / 5 |

Semantic messages, input identities, glossary, strict schema, prompt
`agent2-inventory-v5.0` and rubric `provisional-operational-severity-v1` are identical.
Both use temperature 0 and `max_completion_tokens=8192`; only model ID and B's
explicit `reasoning_effort=none` differ. Each request has one system and one user
message, no prior conversation history. Token/latency differences are observed
usage, not an accuracy measure. This small, repeatedly examined sample supports no
unbiased accuracy percentage or general model-accuracy claim.

### Review of all actual drafts against Slack

This is a **Codex-assisted source review, not human approval or independent ground
truth**. Coverage below counts original messages inventoried; there are no invented
dispositions. All member assignments and evidence IDs resolve correctly. Semantic
support, item-link type/scope and severity require separate inspection.

| Group | Members / inherited flags per arm | A outcome, coverage and findings | B outcome, coverage and findings | B severity review |
| --- | --- | --- | --- | --- |
| `cluster_1ba596334ad5cde7` | 2 / 0 | FAILED, 4/4. QUESTION items have null states and DIRECT answer_status; diagnostic wording request mislabeled. | CONSOLIDATED, 4/4. Both precedence questions OPEN; scoped TL withholding-supersession instruction and diagnostic retained. Unlinked ANSWER remains provisional through existing review. | MEDIUM support uncertain: source shows coordination, not demonstrated labeling consequence. UNKNOWN is defensible. |
| `cluster_6b59d13144282285` | 6 / 2 | FAILED, 5/19. M04 and 14 messages missing, including handling questions and TL guidance. Raw MEDIUM understates cited inability to evaluate. | FAILED, 19/19. Useful silence/player split, questions and full scoped guidance retained. Three invalid answer links, including another member's FACT; both impact sections mix incompatible levels. Scope counts are under-cited. | Canonical UNASSESSED; raw MEDIUM+UNKNOWN and HIGH+MEDIUM independently invalid. E015/E019 support scoped HIGH blockage. |
| `cluster_a6dfe8374217a497` | 3 / 0 | FAILED, 7/7. Context becomes DIRECT answers; question-state contract fails. | CONSOLIDATED, 7/7. Questions PARTIAL/OPEN/OPEN; context no longer answers. TL-endorsed reply retains school-context, on-its-own and independent-flags conditions. Minor school-story citation gap remains. | MEDIUM observation relies on clarification/open questions alone; UNKNOWN is conservative absent demonstrated operational impact. New review retained. |
| `cluster_024655fb52cc3352` | 1 / 0 | FAILED, 2/2. Invalid question state; tentative location advice labeled DIRECT. | CONSOLIDATED, 2/2. TENTATIVE answer, PARTIAL question, original qualification and pinned-file check intact. | N/A/NON_OPERATIONAL supported; no new content dispute. |
| `cluster_14c5fc257d90b58f` | 5 / 3 | FAILED, 17/17. Diagnostic items contain question state; root announcement/instruction only FACT; E015 factual report only diagnostic. | CONSOLIDATED, 17/17. Announcement and instruction restored, null root question, disabled/silent-click differences and scoped TL submission/reload conditions retained. | HIGH supported by reported submission blockage; nonblocking HIGH review and all three inherited obligations preserved. |
| `cluster_06c08cf4143f2022` | 1 / 0 | FAILED, 2/2. Announcement roles lost, inappropriate answer_status; raw HIGH+UNKNOWN inconsistent. | CONSOLIDATED, 2/2. Announcement, instruction, diagnostic and LT-confirmation condition retained; null root question. | **Material blocker:** MEDIUM despite explicit inability to complete labeled tasks across projects. Frozen rubric supports HIGH; automated HIGH review was missed. New content review now routes it without overwriting MEDIUM. |

Actual reactions are preserved: U006's `agree` targets the scoped Quarantine reply;
audio/submission `thumbsup` users are tutors, and safety-announcement `eyes` is tutor
U013. None is promoted to TL approval incorrectly in B. No invented policy
precedence, tried/failed workaround, wider cause or successful submission was found
in B. Its observed-outcome wording describes Slack reports, not independently
verified incidents. Severity judgments remain provisional. Context classification
and the unsupported impact choices still need actual-output review.

### Remaining failure and smallest justified action

Arm B's first failure is `answer_evidence` at
`topics[1].inventory[0].question.answer_item_ids[0]`: T2_I1/E004 (M02) points to
T2_I11/E015, a FACT in M05. Two more links are wrong: T2_I8 points to that FACT;
T2_I12 points to T2_I17/E019, an INSTRUCTION. Actual ANSWER items exist but cannot
be substituted automatically, and another member's answer cannot close M02.
This is a **model-generated relationship error, not an implementation defect**.
The original failure remains. An independent section-only offline check also
finds contradictory severity levels in both topics; it is not an accepted replay.

No parser fix or prompt rewrite is justified automatically. New regression tests
isolate wrong-type and cross-member links and retain valid facts with invalid
severity. The next recommended change is **one focused severity-instruction
clarification**: choose one supported operational level, use UNKNOWN when only
clarification is evidenced, and map explicit inability to perform/submit work to
substantial_blockage at the actual scope. This recommendation has **not** been
applied. Future audio output must independently satisfy the existing link rules.

**Readiness: not ready for broader validation.** The accepted safety announcement's
understated severity and missed HIGH routing are material; zero flags is not the
criterion. The conditional eight-group validation set and live command were not
prepared because this readiness condition failed. No further live run is authorized.

### Review handoff and offline validation

New evidence lives in `data/experiments/agent2_comparison_v5_review/`:
`execution_audit.json`, `review_supplement_A.json`, `review_supplement_B.json`,
`effective_A.json`, `effective_B.json`, and `readiness.json`. Each finding includes
exact affected raw fields, original quotations/reactions/full identities and exact
input/raw-draft/result hashes. The mandatory registry retains the v3.2 and v4
reviews and adds both new supplements. Effective A/B views have 6/5 review groups,
18 identities and five inherited obligations each; 8/7 new content obligations,
no stale bindings. All original automated outcomes, candidate text, severity and
raw evidence remain unchanged. Run-local `effective_output.json` predates this
review; use the loader or these separate refreshed views.

Safe next command to materialize another current view, **zero model calls**:

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/experiments/agent2_comparison_v5/runs/B --output data/experiments/agent2_comparison_v5_review/effective_B_refresh.json
```

Validation: **58 focused tests passed**, then **482 passed, 0 failed, 0 skipped**
in the complete offline suite (162 warnings, 237.00 seconds). The new tests inspect
all twelve actual provider-schema-valid drafts and preserve their original local
verdicts, isolate wrong-type/cross-member links, expose both hidden audio impact
failures, protect independent severity handling and verify effective review bindings.
Exact commands:

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent2_ab_review.py tests/test_agent2_structured.py -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-ab-review --junitxml .cache/agent2_ab_review_v5/focused.xml
.venv\Scripts\python.exe -X utf8 -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-ab-review-full --junitxml .cache/agent2_ab_review_v5/full.xml
```

`milestone_report.json` and test XML in the review directory record validation and
preservation. All **8,721 preexisting files outside three intended documentation/
review-registry edits** retain their before-review hashes, including every run
artifact, frozen input, production module and dependency file. The user's previous
changes and deletion remain untouched. No new model request markers were created.

The old freeze remains untouched. Its code/configuration hashes describe the
executed experiment; the new registry intentionally changes current review metadata.
Do not bypass a fingerprint mismatch or reuse either completed run for another call.

## Historical v5 offline preparation (preserved; both arms subsequently executed)

The following preparation report predates execution. Use the completed review above
for actual outcomes and readiness; the old live commands are historical.

This milestone made **zero paid calls**. The completed `agent2_inventory_pilot_v4`
remains the live baseline: **three CONSOLIDATED, three FAILED, zero INTERRUPTED**;
six attempts, six HTTP 200/normal-stop responses, zero unknown completions or
unprocessed groups. Only **four of 18 identities** belong to consolidated groups.
All five inherited review obligations survive. Actual saved requests had no
`response_format`; all responses identify `gpt-4o-mini-2024-07-18`.

### Implemented contract and transport

The actual Chat Completions body now carries strict `json_schema` response format
generated from the maintained v5 contracts. Every object is closed; every property
is required, with nullable values for explicit unknown/unassessed content. Local
membership, citation, coverage, answer-link and independent severity checks remain.
Provider enforcement does not establish factual support or exhaustive coverage.

Inventory items return evidence IDs and semantic classifications, **not source
quotations**. Python supplies full original messages, authors, reactions, identities,
and qualifiers. Genuine synthesis and impact observations remain model-generated.
Answers carry `TENTATIVE`/`DIRECT`; tentative advice cannot close a question as
ANSWERED. Explicit `impact=null` retains valid facts as CONSOLIDATED with
UNKNOWN/UNASSESSED severity and nonblocking review. Invalid impact is separately
INVALID; it cannot delete valid factual output. Missing messages and substantive
members produce exact IDs and original-source diagnostics, never invented items.

Prompt `agent2-inventory-v5.0` distinguishes handling questions, diagnostics, context,
scoped answers, announcements, instructions and reported/observed impact. A single
message can have several roles. Reply questions survive without becoming an
announcement's root question. Review cues flag possible omissions; they do not
prove semantic correctness. Conditions remain in verbatim full-message scope, not
separately extracted limitations. Rubric stays `provisional-operational-severity-v1`.

Export schema **5**, adapter `inventory-to-display-v2`, supplies fixed metadata in
Python. Historical v2/v3/v4 validators remain separate; old raw outputs are not
upgraded, repaired or accepted under v5. Source-copying errors remain failures under
their original contract. The common Agent 1 transport and its fingerprints are
unchanged; the Agent 2 wrapper still makes exactly one POST per group, with no SDK,
automatic retries, repair, fallback or extra verifier. Refusals and incomplete
outputs are explicit failures; partial HTTP bodies remain unknown completion.
Unsupported-schema/configuration errors stop the arm and preserve evidence.
`completion_status.json` records latency, provider model, finish reason and usage.

### Assisted review of the actual v4 baseline

This is a Codex-assisted source review, **not human approval or an unbiased accuracy
benchmark**. Findings are bound to actual v4 input, raw draft and exported-result
hashes in `data/experiments/agent2_structured_v5/v4_source_review.json` and
`v4_review_supplement.json`. The mandatory registry retains the prior v3.2 supplement
and adds this v4 evidence; it does not transplant old hashes. Use
`load_effective_output(run_dir)` for downstream consumption. The new materialization
`effective_v4.json` has **six effective review groups versus five automated**, all
18 identities and five inherited obligations; no stale bindings. Original v4
outputs, statuses and request ledger are untouched.

| Group | Members / inherited flags | Outcome | Source-review findings |
| --- | --- | --- | --- |
| `cluster_1ba596334ad5cde7` | 2 / 0 | CONSOLIDATED | Both precedence questions and scoped TL withholding-supersession guidance retained. Diagnostic labeled QUESTION; MEDIUM operational-impact support uncertain. |
| `cluster_6b59d13144282285` | 6 / 2 | FAILED | Only 4/19 messages, no dispositions; M04/M05 substantive content and scoped playback guidance missing. Claimed submission impact unsupported by citations. |
| `cluster_a6dfe8374217a497` | 3 / 0 | FAILED | Missing schema_version; handling questions misclassified, context labeled answers. Old quote mismatch retained. Scoped TL-endorsed Quarantine answer itself retains its conditions. |
| `cluster_024655fb52cc3352` | 1 / 0 | CONSOLIDATED | Question and tentative location advice survive. Empty impact invalid; UNKNOWN/unassessed correct. Missing answer link remains a limitation; no confirmed resolution claimed. |
| `cluster_14c5fc257d90b58f` | 5 / 3 | FAILED | Only 4/17 messages, no dispositions; M03/M04 and conditional submission guidance missing. Announcement classified FACT. Raw HIGH reported blockage supported. |
| `cluster_06c08cf4143f2022` | 1 / 0 | CONSOLIDATED | Announcement classified DISCUSSION; structured guidance empty, reply promoted to representative root question. Instruction/condition still recoverable in prose. HIGH reported blockage supported; eyes not approval. |

### Offline validation

The focused integration run passed **166 tests**. After the final transport edge-case
check, the v5-specific run passed **35 tests**. The complete offline suite then
passed **459 tests, 0 failures, 0 skipped**, with 162 warnings in 229.70 seconds.
Tests inspect actual outgoing HTTP bodies, refusal/incomplete/unsupported-schema
handling, all six original v4 drafts under their historical validator, exact missing
source IDs, separate synthetic semantic cases, severity isolation, flags, review
bindings, and both-arm freeze/budget enforcement. Mocked outputs establish behavior,
not future model accuracy. Exact final commands:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_agent2_structured.py -q --tb=short --basetemp .cache/pytest-agent2-structured-final --junitxml .cache/agent2_structured_v5/structured.xml
.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-structured-full --junitxml .cache/agent2_structured_v5/full.xml
```

Catalog and Slack fixture checks pass: 200 identities, 12 channels, 316 replies.
The separate legacy dataset validator still fails its unchanged line-129 rule:
`Unresolved thread contains TL response/approval 1790941015.000132`. That existing
rule treats TL participation as incompatible with unresolved status. Its output
was redirected to `.cache`; neither validator nor source fixtures were changed.
Machine-readable results and test XML are in
`data/experiments/agent2_structured_v5/offline_report.json` and adjacent files.
All 8,533 preexisting files outside the 14 intended code/test/documentation edits
match their before-edit hashes, including every preexisting data artifact. The
user's prior changes and deletion remain untouched. No new request markers exist.

### Controlled comparison, prepared only

Both arms are frozen together in `data/experiments/agent2_comparison_v5/freeze.json`:
the same six groups above, **18 identities and five inherited obligations per arm**,
identical messages, glossary, semantic prompt, operational rubric and response
schema. Saved requests and inputs, code/configuration hashes and the freeze receipt
are checked before either arm can run. Fixed fresh paths `runs/A` and `runs/B` reject
repeats; any interruption consumes that attempt. No paid availability probe ran.

| Parameter | Arm A | Arm B |
| --- | --- | --- |
| Model | `gpt-4o-mini-2024-07-18` (observed baseline snapshot) | `gpt-5.4-2026-03-05` |
| Reasoning effort | Not applicable; omitted | `none`, explicit |
| Temperature | 0 | 0, supported with reasoning `none` |
| Completion limit | `max_completion_tokens=8192` | `max_completion_tokens=8192` |
| Requests | At most 6, one per group | At most 6, one per group |

Model profiles override terminal defaults explicitly; no model substitution is
allowed. `max_tokens` is omitted. Standard uncached prices checked against official
documentation on 2026-10-24: mini **$0.15/M input, $0.60/M output**; GPT-5.4
**$2.50/M input, $15/M output**. Local character-based input estimates, a 2,000-output-
tokens/group scenario, and an output-limit scenario are recorded in `freeze.json`.
The frozen estimate is **$0.0110 for A + $0.2434 for B = $0.2544 total**;
at 8,192 output tokens/group with estimated input, the total is **$0.8340**.
These are estimates, not exact token counts or a billing cap. Account availability
is untested; unsupported configuration stops the arm without fallback.

Sources: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat),
[Chat Completions parameters](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[GPT-5.4 parameters](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.4),
[mini model/prices](https://developers.openai.com/api/docs/models/gpt-4o-mini),
[GPT-5.4 snapshot/prices](https://developers.openai.com/api/docs/models/gpt-5.4).

Offline preflight (no calls):

```powershell
uv run --locked python scripts/run_agent2_comparison.py --dry-run --experiment data/experiments/agent2_comparison_v5
```

Future live commands, **prepared but not authorized or executed by this milestone**:

```powershell
uv run --locked python scripts/run_agent2_comparison.py --run --experiment data/experiments/agent2_comparison_v5 --arm A --max-requests 6
uv run --locked python scripts/run_agent2_comparison.py --run --experiment data/experiments/agent2_comparison_v5 --arm B --max-requests 6
```

Maximum **12 requests total**, zero retries, repairs, fallbacks or extra verifiers.
Both arms must remain frozen; do not change code/prompts after seeing arm A. Record
provider schema acceptance, complete source accounting, question/guidance retention,
unsupported claims, severity support, review preservation, latency and token usage.
The separate `source_review_template.json` is never model input. Review each actual
result against Slack and bind findings to its hashes before choosing a model. The
six selected cases cannot yield an unbiased accuracy percentage; broader behavior
and actual v5 semantic performance remain untested.

## Historical v4 offline milestone (preserved; pilot subsequently executed)

The following records the earlier preparation milestone. Its commands and status
are historical; use the v5 comparison above for the next experiment.

The v4 contract and deterministic compatibility exports are implemented. **Zero
paid calls** were made. A fresh six-group pilot is prepared, not executed. The
last live run remains v3.2: two CONSOLIDATED and four FAILED. Its accepted
Quarantine result still has material semantic findings; no historical outcome,
candidate, response, source fixture, grouping, Agent 1 record or dependency changed.

The model now produces one evidence-indexed `inventory`, concise `shared_issue`,
supported `relevant_differences`, explicit dispositions for messages without items,
and a separate `impact` section. An item has one source ID, an exact excerpt and
a kind: question, diagnostic request, answer, instruction, reported fact,
announcement or context. Multiple items can come from one message. Question status
and same-thread answer links live on the question item. Missing treatment is an
error; it does not become NONE. Every member needs substantive inventory content.

Python derives `open_questions`, `representative_question`, guidance/answer lists,
conversation kind and coverage bookkeeping. It supplies full identities, verbatim
source messages, authors, actual reactions/eligible TL endorsements, hashes and
lineage. Guidance's `scope` contains the entire original message, including its
conditions. `limitations=[]` means conditions were **not separately extracted**;
`conditions_representation=verbatim_full_message_in_scope_not_extracted` is explicit.
Consumers must retain scope rather than interpret the empty list as no conditions.
Diagnostics cannot answer a question. An answer in one thread cannot close another
thread's broader question. Announcements can contain instructions without questions.

Conservative question/directive cues create nonblocking coverage review obligations.
They do not establish that a quoted/rhetorical question is genuine, infer authority,
or establish resolution. Exact excerpts and valid IDs prove traceability, **not
entailment**. The tests explicitly demonstrate that unsupported synthesis can still
pass structural checks; source review remains required.

### Independent severity and compatibility

The model cites each applicable operational criterion/observation once, identifies
reported versus observed evidence, and supplies actual affected scope or null.
Python derives severity level, rationale and impact display fields, rubric version,
assessor and provisional metadata. Criteria must map to one unambiguous level.
UNKNOWN uses insufficient evidence; N/A uses NON_OPERATIONAL. LOW requires evidence
of demonstrated limited operational consequences, not harmless task content.
Per-criterion bases remain available; the aggregate basis is MIXED if they differ.

Invalid impact produces UNKNOWN/UNASSESSED, diagnostics, a retained rejected proposal
and a review obligation, while independently valid facts remain CONSOLIDATED.
Invalid facts remain rejected even with valid severity. Processing state,
`factual_validity`, `severity_validity`, assessment status and review requirements
are distinct. A timeout leaves factual validity UNASSESSED. HIGH creates nonblocking
morning review; LOW/N/A never removes inherited flags. Agent 3 may later record a
separate researched severity without overwriting Agent 2's assessment.

Response/export schema is **4**, prompt `agent2-inventory-v4.0`, rubric remains
`provisional-operational-severity-v1`, model remains `openai/gpt-4o-mini`.
`compatibility_topic()` is the explicit display adapter. Model-generated
`source_assessments`, repeated question/guidance/answer lists, uncertainties,
conversation kind, coherence/review metadata and severity metadata were removed
or made deterministic. Old response contracts are retained in
`topic_contracts_v3.py` / `topic_consolidation_v3.py` (and v2 equivalents).
Historical tests replay under those contracts; v3 responses are rejected by v4.
Code/schema fingerprints invalidate incompatible prepared selections and caches.
The preparation tool requires an explicit `--allow-contract-upgrade` for this
reviewed v3-to-v4 transition; sources, model, selection and call bounds must match.

### Required downstream effective view

Use `threadsense.agents.topic_effective.load_effective_output(run_dir)` for current
downstream reads. Its mandatory registry is `docs/agent2-review-supplements.json`;
additional supplements extend rather than replace that registry. Findings bind to
exact input/raw-response/result file hashes and matching aggregate records.
Applicable obligations are deduplicated with provenance; stale bindings remain
visible in `unapplied_findings` and are never applied to different content. Missing
or altered registered evidence fails closed. Processing outcomes and canonical
files are unchanged; disputed guidance/answers in the effective view are provisional.

The existing v3.2 view is materialized separately in
`data/experiments/agent2_inventory_v4/effective_v3_2.json`: **six effective review
groups versus five automated review groups**, all 18 members and five inherited
obligations, 14 applicable assisted findings, no stale bindings. This is an assisted
review, not human approval. New runs also write `effective_output.json`; call the
loader again after adding reviews instead of trusting an older materialized view.
Do not use raw `consolidations.json` alone as the downstream review-aware handoff.

To materialize a fresh view without model calls (choose a new output file):

```powershell
uv run --locked python scripts/export_agent2_effective.py --run-dir data/processed/agent2_revalidation_v3_2 --output data/experiments/agent2_inventory_v4/effective_v3_2_refresh.json
```

### Simplification and offline validation

Counting independently generated topic semantic containers, excluding names,
membership and metadata: **9 to 5**. The five repeated question/guidance containers
become one inventory. The remaining containers are synthesis, differences,
dispositions and impact. Schema size is **6,463 to 4,257 serialized characters**.
The precedence request is **19,451 to 14,065 characters**; the audio request is
**28,409 to 23,533**. One request per group remains unchanged, with zero retries,
repairs, fallback calls or additional verifiers.

Example response sizes use the same JSON serializer: precedence **2,088 to 1,450**
characters; audio **3,575 to 6,361**. The old values are actual, often incomplete
v3.2 drafts; the new values are source-reviewed **synthetic contract examples**.
The longer audio example retains omitted content. These are not predictions of
live token use or evidence of model improvement. All six comparisons, source hashes,
synthetic drafts/exports, test XML and preservation results are in
`data/experiments/agent2_inventory_v4/offline_report.json` and adjacent artifacts.

The six synthetic examples have valid factual and severity sections: three UNKNOWN,
one N/A and two HIGH, with three review groups and all five inherited obligations.
They are not migrated historical responses or claimed live successes. Separate
tests inject invalid severity and retain valid facts, process groups after HIGH,
preserve flags through successful consolidation, exercise split topics and TL-eyes,
and distinguish applicable/stale review supplements. No missing historical content
was fabricated into old responses. **48 new focused tests passed**, then the full
offline repository suite passed: **424 passed, 0 failed, 0 skipped**, 162 warnings,
218.35 seconds. Exact commands (the existing locked environment was used):

```powershell
.venv\Scripts\python.exe -m pytest tests/test_agent2_inventory.py -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-inventory-focused --junitxml=.cache/agent2_inventory_v4/focused-tests.xml
.venv\Scripts\python.exe -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-inventory-full --junitxml=.cache/agent2_inventory_v4/full-tests.xml
```

All **8,371 preexisting protected files** match their before-edit hashes. The new
production fingerprints match the prepared pilot. `git diff --check` passes.

Catalog and Slack-fixture checks pass (200 identities, 12 channels, 316 replies).
The legacy dataset validator retains its previously documented line-129 failure:
`Unresolved thread contains TL response/approval 1790941015.000132`. Its report
destination was redirected to `.cache` for this check. That unrelated validator
assumes a TL reply/approval cannot coexist with an unresolved thread; source data
and the validator were not changed.

### Prepared next evaluation — not executed

Selection: `docs/agent2-inventory-pilot-v4.json`. Exact requests/configuration hashes:
`data/processed/agent2_inventory_pilot_v4_prepared/`. Same six groups, **18 identities,
five inherited obligations**, six VERIFIED/seven CORRECTED/five NEEDS_REVIEW members.

| Group | Members | Inherited obligations |
| --- | ---: | ---: |
| `cluster_1ba596334ad5cde7` | 2 | 0 |
| `cluster_6b59d13144282285` | 6 | 2 |
| `cluster_a6dfe8374217a497` | 3 | 0 |
| `cluster_024655fb52cc3352` | 1 | 0 |
| `cluster_14c5fc257d90b58f` | 5 | 3 |
| `cluster_06c08cf4143f2022` | 1 | 0 |

Read-only preflight passed:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-inventory-pilot-v4.json
```

Prepared live command, **not authorized/executed by this offline milestone**:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-inventory-pilot-v4.json --max-requests 6 --output-dir data/processed/agent2_inventory_pilot_v4
```

Budget: **at most six requests, one per selected group**, no automatic retries,
repairs, fallback or extra verifiers. The live output directory is fresh and absent.
Inspect every actual output against original Slack after execution, recording
processing/factual/severity/review outcomes separately. Keep selection notes,
synthetic expectations and assisted review judgments out of runtime requests.
If semantic failures persist, recommend a separately authorized controlled comparison
with a stronger model using identical inputs, contract, rubric and evaluation
criteria. Do not change model and contract together or assume an upgrade solves it.

## Historical v3.2 milestone (preserved)

This is the maintained run guide. Agent 2 performs factual consolidation and
preliminary operational-severity assessment from Slack. Agent 3 may later research
the topic and record a separate revised assessment. Agent 2 does not retrieve,
decide policy precedence, assess actionability, or recommend interventions.

The original offline hardening and first review made zero paid calls. The bounded
v3.2 revalidation below made **exactly six new authorized requests**. The finalized
Agent 1 handoff still has 200 identities (81 VERIFIED, 70 CORRECTED, 49 NEEDS_REVIEW)
in 90 unchanged tentative groups. All inherited flags, source/candidate hashes,
review registries, and lineage remain available downstream.

### Bounded v3.2 revalidation: not ready for a larger run

The authorized experiment completed once in
`data/processed/agent2_revalidation_v3_2/`: **2 CONSOLIDATED, 4 FAILED,
0 INTERRUPTED, 0 unprocessed**. All six attempts have saved HTTP 200 responses
with normal completion; there are zero unknown completions. All 18 identities
and five inherited obligations retain their exact canonical evidence/hashes/lineage.
Aggregate records, per-group records and queues agree. Only four threads belong
to the two consolidated groups; the other 14 remain retained failure records.

The immediate comparison baseline is the subsequently executed
`data/processed/agent2_targeted_pilot_v3_1/`, which also contained six FAILED
records. It was already present before this milestone and was not rerun or
counted toward the six new requests. Both it and the original hardening pilot
remain unchanged.

Before execution, the actual saved requests were checked. Existing schema
descriptions did reach the model. Generic instructions were added for explicit
question/guidance coverage, unknown/null handling, TL authorship versus endorsement,
scope/conditions, topic-local evidence and conditional severity requirements.
No case answers, review judgments, labels or synthetic pilot evidence were inserted;
the source-containing user messages were unchanged. **99 offline checks passed**
before freezing. No production code, prompt or model changed during/after execution.

The frozen prompt is `agent2-consolidation-v3.2`, response schema 3, rubric
`provisional-operational-severity-v1`, requested model `openai/gpt-4o-mini`;
all responses identify `gpt-4o-mini-2024-07-18`. Configuration fingerprint:
`178a90c132834306c2496f62214276c51ca2473033b31d5440847dfc6768f632`.
The exact requests match their pre-execution hashes. The transport uses one direct
HTTPS POST per group, with no SDK retry, repair, fallback or extra verifier.

This comparison is a **Codex-assisted source review**, not human approval or an
unbiased accuracy benchmark. Proposals from rejected drafts are distinguished
from their UNKNOWN/unassessed canonical records.

| Group | Members | Previous → new | Remaining validation | Source-review comparison | Severity; obligations retained |
| --- | ---: | --- | --- | --- | --- |
| `cluster_1ba596334ad5cde7` | 2 | FAILED → FAILED | Question coverage | Precedence question still absent from open_questions. The TL withholding-supersession condition is now quoted, but diagnostics are not structured guidance. | Proposed MEDIUM still weakly justified; canonical UNKNOWN. 0/0 obligations. |
| `cluster_6b59d13144282285` | 6 | FAILED → FAILED | Factual member coverage | Inventory improves 5/19 → 19/19 messages, but M04/M05 lack factual citations. Previously retained playback guidance disappears; silence/loading differences and handling questions are lost. No invented workaround failure. | Proposed HIGH blockage partly supported; quality-risk claim unsupported. Canonical UNKNOWN. 2/2 obligations. |
| `cluster_a6dfe8374217a497` | 3 | FAILED → CONSOLIDATED | None | Correct TL_ENDORSED attribution and intact conditional guidance text. Still invents a harmless-versus-harmful contrast, marks explicit questions NONE, and leaves structured scope/limitations incomplete. | Accepted LOW/OBSERVED_OUTCOME lacks operational-impact evidence. 0/0 inherited obligations; new separate content-review flag. |
| `cluster_024655fb52cc3352` | 1 | FAILED → FAILED | Empty severity criteria | N/A/NON_OPERATIONAL remains appropriate, but actual question is NONE and tentative location guidance is absent. MIXED classification is unsupported. | Raw N/A; canonical UNKNOWN. 0/0 obligations. |
| `cluster_14c5fc257d90b58f` | 5 | FAILED → FAILED | Factual member coverage | Missing M03 and scoped TL submission conditions; invented causal/pattern questions replace diagnostics. Scope no longer says all users, and unsupported quality-risk criterion is removed. | Raw HIGH reported blockage defensible; canonical UNKNOWN. 3/3 obligations. |
| `cluster_06c08cf4143f2022` | 1 | FAILED → CONSOLIDATED | None | Correct MIXED/null-question treatment; announcement, conditions and actual QA question retained. Structured guidance remains empty despite instructions appearing in prose. No material unsupported factual claim found in the issue/question text. | Accepted HIGH reported blockage is supported; one morning-review obligation in canonical queue. 0/0 inherited obligations. |

The canonical review queue has five groups (four failures plus the HIGH group).
The accepted Quarantine group was automatically unflagged despite material
content findings. Its new evidence-bound review obligation is recorded separately
in `review_supplement.json`; canonical outcomes and candidates are not rewritten.
Downstream consumers must join this supplement with the canonical/inherited queues.

All 8,272 preexisting protected files and all 56 completed-run files were preserved.
The separate experiment directory
[`data/experiments/agent2_revalidation_v3_2/`](../data/experiments/agent2_revalidation_v3_2/)
contains `freeze.json`, exact frozen code, `offline-tests.xml`, `request_ledger.json`,
`integrity.json`, `comparison.json`, `source_review.json`, and `review_supplement.json`.
Findings bind to actual source, draft and exported-result hashes.

**Stop here. No broader command or additional experiment is prepared.** The common
observed problem is inconsistent evidence-to-output mapping: questions/instructions
are marked NONE, inventories disagree with prose lists, and real IDs accompany
unsupported claims. Stronger instructions did not eliminate it. One focused next
change to consider offline is a single evidence-indexed question/guidance inventory,
with repeated export lists/coverage derived deterministically. This recommendation
is not implemented and would still need semantic review; it cannot guarantee
correct classification of source content or severity.

Live successful merging of inherited flags remains untested: all five obligations
belong to failed groups. HIGH routing is demonstrated, but that group was last, so
continuing to a later group after HIGH is not tested live here. This run also does
not exercise TL-eyes, split-topic outputs, transport failures or unknown completion.
Agent 3 may later record a separate researched severity without overwriting Agent 2.

## Earlier pilot assessment (historical)

The remaining sections preserve earlier milestones and command examples. Their
selections/code fingerprints and occupied output paths are historical; do not use
them as instructions to repeat a paid run. The current completed run is above.

The actual `data/processed/agent2_hardening_pilot_v3/manifest.json` reports
**0 CONSOLIDATED, 6 FAILED, 0 INTERRUPTED**, with zero unprocessed groups.
`complete_with_review` means processing finished; it is not six successful
consolidations. All six attempts have saved HTTP 200 responses with normal `stop`
completion and matching raw text. There are zero unknown completions. Primary
rejections are three schema errors, two member-evidence-coverage errors, and one
severity consistency error; later checks reveal additional omissions.

Mechanical inspection confirms all 18 unique identities (six VERIFIED, seven
CORRECTED, five NEEDS_REVIEW), the complete five inherited obligations, and their
original evidence, candidate/source hashes and lineage. Aggregate/per-group
records, the six-record review queue, and five-member obligation queue agree.
Each raw draft assigns all its member aliases once and uses existing evidence IDs;
that does not establish factual coverage or support. There are **no accepted
topics**: all canonical failure records correctly remain UNASSESSED/UNKNOWN.

The requested model was `openai/gpt-4o-mini`; all provider responses identify
`gpt-4o-mini-2024-07-18`. Response/export schema is 3; rubric is
`provisional-operational-severity-v1`. All 16 recorded code hashes and the exact
requests matched the checkout before the bounded fixes below. The original
configuration hash is
`ece437c5f87e729ea3d3435efa48032b5310cd865d23f68cbf679a9d47785b60`.
The original request had no separate prompt-version field: exact saved system
text, request hashes, and code fingerprints identify its prompt.

This is a **Codex-assisted source review**, not human approval or an unbiased
accuracy benchmark. All six groups were deliberately selected regression cases.
The table reviews actual rejected drafts against every original message/reaction;
raw proposed severities are not canonical assessments.

| Group | Members | Outcome | Inherited obligations | Source-review findings | Raw severity assessment |
| --- | ---: | --- | ---: | --- | --- |
| `cluster_1ba596334ad5cde7` | 2 | FAILED | 0/0 | Precedence question stays in representative_question but drops from open_questions. TL version/date request is not structured guidance. No document is declared superseded. | MEDIUM contradicts INSUFFICIENT_EVIDENCE; generic clarification rationale does not establish impact. |
| `cluster_6b59d13144282285` | 6 | FAILED | 2/2 | M04 lacks factual citations; only 4/19 messages assessed. One scoped playback instruction survives, but other handling questions/TL instructions and conditions are missing. No fabricated workaround attempt/failure. | HIGH blockage may be defensible for affected tasks; material-quality risk, submission inability, and broad scope are not established. |
| `cluster_a6dfe8374217a497` | 3 | FAILED | 0/0 | Keeps “on its own” but drops school-context/independent-flag limits and structured TL-endorsed guidance. Broad question absent from open_questions. | UNKNOWN is reasonable; empty criteria and rationale citations are invalid. |
| `cluster_024655fb52cc3352` | 1 | FAILED | 0/0 | Avatar question remains unresolved; tentative design-assets/pinned-files lead is omitted. | N/A is appropriate; empty criteria and insufficient-evidence basis are invalid. |
| `cluster_14c5fc257d90b58f` | 5 | FAILED | 3/3 | M03's click-does-nothing evidence is absent; disabled/silent-click differences and submission-status conditions are lost. Causal question cites an announcement. Reliability flags are misused as evidence of incoherence. | HIGH is supported as reported cross-project blockage; extent/cause/completed submission remain unverified. |
| `cluster_06c08cf4143f2022` | 1 | FAILED | 0/0 | Correct null representative question and real QA diagnostic. Announcement mislabeled DISCUSSION; structured instructions and required coherence fields omitted. Tutor eyes is not treated as approval. | HIGH blockage is defensible; material-quality risk is unsupported and all severity citation lists are empty. |

QN is Quarantine; there is no “quality note” expansion in these drafts. The actual
TL `agree` reaction is U006 on message `1790893058.000113`, but its qualified answer
was not preserved in structured guidance. The only `eyes` in this selection is by
tutor U013 on the operational announcement; this pilot does not test TL-eyes behavior.
Age-related “minor” is not interpreted as operational severity.

Original artifacts are preserved. Separate, source/output-hash-bound findings and
the review supplement live in
[`data/experiments/agent2_pilot_v3_review_v1/`](../data/experiments/agent2_pilot_v3_review_v1/):
`integrity.json`, `request_ledger.json`, `inherited_obligations.json`,
`source_review.json`, and `review_queue.json`. The supplement flags reported
submission blockage for review without overriding automated severity or clearing
existing obligations. It is not a replacement canonical export/queue.

### Bounded offline fixes and next action

The CLI now prints CONSOLIDATED/FAILED/INTERRUPTED/NOT_RUN counts, saved responses,
and unknown completions. Processing remains nonblocking with the same exit-status
semantics. The request schema now explains existing source-disposition and severity
requirements. An additive `NON_OPERATIONAL` evidence-basis option gives N/A a
truthful basis without inventing an operational risk/outcome; it is restricted to
N/A. Existing UNKNOWN/insufficient-evidence rules, evidence checks and all six
historical rejections remain intact. Schema version remains 3; exact code/request
fingerprints distinguish this revised contract. The operational rubric is unchanged.

The fixes do not establish that the model will preserve missing guidance or scope.
No retry, paid validation, full batch, model change, automatic repair, extra verifier,
or Agent 3 implementation occurred. Agent 3 can still store a separate researched
assessment; Agent 2's original assessment must not be overwritten.

Validation: **375 passed, 0 failed, 0 skipped** (163 warnings; 127.60 seconds),
including 13 new regressions and mocked replay of all six actual rejected responses.
All **8,190** preexisting protected file hashes and **14** Agent 1 code fingerprints
match. The six-case follow-up dry-run passes. The exact command, test XML and
preservation receipt are recorded in
[`validation.json`](../data/experiments/agent2_pilot_v3_review_v1/validation.json).
HIGH/nonblocking review and LOW/N/A inherited-flag retention pass offline tests;
this failed live pilot cannot demonstrate those paths on accepted topics.

A **targeted six-case revalidation** is prepared, not authorized or executed, using
the same 18 identities/five obligations, unchanged model, and a fresh directory.
The selection is `docs/agent2-targeted-pilot-v3-1.json`; exact prepared requests are
in `data/processed/agent2_targeted_pilot_v3_1_prepared/`. All six requests changed
only because their shared schema descriptions/basis enum changed. Review findings
and expected outcomes stay outside requests. Maximum is **six new requests**, one
per group, zero automatic retries/repairs/fallbacks/verifier calls.

Read-only preflight:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-targeted-pilot-v3-1.json
```

For a future separately authorized targeted run only (not executed):

```powershell
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-targeted-pilot-v3-1.json --max-requests 6 --output-dir data/processed/agent2_targeted_pilot_v3_1
```

Do not launch a larger run yet. First source-review those fresh results for full
member/message coverage, retained questions, scoped guidance and supported severity.
This pilot produced no accepted topics and did not exercise split-topic citations,
live accepted-HIGH morning review, malformed JSON recovery, or successful live
merging of flagged members. Offline regressions cover those integration behaviors;
they do not establish live semantic accuracy or a general success rate.

## Historical response replay, not a v3 success-rate estimate

The top-level `data/processed/agent2_full_v1_continued/` is the combined paid run;
its `new_requests/` is a subset and is not counted again. Its unchanged outcomes
are **34 CONSOLIDATED, 55 FAILED, one INTERRUPTED**, covering 200 threads and 49
inherited review obligations. Only 55 threads belong to consolidated groups.
There are 90 attempts, 89 HTTP 200 responses, and one unknown provider completion
(`cluster_128dab46288ce554`). That interrupted request was not retried.

The original responses were replayed against the preserved, real v2 contracts
and validators. Each failed response is counted once by its primary failure:

| Replay outcome | Groups |
| --- | ---: |
| Accepted by original v2 parser | 34 |
| Quotation mismatch | 29 |
| Invalid message reference | 1 |
| Custom consistency rule | 15 |
| Schema error | 4 |
| Malformed JSON | 2 |
| Missing/duplicate/invented membership | 3 |
| Cross-topic citation | 1 |
| Answer-evidence-only failure | 0 |
| No saved response / unknown completion | 1 |

Consistency failures include coherent candidates with multiple topics, invented
questions/answers on pure announcements, and missing review explanations.
Some schema-failing responses also have consistency errors; diagnostic counts
can exceed primary response counts. Structural acceptance does not prove factual
correctness, as the three source-reviewed examples demonstrate.

[Replay summary](../data/experiments/agent2_hardening_v3/original_response_replay/summary.json)
and [per-group diagnostics](../data/experiments/agent2_hardening_v3/original_response_replay/diagnostics.json)
record the validation stage, exception, field path, group and member identities,
and offending reference where applicable. Paid outputs are never rewritten.
To reproduce the replay in another new diagnostics directory:

```powershell
uv run --locked python scripts/replay_agent2_responses.py --source-dir data/processed/agent2_full_v1_continued --output-dir data/experiments/agent2_replay_check
```

## Evidence, completeness, and severity contract

Response/export/configuration schema v3 uses deterministic, request-local member
aliases (`M01`) and original-message evidence IDs (`E001`). The catalog contains
exact Slack text, full identity, authors, roles, and actual reaction users/targets;
it contains no Agent 1 summaries, audit rationales, or evaluation labels. Python
resolves IDs back to exact full-message quotations and canonical member IDs for
export. Unknown IDs fail visibly. There is no fuzzy matching, text normalization,
or message substitution. Exact membership partitioning, every-member factual
coverage, and topic-local evidence remain mandatory.

Every message has an explicit source assessment. OPEN/PARTIAL questions must be
cited in `open_questions`; AVAILABLE guidance must appear as scoped guidance or
an answer. An ANSWERED disposition requires a scoped answer from that member's
conversation. Diagnostics are not answers. Guidance has a cited scope, stated
limitations, and source-backed authority. TL endorsement checks the actual user
and target reply and reuses the existing `this`, `agree`, and `white_check_mark`
policy; `eyes` and `thumbsup` are not authority endorsements. Announcements can retain instructions
without invented questions or answers. Qualifiers and reported document conflicts
must remain explicit; no document is declared authoritative by this agent.

The source review and synthetic regressions cover the three observed omissions:

- `cluster_1ba596334ad5cde7`: the supersession question remains open while the TL
  requests both versions/dates and declines to declare either superseded.
- `cluster_6b59d13144282285`: retain the TL instructions to report affected playback
  tasks and avoid a model-quality failure label; keep the possible workaround
  distinct from an established attempt/failure, and loading failures distinct
  from apparently silent clips.
- `cluster_a6dfe8374217a497`: retain "on its own", the benign school-context scope,
  independent-flag checks, and the actual TL-endorsed reply. A broader unresolved
  question must not become a claim that no guidance exists.

These are Codex-assisted source reviews and explicitly synthetic test outputs,
not human approval, live v3 responses, or independent ground truth. The
[source-review evidence](../data/experiments/agent2_hardening_v3/content_review.json)
binds each finding to the saved source and exact historical response.

The historical `severity.py` defines impact but contains no organizational approval
or rubric version. The active **provisional-operational-severity-v1** is explicitly
not approved organizational policy:

| Level | Provisional operational meaning |
| --- | --- |
| HIGH | Substantial reported/observed blockage or material quality/safety risk |
| MEDIUM | Meaningful, limited operational issue requiring clarification/coordination |
| LOW | Operational issue with limited demonstrated consequences |
| N/A | Clearly non-operational content, such as routine social chatter |
| UNKNOWN | Insufficient impact evidence, or unsuccessful/unassessed processing |

The same Agent 2 request supplies each topic's rubric version, matched criteria,
cited rationale, blockage/scope/consequence evidence, reported-risk versus
observed-outcome basis, and `severity_is_provisional=true`. Criteria must match
the level; HIGH requires cited blockage or consequence information. Severity is
not inferred from flags, member count, unanswered questions, safety vocabulary,
or task-label minor/major categories. Operational announcements can be HIGH.
The avatar-image question is a non-operational regression; a submission-blockage
announcement is an operational regression. Failed/interrupted groups remain
UNASSESSED/UNKNOWN, not N/A.

HIGH adds `morning_review_obligations` and enters the nonblocking review queue.
It does not change interpretation reliability or halt later work. LOW/N/A cannot
clear inherited obligations. Agent 2's per-topic `preliminary_severity` includes
`assessor: agent2`; a future Agent 3 revision must be a separate assessment with
its own evidence, never an overwrite of this original assessment.

## Initial v3 preparation (subsequently executed)

The [original selection](agent2-hardening-pilot-v3.json) binds the original v3 code and the
unchanged model `openai/gpt-4o-mini`. Its six groups are the three content-regression
groups above plus avatar location (`cluster_024655fb52cc3352`), submission blockage
(`cluster_14c5fc257d90b58f`), and an operational announcement
(`cluster_06c08cf4143f2022`). Selection purposes stay outside model requests.
**Maximum: six new requests, one per group; zero retries, revisions, fallbacks,
or separate verifier calls.** The offline hardening milestone only prepared this
selection; its subsequent user-executed results are reviewed above.
The selection contains 18 threads and five inherited Agent 1 review obligations.
The following command examples document the original preparation/execution. Its
fingerprint is intentionally stale after the bounded fixes above; use the new
targeted selection for current preflight, and preserve the old pilot unchanged.

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-hardening-pilot-v3.json
```

Historical execution command (already executed; preserve its destination):

```powershell
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-hardening-pilot-v3.json --max-requests 6 --output-dir data/processed/agent2_hardening_pilot_v3
```

All 90 groups/200 members/49 obligations also have a new offline-only preparation
in `data/processed/agent2_hardening_offline_v3/`. The six-case exact requests are in
`data/processed/agent2_hardening_pilot_prepared_v3/`. These are NOT_RUN records,
not new consolidations. Use a new directory for any execution. Current dry-run
inspection does not require a credential or make calls.

Old selection files (including the four-case file named `agent2-pilot-v3.json`)
refer to **response schema v2** and are intentionally incompatible. Their filenames
are selection revisions, not schema versions. Old responses cannot pass the v3
parser, and old runs cannot be continued under changed code. The v2 validator is
retained solely for historical offline replay. Compatible v3 interruptions use
`continue_agent2_batch.py` with the original selection, newest run as `--source-dir`,
and a new destination; it inspects actual journals and excludes every old attempt,
including start-only and unknown-completion requests.

Recoverable validation/transport failures retain all members and evidence, save
`diagnostics.json` and `validation_diagnostics`, and continue. Fatal configuration
and persistence failures stop and preserve pending groups. Diagnostic/result write
failures are explicitly fatal. Available raw responses and unknown completions
remain visible. No old cached output is relabeled as a v3 model result.

## Historical hardening validation and limits

Final result: **362 passed, 0 failed, 0 skipped** (163 warnings; 133.65 seconds).
The pilot dry-run also passes: six selected groups, 18 identities, five inherited
obligations, and zero calls or writes. Preservation checks matched all **7,917**
preexisting protected file hashes and all **14** frozen Agent 1 code fingerprints.
The complete 90-group preparation retains all 200 canonical rows and all 49
obligations; each of its 90 requests and the pilot's six requests matches current
request construction exactly. Historical artifacts and the existing user deletion
of the pilot archive remain untouched.

The final complete offline suite uses a fresh same-drive temporary directory:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp D:/Christie/2026_AgenticAI/threadsense-agent2-hardening-tests-20261023 --junitxml=data/experiments/agent2_hardening_v3/pytest-results.xml
```

The validation receipt is in
`data/experiments/agent2_hardening_v3/offline_validation.json`. Mocked integration
tests retain all 200 identities and all 49 inherited obligations through failures
and continuation. New regressions exercise evidence resolution, omission guards,
scope/authority, severity, morning review, schema isolation, and persistence errors.

On Windows, keep the temporary directory on the source checkout's drive: two
unchanged Agent 1 reconciliation tests calculate relative paths and cannot use
C: temporary output with this D: checkout. Earlier attempts inside the checkout
also encountered intermittent `WinError 5` during unchanged Agent 1 atomic report
replacement. These environment failures and the final result are retained in the
receipt; no Agent 1 code or assertions were weakened.

The Slack-fixture and topic-catalog checks pass. A separate legacy check,
`scripts/validate_threadsense_dataset.py`, still fails its unchanged line-129
assertion for `1790941015.000132`: it assumes an unresolved thread cannot contain
any TL reply. The actual TL reply (`1790941162.000339`) asks for overlap timestamps
so QA can determine affected scope; it does not answer the original rubric
question. This historical audit assumption conflicts with diagnostic-only replies.
It remains a documented check limitation; source fixtures, evaluation labels,
the frozen evaluation CSV, and Agent 1 outputs were preserved.

A source ID proves traceability, not entailment or completeness. A model may
misclassify a source assessment as NONE, omit a limitation in prose, misjudge scope
or severity, or attach a real but irrelevant source. The inventory/structural
checks and reviewed tests address observed failure modes without proving future
live accuracy. Live v3 success rate and semantic quality remain unmeasured.

## Historical schema-v2 integration record

The following section is preserved historical context. Its architecture and run
commands describe the earlier v2 response contract, not the current v3 workflow.

The offline connection is complete. Agent 2 reads the finalized Agent 1 v3
canonical export directly: **200 unique full identities, 81 VERIFIED,
70 CORRECTED, 49 NEEDS_REVIEW**. All 49 inherited review obligations survive
grouping, model-response validation, and consolidation exports. No paid model
calls were made. The saved full preparation contains **90 NOT_RUN candidates**;
it is not a claim that 200 threads have received live Agent 2 analysis.

## Implemented behavior

`handoff_inputs.py` validates canonical coverage, queue agreement, candidate/source
hashes, source message identities, and saved-result lineage. For the finalized
v3 input it also checks the original completion receipt's artifact hashes.
`topic_inputs.py` joins refreshed groups back to the canonical export and rejects
stale inputs, changed member metadata, duplicate/missing assignments, or crossed
project/batch scope. It no longer reads interpretations from the old 91 groups.

Each member retains its entire original canonical row under `agent1_record`, its
original source snapshot, full project/batch/channel/thread identity, stable
`member_id`, export path/hash, and lineage base. Effective and automated status,
disputed fields, reasons/findings, review evidence, candidate/source hashes, and
original/revised lineage remain intact. Model responses cannot supply or clear
these fields: Python copies them after validation.

The new schema v2 `TopicConsolidation` partitions all supplied member IDs exactly
once. It describes a shared issue, optional question, relevant differences,
unresolved questions, source-cited answers, and uncertainties. Factual prose
requires exact quotations and member-qualified message IDs from the assigned
topic. Every assigned member needs citation coverage. Pure announcements have
no invented question, open-question list, or question/answer resolution.

For any topic with inherited flags or new uncertainty, exported prose carries
`reliability: PROVISIONAL`. Its source-cited answers are retained under
`provisional_answers`, with `supported_answers` empty. Even repeated or confidently
worded model claims cannot clear upstream obligations or enter the supported-answer
slot through merging. Unflagged source-cited prose is explicitly labeled
`SOURCE_CITED_NOT_INDEPENDENTLY_VERIFIED`, not independent ground truth.

Review is nonblocking. One request per candidate is followed by deterministic
membership/evidence checks: **zero retries, zero repairs, no additional verifier
agent or model calls**. Recoverable timeouts, HTTP failures, malformed output, and
validation failures retain the entire candidate and continue with later groups.
Fatal configuration/persistence failures stop; interruption leaves later candidates
NOT_RUN and records unknown provider completion when no response was saved.
Existing output directories are never silently overwritten or resumed.

The group review queue includes inherited and newly arising consolidation flags.
The separate member review queue preserves inherited obligations individually,
independent of recommendations or topic count. Slack resolution stays inside the
unchanged member interpretation and is not used as interpretation reliability.

## Compatibility changes

| Previous behavior | Active v2 behavior |
| --- | --- |
| Load frozen grouping interpretations; require 91 groups | Load all 200 canonical rows directly; validate refreshed membership without a fixed group-count assumption |
| Bare `thread_ids` / message IDs | Stable member IDs bound to full identities; each citation names member, message, and exact quote |
| `TopicAnalysis` / `TopicRollup` with severity, actionability, research needs | Strict factual `TopicConsolidation` / `FactualTopic` in `topic_contracts.py`; Agent 3 fields are rejected |
| CrewAI execution and validation-guided repair scripts | One existing single-POST transport call, deterministic checks, retained failure, no correction loop |
| Human-review screening tied to severity/repair | Nonblocking inherited and new review obligations, independent of recommendations |
| Sample preparation overwrites the historical input | Read-only by default; `--write` creates a new file exclusively |

Legacy classes remain unchanged in `contracts.py` for historical decoding and
Agent 1 fingerprint compatibility. Old Agent 2 outputs, inputs, repair evidence,
and severity/review utilities remain historical assets; the active v2 runner does
not invoke their decision rules. `repair_agent2_sample.py` now explains retirement
and exits without calls. The sample runner uses v2 and allows at most one explicit
`--run` request; the prepared batch pilot below is the evaluation entry point.
The compatibility CrewAI factories use the factual responsibility, but active
batch/sample execution uses the bounded transport directly.

## Refreshed grouping

The approved `scripts/run_thread_grouping.py` is byte-identical to the frozen
baseline's script hash. The new wrapper reuses its embedding and clustering
functions per project/batch, then attaches full canonical metadata and checks
complete identity coverage. It uses the existing cached local MiniLM model with
offline mode enabled; no download or paid embedding service was used.

Unchanged configuration: `sentence-transformers/all-MiniLM-L6-v2`, revision
`b9db1e8a0d3a51769172ba8546f282a73f066e47`, CPU, normalized embeddings, original
question/summary text format, complete-linkage agglomerative clustering with
cosine distance, **threshold 0.50**, project/batch scope, and identical package
versions. The historical script's CLI default of 0.35 was not used.

| Project | Old groups | New groups | Old singletons | New singletons | Review members |
| --- | ---: | ---: | ---: | ---: | ---: |
| Audio/multimodal | 20 | 18 | 9 | 6 | 12 |
| Multilingual | 24 | 22 | 10 | 7 | 13 |
| Response preference | 23 | 25 | 6 | 9 | 16 |
| Safety classification | 24 | 25 | 7 | 9 | 8 |
| Total | **91** | **90** | **32** | **31** | **49** |

There are 61 unchanged membership groups containing 132 threads; 68 threads have
different group memberships. Thirty old memberships are replaced by 29 new
memberships. Forty refreshed groups contain the 49 flagged members. No embedding
inputs were truncated. Candidates remain tentative: a grouping change does not
prove improved semantic accuracy, and a representative summary is not an established
fact. The frozen baseline remains unchanged in `data/processed/grouping/`.

Commands used for local preparation (already completed; do not overwrite them):

```powershell
.venv\Scripts\python.exe scripts/prepare_agent2_grouping.py --write
.venv\Scripts\python.exe .cache/agent2_integration_20261022/prepare_offline_artifacts.py
```

The second helper explicitly disables network, credential retrieval, and model
completion while saving the offline requests, pilot selection, and synthetic
example. For later fresh preparation, use `run_agent2_batch.py --prepare` with a
new output directory. Inspection alone is read-only:

```powershell
uv run --locked python scripts/prepare_agent2_grouping.py
uv run --locked python scripts/run_agent2_batch.py --dry-run --limit 0
```

## Offline validation and representative output

The focused suite passed **48 tests**. The complete suite passed **308 tests,
0 failures, 0 skips**, with 162 dependency warnings in 104.67 seconds:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-agent2-integration-final -o cache_dir=.cache/agent2_integration_20261022/pytest-cache
```

Thirty-one new tests cover canonical loading/corruption, all 200 identities and 49
flags, exact full-scope membership, stale groups, approved grouping parameters,
request isolation, exact quotes and topic-local evidence, legacy-field rejection,
announcements, qualified answer export, and failure continuation. A mocked run over
all 90 candidates makes exactly 90 mocked attempts: 88 structurally valid results,
one timeout, one malformed response, zero unprocessed groups, and all 49 inherited
obligations retained. The timeout remains visible with unknown completion. Fatal
configuration/persistence and interruption tests retain unprocessed groups honestly.
These outcomes establish integration behavior, not live semantic accuracy.

The [representative export](../data/processed/agent2_offline_v2/examples/flagged_consolidation.json)
is a **synthetic offline example constructed with Codex assistance from actual
saved Slack**, not a model response, human approval, or independent ground truth.
It partitions the six-member playback/silence candidate into two topics. Its
playback summary says members recall only a possible workaround; attempts/failure
are not established. Exact Priya replies supply limited task-reporting guidance,
retained as provisional because the topic has unresolved member disputes.
Threads `1790882197.000111` and `1790920171.000109` keep their complete review
obligations. Silent-clip diagnostics do not become a quarantine/scoring answer.
The reviewed input fixture is in `tests/fixtures/agent2_flagged_example_v2.json`.

## Prepared live pilot — not executed

The [selection](agent2-pilot-v2.json) binds exact canonical/grouping/configuration
hashes and the existing configured model **`openai/gpt-4o-mini`**. Selection notes
stay outside model requests. Each case is an independent request with no history.

| Case | Candidate group | Members / inherited flags | Focus |
| --- | --- | ---: | --- |
| 01 | `cluster_6b59d13144282285` | 6 / 2 | Possible workaround versus failed attempt; QN; loading versus silent-clip membership |
| 02 | `cluster_6042d88a3d171626` | 4 / 1 | Recording/reference distinction and evidence-supported answer scope |
| 03 | `cluster_08694739f8f88214` | 2 / 1 | Announcements without invented questions |
| 04 | `cluster_430237353843237f` | 3 / 1 | Citation mismatch example, unresolved scoring, membership differences |

Total: **4 groups, 15 threads, 5 inherited review obligations, at most 4 new request
attempts**. There are no repair, retry, fallback, or separate verifier calls.
Exact prepared requests are in `data/processed/agent2_pilot_prepared_v2/records/`.
No call markers or raw responses exist because no requests have been attempted.

Read-only pilot preflight:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --dry-run --pilot docs/agent2-pilot-v2.json
```

Prepared live command, **not executed in this milestone**:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini'
uv run --locked python scripts/run_agent2_batch.py --run --pilot docs/agent2-pilot-v2.json --max-requests 4 --output-dir data/processed/agent2_pilot_v2
```

Keys come from the existing local `.env`. Use a new output directory; existing
attempts are never retried. The live runner saves exact request bytes, call/start
markers, available raw responses, parsed/failed results, group and member review
queues, and a manifest. A validly completed run with review items exits successfully;
fatal/incomplete work does not. Future live source review must assess actual
responses, including topic boundaries and factual entailment.

## Handoff artifacts and limits

- [Refreshed candidates](../data/processed/grouping_agent1_v3/clusters.json).
- [Grouping comparison](../data/processed/agent2_offline_v2/grouping_comparison.json).
- [All 90 pending candidate records / 200 members](../data/processed/agent2_offline_v2/consolidations.json).
- [49 inherited member obligations](../data/processed/agent2_offline_v2/member_review_queue.json).
- [40 pending candidate groups requiring review](../data/processed/agent2_offline_v2/review_queue.json).
- [Offline preparation manifest](../data/processed/agent2_offline_v2/manifest.json).
- [Offline validation receipt](../data/processed/agent2_offline_v2/offline_validation.json).
- [Prepared pilot manifest](../data/processed/agent2_pilot_prepared_v2/manifest.json).

Exact quotation checks establish that evidence exists, not that a paraphrase is
entailed or a reply is substantive. A model can still invent questions, conflate
incidents, miss uncertainty, or misread an answer. The conservative export prevents
known flagged claims from becoming accepted answers; it cannot discover every
previously missed semantic error. Consolidation can split within a candidate; it
does not recursively merge across candidates. Live accuracy remains unmeasured.

Agent 1's candidates, all fourteen fingerprinted code files, completed v3 outputs,
historical evidence, both review registries, frozen grouping, evaluation data,
dependency declarations/lockfile, and local environment are preserved. No Agent 1
verification/report refresh was run. Future refreshes still require both review
registries. Remaining work is the bounded live Agent 2 pilot and source review,
then separately authorized downstream work. Agent 3, RAG, and the dashboard were
not implemented; future briefing consumers must preserve both inherited member
obligations and new Agent 2 group-level flags, including items with no recommendation.
