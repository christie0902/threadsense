# Fresh-15 model comparison (experiment only)

A small designed fixture (`threadsense_fresh_15_v1`: 15 Slack roots, 6 knowledge documents) run through the standard
ThreadSense pipeline with two model plans. Nothing here changes `main`, the accepted briefing, the public demo or any
saved run; no tracked file and no dependency lock changes.

- **Base:** branch `model-comparison-experiments` at `fd4e53c8e1bf0b1ec02f35de100b4fbd63e967a9` (= `main` = `origin/main`
  on 2026-11-16). The working tree was clean, so there were no uncommitted changes to preserve.
- **Run A:** Claude Sonnet 5.5 (`claude-sonnet-5-5`, native Claude API, your `ant auth login` profile) for every role:
  Agent 1 interpreter, revision, auditor, prose comparison and relevance verifier; Agent 2 taxonomy and consolidation;
  all Agent 3 stages.
- **Run B:** Grok 4.7 (`grok-4.7`, api.x.ai, `XAI_API_KEY`) for the same Agent 3 stages, on Run A's exact Agent 2
  handoff: a `branch` of Run A serves every Agent 1 and Agent 2 request from Run A's saved responses and may send only Grok.
- **Run C (`--arm gpt`):** the repository's original OpenAI plan (gpt-4o-mini / gpt-4.1 / gpt-5.4 / gpt-6.1-sol) on the
  standard transports, unchanged except for the experiment inputs and the Agent 3 user directory; only api.openai.com
  and those four models may send.
- Same local embedding model (all-MiniLM-L6-v2) and the same isolated index (`.index/fresh_15_v1`) for all runs.
- Runs A and B send nothing to OpenAI or OpenRouter (enforced by the route allowlist; checked in the ledger afterwards).

**Results: [RESULTS.md](RESULTS.md)**. Fixes made during the runs:
- `topic_merge.candidates` no longer fails when no pair qualifies (with a test).
- Route-label prices for the Agent 3 reservation.
- Agent 3's user directory now points at the experiment fixture (the default was the demo fixture, which invalidated
  Run A's Agent 3).
- A 600 s delivery timeout.
- The `agent3` command: Agent 3 alone on a saved handoff, with no response reuse.
- `--xai-stream`: streamed Grok delivery (implemented, not run).

## Layout

| Path | What | Read by the pipeline? |
| --- | --- | --- |
| `source/threadsense_fresh_15_fixture.json` | the attached portable fixture (read-only) | no; only by `convert_fixture.py` |
| `answer_key/threadsense_fresh_15_answer_key.md` | the attached answer key (read-only) | **never** |
| `convert_fixture.py` | one-off converter to the repository formats | — |
| `inputs/slack/` | converted Slack fixture (`adapters/mock_slack.py` format) | yes |
| `inputs/knowledge/` | converted knowledge Markdown (`mock-knowledge-markdown-v1`) | index build only |
| `id_map.json` | T01–T15 and PILOT-K01–K06 → runtime IDs, and the mapping choices | no |
| `freeze.json` | sha256 of the fixture, answer key, converter, ID map, inputs and index manifest | checked by preflight and recorded in each run |
| `run_experiment.py`, `delivery.py`, `preflight.py` | the experiment runner (runtime overrides only) | — |
| `preflight_report.json` | the last preflight | — |
| `runs/` | A, A2 (Sonnet), B, B2 (Grok, failed), C v1 (expired key), C v2 (GPT) run directories | — |
| `summarize_run.py`, `reports/` | read-only run summaries (never read the answer key) and Run C's ledger report | — |
| `grok_probe.py`, `diagnostics/` | the paid Grok diagnosis probes and their results | — |
| `RESULTS.md` | scored results, timing, spend, Grok diagnosis | — |

## Commands

The Anthropic SDK is not a project dependency; each command loads a pinned copy on top of the locked environment.

