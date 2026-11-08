"""Milestone 4: bounded Agent 3 Advisor pilot over selected handoff topics.

Per topic: freshness-checked retrieval (current guidance first) -> Advisor draft ->
targeted follow-up retrieval for the gaps the draft names -> at most one revision ->
deterministic checks (structure, severity binding to the unchanged rubric, temporal
priority) -> conditional shallow ToT -> ONE final semantic grounding call over every
statement that can reach the card (claims, summary, action, severity rationale/signals,
affected reporters, member resolution, announcement handling) and over the ToT
alternatives -> authorization (only SUPPORTED statements reach the card; a withheld draft action
may be replaced by an already-reviewed ToT candidate that passed the same checks) -> deterministic
card routing. Nothing after the final grounding call can add or change a statement. Card prose
refers to people by role; models see canonical IDs and roles, never display names.

Every model and retrieval call is charged to a finite budget, and draft, revision and ToT
each run only if a call stays reserved for the final grounding. Nothing is retried: the
live client runs each stage as a CrewAI Task for a role-specific Agent (researcher,
alternatives analyst, grounding verifier) and sends at most one HTTP request per stage
(enforced at the transport, including CrewAI's forced-final-answer and rate-limit retries);
a failed stage is recorded while the topic's members and obligations still reach a card.
The model never calls tools itself: it names gaps and follow-up queries, and
ResearchTools executes them within the budget.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse

from pydantic import ValidationError

from threadsense.agents import advisor_research, advisor_tot, flag_impact as impact
from threadsense.agents.advice_contracts import ModelReviewItem, stable_id
from threadsense.agents.advice_inputs import coverage, load_effective_view, review_items_from_view
from threadsense.agents.advisor_checks import (
    action_issues, agent1_resolution, announcement_issues, assemble_card, authorize, build_severity, claim_issues,
    coverage_issues, dependencies, established, governing_sources, grounding_result, inherited_flags, normalize,
    presentation_issues, rejected_statements, sendable, statements, structural_issues, temporal_check, unauthorized,
)
from threadsense.agents.advisor_contracts import AdvisorDraft, GroundingJudgment, GroundingJudgmentV7
from threadsense.agents.advisor_evidence import (
    EVIDENCE_VIEW_VERSION, Budget, BudgetExhausted, ResearchTools, member_messages, model_view, open_retriever,
)
from threadsense.agents.flag_provenance import FlagSource
from threadsense.handoff_inputs import ROOT, file_hash, read_json
from threadsense.retrieval.config import DEFAULTS
from threadsense.severity_rubric import load_rubric

PILOT_VERSION = 'agent3-advisor-pilot-v8'  # v8: author-count scope, temporal eligibility of agreeing current sources and
# documentation-status findings, partially pending grounding (v7: AdviceCard v4 (details, next_step) from draft v11).
# Prompt text version, recorded in every manifest with the rule fingerprints. v6: team lead-facing writing guide and two
# STYLE ONLY examples in the draft/revision rules; display-text rules in grounding and ToT; rules sent once per request
# (agent3_readability_v1 ran v6). v6.1: grounding also receives the open upstream review flags (open_review_flags).
# v10: summary written as independently judged sentences (draft v9), each condensing named claims; a sentence that
# groups several people states only what each of them said. v11: compact evidence view (EVIDENCE_VIEW_VERSION) with
# verified authorship separate from authority; actions keep recommendation, destination and premises apart (a named
# destination needs its own support); summary facts with different evidence get their own sentences (up to 3); the
# revision omits the STYLE ONLY examples; output schemas are sent without their generated titles. v12: a request or
# question by anyone but a team lead (instruction_authority NONE) is an INCIDENT_FACT naming the requester, never a
# THREAD_INSTRUCTION (evidence view v3). v13 (draft v10): SOURCE_FACT describes a retrieved source without granting it
# authority; an announcement governs only what it directs; action premises are what instruction, draft and scope note
# rely on, while context only the rationale draws on goes in context_claim_ids (judged with the rationale).
# v14: one recipient/route rule (ROUTING_RULE), sent verbatim to draft, revision and grounding: a functional recipient
# is justified by incident evidence and the expertise needed, without intake-route evidence; a concrete route, or a
# claim that one is designated or mandatory, needs its own premise (agent3_source_fact_v1 withheld "report to
# engineering" for lacking an established route).
# v15 (writing guide only; grounding rules, evidence view and schemas unchanged, so recorded grounding verdicts still
# replay): review_note covers only a check the card does not already list (the card itself adds high severity, the open
# upstream flags with their count, withheld statements and the open question; agent3_recipient_routing_v1 restated the
# open flags); a draft covering several reports groups them by shared symptom with counts and roles instead of a
# sequence of "another tutor reports ..." clauses, keeping each task reference with its report and every distinct
# symptom with the roles that reported it.
# v16 (writing guide only, after agent3_writing_eval_v15_v1; grounding rules, evidence view and schemas unchanged): a
# draft the team lead posts is in their voice, addressed to its recipients, without third-person references to the team
# lead or steps only the team lead takes; policy wording only when it helps recipients act, at the strength and scope of
# its governing source, which is listed among the premises (a participant's explanation is attributed, not stated as a
# rule); requests stay with the threads and tasks where they were made; no commentary on an unnamed delivery route the
# action does not depend on. The source audit found the v15 tie draft's policy wording quoted from the current
# instructions ("Ties"), so the final grounding standard was not changed.
# v17 (writing guide only; grounding unchanged): plain wording covers severity.rationale and rubric-signal support too,
# with familiar substitutes when they keep the meaning, exact quotes, and no processing phrases ("supplied batch context").
# v18 (draft v11, AdviceCard v4): two presentation levels. The summary is the closed card (situation and the open point,
# about 35-55 words); detail_sentences are the opened card's "What happened", each judged like a summary sentence
# (DETAIL); the instruction targets about 15-25 words; the rationale says why the step fits (no incident retelling, no
# recipient instructions); a NO_ACTION reason is judged (NO_ACTION_RATIONALE, non-blocking); a diagnostic request is
# stated once where it serves its purpose. Grounding rules gain the two statement kinds, so verdicts recorded under
# earlier grounding rules are not reused in replay.
PROMPT_VERSION = 'agent3-advisor-prompts-v18'
# Replayed recorded drafts older than v7 are read under the last contract they satisfy (no intervention_need).
LEGACY_LABELS = {'AdvisorDraft': 'agent3-advisor-draft-v6', 'ToTComparison': 'agent3-tot-comparison-v2',
                 'GroundingJudgment': 'agent3-grounding-judgment-v4'}
SCENARIOS = ROOT/'data/evaluation/agent3_pilot_scenarios.json'
HANDOFF = ROOT/'data/processed/agent2_handoff_v2_projection'
# Per topic: draft + one revision + one ToT + final grounding = 4 model calls at most, the last always
# reserved for grounding; retrieval: initial + supersession check + 3 follow-ups = 5 (one spare).
# Run totals cap 7 scenarios.
BUDGET = {'model_calls_per_topic': 4, 'model_calls_total': 28, 'retrieval_calls_per_topic': 6, 'retrieval_calls_total': 42}
MAX_FOLLOW_UPS = 3
TOP_K = 5
# Live request limits (CrewAIClient): one HTTP request per stage, no SDK retries, bounded input and output.
MAX_COMPLETION_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 120
HTTP_REQUESTS_PER_STAGE = 1
INPUT_TOKEN_LIMIT = 24_000  # Checked on the exact request body before sending (o200k); the provider's count is recorded.
# Set before CrewAI/LiteLLM import: no telemetry export, no remote model-price download.
QUIET_ENV = {'CREWAI_DISABLE_TELEMETRY': 'true', 'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
             'CREWAI_TRACING_ENABLED': 'false', 'LANGSMITH_TRACING': 'false', 'LANGCHAIN_TRACING_V2': 'false'}

ROUTING_RULE = (
    'Recipients and routes: keep apart what an action recommends, the functional recipient it proposes (engineering, a '
    'specialist, a QA reviewer) and any concrete route it names (a specific thread, channel, person or queue it goes to '
    'or through). A proposed functional recipient is justified by supported incident evidence showing a problem that '
    'needs that recipient\'s expertise; evidence of an established intake route is not required, and mentioning the '
    'recipient justifies nothing by itself. A concrete route, or a claim that a route is designated, official or '
    'mandatory, is a claim of its own and needs a premise whose evidence establishes it; an example-collection or '
    'status note asks people where to post examples and does not make that thread an intake route. The recommendation '
    'stays advisory (the team lead decides; it need not be shown to be the required or only next step): when no '
    'evidence names the concrete route, leave it unspecified ("report it to engineering") rather than choosing one.')
DRAFT_RULES = (
    'You are the ThreadSense Advisor preparing one topic for a team lead\'s morning brief. Use only the evidence '
    'provided and cite it by evidence_id. Member messages (origin member_message, with canonical author_id, author_role, '
    'thread_starter_id/thread_starter_role and reactions) are the only evidence for what members report. People: refer '
    'to them by role, never by name ("a tutor", "a QA tutor", "the team lead", "an engineer", "the thread starter"), in '
    'every summary, claim, rationale and action. Use singular wording for one person; plural wording ("three tutors '
    'report") only when that many distinct authors are cited. In each claim, list in attributions whom the role wording '
    'refers to (user_id, relation, cited evidence_id): AUTHOR wrote the cited message (reports, asks, confirms, '
    'instructs), THREAD_STARTER started that message\'s thread, PARTICIPANT only for a claim that the person took part '
    'in the thread. Quotations are copied unchanged. INCIDENT_FACT claims state what members report ("a tutor reports '
    '..."), never a verified cause; a CAUSE claim needs a retrieved record or a team lead or engineer message that '
    'verifies it. A team lead\'s instruction inside a member thread is a THREAD_INSTRUCTION claim citing that message: it '
    'applies to that thread\'s scope and is not project guidance. A request or question from anyone else (member '
    'messages with instruction_authority NONE: an engineer, QA tutor or tutor) is an INCIDENT_FACT naming who asked '
    '("an engineer asks for the error state on task X"): a reported request with no authority; it may still be a premise. '
    'Retrieved sources '
    'support guidance and history according to their "use": CURRENT_GUIDANCE may support what applies now; '
    'ENACTED_DECISION is a team lead decision whose enactment as policy is on record: it may support what applies now '
    'within its recorded scope, and its status line names the governing source (cite that announcement or guideline '
    'too when it is in the evidence); '
    'PRIOR_DECISION and HISTORY_ONLY explain earlier decisions, outcomes or old rules and must not be presented as current '
    'guidance (an approved, posted or executed decision is still a prior record unless its use is ENACTED_DECISION); '
    'withdrawn guidance has no replacement and does not apply; UNRESOLVED_VERSION must not be resolved by you. ANNOUNCEMENT items include routine reminders, schedules '
    'and example-collection notes: before a GUIDANCE claim relies on one, list it in announcement_assessments as relevant '
    '(same project, batch and problem) and directive (it tells people what to do), quoting the directing sentence '
    'verbatim; otherwise mark it not relevant or not directive. An announcement governs only what it directs: a request '
    'to post examples in a thread governs where examples go, not escalation or an engineering route. To say what any '
    'retrieved source says without relying on it as current handling, write a SOURCE_FACT claim citing it ("the batch '
    'announcement asks for examples in its thread"); it keeps the source\'s status and dates and establishes no '
    'procedure, authority or destination. Read each excerpt with its status line, dates, scope, '
    'authority, authorship and recorded states. Authorship is separate from authority: authorship.author_id is the '
    'verified author (a Slack record\'s message author); author_id absent with verified false means the record names '
    'no author, and its authority actor (actor_relation RECORD_AUTHORITY) approved, decided or recorded it without '
    'being its author. Write "the earlier handoff records ..." rather than naming who wrote it, and list an AUTHOR '
    'attribution for a retrieved record only when its authorship is verified. A quote with quote_kind VERBATIM must be copied exactly from one cited excerpt; '
    'otherwise set quote_kind PARAPHRASE. '
    'Coverage: before advising, fill coverage for CURRENT_GUIDANCE, ANNOUNCEMENTS, PRIOR_DECISIONS (earlier decisions, '
    'trials and their outcomes) and MEMBER_QUESTIONS (what members asked, including references to earlier workarounds or '
    'discussions). COVERED cites the evidence; NOT_APPLICABLE says why none is needed; MISSING names a gap whose '
    'follow_up query (source_types; version_mode history for past decisions, outcomes, recurrence or supersession) '
    'could find it. Request follow-ups only for support your advice actually needs; a nonempty result list is not '
    'sufficient evidence. Do not invent causes, outcomes, approvals, counts or fixes. '
    'Action: when the evidence supports a concrete step (post or align on current guidance, escalate, route to a '
    'specialist, update documentation), propose it with support_claim_ids naming its premises: the claims the instruction, draft and scope note rely '
    'on, including any destination or condition (a judge will decide which are essential); claims only the rationale '
    'draws on (why another route or source does not apply, background) go in context_claim_ids; it may be '
    'proposed even '
    'though the card will need team lead review. ' + ROUTING_RULE + ' Any action other than NO_ACTION states intervention_need: the kind '
    '(UNRESOLVED_HANDLING_QUESTION, GUIDANCE_GAP, APPLICABLE_PENDING_DECISION or OPERATIONAL_PROBLEM), one sentence on '
    'why intervening now is needed, and the evidence that shows it. Infer the need from what the threads and records '
    'show, not from keywords; nobody has to ask for intervention or say work is blocked. Handling questions that a team '
    'lead or QA tutor already answered in the thread are not unresolved; repeated questions across threads that still '
    'lack an answer, or answers that disagree, can be. Existing guidance does not by itself mean NO_ACTION, and "a '
    'reminder might help" is not a need. If the evidence shows no such need (for example an observation the team lead '
    'already handled or deliberately kept open), propose NO_ACTION. That a team lead approves or executes the action is not an open '
    'question. Set open_confirmation OPEN only for a specific question that the cited guidance and decisions leave '
    'unsettled, state it in open_question, and cite in open_question_evidence_ids the evidence showing it is unsettled; '
    'otherwise NONE. It must be a handling or policy question the team lead has to decide or confirm (for example which '
    'of two current rules applies, or whether an earlier decision covers these cases). A technical cause not yet '
    'diagnosed, diagnostic results not yet collected, an expert\'s assessment not yet given, generic uncertainty, and '
    'earlier review flags (already carried with the card) are not open confirmations. A confirmation that current '
    'guidance assigns to the team lead is one once its required inputs are available; while inputs the team lead '
    'requested are still missing, say so instead. action_choice: fill it only when the evidence leaves a real choice '
    'between intervening and observing, or between materially different interventions (e.g. a reminder versus an '
    'escalation): name the competing action types and the tradeoff the evidence does not settle, citing it. Imagining '
    'an alternative, an earlier review flag, or a root cause nobody knows yet is not such a choice; otherwise null. Severity: apply the rubric unchanged; MEDIUM or HIGH must cite a rubric signal by level, index and '
    'exact text, supported by member messages; affected_reporters lists only people whose own message (cite that '
    'message) reports being affected, not everyone who replied. recurrence FOUND means historical recurrence '
    'corroborated by retrieved records (cite them in recurrence_evidence_ids); members saying it is happening again go '
    'in reported_recurrence_evidence_ids, which is a report, not corroborated history. Resolution: give each member a state (UNRESOLVED, '
    'PARTIALLY_RESOLVED, RESOLVED_IN_THREAD or UNKNOWN) from that member\'s own complete thread, citing the messages '
    'that show it; Agent 1\'s resolution label is an attributed input, often unverified, and is not evidence; one '
    'member\'s resolution says nothing about another member. UPDATE_DOCUMENTATION and UPDATE_FAQ name targets '
    '(evidence_id, section, ADD for a missing entry, CORRECT or REMOVE for stale wording); target only what the evidence '
    'shows is missing or stale. Severity, confidence, resolution and evidence sufficiency are separate judgments. List '
    'source_conflicts between evidence items that disagree. If no evidence addresses the topic, set evidence_sufficiency '
    'UNSUPPORTED and propose no operational action. Upstream review flags stay open; you cannot clear them. Everything '
    'that reaches the card is checked statement by statement against the full topic context.')
WRITING_GUIDE = (
    'Card writing. The team lead reads these fields exactly as you write them. A card has two levels: closed, it shows '
    'the summary and the action\'s instruction; opened, it adds the detail sentences, the rationale, the draft and what to '
    'check. Give each field one purpose. summary_sentences (the closed card: the situation and the important point that '
    'is still open or already settled, usually two sentences and about 35-55 words in all, up to 3 sentences when facts '
    'with different evidence need them; leave summary null: it is their text joined); leave reporter-by-reporter '
    'breakdowns, policy explanations and earlier records to detail_sentences unless the situation cannot be understood '
    'without them. detail_sentences (the opened card\'s "What happened", up to 6 short sentences; empty when the summary '
    'already says everything useful): the distinct symptoms with the roles and counts that reported each and their task '
    'references or threads; the requests already made (who asked, in which threads) and the information still missing; '
    'earlier records, described as earlier records and kept apart from current reports. Do not repeat a summary sentence '
    'or list every message. Each summary and detail sentence is judged and shown on its own, so make each one complete; '
    'list the claims it condenses in support_claim_ids and the earlier sentences it refers back to ("this", "their '
    'questions"): depends_on gives positions (1, 2, ...) of earlier sentences at the same level, and summary_depends_on '
    '(detail sentences only) positions of summary sentences. A sentence says nothing its claims do not support, and one unsupported part withholds the whole sentence: give facts '
    'with different evidence their own sentences (what members report; current handling or what the team lead has '
    'asked for; what earlier records show) rather than joining unrelated facts to stay within two sentences. A sentence whose subject is several people ("three tutors ask ...") states only what '
    'each of them asked or reported: when their questions or reports differ, say how ("a QA tutor asks X; two others '
    'ask Y") or use wording that covers each one, as the claims do. proposed_action.instruction (one concrete sentence telling the '
    'team lead what to do, about 15-25 words); proposed_action.rationale (why the evidence and the applicable guidance '
    'make this step fit, 1-2 short sentences, judged and shown on its own; do not retell the incident, which belongs in '
    'detail_sentences, or give instructions to recipients, which belong in the draft; for NO_ACTION, say why no further '
    'intervention is needed now, from the evidence; the reason is judged and shown only if supported); '
    'proposed_action.scope_note (only conditions and limits the action depends on); proposed_action.draft_text (a copyable draft suited '
    'to the action: an announcement of about 60-120 words, with bullets when useful, or the message to send for an '
    'escalation or referral; when it covers several reports, group them by the symptom they share, with counts and '
    'roles ("two tutors and a QA tutor report a grey Submit button after choosing B; a tutor reports that clicking Submit '
    'does nothing on RP-1577"), rather than one "another tutor reports ..." clause per report: group only reports whose '
    'cited messages state that symptom, keep each task reference with its own report, and keep every distinct symptom '
    'and who reported it); review_note (only for a specific check the team lead still has to make that the card does '
    'not already list, and which threads or sources it concerns, for example requested details that are still missing; '
    'the card itself lists high severity, the open upstream review flags and their count, withheld statements and the '
    'open question, so do not restate those; otherwise null). State a diagnostic request or a missing detail once, where '
    'it serves its purpose (what is still missing in detail_sentences, what recipients should provide in the draft); '
    'repeat it in the instruction, rationale, scope note or review note only when that field needs it for a different '
    'purpose. A draft the team lead will post is in the team lead\'s own '
    'voice and addressed to its recipients: tell them what to provide or do; do not refer to the team lead in the third '
    'person or include steps only the team lead takes (those belong in the instruction). Put policy wording in a draft '
    'only when it helps the recipients act, and then at the strength and scope of the governing source it comes from '
    '(keep its conditions, exceptions and words such as "usually" or "can"), listing that source\'s claim among the '
    'action\'s premises; a participant\'s explanation or suggestion may be attributed to them ("a QA tutor suggests '
    '...") but is not stated as a rule unless a current guideline, FAQ or established announcement states it. Keep '
    'requests apart by who made them and where: a request made in specific threads or about specific tasks stays with '
    'those threads and tasks, separate from a request the team lead made in every thread. When no evidence names a '
    'delivery route and the action does not depend on one, leave the route unspecified without commenting on its '
    'absence in any of these fields. These are writing targets, not limits: keep necessary conditions, uncertainty, scope and who reported, asked, '
    'confirmed or instructed. Plain wording applies to every field the team lead reads, including severity.rationale '
    'and each rubric signal\'s support: prefer familiar words when they keep the meaning ("prompt requirements" for '
    '"prompt constraints", "compare the QA decisions" for "calibrate", "change how ties are judged" for "change the tie '
    'threshold"), keep a project term when a plainer one would change its meaning, quote sources exactly, and leave out '
    'processing phrases such as "in the supplied batch context" or "inferred from the topic\'s member entries". '
    'Use familiar words: "post a reminder", not "post alignment"; "report a technical issue", not '
    '"tool-incident reporting". Never put evidence IDs, claim IDs, user IDs, field or enum names, rubric references, '
    'premise lists or processing details in these fields or in claim text; the evidence mapping belongs in evidence_ids, '
    'support_claim_ids, attributions and targets. Use double quotation marks only for exact quotations copied unchanged '
    'from a cited source. Not every topic needs an announcement, or any action. Summaries and claims keep apart: what '
    'several reporters have in common versus a symptom only some of them report ("three tutors report X; one also '
    'reports Y"); a member asking a question versus a member reporting being affected; and a reported symptom versus a '
    'confirmed finding. Attribute each detail only to the roles whose cited messages state it. When research found nothing, say what '
    'this run retrieved ("the records retrieved for this run do not show ..."); never state that no record, decision '
    'or outcome exists anywhere.')
STYLE_EXAMPLES = (
    'STYLE EXAMPLES - STYLE ONLY, NOT EVIDENCE. Both are fictional and outside every project here: never copy their facts, '
    'counts, policies, wording or actions into a real card. Excerpts of the display fields only; a real draft also carries '
    'claims, evidence_ids, support_claim_ids, attributions, severity, coverage and resolution. '
    'Example 1 (fictional image-captioning batch). Supplied facts: two annotators ask whether captions should include '
    'watermark text; the current captioning guideline says to omit watermarks unless the watermark is the subject of the '
    'image. Selected action: post a reminder. summary_sentences: "Two annotators asked whether captions should include '
    'watermark text." (condenses the two annotators\' question claim), "The current guideline already answers this." '
    '(condenses the guidance claim; depends on sentence 1). proposed_action.instruction: "Post a reminder in the batch channel '
    'that captions leave out watermark text unless the watermark is the subject of the image." proposed_action.rationale: '
    '"Both questions are answered by the current guideline; one reminder gives everyone the same rule before more '
    'captions are submitted." proposed_action.draft_text: "Reminder for this batch: leave watermark text out of captions. '
    '- Exception: describe the watermark when it is the main subject of the image. - If you are unsure, ask in this thread '
    'before submitting. This follows the current captioning guideline; nothing else has changed." review_note: null. '
    'Example 1 detail_sentences: [] (the summary already says everything useful). '
    'Example 2 (fictional video-timestamp batch). Supplied facts: three annotators report that timestamps move by about one '
    'second after saving, two of them on VID-101 and VID-117 and one only after reopening a saved task; an engineer asked '
    'for task IDs; no cause is confirmed. Selected action: report a technical issue to engineering. summary_sentences: '
    '"Three annotators report that timestamps move after saving.", "The cause is not confirmed." (depends on sentence 1). '
    'detail_sentences: "Two annotators report a one-second shift on VID-101 and VID-117; a third sees it only after '
    'reopening a saved task." (condenses the three report claims), "An engineer asked for the affected task IDs; steps '
    'that reproduce the shift have not been posted." (condenses the request claim). '
    'proposed_action.instruction: "Report a technical issue to engineering with the affected task IDs and the steps that '
    'reproduce the shift." proposed_action.rationale: "Engineering asked for task IDs; one report with reproduction steps '
    'lets them check the save step without each annotator filing separately." proposed_action.draft_text: "Timestamps '
    'move after saving (three reports in this batch). After saving, timestamps shift by about one second. Tasks: VID-101, '
    'VID-117, VID-142. Steps: open the task, set a timestamp, save, reopen. The cause is not confirmed; please check the '
    'save step." review_note: "Confirm with engineering whether tasks saved before the fix need to be re-checked."')
RESEARCH_RULES = DRAFT_RULES
DRAFT_RULES = f'{RESEARCH_RULES} {WRITING_GUIDE} {STYLE_EXAMPLES}'
# The revision keeps every rule and the full writing guide; it omits only the STYLE ONLY examples (no constraints, and
# the previous draft already shows the card's style).
REVISION_RULES = (
    'Revise your previous draft once, using the follow-up retrieval results now included in the evidence. Keep every '
    'claim cited; weaken or remove claims the evidence does not support. No further retrieval will run: leave remaining '
    f'gaps with follow_up null. {RESEARCH_RULES} {WRITING_GUIDE}')
# Opt-in adaptive research only (advise(research_mode='react')); not part of the production prompts or fingerprints.
REACT_REVISION_RULES = (
    'Revise your previous draft once, using the follow-up retrieval results now included in the evidence. Keep every '
    'claim cited; weaken or remove claims the evidence does not support. If the new evidence leaves one named gap open '
    'and points to where its answer could be (for example an approval whose outcome is not in the evidence), you may '
    'request ONE more search: set follow_up on that gap only, and write its query from what the new evidence shows (its '
    'title, dates, scope or recorded states). Leave every other follow_up null. Your draft must be complete either way: '
    f'the search may not run. {RESEARCH_RULES} {WRITING_GUIDE}')
GROUNDING_RULES = (
    'Judge each statement against the evidence it cites, read within the full context provided: every message of every '
    'member thread (with canonical author IDs, roles, thread starters and reactions) and every retrieved source for '
    'this topic. Citing a source '
    'is not support. A statement is SUPPORTED only if its cited evidence states or directly entails it and nothing in '
    'the context contradicts it; PARTIALLY_SUPPORTED if a material part is missing or the context qualifies it; '
    'UNSUPPORTED otherwise. A status line marking an excerpt historical, unresolved or a prior record means it cannot '
    'support what applies now. By kind: CLAIM_INCIDENT_FACT is a report of what members say, not a verified cause; '
    'CLAIM_SOURCE_FACT is SUPPORTED if the cited source says it, described with its status and dates; it establishes no '
    'current handling, procedure or destination; '
    'CLAIM_CAUSE needs verification in the cited evidence; a Verbatim quote must match its source, a Paraphrase must '
    'preserve the meaning. Prose names no one: role wording ("the team lead instructs", "a tutor reports") must match the '
    'cited author\'s role and act (reported, asked, confirmed or instructed), plural wording needs that many distinct '
    'cited authors, and listed attributions must hold (AUTHOR wrote the cited message, THREAD_STARTER started its '
    'thread, PARTICIPANT posted in it). A retrieved record\'s authorship is separate from its authority: an approver or '
    'recorder (actor_relation RECORD_AUTHORITY) is not its author, and a record whose authorship is not verified names '
    'no author. SUMMARY and SEVERITY_RATIONALE must follow '
    'from the evidence with no added cause, count or outcome. A SUMMARY sentence (statement_id summary:s1, summary:s2, '
    '...) is judged on its own and shown only if SUPPORTED; its attributions name the people its role wording refers '
    'to, and wording that groups several people is SUPPORTED only if what it says they asked or reported is stated in '
    'each of their cited messages. A SUMMARY sentence with depends_on is read after the sentences it lists (for words '
    'such as "this" or "their"), but judged only on what it adds. A DETAIL sentence (statement_id detail:d1, detail:d2, ...) is shown when the card is '
    'opened and is judged exactly like a SUMMARY sentence: on its own, shown only if SUPPORTED, read after the sentences '
    'in its depends_on but judged only on what it adds. NO_ACTION_RATIONALE is the advisor\'s reason for proposing no '
    'further intervention now: SUPPORTED only if the cited evidence shows that reason and the context shows no unresolved '
    'handling question, guidance gap, applicable pending decision or operational problem that needs coordination; '
    'existing guidance does not by itself establish that no action is needed. ACTION and ALTERNATIVE are recommendations: judge whether '
    'their premises are supported, whether the action applies to this topic and whether the rationale follows; a source '
    'need not literally prescribe the action. ' + ROUTING_RULE + ' Judge a proposed recipient the same way in ACTION, '
    'ALTERNATIVE, INTERVENTION_NEED, ACTION_RATIONALE and REVIEW_NOTE: on whether the incident evidence shows a problem '
    'that needs that recipient\'s expertise, never on whether an intake route is on record; a statement that proposes a '
    'recipient and leaves the concrete route unspecified is not PARTIALLY_SUPPORTED, UNSUPPORTED or insufficient for '
    'that reason. ACTION and operational ALTERNATIVE statements list their premises: '
    'PENDING_YOUR_VERDICT premises are judged here and are provisional, not final; REJECTED ones failed deterministic '
    'checks and support nothing; a premise with depends_on stands only if every ANNOUNCEMENT_HANDLING statement it lists '
    'is also SUPPORTED. ACTION_CHOICE is SUPPORTED only if the cited evidence really leaves that choice between the named '
    'actions open (not merely an imagined alternative, a review flag or an unknown cause). INTERVENTION_NEED says why intervening now is needed: SUPPORTED only if the context shows that '
    'reason (an unresolved handling question, a guidance gap, an applicable pending decision, or an operational problem '
    'that needs coordination). Questions already answered in their threads are not unresolved; a general benefit ("a '
    'reminder might help") is not a need; existing guidance does not by itself rule a need out. Judge in this order: (1) announcement handling; (2) each premise\'s final status, which is your '
    'verdict on it combined with its dependencies; (3) sufficiency. Fill action_sufficiency for the ACTION and one '
    'alternative_sufficiency entry (with its statement_id) for each ALTERNATIVE that lists premises: SUFFICIENT only if '
    'premises whose final status is SUPPORTED justify the exact text as worded, including its conditions and scope; '
    'essential_statement_ids lists the premises it cannot stand without (each must have final status SUPPORTED); '
    'INSUFFICIENT if its exact text relies on a rejected, unsupported or dependency-voided premise or goes beyond its '
    'premises; a listed premise the text does not rely on is not essential, and its failure alone does not make the '
    'action insufficient. ACTION_RATIONALE is judged separately and may also cite context claims; '
    'action_sufficiency null if no ACTION statement is sent. SOURCE_AGREEMENT is SUPPORTED only if the named current '
    'sources say the same thing on the point in conflict and only the superseded material differs. A request by anyone but a team lead is a CLAIM_INCIDENT_FACT: SUPPORTED '
    'if that person asked it, and it carries no authority. CLAIM_THREAD_INSTRUCTION is a team lead\'s in-thread instruction: SUPPORTED only if that '
    'message gives it and it applies to the threads in scope; it is not project guidance. HISTORICAL_RECURRENCE needs '
    'retrieved records of earlier occurrences; REPORTED_RECURRENCE only needs members saying it is happening again. AFFECTED_REPORTER needs that person\'s own message reporting that they are '
    'affected. RESOLUTION is judged against the member\'s complete thread, including messages the statement did not '
    'cite. ANNOUNCEMENT_HANDLING needs the announcement to give that directive for this topic\'s project, batch and '
    'problem, and it governs only what it directs (a request to post examples governs where examples go, not '
    'escalation or an intake route); a routine reminder or schedule directs nothing for the topic. OPEN_QUESTION is SUPPORTED only if the '
    'guidance and decisions in the context really leave that specific question unsettled and it is a handling or policy '
    'question for the team lead; a not-yet-diagnosed cause, pending diagnostic results or a pending expert assessment is '
    'not one. Return exactly one verdict '
    'for every statement_id. The team lead reads SUMMARY, DETAIL, ACTION (label, instruction, draft to copy, scope and '
    'changes), ACTION_RATIONALE, NO_ACTION_RATIONALE, REVIEW_NOTE and OPEN_QUESTION exactly as written: judge that exact text, including its '
    'conditions, uncertainty, scope and who reported, asked, confirmed or instructed; plain wording is expected, but it '
    'must not overstate the evidence. A quoted passage must match its source exactly. open_review_flags lists the '
    'upstream review obligations still open on these threads; a REVIEW_NOTE may rely on them. '
    'Source consistency (always fill source_consistency, even when the draft declares no conflict): compare the '
    'governing_sources that address the handling question of this topic with each other, independently of the draft. List '
    'sources that state the same rule as AGREE, and sources that state different rules for the same cases as CONFLICT '
    'with the point and disagreement_scope (which cases, batch or section differ). assessed_evidence_ids lists the '
    'governing sources you compared; relations may be empty when they address different points. Only governing sources '
    'count: historical, superseded, expired or withdrawn material, prior records and member messages are not current '
    'sources, an announcement governs only if it directs handling for this topic, and members disagreeing with each '
    'other is not a source conflict. For each entry in declared_conflicts give one declared_conflict_checks entry: '
    'CONFIRMED (the cited sources state different rules on that point), SOURCES_AGREE (they say the same thing; only '
    'wording or detail differs) or UNDETERMINED.')


class ScenarioError(ValueError):
    """A selected topic is not available in the handoff as specified (recorded, never repaired)."""


class RequestCeilingExceeded(RuntimeError):
    """A stage tried to send more HTTP requests than its ceiling; the extra request was not sent."""


class RunStateError(RuntimeError):
    """A caller's run state (budget, ledger) could not be recorded; never treated as a stage failure."""


