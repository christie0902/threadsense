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

from threadsense.agents import advisor_tot
from threadsense.agents.advice_contracts import ModelReviewItem, stable_id
from threadsense.agents.advice_inputs import coverage, load_effective_view, review_items_from_view
from threadsense.agents.advisor_checks import (
    action_issues, agent1_resolution, announcement_issues, assemble_card, authorize, build_severity, claim_issues,
    coverage_issues, dependencies, established, grounding_result, inherited_flags, normalize, presentation_issues,
    rejected_statements, sendable, statements, structural_issues, temporal_check, unauthorized,
)
from threadsense.agents.advisor_contracts import AdvisorDraft, GroundingJudgment
from threadsense.agents.advisor_evidence import (
    Budget, BudgetExhausted, ResearchTools, member_messages, model_view, open_retriever,
)
from threadsense.handoff_inputs import ROOT, file_hash, read_json
from threadsense.retrieval.config import DEFAULTS
from threadsense.severity_rubric import load_rubric

PILOT_VERSION = 'agent3-advisor-pilot-v6'
# Prompt text version, recorded in every manifest with the rule fingerprints. v6: team lead-facing writing guide and two
# STYLE ONLY examples in the draft/revision rules; display-text rules in grounding and ToT; rules sent once per request
# (agent3_readability_v1 ran v6). v6.1: grounding also receives the open upstream review flags (open_review_flags).
PROMPT_VERSION = 'agent3-advisor-prompts-v7'
# Replayed recorded drafts older than v7 are read under the last contract they satisfy (no intervention_need).
LEGACY_LABELS = {'AdvisorDraft': 'agent3-advisor-draft-v6'}
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
    'applies to that thread\'s scope and is not project guidance. Retrieved sources '
    'support guidance and history according to their "use": CURRENT_GUIDANCE may support what applies now; '
    'PRIOR_DECISION and HISTORY_ONLY explain earlier decisions, outcomes or old rules and must not be presented as current '
    'guidance; UNRESOLVED_VERSION must not be resolved by you. ANNOUNCEMENT items include routine reminders, schedules '
    'and example-collection notes: before a GUIDANCE claim relies on one, list it in announcement_assessments as relevant '
    '(same project, batch and problem) and directive (it tells people what to do), quoting the directing sentence '
    'verbatim; otherwise mark it not relevant or not directive. Read each excerpt with its status line, dates, scope, '
    'authority and recorded states. A quote with quote_kind VERBATIM must be copied exactly from one cited excerpt; '
    'otherwise set quote_kind PARAPHRASE. '
    'Coverage: before advising, fill coverage for CURRENT_GUIDANCE, ANNOUNCEMENTS, PRIOR_DECISIONS (earlier decisions, '
    'trials and their outcomes) and MEMBER_QUESTIONS (what members asked, including references to earlier workarounds or '
    'discussions). COVERED cites the evidence; NOT_APPLICABLE says why none is needed; MISSING names a gap whose '
    'follow_up query (source_types; version_mode history for past decisions, outcomes, recurrence or supersession) '
    'could find it. Request follow-ups only for support your advice actually needs; a nonempty result list is not '
    'sufficient evidence. Do not invent causes, outcomes, approvals, counts or fixes. '
    'Action: when the evidence supports a concrete step (post or align on current guidance, escalate, route to a '
    'specialist, update documentation), propose it with support_claim_ids naming all its premises (a judge will decide which are essential); it may be '
    'proposed even '
    'though the card will need team lead review. Any action other than NO_ACTION states intervention_need: the kind '
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
    'earlier review flags (already carried with the card) are not open confirmations. Severity: apply the rubric unchanged; MEDIUM or HIGH must cite a rubric signal by level, index and '
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
    'Card writing. The team lead reads these fields exactly as you write them: summary (what happened, 1-2 short '
    'sentences); proposed_action.instruction (one concrete sentence telling the team lead what to do); '
    'proposed_action.rationale (why that helps, 1-2 short sentences); proposed_action.draft_text (a copyable draft suited '
    'to the action: an announcement of about 60-120 words, with bullets when useful, or the message to send for an '
    'escalation or referral); review_note (only when something specific still needs the team lead\'s review; otherwise '
    'null). These are writing targets, not limits: keep necessary conditions, uncertainty, scope and who reported, asked, '
    'confirmed or instructed. Use familiar words: "post a reminder", not "post alignment"; "report a technical issue", not '
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
    'image. Selected action: post a reminder. summary: "Two annotators asked whether captions should include watermark '
    'text. The current guideline already answers this." proposed_action.instruction: "Post a reminder in the batch channel '
    'that captions leave out watermark text unless the watermark is the subject of the image." proposed_action.rationale: '
    '"Both questions are answered by the current guideline; one reminder gives everyone the same rule before more '
    'captions are submitted." proposed_action.draft_text: "Reminder for this batch: leave watermark text out of captions. '
    '- Exception: describe the watermark when it is the main subject of the image. - If you are unsure, ask in this thread '
    'before submitting. This follows the current captioning guideline; nothing else has changed." review_note: null. '
    'Example 2 (fictional video-timestamp batch). Supplied facts: three annotators report that timestamps move by about one '
    'second after saving; an engineer asked for task IDs; no cause is confirmed. Selected action: report a technical issue '
    'to engineering. summary: "Three annotators report that timestamps move after saving. The cause is not confirmed." '
    'proposed_action.instruction: "Report a technical issue to engineering with the affected task IDs and the steps that '
    'reproduce the shift." proposed_action.rationale: "Engineering asked for task IDs; one report with reproduction steps '
    'lets them check the save step without each annotator filing separately." proposed_action.draft_text: "Timestamps '
    'move after saving (three reports in this batch). After saving, timestamps shift by about one second. Tasks: VID-101, '
    'VID-117, VID-142. Steps: open the task, set a timestamp, save, reopen. The cause is not confirmed; please check the '
    'save step." review_note: "Confirm with engineering whether tasks saved before the fix need to be re-checked."')
