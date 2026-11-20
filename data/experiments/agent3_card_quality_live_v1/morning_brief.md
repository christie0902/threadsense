# Morning brief - 2026-10-02T12:00:00Z

Status: **COMPLETE**. Semantic judgments: LIVE_MODEL. Live model judgments (LIVE_MODEL).

Window 2026-10-01T12:00:00+00:00 to 2026-10-02T12:00:00+00:00: 23 announcements (23 in the retrieval snapshot).

3 cards (NEEDS_REVIEW 3); 37 Model Review Queue items; 174 discussion members (10 on cards); 0 announcement-route members.

Retrieval snapshot `.index/retrieval` (cutoff 2026-10-02T12:00:00Z, build 4da16f090eb5): 0 saved TL decisions, 0 earlier announcements kept as history.

The discussions come from the Agent 2 handoff for this window.

Scoped run: 3 of 63 work items (60 out of scope; their members and review items are still accounted for).

## Spanish tú/usted register switching

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and three tutors report or question Spanish tú/usted inconsistencies across four threads. Current guidance calls for Spanish QA review; the team lead requested more context in one thread and directed final scoring to Spanish QA in another.

**What to do: Ask a language specialist to review.** Refer the reported Spanish register cases to Spanish QA for contextual scoring, carrying forward the thread-specific requests for supporting evidence.

**Why.** Current guidance assigns Spanish register assessment to Spanish QA and requires a case-specific rationale. Following through on the pending reviews fits that guidance without turning one thread's instruction into a project-wide rule.

**Draft to copy:**

> To the reporters: A QA tutor reports alternation; two tutors report usted changing to tú for the same user, with one also reporting unrequested informality. A tutor asks about lowering naturalness. In the formal-address thread, provide the exact before/after sentences and target audience requested by the team lead, plus the full Spanish exchange requested by a QA tutor.
> To Spanish QA: Review these cases in context and give case-specific scoring reasons. A QA tutor requested addressee checks in the formal-address and unrequested-informality threads. The team lead directed final scoring to Spanish QA for the naturalness-review example. Check intended formality, quotations and discourse context; an apparent shift is not an automatic major penalty.

**Still needs review:**
- Severity is high under the team rubric.

Threads: #multilingual-eval-general, 2026-10-01, started by a QA tutor: "Model alternates tú and usted — major?" (1790875469.000182); #multilingual-eval-qa, 2026-10-01, started by a QA tutor: "Should formal address always be preferred in ES?" (1790896116.000178); #multilingual-eval-general, 2026-10-02, started by a tutor: "Spanish register changes without the user requesting informality." (1790910015.000180); #multilingual-eval-general, 2026-10-02, started by a tutor: "Issue: Is tú vs usted inconsistency substantial enough to lower naturalness?" (1790922554.000179)

Sources: multilingual-eval-faq@1.1 (Register and honorifics); multilingual-eval-instructions@1.2 (Register and honorifics); multilingual-eval-instructions@1.2 (Content-quality rubric); multi-locale-announcement@1.0

## Waveform loads but playback will not start

Needs Review - severity high (assessed), mixed

**What happened.** A QA tutor and three tutors report playback failures across three threads; the QA tutor and two tutors describe a visible waveform without sound. Current guidance treats unavailable playback as a tool incident, but the threads do not establish restored playback.

**What to do: Report a technical issue to engineering.** Report the playback failures to engineering for investigation, with reporter follow-up on the outstanding diagnostics and current tool-incident handling.

**Why.** Current instructions classify these symptoms as tool incidents, and an engineer has already requested diagnostics for AUDIO-4294. Handling advice alone does not establish that an affected task can be evaluated.

**Draft to copy:**

> To the reporters: Report affected task IDs, browser/error state, and whether another clip plays; leave content quality unassessed while audio is unavailable. For AUDIO-4294, provide the LT error state and time requested by an engineer, plus the playhead-at-zero check a tutor requested. In the earlier QA thread, answer the QA tutor's request for the task reference, browser state, and whether the audio element loads.
> To engineering: Please investigate playback failures reported by a QA tutor and three tutors. The QA tutor and two tutors report a visible waveform but Play never starts sound; a tutor reports audio will not play on AUDIO-4294.

