# Briefing eligibility audit (briefing-routing-v1)

Source: `data/experiments/threadsense_full_v1/stages/agent3/overnight_run` (immutable). Zero model calls. Relevance labels: `data/evaluation/briefing_relevance_labels_v2.json` (developer audit, not confirmed by a team lead).

Audited, input-bound relevance labels (developer audit, not confirmed by a team lead); no automatic relevance classification. Unlabelled cards, or cards whose saved messages changed, stay in the brief.

Before: {'OBSERVATION': 12, 'NEEDS_REVIEW': 61, 'RECOMMENDED_ACTION': 8}. After: {'NEEDS_REVIEW': 66, 'OBSERVATION': 7, 'RECOMMENDED_ACTION': 8}. In the brief: 77 {'NEEDS_REVIEW': 66, 'RECOMMENDED_ACTION': 8, 'OBSERVATION': 3}; history {'HISTORY_ROUTINE': 2, 'EXCLUDED_SOCIAL': 2}.

| Topic | Before | Next step | Relevance | Outstanding | Saved judgment | After | Brief |
|---|---|---|---|---|---|---|---|
| Audio-transcript mismatch clarification | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | Still open (no action needed now) | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Conflicting QN guidance sources | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Pending follow-up | UPDATE_DOCUMENTATION: action REJECTED_ACTION_TARGET_SECTION_NOT_CITED, action:need SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Japanese honorific consistency review | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Pending follow-up | ROUTE_TO_LANGUAGE_SPECIALIST: action NO_INTERVENTION_NEED, action:need PARTIALLY_SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Japanese register consistency and honorific use | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Major error classification for incorrect year | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Misattributed DOI citations | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | No-action choice needs review | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Overlapping or background speech affecting transcription | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Prompt-injection claims vs actual output content | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| QN rule version reconciliation | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Pending follow-up | UPDATE_DOCUMENTATION: action REJECTED_ACTION_TARGET_WRONG_TYPE, action:need SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Rubric version conflict | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Unfindable or non-existent references | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Citation support verification | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Korean language QA edge cases | OBSERVATION | RECOMMENDATION_WITHHELD | PROJECT | Pending follow-up | ROUTE_TO_LANGUAGE_SPECIALIST: action NO_INTERVENTION_NEED, action:need PARTIALLY_SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Language-day greetings | OBSERVATION | NO_ACTION_NEEDED | SOCIAL_ONLY | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | EXCLUDED_SOCIAL |
| QA threshold consistency across review teams | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Queue coverage and closure reminders | OBSERVATION | NO_ACTION_NEEDED | ROUTINE_NOTICE | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Regional vocabulary fit for target audience | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Repeated ending phrase in generated answer | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Pending follow-up | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Social greetings and well-wishes | OBSERVATION | NO_ACTION_NEEDED | SOCIAL_ONLY | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | EXCLUDED_SOCIAL |
| Team avatar asset location | OBSERVATION | NO_ACTION_NEEDED | ROUTINE_ADMIN | Still open (no action needed now) | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | HISTORY_ROUTINE |
| Tie threshold for near-identical responses | OBSERVATION | NO_ACTION_NEEDED | ROUTINE_NO_FINDING | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | HISTORY_ROUTINE |
| Classify observable content over unsupported override claims | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Consistent threshold for comparable borderline cases | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Public business addresses as contact data | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Suggestive vs explicit content boundary | OBSERVATION | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Work environment and background noise | OBSERVATION | NO_ACTION_NEEDED | MIXED | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |

55 cards with a supported recommended action are unchanged and not listed.

## Relevance decisions

- **Language-day greetings** (SOCIAL_ONLY -> EXCLUDED_SOCIAL, resolution UNKNOWN): Greetings only ("Happy language-day Friday"); no project content.
- **Queue coverage and closure reminders** (ROUTINE_NOTICE -> IN_BRIEFING, resolution UNKNOWN): Two time-bound notices: a same-day queue closure reminder and next-day shift coverage. Each is checked against the briefing cutoff; a notice still current at the cutoff keeps the card in the brief.
  Evidence (SUPPORTED statements): claim:c1, claim:c2, claim:c4.
  Notice member_809df2faae873ed0419f1574 "Queue closes at 6 PM today": latest end 2026-10-02T12:30:00Z.
  Notice member_211e8a1284a7577600ae8ad4 "Early preference queue shift coverage tomorrow": latest end 2026-10-04T01:00:00Z.
  Kept in the brief because: a notice is still current at the briefing cutoff (member_809df2faae873ed0419f1574: latest end 2026-10-02T12:30:00Z); a notice is still current at the briefing cutoff (member_211e8a1284a7577600ae8ad4: latest end 2026-10-04T01:00:00Z).
- **Social greetings and well-wishes** (SOCIAL_ONLY -> EXCLUDED_SOCIAL, resolution UNKNOWN): Well-wishes and a remark that the chat is quiet; no project content.
- **Suggestive vs explicit content boundary** (PROJECT -> IN_BRIEFING, resolution RESOLVED_IN_THREAD): Kept: answered for this task only, while the retrieved instructions state no romance-versus-explicit boundary (claim c5, detail d2). A guidance gap in safety classification that can recur has continuing briefing value; no action is generated for it.
  Evidence (SUPPORTED statements): claim:c5, detail:d2, resolution:member_a070a26269217b5a5e4dbfe0, action:no_action.
- **Team avatar asset location** (ROUTINE_ADMIN -> HISTORY_ROUTINE, resolution PARTIALLY_RESOLVED): Administrative question about where the team avatar image is saved; no annotation work, model behavior, tooling or working-condition finding. The thread is only partly answered: it goes to history with its PARTIALLY_RESOLVED status and open step kept, not resolved.
  Evidence (SUPPORTED statements): claim:c3, action:no_action, severity:rationale.
- **Tie threshold for near-identical responses** (ROUTINE_NO_FINDING -> HISTORY_ROUTINE, resolution RESOLVED_IN_THREAD): History: both pair-specific tie questions were answered in their threads, consistent with current instructions and FAQ (claims c6, c7), with no remaining request. The open tie-consistency issue stays in the brief on its own card (QA inconsistency on tie judgments).
  Evidence (SUPPORTED statements): resolution:member_4ae1700632c4a55ae1a24a4d, resolution:member_cbc21f1a0a95a7a98a8daec4, claim:c6, claim:c7, action:no_action.
- **Work environment and background noise** (MIXED -> IN_BRIEFING, resolution UNKNOWN): Friendly exchange that also reports a working-condition finding (background noise makes clip review harder).