DRAFT_RULES = f'{DRAFT_RULES} {WRITING_GUIDE} {STYLE_EXAMPLES}'
REVISION_RULES = (
    'Revise your previous draft once, using the follow-up retrieval results now included in the evidence. Keep every '
    'claim cited; weaken or remove claims the evidence does not support. No further retrieval will run: leave remaining '
    'gaps with follow_up null. ' + DRAFT_RULES)
GROUNDING_RULES = (
    'Judge each statement against the evidence it cites, read within the full context provided: every message of every '
    'member thread (with canonical author IDs, roles, thread starters and reactions) and every retrieved source for '
    'this topic. Citing a source '
    'is not support. A statement is SUPPORTED only if its cited evidence states or directly entails it and nothing in '
    'the context contradicts it; PARTIALLY_SUPPORTED if a material part is missing or the context qualifies it; '
    'UNSUPPORTED otherwise. A status line marking an excerpt historical, unresolved or a prior record means it cannot '
    'support what applies now. By kind: CLAIM_INCIDENT_FACT is a report of what members say, not a verified cause; '
    'CLAIM_CAUSE needs verification in the cited evidence; a Verbatim quote must match its source, a Paraphrase must '
    'preserve the meaning. Prose names no one: role wording ("the team lead instructs", "a tutor reports") must match the '
    'cited author\'s role and act (reported, asked, confirmed or instructed), plural wording needs that many distinct '
    'cited authors, and listed attributions must hold (AUTHOR wrote the cited message, THREAD_STARTER started its '
    'thread, PARTICIPANT posted in it). SUMMARY and SEVERITY_RATIONALE must follow '
    'from the evidence with no added cause, count or outcome. ACTION and ALTERNATIVE are recommendations: judge whether '
    'their premises are supported, whether the action applies to this topic and whether the rationale follows; a source '
    'need not literally prescribe the action. ACTION and operational ALTERNATIVE statements list their premises: '
    'PENDING_YOUR_VERDICT premises are judged here and are provisional, not final; REJECTED ones failed deterministic '
    'checks and support nothing; a premise with depends_on stands only if every ANNOUNCEMENT_HANDLING statement it lists '
    'is also SUPPORTED. INTERVENTION_NEED says why intervening now is needed: SUPPORTED only if the context shows that '
    'reason (an unresolved handling question, a guidance gap, an applicable pending decision, or an operational problem '
    'that needs coordination). Questions already answered in their threads are not unresolved; a general benefit ("a '
    'reminder might help") is not a need; existing guidance does not by itself rule a need out. Judge in this order: (1) announcement handling; (2) each premise\'s final status, which is your '
    'verdict on it combined with its dependencies; (3) sufficiency. Fill action_sufficiency for the ACTION and one '
    'alternative_sufficiency entry (with its statement_id) for each ALTERNATIVE that lists premises: SUFFICIENT only if '
    'premises whose final status is SUPPORTED justify the exact text as worded, including its conditions and scope; '
    'essential_statement_ids lists the premises it cannot stand without (each must have final status SUPPORTED); '
    'INSUFFICIENT if it relies on a rejected, unsupported or dependency-voided premise or goes beyond its premises; '
    'action_sufficiency null if no ACTION statement is sent. SOURCE_AGREEMENT is SUPPORTED only if the named current '
    'sources say the same thing on the point in conflict and only the superseded material differs. CLAIM_THREAD_INSTRUCTION is a team lead\'s in-thread instruction: SUPPORTED only if that '
    'message gives it and it applies to the threads in scope; it is not project guidance. HISTORICAL_RECURRENCE needs '
    'retrieved records of earlier occurrences; REPORTED_RECURRENCE only needs members saying it is happening again. AFFECTED_REPORTER needs that person\'s own message reporting that they are '
    'affected. RESOLUTION is judged against the member\'s complete thread, including messages the statement did not '
    'cite. ANNOUNCEMENT_HANDLING needs the announcement to give that directive for this topic\'s project, batch and '
    'problem (a routine reminder, schedule or example-collection note does not). OPEN_QUESTION is SUPPORTED only if the '
    'guidance and decisions in the context really leave that specific question unsettled and it is a handling or policy '
    'question for the team lead; a not-yet-diagnosed cause, pending diagnostic results or a pending expert assessment is '
    'not one. Return exactly one verdict '
    'for every statement_id. The team lead reads SUMMARY, ACTION (label, instruction, draft to copy, scope and '
    'changes), ACTION_RATIONALE, REVIEW_NOTE and OPEN_QUESTION exactly as written: judge that exact text, including its '
    'conditions, uncertainty, scope and who reported, asked, confirmed or instructed; plain wording is expected, but it '
    'must not overstate the evidence. A quoted passage must match its source exactly. open_review_flags lists the '
    'upstream review obligations still open on these threads; a REVIEW_NOTE may rely on them.')


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
        self.refused, self.input_tokens = None, None

    def __enter__(self):
        import httpx
        self._original, guard = httpx.HTTPTransport.handle_request, self

        def handle(transport, request):
            if len(guard.sent) >= guard.limit:
                guard.blocked.append(str(request.url))
                raise RequestCeilingExceeded(f'{guard.limit} HTTP request(s) per stage; {request.url} was not sent')
            if guard.input_token_limit:  # The exact body about to be sent, framework prompt included.
                messages = json.loads(request.content or b'{}').get('messages') or []
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
        self.last_requests = None
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
        self.last_input_estimate = guard.input_tokens
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
    verdict is reused only for a statement whose kind, text, evidence and attributions, and whose full evidence
    context, are unchanged. ACTION and ALTERNATIVE verdicts are not reused when they list premises: since pilot v5 their
    premises are shown as provisional with their dependencies, which changes what was judged. Anything else
    (sufficiency, source agreement) is PENDING, never invented."""
    label = 'REPLAY_RECORDED'
    replay = True
    retrieval_expansion = False  # Recorded runs predate the bounded expansion; replay keeps their retrieval.

    def __init__(self, run_dir):
        self.run_dir, self.recorded, self.reuse_log = Path(run_dir), {}, []
        for path in sorted((self.run_dir/'results').glob('*.json')):
            r = read_json(path)
            self.recorded[r['scenario']['id']] = {
                'raw': {c['stage']: c['raw'] for c in r.get('model_calls', []) if c.get('raw')},
                'failed': {c['stage']: c for c in r.get('model_calls', []) if c.get('status') == 'FAILED'},
                'statements': {s['statement_id']: s for s in (r.get('grounding') or {}).get('statements', [])},
                'context': set(r.get('evidence_ledger', {}))}
        self.fingerprint = sha256(json.dumps({k: v['raw'] for k, v in self.recorded.items()}, sort_keys=True).encode()).hexdigest()

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
        if isinstance(value, dict) and legacy and value.get('contract_version') != default:
            value['contract_version'] = legacy  # Recorded content predates newer requirements; it keeps the old rules.
        elif default and isinstance(value, dict) and value.get('contract_version') not in (None, default):
            value['contract_version'] = default  # Version label only; the recorded content is unchanged.
        return json.dumps(value, ensure_ascii=False)

    def _judgment(self, payload, rec):
        context = {e['evidence_id'] for e in payload['member_threads'] + payload['retrieved_sources']}
        verdicts = []
        def content(x):
            return x['kind'], x['text'], x['evidence_ids'], x.get('attributions', [])
        for s in payload['statements']:
            old = rec['statements'].get(s['statement_id'])
            same = (old is not None and context == rec['context'] and old.get('model_verdict') in
                    ('SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED') and content(old) == content(s) and 'premises' not in s)
            self.reuse_log.append({'scenario_id': payload['scenario_id'], 'statement_id': s['statement_id'],
                                   'reused': bool(same), 'reason': None if same else
                                   'not recorded' if old is None else 'context changed' if context != rec['context'] else
                                   'content changed' if content(old) != content(s) else
                                   'premises now shown as provisional with dependencies' if 'premises' in s else
                                   f"recorded verdict {old.get('model_verdict')}"})
            if same:
                verdicts.append({'statement_id': s['statement_id'], 'verdict': old['model_verdict'],
                                 'rationale': old.get('rationale') or 'Recorded verdict (replay).'})
        return {'verdicts': verdicts, 'action_sufficiency': None, 'alternative_sufficiency': []}


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


def _json_text(raw):
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return text


class Stages:
    """Budgeted model stages for one topic; zero retries, failures recorded and returned as None.
    `reserve` holds back calls for later stages (the final grounding call)."""

    def __init__(self, client, budget, scenario_id):
        self.client, self.budget, self.scenario_id, self.log = client, budget, scenario_id, []

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
        try:
            raw = self.client.complete(stage, {**payload, 'scenario_id': self.scenario_id, 'stage': stage,
                                               'output_schema': schema.model_json_schema()}, schema)
            entry.update(raw=raw, raw_sha256=sha256(raw.encode('utf-8')).hexdigest())
            value = schema.model_validate(json.loads(_json_text(raw)))
        except (BoundaryNotObserved, RunStateError):
            raise  # Unverifiable call accounting or unsaved run state stops the run.
        except Exception as error:  # Any provider, parsing or validation error: record it, never retry.
            self.log.append({**entry, **self._requests(), 'status': 'FAILED', 'failure_class': failure_class(error),
                             'error': f'{type(error).__name__}: {str(error)[:400]}'})
            return None
        self.log.append({**entry, **self._requests(), 'status': 'OK'})
        return value

    def _requests(self):
        stats = getattr(self.client, 'last_requests', None)
        estimate = getattr(self.client, 'last_input_estimate', None)
        return {**({'http_requests': stats} if stats is not None else {}),
                **({'input_tokens_estimate': estimate} if estimate is not None else {})}


def topic_packet(view, scenario):
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
    """Model-facing evidence: member messages without display names (model_view), then retrieved sources."""
    return ([model_view(v) for v in ledger.values() if v['origin'] == 'member_message'],
            [v for v in ledger.values() if v['origin'] == 'retrieved_source'])


def _research_payload(rules, topic, ledger, tools, rubric, interpretations):
    members, retrieved = _split(ledger)
    return {'rules': rules, 'topic': topic, 'member_evidence': members, 'agent1_interpretations': interpretations,
            'retrieved_evidence': retrieved, 'retrieval_notes': tools.notes(), 'rubric': rubric_payload(rubric),
            'limits': {'follow_up_queries': MAX_FOLLOW_UPS}}


def grounding_payload(stmts, ledger, topic, rejected=None, depends=None, review_flags=None):
    """Sendable statements plus the full topic context: every message of every member thread (canonical IDs, roles,
    thread starters, reactions) and every retrieved source, so the draft's citations do not set the judge's evidence
    window. Premises are shown as provisional (pending the judge's own verdict) with the announcements they depend on,
    never as final. `review_flags`: the upstream review obligations still open on these threads (a REVIEW_NOTE may
    rely on them)."""
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
        if 'premises' in s:
            out['premises'] = [premise(i) for i in s['premises']]
        return out
    return {'rules': GROUNDING_RULES, 'topic': topic, 'statements': [shown(s) for s in sent],
            'member_threads': members, 'retrieved_sources': retrieved, 'open_review_flags': list(review_flags or [])}


def _final_grounding(call, draft, ledger, topic, stmts, structural, actions, review_flags=None):
    """Structurally rejected statements are withheld; everything else still goes to the one semantic call."""
    rejected = rejected_statements(draft, stmts, structural, actions)
    if not sendable(stmts, rejected):
        return grounding_result(draft, ledger, stmts, structural=structural, actions=actions,
                                reason='NOTHING_CITED' if not rejected else 'ALL_STATEMENTS_REJECTED')
    judgment = call('grounding', grounding_payload(stmts, ledger, topic, rejected, dependencies(draft, ledger), review_flags),
                    GroundingJudgment)
    return grounding_result(draft, ledger, stmts, structural=structural, actions=actions, judgment=judgment,
                            ran=judgment is not None, reason='GROUNDING_CALL_FAILED_OR_OVER_BUDGET',
                            pending=getattr(call.client, 'replay', False))


def _review_items(packet, card):
    items = review_items_from_view({'records': [packet['record']]})
    linked = set(card.lineage.member_ids)
    return [ModelReviewItem.model_validate({**i.model_dump(mode='json'), 'related_card_ids': [card.card_id]})
            if set(i.member_ids) & linked or not i.member_ids else i for i in items]


NOT_RUN = {'structural_issues': [], 'action_issues': [], 'statements': [], 'unsupported': [], 'unjudged': [],
           'extraneous_verdicts': []}


def advise(scenario, *, view, retriever, client, budget, rubric, run_id, as_of, initial=None):
    """One topic. Never raises for model or budget problems; ScenarioError only for a missing topic.
    `initial` replaces the derived initial query (used to test recovery from an incomplete first pass)."""
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
    follow_ups, unfilled = [], []
    if draft is not None:
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
            revised = call('revision', {**payload, 'previous_draft': draft.model_dump(), 'follow_ups': follow_ups},
                           AdvisorDraft, reserve=1)
            draft = revised or draft
        unfilled = [g.model_dump() for g in draft.gaps]
    revised, normalization = draft is not first, []
    if draft is not None:  # Role-label and recurrence corrections, recorded; never content repair.
        draft, normalization = normalize(draft, ledger)
    flags = inherited_flags(packet['record'], packet['member_ids'], projection_gap=packet['projection_gap'])
    tot, diagnostics, temporal_pre, covered_issues, action_notes = {'status': 'NOT_TRIGGERED', 'triggers': []}, [], None, [], []
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
        draft, adopted = advisor_tot.adopt(tot, draft)  # A selected candidate may become the action; flags untouched.
        action_notes = [adopted] if adopted else []
        actions = action_issues(draft, ledger)
        stmts = statements(draft, ledger, severity=severity, alternatives=advisor_tot.alternatives(tot))
        grounding = _final_grounding(call, draft, ledger, topic, stmts, structural, actions,
                                     [{k: v for k, v in f.model_dump().items() if v} for f in flags])
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
        # Recorded supersession is credited only to announcements the final grounding verified; several current
        # sources explain a superseded section only if the final grounding judged that they agree.
        temporal = temporal_check(draft, ledger, final['handling'],
                                  {s['statement_id']: s['verdict'] for s in grounding['statements']})
        diagnostics += normalization + [
            {'code': 'ALTERNATIVE_NOT_GROUNDED' if w['kind'] == 'ALTERNATIVE' else 'WITHHELD_STATEMENT', **w}
            for w in final['withheld']]
        if draft.evidence_sufficiency == 'UNSUPPORTED' and draft.proposed_action and \
                draft.proposed_action.action_type != 'NO_ACTION':
            diagnostics.append({'code': 'UNSUPPORTED_ACTION_NOT_CARRIED', 'action': draft.proposed_action.model_dump()})
    outcome = {'draft': draft, 'ledger': ledger, 'inherited_flags': flags, 'grounding': grounding, 'temporal': temporal,
               'final': final, 'evidence_sufficiency': draft.evidence_sufficiency if draft else None,
               'coverage_issues': covered_issues, 'action_source': 'TOT' if action_notes and action_notes[0].startswith(
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
    items = _review_items(packet, card)
    covered = coverage({'records': [packet['record']]}, cards=[card], review_items=items)
    # Members of the group's other topics are outside this scenario (not lost); obligations must all be carried.
    covered = {'group_members_outside_this_card': covered['missing_members'],
               'uncarried_obligations': covered['missing_obligations']}
    return {'scenario': scenario, 'status': 'CARD', 'topic': {**topic, 'initial_query': query},
            'retrieval_trace': tools.trace, 'retrieval_notes': tools.notes(), 'follow_ups': follow_ups,
            'unfilled_gaps': unfilled, 'model_calls': call.log,
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


def prompt_fingerprints():
    """SHA-256 of every rule text and output schema the model sees."""
    from threadsense.agents.advisor_contracts import ToTComparison
    digest = lambda text: sha256(text.encode('utf-8')).hexdigest()  # noqa: E731
    return {'prompt_version': PROMPT_VERSION, 'draft_rules': digest(DRAFT_RULES), 'revision_rules': digest(REVISION_RULES),
            'writing_guide': digest(WRITING_GUIDE), 'style_examples': digest(STYLE_EXAMPLES), 'grounding_rules': digest(GROUNDING_RULES),
            'tot_rules': digest(advisor_tot.RULES),
            'schemas': {s.__name__: digest(json.dumps(s.model_json_schema(), sort_keys=True))
                        for s in (AdvisorDraft, GroundingJudgment, ToTComparison)},
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
        tokens, counter = _tokens(task_description({**payload, 'output_schema': AdvisorDraft.model_json_schema()}, AdvisorDraft))
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
