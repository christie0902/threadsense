# Fresh-15 model comparison: results (developer-scored)

Fixture `threadsense_fresh_15_v1` (15 Slack roots, 6 knowledge documents, cutoff 2026-10-17T00:00:00Z), run on
2026-11-16 on branch `model-comparison-experiments` (base `fd4e53c`). The answer key was opened only after every run
below had saved its outputs. One run per setup: these are observed results on one small, designed synthetic
fixture, not estimates of general model quality.

## Runs

| Run | Directory (`experiments/fresh_15_v1/runs/`) | Models | Result |
| --- | --- | --- | --- |
| A | `A_sonnet_v1` | Claude Sonnet 5.5 at every stage | Complete after 2 resumes. Its Agent 3 output is **invalid** (harness defect: Agent 3's user directory pointed at the demo fixture, so every card failed grounding on "unknown person"). Upstream stages valid. |
| A2 | `A2_sonnet_agent3_v1` | Sonnet 5.5, Agent 3 only, on Run A's saved handoff | Complete; the valid Sonnet Agent 3 result |
| B | `B_grok_v1` | Grok 4.7 Agent 3 on Run A's handoff (120 s timeout) | Failed: 7/7 requests timed out, no output |
| B2 | `B2_grok_agent3_v1` | Same, 600 s timeout | Failed: 7/7 requests timed out, no output |
| C | `C_gpt_v2` | The repository's original OpenAI plan: gpt-4o-mini-2024-07-18 (Agent 1), gpt-4.1 (verifier), gpt-5.4-2026-03-05 low (Agent 2), gpt-6.1-sol medium (Agent 3) | Complete in one pass |
| (C v1) | `C_gpt_v1` | — | Stopped at the first request: expired OpenAI key (HTTP 401, not billed) |

"Sonnet plan" below = Run A upstream (Agents 1–2) + Run A2 (Agent 3) on that exact handoff. "GPT plan" = Run C.

## Scenario scores (developer-scored against the answer key)

| Case (threads) | Sonnet plan | GPT plan |
| --- | --- | --- |
| Seek freezes (T01–T03) | **Pass.** One card T01–T03: `ESCALATE_ENGINEERING`, scoped to AUD-741/754/768, cause stated as unconfirmed. Cites PILOT-K01, T01#0–2, T02#0–1, T03#0–1. HIGH, held in review (grounding judged 3 statements partially supported; they were withheld). | **Partial.** T01–T02 card passes (`ESCALATE_ENGINEERING`, scoped, cause unconfirmed; PILOT-K01/K02, T01#0–2, T02#0–1; grounding passed; HIGH, in review). Agent 2 split T03 into its own topic, which got a second engineering card (PILOT-K01, T03#0–1; grounding failed → review). That makes two referrals for one defect against K01's "one scoped incident". Not a listed failure. |
| Silent media (T04–T05) | **Pass.** Agent 2 split T04 and T05 (separate action scopes, as the key requires). T04: no action needed (QA answered with the flag). T05: ask for the task ID and a local playback check before a disposition. Both in review (inherited Agent 1 flags). PILOT-K01/K02, T04#0–1, T05#0–1. | **Pass.** Same split. T04: no action needed (in review). T05: ask for the task ID and a local playback check; scope says the disposition is not confirmed. Shown as a recommended action. Same citations. |
| Versioned reviewer notes (T06–T08) | **Partial.** One card T06–T08 states the current/archive rule correctly (PILOT-K03/K04, T15, T06–T08 messages). The recommendation was withheld because the judge found the need for action only partly supported, so the card sits in review with no clarification to send. No misapplied rule. | **Pass.** T06–T07: a conditional reminder that does not decide either task's rule before the batch is confirmed (PILOT-K03/K04, T15, T06#0–1, T07#0–1). T08 split off as an Observation: the archive keeps the old format (PILOT-K03/K04, T15, T08#0–1). Defensible finer split. |
| Equivalent formatting (T09–T10) | **Pass.** One card, no action needed (Tie already answered in both threads). PILOT-K05, T09#0–1, T10#0–1. In review (inherited T09 flag; 2 partially supported statements withheld). | **Partial.** Agent 2 split T09 and T10. T09: no action needed (PILOT-K05, T09#0–1; in review, inherited flag). T10: the grounding request failed with an OpenAI HTTP 520 (no retry by design), so the summary was withheld and the card routed to review. A recorded provider failure, not a wrong answer. |
| Archived activity count (T11–T12) | **Pass.** No intervention proposed; the evidence gap is explicit; routed to review. Cites PILOT-K05 (retrieved, not used to assert a counter rule). | **Pass.** Same disposition and citation; the unsupported no-action reason was withheld. |
| Export character differences (T13–T14) | **Pass.** Observation: the lead has already requested the checks, cause kept open. PILOT-K06, T13#0–1, T14#0–1. No product-wide claim, no claim that a comparison happened. | **Pass.** Same disposition and citations. |
| **Total** | **5 pass, 1 partial, 0 fail** | **4 pass, 2 partial, 0 fail** |

Both plans scored on the same measures:

| Measure | Sonnet plan | GPT plan |
| --- | --- | --- |
| Required review misses | 0 | 0 |
| Unsupported claims shown on cards | 0 found | 0 found |
| Overly broad actions | 0 | 0 |
| Cards the system marked HIGH | 1 | 1 |
| HIGH cards still in review | 1 | 1 |

Minor wording notes (Sonnet), not counted as unsupported claims:
- The T06–T08 summary says "two tutors ask" on a three-thread card. That card is in review anyway.
- The T13–T14 summary says the lead asked "each tutor for the original file and viewer details". That's exact for T13 and loose for T14, where the lead asked for a UTF-8 editor check.

## Agent 1: resolution against the key

| Thread | Key | Sonnet | GPT |
| --- | --- | --- | --- |
| T01–T03, T05–T07, T11–T13 | UNRESOLVED | UNRESOLVED (all) | UNRESOLVED (all) |
| T02 | UNRESOLVED | UNRESOLVED | **PARTIALLY_RESOLVED** (flagged for review) |
| T04, T08, T09, T10 | RESOLVED_IN_THREAD | RESOLVED_IN_THREAD (all) | RESOLVED_IN_THREAD (all) |
| T14 | PARTIALLY_RESOLVED | UNRESOLVED | UNRESOLVED |

- **Exact agreement:** Sonnet 13/14, GPT 12/14. Excluding T14: Sonnet 13/13, GPT 12/13.
- **T14 qualitative alternative** (UNRESOLVED is acceptable if the useful lead instruction is preserved and the cause is kept open):
  - Sonnet **meets it**: "The only reply gives diagnostic steps and asks for a follow-up report on whether the downloaded text still differs ... the issue remains open".
  - GPT **does not**: "requests further diagnostics but does not provide a substantive answer". The cause stays open, but the instruction isn't preserved.
- **Authority messages:** both credited exactly T04#1, T08#1, T09#1 and T10#1, and nothing else.
- **Verification:** Sonnet 7 verified / 1 corrected / 6 needs review. GPT 6 / 5 / 3.
- **Review obligations:** all needs-review items reached the cards as inherited flags (Sonnet 6, GPT 3).

## Upstream differences vs Agent 3 differences

The two plans have different Agent 1/2 outputs, so their Agent 3 cards do not rest on the same handoff.

- **Upstream:**
  - Agent 2 grouping: Sonnet formed 7 topics, matching the design except the T04/T05 split. GPT formed 10 topics, additionally splitting T03, T08 and T10.
  - Agent 1 resolution: 13/14 vs 12/14.
  - Both GPT partials trace to its Agent 2 splits (T03, T10), plus one provider error (T10).
- **Agent 3, on topics with identical membership** (T04, T05, T11–T12, T13–T14): the two models gave the same dispositions with the same citations. GPT's T05 action is shown rather than held because GPT's Agent 1 verified T05 (an upstream difference).
- **The one Agent 3 difference on comparable scope:** versioned notes. Sonnet withheld its recommendation (T06–T08 together); GPT produced a correct conditional reminder (T06–T07, with T08 split off).
- **Not isolated:** an Agent 3-only GPT run on Run A's handoff (like A2) would separate the two cleanly. It was not run.

## Accounting

Both plans:
- **Ingestion:** 15 roots = 14 discussion + 1 announcement. T15 was extracted through the announcement path and cited as "T15 (announcement)" on the notes cards, never as a discussion topic.
- **Threads:** all 14 discussion threads appear on cards. 0 Agent 1 rejections, 0 processing-history exclusions, 0 unassigned.
- **Citations:** every cited source resolves in the dashboard (A2 36/36, C 34/34).
- **Usable briefing:** yes for both, loaded through the real dashboard API.

| | Sonnet plan | GPT plan |
| --- | --- | --- |
| Cards (line) | 7 (6 needs review, 1 Observation) | 10 (6 needs review, 2 recommended action, 2 Observation) |
| Review queue (inherited Agent 1 items) | 6 | 3 |

## Time (time.perf_counter, seconds)

| Stage | Sonnet | GPT |
| --- | --- | --- |
| Agent 1 interpret | 63.1 | 86.4 |
| Agent 1 verify | 327.5 | 224.0 |
| Grouping (local embeddings) | 15.1 | 13.6 |
| Agent 2 + consolidation | 22.1 (0 candidate sets) | 42.0 (1 judged set) |
| **Agent 3** | **227.3** (A2) | **511.1** |
| Ingestion → usable briefing | **≈ 658** (composite: Run A's successful stages + A2's Agent 3 + check) | **878.6** (one uninterrupted run) |

- **Setup** (run creation, not in the totals): 5.8–6.2 s.
- **Index rebuild:** 9.0 s. Embedding model load: 12.3 s.
- **Sonnet total excludes:** Run A's two failed attempts (0.06 s and 0.004 s, both before any model call), the fix time between attempts, and Run A's invalid Agent 3 (223.7 s).
- **Concurrency:** Run C overlapped with the two Grok diagnostic probes, which only waited on network.

## Spend and tokens

| | Requests | Charged | Input / output tokens | Cap |
| --- | --- | --- | --- | --- |
| Sonnet Agents 1–2 (Run A) | 63 | $0.972 | 192,547 / 58,695 | |
| Sonnet Agent 3 (A2) | 15 | $0.796 | 216,992 / 36,226 | $1.50 |
| **Sonnet plan** | 78 | **$1.768** | | |
| Run A total (incl. invalid Agent 3, $0.784) | 78 | $1.757 | | $4.50 |
| GPT Agents 1–2 (Run C) | 66 (+2 reused within the run) | $0.328 | 114,449 / 27,689 (7,680 cached) | |
| GPT Agent 3 (Run C) | 20 + 1 failed | $0.851 | 175,726 / 41,130 (3,818 reasoning) | |
| **GPT plan** | 86 sent | **$1.179** charged + $0.178 reserved (UNCERTAIN) | | $4.50 |
| Grok B + B2 | 14 | ledger: $1.88 reserved (UNCERTAIN); **xAI console: $1.84 billed** | — | $4.50 / $3.00 |
| Grok diagnostic probes | 3 | $0.27 (xAI-reported) | | |

- **The $0.178 UNCERTAIN reservation in Run C** belongs to the HTTP 520 request. Provider errors are normally not billed, but that's an estimate; the OpenAI dashboard has the actual charge.
- **Prompt caching:** none requested on Sonnet, and none occurred. OpenAI's automatic caching hit 7,680 tokens in Agent 1 interpret.
- **Retries:** none anywhere, by design. Every failure was recorded once.
- **Where requests went** (from the ledgers):
  - Runs A, A2, B, B2: 0 OpenAI or OpenRouter rows (A/A2 api.anthropic.com only; B/B2 api.x.ai plus reused Anthropic rows).
  - Run C: all 89 rows on api.openai.com.

## Grok: technical failure, diagnosed

All 14 Grok Agent 3 requests (B: 120 s timeout; B2: 600 s) returned nothing before the timeout. Free checks ruled out the key (active, unblocked), the model (`grok-4.7` listed) and the setting (`medium` supported).

Two paid probes (`diagnostics/grok_probe_v1`, `diagnostics/grok_probe_v2_keepalive`, script `grok_probe.py`) resent the smallest B2 request:

| Probe | Result | Time | Reasoning tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- | --- |
| Streamed | Valid JSON, `finish_reason: stop`; first content token at 219 s | 238 s | 15,842 | 2,736 | $0.132 |
| Not streamed, with TCP keepalive | Valid JSON | 247 s | 17,246 | 2,512 | $0.139 |

**What the probes show:**
- **Grok works:** about 4 minutes per Agent 3 request at medium effort, with roughly 16–17k reasoning tokens. xAI doesn't count those against `max_tokens`.
- **Why B timed out:** 120 s is shorter than that work.
- **Why B2 timed out:** its non-streamed connections had no keepalive and sat silent for about 4 minutes. With keepalive the same request succeeded, so something on the network path drops idle connections.
- **xAI finished every request:** each probe cost the same as xAI billed per timed-out request (14 × ≈$0.13 = $1.84).
- **Cause:** client timeout plus the network path, not the model's output.

Streamed delivery is implemented (`run_experiment.py agent3 --xai-stream`; Grok's reservation covers reasoning beyond `max_tokens`) but has **not been run**. A Grok Agent 3 run on Run A's handoff would take about an hour (about 4 minutes × 15 requests) and cost roughly $2.

## Commands

```sh
U="uv run --locked --with anthropic==2.4.0 python experiments/fresh_15_v1/run_experiment.py"
$U preflight --arm gpt                                                        # zero calls
$U live --write experiments/fresh_15_v1/runs/A_sonnet_v1 --run --max-cost 4.5             # Run A (paid)
$U agent3 --arm sonnet --source experiments/fresh_15_v1/runs/A_sonnet_v1 \
          --write experiments/fresh_15_v1/runs/A2_sonnet_agent3_v1 --run --max-cost 1.5   # Run A2 (paid)
$U agent3 --arm grok --source experiments/fresh_15_v1/runs/A_sonnet_v1 \
          --write experiments/fresh_15_v1/runs/B2_grok_agent3_v1 --run --max-cost 3.0     # Run B2 (paid, failed)
$U live --arm gpt --write experiments/fresh_15_v1/runs/C_gpt_v2 --run --max-cost 4.5      # Run C (paid)
$U ledger <run dir>
uv run --locked python experiments/fresh_15_v1/summarize_run.py <run dir>    # read-only; never reads the answer key
uv run --locked python experiments/fresh_15_v1/grok_probe.py --run --out <name> [--nonstream-keepalive --skip-tiny]  # paid probe
# Not run: $U agent3 --arm grok --xai-stream --source .../A_sonnet_v1 --write .../B3_grok_agent3_stream_v1 --run --max-cost 2.5
```

## Reports

- Run summaries: `reports/summary_<run>.txt`.
- Run C ledger: `reports/ledger_C_gpt_v2.json`.
- Per-run files: `timing.json`, `usable_briefing.json`, `ledger_summary.json` and `run_manifest.json` in each run directory.
- Grok probes: `diagnostics/`.