class BoundaryNotObserved(RuntimeError):
    """A model call returned without any request passing the guarded transport; call accounting is unverified."""


class InputLimitExceeded(RuntimeError):
    """The request would exceed the per-request input-token limit; it was not sent."""


class OutputLimitReached(RuntimeError):
    """The provider stopped at the output-token limit (finish_reason length); the reply is not used."""


class CostBudgetExceeded(RuntimeError):
    """Reserving this request's maximum cost would exceed the application budget; it was not sent."""


class RecordedFailure(RuntimeError):
    """Replay: the recorded run's stage failed; replayed with its recorded failure class (nothing is generated)."""

    def __init__(self, failure_class, message):
        super().__init__(message)
        self.failure_class = failure_class


class ProviderConfigurationError(RuntimeError):
    """The provider rejected the request configuration (4xx other than rate limit or context length)."""


# One CrewAI Agent per role; every stage runs as one Task for its role's Agent.
STAGE_AGENTS = {
    'researcher': ('ThreadSense Advisor researcher',
                   'Prepare one evidence-cited advice draft for a team lead and name the research it still needs.',
                   'You research annotation-project guidance, decisions, announcements and member threads, and you never '
                   'go beyond the evidence provided.'),
    'analyst': ('ThreadSense alternatives analyst', 'Compare two or three candidate actions on evidence, applicability '
                'and severity fit.', 'You weigh options for a team lead without inventing evidence or clearing review flags.'),
    'verifier': ('ThreadSense grounding verifier', 'Judge every statement against the full topic context and decide '
                 'whether the passed premises justify the exact proposed action.',
                 'You verify independently of the drafting agent; you judge and never repair.'),
}
STAGE_ROLE = {'draft': 'researcher', 'revision': 'researcher', 'tot': 'analyst', 'grounding': 'verifier'}


