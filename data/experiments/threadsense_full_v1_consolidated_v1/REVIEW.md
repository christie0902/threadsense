# Relevance and consolidation repair (offline)

Zero model calls. Relevance: audited thread labels (developer audit, not confirmed by a team lead; no automatic relevance classifier). Consolidation: prepared Agent 2 decisions (PREPARED_AUDIT), not live judgments.

Before: 77 briefing items from 81 cards. After: 63 briefing items (49 reused cards + 14 consolidated issues pending fresh grounding); 3 threads in processing history.

## Processing history (excluded from clustering)

- C_SAFETY_GENERAL 1790894591.000100 (ROUTINE_ADMIN, AUDITED_LABEL): Where the team avatar image is saved: administrative, no bearing on annotation work, model behavior, tools or working conditions.
- C_MULTI_GENERAL 1790901493.000191 (SOCIAL_ONLY, AUDITED_LABEL): Language-day greetings only; no project content.
- C_RP_GENERAL 1790911349.000052 (SOCIAL_ONLY, AUDITED_LABEL): Well-wishes and a remark that the chat is quiet; no project content.

## Consolidated issues (pending fresh grounding)

- **QN handling for fictional contact details** <- QN handling for fictional phone numbers (needs review); Fictional placeholder contact details and QN handling (needs review)
  Basis: Both topics ask whether invented contact details (phone numbers, email addresses) need QN under the current rule, with members citing differing note versions; same safety policy question.
  Open subquestions: 5; review codes kept: GROUNDING_FAILURE, INHERITED_FLAG.
- **Spanish tú/usted register switching** <- Spanish register consistency (tú vs usted) (needs review); Spanish formal vs informal address alignment (needs review)
  Basis: Both topics concern Spanish responses that switch between usted and tú for the same addressee; same language-specialist route and question.
  Open subquestions: 4; review codes kept: GROUNDING_FAILURE, OTHER.
- **When a wrong date or year is a major factual error** <- Majority threshold for incorrect dates and key facts (recommended action); Rubric alignment on significant factual errors (needs review); Major error classification for incorrect year (needs review)
  Basis: All three topics ask when an incorrect date, year or key fact counts as a major factual error; judged as one set because the two accepted pairs overlap.
  Open subquestions: 6; review codes kept: GROUNDING_FAILURE, INHERITED_FLAG, NO_ACTION_NOT_SUPPORTED, OPEN_FOLLOW_UP, OTHER, TEMPORAL_CONFLICT.
- **Cosmetic differences: tie versus preference** <- Preference requires material user benefit (needs review); Tie threshold for near-identical responses (observation)
  Basis: Both topics ask whether slightly clearer or nicer wording justifies a preference or a tie, answered by the meaningful user-benefit criterion.
  Open subquestions: 3; review codes kept: INHERITED_FLAG.
- **Older scoring guide screenshot versus newer pinned note** <- Conflicting guidance source of truth (needs review); Rubric version conflict (needs review)
  Basis: Both topics ask whether an older scoring-guide screenshot or example is replaced by the newer pinned note or alignment announcement in response preference.
  Open subquestions: 3; review codes kept: GROUNDING_FAILURE, NO_ACTION_NOT_SUPPORTED, OPEN_CONFIRMATION, OPEN_FOLLOW_UP, OTHER.
- **Public business contact details are not private PII** <- Public business addresses as contact data (needs review); Public business contact information as PII (needs review)
  Basis: Both topics ask whether a business address or phone number from an official or published listing is private PII; same safety policy question.
  Open subquestions: 1; review codes kept: GROUNDING_FAILURE, INHERITED_FLAG, OTHER, TEMPORAL_CONFLICT.
- **Overlapping speech in transcription** <- Overlapping or background speech affecting transcription (needs review); Marking overlapping speech as unintelligible (needs review)
  Basis: Both topics ask how to transcribe or mark segments where two speakers overlap.
  Open subquestions: 3; review codes kept: GROUNDING_FAILURE, INHERITED_FLAG, NO_ACTION_NOT_SUPPORTED, OPEN_FOLLOW_UP, OTHER.
- **Which QN rule applies: old help page versus later announcement** <- Conflicting QN guidance sources (needs review); QN rule version reconciliation (needs review)
  Basis: Both topics ask whether a later announcement replaces an older QN note or help-page trigger; same documentation conflict.
  Open subquestions: 3; review codes kept: GROUNDING_FAILURE, OPEN_FOLLOW_UP, RECOMMENDATION_WITHHELD.
- **Transcript and audio content mismatch** <- Transcript and audio content mismatch (needs review); Audio-transcript mismatch clarification (needs review)
  Basis: Both topics concern a transcript that differs from what the recording says (including a spoken number shown as a different numeral).
  Open subquestions: 4; review codes kept: HIGH_SEVERITY, INHERITED_FLAG.
