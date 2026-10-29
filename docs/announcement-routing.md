# Announcement sources and prospective discussion routing

This integration routes announcement channels before interpretation. It makes no
model calls or embeddings and adds no retrieval backend. The completed Agent 1
v3 and Agent 2 v7 releases remain historical evidence, including their original
200 identities, 49 inherited obligations, raw responses and review findings.

## Data flow and configuration

`routing.py` is the shared deterministic boundary. Explicit IDs/types in
`data/config/channel_routes.json` identify the four announcement channels:
`C_AUDIO_ANNOUNCEMENTS`, `C_MULTI_ANNOUNCEMENTS`, `C_RP_ANNOUNCEMENTS` and
`C_SAFETY_ANNOUNCEMENTS`. Existing GENERAL, QA and TUTOR metadata identifies
discussions. Conflicting configuration fails; names, keywords, a TL reply and
`eyes` reactions never determine the route or approval.

- Announcement source activity → extraction → immutable knowledge-source JSON.
- Discussion activity → unchanged Agent 1 interpretation → approved local
  clustering → taxonomy-only Agent 2.
- Both routes retain identity, source evidence and any matching canonical Agent 1
  review metadata. Routing cannot clear an obligation.

Daily extraction requires an explicit timezone-aware cutoff. Selection uses
`[cutoff minus 24 hours, cutoff)`, comparing exact decimal Slack timestamp strings.
An older root is included when a supplied reply or edit is in the window; older
parent/context messages stay attached. A visible post-cutoff edit makes historical
content reconstruction impossible, so that thread is reported as a selection
failure. Unreadable timestamps are explicitly unclassified, not counted as outside
the window. Thread counts, active message counts and context counts are separate.

The fixture adapter exposes creation and supplied last-edit timestamps only.
It cannot recover deleted messages, earlier edit versions or reaction event times;
reaction-only activity is not claimed. Snapshot reactions have attribution but no
guarantee they existed at a historical cutoff. A live Slack connector is deferred.
TL decisions outside announcement channels are not mirrored in this implementation.

## Zero-call commands

Run from the repository root with the existing locked environment. This cutoff
matches the saved fixture day; use the actual timezone-aware cutoff for later
source snapshots. No environment API key is required by these commands.

```powershell
uv run --locked python scripts/route_source_activity.py --dry-run --cutoff 2026-10-02T12:00:00Z
uv run --locked python scripts/run_agent1_batch.py --dry-run --limit 0 --cutoff 2026-10-02T12:00:00Z
uv run --locked python scripts/prepare_agent2_grouping.py
uv run --locked python scripts/run_agent2_batch.py --dry-run --limit 0
```

To exercise persistence with the existing fixtures **in temporary storage**, use
fresh receipt paths on each invocation. Repeating the same window deduplicates the
source versions. Receipts belong outside knowledge directories.

```powershell
uv run --locked python scripts/route_source_activity.py --write --cutoff 2026-10-02T12:00:00Z --source-dir .cache/source-routing-demo --manifest .cache/source-routing-demo-first.json
uv run --locked python scripts/route_source_activity.py --write --cutoff 2026-10-02T12:00:00Z --source-dir .cache/source-routing-demo --manifest .cache/source-routing-demo-repeat.json
```