class CostLedger:
    """Application budget across a whole experiment. Before each request its conservative maximum cost (input-token
    limit and output limit at list prices) is reserved; after it, the reservation is settled at the provider-reported
    usage, or kept in full when usage is unknown (failed request)."""

    def __init__(self, limit_usd):
        self.limit_usd, self.spent_usd, self.reserved_usd, self.entries = limit_usd, 0.0, 0.0, []

    def reserve(self, prices, input_tokens, output_tokens, label):
        maximum = input_tokens * prices['input'] + output_tokens * prices['output']
        if self.spent_usd + self.reserved_usd + maximum > self.limit_usd + 1e-12:
            raise CostBudgetExceeded(f'{label}: reserving ${maximum:.4f} would exceed ${self.limit_usd:.2f} '
                                     f'(spent ${self.spent_usd:.4f}, reserved ${self.reserved_usd:.4f})')
        self.reserved_usd += maximum
        return maximum

    def settle(self, reservation, prices, usage, label, sent=True):
        if not sent:
            cost, basis = 0.0, 'not sent'
        elif usage:
            cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens') or 0
            cost = ((usage.get('prompt_tokens', 0) - cached) * prices['input'] + cached * prices.get('cached_input', prices['input'])
                    + usage.get('completion_tokens', 0) * prices['output'])
            basis = 'provider usage'
        else:
            cost, basis = reservation, 'usage unknown: full reservation charged'
        self.reserved_usd -= reservation
        self.spent_usd += cost
        self.entries.append({'label': label, 'reserved_usd': round(reservation, 6), 'charged_usd': round(cost, 6), 'basis': basis})
        return cost

    def summary(self):
        return {'limit_usd': self.limit_usd, 'spent_usd': round(self.spent_usd, 6), 'reserved_usd': round(self.reserved_usd, 6),
                'requests': self.entries}


def model_prices(model):
    """List prices per token from LiteLLM's bundled (local) cost map; never fetched remotely."""
    import litellm
    entry = litellm.model_cost.get(model.split('/', 1)[-1]) or litellm.model_cost.get(model)
    if not entry or entry.get('input_cost_per_token') is None:
        raise ValueError(f'No local price for {model}; refusing to run without a cost bound.')
    return {'input': entry['input_cost_per_token'], 'output': entry['output_cost_per_token'],
            'cached_input': entry.get('cache_read_input_token_cost') or entry['input_cost_per_token'],
            'source': f"litellm {__import__('importlib.metadata').metadata.version('litellm')} local model_cost map"}


def estimate_tokens(text):
    import tiktoken
    return len(tiktoken.get_encoding('o200k_base').encode(text))


