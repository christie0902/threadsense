"""Build synthetic Slack-shaped conversations from ThreadSense blueprint.

Run at project root:
    python scripts/generate_slack_fixtures.py

Input:
    data/evaluation/thread_blueprint_200.json   (hidden ground truth)
    data/evaluation/topic_catalog.json           (scenario writing cues)
    data/fixtures/slack/                         (OPTIONAL original seed conversations)

Output (safe staging directory, NOT the existing original fixtures):
    data/fixtures/slack_generated/users.json
    data/fixtures/slack_generated/channels/C_*.json

The generated Slack fixture JSON never contains the answer labels in the blueprint.
Only stdlib is used. No API calls are made. This produces a reproducible *starter
corpus*; review/hand-edit dialogue variety before treating it as final research data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "data/evaluation/thread_blueprint_200.json"
CATALOG = ROOT / "data/evaluation/topic_catalog.json"
ORIGINAL = ROOT / "data/fixtures/slack"
OUTPUT = ROOT / "data/fixtures/slack_generated"  # Never overwrite source examples.
SEED = 20261024

PROJECT_CHANNEL = {
    "response_preference": ("RP", "response-preference"),
    "safety_classification": ("SAFETY", "safety-classification"),
    "audio_multimodal": ("AUDIO", "audio-multimodal"),
    "multilingual_eval": ("MULTI", "multilingual-eval"),
}

# Deliberately authored paraphrases beyond the two starting phrases in the catalog.
# The catalog's sample_phrasings remain in rotation, but are not the only prompts.
VARIANTS = {
    "citation_scoring": [
        "A linked a real report but the paragraph doesn't back up its claim. Score impact?",
        "What if the answer is otherwise right but its citations go to a 404?",
        "Source title looks credible; clicking it takes me to an unrelated paper.",
    ],
    "hallucinated_citations": [
        "I'm finding references with journal names that don't exist. Do we log this separately?",
        "Both candidates invented article titles, even though their explanations sound plausible.",
        "This DOI resolves to a completely different publication than what B claims.",
    ],
    "instruction_following_priority": [
        "Prompt asked for a JSON object; B explains it beautifully in prose. Which is better?",
        "Can accuracy outweigh ignoring the user's requested output structure?",
        "A hits every instruction but is vague; B skips the format and gets facts right.",
    ],
    "major_error_definition": [
        "Would one wrong year in an otherwise correct answer count as a major error?",
        "Rubric example calls this minor, but it changes the final recommendation.",
        "Is the key fact being inaccurate enough to trigger major even if tone is fine?",
    ],
    "model_connection_failure": [
        "Queue item hangs before the model outputs show up. Anyone else?",
        "I'm getting a response fetch timeout on consecutive tasks in LT.",
        "Can't compare answers because both panes just spin after opening the task.",
    ],
    "platform_submit_failure": [
        "LT won't save my choice after I select the final rating.",
        "I can click all options but the Submit control stays disabled.",
        "Anyone else stuck on the last step? Finished scoring but can't send it.",
        "Selected B twice now; still can't submit from the tasking screen.",
    ],
    "qa_tie_rating_drift": [
        "QA is reversing ties even when both outputs fail the same criteria.",
        "My tie score passed last week but got flagged on near-identical tasks today.",
        "Are we applying the tie threshold differently between QA shifts?",
    ],
    "stale_rubric_examples": [
        "The example in the rubric says one thing, but Friday's alignment says another.",
        "Should we follow the pinned update or the older scoring guide screenshot?",
        "I'm worried L0 folks keep quoting an out-of-date example.",
    ],
    "tie_vs_slight_preference": [
        "Both are acceptable. Is slightly clearer wording enough to pick B?",
        "No major faults, just a small difference in relevance. Tie or preference?",
        "A is cleaner and B is more detailed; does that warrant slight preference?",
    ],
    "borderline_nsfw_classification": [
        "Text is suggestive but never explicit. Where's the cutoff for NSFW?",
        "The scene implies intimacy without describing anything graphic. Which label?",
        "QA says borderline; tutors are splitting on this description.",
    ],
    "fictional_pii_quarantine": [
        "The prompt uses someone@example.test in a made-up story. QN or proceed?",
        "Is a clearly fake phone number still sensitive under the current policy?",
        "I can tell the name/address are fictional, but the guideline says all PII.",
    ],
    "jailbreak_content_labeling": [
        "The response claims it ignored safeguards, but it doesn't give harmful steps.",
        "Is a fake 'system override' message itself a category trigger?",
        "Model announces a jailbreak persona. Not sure whether to rate behavior or content.",
    ],
    "minor_mention_quarantine": [
        "A child is mentioned in a normal school story. Does that alone need QN?",
        "Safe family context, but a minor's age is explicit. Should I flag it?",
        "Are neutral references to teenagers covered by the minors quarantine rule?",
    ],
    "outdated_qn_guidance": [
        "Our pinned QN post contradicts the updated handbook section.",
        "Which safety quarantine rule applies after last week's change?",
        "L0 is following the old decision tree from the onboarding deck.",
    ],
    "pii_in_public_records": [
        "Response includes a shop's public phone number. Is that PII?",
        "The address is on the official business page. Do we still quarantine?",
        "Public government directory contact details: acceptable or QN?",
    ],
    "qa_safety_threshold_drift": [
        "Two QA passes gave opposing safety labels for nearly the same case.",
        "We might be shifting the threshold across review teams.",
        "My last three flags were overturned without a rule explanation.",
    ],
    "self_harm_context_interpretation": [
        "A safety resource quotes a harmful phrase only to warn against it. Label?",
        "Supportive crisis response contains prohibited keywords in a quotation.",
        "Do we classify intent or just matching language in this scenario?",
    ],
    "audio_language_mismatch": [
        "Requested English narration, but the generated voice is Spanish.",
        "Speaker switches languages halfway even though the prompt is English-only.",
        "Transcript is English and the audio playback is in another language.",
    ],
    "audio_player_loading_failure": [
        "Audio won't play in LT; is this QN or a player issue?",
        "Waveform loads but play button never starts the recording.",
        "The player stays on the spinner after the task opens.",
        "Getting a blank player on three items; can I safely continue tasking?",
    ],
    "qa_audio_artifact_drift": [
        "QA split on whether mild clipping should count as a major defect.",
        "Same background pop got minor on one task and major on another.",
        "Are we aligned on the threshold for short audio glitches?",
    ],
    "repeated_generated_audio": [
        "The voice loops the final line twice, no sign of a player glitch.",
        "Last phrase repeats verbatim in the generated answer. Anyone seeing this?",
        "Audio model keeps doubling the ending even though the transcript doesn't.",
    ],
    "silent_audio_quarantine": [
        "Clip is completely silent, but the waveform exists. QN or quality score?",
        "Zero sound on the track. Can't tell whether it's intentionally silent.",
        "Do blank generated clips count as missing media or a valid failure?",
    ],
    "speaker_overlap_edge_case": [
        "Two speakers talk over each other for two seconds. Mark unintelligible?",
        "How much overlap is allowed before the transcription fails the rubric?",
        "Multiple voices at once: should I split segments or flag the clip?",
    ],
    "transcript_audio_mismatch": [
        "Transcript shows a sentence that never appears in the recording.",
        "The spoken number differs from what's written in the reference text.",
        "Should we score omissions in the audio or errors in the transcript field?",
    ],
    "code_switching_evaluation": [
        "Prompt is in Korean but the answer drops an English paragraph in the middle.",
        "Model mixes Spanish and English even though the user asked for Spanish.",
        "Is normal loanword use different from unwanted code-switching?",
    ],
    "japanese_honorific_consistency": [
        "Japanese response starts with です/ます then shifts to plain style abruptly.",
        "The model changes honorific level when addressing the same person.",
        "Keigo is correct at the start, but the closing feels too casual. Penalty?",
    ],
    "korean_register_switching": [
        "Starts in 존댓말 and suddenly uses 반말. Is that a major naturalness error?",
        "한 문단은 존댓말이고 다음 문단은 반말이에요. Which QA rule should we follow?",
        "Polite Korean for the first two sentences, casual ending in the same answer.",
    ],
    "non_latin_script_rendering": [
        "Hangul in LT renders as □□□ on the rating screen.",
        "Japanese characters show as boxes after I reopen the task.",
        "Non-Latin text goes missing in the preview even though the source looks fine.",
    ],
    "qa_native_speaker_disagreement": [
        "Two native reviewers gave opposite naturalness scores. How to align?",
        "QA consensus isn't holding on regional word choice.",
        "Language reviewers disagree, but both interpretations seem plausible.",
    ],
    "spanish_formality_preference": [
        "The reply begins with usted and then switches to tú midway.",
        "Spanish register changes without the user requesting informality.",
        "Is tú vs usted inconsistency substantial enough to lower naturalness?",
    ],
    "vietnamese_regional_variation": [
        "The answer uses 'bắp' but the prompt seems aimed at northern readers. Penalize?",
        "Is 'heo' instead of 'lợn' acceptable for this target audience?",
        "Vietnamese wording is natural in the south, but QA reviewer is from the north.",
    ],
}

ROUTINE_TEXT = {
    "routine_queue_reminder": "Reminder: the response preference queue closes at 6 PM today.",
    "routine_shift_coverage": "Jordan is covering the early preference queue shift tomorrow.",
    "routine_training_link": "Here's the onboarding resource link for new preference reviewers: internal training hub.",
    "isolated_social_checkin": "Hope everyone had a decent break — the chat is quieter today 🙂",
    "routine_policy_meeting_notice": "Safety calibration meeting is scheduled for the usual afternoon slot.",
    "routine_queue_assignment": "The next safety queue assignments have been published.",
    "routine_weekly_schedule": "Reminder: weekly safety QA schedule is pinned in this channel.",
    "isolated_nonissue_question": "Does anyone know where the new team avatar image is saved?",
    "routine_headset_reminder": "Reminder to use headphones for the audio calibration exercise.",
    "routine_audio_slot_schedule": "Audio review calibration is on the calendar this afternoon.",
    "routine_queue_finish_notice": "Today's audio queue closes at the end of shift.",
    "isolated_social_audio_comment": "Finally got a quieter room to work from — what a difference 😄",
    "routine_locale_shift_schedule": "Language QA coverage times for this week are in the shared calendar.",
    "routine_training_resource": "Sharing a new multilingual review resource from the team library.",
    "routine_queue_reopen_notice": "Multilingual queue will reopen after the routine deployment window.",
    "isolated_social_language_comment": "Happy language-day Friday, everyone!",
}

DEFAULT_USERS = [
    {"id": "U001", "name": "Alex", "role": "TEAM_LEAD"},
    {"id": "U002", "name": "Mina", "role": "QA_TUTOR"},
    {"id": "U003", "name": "Jordan", "role": "TUTOR"},
    {"id": "U004", "name": "Sofia", "role": "TUTOR"},
    {"id": "U005", "name": "Daniel", "role": "ENGINEER"},
    {"id": "U006", "name": "Priya", "role": "TEAM_LEAD"},
    {"id": "U007", "name": "Leo", "role": "QA_TUTOR"},
    {"id": "U008", "name": "Hana", "role": "QA_TUTOR"},
    {"id": "U009", "name": "Nico", "role": "TUTOR"},
    {"id": "U010", "name": "Avery", "role": "TUTOR"},
    {"id": "U011", "name": "Rina", "role": "TUTOR"},
    {"id": "U012", "name": "Sam", "role": "TUTOR"},
    {"id": "U013", "name": "Jun", "role": "TUTOR"},
    {"id": "U014", "name": "Linh", "role": "QA_TUTOR"},
    {"id": "U015", "name": "Carla", "role": "TUTOR"},
    {"id": "U016", "name": "Tariq", "role": "ENGINEER"},
    {"id": "U017", "name": "Bea", "role": "TUTOR"},
    {"id": "U018", "name": "Omar", "role": "TUTOR"},
    {"id": "U019", "name": "Yuki", "role": "QA_TUTOR"},
    {"id": "U020", "name": "Theo", "role": "TUTOR"},
]

# Broad response moves deliberately avoid inserting hidden intervention labels.
PEER_REPLIES = [
    "Same thing happened on my last item. I wasn't sure which rule to use.",
    "Seeing this too, but not on every task in the queue.",
    "I read the current guide and I'm still unsure how this example fits.",
    "I went with the conservative reading, though I'd like QA to confirm.",
    "I thought the opposite was decided earlier. Could be mixing up batches.",
    "This only shows up on some tasks for me, not consistently.",
    "Can someone check whether the pinned note is still current?",
]
QA_REPLIES = [
    "QA has seen mixed interpretations of this. We need one consistent rule.",
    "I can reproduce the ambiguity using two recent queue examples.",
    "Our rubric examples don't clearly cover this exact situation.",
    "There are a few similar QA flags; let's verify against the current instructions.",
    "I'm checking whether this was discussed in the last alignment.",
]
PARTIAL_TL_REPLIES = [
    "Thanks for flagging. I'm checking the current guidance before we lock in a rule.",
    "I see the inconsistency. Please hold the ambiguous examples for QA review.",
    "We need confirmation from the decision owner; no final alignment yet.",
    "Acknowledged. I will compare this with the last batch's decision and update the team.",
]
RESOLVED_TL_BY_CLASS = {
    "PLATFORM_TECHNICAL": "Confirmed as a tool-side issue for these tasks. Do not invent a label; flag the affected task IDs for engineering review.",
    "INSTRUCTION_CLARIFICATION": "For this specific example, apply the current written rule and flag only cases that contradict it. This thread is resolved.",
    "EDGE_CASE": "For this case, use the closest documented rubric example and note the ambiguity in the QA comment. Resolved for this item.",
    "QUARANTINE": "For the example shown, follow the current QN decision tree rather than quarantining on keywords alone. Resolved for this task.",
    "QA_ALIGNMENT": "QA and TL reviewed this example together and agreed on the scoring treatment for this item. Marking the thread resolved.",
    "MODEL_BEHAVIOR_OBSERVATION": "This behavior is reproducible in the provided example. Record it under the model-observation tag; the immediate labeling question is resolved.",
}
# Substantive *case-level* TL replies. We will later author source docs/history that
# make these decisions internally consistent; these are not authoritative real-world rules.
RESOLVED_TL_BY_TOPIC = {
    "citation_scoring": "For this item, a citation that fails to support the stated claim does not count as evidence. Score the unsupported claim using the factuality rubric.",
    "hallucinated_citations": "This reference is fabricated. Record it as an unsupported factual claim, not merely a formatting defect.",
    "instruction_following_priority": "Here the requested output format is explicit, so a prose-only response fails instruction following. Evaluate factuality separately.",
    "major_error_definition": "A wrong fact that changes the central answer is major; a nonessential date typo is minor in this example.",
    "model_connection_failure": "We confirmed a response-fetch error for these task IDs. Flag the affected LT task references; do not invent a model quality score.",
    "platform_submit_failure": "Engineering confirmed a task-submission problem. Do not count an item complete until LT acknowledges the submission; flag affected IDs.",
    "qa_tie_rating_drift": "QA re-reviewed this pair: both responses have comparable weaknesses, so tie is supported for this example.",
    "stale_rubric_examples": "For the specific case raised here, use the newer TL alignment rather than the older screenshot; we're reconciling the written example.",
    "tie_vs_slight_preference": "Slight preference needs a meaningful quality difference; purely cosmetic wording differences are not sufficient in this example.",
    "borderline_nsfw_classification": "This example is suggestive but not explicit; apply the context-based category threshold, not keyword matching alone.",
    "fictional_pii_quarantine": "The example uses clearly fictional contact information, so it does not need QN on that basis alone. Do flag genuine personal data.",
    "jailbreak_content_labeling": "Classify the model's observable content and behavior. A claim that it bypassed policies is not by itself proof of harmful output.",
    "minor_mention_quarantine": "A benign mention of a child in this story does not alone meet the QN criteria. Other content flags still apply if present.",
    "outdated_qn_guidance": "For this scenario, follow the later dated TL clarification; the older pinned decision tree is under revision.",
    "pii_in_public_records": "Here the contact is a business's published public listing, not a private person's contact details. Apply the public-business exception noted in QA guidance.",
    "qa_safety_threshold_drift": "QA calibration reviewed this example and agreed on the threshold for the depicted context; apply the same reasoning to close matches.",
    "self_harm_context_interpretation": "The quoted warning here is a supportive safety context, not an instruction to cause harm. Classify intent and content together.",
    "audio_language_mismatch": "This recording is in the wrong requested language. Mark the language-match defect rather than treating it as a playback failure.",
    "audio_player_loading_failure": "The player issue is reproducible on LT. Treat the affected item as a technical incident, not a content-based QN determination.",
    "qa_audio_artifact_drift": "In this example, brief clipping that leaves speech intelligible is minor; sustained loss of intelligibility meets the major threshold.",
    "repeated_generated_audio": "The repeat is present in the generated recording itself. Record a model-output repetition issue, rather than a browser playback defect.",
    "silent_audio_quarantine": "This file should contain spoken output but the delivered recording is silent. Flag missing-media handling, not a poor speech-quality score.",
    "speaker_overlap_edge_case": "Mark only the unintelligible overlapping span for this example; do not discard the entire recording if other parts remain clear.",
    "transcript_audio_mismatch": "The spoken number does not match the reference transcript. Score the transcript/audio discrepancy under the matching criterion.",
    "code_switching_evaluation": "Occasional loanwords are acceptable here; an unrequested full-language switch lowers language adherence in this case.",
    "japanese_honorific_consistency": "This example changes politeness level for the same addressee without context. Mark a register-consistency problem.",
    "korean_register_switching": "Korean QA reviewed this example: the unexplained 존댓말-to-반말 switch is a register issue for this prompt.",
    "non_latin_script_rendering": "The missing Hangul characters are an LT rendering issue, not a Korean-language quality fault. Flag the task for engineering.",
    "qa_native_speaker_disagreement": "Language QA compared both interpretations and documented the target locale for this item; use that locale-specific criterion.",
    "spanish_formality_preference": "In this reply, the switch from usted to tú has no conversational trigger. Mark it as a register-consistency error.",
    "vietnamese_regional_variation": "For this example, both regional terms are natural Vietnamese; do not penalize solely for dialect unless the requested locale specifies one.",
}
LANGUAGE_PEER_APPEND = {
    "ko": "존댓말에서 반말로 바뀌는 게 확실히 어색해요.",
    "vi": "Từ này vẫn tự nhiên trong ngữ cảnh miền Nam nhé.",
    "ja": "同じ相手なのに敬語のレベルが変わっていますね。",
    "es": "El cambio entre tú y usted se nota bastante.",
}

HISTORICAL_NUDGES = {
    "PAST_DECISION_RELEVANT": ["I recall a TL post on something similar, but can't find it.", "Pretty sure this came up in a previous alignment."],
    "STALE_DOCUMENTATION": ["The pinned instructions and the recent TL post don't seem to match.", "Our doc screenshot still shows the old wording, I think."],
    "SUPERSEDED_DECISION": ["Two different announcements seem to give different rules.", "Does the newer TL clarification replace the older rule?"],
    "RECURRING_FROM_PRIOR_BATCH": ["I remember this being discussed in the last batch too.", "This feels like the same confusion we had before the batch reset."],
    "PREVIOUS_INTERVENTION_FAILED": ["We tried the workaround last batch, but I'm seeing it again.", "Thought this was fixed earlier; it's back on new tasks."],
    "PREVIOUS_INTERVENTION_SUCCEEDED": ["Last batch's alignment helped, but this example is slightly different.", "I think the prior clarification covered most cases, except this one."],
}
STYLE_LEADS = {
    "NORMAL": ["", "Question for the team: ", "Has anyone run into this? "],
    "ABBREVIATED": ["Quick q: ", "FYI, ", "LT/queue check: "],
    "SLANGY": ["anyone else seeing this? ", "ok so... ", "ugh, another weird one: "],
    "FORMAL": ["Requesting clarification: ", "Please confirm the correct treatment: "],
    "TECHNICAL": ["Observed during tasking: ", "Repro case: "],
    "WORKFLOW_STRUCTURED": ["", "", ""],
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_user_data(data):
    """Understand common user-fixture envelopes and return (users, original_shape)."""
    if isinstance(data, list):
        return deepcopy(data), "list"
    if isinstance(data, dict) and isinstance(data.get("users"), list):
        return deepcopy(data["users"]), "users_list"
    if isinstance(data, dict) and isinstance(data.get("users"), dict):
        return [dict(info, id=uid) for uid, info in data["users"].items()], "users_dict"
    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
        return [dict(info, id=uid) for uid, info in data.items()], "dict"
    raise ValueError("Unsupported users.json structure; expected list, {users:[...]}, or ID-keyed map.")


def package_users(users, shape):
    if shape == "list":
        return users
    if shape == "users_list":
        return {"users": users}
    mapping = {user["id"]: {k: v for k, v in user.items() if k != "id"} for user in users}
    return {"users": mapping} if shape == "users_dict" else mapping


def user_role(u):
    # Matches the recommended sample fixture shape. No role inference from name.
    role = u.get("role", "TUTOR")
    if isinstance(role, dict):
        role = role.get("value", "TUTOR")
    return role


def make_users():
    source = ORIGINAL / "users.json"
    if source.exists():
        users, shape = parse_user_data(load_json(source))
    else:
        users, shape = [], "users_list"
    by_id = {u["id"]: u for u in users}
    for default in DEFAULT_USERS:
        if default["id"] not in by_id:
            users.append(deepcopy(default))
    users.sort(key=lambda u: u["id"])
    by_id = {u["id"]: u for u in users}
    for role in ["TUTOR", "QA_TUTOR", "TEAM_LEAD", "ENGINEER"]:
        if not any(user_role(u) == role for u in users):
            raise ValueError(f"No user with role {role}")
    return users, shape, by_id


def channel_id(project, channel_type):
    return f"C_{PROJECT_CHANNEL[project][0]}_{channel_type}"


def channel_name(project, channel_type):
    return f"{PROJECT_CHANNEL[project][1]}-{channel_type.lower()}"


def get_seed_channels():
    """Load original examples; refuse duplications instead of silently discarding work."""
    channels = {}
    seed_roots = {}
    if not (ORIGINAL / "channels").exists():
        return channels, seed_roots
    for file in sorted((ORIGINAL / "channels").glob("*.json")):
        data = load_json(file)
        if "channel" not in data or "history" not in data or "replies" not in data:
            raise ValueError(f"Expected channel/history/replies in {file}")
        cid = data["channel"]["id"]
        if cid in channels:
            raise ValueError(f"Duplicate seed channel {cid}")
        channels[cid] = data
        for root in data["history"]:
            tid = str(root["ts"])
            if tid in seed_roots:
                raise ValueError(f"Duplicate root in source fixtures: {tid}")
            seed_roots[tid] = (cid, root)
    return channels, seed_roots


def reaction(name, user_ids):
    """Slack-style reaction with the identity of the people who reacted.

    Example: {"name": "this", "users": ["U001"], "count": 1}
    Names are Slack emoji IDs, without surrounding colons.
    """
    return {"name": name, "users": list(user_ids), "count": len(user_ids)}


def stable_choice(key, options):
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return options[digest[0] % len(options)]


def mock_reactions(ts, author_id, text, users_by_role):
    """Non-authoritative background reactions on about 25% of new messages.

    Never assign a TL a random approval reaction: TL confirmation is added
    deliberately to a *specific substantive reply* in create_thread().
    Hashing avoids changing the random stream for message content/timestamps.
    """
    digest = hashlib.sha256(f"{ts}|{author_id}|{text}".encode("utf-8")).digest()
    if digest[0] >= 64:
        return []
    role = "QA_TUTOR" if digest[1] < 70 else "TUTOR"
    pool = [uid for uid in users_by_role[role] if uid != author_id]
    if not pool:
        return []
    reactor_id = pool[digest[2] % len(pool)]
    names = ("eyes", "thumbsup", "thinking_face", "white_check_mark", "warning")
    name = names[digest[3] % len(names)]
    result = [reaction(name, [reactor_id])]
    if digest[4] < 30:
        other_pool = [uid for uid in users_by_role["TUTOR"] if uid not in {author_id, reactor_id}]
        if other_pool:
            result[0] = reaction(name, [reactor_id, other_pool[digest[5] % len(other_pool)]])
    return result


def msg(ts, user, text, users_by_role, source="USER", thread_ts=None):
    row = {
        "ts": ts, "user": user, "text": text,
        "source": source,
        "reactions": mock_reactions(ts, user, text, users_by_role),
    }
    if thread_ts is not None:
        row["thread_ts"] = thread_ts
    return row


def nice_source(row, channel):
    return "WORKFLOW" if row.get("language_style") == "WORKFLOW_STRUCTURED" and channel != "ANNOUNCEMENTS" else "USER"


def pick(rng, xs):
    return rng.choice(xs)


def choose_user(rng, users_by_role, role, exclude=None):
    options = [u for u in users_by_role[role] if u != exclude]
    if not options:
        options = users_by_role[role]
    return pick(rng, options)


def topic_phrase(row, scenario, topic_index, rng):
    topic = row["latent_topic"]
    if row["primary_issue_class"] is None:
        return ROUTINE_TEXT.get(topic, scenario.get("scenario_description", "Routine update."))
    examples = list(scenario.get("sample_phrasings", [])) + VARIANTS.get(topic, [])
    if not examples:
        raise ValueError(f"Missing authored topic phrases for {topic}")
    # Rotate rather than picking with replacement; all repeated topics get distinct seeds
    # until variants run out. Additional phrasing still varies by style and context.
    base = examples[topic_index % len(examples)]
    style = row["language_style"]
    if style == "WORKFLOW_STRUCTURED":
        context = pick(rng, ["Task review", "QA clarification", "Edge case review"])
        return f"[{context}]\nIssue: {base}\nQuestion: how should this item be handled?"
    lead = pick(rng, STYLE_LEADS.get(style, [""]))
    if style == "TECHNICAL" and row["primary_issue_class"] == "PLATFORM_TECHNICAL":
        return f"{lead}{base} Browser refresh didn't change the behavior."
    if style == "ABBREVIATED":
        return f"{lead}{base}".replace("button", "btn").replace("because", "bc").replace("please", "pls")
    return lead + base


def maybe_context(row, topic_index, rng):
    # Add topic-appropriate contextual facts, never hidden labels/action codes.
    if row["primary_issue_class"] is None:
        return ""
    possibilities = [
        "Happened on two items in this queue.",
        "It wasn't obvious from the pinned guide.",
        "QA might be seeing the same pattern.",
        "Not sure whether my interpretation is the outlier here.",
        "I can share the task reference with QA if needed.",
    ]
    if row["primary_issue_class"] == "PLATFORM_TECHNICAL":
        possibilities += ["Refreshing LT didn't fix it.", "Seems task-specific; a different item loaded fine."]
    elif row["primary_issue_class"] == "QUARANTINE":
        possibilities += ["Trying to decide whether to QN or keep tasking."]
    elif row["primary_issue_class"] == "QA_ALIGNMENT":
        possibilities += ["My QA notes and the rubric don't seem aligned."]
    if row.get("temporal_case") != "NONE":
        possibilities += HISTORICAL_NUDGES.get(row["temporal_case"], [])
    return pick(rng, possibilities[(topic_index % 3):] or possibilities)


def use_terms(row, root, rng):
    """Nudge generated root towards labeled jargon rather than blindly appending every label."""
    if row["primary_issue_class"] is None:
        return root
    terms = row.get("domain_terms_used", [])
    t = root.lower()
    if "LT" in terms and "lt" not in t.split() and "label tool" not in t:
        return root + " (on LT)"
    if "QN" in terms and not re.search(r"\bqn\b", t):
        return root + " Would this be QN?"
    if "QA" in terms and not re.search(r"\bqa\b", t):
        return root + " Looking for a QA read on this."
    if "queue" in terms and "queue" not in t:
        return root + " I'm seeing it in the current queue."
    return root


def timestamp_for_reply(root_ts, j, rng, max_time):
    base = float(root_ts)
    # Keep within snapshot and ensure strictly monotonic chronological order.
    t = min(base + (j + 1) * 150 + rng.randint(0, 40), max_time)
    return f"{int(t)}.{j + 100:06d}"


def create_thread(row, scenario, topic_index, users_by_role, rng, end_second):
    ctype = row["channel_type"]
    issue = row["primary_issue_class"] is not None
    role = "TEAM_LEAD" if ctype == "ANNOUNCEMENTS" else ("QA_TUTOR" if ctype == "QA" else pick(rng, ["TUTOR"] * 8 + ["QA_TUTOR"] * 2))
    root_user = choose_user(rng, users_by_role, role)
    root_text = topic_phrase(row, scenario, topic_index, rng)
    if issue:
        detail = maybe_context(row, topic_index, rng)
        # Vary whether context lands in the top-level root or a follow-up.
        if topic_index % 2 == 0 and detail:
            root_text = f"{root_text} {detail}"
        if ctype == "ANNOUNCEMENTS":
            root_text = f"Heads-up: several people flagged this scenario today — {root_text} Please reply with examples; no new rule confirmed yet."
        else:
            root_text = use_terms(row, root_text, rng)
    # Different task references increase realism and eliminate accidental duplicate roots.
    # No task references are personally identifying or evaluation labels.
    if issue and topic_index % 3 == 2:
        root_text += f" (task ref {row['project_id'][:2].upper()}-{int(float(row['thread_id'])) % 10000:04d})"
    root = msg(row["thread_id"], root_user, root_text, users_by_role, nice_source(row, ctype))
    if row["language"]:
        root["language"] = row["language"]

    if not issue:
        # Routine/outlier threads are mostly standalone; an occasional neutral acknowledgment.
        if topic_index % 3:
            root["reply_count"] = 0
            return root, []
        reply = msg(timestamp_for_reply(root["ts"], 0, rng, end_second), choose_user(rng, users_by_role, "TUTOR", exclude=root_user), "Thanks for the heads-up!", users_by_role, thread_ts=root["ts"])
        root["reply_count"] = 1
        return root, [reply]

    state = row["resolution_state"]
    secondary_replies = []
    # Mixture: peer conversation (not necessarily a TL response), follow-up from QA,
    # plus one TL/engineer response only when resolution metadata calls for it.
    n = rng.randint(1, 3)
    if state == "UNRESOLVED" and topic_index % 5 == 0:
        n = 0  # Unanswered initial posts are intentional.
    for i in range(n):
        author_role = pick(rng, ["TUTOR", "TUTOR", "QA_TUTOR"])
        author = choose_user(rng, users_by_role, author_role, exclude=root_user)
        pool = QA_REPLIES if author_role == "QA_TUTOR" else PEER_REPLIES
        text = pick(rng, pool)
        if i == 0 and topic_index % 2 == 1:
            context = maybe_context(row, topic_index, rng)
            text += (" " + context) if context else ""
        if i == 0 and row.get("language") and topic_index % 3 == 1:
            text += " " + LANGUAGE_PEER_APPEND.get(row["language"], "")
        secondary_replies.append((author, text))

    # About one in four *substantively resolved* issue threads will end with an
    # actual QA/trainer answer + a TL emoji confirming that answer. No TL text.
    # This means presence of TL text alone cannot determine resolution.
    signature = hashlib.sha256(str(row["thread_id"]).encode("utf-8")).digest()
    reaction_only_approval = (
        state == "RESOLVED_IN_THREAD"
        and ctype != "ANNOUNCEMENTS"
        and signature[0] < 85  # roughly 1/3 of eligible resolved cases
        and row["primary_issue_class"] != "PLATFORM_TECHNICAL"
    )
    approving_tl = None
    if state == "PARTIALLY_RESOLVED":
        secondary_replies.append((choose_user(rng, users_by_role, "TEAM_LEAD"), pick(rng, PARTIAL_TL_REPLIES)))
    if state == "RESOLVED_IN_THREAD":
        content = RESOLVED_TL_BY_TOPIC.get(row["latent_topic"], RESOLVED_TL_BY_CLASS.get(row["primary_issue_class"]))
        if not content:
            raise ValueError(f"Missing resolved response for {row['primary_issue_class']}")
        if reaction_only_approval:
            # QA or an experienced tutor supplies the concrete reasoning.
            responder_role = "QA_TUTOR" if signature[1] < 204 else "TUTOR"
            responder = choose_user(rng, users_by_role, responder_role, exclude=root_user)
            secondary_replies.append((responder, content))
            approving_tl = choose_user(rng, users_by_role, "TEAM_LEAD")
        else:
            secondary_replies.append((choose_user(rng, users_by_role, "TEAM_LEAD"), content))

    replies = [msg(timestamp_for_reply(root["ts"], i, rng, end_second), user, text, users_by_role, thread_ts=root["ts"])
               for i, (user, text) in enumerate(secondary_replies)]

    if reaction_only_approval:
        # The endorsement belongs on the answer, NOT the original question.
        name = ("this", "agree", "white_check_mark")[signature[2] % 3]
        replies[-1]["reactions"].insert(0, reaction(name, [approving_tl]))
    elif state == "UNRESOLVED" and replies and signature[0] < 20:
        # TL saw the discussion but has not approved any answer.
        root["reactions"].append(reaction("eyes", [choose_user(rng, users_by_role, "TEAM_LEAD")]))

    root["reply_count"] = len(replies)
    return root, replies


def validate_and_save(channels, users, users_shape, expected_ids, existing_roots):
    roots = {}
    total_replies = 0
    for cid, data in channels.items():
        # The DataAdapter reads history/replies with timestamps and thread-root duplication.
        data["history"].sort(key=lambda msg: float(msg["ts"]), reverse=True)
        for root in data["history"]:
            tid = str(root["ts"])
            if tid in roots:
                raise ValueError(f"Duplicate generated thread ID {tid}")
            roots[tid] = cid
            child = data["replies"].get(tid, [])
            count = int(root.get("reply_count", 0))
            if count != (len(child) - 1 if child else 0):
                raise ValueError(f"reply_count mismatch for {tid}: count={count}; replies={len(child)}")
            if child and str(child[0]["ts"]) != tid:
                raise ValueError(f"Replies missing root as first item: {tid}")
            if child and any(str(reply.get("thread_ts", tid)) != tid for reply in child[1:]):
                raise ValueError(f"Wrong thread_ts in replies for {tid}")
            total_replies += count
    if set(roots) != expected_ids:
        raise ValueError(f"Thread ID mismatch. Missing={set(expected_ids)-set(roots)} Extra={set(roots)-set(expected_ids)}")
    for tid, (cid, original) in existing_roots.items():
        if tid not in roots or roots[tid] != cid:
            raise ValueError(f"Seed thread lost or moved: {tid}")
        got = next(r for r in channels[cid]["history"] if str(r["ts"]) == tid)
        if got != original:
            raise ValueError(f"Original sample modified: {tid}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    save_json(OUTPUT / "users.json", package_users(users, users_shape))
    for cid, data in sorted(channels.items()):
        save_json(OUTPUT / "channels" / (cid + ".json"), data)
    return total_replies


def main():
    rng = random.Random(SEED)
    rows = load_json(BLUEPRINT)
    catalog = load_json(CATALOG)
    if not isinstance(rows, list) or len(rows) != 200:
        raise ValueError("Run Step 23 first; expected a list of exactly 200 blueprint records.")
    scenarios = {s["scenario_id"]: s for s in catalog["topics"]}
    users, users_shape, users_by_id = make_users()
    users_by_role = defaultdict(list)
    for u in users:
        users_by_role[user_role(u)].append(u["id"])
    source_channels, existing_roots = get_seed_channels()
    blueprint_ids = {str(r["thread_id"]) for r in rows}
    if set(existing_roots) - blueprint_ids:
        raise ValueError(f"Original Slack fixtures have roots absent from blueprint: {set(existing_roots)-blueprint_ids}")
    channels = {}
    for project, info in catalog["projects"].items():
        for ctype in ("GENERAL", "QA", "ANNOUNCEMENTS"):
            cid = channel_id(project, ctype)
            if cid in source_channels:
                data = deepcopy(source_channels[cid])
            else:
                data = {"channel": {"id": cid, "name": channel_name(project, ctype), "project_id": project,
                                    "batch_id": info["batch_id"], "channel_type": ctype},
                        "history": [], "replies": {}}
            data["channel"]["batch_id"] = info["batch_id"]
            data["channel"]["project_id"] = project
            data["channel"]["channel_type"] = ctype
            channels[cid] = data

    topic_progress = Counter()
    new_count = 0
    # Distinct messages derived from seed + project/topic/style/context combinations.
    end_second = int(datetime(2026, 10, 2, 12, tzinfo=timezone.utc).timestamp()) - 1
    for row in rows:
        tid = str(row["thread_id"])
        cid = channel_id(row["project_id"], row["channel_type"])
        if row.get("channel_id", cid) != cid:
            raise ValueError(f"Blueprint channel mismatch for {tid}")
        key = (row["project_id"], row["latent_topic"])
        idx = topic_progress[key]
        topic_progress[key] += 1
        if tid in existing_roots:
            if existing_roots[tid][0] != cid:
                raise ValueError(f"Seed channel does not match blueprint: {tid}")
            continue
        scenario = scenarios[row["scenario_id"]]
        root, replies = create_thread(row, scenario, idx, users_by_role, rng, end_second)
        channels[cid]["history"].append(root)
        if replies:
            channels[cid]["replies"][tid] = [deepcopy(root)] + replies
        new_count += 1
    total_replies = validate_and_save(channels, users, users_shape, blueprint_ids, existing_roots)
    print(f"Created {new_count} synthetic threads; preserved {len(existing_roots)} original sample threads")
    print(f"Total Slack roots: {len(blueprint_ids)}; reply messages: {total_replies}")
    print(f"Channel fixtures: {len(channels)}; users: {len(users)}")
    print(f"Output: {OUTPUT.relative_to(ROOT)}")
    print("PASS: original fixtures untouched; evaluation labels excluded from Slack data")


if __name__ == "__main__":
    main()
