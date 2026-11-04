# Batch versus adaptive follow-up research (offline)

Zero model calls. Snapshot 4da16f090eb5 (cutoff 2026-10-02T12:00:00Z). Controller decisions: scripted stand-in. Drafts: prepared.

| Case | Arm | Follow-up searches | Expected evidence recovered | Used in a revision | Unnecessary searches | Stop reason | Model requests (est.) |
|---|---|---|---|---|---|---|---|
| audio_trial_outcome | batch (production) | 1 | audio-playback-trial-outcome@1.0 | not measured offline | 0 | ALL_REQUESTED_QUERIES_RUN | 3 |
| audio_trial_outcome | react (opt-in) | 1 | audio-playback-trial-outcome@1.0 | not measured offline | 0 | GAP_FILLED | 3 |
| audio_trial_outcome | batch (production), expansion off | 1 | no | not measured offline | 1 | ALL_REQUESTED_QUERIES_RUN | 3 |
| audio_trial_outcome | react (opt-in), expansion off | 2 | audio-playback-trial-outcome@1.0 | not measured offline | 0 | FOLLOW_UP_LIMIT | 4 |
| audio_trial_outcome | react (opt-in), expansion off, ceiling 5 | 2 | audio-playback-trial-outcome@1.0 | not measured offline | 0 | FOLLOW_UP_LIMIT | 4 |
| audio_trial_outcome | react (opt-in), expansion off, comparison triggered as in the live v6.2 run | 1 | no | not measured offline | 1 | REQUEST_CEILING | 4 |
| control_initial_evidence_answers | batch (production) | 0 | n/a | not measured offline | 0 | NO_GAP | 2 |
| control_initial_evidence_answers | react (opt-in) | 0 | n/a | not measured offline | 0 | NO_GAP | 2 |
| gap_corpus_cannot_answer | batch (production) | 1 | n/a | not measured offline | 1 | ALL_REQUESTED_QUERIES_RUN | 4 |
| gap_corpus_cannot_answer | react (opt-in) | 1 | n/a | not measured offline | 1 | REQUEST_CEILING | 4 |
| gap_corpus_cannot_answer | batch (production), expansion off | 1 | n/a | not measured offline | 1 | ALL_REQUESTED_QUERIES_RUN | 4 |
| gap_corpus_cannot_answer | react (opt-in), expansion off | 1 | n/a | not measured offline | 1 | REQUEST_CEILING | 4 |
| gap_corpus_cannot_answer | react (opt-in), expansion off, ceiling 5 | 2 | n/a | not measured offline | 2 | FOLLOW_UP_LIMIT | 5 (over the ceiling) |
