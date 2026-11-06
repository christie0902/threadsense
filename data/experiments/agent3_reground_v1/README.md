# Targeted re-grounding (2026-11-06, paid, approved)

Two single grounding requests (`scripts/reground_topic.py`, `gpt-6.1-sol`) over items of
`threadsense_full_v1_consolidated_refresh_v1`. Every other stage is the refresh run's recorded output; the request
judged every statement afresh. Total charged: $0.094 of $0.42 reserved.

| File | Card | Charged | Grounding | Card after |
|---|---|---|---|---|
| `overlapping_speech.json` | Overlapping speech in transcription | $0.051 | PASSED (35/35 SUPPORTED, incl. `claim:c1`) | Needs Review (inherited flag only), action shown |
| `format_compliance.json` | Format compliance versus accuracy | $0.043 | PASSED (all SUPPORTED, incl. the 3 edited statements) | Recommended Action, severity MEDIUM, reminder shown |

Provenance: the overlap card's text is unchanged model output. On the format card, three statements (summary sentence 1,
the reason to intervene, the severity signal) are developer-drafted wording (`data/evaluation/agent3_format_card_wording_v1.json`)
that the live model judged SUPPORTED; the rest is the refresh run's model output.

Not yet folded into the combined briefing (`threadsense_full_v1_combined_v1` is unchanged).
