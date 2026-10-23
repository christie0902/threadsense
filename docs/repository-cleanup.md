# Repository cleanup — 2026-10-22

Cleanup is complete within the inspected scope. Working runtime logic, prompts,
models, dependencies, tests, source data, and Agent 2 behavior were preserved.
No paid calls, model reruns, commits, or pushes were made. Sixteen inaccessible
old test directories were retained rather than deleting material without a
verified recovery copy.

## Removed and consolidated

| Group | Changes and dependency check |
| --- | --- |
| Superseded instructions | Removed `docs/agent1-verification.md`, `docs/agent1-integration-readiness.md`, and `docs/agent1-integration-results.md`. Merged useful workflow, persistence, evidence, historical failure, and downstream details into the current handoff guide. Removed old blocking gates, retry/stage bounds, and instructions to continue v2. |
| Obsolete script | Removed `scripts/generate_slack_fixtures_old.py`. The current generator remains. No import, dynamic loader, test, entry-point, or maintained-document caller referenced the old copy. Historical integrity inventories mention its hash; Git preserves the exact old file. |
| Accidental output | Removed the root file named `hort ` followed by a literal backtick: saved Git warnings/diff statistics, with no caller or evidence role. |
| Temporary setup/test output | Removed 15 inspected pytest cache/temporary directories and `.cache/check_demo_startup.py`, `.cache/crewai-check.in`, `.cache/crewai-resolved.txt`: **14,194 files, 29,740,580 bytes (28.36 MiB)**. Maintained configuration/startup tests cover the old mock startup check; the dependency lockfile is authoritative. |

The repository was clean at the starting commit
`053d3144f735597c0d3976db3e830690dfcc3afc`. Committed deletions and prior versions of
edited documentation remain recoverable from that commit. No preexisting tracked
or untracked user changes were overwritten.

Before deleting ignored temporary material, every archived file was checksum
verified, copied outside the working tree, verified again, and checked against
the unchanged original. Recovery location:

```text
D:\Christie\2026_AgenticAI\threadsense-cleanup-recovery-20261022\
```

It contains one ZIP per removed directory, the three loose setup-check files,
and `manifest.json` with original paths and file hashes. Restore selected entries
to their recorded `.cache` locations if needed. The temporary in-repository
archive staging directory was deleted after external verification.

## Authoritative documentation and entry points

- [README](../README.md): purpose, current architecture, setup/configuration,
  safe run/test commands, troubleshooting, and the complete retained entry-point table.
- [Agent 1 handoff](agent1-nonblocking-handoff.md): current verification contract,
  cache/persistence behavior, both-registry preflight, review binding, historical
  evidence, and the planned Agent 2 connection.
- [Final Agent 1 results](agent1-full-batch-results.md): completed execution,
  all twelve Codex-assisted review outcomes and limitations, final artifact links.
- [Prose benchmark](../experiments/prose_comparison_v1/README.md): retained reviewed
  synthetic cases, evidence isolation, scoring, and actual saved v2 results.
- This cleanup record: scope, recovery, and post-change checks.

The operational entry points remain `run_agent1_demo.py`, `run_agent1_batch.py`,
`run_agent1_verification.py`, `run_thread_grouping.py`, and the existing Agent 2
prepare/sample/batch/repair scripts under `scripts/`. Historical reconciliation,
the prose comparator, dataset generators/validators, and `main.py` fixture
inspection remain available; their purposes and write boundaries are in the README.

## Retained evidence and uncertain candidates

All `data/` files were retained, including Slack, runtime glossary, evaluation
material, frozen interpretations/grouping, Agent 2 assets, all pilots, and both
final v3 directories. The pilot review registry and fixed twelve-record selection
are unchanged. Pilot v1 supports old-schema rejection tests; v5 provides benchmark
sources; v6 provides exact review bindings and interrupted-request evidence;
the live prose experiment supplies real saved-response replay. Older intermediate
outputs also appear in historical preservation inventories, so they were retained.

