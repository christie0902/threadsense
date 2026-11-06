# Briefing eligibility audit (briefing-routing-v1)

Source: `data/experiments/threadsense_full_v1/stages/agent3/overnight_run` (immutable). Zero model calls. Relevance labels: `data/evaluation/briefing_relevance_labels_v1.json` (developer audit, not confirmed by a team lead).

Before: {'OBSERVATION': 12, 'NEEDS_REVIEW': 61, 'RECOMMENDED_ACTION': 8}. After: {'NEEDS_REVIEW': 66, 'OBSERVATION': 7, 'RECOMMENDED_ACTION': 8}. In the brief: 79 {'NEEDS_REVIEW': 66, 'OBSERVATION': 5, 'RECOMMENDED_ACTION': 8}; history {'EXCLUDED_SOCIAL': 2}.

| Topic | Before | Next step | Relevance | Outstanding | Saved judgment | After | Brief |
|---|---|---|---|---|---|---|---|
| Audio-transcript mismatch clarification | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | Open thread being monitored | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Conflicting QN guidance sources | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Waiting on a requested step | UPDATE_DOCUMENTATION: action REJECTED_ACTION_TARGET_SECTION_NOT_CITED, action:need SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Japanese honorific consistency review | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Question still open in the thread | ROUTE_TO_LANGUAGE_SPECIALIST: action NO_INTERVENTION_NEED, action:need PARTIALLY_SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Japanese register consistency and honorific use | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Major error classification for incorrect year | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Misattributed DOI citations | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | No-action choice needs review | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Overlapping or background speech affecting transcription | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Prompt-injection claims vs actual output content | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| QN rule version reconciliation | NEEDS_REVIEW | RECOMMENDATION_WITHHELD | PROJECT | Question still open in the thread | UPDATE_DOCUMENTATION: action REJECTED_ACTION_TARGET_WRONG_TYPE, action:need SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Rubric version conflict | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Unfindable or non-existent references | NEEDS_REVIEW | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Citation support verification | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Korean language QA edge cases | OBSERVATION | RECOMMENDATION_WITHHELD | PROJECT | Waiting on a requested step | ROUTE_TO_LANGUAGE_SPECIALIST: action NO_INTERVENTION_NEED, action:need PARTIALLY_SUPPORTED, action:rationale SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Language-day greetings | OBSERVATION | NO_ACTION_NEEDED | SOCIAL_ONLY | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | EXCLUDED_SOCIAL |
| QA threshold consistency across review teams | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action PARTIALLY_SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Regional vocabulary fit for target audience | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Waiting on a requested step | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Repeated ending phrase in generated answer | OBSERVATION | NO_INTERVENTION_PROPOSED | PROJECT | Question still open in the thread | NO_ACTION: action:no_action UNSUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Social greetings and well-wishes | OBSERVATION | NO_ACTION_NEEDED | SOCIAL_ONLY | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | EXCLUDED_SOCIAL |
| Team avatar asset location | OBSERVATION | NO_ACTION_NEEDED | ROUTINE_NO_FINDING | Open thread being monitored | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Classify observable content over unsupported override claims | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Consistent threshold for comparable borderline cases | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Public business addresses as contact data | NEEDS_REVIEW | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | NEEDS_REVIEW | IN_BRIEFING |
| Queue coverage and closure reminders | OBSERVATION | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Suggestive vs explicit content boundary | OBSERVATION | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Tie threshold for near-identical responses | OBSERVATION | NO_ACTION_NEEDED | PROJECT | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |
| Work environment and background noise | OBSERVATION | NO_ACTION_NEEDED | MIXED | - | NO_ACTION: action:no_action SUPPORTED | OBSERVATION | IN_BRIEFING |

55 cards with a supported recommended action are unchanged and not listed.