- **Format compliance versus accuracy** <- Format compliance versus content quality (recommended action); Instruction-following vs accuracy tradeoff (recommended action)
  Basis: Both topics ask which response wins when one follows the requested format and the other is more accurate.
  Open subquestions: 3; review codes kept: none.
- **Benign mention of a minor and QN** <- Minor mention alone does not require QN (recommended action); Flagging safe content that mentions a minor's age (needs review)
  Basis: Both topics ask whether safe content that mentions a child or a minor's age needs QN or a flag by itself.
  Open subquestions: 3; review codes kept: GROUNDING_FAILURE.
- **Repeated final line in generated audio** <- Repeated final line in exported audio vs LT playback loop (needs review); Repeated ending phrase in generated answer (needs review)
  Basis: Both topics report the generated answer repeating its last phrase or sentence; same model behavior.
  Open subquestions: 6; review codes kept: HIGH_SEVERITY, INHERITED_FLAG, NO_ACTION_NOT_SUPPORTED, OPEN_FOLLOW_UP.
- **Vietnamese regional vocabulary and target locale** <- Regional vocabulary fit for target audience (needs review); Vietnamese regional variant scoring alignment (needs review)
  Basis: Both topics concern Vietnamese regional word choice (southern versus northern usage) and the team lead's request to confirm the target audience before scoring.
  Open subquestions: 6; review codes kept: HIGH_SEVERITY, INHERITED_FLAG, NO_ACTION_NOT_SUPPORTED, OPEN_FOLLOW_UP.
- **LT response content fails to load in comparison view** <- Response fetch failure in comparison view (needs review); LT response-fetch timeout investigation (needs review)
  Basis: Both topics report LT failing to show Response A and B (spinning panes or a timeout) before comparison, with the team lead asking for task IDs and error state; same tool failure mode.
  Open subquestions: 2; review codes kept: HIGH_SEVERITY, INHERITED_FLAG.

## Candidate sets kept separate

- Locale-specific naturalness QA alignment || Vietnamese regional variant scoring alignment: UNCERTAIN. The locale topic never names its language or locale, so the same language-specialist route as the Vietnamese regional topic cannot be confirmed.
- Korean language QA edge cases || Korean honorific register shift clarification: DISTINCT. The Korean QA topic mixes a register-shift thread with an English-paragraph code-switching thread; merging the topic would pull an unrelated case into the honorific issue.
- Quoted harmful wording in warning or support context || Prompt-injection claims vs actual output content: DISTINCT. Quoted harmful wording in supportive context and roleplay jailbreak claims are different classification questions.
- LT player fails to load audio || Silent audio handling || Audio clip playback verification: DISTINCT. A player that never loads is a tool failure; a silent clip is model output content; the clip-verification topic mixes both.
- Task review for unsupported or mismatched sources || Citation support verification: DISTINCT. The source-review topic mixes a DOI that resolves to an unrelated article with an unsupported-claim case; the citation topic is only unsupported claims.
- Dead citation links vs factual correctness || Unfindable or non-existent references: DISTINCT. A dead link (source access failure) differs from references that do not exist.
- Public business contact information as PII || QN handling for fictional phone numbers: DISTINCT. Published business contact data and invented contact details are different policy questions.
- Dead citation links vs factual correctness || Task review for unsupported or mismatched sources: DISTINCT. Dead citation links and fabricated or unsupported sources are different failure modes.
- Register consistency across formality levels || Spanish formal vs informal address alignment: DISTINCT. The register-consistency topic mixes Korean and Spanish threads (different language-specialist routes).
- Waveform loads but playback will not start || Silent audio handling || Audio clip playback verification: DISTINCT. Playback that will not start is a tool failure; a silent clip is output content; the clip-verification topic mixes both.
- Locale-specific naturalness QA alignment || Korean language QA edge cases: DISTINCT. A locale naturalness disagreement and Korean register or code-switching cases are different questions.
- Preference requires material user benefit || Instruction-following vs accuracy tradeoff: DISTINCT. Preferring clearer wording and trading format against accuracy are different preference questions.
- Language adherence with code-switching responses || Loanwords vs unwanted code-switching: DISTINCT. Whether normal loanwords count as code-switching is a narrower definitional question than penalizing unrequested language changes.
- Overlapping or background speech affecting transcription || Repeated final line in exported audio vs LT playback loop: DISTINCT. Overlapping speech in transcription and a repeated final line are different audio problems.
- Register consistency across formality levels || Japanese register consistency and honorific use: DISTINCT. Mixed Korean and Spanish register questions and a Japanese honorific question use different language-specialist routes.
- Task review for unsupported or mismatched sources || LT response-fetch timeout investigation: DISTINCT. Source-review questions and a response-fetch tool failure are unrelated.
- LT review submission confirmation || LT audio task submission failure: DISTINCT. The submission topic mixes a disabled Submit button with a missing confirmation; different tool failure modes from a confirmation-only report.
- Korean honorific register shift clarification || Japanese keigo register-shift scoring: DISTINCT. Korean and Japanese register shifts are reviewed by different language specialists.
- Rubric alignment on significant factual errors || Rubric version conflict: DISTINCT. Defining a significant factual error differs from which rubric version is valid.
- Japanese text rendering issue || LT Hangul rendering issue: UNCERTAIN. Both show characters as boxes, but in different scripts and conditions (on reopening versus inside LT only); no evidence of one cause.
- Spanish register consistency (tú vs usted) || Language adherence with code-switching responses: DISTINCT. Register switching and language adherence are different questions.
- Spanish register consistency (tú vs usted) || Japanese register consistency and honorific use: DISTINCT. Spanish and Japanese register questions use different language-specialist routes.