**Still needs review:**
- Severity is high under the team rubric.
- 1 earlier review flag is still open on these threads.

Threads: #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Could QA clarify this case: Waveform loads but play button never starts the recording." (1790903186.000110); #audio-multimodal-general, 2026-10-02, started by a tutor: "Audio won't play in LT; is this QN or a player issue?" (1790934294.000106); #audio-multimodal-qa, 2026-10-02, started by a QA tutor: "Issue: Waveform loads but play button never starts the recording." (1790941945.000105)

Sources: audio-multimodal-instructions@1.3 (Playback and unavailable content); audio-playback-trial-outcome@1.0 (Trial observation); audio-headset-check-approval@1.0 (Evidence available at review); knowledge_be3b20a90ec99ba14f12a391aa44588ea311eb5cf54076f0c729dc01c98b163d; knowledge_5ed9124870dd8eefcb7205ccae406532b720c5974c8e33d94d542f1be6fe1bbb

## Which QN rule applies: old help page versus later announcement

Needs Review - severity medium (assessed), mixed

**What happened.** A QA tutor and two tutors ask which QN rule applies amid conflicting documents or a recent change. Current guidance settles the fictional-contact exception, but the reports do not identify enough detail to establish whether that exception resolves their cases.

**Still needs review:**
- Recommendation needs review: the proposed action did not pass the checks.

Threads: #safety-classification-general, 2026-10-01, started by a QA tutor: "Help page still lists old quarantine trigger." (1790862407.000075); #safety-classification-general, 2026-10-02, started by a tutor: "Our pinned QN post contradicts the updated handbook section." (1790912292.000079); #safety-classification-general, 2026-10-02, started by a tutor: "Which safety quarantine rule applies after last week's change?" (1790924588.000076)

Sources: safety-classification-instructions@1.4 (Quarantine and contact details); safety-classification-faq@1.1 (Quarantine and QN); safety-classification-faq@1.1 (Conflicting sources); safety-classification-instructions@1.4 (Documentation discrepancies); safety-doc-sync-approval@1.0 (Evidence); safety-doc-sync-outcome@1.0 (Follow-up inspection); knowledge_7e90c9b5882834b19502bbf6aabef86ebcfd3d5977eb3cfdda93eb915c70fe67; knowledge_6be658d336d947f915ccc6de345828a558206039816fa6e91c7fe792b76207a8

## Consolidated topics

14 consolidated issues from 29 Agent 2 topics (PREPARED_AUDIT).

- **QN handling for fictional contact details** (2 topics)
- **Spanish tú/usted register switching** (2 topics)
- **When a wrong date or year is a major factual error** (3 topics)
- **Cosmetic differences: tie versus preference** (2 topics)
- **Older scoring guide screenshot versus newer pinned note** (2 topics)
- **Public business contact details are not private PII** (2 topics)
- **Overlapping speech in transcription** (2 topics)
- **Which QN rule applies: old help page versus later announcement** (2 topics)
- **Transcript and audio content mismatch** (2 topics)
- **Format compliance versus accuracy** (2 topics)
- **Benign mention of a minor and QN** (2 topics)
- **Repeated final line in generated audio** (2 topics)
- **Vietnamese regional vocabulary and target locale** (2 topics)
- **LT response content fails to load in comparison view** (2 topics)

## Processing history

Kept out of issue clustering by Agent 1 relevance; identities and review obligations kept:

- C_SAFETY_GENERAL 1790894591.000100: PROCESSING_HISTORY (ROUTINE_ADMIN; not clustered). Where the team avatar image is saved: administrative, no bearing on annotation work, model behavior, tools or working conditions.
- C_MULTI_GENERAL 1790901493.000191: PROCESSING_HISTORY (SOCIAL_ONLY; not clustered). Language-day greetings only; no project content.
- C_RP_GENERAL 1790911349.000052: PROCESSING_HISTORY (SOCIAL_ONLY; not clustered). Well-wishes and a remark that the chat is quiet; no project content.

## Model Review Queue

37 items (separate from the cards above):

- agent1 inherited_agent1_review: 37

## Usage

Requests sent 6, blocked 0; input 92370, output 22644 tokens; charged $0.4112.

