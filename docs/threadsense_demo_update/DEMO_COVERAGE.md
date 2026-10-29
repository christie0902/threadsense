# Demo coverage notes — evaluation only

Do not index this document or give it to runtime agents.

| Case | Intended evidence behavior | Limit |
| --- | --- | --- |
| FAQ edge case | Retrieve handling from instructions; identify the narrower FAQ coverage gap | General reporting already exists; do not invent a new policy |
| JSON vs prose | Identify the formatting violation and absence of a universal preference ordering | Actual pairs can sometimes be settled without a universal rule |
| Fictional PII | Compare the actual old rule with its scoped, dated supersession | New instructions are current; the old help-page copy is stale |
| Language routing | Preserve locale/context checks and route disputed cases to matching language QA | Valid loanwords/variants are not automatic errors |
| Already announced | Cite the new announcement and later questions | Recurrence does not prove users read or ignored the announcement |
| QA misalignment | Compare actual task evidence with consistent tie/clipping guidance | A single disagreement is not proof of a systemic defect |
| Technical escalation | Recommend evidence capture/escalation when justified | No completed escalation or ticket is fabricated |
| Observation only | Preserve generation-versus-playback uncertainty | Do not force a confirmed model-defect narrative |
| Upstream flags | Consume the actual effective review registry | Flags are not supplied by these source documents |

ToT/card-line expectations depend on the implemented rules and available handoff flags; this package does not hard-code them into source content.
