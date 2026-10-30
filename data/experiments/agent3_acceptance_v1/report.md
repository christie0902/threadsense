# Agent 3 pilot - agent3pilot_03a10d4b972a9d5ce0dfe295cc0c32a3

Semantic judgments: **LIVE_MODEL**. Deterministic checks (citations, applicability, severity binding, temporal priority, authorization, routing, budgets) ran for real; with SCRIPTED_MOCK, the draft, grounding and comparison judgments are prepared responses and say nothing about model quality.

Handoff `data/processed/agent2_handoff_v2_projection`; index `knowledge-chunks-v2` (CURRENT (checked once before research)); as-of 2026-10-02T12:00:00Z; rubric severity-rubric-v3-semantic-signals (SHARED_DEFAULT).

Budget limits {'model_calls_per_topic': 4, 'model_calls_total': 28, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 42}; consumed {'retrieval_calls': 10, 'model_calls': 21}; HTTP requests {'sent': 21, 'blocked': 0}.

## audio_playback: Current handling announcement plus FAQ gap.

Topic: LT audio player playback failure (`cluster_6b59d13144282285`, 4 members)
- Card line: **NEEDS_REVIEW**; action: None; confidence 0.96 (HIGH)
- Severity: HIGH (ASSESSED); signals ['HIGH[3]']; affected reporters LOWER_BOUND 4; issues none
- Resolution: MIXED from grounded member states ['PARTIALLY_RESOLVED', 'PARTIALLY_RESOLVED', 'UNRESOLVED', 'UNRESOLVED']; Agent 1 attributed [('PARTIALLY_RESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'NEEDS_REVIEW')]
- Grounding: **FAILED** (STRUCTURAL+SEMANTIC); 31 statements; structural issues ['NAME_NOT_IN_CITED_EVIDENCE', 'NOT_A_CURRENT_ANNOUNCEMENT']; not supported ['claim:c2', 'action', 'announcement:k:slack:C_AUDIO_ANNOUNCEMENTS:1790890099.000112:64d38d33']
- Established announcement handling: `k:slack:C_AUDIO_ANNOUNCEMENTS:1790892000.000901:1c524924`
- Withheld from the card: claim:c2 (REJECTED_NAME_NOT_IN_CITED_EVIDENCE): Omar reports that LT audio will not play on AUDIO-6012 and asks whether this is QN or a player issue, recalling a previous-queue workaround.; action (INSUFFICIENT_PREMISES): POST_ALIGNMENT: Audio batch 06 playback handling: if the LT player never loads or starts, including when a waveform appears but playback doe; announcement:k:slack:C_AUDIO_ANNOUNCEMENTS:1790890099.000112:64d38d33 (PARTIALLY_SUPPORTED): This announcement applies to this topic and directs current handling: "Please keep examples in this thread while we check the scope.". Same 
- Temporal: NONE_FOUND; findings none
- ToT: COMPARED ['OPEN_CONFIRMATION']; presentation PREFERRED_WITH_ALTERNATIVES; candidates [('alignment_now', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('engineering_followup', 'ESCALATE_ENGINEERING', True, 'SUPPORTED', []), ('wait_for_confirmation', 'NO_ACTION', True, 'SUPPORTED', [])]
- Review reasons: HIGH_SEVERITY: Assessed HIGH under the shared default rubric.; INHERITED_FLAG: Upstream obligations remain open: inherited_agent1_review x2; GROUNDING_FAILURE: Withheld from this card: claim:c2: REJECTED_NAME_NOT_IN_CITED_EVIDENCE; action: INSUFFICIENT_PREMISES; announcement:k:slack:C_AUDIO_ANNOUNCEMENTS:1790890099.000; OPEN_CONFIRMATION: For the currently affected tasks, what do the requested reproduction and comparison-clip checks show, and has playback actually recovered? Current handling and 
- Inherited flags: 2; uncarried obligations none; group members in other topics (outside this card) 2
- Model calls: ['draft:OK', 'revision:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 2, 'model_calls': 4}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:audio-multimodal-faq@1.1:c724358c`, `k:slack:C_AUDIO_ANNOUNCEMENTS:1790892000.000901:1c524924`, `k:audio-multimodal-instructions@1.3:1c6df70e`, `k:audio-playback-trial-post@1.0:d674dbe6`, `k:slack:C_AUDIO_ANNOUNCEMENTS:1790890099.000112:64d38d33` |
| 2 | gap:PRIOR_DECISION_OUTCOME | history | decision,announcement,guideline,faq | `k:audio-playback-trial-approval@1.0:1779c36a`, `k:audio-playback-trial-outcome@1.0:16332fce`, `k:audio-playback-trial-approval@1.0:5e945970` |

Cited sources: k:audio-multimodal-instructions@1.3:1c6df70e (CURRENT_GUIDANCE; CURRENT), k:audio-multimodal-faq@1.1:c724358c (CURRENT_GUIDANCE; CURRENT), k:slack:C_AUDIO_ANNOUNCEMENTS:1790892000.000901:1c524924 (CURRENT_HANDLING (announcement verified for this topic); CURRENT), k:audio-playback-trial-approval@1.0:1779c36a (HISTORY_ONLY; CURRENT), k:audio-playback-trial-approval@1.0:5e945970 (HISTORY_ONLY; CURRENT), k:audio-playback-trial-post@1.0:d674dbe6 (HISTORY_ONLY; CURRENT), k:audio-playback-trial-outcome@1.0:16332fce (PRIOR_DECISION; CURRENT)

## json_vs_prose: Unresolved TL confirmation.

Topic: Format adherence vs factual accuracy (`cluster_fb1dce1eeeedc4cb`, 3 members)
- Card line: **NEEDS_REVIEW**; action: POST_ALIGNMENT; confidence 0.93 (HIGH)
- Severity: MEDIUM (ASSESSED); signals ['MEDIUM[0]']; affected reporters LOWER_BOUND 2; issues none
- Resolution: UNKNOWN from grounded member states ['UNKNOWN', 'UNRESOLVED', 'UNRESOLVED']; Agent 1 attributed [('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'VERIFIED')]
- Grounding: **FAILED** (STRUCTURAL+SEMANTIC); 22 statements; structural issues ['NAME_NOT_IN_CITED_EVIDENCE']; not supported ['claim:C6', 'resolution:member_225803f43142caa5d3c165cf', 'reporter:U018']
- Established announcement handling: none
- Withheld from the card: claim:C6 (REJECTED_NAME_NOT_IN_CITED_EVIDENCE): In Omar's thread, Alex asks for the exact formatting instruction so QA can verify whether it was mandatory before weighing the responses. Th; resolution:member_225803f43142caa5d3c165cf (PARTIALLY_SUPPORTED): Member thread member_225803f43142caa5d3c165cf is UNRESOLVED: Replies discuss separate compliance and correctness dimensions and ask about ma; reporter:U018 (UNSUPPORTED): U018 reports, in their own cited message, being affected by this problem.
- Temporal: NONE_FOUND; findings none
- ToT: COMPARED ['OPEN_CONFIRMATION']; presentation PREFERRED_WITH_ALTERNATIVES; candidates [('alignment_now', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('case_review_session', 'SCHEDULE_ALIGNMENT', True, 'SUPPORTED', []), ('wait_for_tl', 'NO_ACTION', True, 'PARTIALLY_SUPPORTED', [])]
- Review reasons: INHERITED_FLAG: Upstream obligations remain open: inherited_agent1_review x1; GROUNDING_FAILURE: Withheld from this card: claim:C6: REJECTED_NAME_NOT_IN_CITED_EVIDENCE; resolution:member_225803f43142caa5d3c165cf: PARTIALLY_SUPPORTED; reporter:U018: UNSUPPOR; OPEN_CONFIRMATION: For each reported pair, including RP-3824, what preference is warranted once the exact prompt and both responses establish whether the structure was mandatory a
- Inherited flags: 1; uncarried obligations none; group members in other topics (outside this card) 0
- Model calls: ['draft:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 1, 'model_calls': 3}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:response-preference-faq@1.1:fa9b6a3d`, `k:rp-tie-calibration-outcome@1.0:053fe48a`, `k:response-preference-instructions@1.1:a71c54c7`, `k:rp-audit-manifest-post@1.0:f64eba9c`, `k:rp-tie-calibration-post@1.0:4a3c786f` |

Cited sources: k:response-preference-faq@1.1:fa9b6a3d (CURRENT_GUIDANCE; CURRENT), k:response-preference-instructions@1.1:a71c54c7 (CURRENT_GUIDANCE; CURRENT), k:rp-tie-calibration-outcome@1.0:053fe48a (PRIOR_DECISION; CURRENT)

## fictional_pii: Current clarification and stale help-page section.

Topic: Fictional phone number quarantine handling (`cluster_9378eb54bc546fcd`, 3 members)
- Card line: **NEEDS_REVIEW**; action: UPDATE_DOCUMENTATION; confidence 0.94 (HIGH)
- Severity: HIGH (ASSESSED); signals ['HIGH[3]']; affected reporters LOWER_BOUND 3; issues none
- Resolution: MIXED from grounded member states ['PARTIALLY_RESOLVED', 'UNKNOWN', 'UNRESOLVED']; Agent 1 attributed [('PARTIALLY_RESOLVED', 'CORRECTED'), ('PARTIALLY_RESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'CORRECTED')]
- Grounding: **FAILED** (SEMANTIC); 23 statements; structural issues none; not supported ['announcement:k:slack:C_SAFETY_ANNOUNCEMENTS:1790920369.000062:16f43f1b', 'resolution:member_b26b6a34827bebdc9e52666f']
- Established announcement handling: `k:safety-fictional-pii-clarification@1.0:3682998e`, `k:safety-pii-clarification-post@1.0:8dc35766`
- Withheld from the card: announcement:k:slack:C_SAFETY_ANNOUNCEMENTS:1790920369.000062:16f43f1b (UNSUPPORTED): This announcement applies to this topic and directs current handling: "Please keep examples in this thread while we check the scope.". Same ; resolution:member_b26b6a34827bebdc9e52666f (PARTIALLY_SUPPORTED): Member thread member_b26b6a34827bebdc9e52666f is UNRESOLVED: Peer replies discuss fictional characters, request verification that details ar
- Temporal: DETECTED; findings [('UNEXPLAINED_SOURCE_CONFLICT', 'DETECTED'), ('UNEXPLAINED_SOURCE_CONFLICT', 'DETECTED')]
- ToT: COMPARED ['TEMPORAL_CONFLICT']; presentation SURFACE_GROUNDED_ALTERNATIVES; candidates [('candidate_1', 'UPDATE_DOCUMENTATION', True, 'PARTIALLY_SUPPORTED', ['APPLICABILITY_OVERSTATED']), ('candidate_2', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('candidate_3', 'NO_ACTION', True, 'PARTIALLY_SUPPORTED', [])]
- Review reasons: HIGH_SEVERITY: Assessed HIGH under the shared default rubric.; INHERITED_FLAG: Upstream obligations remain open: inherited_agent1_review x1; TEMPORAL_CONFLICT: UNEXPLAINED_SOURCE_CONFLICT: The old help-page branch requires initial quarantine for fictional contact details; current sources exempt verified fictional place; GROUNDING_FAILURE: Withheld from this card: announcement:k:slack:C_SAFETY_ANNOUNCEMENTS:1790920369.000062:16f43f1b: UNSUPPORTED; resolution:member_b26b6a34827bebdc9e52666f: PARTIA
- Inherited flags: 1; uncarried obligations none; group members in other topics (outside this card) 0
- Model calls: ['draft:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 2, 'model_calls': 3}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:safety-classification-faq@1.1:6025b955`, `k:safety-classification-faq@1.1:7efcb54d`, `k:safety-fictional-pii-clarification@1.0:3682998e`, `k:safety-pii-clarification-post@1.0:8dc35766`, `k:slack:C_SAFETY_ANNOUNCEMENTS:1790920369.000062:16f43f1b` |
| 2 | supersession_check | history | guideline,faq,decision,announcement | `k:safety-qn-help-page@1.0:983cdeaa` |

Cited sources: k:safety-classification-faq@1.1:6025b955 (CURRENT_GUIDANCE; CURRENT), k:safety-fictional-pii-clarification@1.0:3682998e (CURRENT_HANDLING (announcement verified for this topic); CURRENT), k:safety-pii-clarification-post@1.0:8dc35766 (CURRENT_HANDLING (announcement verified for this topic); CURRENT), k:safety-qn-help-page@1.0:983cdeaa (HISTORY_ONLY; SECTION_SUPERSEDED)

## korean_register: Language-specific question: scoped precedent and expert routing.

Topic: Korean honorific level inconsistency QA (`cluster_3b950ad40b12ab58`, 4 members)
- Card line: **NEEDS_REVIEW**; action: ROUTE_TO_LANGUAGE_SPECIALIST; confidence 0.94 (HIGH)
- Severity: HIGH (ASSESSED); signals ['HIGH[3]']; affected reporters LOWER_BOUND 3; issues none
- Resolution: UNKNOWN from grounded member states ['UNKNOWN', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED']; Agent 1 attributed [('UNRESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'VERIFIED'), ('UNRESOLVED', 'VERIFIED'), ('UNRESOLVED', 'VERIFIED')]
- Grounding: **FAILED** (STRUCTURAL+SEMANTIC); 24 statements; structural issues ['NAME_NOT_IN_CITED_EVIDENCE']; not supported ['claim:c5', 'resolution:member_74e92dc600ce9bbc7f5bfc91']
- Established announcement handling: none
- Withheld from the card: claim:c5 (REJECTED_NAME_NOT_IN_CITED_EVIDENCE): In Sofia's thread, Alex instructs that Korean QA needs context and sentence endings before severity is decided, and states that the prior-ba; resolution:member_74e92dc600ce9bbc7f5bfc91 (PARTIALLY_SUPPORTED): Member thread member_74e92dc600ce9bbc7f5bfc91 is UNRESOLVED: Replies raise possible quotation and addressee explanations but do not establis
- Temporal: NONE_FOUND; findings none
- ToT: COMPARED ['OPEN_CONFIRMATION']; presentation PREFERRED_WITH_ALTERNATIVES; candidates [('route_current_cases', 'ROUTE_TO_LANGUAGE_SPECIALIST', True, 'SUPPORTED', []), ('post_current_guidance_alignment', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('wait_for_tl_confirmation', 'NO_ACTION', True, 'PARTIALLY_SUPPORTED', [])]
- Review reasons: HIGH_SEVERITY: Assessed HIGH under the shared default rubric.; INHERITED_FLAG: Upstream obligations remain open: inherited_agent1_review x1; GROUNDING_FAILURE: Withheld from this card: claim:c5: REJECTED_NAME_NOT_IN_CITED_EVIDENCE; resolution:member_74e92dc600ce9bbc7f5bfc91: PARTIALLY_SUPPORTED; OPEN_CONFIRMATION: For the current reported cases, does the full Korean context establish a justified quotation or speaker/addressee change, or an inappropriate shift, and what de
- Inherited flags: 1; uncarried obligations none; group members in other topics (outside this card) 0
- Model calls: ['draft:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 1, 'model_calls': 3}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:multi-korean-referral@1.0:929d7cee`, `k:multilingual-eval-faq@1.1:c080929d`, `k:multi-korean-scoped-result@1.0:5b489480`, `k:multilingual-eval-instructions@1.2:e19f0e0c`, `k:multilingual-eval-instructions@1.2:db772378` |

Cited sources: k:multilingual-eval-instructions@1.2:e19f0e0c (CURRENT_GUIDANCE; CURRENT), k:multilingual-eval-faq@1.1:c080929d (CURRENT_GUIDANCE; CURRENT), k:multilingual-eval-instructions@1.2:db772378 (CURRENT_GUIDANCE; CURRENT), k:multi-korean-referral@1.0:929d7cee (PRIOR_DECISION; CURRENT), k:multi-korean-scoped-result@1.0:5b489480 (PRIOR_DECISION; CURRENT)

## submit_failure: Escalation evidence and misleading resolved history. The Submit threads are a projection gap: no Agent 2 topic exists, so the card covers the group's unassigned members and keeps the gap visible.

Topic: Unassigned members of routed_440e64c7fbdcc49f (projection gap; no Agent 2 topic) (`routed_440e64c7fbdcc49f`, 4 members)
- Card line: **NEEDS_REVIEW**; action: None; confidence 0.93 (HIGH)
- Severity: HIGH (ASSESSED); signals ['HIGH[0]', 'HIGH[3]']; affected reporters LOWER_BOUND 5; issues none
- Resolution: UNRESOLVED from grounded member states ['UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED']; Agent 1 attributed [('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'VERIFIED')]
- Grounding: **FAILED** (SEMANTIC); 35 statements; structural issues none; not supported ['claim:C13', 'action', 'announcement:k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7db831c7']
- Established announcement handling: none
- Withheld from the card: claim:C13 (ANNOUNCEMENT_NOT_VERIFIED): The relevant batch-15 announcement directs keeping Submit examples in its thread while scope is checked. Its directive concerns example coll; action (ESSENTIAL_PREMISE_NOT_PASSED): ESCALATE_ENGINEERING: Collect and route the new Submit-failure examples to engineering. Capture task ID, required-field state, error or LT s; announcement:k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7db831c7 (UNSUPPORTED): This announcement applies to this topic and directs current handling: "Please keep examples in this thread while we check the scope.". The a
- Temporal: NONE_FOUND; findings none
- ToT: COMPARED ['OPEN_CONFIRMATION']; presentation PREFERRED_WITH_ALTERNATIVES; candidates [('scoped_engineering_handoff', 'ESCALATE_ENGINEERING', True, 'SUPPORTED', []), ('diagnostic_alignment_only', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('wait_for_tl_confirmation', 'NO_ACTION', True, 'PARTIALLY_SUPPORTED', [])]
- Review reasons: HIGH_SEVERITY: Assessed HIGH under the shared default rubric.; INHERITED_FLAG: Upstream obligations remain open: inherited_agent1_review x2, projection_gap x1; GROUNDING_FAILURE: Withheld from this card: claim:C13: ANNOUNCEMENT_NOT_VERIFIED; action: ESSENTIAL_PREMISE_NOT_PASSED; announcement:k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7; OPEN_CONFIRMATION: Do the new disabled-control and nonresponsive-click examples match the earlier batch-15 engineering incident, or require separate investigation? The earlier rec
- Inherited flags: 3; uncarried obligations none; group members in other topics (outside this card) 0
- Model calls: ['draft:OK', 'revision:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 2, 'model_calls': 4}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:rp-submit-zoom-generalization-rejected@1.0:044e436d`, `k:slack:C_RP_ANNOUNCEMENTS:1790888971.000030:7db831c7`, `k:rp-submit-engineering-handoff@1.0:d84c905d`, `k:response-preference-instructions@1.1:36683c52`, `k:rp-submit-engineering-handoff@1.0:6afb6e6d` |
| 2 | gap:PRIOR_DECISION_OUTCOME | history | decision,announcement,guideline | `k:rp-tie-calibration-approval@1.0:99b5da48`, `k:rp-tie-calibration-outcome@1.0:053fe48a` |

Cited sources: k:response-preference-instructions@1.1:36683c52 (CURRENT_GUIDANCE; CURRENT), k:rp-submit-engineering-handoff@1.0:d84c905d (PRIOR_DECISION; CURRENT), k:rp-submit-engineering-handoff@1.0:6afb6e6d (PRIOR_DECISION; CURRENT), k:rp-submit-zoom-generalization-rejected@1.0:044e436d (PRIOR_DECISION; CURRENT), k:rp-tie-calibration-approval@1.0:99b5da48 (PRIOR_DECISION; CURRENT), k:rp-tie-calibration-outcome@1.0:053fe48a (PRIOR_DECISION; CURRENT)

## repeated_ending: Observation; avoid inventing a confirmed cause.

Topic: Repeated final line in exported audio (`cluster_b7e5234380f9ea67`, 5 members)
- Card line: **NEEDS_REVIEW**; action: POST_ALIGNMENT; confidence 0.9 (HIGH)
- Severity: HIGH (ASSESSED); signals ['HIGH[3]']; affected reporters LOWER_BOUND 7; issues none
- Resolution: UNKNOWN from grounded member states ['UNKNOWN', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED', 'UNRESOLVED']; Agent 1 attributed [('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'CORRECTED'), ('UNRESOLVED', 'NEEDS_REVIEW'), ('UNRESOLVED', 'VERIFIED'), ('UNRESOLVED', 'VERIFIED')]
- Grounding: **FAILED** (SEMANTIC); 28 statements; structural issues none; not supported ['resolution:member_a05733133a11c3689d715928']
- Established announcement handling: none
- Withheld from the card: resolution:member_a05733133a11c3689d715928 (PARTIALLY_SUPPORTED): Member thread member_a05733133a11c3689d715928 is UNRESOLVED: The thread adds a transcript/recording observation and requests comparison, but
- Temporal: NONE_FOUND; findings none
- ToT: COMPARED ['OPEN_CONFIRMATION']; presentation PREFERRED_WITH_ALTERNATIVES; candidates [('alignment_now', 'POST_ALIGNMENT', True, 'SUPPORTED', []), ('engineering_investigation', 'ESCALATE_ENGINEERING', True, 'PARTIALLY_SUPPORTED', []), ('wait_for_tl', 'NO_ACTION', True, 'PARTIALLY_SUPPORTED', [])]
- Review reasons: HIGH_SEVERITY: Assessed HIGH under the shared default rubric.; INHERITED_FLAG: Upstream obligations remain open: assisted_content_review x1, inherited_agent1_review x1; GROUNDING_FAILURE: Withheld from this card: resolution:member_a05733133a11c3689d715928: PARTIALLY_SUPPORTED; OPEN_CONFIRMATION: Do task-specific downloaded-file versus player comparisons establish that the reported repeated endings are present in the generated files, rather than only in 
- Inherited flags: 2; uncarried obligations none; group members in other topics (outside this card) 0
- Model calls: ['draft:OK', 'tot:OK', 'grounding:OK']; budget used {'retrieval_calls': 1, 'model_calls': 3}

| Step | Purpose | Mode | Types | New evidence |
| --- | --- | --- | --- | --- |
| 1 | initial_current_guidance | current | guideline,faq,decision,announcement | `k:audio-multimodal-instructions@1.3:7a5ab59d`, `k:audio-repeat-observation-review@1.0:ae0550d0`, `k:slack:C_AUDIO_ANNOUNCEMENTS:1790892000.000901:1c524924`, `k:audio-multimodal-faq@1.1:e9bcf43a`, `k:audio-multimodal-instructions@1.3:eb85357a` |

Cited sources: k:audio-multimodal-instructions@1.3:7a5ab59d (CURRENT_GUIDANCE; CURRENT), k:audio-multimodal-faq@1.1:e9bcf43a (CURRENT_GUIDANCE; CURRENT), k:audio-repeat-observation-review@1.0:ae0550d0 (PRIOR_DECISION; CURRENT)

## control_unsupported_payroll: Negative control: no source answers this.

Control outcome: **UNSUPPORTED** (no card). Retrieved 5 results; model calls ['draft:OK'].