## Shared actions

- Update the documentation (safety-qn-help-page@1.0 - Contact details): QN handling for fictional phone numbers [GROUNDING_FAILURE, INHERITED_FLAG]; Fictional placeholder contact details and QN handling [INHERITED_FLAG]
  Distinct topics support the same edit; this does not mean they share a cause. Related, not coordinated: Conflicting QN guidance sources

## Targeted Agent 3 refresh (not run)

- QN handling for fictional contact details (consolidated:consolidated_1eef9f984ee99bde): up to 4 requests
- Spanish tú/usted register switching (consolidated:consolidated_630d2bc373210782): up to 4 requests
- When a wrong date or year is a major factual error (consolidated:consolidated_95d0484d983ba712): up to 4 requests
- Cosmetic differences: tie versus preference (consolidated:consolidated_98704bfcf6102cd2): up to 4 requests
- Older scoring guide screenshot versus newer pinned note (consolidated:consolidated_082192b08cfcaf44): up to 4 requests
- Public business contact details are not private PII (consolidated:consolidated_9169449e1b82de41): up to 4 requests
- Overlapping speech in transcription (consolidated:consolidated_a95a89a02e04076d): up to 4 requests
- Which QN rule applies: old help page versus later announcement (consolidated:consolidated_5ebdd253f37a4102): up to 4 requests
- Transcript and audio content mismatch (consolidated:consolidated_6ae73962cc6d9c20): up to 4 requests
- Format compliance versus accuracy (consolidated:consolidated_90b29c234158a34b): up to 4 requests
- Benign mention of a minor and QN (consolidated:consolidated_484c74e7de655b9a): up to 4 requests
- Repeated final line in generated audio (consolidated:consolidated_eddc162776249e22): up to 4 requests
- Vietnamese regional vocabulary and target locale (consolidated:consolidated_a322c45298c18a22): up to 4 requests
- LT response content fails to load in comparison view (consolidated:consolidated_9ec2cbb386851835): up to 4 requests

Ceiling 56 requests, --max-cost $4.00 (expected about $1.95 at the full run's average). Preview with zero calls by dropping --run and --write:

```
uv run --locked python scripts/run_agent3_overnight.py --run --cutoff 2026-10-02T12:00:00Z --write data/experiments/<new dir> --handoff data/experiments/threadsense_full_v1/stages/agent2/agent2_v1 --fixture-root data/experiments/threadsense_full_v1/snapshot/slack --consolidation data/experiments/threadsense_full_v1_consolidated_v1/consolidation.json --processing-history data/experiments/threadsense_full_v1_consolidated_v1/relevance/processing_history.json --only consolidated:consolidated_1eef9f984ee99bde --only consolidated:consolidated_630d2bc373210782 --only consolidated:consolidated_95d0484d983ba712 --only consolidated:consolidated_98704bfcf6102cd2 --only consolidated:consolidated_082192b08cfcaf44 --only consolidated:consolidated_9169449e1b82de41 --only consolidated:consolidated_a95a89a02e04076d --only consolidated:consolidated_5ebdd253f37a4102 --only consolidated:consolidated_6ae73962cc6d9c20 --only consolidated:consolidated_90b29c234158a34b --only consolidated:consolidated_484c74e7de655b9a --only consolidated:consolidated_eddc162776249e22 --only consolidated:consolidated_a322c45298c18a22 --only consolidated:consolidated_9ec2cbb386851835 --max-requests 56 --max-cost 4.00
```

Live Agent 2 consolidation judgments in place of the prepared decisions: 38 requests, about $0.15.
