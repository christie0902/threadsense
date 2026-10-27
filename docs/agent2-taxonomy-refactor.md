# Agent 2 taxonomy v7 completion report

**Closed on 2026-10-27: complete with nonblocking review.** All 90 canonical
groups consolidated into 97 topics. All 200 full identities, 516 source messages
and 49 inherited Agent 1 obligations remain available. Zero failed, interrupted
or unprocessed groups; zero unknown completions. The accepted four-group pilot
was reused unchanged; exactly **86 new requests** completed. No retries, repairs,
fallbacks, verifier calls or Agent 3 implementation occurred.

The assisted taxonomy review found no obvious consequential membership defect.
Three naming cautions remain in the effective handoff. This closes taxonomy,
not inherited interpretation disputes or future policy research. Consolidation
acceptance is not an accuracy benchmark.

## Frozen producer and responsibility

Preflight matched the accepted pilot's code, model parameters, prompt, strict
schema, glossary and grouping. All 86 serialized live requests match their frozen
prepared requests. No producer, assembly/export, dependency, glossary, grouping,
Agent 1, model or prompt code changed during this milestone.

| Setting | Accepted and executed value |
| --- | --- |
| Requested / returned snapshot | `openai/gpt-5.4-2026-03-05` / `gpt-5.4-2026-03-05` |
| Reasoning / output allowance | `low` / `max_completion_tokens=8192` |
| Sampling parameters | `temperature`, `top_p`, `logprobs` absent |
| Prompt / strict response schema | `agent2-taxonomy-v7` / 7 |
| Passive export / effective handoff | `taxonomy-to-canonical-v1` / `agent2-taxonomy-handoff-v1` |
| Separate severity rubric / rule | `provisional-operational-severity-v2` / `canonical-impact-availability-v1` |
| Bounds | One request/group; zero retries, repairs, fallbacks or verifiers |

Agent 2 receives canonical summaries/questions, stable member IDs, project/batch
context and the approved glossary. It returns topics, membership rationales and
rejected IDs. Names and rationales are grouping metadata, not authoritative guidance.
It does not interpret Slack, verify answers, generate research narratives or assign
model severity. Full sources and canonical records survive passively.

The original v7 refactor retains explicit historical schema dispatch, bounded
transport, exact partitions, failure preservation and the mandatory output-bound
review registry. Historical v6 modules/results remain preserved; none was reused
as a v7 result. The pre-closure report and guide are archived in
[`previous_docs/`](../data/experiments/agent2_taxonomy_final_v7/previous_docs/).

## Coverage and requests

| Scope | Groups | Identities | Inherited obligations | Attempts / saved responses |
| --- | ---: | ---: | ---: | ---: |
| Accepted pilot, reused | 4 | 11 | 3 | 4 historical / 4 |
| Remaining inputs, newly executed | 86 | 189 | 46 | 86 new / 86 |
| Canonical v7 dataset | 90 | 200 | 49 | 90 original / 90 |

All 90 groups are CONSOLIDATED; FAILED=0, INTERRUPTED=0, NOT_RUN=0.
Every original call has a completed HTTP 200 response, matching requested/returned
snapshot and `finish_reason=stop`. Unknown completions and starts without call
markers are zero. Assembly, review and validation made zero model calls.

| Project | Groups | Members | Topics | Inherited obligations |
| --- | ---: | ---: | ---: | ---: |
| Audio/multimodal | 18 | 45 | 21 | 12 |
| Multilingual evaluation | 22 | 50 | 23 | 13 |
| Response preference | 25 | 55 | 27 | 16 |
| Safety classification | 25 | 50 | 26 | 8 |
| Total | 90 | 200 | 97 | 49 |

Seven groups split into two topics. **200 assigned + 0 rejected + 0
failed/unassigned = 200**, without duplication or loss. All 49 obligations belong
to retained assigned members: three pilot plus 46 remaining. Complete member
objects and inherited obligations compare equal to canonical input/export,
including metadata, evidence, full identity, source/candidate hashes and lineage.
Agent 1 remains 81 VERIFIED, 70 CORRECTED and 49 NEEDS_REVIEW.

