# Agent 2 offline integration — 2026-10-23

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
