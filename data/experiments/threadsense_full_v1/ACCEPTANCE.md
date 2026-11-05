# Full ThreadSense run v1: acceptance

Fresh live run of the complete pipeline over the demo fixture snapshot (`data/fixtures/slack_generated_demo`, 201 threads,
cutoff 2026-10-02T12:00:00Z): routing, then Agent 1 interpretation and verification, then grouping, then Agent 2
taxonomy, then Agent 3 overnight advice, then the morning brief. Run 2026-11-05, 16:32 to 19:25 UTC.

**Status: COMPLETE.** Every planned item is accounted for. One thread was rejected by Agent 1 and is recorded as
unfinished work, not dropped. Every result in this run is labelled `FRESH_LIVE`, apart from 10 verification requests
labelled `REUSED_RUN`: each was byte-identical to a request already sent in this run, so its saved response was served.
No earlier Agent 1 or Agent 2 result was used.

## Configuration (frozen in `run_manifest.json`)

| Stage | Model | Notes |
|---|---|---|
| Agent 1 interpretation | `openai/gpt-4o-mini-2024-07-18` | `scripts/run_agent1_batch.py` |
| Agent 1 verification | `openai/gpt-4.1` (returned `gpt-4.1-2025-04-14`), with revisions on gpt-4o-mini | `scripts/run_agent1_verification.py` (fingerprinted bytes unchanged) |
| Agent 2 | `openai/gpt-5.4-2026-03-05`, reasoning low, 8,192 output tokens | `topic_pipeline.execute_batch` |
| Agent 3 | `openai/gpt-6.1-sol`, medium reasoning, default tier, 24,000 / 16,384 tokens, 120 s, 0 SDK retries, no fallback | overnight workflow, prompts v18 |

Settings: ReAct research off, flag-impact off, conditional revision and ToT on. The corpus, rubric, routing, prompts and
evaluation labels are unchanged. The retrieval index is `.index/retrieval` (build `4da16f090eb5`), copied into
`snapshot/`.

## Budget and cost

The hard ceiling was $39.00, fixed in `ledger.sqlite3` for the whole run; the expected-spend target was $30 or less.
Before each request, the run reserved that request's maximum possible charge.

| Agent | Requests | Charged | Preflight expected | Largest reservation |
|---|---:|---:|---:|---:|
| Agent 1 interpretation | 178 | $0.055 | $0.15 | $0.003 |
| Agent 1 verification | 496 sent + 10 reused | $3.671 | $3.88 | $0.135 |
| Agent 2 | 76 | $0.307 | $0.32 | $0.128 |
| Agent 3 | 187 | $11.284 | $10.85 | $0.227 |
| **Total** | **937 sent** | **$15.317** | $15.20 | |

Ledger facts:
- All 947 ledger rows ended SETTLED or REUSED; none was left UNCERTAIN or RESERVED.
- Every sent request returned HTTP 200 and has a provider request ID.
- The returned model snapshots match the configuration.

Agent 3's own ledger reports $10.14 because it prices all Sol input at $2.00 per million. The run ledger prices Sol's
reported `cache_write_tokens` at the $2.50 cache-write rate, and the run ledger figure is the one used here.
- Agent 3 work: 81 drafts, 81 groundings, 17 revisions and 8 ToT comparisons. 60 items used 2 requests, 17 used 3 and
  4 used 4.
- The run had two resumes, both recorded in `run_manifest.json` with reasons:
  1. Agent 1 rejected one thread. Verification needs a source view without it, so the pipeline was changed to build
     that view and record the thread as unfinished work.
  2. An attempt-numbering fix (FileExistsError raised before any request).

  Neither resume resent a request.

## Cache savings (actual)

- **Provider prompt caching:**
  - Agent 1 interpretation: $0.007 saved.
  - Agent 1 verification: $0.024 saved (44,032 cached tokens).
  - Agent 2: no cache reads (short, distinct prompts).
  - Agent 3: no cache reads. Sol reported 2,297,573 cache-write tokens, almost all of its input. Each draft, revision
    and grounding prompt starts with item-specific content, so no 30-minute prefix was ever read back. At the
    documented write rate this cost about $1.15 more than the plain input rate, with nothing saved.
- **Local cache within the run:** 10 identical verification requests were served from the run's own cache, avoiding
  $0.123.
- **Local cache in replay:** the network-disabled replay reused all 947 responses, avoiding $15.32 (see Validation).

## Accounting