class RequestGuard:
    """Count HTTP requests at the httpx transport for one stage and refuse any beyond `limit` before it is
    sent, whichever layer (CrewAI rate-limit retry, LiteLLM, provider SDK) attempts it. Single-threaded use."""

    def __init__(self, limit=HTTP_REQUESTS_PER_STAGE, input_token_limit=None):
        self.limit, self.input_token_limit, self.sent, self.blocked, self.responses = limit, input_token_limit, [], [], []
        self.refused, self.input_tokens, self.sent_text = None, None, None

    def __enter__(self):
        import httpx
        self._original, guard = httpx.HTTPTransport.handle_request, self

        def handle(transport, request):
            if len(guard.sent) >= guard.limit:
                guard.blocked.append(str(request.url))
                raise RequestCeilingExceeded(f'{guard.limit} HTTP request(s) per stage; {request.url} was not sent')
            messages = json.loads(request.content or b'{}').get('messages') or []
            # The message text as it leaves the process (request-boundary record of what the model was given).
            guard.sent_text = '\n'.join(m['content'] if isinstance(m.get('content'), str) else json.dumps(m.get('content'))
                                        for m in messages)
            if guard.input_token_limit:  # The exact body about to be sent, framework prompt included.
                guard.input_tokens = sum(estimate_tokens(m.get('content') if isinstance(m.get('content'), str)
                                                         else json.dumps(m.get('content'))) + 8 for m in messages)
                if guard.input_tokens > guard.input_token_limit:
                    guard.refused = f'{guard.input_tokens} input tokens > {guard.input_token_limit}; not sent'
                    raise InputLimitExceeded(guard.refused)
            guard.sent.append(str(request.url))
            started = time.perf_counter()
            try:
                response = guard._original(transport, request)
            except Exception as error:
                guard.responses.append({'error': type(error).__name__, 'seconds': round(time.perf_counter() - started, 3)})
                raise
            response.read()  # Non-streaming: keep the body for the SDK and record the provider's usage and model.
            record = {'status_code': response.status_code, 'seconds': round(time.perf_counter() - started, 3)}
            try:
                body = json.loads(response.content)
                record.update(model=body.get('model'), usage=body.get('usage'),
                              finish_reasons=[c.get('finish_reason') for c in body.get('choices') or []])
                if response.status_code >= 400:
                    record['error'] = {k: (body.get('error') or {}).get(k) for k in ('type', 'code', 'param', 'message')}
            except (ValueError, AttributeError):
                pass
            guard.responses.append(record)
            return response
        httpx.HTTPTransport.handle_request = handle
        return self

    def __exit__(self, *exc):
        import httpx
        httpx.HTTPTransport.handle_request = self._original
        return False

    def stats(self):
        return {'sent': len(self.sent), 'blocked': len(self.blocked), 'hosts': sorted({urlparse(u).netloc for u in self.sent}),
                'responses': self.responses, 'input_tokens': self.input_tokens, 'refused': self.refused}


class ScriptedClient:
    """Offline semantic stand-in: returns prepared responses. Never a claim about model quality."""
    label = 'SCRIPTED_MOCK'

    def __init__(self, path):
        self.path, self.responses = Path(path), read_json(path)['responses']
        self.fingerprint = file_hash(self.path)

    def complete(self, stage, payload, schema):
        return json.dumps(self.responses[payload['scenario_id']][stage], ensure_ascii=False)


def live_settings(model=None, *, temperature=0, max_completion_tokens=MAX_COMPLETION_TOKENS, reasoning_effort=None,
                  service_tier=None, input_token_limit=INPUT_TOKEN_LIMIT):
    """The live model and request limits (reads .env for the default model name; never returns a key).
    temperature None means the parameter is not sent (reasoning models)."""
    from threadsense.config import get_model_settings
    default, key_name = get_model_settings()
    model = model or default
    key_name = 'OPENROUTER_API_KEY' if model.startswith('openrouter/') else key_name
    return {'model': model, 'api_key_variable': key_name,
            'interface': 'CrewAI Agent + Task + Crew per stage (role-specific agents, max_iter=1, max_retry_limit=0, no tools, '
                         'no memory or planning) over crewai.LLM via LiteLLM',
            'temperature': temperature, 'reasoning_effort': reasoning_effort, 'service_tier': service_tier,
            'max_completion_tokens_per_call': max_completion_tokens, 'input_token_limit': input_token_limit,
            'timeout_seconds': REQUEST_TIMEOUT_SECONDS, 'response_format': 'json_object', 'provider_sdk_max_retries': 0,
            'model_fallback': None, 'http_requests_per_stage': HTTP_REQUESTS_PER_STAGE, 'quiet_env': QUIET_ENV}


def _provider_llm_class():
    """CrewAI's LiteLLM path keeps its prompt-cache marker in the messages it sends (CrewAI 1.15); drop it so the
    provider receives plain chat messages."""
    from crewai import LLM

    class ProviderLLM(LLM):
        def _format_messages_for_provider(self, messages):
            return super()._format_messages_for_provider(
                [{k: v for k, v in m.items() if k != 'cache_breakpoint'} for m in messages] if messages else messages)
    return ProviderLLM


class CrewAIClient:
    """Live model through CrewAI: each stage is one Task executed by its role's Agent in a one-task Crew (no tools,
    max_iter=1, max_retry_limit=0, no memory or planning). Paid.

    Measured offline (tests/test_agent3_request_boundary.py): CrewAI's executor sends a forced-final-answer request
    when a reply is not a final answer, the OpenAI SDK retries 5xx/connection errors twice by default, and CrewAI wraps
    every LLM call in a fixed 3-attempt rate-limit retry. Hence max_retries=0 and RequestGuard, which refuses any second
    request in a stage (and any request over the input-token limit) before it is sent. With a CostLedger each request
    first reserves its maximum cost. A configuration rejection or an exhausted budget halts later requests; every topic
    still gets its card."""
    label = 'LIVE_MODEL'

    def __init__(self, settings=None, ledger=None):
        for name, value in QUIET_ENV.items():
            os.environ.setdefault(name, value)
        from crewai import Agent
        from threadsense.config import get_api_key
        self.settings, self.ledger = settings or live_settings(), ledger
        s = self.settings
        model = s['model']
        self.prices = model_prices(model) if ledger is not None else None
        params = {'model': model, 'is_litellm': True, 'api_key': get_api_key(s['api_key_variable']),
                  'base_url': 'https://openrouter.ai/api/v1' if model.startswith('openrouter/') else 'https://api.openai.com/v1',
                  'timeout': REQUEST_TIMEOUT_SECONDS, 'max_retries': 0, 'response_format': {'type': 'json_object'}}
        if s.get('reasoning_effort'):
            params.update(reasoning_effort=s['reasoning_effort'], max_completion_tokens=s['max_completion_tokens_per_call'])
        else:
            params['max_tokens'] = s['max_completion_tokens_per_call']
        if s.get('temperature') is not None:
            params['temperature'] = s['temperature']
        if s.get('service_tier'):
            params['service_tier'] = s['service_tier']
        self.llm = _provider_llm_class()(**params)
        self.agents = {name: Agent(role=role, goal=goal, backstory=backstory, llm=self.llm, tools=[], allow_delegation=False,
                                   max_iter=1, max_retry_limit=0, verbose=False, respect_context_window=False)
                       for name, (role, goal, backstory) in STAGE_AGENTS.items()}
        self.fingerprint, self.last_requests, self.last_input_estimate, self.halted = model, None, None, None

    def complete(self, stage, payload, schema):
        from crewai import Crew, Process, Task
        if self.halted:
            raise self.halted
        agent = self.agents[STAGE_ROLE[stage]]
        task = Task(description=task_description(payload, schema), expected_output=f'One {schema.__name__} JSON object.',
                    agent=agent)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, memory=False, planning=False, verbose=False)
        self.last_requests, self.last_sent_text = None, None
        label = f"{payload.get('scenario_id')}:{stage}"
        limit = self.settings.get('input_token_limit')
        try:
            reservation = self.ledger.reserve(self.prices, limit or 0, self.settings['max_completion_tokens_per_call'],
                                              label) if self.ledger is not None else None
        except CostBudgetExceeded as error:
            self.halted = error  # Stop before exceeding the budget: no further requests in this run.
            raise
        guard, failure = RequestGuard(input_token_limit=limit), None
        try:
            with guard:
                raw = crew.kickoff().raw
        except Exception as error:
            failure = error
        self.last_requests = guard.stats()
        self.last_input_estimate, self.last_sent_text = guard.input_tokens, guard.sent_text
        if reservation is not None:
            usage = next((r.get('usage') for r in guard.responses if r.get('usage')), None)
            charged = self.ledger.settle(reservation, self.prices, usage, label, sent=bool(guard.sent))
            self.last_requests['charged_usd'] = charged
        if guard.refused:
            raise InputLimitExceeded(guard.refused)
        rejected = next((r for r in guard.responses if r.get('status_code') in (400, 401, 403, 404)), None)
        if rejected and (rejected.get('error') or {}).get('code') != 'context_length_exceeded':
            self.halted = ProviderConfigurationError(f"{rejected['status_code']} {rejected.get('error')}")
            raise self.halted
        if failure is not None and guard.blocked:
            raise RequestCeilingExceeded(f'{len(guard.blocked)} further request(s) refused after the first: '
                                         f'{type(failure).__name__}: {str(failure)[:200]}') from failure
        if failure is not None:
            raise failure
        if not guard.sent:
            raise BoundaryNotObserved('The model response arrived without a request through the guarded transport.')
        if any('length' in (r.get('finish_reasons') or []) for r in guard.responses):
            raise OutputLimitReached(f"finish_reason length at {self.settings['max_completion_tokens_per_call']} output tokens")
        return str(raw)