The small `agent1_verified_pilot_v5.7z` was retained: its complete equivalence to
the expanded evidence has not been established. Earlier local code snapshots may
contain otherwise uncommitted recovery material and were retained. The full-batch
audit helpers under `.cache/agent1_full_batch_20261022/` remain with their original
inputs. Their closed-milestone checks expect the original tree; their historical
hash ledgers were not rewritten to hide later documentation cleanup.

Fourteen source/runner files participate in v3 fingerprints. They were left
byte-identical, including historical audit helpers inside active modules. Runtime
modules with unclear independent callers were retained rather than refactored.
The local `.venv` and package executables remain intact.

Sixteen old pytest directories could not be fully inspected under the available
Windows access permissions, so no deletion or ownership/ACL change was attempted.
Their exact paths are recorded in
`../.cache/repository_cleanup_20261022/cache_cleanup.json` under
`retained_access_denied`. New validation temporary output is also retained.

## Validation results

Full offline suite after code/documentation cleanup:

```powershell
uv run --locked --extra dev python -m pytest -q --disable-warnings --tb=short --basetemp .cache/pytest-cleanup-final -o cache_dir=.cache/repository_cleanup_20261022/pytest-cache
```

**277 passed, 0 failed, 0 skipped; 162 dependency warnings; 87.69 seconds.**
The separate cache directory kept this run independent of old temporary files
being archived. No tests or assertions were removed or changed. Coverage still
includes workaround claims, recording/reference reversal, QN, actual TL reactions,
announcements, real prose validation, nonblocking failures, and review propagation.

All **40 Python syntax checks, 23 package-module imports, and nine read-only CLI
checks passed**. These exercised fixture inspection, Agent 1 inspection/baseline
dry run, grouping input checks, existing Agent 2 sample/batch preflights, verifier
help, historical reconciliation dry run, and benchmark help. Write-only authoring
and preparation scripts were syntax-checked without regenerating artifacts.

Finalized v3 preflight, using the original settings and both review registries:

```powershell
$env:THREADSENSE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
$env:THREADSENSE_VERIFIER_MODEL = 'openai/gpt-4.1'
uv run --locked python scripts/run_agent1_verification.py --dry-run --limit 0 --content-review docs/agent1-pilot-content-review.json --content-review data/processed/agent1_full_batch_review_v3/content_review.json --output-dir data/processed/agent1_verified_v3
```

**Exit 0: 200 compatible records, zero unstarted, zero remaining model tasks;
16 valid reviews, zero invalid.** uv required access to its existing Windows cache
outside the sandbox; no dependencies or saved model settings were changed.

A separate model/network-disabled preservation audit verified:

- **4,769 protected files byte-identical**, including configuration and local
  `.env` (contents never printed), all data, tests, active code, and benchmark inputs.
- All original receipt hashes match; complete final output and review directories
  are unchanged. Fourteen fingerprinted code files retain their exact bytes.
- Exactly 200 unique full identities match the frozen inputs; zero unprocessed.
  The 49-record queue exactly equals flagged canonical records.
- Effective counts remain **81 VERIFIED / 70 CORRECTED / 49 NEEDS_REVIEW**;
  original automated counts remain **82 / 71 / 47**.
- **1,117 lineage/review file and JSON-pointer references resolve**, with candidate,
  source, and applicable review evidence hashes checked.
- Request accounting remains **593 attempts, 593 completed responses, zero unknown
  completion requests** for v3. Historical v6's unknown request remains unchanged.

Machine-readable cleanup receipts and read-only validation code are under
`.cache/repository_cleanup_20261022/`; they contain no copied credentials.
Maintained local documentation links and referenced entry-point paths were checked,
and `git diff --check` passed.

No production defect was introduced or repaired. Documentation previously
described the completed run as pending and omitted the full-batch review registry
from current commands; those instructions are corrected. Agent 2 still needs its
planned canonical-export connection, retaining all 200 records, review flags and
lineage. A successful fresh revision can remain CORRECTED; unresolved disputes
remain effective NEEDS_REVIEW without blocking downstream availability.