Automated review queue: **40 groups**. Reviewed effective queue: **41 groups**,
with **49 inherited obligations plus three naming cautions**. Two cautions affect
already-flagged groups; one adds a review group. Processing outcomes and candidate
text are unchanged. All 97 preliminary topic severities are **UNKNOWN/UNASSESSED**:
canonical inputs lack approved structured impact signals. Review flags and
task-labeling major/minor language do not imply operational severity.

## Usage and spending

Preflight estimated $1.633503 for 1,000 completion tokens per new group, or
$10.911183 at every 8,192-token allowance with estimated input. The existing
86-attempt/output bounds were respected. No additional local dollar cap was found;
provider billing limits were neither probed nor raised.

| Usage | New 86 requests | Reused pilot | Combined historical + new |
| --- | ---: | ---: | ---: |
| Input tokens | 65,807 | 3,386 | 69,193 |
| Cached input tokens | 0 | 0 | 0 |
| Output tokens, including reasoning | 11,280 | 576 | 11,856 |
| Reasoning tokens, already included above | 1,466 | 62 | 1,528 |
| Total tokens | 77,087 | 3,962 | 81,049 |
| Summed request latency | 220.429 s | 13.192 s | 233.621 s |
| Standard-rate cost estimate from usage | $0.333718 | $0.017105 | $0.350823 |