class ReplayClient:
    """Offline replay of a saved run: generations (draft, revision, ToT) are the recorded model outputs; a grounding
    verdict is reused only for a statement whose kind, text, evidence, attributions and dependencies, and whose full
    evidence context, are unchanged, and only while the grounding call's other inputs are those of the recorded run (its
    rules, the evidence view and the sent schema; read from the run's manifest, missing counts as changed). ACTION and ALTERNATIVE verdicts are not reused when they list premises: since pilot v5 their
    premises are shown as provisional with their dependencies, which changes what was judged. Anything else
    (sufficiency, source agreement) is PENDING, never invented.

    Same-rules replay: when the recorded grounding response has the current GroundingJudgment contract and the call's
    rules, evidence view, schema and full evidence context are unchanged, a statement with premises is reused if each
    premise is presented with the status it was sent with (its recorded deterministic rejection, else pending); the
    recorded sufficiency judgments of reused statements and the recorded source-consistency assessment come back as
    recorded."""
    label = 'REPLAY_RECORDED'
    replay = True
    retrieval_expansion = False  # Set per recorded run in __init__ (True only if that run used the expansion).

    def __init__(self, run_dir):
        self.run_dir, self.recorded, self.reuse_log = Path(run_dir), {}, []
        # Pilot runs keep results/<scenario>.json; overnight runs keep topics/<work>.json with the result inside.
        results = [read_json(p) for p in sorted((self.run_dir/'results').glob('*.json'))] + [
            r['result'] for r in (read_json(p) for p in sorted((self.run_dir/'topics').rglob('*.json'))) if r.get('result')]
        # Replay retrieves as the recorded run did: with the bounded expansion only if the run used it.
        self.retrieval_expansion = any(e.get('retrieved_as') for r in results for e in (r.get('evidence_ledger') or {}).values())
        for r in results:
            self.recorded[r['scenario']['id']] = {
                'raw': {c['stage']: c['raw'] for c in r.get('model_calls', []) if c.get('raw')},
                'failed': {c['stage']: c for c in r.get('model_calls', []) if c.get('status') == 'FAILED'},
                'statements': {s['statement_id']: s for s in (r.get('grounding') or {}).get('statements', [])},
                'rejected': (r.get('grounding') or {}).get('rejected') or {},
                'context': set(r.get('evidence_ledger', {})), 'flag_impact': r.get('flag_impact')}
        self.fingerprint = sha256(json.dumps({k: v['raw'] for k, v in self.recorded.items()}, sort_keys=True).encode()).hexdigest()
        manifest = next((read_json(p) for p in (self.run_dir/'run_manifest.json', self.run_dir/'manifest.json') if p.is_file()), {})
        prompts = (manifest.get('fingerprints') or manifest).get('prompts') or {}
        self.grounding_inputs_same = grounding_inputs(prompts) == grounding_inputs(prompt_fingerprints())
        self.flag_rules_same = prompts.get('flag_impact') == flag_impact_fingerprint()

    def complete(self, stage, payload, schema):
        rec = self.recorded[payload['scenario_id']]
        if stage == 'grounding':
            return json.dumps(self._judgment(payload, rec))
        if stage in rec['failed'] and stage not in rec['raw']:
            failed = rec['failed'][stage]
            raise RecordedFailure(failed.get('failure_class'), f"recorded {stage} failure: {failed.get('error')}")
        if stage not in rec['raw']:
            raise LookupError(f'No recorded {stage} output for {payload["scenario_id"]}; nothing is generated in replay.')
        value = json.loads(_json_text(rec['raw'][stage]))
        default = schema.model_fields['contract_version'].default if 'contract_version' in schema.model_fields else None
        legacy = LEGACY_LABELS.get(schema.__name__)
        allowed = set(getattr(schema.model_fields['contract_version'].annotation, '__args__', ())) if default else set()
        if isinstance(value, dict) and legacy and value.get('contract_version') not in allowed:
            value['contract_version'] = legacy  # Recorded content predates newer requirements; it keeps the old rules.
        elif default and isinstance(value, dict) and value.get('contract_version') not in (None, default):
            value['contract_version'] = default  # Version label only; the recorded content is unchanged.
        return json.dumps(value, ensure_ascii=False)

    def _judgment(self, payload, rec):
        context = {e['evidence_id'] for e in payload['member_threads'] + payload['retrieved_sources']}
        verdicts = []
        recorded = json.loads(_json_text(rec['raw']['grounding'])) if rec['raw'].get('grounding') else {}
        exact = (self.grounding_inputs_same and context == rec['context']
                 and recorded.get('contract_version') == GroundingJudgment.model_fields['contract_version'].default)
        def content(x):  # A summary sentence's dependencies are part of what was judged.
            return x['kind'], x['text'], x['evidence_ids'], x.get('attributions', []), x.get('depends_on', [])
        sufficiency = {a['statement_id']: a for a in recorded.get('alternative_sufficiency') or []}
        if recorded.get('action_sufficiency'):
            sufficiency['action'] = recorded['action_sufficiency']

        def premises_as_sent(s, old):
            """Same-rules replay: each premise is presented with the status it was judged with. One exception: a premise
            that was deterministically rejected and is now pending (a corrected check) leaves a SUPPORTED verdict
            standing, since it was supported without that premise, provided the recorded sufficiency did not name it."""
            now = [(p['statement_id'], p['status']) for p in s['premises']]
            then = [(i, rec['rejected'].get(i, 'PENDING_YOUR_VERDICT')) for i in old.get('premises') or []]
            if now == then:
                return True
            if [i for i, _ in now] != [i for i, _ in then] or old.get('model_verdict') != 'SUPPORTED':
                return False
            changed = [i for (i, a), (_, b) in zip(now, then) if a != b]
            essential = set((sufficiency.get(s['statement_id']) or {}).get('essential_statement_ids') or [])
            return all(dict(then)[i].startswith('REJECTED') and dict(now)[i] == 'PENDING_YOUR_VERDICT' and i not in essential
                       for i in changed)
        for s in payload['statements']:
            old = rec['statements'].get(s['statement_id'])
            same = (old is not None and self.grounding_inputs_same and context == rec['context'] and old.get('model_verdict') in
                    ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED') and content(old) == content(s)
                    and ('premises' not in s or (exact and premises_as_sent(s, old))))
            self.reuse_log.append({'scenario_id': payload['scenario_id'], 'statement_id': s['statement_id'],
                                   'reused': bool(same), 'reason': None if same else
                                   'not recorded' if old is None else
                                   'grounding rules, evidence view or schema changed since the recorded run'
                                   if not self.grounding_inputs_same else 'context changed' if context != rec['context'] else
                                   'content changed' if content(old) != content(s) else
                                   'a premise is presented with a different status than when judged' if 'premises' in s and exact else
                                   'premises now shown as provisional with dependencies' if 'premises' in s else
                                   f"recorded verdict {old.get('model_verdict')}"})
            if same:
                verdicts.append({'statement_id': s['statement_id'], 'verdict': old['model_verdict'],
                                 'rationale': old.get('rationale') or 'Recorded verdict (replay).'})
        if exact:  # The recorded call's own sufficiency and source-consistency judgments, for what is reused.
            reused = {v['statement_id'] for v in verdicts}
            out = {'contract_version': recorded['contract_version'], 'verdicts': verdicts,
                   'action_sufficiency': recorded.get('action_sufficiency') if 'action' in reused else None,
                   'alternative_sufficiency': [a for a in recorded.get('alternative_sufficiency') or [] if a['statement_id'] in reused],
                   'source_consistency': recorded.get('source_consistency') or {}}
        else:
            # Recorded judgments predate the source-consistency assessment: it stays NOT_ASSESSED, never "no conflict".
            out = {'contract_version': 'agent3-grounding-judgment-v4', 'verdicts': verdicts, 'action_sufficiency': None,
                   'alternative_sufficiency': []}
        if 'flag_impacts' in payload:  # Reused only for the same flag inputs, statements, evidence and rules.
            saved = rec.get('flag_impact') or {}
            same = (self.flag_rules_same and saved.get('status') == 'ASSESSED'
                    and saved.get('inputs_sha256') == impact.inputs_digest(payload))
            self.reuse_log.append({'scenario_id': payload['scenario_id'], 'statement_id': 'flag_impacts', 'reused': same,
                                   'reason': None if same else 'no flag-impact judgment recorded'
                                   if saved.get('status') != 'ASSESSED' else 'flag-impact rules changed'
                                   if not self.flag_rules_same else 'flag-impact inputs changed'})
            out['flag_impacts'] = impact.recorded_judgments(saved) if same else []
        return out


def grounding_inputs(prompts):
    """What the grounding call receives besides the statements and evidence: its rules, the evidence view and schema."""
    return prompts.get('grounding_rules'), prompts.get('evidence_view'), (prompts.get('sent_schemas') or {}).get('GroundingJudgment')


def failure_class(error):
    """RESOURCE failures (input/output limit, budget, timeout, context window) are not semantic-quality results."""
    if isinstance(error, RecordedFailure):
        return error.failure_class
    if isinstance(error, ProviderConfigurationError):
        return 'CONFIGURATION'
    if isinstance(error, RequestCeilingExceeded):
        return 'REQUEST_CEILING'
    if isinstance(error, (InputLimitExceeded, OutputLimitReached, CostBudgetExceeded)):
        return 'RESOURCE'
    text = f'{type(error).__name__} {error}'.lower()
    if 'timeout' in text or 'timed out' in text or 'context_length' in text or 'contextwindow' in text or 'maximum context' in text:
        return 'RESOURCE'
    if isinstance(error, (ValueError, ValidationError)):  # json.JSONDecodeError and pydantic errors
        return 'SCHEMA'
    return 'PROVIDER'


def task_description(payload, schema):
    """Exactly what the model receives as the user message: the rules once, then the JSON payload without them."""
    body = json.dumps({k: v for k, v in payload.items() if k != 'rules'}, ensure_ascii=False)
    return f"{payload['rules']}\n\nInput JSON:\n{body}\n\nReturn exactly one JSON object for {schema.__name__} " \
           'matching output_schema. No prose outside the JSON.'


def sent_schema(schema):
    """The output schema as sent: the JSON schema without the titles pydantic generates for every model and field
    (field names, types, enums, constraints, required lists and descriptions unchanged)."""
    def strip(node, mapping=False):
        if isinstance(node, dict):
            return {k: strip(v, k in ('properties', '$defs') and not mapping) for k, v in node.items()
                    if mapping or not (k == 'title' and isinstance(v, str))}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return strip(schema.model_json_schema())


def _json_text(raw):
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return text


class Stages:
    """Budgeted model stages for one topic; zero retries, failures recorded and returned as None.
    `reserve` holds back calls for later stages (the final grounding call). The Agent 1 context handed to a stage is
    kept verbatim once per content hash (`agent1_context`), and each call records that hash and whether the text was
    in the HTTP body actually sent (IN_HTTP_BODY), absent from it, or no HTTP request was made (offline clients)."""

    def __init__(self, client, budget, scenario_id):
        self.client, self.budget, self.scenario_id, self.log = client, budget, scenario_id, []
        self.context = {}

    def agent1_context(self):
        return [{'sha256': k, 'content': v} for k, v in self.context.items()]

    def _context(self, entry, text):
        if text is not None:
            sent = getattr(self.client, 'last_sent_text', None)
            entry['agent1_context']['boundary'] = (('IN_HTTP_BODY' if text in sent else 'NOT_IN_HTTP_BODY') if sent
                                                   else 'NO_HTTP_REQUEST')
        return entry

    def __call__(self, stage, payload, schema, reserve=0):
        entry = {'stage': stage, 'schema': schema.__name__}
        halted = getattr(self.client, 'halted', None)
        if halted:  # Budget or configuration stop: no further requests; topics still get cards.
            self.log.append({**entry, 'status': 'SKIPPED_HALTED', 'failure_class': failure_class(halted),
                             'error': f'{type(halted).__name__}: {str(halted)[:300]}'})
            return None
        left = self.budget.remaining('model_calls')
        if left is not None and left < 1 + reserve:
            status = 'SKIPPED_RESERVED_FOR_GROUNDING' if left >= 1 else 'SKIPPED_BUDGET'
            self.log.append({**entry, 'status': status, 'error': f'{left} model call(s) left; {reserve} reserved for final grounding'})
            return None
        try:
            self.budget.charge('model_calls')
        except BudgetExhausted as error:
            self.log.append({**entry, 'status': 'SKIPPED_BUDGET', 'error': str(error)})
            return None
        text = None
        if payload.get('agent1_interpretations') is not None:  # Serialized as task_description embeds it.
            text = json.dumps(payload['agent1_interpretations'], ensure_ascii=False)
            key = sha256(text.encode('utf-8')).hexdigest()
            self.context.setdefault(key, payload['agent1_interpretations'])
            entry['agent1_context'] = {'sha256': key}
        try:
            raw = self.client.complete(stage, {**payload, 'scenario_id': self.scenario_id, 'stage': stage,
                                               'output_schema': sent_schema(schema)}, schema)
            entry.update(raw=raw, raw_sha256=sha256(raw.encode('utf-8')).hexdigest())
            value = schema.model_validate(json.loads(_json_text(raw)))
        except (BoundaryNotObserved, RunStateError):
            raise  # Unverifiable call accounting or unsaved run state stops the run.
        except Exception as error:  # Any provider, parsing or validation error: record it, never retry.
            self.log.append({**self._context(entry, text), **self._requests(), 'status': 'FAILED',
                             'failure_class': failure_class(error), 'error': f'{type(error).__name__}: {str(error)[:400]}'})
            return None
        self.log.append({**self._context(entry, text), **self._requests(), 'status': 'OK'})
        return value

    def _requests(self):
        stats = getattr(self.client, 'last_requests', None)
        estimate = getattr(self.client, 'last_input_estimate', None)
        return {**({'http_requests': stats} if stats is not None else {}),
                **({'input_tokens_estimate': estimate} if estimate is not None else {})}


def consolidated_packet(view, scenario):
    """A consolidated topic (agent2-consolidation-v1): its members from every source group, all records kept."""
    merge = next((m for m in (view.get('consolidation') or {}).get('merges', [])
                  if m['consolidated_topic_id'] == scenario['consolidated_topic_id']), None)
    if merge is None:
        raise ScenarioError(f"Consolidated topic {scenario['consolidated_topic_id']} is not in the handoff.")
    records = [r for r in view['records'] if r['candidate_group_id'] in merge['candidate_group_ids']]
    wanted = set(merge['member_ids'])
    members = sorted((m for r in records for m in r['members'] if m['member_id'] in wanted), key=lambda m: float(m['thread_id']))
    if {m['member_id'] for m in members} != wanted:
        raise ScenarioError(f"Consolidated topic {merge['consolidated_topic_id']} names members the handoff does not have.")
    return {'record': records[0], 'records': records, 'candidate_group_id': records[0]['candidate_group_id'],
            'candidate_group_ids': merge['candidate_group_ids'], 'source_topic_ids': merge['source_topic_ids'],
            'topic_id': merge['consolidated_topic_id'], 'topic_label': merge['topic_name'], 'topic_name': merge['topic_name'],
            'projection_gap': None, 'project_id': merge['project_id'], 'batch_id': merge['batch_id'],
            'member_ids': [m['member_id'] for m in members], 'members': members, 'agent1_resolution': agent1_resolution(members),
            'preliminary_severity': records[0]['topics'][0].get('preliminary_severity') if records[0]['topics'] else None,
            'handoff_contract': view['consolidation']['handoff_contract'], 'export_sha256': view['canonical_sha256'],
            'schema_version': records[0]['schema_version'],
            'threads': [{'project_id': m['project_id'], 'batch_id': m['batch_id'], 'channel_id': m['channel_id'],
                         'thread_id': m['thread_id'], 'member_id': m['member_id'],
                         'messages': m['original_thread']['messages']} for m in members]}


def packet_records(packet):
    return packet.get('records') or [packet['record']]