| Stage | In | Out |
|---|---|---|
| Routing | 201 threads | 23 announcements to the knowledge path; 178 discussions to Agent 1 |
| Agent 1 interpretation | 178 | 177 accepted; 1 rejected (`multilingual_eval` C_MULTI_QA `1790866887.000147`, AUTHORITY_INELIGIBLE: it cited an ineligible author's message; retries disabled) |
| Agent 1 verification | 177 | 79 VERIFIED / 61 CORRECTED / 37 NEEDS_REVIEW, 0 unprocessed |
| Grouping | 177 | 76 clusters (27 singletons), 37 review members |
| Agent 2 | 76 groups | 76 CONSOLIDATED, 0 unprocessed, 177 identities, 37 inherited obligations, 28 review groups |
| Agent 3 | 81 work items | 81 cards (61 Needs Review, 8 Recommended Action, 12 Observation), 177 members on cards, 37 queue items, accounting COMPLETE |

Closure: 177 members on cards + 1 recorded rejection + 23 announcements = 201 threads.

The rejected thread is in `final/run_summary.json` under `unfinished_work`, with its failure file and the saved
request and response. It was not verified, grouped or advised.

This run has no announcement-route members and no announcement-route obligations, because announcements bypass Agent 1
here. The 8 announcement-route obligations in `agent2_handoff_v2_projection` come from the historical v7 release,
where announcements had passed through Agent 1.

Needs Review reasons, which overlap: inherited Agent 1 flag 29, grounding failure 25, high severity 21, other 24, open
confirmation 3, temporal conflict 2.

## Validation

Details are in `validation.json`.
- **Cards against evidence:**
  - All 1,238 card references resolve to the topic's evidence ledger and the snapshot.
  - None of the 60 statements judged other than SUPPORTED appears in displayed prose.
  - All 25 cards with failed grounding are routed to Needs Review.
  - I read the 8 Recommended Action cards against their messages and author roles: facts, roles and counts match.
- **Real dashboard:** `scripts/run_dashboard.py` was run on `stages/agent3` with a throwaway decision store.
  - Loaded without error: the brief, all 81 cards, 81 flag views, 555 evidence items, 177 member threads and the
    37-item review queue.
  - A Chrome screenshot of the overview shows 61 / 8 / 21 / 37 with no console errors.
- **Network-disabled render:** `run_threadsense_full.py render` returned the brief with status 200 and all 81 cards.
- **Network-disabled replay:** `data/experiments/threadsense_full_v1_replay/` reused 947 requests, sent 0, spent $0, and
  completed all 7 stages.
  - All 89 compared artifacts are semantically identical to the live run.
  - The differences are limited to timestamps, run paths and the IDs and hashes derived from them.
  - `morning_brief.md` is byte-identical.

## Limitations and follow-ups

- **Agent 1 rejection.** The run has no automatic retry by design. The rejected thread needs a human look or a
  separately authorized rerun.
- **Batch API not used.** It is available for all four models, but using it would mean changing the fingerprinted
  Agent 1 transports and Agent 2's per-group synchronous runner. The estimated saving was under $0.20 for Agent 2.
- **Sol caching added cost.** Automatic cache writes cost about $1.15 with no reads. Prompts that put the shared rules
  first would let later requests read the cache, but that would be a prompt-layout change and needs its own evaluation.
- **Review registries not applied.** The hash-bound human review registries in `data/metadata/` cover the frozen v3/v7
  runs. They do not apply to new interpretations, so this run's 37 NEEDS_REVIEW verifications reach the queue
  unreviewed.
- **Wording defect.** The Agent 2 topic name "Majority threshold…" should read "Major".
- **Dashboard gap.** Five historical announcement documents offer a thread link to a Slack thread that is not in the
  snapshot, so the link returns 404. This is an existing gap.
- **First replay attempt stopped.** It made no calls. An Agent 2 report write hit the known WinError 5 lock, and then
  Agent 3's own budget was computed from the replay's $0 ceiling. The budget is fixed in `pipeline.agent3_budget`,
  with a test. The stopped directory is kept outside the repo at `D:/tsb/full/replay_attempt1_stopped`.
- **Developer evaluation only.** The card inspection is the developer's own; no team lead has reviewed these cards.
- **Not reused.** Severity and wording variation seen in earlier evaluations still applies. No saved TL decisions were
  in the index (0 decisions, 0 earlier announcements kept as history).

## Files

`run_manifest.json` (configuration, checkout, resumes), `preflight.json` (zero-call estimate and wiring checks),
`ledger.sqlite3` and `ledger_summary.json`, `objects/` (exact request bodies without credentials and raw responses,
content-addressed), `snapshot/`, `stages/*/stage_manifest.json` (dependencies, output tree hash, request counts),
`stages/agent3/overnight_run/` (brief, cards, queue, accounting), `final/run_summary.json`, `validation.json`.