```sh
U="uv run --locked --with anthropic==2.4.0 python experiments/fresh_15_v1/run_experiment.py"
$U preflight                       # zero model calls
$U preflight --arm sonnet --count-tokens   # plus free Anthropic token counting of the translated requests
$U live --write experiments/fresh_15_v1/runs/A_sonnet_v1 --run --max-cost 4.5                  # Run A (PAID)
$U ledger experiments/fresh_15_v1/runs/A_sonnet_v1
$U branch --source experiments/fresh_15_v1/runs/A_sonnet_v1 \
          --write experiments/fresh_15_v1/runs/B_grok_v1 --run --max-cost 4.5                  # Run B (PAID)
$U ledger experiments/fresh_15_v1/runs/B_grok_v1
$U resume <run dir> --reason "..."                                                             # only if interrupted
```

Never use `scripts/run_threadsense_full.py resume` on these runs: it would apply the default OpenAI configuration (it
refuses, because the saved configuration differs).

## How requests are delivered

The pipeline's fingerprinted transports only speak OpenAI-format chat requests on an `openai/` or `openrouter/` route.
The experiment keeps the pipeline on its `openrouter/...` route label and intercepts every request at the transport
(`delivery.py`):

- **Sonnet:** translated to the native Messages API and sent with the official SDK (`anthropic==2.4.0`) on the `ant`
  profile. System messages → `system`; strict `json_schema` → native structured outputs; `json_object` dropped (no native
  equivalent; the prompt asks for JSON and the pipeline validates locally, as before); `temperature` dropped (Sonnet 5.5
  rejects non-default sampling). Thinking: Agent 3 adaptive at effort `medium`; Agents 1–2 off (`between_tools`).
  The response is converted back to the chat format the pipeline parses; the stored raw response stays native.
- **Grok:** the same OpenAI-format body to api.x.ai with `reasoning_effort: medium` for Agent 3 and without `stop`
  (unsupported by xAI reasoning models).

The OpenRouter key slot holds a placeholder the pipeline requires; it is never sent.

## Safeguards

- **Existing guard on every delivered request:** exact body stored, maximum cost reserved against `--max-cost` before
  sending (input estimate ×1.6 for tokenizer differences, full output cap), one send, raw response stored before parsing,
  cost settled from the provider's usage (xAI: its reported cost when present, otherwise output including reasoning
  tokens, which can only overstate).
- **Route allowlist:** only api.anthropic.com and api.x.ai; only the arm's model may send (Run A `claude-sonnet-5-5`,
  Run B `grok-4.7`); direct use of openrouter.ai, api.openai.com, api.anthropic.com or api.x.ai outside the delivery
  path is refused on both transports. A refused request is stopped before it is reserved or sent.
- **No retries, no fallback models** (SDK `max_retries=0`; unchanged elsewhere).
- **Disabled for this experiment:** reviewer-feedback snapshots, review lessons, historical parent caches (Run A has
  none; Run B reads Run A only), ReAct research and flag impact.

## Adapter limitations

1. Channel IDs gain a `C_` prefix (`C91AUDIO01` → `C_91AUDIO01`): every loader selects `channels/C_*.json`.
2. Knowledge dates become midnight UTC timestamps.
3. **Archive applicability** has no structured field. K03 (v1.4) and K04 (v2.0) share one document identity; from
   2026-10-14 K04 is current and K03 is a superseded revision, withheld from current-mode retrieval (available in
   history mode). The archive rule still reaches Agent 3 through K04's own text and T15.
4. The fixture gives no approver for its documents; they are recorded as approved by `fixture` (role TEAM_LEAD).
5. Agent 2 hard-codes `OPENAI_API_KEY` for a model override, and its consolidation judge defaults to that key. Both files
   are fingerprinted, so the runner routes around it at runtime (recorded in each run's manifest).
6. Sonnet runs without `temperature` (not pinned at 0); Agent 3's JSON output on Sonnet relies on the prompt and local
   validation instead of a JSON mode. Grok keeps temperature 0 and JSON mode.
7. Reasoning differs by design only in provider controls: both Agent 3 models run at medium effort.
