---
authoring_schema: mock-knowledge-markdown-v1
document_id: audio-multimodal-instructions
document_type: instructions
project_id: audio_multimodal
scope: project
batch_id: null
version: '1.3'
effective_at: '2026-09-15T13:00:00Z'
last_updated: '2026-09-15T13:00:00Z'
status: approved
authority:
  approved_by: U006
  role: TEAM_LEAD
  provenance: synthetic_manual_record
source:
  system: manual
  manual_key: audio-multimodal-instructions
synthetic: true
tags:
- audio
- playback
- quality
- submission
---

# Audio Multimodal — Instructions (v1.3)

## Project purpose
Evaluate audio intelligibility, correspondence with the reference transcript, and requested language. Distinguish recording/model defects from Label Tool (LT) failures.

## Playback and unavailable content
- If the player fails to load or start, report a tool incident with the task ID.
- A visible waveform with no playback is still a playback/tool incident; the waveform alone does not establish that the recording is silent.
- Do not score unavailable audio as a model-quality failure or make a content-based Quarantine (QN) decision solely because playback is unavailable.
- Capture the browser/error state and whether another clip plays. An old workaround must be checked against the current symptoms; recurrence alone does not establish which fix was tried or why it failed.
- Handling guidance does not confirm that playback has been repaired or that an affected task can be evaluated.

## Scoring audio quality
- Assess intelligibility and the affected span, not the word “clipping” alone.
- Brief, localized clipping or static with speech remaining clear is a minor defect.
- An artifact that makes a material speech span unusable is a major defect.
- Continuous artifacts or borderline impact require QA review with timestamps and an intelligibility description. Duration alone does not establish a major defect.
- Before treating silence as a content issue, verify playback, volume, and whether the audio file itself is silent. Preserve uncertainty when this cannot be checked.

## Overlap and transcript correspondence
Mark the overlapping or unintelligible interval. Keep usable portions of the clip and timestamp the affected span. Distinguish words missing from the audio from mistakes in the reference transcript.

## Language and repeated audio
Confirm the requested language and any permitted switching before recording a language mismatch. A familiar accent or an ordinary loanword is not automatically a defect.

When a phrase repeats, record where it occurs. If feasible, compare the downloaded file with player output. Do not call it a confirmed generation defect until the available evidence distinguishes generation from playback.

## Content-quality rubric
Major/minor here describe task-quality defects, not operational incident severity.

| Dimension | Major defect | Minor defect | Acceptable / no automatic penalty |
| --- | --- | --- | --- |
| Intelligibility | A material speech span is unusable | Brief clipping/static with words still clear | Background variation that does not impair the task |
| Audio–transcript correspondence | Key content is missing or contradicted | A limited omission that does not change meaning | Equivalent wording where the task allows it |
| Language match | A substantial unrequested mismatch with the required language | A limited genuine mismatch affecting adherence | Permitted switching, ordinary loanwords, or an acceptable accent |

## Tool incidents and submission
| Incident | Required handling |
| --- | --- |
| Playback unavailable | Report task ID and reproduction details; leave content quality unassessed |
| Intermittent playback | Record the affected tasks and whether access returned; do not assume every task recovered |
| Submit disabled or click fails | Capture task ID, required-field state, error and button behavior |
| Confirmation delayed | Check the actual receipt before recording submission as complete |

Tool incidents are assessed separately under the operational severity rubric. A selected rating or successful reload is not proof that the original task was submitted.
