# Agent 2 source-folder cleanup — 2026-10-28

The active `src/threadsense/agents` folder no longer contains numbered topic
contracts or consolidation engines. Start with `topic_contracts.py` for the
current taxonomy schema, `topic_taxonomy.py` for its implementation and
`topic_consolidation.py` for the stable public entry point/version dispatch.

## What was removed and what was retained

- Moved eleven historical modules to `src/threadsense/legacy/agent2/`: four
  contract files (v2/v3/v4/v5), four consolidation files (v2/v3/v4/v6),
  `topic_evidence.py`, `operational_severity.py`, and `topic_comparison.py`.
- Extracted the historical v6 schema classes from the mixed current contract
  into `legacy/agent2/topic_contracts_v6.py`. The current contract now contains
  only its two taxonomy models and their strict base class.
- Kept the frozen v7 exporter in `legacy/topic_taxonomy_v7.py`. All older numbered
  contracts still have real replay/regression callers; deleting all but one would
  break historical evidence validation. The existing v6 implementation handles
  explicit v5 replay, so there is no redundant consolidation v5 file to retain.
- Deleted `agents/topic_review.py` and `agents/review_decisions.py`. Neither had
  a caller, CLI integration or test reference; both belonged to the retired v1
  topic-analysis workflow. Their source remains recoverable from Git. The current
  `topic_effective.py` review loader, mandatory registries and all review artifacts
  remain intact. Agent 1's shared contracts were left untouched.

Shared candidate identity/hash checks moved unchanged from the old v6 engine to
`topic_inputs.py`; both current and historical consumers call that function.
Historical schema construction in `topic_requests.py` is now lazy. Importing the
current pipeline/analyst and constructing its provider schema loads none of the
historical semantic engines. No prompts, rules, schema fields, model parameters or
validation thresholds changed.

Repository imports, CLI compatibility callers and producer fingerprint paths
were updated. External code importing `threadsense.agents.topic_*_vN` must switch
to `threadsense.legacy.agent2.topic_*_vN`. The public
`threadsense.agents.topic_consolidation` API keeps its version arguments.
Existing frozen fingerprints are not rewritten or bypassed: a future live run
requires preparation against the current code. Historical offline replay remains
supported. No paid calls or embeddings are part of this cleanup.

## Verification

Before editing, requests and exports for all **81 prospective groups** were
fingerprinted. After cleanup, all request contents, pending exports and synthetic
assigned-member exports match exactly. The current taxonomy prompt, taxonomy
schema, historical v6 schema and provider schemas also match their pre-cleanup
snapshots. These structural checks do not assert semantic accuracy.

Seven focused layout/import regressions check lazy historical imports, explicit
v2-v6 dispatch, absence of numbered files in the active folder and existence of
every fingerprinted producer path. Existing tests retain their assertions and use
the explicit historical import paths. The full-suite receipt is reported with
the delivery; historical results and fixtures are preserved.

Final validation: **614 passed, 0 failed, 0 errors, 0 skipped** in 308.02 seconds
(5:08), in one complete offline pytest invocation. The 162 remaining warnings are
CrewAI deprecations. The separate focused import/layout run was **7 passed**;
these totals are not added together. No paid calls were made.

The exact command, log, JUnit XML, complete diff and before/after file hashes are
under `.cache/agent2-code-cleanup/full-offline-cleanup-20261028T120324Z/`. The
repository was unchanged during the full run. Afterward, one surplus EOF blank
line was removed from `topic_inputs.py` with identical Python AST, this report
was completed, and orphaned ignored bytecode was removed. That formatting-only
source delta is recorded in `post-test-formatting.json`; no semantic changes
followed the full run. `git diff --check` and Python compilation passed.
