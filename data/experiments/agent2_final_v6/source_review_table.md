# Exact semantic-review coverage for final Agent 2 v6

Codex-assisted source review, not human approval or an independent accuracy benchmark.
The 32 new reviews cover 80 identities/211 messages. Eight unchanged reused candidates
retain their original reviews covering 23 identities/61 messages. Total: 40 groups,
103 identities, 272 messages. The other 50 groups/97 identities/244 messages received
mechanical checks, not semantic certification. See the [frozen selection criteria](pre_run_review.json),
[new full assessments and exact evidence](review_supplement.json),
[original reused assessments](../agent2_uncertainty_v6/review_supplement.json), and
[combined bound review](../../processed/agent2_final_v6/combined_review_supplement.json).
Eight new findings and two retained original findings apply through the mandatory loader.

| Group | Project | Members / messages | Automated outcome | Automated severity | Inherited obligations | Review provenance | Findings |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| `cluster_aa0548b34bd2cbdc` | audio_multimodal | 1 / 2 | CONSOLIDATED | UNKNOWN | 0 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_6042d88a3d171626` | audio_multimodal | 4 / 9 | CONSOLIDATED | UNKNOWN/UNKNOWN | 1 | reused original review | RESOLUTION_SCOPE_UNCERTAINTY; OVEREXCLUSIVE_FOLLOWUP_DESCRIPTION |
| `cluster_db20d884110726af` | multilingual_eval | 3 / 9 | CONSOLIDATED | UNKNOWN | 2 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_6ac8dcc3e5d75776` | multilingual_eval | 4 / 10 | CONSOLIDATED | UNKNOWN | 1 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_608d1e987c058c11` | multilingual_eval | 4 / 13 | CONSOLIDATED | HIGH | 0 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_7a710abcd893e0a6` | safety_classification | 4 / 11 | CONSOLIDATED | UNKNOWN | 1 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_098a12c005ecf00b` | response_preference | 2 / 4 | CONSOLIDATED | UNKNOWN/UNKNOWN | 0 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_e849ac33e11b49fe` | response_preference | 1 / 3 | CONSOLIDATED | UNKNOWN | 0 | reused original review | No material finding recorded; see assessment limitations |
| `cluster_6b59d13144282285` | audio_multimodal | 6 / 19 | CONSOLIDATED | UNKNOWN/HIGH | 2 | new assisted review | OVEREXCLUSIVE_REPLY_NOTE |
| `cluster_ab4fa9e9a46e0a07` | audio_multimodal | 5 / 13 | CONSOLIDATED | HIGH | 1 | new assisted review | OVEREXCLUSIVE_GUIDANCE_SUMMARY |
| `cluster_b86492028238aec3` | audio_multimodal | 3 / 6 | CONSOLIDATED | HIGH | 1 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_bc1ccc03c19a64cf` | audio_multimodal | 2 / 5 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_8190481b92f62c4f` | audio_multimodal | 1 / 2 | CONSOLIDATED | HIGH | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_cd187cdcd10ce01b` | audio_multimodal | 1 / 2 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_0df9e215dec4e314` | multilingual_eval | 4 / 10 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | CONTEXT_OR_TENTATIVE_COMPARISON_AS_DIRECT_ANSWER |
| `cluster_17bdf57b8379a917` | multilingual_eval | 3 / 7 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_9b2d023be9a7459c` | multilingual_eval | 2 / 5 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_0220b905049d72c6` | multilingual_eval | 1 / 4 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_be4e3bac742eccb3` | multilingual_eval | 1 / 2 | FAILED | UNKNOWN/unassessed | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_14c5fc257d90b58f` | response_preference | 5 / 17 | CONSOLIDATED | HIGH | 3 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_f944891544b06f79` | response_preference | 5 / 13 | CONSOLIDATED | UNKNOWN | 2 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_2d814c8e21470de9` | response_preference | 4 / 7 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | RESOLUTION_SCOPE_UNCERTAINTY |
| `cluster_430237353843237f` | response_preference | 3 / 8 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_fff2a52a6010f8e7` | response_preference | 3 / 9 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | INVENTED_PREFERENCE_DECISION |
| `cluster_1ba596334ad5cde7` | response_preference | 2 / 4 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_4a8809dfc56fd3f9` | response_preference | 2 / 5 | CONSOLIDATED | HIGH | 2 | new assisted review | DIAGNOSTIC_ALTERNATIVE_AS_OBSERVED_SYMPTOM |
| `cluster_4ee8bbfaa21d62ec` | response_preference | 2 / 4 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_dc219b33a3be1a2e` | response_preference | 2 / 8 | CONSOLIDATED | LOW | 1 | new assisted review | UNDERSTATED_WORK_BLOCKAGE |
| `cluster_8e09163eab37a4cc` | response_preference | 1 / 3 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_c9bdba359e6e7cd2` | response_preference | 1 / 2 | FAILED | UNKNOWN/unassessed | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_cea91beb01258723` | safety_classification | 4 / 12 | CONSOLIDATED | HIGH | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_11ce3cfce9431006` | safety_classification | 3 / 8 | CONSOLIDATED | HIGH | 0 | new assisted review | INCOMPLETE_CITATION_FOR_TASK_REFERENCE |
| `cluster_1f272d7fa384df0c` | safety_classification | 3 / 10 | CONSOLIDATED | UNKNOWN | 1 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_a6dfe8374217a497` | safety_classification | 3 / 7 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_96fdf164d2c17844` | safety_classification | 2 / 5 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_b3bfce178039d7d4` | safety_classification | 2 / 4 | CONSOLIDATED | UNKNOWN/UNKNOWN | 1 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_024655fb52cc3352` | safety_classification | 1 / 2 | CONSOLIDATED | N/A | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_06c08cf4143f2022` | safety_classification | 1 / 2 | CONSOLIDATED | HIGH | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_083355b88d76dca6` | safety_classification | 1 / 2 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
| `cluster_746ef6a7762162f9` | safety_classification | 1 / 4 | CONSOLIDATED | UNKNOWN | 0 | new assisted review | No material finding recorded; see assessment limitations |