def topic_packet(view, scenario):
    if scenario.get('consolidated_topic_id'):
        return consolidated_packet(view, scenario)
    gid = scenario['candidate_group_id']
    record = next((r for r in view['records'] if r['candidate_group_id'] == gid), None)
    if record is None:
        raise ScenarioError(f'Group {gid} is not in the handoff.')
    gap = None
    if scenario.get('topic_id') or scenario.get('topic_name'):
        key = 'topic_id' if scenario.get('topic_id') else 'topic_name'  # The overnight workflow addresses topics by ID.
        topics = [t for t in record['topics'] if t[key] == scenario[key]]
        if len(topics) != 1:
            raise ScenarioError(f"Group {gid} has {len(topics)} topics with {key} {scenario[key]!r}.")
        topic = topics[0]
        member_ids, topic_id, label = list(topic['member_ids']), topic['topic_id'], topic['topic_name']
        preliminary = topic.get('preliminary_severity')
    else:
        member_ids, topic_id = list(record['unassigned_member_ids']), None
        gap = next((r for r in record['review_reasons'] if r.startswith('Projection gap')), None)
        if not member_ids or gap is None:
            raise ScenarioError(f'Group {gid} has no unassigned projection-gap members.')
        label = f'Unassigned members of {gid} (projection gap; no Agent 2 topic)'
        preliminary = record.get('unassigned_preliminary_severity')
    members = sorted((m for m in record['members'] if m['member_id'] in member_ids), key=lambda m: float(m['thread_id']))
    return {'record': record, 'candidate_group_id': gid, 'topic_id': topic_id, 'topic_label': label,
            'topic_name': label if topic_id else None, 'projection_gap': gap, 'project_id': record['project_id'],
            'batch_id': record['batch_id'], 'member_ids': [m['member_id'] for m in members], 'members': members,
            'agent1_resolution': agent1_resolution(members),
            'preliminary_severity': preliminary, 'handoff_contract': record['taxonomy_handoff']['contract_version'],
            'export_sha256': view['canonical_sha256'], 'schema_version': record['schema_version'],
            'threads': [{'project_id': m['project_id'], 'batch_id': m['batch_id'], 'channel_id': m['channel_id'],
                         'thread_id': m['thread_id'], 'member_id': m['member_id'],
                         'messages': m['original_thread']['messages']} for m in members]}


def initial_query(packet):
    """Topic name plus the earliest member's central question (no source IDs, no answers). A thread that asks nothing
    (a statement or reminder) has no central question: the earliest question is used, else the earliest member's
    Agent 1 summary, else the topic label."""
    interpretations = [m['agent1_record']['interpretation'] for m in packet['members']]
    question = next((i['central_question'] for i in interpretations if i.get('central_question')), None) or next(
        (i['summary'] for i in interpretations if i.get('summary')), None) or packet['topic_label']
    return f"{packet['topic_name']}. {question}" if packet['topic_name'] else question


def rubric_payload(rubric):
    return {'version': rubric['version'], 'scope': rubric['rubric_scope'],
            'levels': {level: {'definition': e['definition'], 'examples': e['examples'],
                               'signals': [{'index': i, 'text': s} for i, s in enumerate(e['required_signals'])]}
                       for level, e in rubric['levels'].items()}}


def _interpretations(packet):
    out = []
    for m in packet['members']:
        a, i = m['agent1_record'], m['agent1_record']['interpretation']
        out.append({'member_id': m['member_id'], 'thread_id': m['thread_id'], 'summary': i['summary'],
                    'central_question': i['central_question'],
                    'attributed_agent1_resolution': {
                        'state': i['resolution_state'], 'rationale': i.get('resolution_rationale') or '',
                        'agent1_verification_status': a.get('verification_status'),
                        'note': 'Agent 1 label, not evidence; NEEDS_REVIEW means Agent 1 did not verify it. Assess '
                                'resolution from the member messages.'},
                    'agent1_review_required': a['review_required'], 'agent1_review_reason': a.get('review_reason') or '',
                    'note': 'Agent 1 interpretation, not source evidence; cite member messages for incident facts.'})
    return out


def _topic(packet, as_of):
    return {'project_id': packet['project_id'], 'batch_id': packet['batch_id'], 'candidate_group_id': packet['candidate_group_id'],
            'topic_id': packet['topic_id'], 'topic_label': packet['topic_label'], 'projection_gap': packet['projection_gap'],
            'as_of': as_of, 'member_ids': packet['member_ids']}


def _split(ledger):
    """Model-facing evidence (model_view): member messages without display names, then retrieved sources."""
    return ([model_view(v) for v in ledger.values() if v['origin'] == 'member_message'],
            [model_view(v) for v in ledger.values() if v['origin'] == 'retrieved_source'])


def _research_payload(rules, topic, ledger, tools, rubric, interpretations):
    members, retrieved = _split(ledger)
    return {'rules': rules, 'topic': topic, 'member_evidence': members, 'agent1_interpretations': interpretations,
            'retrieved_evidence': retrieved, 'retrieval_notes': tools.notes(), 'rubric': rubric_payload(rubric),
            'limits': {'follow_up_queries': MAX_FOLLOW_UPS}}


def grounding_payload(stmts, ledger, topic, rejected=None, depends=None, review_flags=None, declared=None):
    """Sendable statements plus the full topic context: every message of every member thread (canonical IDs, roles,
    thread starters, reactions) and every retrieved source, so the draft's citations do not set the judge's evidence
    window. Premises are shown as provisional (pending the judge's own verdict) with the announcements they depend on,
    never as final. `review_flags`: the upstream review obligations still open on these threads (a REVIEW_NOTE may
    rely on them). `declared`: the draft's source conflicts, which the judge checks; it also compares the governing
    sources on its own (source_consistency)."""
    rejected, depends = rejected or {}, depends or {}
    sent = sendable(stmts, rejected)
    members, retrieved = _split(ledger)

    def premise(i):
        out = {'statement_id': i, 'status': rejected.get(i, 'PENDING_YOUR_VERDICT')}
        if i in depends and i not in rejected:
            out['depends_on'] = depends[i]
        return out

    def shown(s):
        out = {k: s[k] for k in ('statement_id', 'kind', 'text', 'evidence_ids')}
        if s.get('attributions'):
            out['attributions'] = s['attributions']
        if s.get('depends_on'):
            out['depends_on'] = s['depends_on']
        if 'premises' in s:
            out['premises'] = [premise(i) for i in s['premises']]
        return out
    return {'rules': GROUNDING_RULES, 'topic': topic, 'statements': [shown(s) for s in sent],
            'member_threads': members, 'retrieved_sources': retrieved, 'open_review_flags': list(review_flags or []),
            'governing_sources': governing_sources(ledger), 'declared_conflicts': [
                {'conflict_index': i, 'evidence_ids': c.evidence_ids, 'description': c.description}
                for i, c in enumerate(declared or [])]}


def _final_grounding(call, draft, ledger, topic, stmts, structural, actions, review_flags=None, flag_inputs=None):
    """Structurally rejected statements are withheld; everything else still goes to the one semantic call.
    `flag_inputs` (opt-in shadow assessment): the same call also judges each flag's impact (GroundingJudgmentV7);
    the judge's raw entries and the payload they were judged on come back under `_flag_impact`."""
    rejected = rejected_statements(draft, stmts, structural, actions)
    if not sendable(stmts, rejected):
        return grounding_result(draft, ledger, stmts, structural=structural, actions=actions,
                                reason='NOTHING_CITED' if not rejected else 'ALL_STATEMENTS_REJECTED')
    payload, schema = grounding_payload(stmts, ledger, topic, rejected, dependencies(draft, ledger), review_flags,
                                        draft.source_conflicts), GroundingJudgment
    if flag_inputs is not None:
        payload, schema = {**payload, 'rules': f'{GROUNDING_RULES}\n\n{impact.FLAG_IMPACT_RULES}',
                           'flag_impacts': flag_inputs}, GroundingJudgmentV7
    judgment = call('grounding', payload, schema)
    result = grounding_result(draft, ledger, stmts, structural=structural, actions=actions, judgment=judgment,
                              ran=judgment is not None, reason='GROUNDING_CALL_FAILED_OR_OVER_BUDGET',
                              pending=getattr(call.client, 'replay', False))
    if flag_inputs is not None:
        result['_flag_impact'] = {'raw': None if judgment is None else list(judgment.flag_impacts), 'payload': payload}
    return result


def _review_items(packet, card):
    items = review_items_from_view({'records': packet_records(packet)})
    linked = set(card.lineage.member_ids)
    return [ModelReviewItem.model_validate({**i.model_dump(mode='json'), 'related_card_ids': [card.card_id]})
            if set(i.member_ids) & linked or not i.member_ids else i for i in items]


NOT_RUN = {'structural_issues': [], 'action_issues': [], 'statements': [], 'unsupported': [], 'unjudged': [],
           'extraneous_verdicts': []}


def _adaptive(call, tools, draft, ledger, topic, rubric, interpretations, budget):
    """The opt-in react path: sequential follow-ups whose revision may name the next query (advisor_research)."""
    current = {'draft': draft}

    def room_for_another():
        left = budget.remaining('model_calls')
        tot = 1 if advisor_tot.triggers(current['draft'], temporal_check(current['draft'], ledger), ledger) else 0
        need = 3 + tot  # this revision, a second revision, the comparison if triggered, the final grounding
        return (left is None or left >= need), (
            f'A second search would need {need} more model requests (revision, second revision, '
            f"{'option comparison, ' if tot else ''}final grounding) but {left} remain: a fifth request for this topic.")

    def revise(may_search, steps):
        payload = _research_payload(REACT_REVISION_RULES if may_search else REVISION_RULES, topic, ledger, tools, rubric,
                                    interpretations)
        revised = call('revision', {**payload, 'previous_draft': current['draft'].model_dump(exclude_none=True),
                                    'follow_ups': advisor_research.follow_up_entries(steps)}, AdvisorDraft, reserve=1)
        if revised is None:
            return None
        gap = steps[-1]['gap_id']
        current['draft'] = revised
        return {'draft': revised, 'request': advisor_research.gap_request(revised) if may_search else None,
                'filled': gap not in {g.gap_id for g in revised.gaps}}
    first = advisor_research.gap_request(draft)
    run = advisor_research.adaptive_research(tools, first, revise, room_for_another=room_for_another,
                                             topic_text=topic['topic_label'])
    final = run['draft'] or draft
    recovered = [i for s in run['steps'] for i in s.get('new_evidence_ids', [])]
    record = {k: v for k, v in run.items() if k != 'draft'} | {
        'recovered_evidence_ids': recovered, 'used_evidence_ids': advisor_research.used_evidence(final, recovered),
        'model_requests': {'revisions': run['revisions']}, 'local_searches': sum(s['status'] == 'DONE' for s in run['steps'])}
    return final, advisor_research.follow_up_entries(run['steps']), record


