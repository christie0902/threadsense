# ThreadSense mock-data update — placement guide

Prepared October 28, 2026. This package contains revised synthetic sources and a separate demo Slack snapshot. It does not change agent code, install retrieval, or migrate existing processed exports.

## Put the files here

Extract the ZIP into the ThreadSense repository root, keeping its folder structure. If doing this manually, merge these folders:

| Package folder | Repository destination | Contents |
| --- | --- | --- |
| mock_knowledge/instructions/ | mock_knowledge/instructions/ | Four revised project instructions and history/safety_qn_help_page_v1.0.md |
| mock_knowledge/faq/ | mock_knowledge/faq/ | Four revised project FAQs |
| mock_knowledge/decisions/ | mock_knowledge/decisions/ | One newly authored synthetic safety clarification |
| data/fixtures/slack_generated_demo/ | data/fixtures/slack_generated_demo/ | Complete 12-channel + users demo snapshot, with one additional audio announcement |
| docs/threadsense_demo_update/ | docs/threadsense_demo_update/ | This guide, review notes and validation/source manifests; never include this folder in retrieval |

Back up your existing eight instruction/FAQ files before replacing them, especially if you edited them after uploading them. The two additional safety records are newly authored synthetic supplements, not recovered history. Retain any separate historical sources you already created; compare their scope/dates before combining overlapping decisions.

Your latest plan uses mock_knowledge/ as the source layout. Keep severity_rubric.py and domain_lexicon.json in their existing data/knowledge/ location. Do not move them into the retrieval corpus.

## The announcement is already added

No manual JSON editing is needed. The complete new channel file is:

data/fixtures/slack_generated_demo/channels/C_AUDIO_ANNOUNCEMENTS.json

New announcement identity:
- Project: audio_multimodal
- Batch: audio_batch_06
- Channel: C_AUDIO_ANNOUNCEMENTS
- Author: U006 / Priya / TEAM_LEAD
- Exact timestamp: 1790892000.000901
- Time: October 1, 2026, 18:00 America/New_York (22:00 UTC; fractional timestamp retained)
- Replies: none
- Content: handling for unavailable playback, evidence to collect, and no claim of a completed repair

It follows the existing October 1 17:28 status post and precedes later questions, including 1790896012.001900 in C_AUDIO_GENERAL and 1790903186.000110 in C_AUDIO_QA.

The original data/fixtures/slack_generated/ directory is not part of this package and should remain unchanged. Configure the fixture adapter/source loader to read data/fixtures/slack_generated_demo/ for the demo. The loader flag/configuration has not been supplied here, so no unverified command-line option is prescribed.

The demo snapshot has 201 threads and 517 messages: 178 discussion threads and 23 announcement threads. All original 200 threads/516 messages retain their content and metadata. Reusing this complete snapshot does not add the announcement repeatedly.

Refresh announcement extraction and index inputs when those components are configured for this root. Preserve the original release outputs/manifests; do not relabel an old 200-thread export as the new 201-thread snapshot or bypass its integrity checks. The new record does not require interpreting an additional discussion thread. Do not restart Agent 1/2 semantic experiments for this data addition.

## What changed and why

- Audio: the precise waveform/no-play FAQ entry was removed, while its actual handling rule remains in the instructions. The remaining general FAQ supports reporting without fully duplicating the symptom-specific entry.
- RP: the rules distinguish an explicit formatting violation from the unresolved universal comparison of formatting versus factuality.
- Multilingual: acceptable loanwords, valid regional variants and reviewer preferences are not listed as minor errors. Language QA checks context and impact.
- Tool incidents: playback, rendering, fetch and submission failures are separate from task-quality Major/Minor labels.
- Audio clipping: instructions and FAQ consistently distinguish clear brief clipping from continuous/borderline cases requiring evidence.
- Safety: the current instructions/FAQ reference a specific older help page and a dated TL clarification. The help-page copy retains the older text; supersession metadata states which section no longer applies.
- All sources have structured front matter with identity, version, project, authority, effective date and synthetic provenance.

## Fictional-PII source chain

| Source | Effective time (UTC) | Meaning |
| --- | --- | --- |
| safety_qn_help_page_v1.0.md | August 20, 2026, 13:00 | Old blanket initial-QN rule for contact details |
| safety_fictional_pii_clarification_2026-09-10.md | September 10, 2026, 13:00 | Scoped TL-approved exception for verified fictional placeholders |
| safety_classification_instructions.md v1.4 | September 10, 2026, 15:00 | Current instructions reflect the clarification |
| safety_classification_faq.md v1.1 | September 12, 2026, 13:00 | FAQ identifies the exact older help-page copy |

These are synthetic fixture dates, not claims about when files were authored in real life. The package creation date is October 28. No document cites a future announcement relative to its fictional version.

This demonstrates stale documentation and scoped supersession. The authoritative rule is recoverable; ambiguity about a particular task or an unavailable source can still require review. Do not describe this as “current instructions are stale”: the old help-page copy is stale.

## Ingestion boundary

The Markdown header uses mock-knowledge-markdown-v1, an authoring format for these sources. It is NOT a claim that these files already satisfy the repository's knowledge-source-v1 JSON schema or Pydantic contracts.

At the ingestion milestone, normalize these Markdown files into the existing shared source/chunk interface. Preserve IDs, versions, scope, authority, source links and supersession. Map the manual announcement into the decisions collection with document_type=announcement; no separate decision database is needed.

Do not index docs/threadsense_demo_update/, this README, the validation report, source manifest, hidden evaluation files, or expected demo outcomes. The two supplementary safety sources belong in retrieval; the coverage notes do not.

A new Slack announcement should enter knowledge through the announcement extractor. Do not also manufacture a second manual source for the same Slack message.

## What remains open

This package does not manufacture an engineering ticket or a confirmed failed/successful historical intervention. “Recommend escalation” and “already escalated” remain different claims. It also does not manufacture Agent 1/2 review flags. Use the actual handoff and review registries for that demo.

A suggested FAQ entry or re-announcement can still be routed to Needs Review if HIGH severity, inherited flags or other guardrails apply. Correct evidence does not guarantee a specific card line.

The historical documents you have not supplied still need reconciliation before they are combined with these supplements. Exact runtime loading, retrieval and Agent 3 behavior have not been executed.

## Verification performed

See validation_report.json for the actual mechanical checks and source_manifest.json for identities/hashes. Checks cover JSON/YAML parsing, source references, date order, existing-message preservation, announcement timing and corpus counts. They are not a semantic accuracy benchmark or a repository regression run.

## Key takeaway

A policy can be correct, a help-page copy can be stale, and a technical incident can still be unresolved. Keep those states separate. Task-quality Major/Minor labels also do not determine Agent 3 operational severity.
