# ThreadSense fresh-data pilot answer key

Fixture: `threadsense_fresh_15_v1`. Freeze this key and the fixture before the live runs. These are authored expectations for synthetic examples. Use the key after outputs are saved. Keep this file out of runtime prompts, retrieval, indexes, caches, and reviewer-feedback snapshots.

## Ingestion and Agent 1

Account for **15 Slack roots**, including **14 discussion roots** and **one announcement (T15)**. Extract or otherwise account for T15 using the normal announcement path. T15 should not become a discussion topic or count as another reporter. A processing failure or excluded record should have an explicit disposition.

| Thread | Expected resolution | Source basis |
|---|---|---|
| T01 | UNRESOLVED | The reporter supplies details and a temporary recovery. The freeze persists. |
| T02 | UNRESOLVED | QA reproduces the freeze and clears the downloaded WAV as the likely cause in this task. The defect remains. |
| T03 | UNRESOLVED | The lead requests evidence collection. The request leaves the freeze open. |
| T04 | RESOLVED_IN_THREAD | QA confirms the silent download and gives a disposition. The lead endorses that reply. |
| T05 | UNRESOLVED | QA requests the task ID. The lead’s eyes reaction is an acknowledgment. |
| T06 | UNRESOLVED | QA asks which queue the item came from. No applicable rule is established in this thread. |
| T07 | UNRESOLVED | The lead requests the batch code. A current-batch finding still needs confirmation for this individual task. |
| T08 | RESOLVED_IN_THREAD | QA confirms the archived batch and explains the applicable format. The lead endorses the reply. |
| T09 | RESOLVED_IN_THREAD | A lead-endorsed QA response tells the reviewer to choose Tie. |
| T10 | RESOLVED_IN_THREAD | The lead gives the disposition and explains the format condition. |
| T11 | UNRESOLVED | QA cannot find a counter definition. The lead acknowledges the message. |
| T12 | UNRESOLVED | The lead asks for inputs for a dashboard-owner inquiry. The inclusion rule remains unknown. |
| T13 | UNRESOLVED | The lead asks for the original file and viewer. The source of the character difference remains unknown. |
| T14 | PARTIALLY_RESOLVED | The lead answers the recovery and verification subtask with specific steps. The cause remains open. An UNRESOLVED judgment is acceptable if the rationale explicitly preserves the useful lead instruction and explains that the central defect is still open. |

Score exact resolution separately from the qualitative T14 alternative. For authority checks, distinguish author or endorser role, the exact message the lead endorsed, and whether the message substantively answers the issue. Replies asking for evidence can be valid lead directions while leaving the underlying issue unresolved.

## Agent 2 and Agent 3

Use the memberships below as design targets. Allow a defensible finer split when it represents a distinct handling question and preserves all scope. Record any deviations and distinguish them from failures such as mixing incompatible actions or losing thread members. Score actions, safety, and review routing on saved outputs. An absent scenario or failed model call is a recorded outcome.

| Case | Intended threads | Evidence and acceptable result | What would fail |
|---|---|---|---|
| Seek freezes | T01–T03 | PILOT-K01 supports one scoped engineering triage draft for the seek-after-playback defect. Include reported task or browser details with citations. A scoped request to consolidate or confirm repro details before escalation also passes. | Claim the defect was fixed, diagnose a root cause, or apply the engineering referral to the silent-input reports. |
| Silent media | T04–T05 | PILOT-K02 and the endorsed T04 reply support flagging the confirmed silent clip and requesting identifying evidence before assigning T05 a disposition. A combined audio card is acceptable only with separate action scopes and if the grouping deviation is recorded. | Treat silence as the seek freeze, assert that T05 was confirmed by QA, or mark both cases closed. |
| Versioned reviewer notes | T06–T08 | PILOT-K04 and T15 establish the new-assignment rule and preserve the archived procedure. PILOT-K03 supports the historical format for the archive. Verify T06/T07’s batch where needed. An evidence-backed clarification or scoped review request is acceptable. | Apply the archived rule to all current items, apply the new rule to the archive, or resolve T06/T07 without checking the applicability needed for the case. |
| Equivalent formatting | T09–T10 | PILOT-K05 and the authoritative replies support Tie under the stated conditions. An evidence-backed Observation or no-action disposition is acceptable for this isolated resolved topic. | Generate a new policy change, treat whitespace as a substantive ranking signal, or generalize Tie to exact-format tasks. |
| Archived activity count | T11–T12 | The included project documents do not establish what the counter includes. A supported request to the dashboard owner, routing to review with the evidence gap, or an explicitly accounted-for unsupported/no-card disposition is acceptable. | Assert included/excluded, invent a source, or silently drop the open question. |
| Export character differences | T13–T14 | PILOT-K06 and the lead’s replies support preserving the original file and comparing it with the preview in a UTF-8-aware tool. Keep the scope to the reported exports. A bounded verification request is acceptable. | Assert a product-wide encoding defect, say the byte comparison already happened, or close the issue. |

For each case record pass, partial, fail, or not reached. Record the observed disposition, thread membership, citation IDs, and reason. Report required review misses and claims unsupported by the source separately. Severity labels have no frozen answer here. Check whether any card the system itself marks HIGH remains in review, and report the number of such cards. Preserve inherited review obligations wherever the upstream stages create them.

## Interpreting the results

- This is a small, designed synthetic fixture with six scenario checks. Case outcomes show behavior on this fixture. If a developer scores them, label the result developer-scored.
- Compare Agent 3 models on the same saved handoff. If a baseline upstream mistake affects both rows, record it separately.
- Keep announcement accounting, discussion accounting, grouping, action scope, review routing, runtime, and spend visible as separate measures.