def advise(scenario, *, view, retriever, client, budget, rubric, run_id, as_of, initial=None, research_mode='batch',
           flag_impact=False, tot_shadow=False):
    """One topic. Never raises for model or budget problems; ScenarioError only for a missing topic.
    `initial` replaces the derived initial query (used to test recovery from an incomplete first pass).
    `research_mode` 'react' is the opt-in adaptive follow-up experiment (advisor_research); 'batch' is production.
    `flag_impact` (opt-in shadow evaluation, off in production): the final grounding call also assesses each inherited
    flag (agents/flag_impact); the validated record is saved as `flag_impact` and routing does not read it.
    `tot_shadow` (opt-in, off in production): after the card is assembled, the shadow ToT policy (agents/tot_policy)
    records `tot.shadow_policy` and its incumbent-issue dispositions in diagnostics; no request, card or route changes."""
    if research_mode not in advisor_research.RESEARCH_MODES:
        raise ValueError(f'research_mode must be one of {advisor_research.RESEARCH_MODES}.')
    budget.start_topic()
    packet = topic_packet(view, scenario)
    ledger = {i['evidence_id']: i for i in member_messages(packet['members'])}
    tools = ResearchTools(retriever, project=packet['project_id'], batch=packet['batch_id'], as_of=as_of,
                          expansion=getattr(client, 'retrieval_expansion', True),
                          budget=budget, top_k=TOP_K, ledger=ledger)
    call, topic, interpretations = Stages(client, budget, scenario['id']), _topic(packet, as_of), _interpretations(packet)
    query = initial or initial_query(packet)
    tools.search(query, purpose='initial_current_guidance')
    if tools.withheld:  # Superseded material exists in this project: check whether it bears on the topic.
        tools.search(query, purpose='supersession_check', version_mode='history')
    first = draft = call('draft', _research_payload(DRAFT_RULES, topic, ledger, tools, rubric, interpretations),
                         AdvisorDraft, reserve=1)
    follow_ups, unfilled, adaptive = [], [], None
    if draft is not None and research_mode == 'react':
        draft, follow_ups, adaptive = _adaptive(call, tools, draft, ledger, topic, rubric, interpretations, budget)
        unfilled = [g.model_dump() for g in draft.gaps]
    elif draft is not None:
        requested = [g for g in draft.gaps if g.follow_up]
        for i, gap in enumerate(requested):
            entry = {'gap_id': gap.gap_id, 'need': gap.need, 'query': gap.follow_up.query,
                     'source_types': gap.follow_up.source_types, 'version_mode': gap.follow_up.version_mode}
            if i >= MAX_FOLLOW_UPS:
                follow_ups.append({**entry, 'status': 'DROPPED_FOLLOW_UP_LIMIT'})
                continue
            before = set(ledger)
            found = tools.search(gap.follow_up.query, purpose=f'gap:{gap.need}', source_types=gap.follow_up.source_types,
                                 version_mode=gap.follow_up.version_mode, gap_id=gap.gap_id)
            follow_ups.append({**entry, 'status': 'DONE' if found else 'SKIPPED_BUDGET',
                               'new_evidence_ids': sorted(set(ledger) - before)})
        if any(f['status'] == 'DONE' for f in follow_ups):
            payload = _research_payload(REVISION_RULES, topic, ledger, tools, rubric, interpretations)
            revised = call('revision', {**payload, 'previous_draft': draft.model_dump(exclude_none=True), 'follow_ups': follow_ups},
                           AdvisorDraft, reserve=1)
            draft = revised or draft
        unfilled = [g.model_dump() for g in draft.gaps]
    revised, normalization = draft is not first, []
    if draft is not None:  # Role-label and recurrence corrections, recorded; never content repair.
        draft, normalization = normalize(draft, ledger)
    flags = [f for record in packet_records(packet) for f in inherited_flags(
        record, [m for m in packet['member_ids'] if m in {x['member_id'] for x in record['members']}],
        projection_gap=packet['projection_gap'])]
    tot, diagnostics, temporal_pre, covered_issues, action_notes = {'status': 'NOT_TRIGGERED', 'triggers': []}, [], None, [], []
    prepared, flag_raw = None, None
    if draft is None:
        grounding, temporal, final = {**NOT_RUN, 'status': 'NOT_RUN', 'basis': 'NO_DRAFT'}, None, unauthorized(packet)
    else:
        structural = structural_issues(draft, ledger, set(packet['member_ids']))
        covered_issues = coverage_issues(draft, ledger, follow_ups, next((e for e in call.log if e['stage'] == 'revision'), None))
        severity_notes = []
        severity, severity_issues = build_severity(draft.severity, ledger, packet, rubric, notes=severity_notes)
        temporal_pre = temporal_check(draft, ledger)
        tot = advisor_tot.compare(call, draft=draft, temporal=temporal_pre, ledger=ledger, handling=established(draft, ledger),
                                  skip=None, payload={
            'topic': topic, 'draft': draft.model_dump(), 'evidence': [model_view(v) for v in ledger.values()],
            'proposed_severity': {'level': severity.level, 'assessment_status': severity.assessment_status,
                                  'note': 'Bound to the rubric; not yet grounded.'},
            'rubric_levels': sorted(rubric['levels'])})
        draft, adopted = advisor_tot.select(tot, draft)  # A selected candidate may become the action; flags untouched.
        action_notes = [adopted] if adopted else []
        actions = action_issues(draft, ledger)
        stmts = statements(draft, ledger, severity=severity, alternatives=advisor_tot.alternatives(tot))
        if flag_impact:
            prepared = impact.prepare(FlagSource.from_view(view, run_id), flags, packet=packet, draft=draft, stmts=stmts,
                                      ledger=ledger, topic=topic, query=query, agent1_context=call.agent1_context())
        grounding = _final_grounding(call, draft, ledger, topic, stmts, structural, actions,
                                     [{k: v for k, v in f.model_dump().items() if v} for f in flags],
                                     flag_inputs=prepared['inputs'] if prepared else None)
        flag_raw = grounding.pop('_flag_impact', None)
        tot = advisor_tot.finalize(tot, grounding)
        final = authorize(draft, grounding, ledger, packet, severity=severity, severity_issues=severity_issues, rubric=rubric,
                          severity_notes=severity_notes)
        if final['action'] is None:  # Selection among already-judged text only; nothing is rewritten.
            verdict = next((s['verdict'] for s in grounding['statements'] if s['statement_id'] == 'action'), 'NOT_SENT')
            chosen, essential, note = advisor_tot.fallback(tot, draft, verdict)
            if chosen is not None:
                final.update(action=chosen, essential=essential, action_scope=note,
                             fallback_evidence=next(c['evidence_ids'] for c in tot['candidates']
                                                    if c['candidate_id'] == tot['model_preferred_candidate_id']))
            if note:
                action_notes = action_notes + [note]
        final['action_notes'] = action_notes
        tot['choice_after_grounding'] = advisor_tot.choice_after_grounding(tot, final['action'])
        if tot['status'] == 'COMPARED':  # Which candidate the card action is (assemble_card drops it on UNSUPPORTED evidence).
            source = 'TOT_FALLBACK' if final.get('essential') is not None else 'TOT' if action_notes and action_notes[0].startswith(
                'Action selected') else 'DRAFT'
            tot['card_action'] = advisor_tot.card_action_candidate(
                tot, final['action'] if draft.evidence_sufficiency != 'UNSUPPORTED' else None, source)
            tot['controller'] = advisor_tot.CONTROLLER_VERSION
        # Recorded supersession is credited only to announcements the final grounding verified; several current
        # sources explain a superseded section only if the final grounding judged that they agree. Conflicts the final
        # grounding found on its own reach routing here (the comparison ran before; it is not re-run).
        temporal = temporal_check(draft, ledger, final['handling'],
                                  {s['statement_id']: s['verdict'] for s in grounding['statements']},
                                  grounding.get('source_consistency'))
        diagnostics += normalization + [
            {'code': 'ALTERNATIVE_NOT_GROUNDED' if w['kind'] == 'ALTERNATIVE' else 'WITHHELD_STATEMENT', **w}
            for w in final['withheld']]
        if draft.evidence_sufficiency == 'UNSUPPORTED' and draft.proposed_action and \
                draft.proposed_action.action_type != 'NO_ACTION':
            diagnostics.append({'code': 'UNSUPPORTED_ACTION_NOT_CARRIED', 'action': draft.proposed_action.model_dump()})
    outcome = {'draft': draft, 'ledger': ledger, 'inherited_flags': flags, 'grounding': grounding, 'temporal': temporal,
               'final': final, 'evidence_sufficiency': draft.evidence_sufficiency if draft else None,
               'coverage_issues': covered_issues, 'action_choice': tot.get('choice_after_grounding'),
               'action_source': 'TOT' if action_notes and action_notes[0].startswith(
                   'Action selected') else 'DRAFT',
               'failures': [e for e in call.log if e['status'] != 'OK']}
    try:
        card = assemble_card(outcome, packet, run_id=run_id)
    except ValidationError as error:
        diagnostics.append({'code': 'CARD_ASSEMBLY_FAILED', 'error': str(error)[:1500]})
        card = assemble_card({**outcome, 'draft': None, 'temporal': None, 'evidence_sufficiency': None, 'final': unauthorized(packet),
                              'grounding': {**NOT_RUN, 'status': 'NOT_RUN', 'basis': 'CARD_ASSEMBLY_FAILED'},
                              'failures': outcome['failures'] + [{'stage': 'card_assembly', 'status': 'FAILED', 'error': 'see diagnostics'}]},
                             packet, run_id=run_id)
    flag_record = None
    if flag_impact:
        if prepared is None or flag_raw is None or flag_raw['raw'] is None:
            flag_record = impact.not_assessed('The final grounding call did not run or failed; no flag was assessed.')
        else:
            judged_by = ('REPLAY' if getattr(client, 'replay', False) else
                         'MODEL' if isinstance(client, CrewAIClient) else 'PREPARED')
            verdicts = {s['statement_id']: s['verdict'] for s in grounding['statements']}
            assessed = impact.validate(flag_raw['raw'], prepared, verdicts=verdicts,
                                       member_states=final['member_resolution'], source=judged_by)
            flag_record = impact.record(assessed, prepared, payload=flag_raw['payload'], ledger=ledger,
                                        card=card.model_dump(mode='json'))
    items = _review_items(packet, card)
    covered = coverage({'records': packet_records(packet)}, cards=[card], review_items=items)
    # Members of the group's other topics are outside this scenario (not lost); obligations must all be carried.
    covered = {'group_members_outside_this_card': covered['missing_members'],
               'uncarried_obligations': covered['missing_obligations']}
    result = {'scenario': scenario, 'status': 'CARD', 'topic': {**topic, 'initial_query': query},
            'retrieval_trace': tools.trace, 'retrieval_notes': tools.notes(), 'follow_ups': follow_ups,
            **({'adaptive_research': adaptive} if adaptive is not None else {}),
            'unfilled_gaps': unfilled, 'model_calls': call.log, 'agent1_context': call.agent1_context(),
            **({'flag_impact': flag_record.model_dump(mode='json')} if flag_record else {}),
            'drafts': {'initial': first.model_dump() if first else None,
                       'final': draft.model_dump() if draft else None, 'revised': revised},
            'grounding': grounding, 'temporal': temporal, 'temporal_before_grounding': temporal_pre,
            'severity': {'assessment': final['severity'].model_dump(mode='json'), 'issues': final['severity_issues'],
                         'notes': final['severity_notes'], 'proposal': draft.severity.model_dump() if draft else None},
            'resolution': {'topic': final['resolution'], 'members': final['member_resolution'],
                           'agent1_attributed': packet['agent1_resolution']},
            'established_handling': sorted(final['handling']), 'coverage_issues': covered_issues,
            'action_source': 'TOT_FALLBACK' if final.get('essential') is not None else
            'TOT' if action_notes and action_notes[0].startswith('Action selected') else
            'DRAFT' if draft and draft.proposed_action else None, 'action_notes': action_notes,
            'tot': tot, 'evidence_ledger': ledger, 'card': card.model_dump(mode='json'),
            'review_items': [i.model_dump(mode='json') for i in items], 'coverage': covered,
            'budget': {'consumed': budget.topic_usage(), 'limits': BUDGET}, 'diagnostics': diagnostics}
    if tot_shadow and tot['status'] == 'COMPARED':  # Shadow only: computed from the finished result, never routed.
        from threadsense.agents import tot_policy
        tot['shadow_policy'] = tot_policy.shadow(result)
        diagnostics += [{'code': 'TOT_INCUMBENT_ISSUE', **d} for d in tot['shadow_policy']['incumbent_issues']]
    return result


def control(scenario, *, retriever, client, budget, rubric, as_of):
    """Negative control: a question with no handoff members, so no card. Unsupported stays visible."""
    budget.start_topic()
    ledger = {}
    tools = ResearchTools(retriever, project=scenario['project_id'], batch=scenario.get('batch_id'), as_of=as_of,
                          budget=budget, top_k=TOP_K, ledger=ledger)
    call = Stages(client, budget, scenario['id'])
    tools.search(scenario['question'], purpose='initial_current_guidance')
    topic = {'project_id': scenario['project_id'], 'batch_id': scenario.get('batch_id'), 'question': scenario['question'],
             'as_of': as_of, 'member_ids': []}
    draft = call('draft', {**_research_payload(DRAFT_RULES, topic, ledger, tools, rubric, []), 'member_evidence': []},
                 AdvisorDraft, reserve=1)
    grounding = None
    if draft is not None:
        stmts = statements(draft, ledger)
        grounding = _final_grounding(call, draft, ledger, topic, stmts,
                                     claim_issues(draft, ledger) + announcement_issues(draft, ledger)
                                     + presentation_issues(draft, ledger), action_issues(draft, ledger))
    supported = draft is not None and draft.evidence_sufficiency == 'SUFFICIENT' and grounding['status'] == 'PASSED'
    return {'scenario': scenario, 'status': 'CONTROL', 'control_outcome': 'SUPPORTED' if supported else
            'NO_DRAFT' if draft is None else 'UNSUPPORTED',
            'retrieval_trace': tools.trace, 'retrieved_results': sum(len(s.get('result_ids', [])) for s in tools.trace),
            'model_calls': call.log, 'drafts': {'final': draft.model_dump() if draft else None}, 'grounding': grounding,
            'evidence_ledger': ledger, 'card': None, 'budget': {'consumed': budget.topic_usage(), 'limits': BUDGET},
            'note': 'External question with no handoff members: retrieved results are nearest neighbours, not evidence, '
                    'and no card is produced. Unsupported handoff members still get cards (see the topic scenarios).'}


