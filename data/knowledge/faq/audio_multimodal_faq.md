---
authoring_schema: mock-knowledge-markdown-v1
document_id: audio-multimodal-faq
document_type: faq
project_id: audio_multimodal
scope: project
batch_id: null
version: '1.1'
effective_at: '2026-09-20T13:00:00Z'
last_updated: '2026-09-20T13:00:00Z'
status: approved
authority:
  approved_by: U006
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: audio-multimodal-faq
synthetic: true
tags:
- audio
- playback
- clipping
- faq
---

# Audio Multimodal — FAQ (v1.1)

## Playback and tool issues

### Q: What if the player spins forever or never loads?
Report the task ID and available reproduction details as a tool incident. Do not score the recording as a model-quality failure while it cannot be evaluated.

### Q: Can I use QN because playback is unavailable?
Playback failure alone does not establish a content-based QN reason. Report the tool incident. If other accessible evidence raises a separate content concern, retain it for review rather than assuming what the unavailable audio contains.

## Scoring

### Q: How should I score mild clipping?
Brief, localized clipping with clear speech is a minor defect. Timestamp the affected span. For continuous artifacts or unclear impact, ask QA to review intelligibility and scope; do not decide from duration alone.

### Q: The transcript and audio disagree. What do I do?
Record the exact mismatch as a correspondence issue. Distinguish a recording error from a reference-transcript error; do not classify the mismatch as a playback failure.

### Q: How much speaker overlap is allowed before the transcription fails?
Mark the overlapping or unintelligible interval and preserve the usable remainder. Timestamp the span. Do not infer a whole-clip failure from a short affected interval.

## Language and TTS

### Q: The generated speech is in the wrong language. Is that a playback failure?
Confirm the requested language and permitted switching. If the recording itself contains an unrequested language mismatch, record it as a language-quality issue rather than a playback failure.
