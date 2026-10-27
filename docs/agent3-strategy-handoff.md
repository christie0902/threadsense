# Agent 3 strategy discussion handoff

Agent 2 taxonomy v7 is complete with nonblocking review. This prepares the next
design discussion; it does not implement Agent 3 or authorize model calls.

Use `data/processed/agent2_taxonomy_final_v7/release_manifest.json` and
`effective_output_reviewed.json`, or `load_effective_output()` on that directory.
There are **90 groups, 97 topics, 200 unique canonical identities and 516 source
messages**, with **49 inherited Agent 1 obligations plus three naming cautions**
across 41 effective review groups. All members are assigned. No failed/rejected
members occurred, but future consumers must support and retain them.

Contract `agent2-taxonomy-handoff-v1` contains topics/member IDs, full canonical
member/source records, dispositions, rejected/unassigned IDs, effective obligations,
review evidence and grouping provenance. Processing is nonblocking. Automated
`consolidations.json` and per-group evidence are immutable; registered reviews add
an effective view with exact hash bindings. See the
[guide](agent2-offline-integration.md) and [report](agent2-taxonomy-refactor.md).

Agent 2 did not reverify answers, policy, source quotations or canonical summaries.
Names/rationales are navigation metadata. The minor-mention QN title is not a
general Quarantine rule; two audio naming cautions do not establish language or
failure location for every member. Existing disputes and canonical terminology
errors remain visible. Approved glossary: QN means Quarantine.

All topic severities are deterministic UNKNOWN/UNASSESSED because canonical inputs
lack approved structured impact signals. Research may revise severity with explicit
evidence. Flags alone must not imply MEDIUM, and task-labeling major/minor is
separate from operational impact. HIGH should create a nonblocking obligation;
LOW/N/A must not clear inherited obligations.

Decide these points before implementation:

1. **Research unit:** topics are an index. Preserve different member questions and
   conditions; do not collapse them into one answer. Decide how to relate similar
   topics across groups/projects without losing their identities.
2. **Evidence and authority:** define approved sources, access, recency/version
   handling and requirements for policy/answer reassessment. Original Slack and
   Agent 1 lineage are available; no RAG or connector was added here.
3. **Disputes:** carry each inherited and naming obligation independently. New
   research needs exact source/candidate/output bindings. Grouping success,
   recurrence or a broad summary cannot erase a member's disputed claim.
4. **Strategy and severity:** define evidence-supported operational impact,
   actionability and recommendations, with UNKNOWN when unsupported. Keep Slack
   resolution separate from interpretation/research reliability.
5. **Briefing and budget:** retain Needs Review items even without an ordinary
   recommendation, including announcements, social material and future failed or
   rejected members. Agree an offline contract, bounded request budget and fresh
   validation selection before any live Agent 3 execution.

Limits: no raw-Slack semantic review was reopened; no accuracy percentage is
claimed; naming granularity remains subjective. The live v7 run had no failures
or outliers. Existing 294 Agent 2 checks pass, while historical full-suite Windows
atomic-replacement and cross-drive failures remain documented. No Agent 1 rewrite
is part of this handoff.