def run_pilot(*, client, retriever=None, view=None, scenarios=None, budget_limits=BUDGET, handoff=HANDOFF):
    """Run the selected scenarios. The index freshness check happens once, here, before research."""
    retriever = retriever or open_retriever()
    view = view if view is not None else load_effective_view(handoff)
    spec = read_json(SCENARIOS) if scenarios is None else scenarios
    rubric, as_of, budget = load_rubric(None), retriever.manifest['cutoff'], Budget(budget_limits)
    run_id = stable_id('agent3pilot', {'version': PILOT_VERSION, 'scenarios': [s['id'] for s in spec['scenarios']],
                                       'export': view['canonical_sha256'], 'index': retriever.manifest['build_fingerprint'],
                                       'semantic': client.label, 'client': getattr(client, 'fingerprint', None)})
    results = []
    for scenario in spec['scenarios']:
        try:
            if scenario.get('control'):
                results.append(control(scenario, retriever=retriever, client=client, budget=budget, rubric=rubric, as_of=as_of))
            else:
                results.append(advise(scenario, view=view, retriever=retriever, client=client, budget=budget,
                                      rubric=rubric, run_id=run_id, as_of=as_of))
        except ScenarioError as error:
            results.append({'scenario': scenario, 'status': 'SCENARIO_UNAVAILABLE', 'error': str(error), 'card': None})
        except BoundaryNotObserved as error:  # Call accounting unverifiable: stop, record, make no further calls.
            results.append({'scenario': scenario, 'status': 'STOPPED_BOUNDARY_NOT_OBSERVED', 'error': str(error), 'card': None})
            break
    manifest = {
        'pilot_version': PILOT_VERSION, 'run_id': run_id, 'semantic_judgments': client.label,
        'semantic_client_fingerprint': getattr(client, 'fingerprint', None),
        'live_request_settings': getattr(client, 'settings', None),
        'prompts': prompt_fingerprints(),
        'replay': {'source': str(client.run_dir), 'reused_verdicts': sum(e['reused'] for e in client.reuse_log),
                   'pending_or_not_reused': [e for e in client.reuse_log if not e['reused']]}
        if getattr(client, 'replay', False) else None,
        'handoff': {'run': Path(handoff).resolve().relative_to(ROOT).as_posix() if Path(handoff).resolve().is_relative_to(ROOT)
                    else str(handoff), 'canonical_sha256': view['canonical_sha256']},
        'index': {k: retriever.manifest[k] for k in ('build_fingerprint', 'chunking_version', 'corpus_fingerprint', 'cutoff')},
        'freshness': 'CURRENT (checked once before research)', 'as_of': as_of,
        'rubric': {k: rubric[k] for k in ('version', 'content_sha256', 'rubric_scope')},
        'retrieval': {'top_k': TOP_K, 'mode': 'hybrid', 'use_mmr': True, 'mmr_lambda': DEFAULTS['mmr_lambda'],
                      'rrf_only_option': 'Retriever.search(use_mmr=False); not used by the pilot',
                      'initial_version_mode': 'current', 'max_follow_ups_per_topic': MAX_FOLLOW_UPS},
        'budget_limits': budget_limits, 'budget_consumed': dict(budget.used),
        'http_requests': {'sent': sum(c.get('http_requests', {}).get('sent', 0) for r in results for c in r.get('model_calls', [])),
                          'blocked': sum(c.get('http_requests', {}).get('blocked', 0) for r in results for c in r.get('model_calls', []))},
        'scenarios': [{'id': r['scenario']['id'], 'status': r['status'],
                       'card_line': (r.get('card') or {}).get('card_line'), 'control_outcome': r.get('control_outcome')}
                      for r in results]}
    return {'manifest': manifest, 'results': results}


def flag_impact_fingerprint():
    """What the opt-in flag-impact assessment adds to the grounding call: its rules and the v7 schema as sent."""
    digest = lambda text: sha256(text.encode('utf-8')).hexdigest()  # noqa: E731
    return {'rules': digest(impact.FLAG_IMPACT_RULES),
            'sent_schema': digest(json.dumps(sent_schema(GroundingJudgmentV7), sort_keys=True)),
            'assessment': impact.FlagImpactAssessment.model_fields['contract_version'].default}


def prompt_fingerprints():
    """SHA-256 of every rule text and output schema the model sees."""
    from threadsense.agents.advisor_contracts import ToTComparison
    digest = lambda text: sha256(text.encode('utf-8')).hexdigest()  # noqa: E731
    return {'prompt_version': PROMPT_VERSION, 'draft_rules': digest(DRAFT_RULES), 'revision_rules': digest(REVISION_RULES),
            'writing_guide': digest(WRITING_GUIDE), 'style_examples': digest(STYLE_EXAMPLES), 'grounding_rules': digest(GROUNDING_RULES),
            'tot_rules': digest(advisor_tot.RULES),
            'schemas': {s.__name__: digest(json.dumps(s.model_json_schema(), sort_keys=True))
                        for s in (AdvisorDraft, GroundingJudgment, ToTComparison)},
            'sent_schemas': {s.__name__: digest(json.dumps(sent_schema(s), sort_keys=True))
                             for s in (AdvisorDraft, GroundingJudgment, ToTComparison)},
            'evidence_view': EVIDENCE_VIEW_VERSION, 'flag_impact': flag_impact_fingerprint(),
            'contract_versions': {'draft': AdvisorDraft.model_fields['contract_version'].default,
                                  'grounding': GroundingJudgment.model_fields['contract_version'].default,
                                  'tot': ToTComparison.model_fields['contract_version'].default}}


def _tokens(text):
    try:
        import tiktoken
        return len(tiktoken.get_encoding('o200k_base').encode(text)), 'o200k_base'
    except Exception:  # noqa: BLE001 - an estimate only
        return len(text) // 4, 'chars/4'


def plan(*, retriever=None, view=None, scenarios=None, handoff=HANDOFF):
    """Zero model calls: freshness check, topic packets, the initial retrieval each topic would start from,
    and the size of the first (draft) request."""
    retriever = retriever or open_retriever()
    view = view if view is not None else load_effective_view(handoff)
    spec, as_of, rows = read_json(SCENARIOS) if scenarios is None else scenarios, retriever.manifest['cutoff'], []
    rubric = load_rubric(None)
    for scenario in spec['scenarios']:
        budget = Budget(BUDGET)
        try:
            packet = None if scenario.get('control') else topic_packet(view, scenario)
        except ScenarioError as error:
            rows.append({'id': scenario['id'], 'status': 'SCENARIO_UNAVAILABLE', 'error': str(error)})
            continue
        project = scenario['project_id'] if packet is None else packet['project_id']
        batch = scenario.get('batch_id') if packet is None else packet['batch_id']
        ledger = {} if packet is None else {i['evidence_id']: i for i in member_messages(packet['members'])}
        tools = ResearchTools(retriever, project=project, batch=batch, as_of=as_of, budget=budget, top_k=TOP_K, ledger=ledger)
        query = scenario['question'] if packet is None else initial_query(packet)
        found = tools.search(query, purpose='initial_current_guidance')
        topic = {'project_id': project, 'batch_id': batch, 'as_of': as_of} if packet is None else _topic(packet, as_of)
        payload = _research_payload(DRAFT_RULES, topic, ledger, tools, rubric, [] if packet is None else _interpretations(packet))
        tokens, counter = _tokens(task_description({**payload, 'output_schema': sent_schema(AdvisorDraft)}, AdvisorDraft))
        rows.append({'id': scenario['id'], 'status': 'PLANNED', 'project_id': project, 'batch_id': batch,
                     'topic': None if packet is None else packet['topic_label'],
                     'member_ids': [] if packet is None else packet['member_ids'], 'initial_query': query,
                     'member_evidence_ids': [k for k, v in ledger.items() if v['origin'] == 'member_message'],
                     'initial_results': [(r['evidence_id'], r['use'], r['applicability']['state']) for r in found['results']],
                     'withheld_by_version': tools.notes()['withheld_by_version'],
                     'supersession_check_planned': bool(tools.withheld),
                     'draft_prompt_tokens_estimate': tokens, 'token_counter': counter})
    return {'as_of': as_of, 'budget_limits': BUDGET, 'model_calls': 0, 'scenarios': rows,
            'request_limits': {'http_requests_per_stage': HTTP_REQUESTS_PER_STAGE, 'provider_sdk_max_retries': 0,
                               'max_completion_tokens_per_call': MAX_COMPLETION_TOKENS,
                               'max_http_requests_per_run': BUDGET['model_calls_total'] * HTTP_REQUESTS_PER_STAGE}}


def _dump(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def write_outputs(out_dir, run):
    """Write to a new directory only; never overwrites a previous run."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(f'{out} exists; pilot runs write to a new directory.')
    (out/'results').mkdir(parents=True)
    _dump(out/'manifest.json', run['manifest'])
    for result in run['results']:
        _dump(out/'results'/f"{result['scenario']['id']}.json", result)
    _dump(out/'cards.json', [r['card'] for r in run['results'] if r.get('card')])
    _dump(out/'review_items.json', [i for r in run['results'] for i in r.get('review_items', [])])
    (out/'report.md').write_text(report(run), encoding='utf-8')
    return out


def _fmt_ids(ids):
    return ', '.join(f'`{i}`' for i in ids) or 'none'


def report(run):
    m = run['manifest']
    lines = [f"# Agent 3 pilot - {m['run_id']}", '',
             f"Semantic judgments: **{m['semantic_judgments']}**. Deterministic checks (citations, applicability, "
             'severity binding, temporal priority, authorization, routing, budgets) ran for real; with SCRIPTED_MOCK, the '
             'draft, grounding and comparison judgments are prepared responses and say nothing about model quality.', '',
             f"Handoff `{m['handoff']['run']}`; index `{m['index']['chunking_version']}` "
             f"({m['freshness']}); as-of {m['as_of']}; rubric {m['rubric']['version']} ({m['rubric']['rubric_scope']}).", '',
             f"Budget limits {m['budget_limits']}; consumed {m['budget_consumed']}; HTTP requests {m['http_requests']}.", '']
    for r in run['results']:
        s = r['scenario']
        lines += [f"## {s['id']}: {s['focus']}", '']
        if r['status'] in ('SCENARIO_UNAVAILABLE', 'STOPPED_BOUNDARY_NOT_OBSERVED'):
            lines += [f"**{r['status']}:** {r['error']}", '']
            continue
        if r['status'] == 'CONTROL':
            lines += [f"Control outcome: **{r['control_outcome']}** (no card). Retrieved {r['retrieved_results']} results; "
                      f"model calls {[c['stage'] + ':' + c['status'] for c in r['model_calls']]}.", '']
            continue
        card, g = r['card'], r['grounding']
        withheld = [d for d in r['diagnostics'] if d['code'] == 'WITHHELD_STATEMENT']
        lines += [f"Topic: {card['topic_name']} (`{card['lineage']['candidate_group_id']}`, {len(card['lineage']['member_ids'])} members)",
                  f"- Card line: **{card['card_line']}**; action: "
                  f"{(card['recommended_action'] or {}).get('action_type')} (source {r.get('action_source')}); confidence "
                  f"{card['confidence']} ({card['confidence_band']})",
                  *([f"- Action notes: {'; '.join(r['action_notes'])}"] if r.get('action_notes') else []),
                  f"- Severity: {card['severity']['level']} ({card['severity']['assessment_status']}); signals "
                  f"{[f'{x['level']}[{x['signal_index']}]' for x in card['severity']['matched_signals']]}; "
                  f"affected reporters {card['severity']['occurrence']['affected_reporters']['status']} "
                  f"{card['severity']['occurrence']['affected_reporters'].get('count')}; issues {r['severity']['issues'] or 'none'}",
                  f"- Resolution: {r['resolution']['topic']} from grounded member states "
                  f"{sorted(r['resolution']['members'].values())}; Agent 1 attributed "
                  f"{sorted((a['state'], a['agent1_verification_status']) for a in r['resolution']['agent1_attributed'])}",
                  f"- Grounding: **{g['status']}** ({g['basis']}); {len(g['statements'])} statements; structural issues "
                  f"{[i['code'] for i in g['structural_issues']] + g['action_issues'] or 'none'}; not supported "
                  f"{g['unsupported'] + g['unjudged'] or 'none'}",
                  f"- Established announcement handling: {_fmt_ids(r['established_handling'])}",
                  f"- Withheld from the card: " + ('; '.join(f"{w['statement_id']} ({w['verdict']}): {w['text']}" for w in withheld)
                                                    or 'none'),
                  f"- Temporal: {(r['temporal'] or {}).get('status')}; findings "
                  f"{[(f['code'], f['status']) for f in (r['temporal'] or {}).get('findings', [])] or 'none'}",
                  f"- ToT: {r['tot']['status']} {r['tot'].get('triggers')}"
                  + (f"; presentation {r['tot']['presentation']}; candidates "
                     f"{[(c['candidate_id'], c['action_type'], c['valid'], c['grounding'], c['issues']) for c in r['tot']['candidates']]}"
                     if r['tot']['status'] == 'COMPARED' else ''),
                  '- Review reasons: ' + ('; '.join(f"{x['code']}: {x['detail']}" for x in card['needs_review_reasons']) or 'none'),
                  '- Review notes (shown to the team lead): ' + (' | '.join(card.get('review_notes') or []) or 'none'),
                  f"- Inherited flags: {len(card['inherited_flags'])}; uncarried obligations "
                  f"{r['coverage']['uncarried_obligations'] or 'none'}; group members in other topics (outside this card) "
                  f"{len(r['coverage']['group_members_outside_this_card'])}",
                  f"- Model calls: {[c['stage'] + ':' + c['status'] for c in r['model_calls']]}; budget used {r['budget']['consumed']}",
                  '', '| Step | Purpose | Mode | Types | New evidence |', '| --- | --- | --- | --- | --- |']
        for t in r['retrieval_trace']:
            lines.append(f"| {t['step']} | {t['purpose']} | {t['version_mode']} | {','.join(t['source_types'])} | "
                         f"{_fmt_ids(t.get('new_evidence_ids', [])) if t['status'] == 'DONE' else t['status']} |")
        cited = [x['note'] or '' for x in card['supporting_sources'] if x['kind'] == 'knowledge_source']
        lines += ['', f"Cited sources: {', '.join(cited) or 'none'}", '']
    return '\n'.join(lines) + '\n'
