# Required historical Agent 2 compatibility

These modules are kept because saved responses and offline regression/replay
tools still use their exact contracts. They are not alternate current producers.
Deleting all but one version would remove support for existing evidence.

| Saved response | Contract | Parser/export |
| --- | --- | --- |
| v2 | `topic_contracts_v2.py` | `topic_consolidation_v2.py`; `scripts/replay_agent2_responses.py` |
| v3 | `topic_contracts_v3.py` | `topic_consolidation_v3.py` |
| v4 | `topic_contracts_v4.py` | `topic_consolidation_v4.py` |
| v5 | `topic_contracts_v5.py` | Explicit v5 dispatch in `topic_consolidation_v6.py` |
| v6 | `topic_contracts_v6.py` | `topic_consolidation_v6.py` |

`topic_evidence.py` and `operational_severity.py` support these historical
contracts. `topic_comparison.py` retains the old experiment controller and still
rejects execution under the current taxonomy configuration. Its CLI path is
unchanged. The current taxonomy implementation never imports these engines.

Imports previously under `threadsense.agents.topic_*_vN` now use
`threadsense.legacy.agent2.topic_*_vN`. Repository callers and tests have been
updated. The public `threadsense.agents.topic_consolidation` entry point retains
its explicit `response_schema_version` and `export_adapter_version` dispatch.
The independent frozen-v7 exporter is in `../topic_taxonomy_v7.py`.

This relocation does not change prompts, schemas, model settings, source data or
saved results. Current code fingerprints change because file paths and imports
change: existing frozen fingerprints are never rewritten or bypassed. Prepare a
fresh selection before a future live run; offline historical replay remains
available. No model calls are part of this cleanup.