For your supplied source snapshot, replace `--fixtures` with its directory
(the existing adapter's `channels/*.json` and `users.json` format) and omit
`--source-dir` to persist under `data/knowledge/decisions`. Use one writer per
source directory. No source content was added to production knowledge folders
by this integration. `--write` never interprets the discussion route.

To save the full canonical routing ledger without embeddings:

```powershell
uv run --locked python scripts/prepare_agent2_grouping.py --routing-manifest .cache/canonical-routing.json
```

Each ledger path must be fresh. Agent 2 preparation also saves the complete
partition as `routing_manifest.json`, including excluded announcement sources and
their inherited obligations. Each projected group references its hash.

Agent 1 sample/batch live processing now requires `--cutoff`. Inspection/list
mode is read-only. Batch dry runs without a cutoff explicitly inspect the complete
snapshot, not a daily window. The verification runner consumes already frozen
interpretations, filters announcement sources and records its routing partition;
it is not daily ingestion and cannot be used to refresh the frozen v3 directory
under its old fingerprint. Use the historical effective loaders to inspect releases.
No interpretation/verification executions are part of this integration.

## Source format and manual locations

The machine-readable schema is [knowledge-source.schema.json](knowledge-source.schema.json).
`SourceRecord` additionally verifies identity/content hashes and timezone-aware
timestamps; JSON Schema alone cannot express these checks.

| Field | Meaning |
| --- | --- |
| `schema_version` | `knowledge-source-v1` |
| `source` | `system` (`slack` or `manual`); known workspace, project, batch, channel, thread, message IDs; reference/permalink |
| `source.manual_key` | Required stable key for a manually authored source; do not change across revisions |
| `scope` | `project`, explicitly `shared`, or `unknown`; missing project is never global authority |
| `document_type`, `record_kind` | announcement/status update, explicitly marked decision, guideline or FAQ; no semantic inference |
| `original_text`, `author` | Original content and recorded author identity/role; unknown metadata stays null/empty |
| `replies`, `reactions`, `source_metadata` | Original attributed context, reaction users/targets and structured source metadata |
| `authority` | Recorded role and explicit approval marker, if supplied; channel membership and reactions do not establish approval |
| `created_at`, `edited_at` | Source event times |
| `source_capture_at`, `captured_at` | Supplied snapshot capture time, versus local extraction observation time |
| `extraction_window` | Daily selection receipt, distinct from source event time |
| `effective_at`, `supersedes` | Explicit structured source values only; no inferred precedence |
| `inherited_agent1` | Complete matching canonical member, including review reasons, evidence, hashes and lineage |
| `record_id`, `version_id`, `content_sha256` | Computed and verified identity/content bindings |
| `previous_version_ids` | Prior versions of the same record; separate from decision supersession |

For a manual file, supply `source.system="manual"`, a stable `manual_key`, known
project/scope, `document_type`, matching `record_kind`, and `original_text`.
Supply additional metadata when known. Omit the three computed ID/hash fields;
the adapter calculates them (or validates supplied values). A manual copy of an
actual Slack source should keep `source.system="slack"` and its exact original
IDs, enabling deduplication with later extraction. JSON may contain one record
or a list of records. Do not substitute realistic invented source evidence.

Place your own content in:

- `data/knowledge/instructions/manual/<stable-key>/<revision>.json`
- `data/knowledge/faq/manual/<stable-key>/<revision>.json`
- `data/knowledge/decisions/<project>/manual/<stable-key>/<revision>.json`

Project directories are `audio_multimodal`, `multilingual_eval`,
`response_preference`, `safety_classification`; `cross_project` requires explicit
shared scope. Unknown projects are extracted to `_unknown`, not `cross_project`.
The existing `data/knowledge/domain_lexicon.json` stays in place and is not treated
as a document by this adapter. The editable severity rubric is also not a document.

Extraction writes only
`decisions/<project>/extracted/<record_id>/<version_id>/source.json`. It never
overwrites an earlier version or a manual file. A changed reply, text, source
metadata or preserved review metadata creates a distinguishable version; changing
capture time/window alone does not. Keep manual versions immutable and add a new
revision file when content changes. There is no “newest always wins” policy.
Malformed manual JSON blocks extraction for that project explicitly rather than
being ignored. Failed atomic writes remain visible in receipts; inspect a partial
version directory before rerunning. No automatic persistence retries are added.

## Shared knowledge ingestion contract

`knowledge_sources.iter_documents(paths)` accepts extracted and manually supplied
historical JSON, regardless of age, and Markdown files with
`authoring_schema: mock-knowledge-markdown-v1` front matter (added for Agent 3
milestone 2; mapping in [agent3-plan.md](agent3-plan.md#milestone-2-implemented)).
`normalize_document(record)` emits:

```text
document_id: stable source identity hash
version_id: content version hash
text: original content plus explicitly attributed context replies
metadata: JSON-serializable source, project/batch/scope, document_type,
          timestamps, authority, citation provenance, content hash,
          revision links and inherited review metadata
```

Identical document/version pairs are emitted once per ingestion. Receipts,
verification findings and hashes stay in metadata, not embedded text. Replies
remain context, not approved decisions. Source versions older than 24 hours are
available: the daily limit applies to extraction only.

The future flow is **source documents → shared ingestion/chunking/embedding →
shared vector database → Agent 3 retrieval**. The ingestion job discovers source
paths; Agent 3 need not know filesystem paths or query a decision-specific store.
Guidelines, FAQs, announcements and decisions use this same envelope. Future chunks
must carry parent `document_id`, `version_id`, citation provenance, project/scope,
authority and review metadata. Collection/namespace choices are logical indexing
organization, not another storage solution. Chunking, search, ranking, embeddings,
vector writes, conflict resolution and Agent 3 integration are deferred.

## Severity and compatibility

The deleted `agents/severity.py` was still imported by contracts, topic review,
v2 compatibility and active v7 post-export assessment. These imports are resolved:
neutral historical enums live in `legacy/severity_types.py`; exact historical v7
assessment/export behavior is isolated in `legacy/taxonomy_severity_v7.py` and
`legacy/topic_taxonomy_v7.py`. This is not a duplicate of the editable rubric.

The subsequent source-folder cleanup moved historical v2-v6 contracts,
consolidation engines and their evidence/severity helpers into
`src/threadsense/legacy/agent2/`. `agents/topic_contracts.py` now contains only the
current taxonomy schema. The active taxonomy uses shared identity/hash validation
from `topic_inputs.py` and no longer imports the v6 semantic engine. See the
[source layout](../src/threadsense/agents/README.md). Saved output bytes and schema
definitions remain unchanged; new code fingerprints include the relocated paths.

Active Agent 2 performs no rubric evaluation. Its export is now **schema 8**,
`taxonomy-to-canonical-v2`, with `agent2-taxonomy-handoff-v2`. Compatibility severity
is only `UNKNOWN`, `UNASSESSED`, deferred to `AGENT3`, with no claimed assessor,
rubric evaluation or automatic LOW fallback. Inherited flags remain independent.
The taxonomy model prompt and strict response schema remain version 7 unchanged.
Historical schema 7 loading/replay preserves its original severity metadata and
handoff v1. No historical output is rewritten.

`data/knowledge/severity_rubric.py` is the intended editable Agent 3 rubric,
version `severity-rubric-v2-with-signals`. Its rules were not changed. Two strategy
questions remain: `get_rubric_for_project` currently returns only the default
rubric; the LOW-default comment needs reconciliation with UNKNOWN when evidence
is insufficient. Neither becomes runtime behavior here.

The approved grouping algorithm and configuration are unchanged. An exact copy
of the old grouping producer is isolated in `legacy/grouping_v1.py` so historical
fingerprints remain meaningful. Current loaders validate the full original input
set, then project membership to discussions; partial groups receive new IDs and
all projected groups carry routing provenance. This is not fresh embedding-based
clustering. Explicit historical loaders retain all 200 inputs.

The prior repository cleanup removed runtime JSON registries still required by
historical loaders. Eighteen exact metadata files were recovered from commit
`b293f3b` under `data/metadata/historical`, with hashes checked against saved
receipts and recorded in `recovery_manifest.json`. Only enumerated missing logical
paths resolve to these hash-verified copies; arbitrary fingerprint failures are
not bypassed. The active Agent 2 review registry is
`data/metadata/agent2-review-supplements.json`. Deleted prose reports were not
restored, and both Agent 1 review registries remain available.

## Validation receipt

The saved fixture window above yields **200 source threads / 516 messages**,
**178 discussions / 22 announcements**, no selection/extraction failures, and zero
calls. All 22 source records validate without storage in dry-run mode. Canonical
review accounting is **41 discussion obligations + 8 announcement obligations =
49**. Projecting the existing grouping yields **81 discussion groups**, retaining
all 178 eligible identities, with no embeddings computed.

Persistence was also exercised only under `.cache/source-routing-demo`: the
first invocation saved 22 new records; the second skipped 22 duplicates. Both
reported zero failures/revisions/calls. The common adapter emits 22 unique
document/version pairs and retains all eight announcement-side obligations with
source/candidate lineage. Production knowledge folders contain no added content.
All **819 frozen v7 files** match the hashes captured before this work, and all
18 recovered metadata files match their saved receipt hashes.

The full regression execution recorded **578 passed / 25 failed**. These exposed
the new routing receipt's placement/cache recognition and test migrations
(historical payload selection and the new cutoff requirement). A subsequent
affected run recorded **163 passed / 9 failed** before the remaining cache receipt
recognition and cutoff fixture fixes. Its Agent 2 migration checks all passed.
The final focused receipt is **87 passed / 0 failed**, including all remaining
failed cases and the new assembly/continuation regressions. These are separate executions, not counts
that can be added into a green full-suite claim. An earlier collection attempt
stopped on a test-fixture indentation mistake, which was corrected.

Exact commands used (existing local Python 3.13 environment, no dependency sync):

```powershell
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_announcement_routing.py tests/test_knowledge_sources.py -q --tb=short --basetemp .cache/pytest-routing-initial
.venv\Scripts\python.exe -X utf8 -m pytest -q --tb=short --basetemp .cache/pytest-routing-regression-2 --junitxml=.cache/announcement-routing/regression-2.xml
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent1_verification_batch.py tests/test_agent2_inventory.py tests/test_agent2_pilot_review.py tests/test_agent2_structured.py tests/test_llm_configuration.py tests/test_announcement_routing.py tests/test_knowledge_sources.py -q --tb=short --basetemp .cache/pytest-routing-affected --junitxml=.cache/announcement-routing/affected.xml
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent1_verification_batch.py tests/test_llm_configuration.py tests/test_announcement_routing.py tests/test_knowledge_sources.py tests/test_agent2_continuation.py -q --tb=short --basetemp .cache/pytest-routing-final --junitxml=.cache/announcement-routing/final.xml
```

The initial focused receipt was **33 passed**. Additional source/sample, assembly
and continuation regressions were added afterward. Historical Windows atomic
replacement and cross-drive temporary-path failures remain documented limitations
of earlier receipts; this integration does not claim to have repaired them. The
current commands use workspace-local temporary paths. No full-suite rerun was
performed merely to obtain a green receipt. Mocked tests establish routing and
compatibility behavior, not model accuracy.

`git diff --check` and Python compilation also passed. No new paid requests,
embeddings, index writes or Agent 3 implementation occurred.

## Changed implementation areas

| Files | Change |
| --- | --- |
| `routing.py`, `source_ingestion.py`, `adapters/mock_slack.py`, `models.py`, `data/config/channel_routes.json` | Shared channel partition, exact activity windows, lossless source context and explicit TUTOR support |
| `knowledge_sources.py`, `scripts/route_source_activity.py` | Validated versioned files, immutable persistence and common historical/manual ingestion envelope |
| `run_agent1_batch.py`, `run_agent1_demo.py`, `run_agent1_verification.py`, `agents/thread_interpreter.py` | Route before processing, require daily cutoff for fresh interpretation, bind routing receipts to new verification caches |
| `handoff_inputs.py`, `topic_inputs.py`, `topic_grouping.py`, grouping scripts | Full canonical validation followed by complete discussion/announcement accounting, preserving approved grouping parameters |
| `topic_taxonomy.py`, `topic_consolidation.py`, `topic_pipeline.py`, `topic_effective.py`, `topic_continuation.py`, Agent 2 preparation/assembly scripts | Versioned unassessed export and retention of routing/obligation evidence through handoff, assembly and continuation |
| `legacy/`, legacy enum import consumers | Explicit historical serialization, replay and approved algorithm compatibility |
| `metadata_paths.py`, `agents/verification_handoff.py`, `data/metadata/`, `.gitattributes` | Hash-checked recovery of required historical JSON metadata, preserving byte-sensitive copies |
| `tests/test_announcement_routing.py`, `tests/test_knowledge_sources.py`, affected regression fixtures | New offline behavior checks and explicit historical contract bindings; no augmented saved model responses |
| Knowledge folder READMEs, schema, this guide, README and summary addenda | Manual authoring locations, operational commands and compatibility documentation |

All Python module names above are under `src/threadsense/` unless identified as
scripts. No dependency, prompt, grouping parameter, lexicon, source fixture or
historical result changes were made.