New-request median latency: 2.448 s, range 1.810?5.690 s. This is request latency,
not total batch/persistence wall time. Costs use $2.50/M input, $0.25/M cached input
and $15/M output; they are calculations from provider usage, not invoices.
[Official pricing](https://developers.openai.com/api/docs/models/gpt-5.4).
Exact usage, latency, model IDs and evidence hashes are in the
[`request_ledger.json`](../data/experiments/agent2_taxonomy_final_v7/request_ledger.json).

## Assisted taxonomy review

Codex inspected all **90 groups and 200 canonical summaries/questions**, including
all seven splits, the eight groups fixed before execution across four projects,
and the accepted pilot. No rejected/all-rejected or failed groups occurred.
This is an assisted taxonomy review, not human approval, raw-Slack reinterpretation
or independent ground truth. Evaluation notes never entered runtime requests.

| Review focus | Observation |
| --- | --- |
| Audio splits: `cluster_6042d88a3d171626`, `cluster_e6a79dfad226e738`, accepted `cluster_6b59d13144282285` | Transcript/recording mismatch, silent-file content and player failure kept distinct where split; original members and disputes retained. |
| Multilingual split: `cluster_6d503e25f7b2c30c` | Regional vocabulary acceptability separated from English language switching. |
| Response splits: `cluster_f944891544b06f79`, `cluster_839fecb69ec3fa12` | Cosmetic tie judgments separated from inconsistent QA decisions; unfindable references separated from misattributed DOI. |
| Safety split: `cluster_01c1906236921239` | QA schedule separated from batch/guidance-scope announcement. |
| Fixed audio sample: `cluster_ab4fa9e9a46e0a07`, `cluster_b7e5234380f9ea67` | Playback failures and repeated endings each form coherent groups; repeated-ending name has the caution below. |
| Fixed multilingual sample: `cluster_0df9e215dec4e314`, `cluster_3b950ad40b12ab58` | Mixed-language adherence and Korean register transitions cohere; original distinctions remain in members. |
| Fixed response sample: `cluster_14c5fc257d90b58f`, `cluster_f944891544b06f79` | Submission problems cohere; split tie topics retain individual QA differences. |
| Fixed safety sample: `cluster_7a710abcd893e0a6`, `cluster_1f272d7fa384df0c` | Contextual harmful-wording classification and override-language classification cohere without establishing policy. |
| Announcements and social material | Broad workflow topics and social singletons retained; taxonomy does not create a question or resolve disputed canonical questions. |

Three exact-output findings are registered separately:

| Group | Naming caution | Disposition |
| --- | --- | --- |
| `cluster_7249f5e5bbe9af0b` | ?Requested English audio generated in Spanish? is narrower than member 4's unspecified other-language switch. | Nonblocking; language-adherence grouping remains coherent. |
| `cluster_b7e5234380f9ea67` | ?Repeated final line in exported audio? over-specifies location for members 1 and 4, which still compare file versus player. | Nonblocking; title must not establish cause/location for every member. |
| `cluster_a6dfe8374217a497` | ?Minor mention alone does not require QN? is answer-shaped although canonical members 2/3 retain questions or diagnostics. | Nonblocking; topic label only, never a general Quarantine rule. |

Each finding binds to exact input, raw-response and result hashes and includes
its affected field and canonical member evidence. The effective loader exposes
all three, with zero stale/unapplied findings. Conservative PROVISIONAL assignment
routing does not assert incorrect membership. No name, rationale, automated
result or inherited flag was edited. No prompt experiment was started for wording.
Full per-group evidence is in
[`taxonomy_review.json`](../data/experiments/agent2_taxonomy_final_v7/taxonomy_review.json).

## Validation and limitations

The actual release audit **passed**: exact source-run copies, request/configuration
compatibility, all 90 deterministic response replays, complete canonical records,
exact partitions, 49 inherited obligations, queues, reviewed handoffs, review
bindings, request accounting and severity provenance. Exact command:

```powershell
.venv\Scripts\python.exe -X utf8 data/experiments/agent2_taxonomy_final_v7/validate_release.py
```

The saved [`validation.json`](../data/experiments/agent2_taxonomy_final_v7/validation.json)
is an actual-artifact audit, not a new pytest receipt. One-off receipt writers
use fresh files and should not be rerun over the completed release. No production
or assembly/export code changed, so existing checks were reused and the full
suite was not repeatedly rerun.

| Existing offline receipt | Actual result |
| --- | --- |
| Historical Agent 2 migration checks | 254 passed, 0 failed |
| Active taxonomy checks | 40 passed, 0 failed |
| Full suite, final 570-test workspace collection | 569 passed, 1 failed, 164 warnings |
| Full suite, Windows temporary directory on C: | 568 passed, 2 failed, 164 warnings |
| Isolated unchanged Agent 1 stress test | 1 passed |
| Two unchanged reconciliation tests with D: output | 2 passed |

**294 Agent 2-related checks passed; there is no single green full-suite run.**
The workspace failure was Windows `WinError 5` during atomic replacement in the
unchanged Agent 1 200-record stress test (reproduced on two temporary report files;
external locking cause unconfirmed). The C: run exposed two legacy Agent 1
cross-drive `os.path.relpath` failures against D: evidence. Those limitations remain;
Agent 1 was not rewritten. Exact historical commands and JUnit references are in
[`validation.json`](../data/experiments/agent2_taxonomy_v7/validation.json).
No active Agent 2 persistence or integrity failure occurred during execution,
assembly or reviewed export. No combined ?570 passed? claim is made.

No live rejection, failure, refusal, truncation or interrupted request occurred;
those paths retain offline coverage only. Taxonomy review cannot certify Agent 1
interpretation accuracy or policy truth. Naming granularity remains subjective;
identical names across groups do not imply global deduplication. All inherited
obligations and three cautions continue nonblocking downstream.

## Canonical release and next discussion

Canonical directory: **`data/processed/agent2_taxonomy_final_v7/`**.

- `consolidations.json`: immutable automated 90-group dataset; `records/` contains
  byte-identical source inputs, requests, responses and results.
- `effective_output_reviewed.json`: current maintained snapshot, including
  `taxonomy_handoff` (`agent2-taxonomy-handoff-v1`) and effective review queues.
- `effective_review_queue.json`: matching 41-group reviewed queue.
- `member_review_queue.json`: all 49 original inherited obligations.
- `review_queue.json`: original automated 40-group queue, preserved separately.
- `manifest.json`: immutable assembly receipt; `release_manifest.json`: current
  reviewed handoff pointer, hashes, counts and review provenance. Assembly-time
  `effective_output.json` is historical; use the reviewed view or loader.

The mandatory registry retains all eleven historical entries, then adds the
assembler's empty v7 review aggregate and the new exact-output taxonomy review.
No v6 content dispute applies to new taxonomy outputs. Completed freezes and
original pilot remain unchanged. Preservation details are in
[`preservation.json`](../data/experiments/agent2_taxonomy_final_v7/preservation.json).
Only execution/evidence artifacts, review registrations and maintained docs were
added/updated; no historical artifacts or unproven clutter were removed.

Agent 2 is closed at this scope. Next is an **Agent 3 strategy discussion** using
[the updated handoff](agent3-strategy-handoff.md), not more Agent 2 calls or an Agent 3
implementation. The [operational guide](agent2-offline-integration.md) provides
current read-only inspection and zero-call export commands.
