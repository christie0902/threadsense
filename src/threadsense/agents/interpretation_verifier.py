"""Deterministic checks against source metadata and validated evidence.

The controller combines source-only analysis with fresh prose assessments.
This module never calls a model or rewrites an interpretation.
"""

import re

from threadsense.agents.contracts import (
    DecisionCoverageStatus, DecisionEvidenceAudit, ReplyContribution,
    ResolutionState, ThreadInterpretation, VerificationCategory, VerificationFinding,
)
from threadsense.agents.decision_evidence_audit import validate_decision_evidence_audit
from threadsense.agents.thread_interpreter import (
    AUTHORITY_ENDORSEMENTS, get_authority_eligible_message_ids, validate_interpretation_references,
)
from threadsense.models import Role, Thread
from threadsense.terminology import get_terms


ANSWER_TYPES = {ReplyContribution.COMPLETE_ANSWER, ReplyContribution.PARTIAL_ANSWER}


def find_glossary_conflicts(interpretation: ThreadInterpretation) -> list[str]:
    """Detect explicit acronym expansions conflicting with the official glossary."""
    content = "\n".join((interpretation.summary, interpretation.central_question or "",
                         interpretation.resolution_rationale))
    conflicts = []
    terms = get_terms()
    for term, definition in terms.items():
        if not term.isalpha() or not term.isupper():
            continue
        approved = " ".join(definition.lower().split())
        # A comma can introduce explanatory prose: LT is still "Label Tool".
        short_definition = approved.split(",", 1)[0]
        allowed = {approved, short_definition}
        if " or " in short_definition:
            allowed.update(short_definition.split(" or "))
        patterns = (
            rf"\b{re.escape(term)}\s*\(([^()]{{1,80}})\)",
            rf"\b{re.escape(term)}\s+(?:means|stands for|is short for|is an abbreviation for)\s+([^.;\n]{{1,80}})",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                claimed = " ".join(match.group(1).lower().split())
                # A rejected alternative is not an asserted expansion.
                if re.match(r"(?:not|never|rather than)\b", claimed):
                    continue
                claimed = re.sub(r"^(?:a|an)\s+", "", claimed)
                if any(claimed == value or claimed.startswith(value + " ")
                       or claimed.startswith(value + ",") for value in allowed):
                    continue
                conflicts.append(f"{term} ({match.group(1)}) conflicts with approved definition: {definition}")
    if terms.get("QN", "").strip().lower() == "quarantine":
        for wrong_meaning in ("quality issue", "quality note"):
            escaped = re.escape(wrong_meaning)
            patterns = (
                rf"\b{escaped}\s*\(\s*QN\s*\)",
                rf"\bQN\s+is\s+(?:an?\s+)?{escaped}\b",
            )
            if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns):
                conflicts.append(f"QN incorrectly expanded as '{wrong_meaning}'; approved definition: Quarantine")
    return list(dict.fromkeys(conflicts))


def verify_interpretation(
    thread: Thread,
    interpretation: ThreadInterpretation,
    audit: DecisionEvidenceAudit | None = None,
) -> list[VerificationFinding]:
    """Return discrepancies without an LLM call or interpretation mutation.

    audit=None runs only structural/terminology checks. The workflow must obtain
    a validated audit before assigning VERIFIED.
    """
    findings: list[VerificationFinding] = []
    source_ids = {message.message_id for message in thread.messages}

    def add(category, explanation, ids=(), fields=()):
        findings.append(VerificationFinding(category=category, explanation=explanation,
                                            evidence_message_ids=[item for item in dict.fromkeys(ids) if item in source_ids],
                                            disputed_fields=list(fields)))

    try:
        ThreadInterpretation.model_validate(interpretation.model_dump())
        validate_interpretation_references(thread, interpretation)
    except (ValueError, TypeError) as exc:
        add(VerificationCategory.EVIDENCE, str(exc), fields=("thread_id", "authority_evidence_message_ids",
                                                          "authoritative_response_present"))
    if not interpretation.summary.strip():
        add(VerificationCategory.SUMMARY, "The interpretation summary is empty.", fields=("summary",))
    if not interpretation.resolution_rationale.strip():
        add(VerificationCategory.RESOLUTION, "The interpretation has no resolution rationale.",
            fields=("resolution_rationale",))
    message_ids = [message.message_id for message in thread.messages]
    if len(message_ids) != len(set(message_ids)):
        add(VerificationCategory.EVIDENCE, "Original Slack thread contains duplicate message IDs.")
    if message_ids.count(thread.thread_id) != 1:
        add(VerificationCategory.EVIDENCE, "Original Slack thread must have exactly one root message.")
    cited = interpretation.authority_evidence_message_ids
    if len(cited) != len(set(cited)):
        add(VerificationCategory.EVIDENCE, "Duplicate authority evidence IDs.", cited,
            ("authority_evidence_message_ids",))
    if thread.thread_id in cited:
        add(VerificationCategory.AUTHORITY, "A root question cannot serve as its own authoritative reply.",
            (thread.thread_id,), ("authority_evidence_message_ids", "authoritative_response_present"))

    author_roles = {}
    for message in thread.messages:
        if message.author_id in author_roles and author_roles[message.author_id] != message.author_role:
            add(VerificationCategory.EVIDENCE, "Conflicting author-role metadata for the same user.", (message.message_id,))
        author_roles[message.author_id] = message.author_role
        if message.author_role not in set(Role):
            add(VerificationCategory.EVIDENCE, "Unknown speaker role.", (message.message_id,))
    for message in thread.messages:
        for reaction in message.reactions:
            users = set(reaction.users)
            if len(users) != len(reaction.users):
                add(VerificationCategory.EVIDENCE, "Reaction contains duplicate reactor IDs.", (message.message_id,))
            if reaction.count is not None and reaction.count != len(users):
                add(VerificationCategory.EVIDENCE, "Reaction count does not match its reactor IDs.", (message.message_id,))
            if set(reaction.reactor_roles) - users:
                add(VerificationCategory.EVIDENCE, "Reaction roles cite users absent from the reaction.", (message.message_id,))
            if reaction.name in AUTHORITY_ENDORSEMENTS and users - set(reaction.reactor_roles):
                add(VerificationCategory.EVIDENCE, "Endorsement reaction has unverified reactor roles.",
                    (message.message_id,), ("authoritative_response_present", "authority_evidence_message_ids"))
            for user_id, role in reaction.reactor_roles.items():
                if role not in set(Role) or (user_id in author_roles and author_roles[user_id] != role):
                    add(VerificationCategory.EVIDENCE, "Reaction role conflicts with known speaker metadata.", (message.message_id,))

    for conflict in find_glossary_conflicts(interpretation):
        add(VerificationCategory.TERMINOLOGY, conflict,
            fields=("summary", "central_question", "resolution_rationale"))
    if audit is None:
        return findings
    try:
        audit = DecisionEvidenceAudit.model_validate(audit.model_dump())
        validate_decision_evidence_audit(thread, audit, interpretation)
    except (ValueError, TypeError) as exc:
        add(VerificationCategory.EVIDENCE, f"Decision-evidence audit is invalid: {exc}",
            fields=("central_question", "resolution_state", "authority_evidence_message_ids"))
        return findings
    findings.extend(audit.interpretation_findings)

    prose_categories = {
        "summary": VerificationCategory.SUMMARY,
        "central_question": VerificationCategory.CENTRAL_QUESTION,
        "resolution_rationale": VerificationCategory.RESOLUTION,
    }

    for assessment in audit.prose_assessments:
        if assessment.verdict == "SUPPORTED":
            continue

        field = assessment.unit_id.split(":", 1)[0]

        findings.append(
            VerificationFinding(
                category=prose_categories[field],
                explanation=(
                    f"Prose unit {assessment.unit_id}: "
                    f"{assessment.verdict}.\n"
                    f"Candidate: {assessment.candidate_text}\n"
                    f"Source establishes: "
                    f"{assessment.source_interpretation}\n"
                    f"Reason: {assessment.explanation}"
                ),
                evidence_message_ids=list(
                    assessment.evidence_message_ids
                ),
                evidence_quotes=list(
                    assessment.evidence_quotes
                ),
                disputed_fields=[field],
            )
        )

    root_ids = (thread.thread_id,)
    if audit.requested_decisions and not (interpretation.central_question or "").strip():
        add(VerificationCategory.CENTRAL_QUESTION, "The audit found a root request, but the interpretation has no central question.",
            root_ids, ("central_question",))
    if not audit.requested_decisions:
        if interpretation.central_question is not None:
            add(VerificationCategory.CENTRAL_QUESTION, "The audit found no requested decision, but the interpretation supplies a question.",
                root_ids, ("central_question",))
        # There is no N/A value in the saved interpretation schema. For an
        # announcement, leave its legacy label alone and audit its prose.
    for uncertainty in audit.uncertainties:
        add(VerificationCategory.OTHER, f"Independent audit uncertainty: {uncertainty}", root_ids,
            ("central_question", "resolution_state", "authority_evidence_message_ids"))
    for assessment in audit.reply_assessments:
        if assessment.contribution == ReplyContribution.UNCERTAIN:
            add(VerificationCategory.EVIDENCE, f"Reply contribution remains uncertain: {assessment.explanation}",
                (assessment.message_id,), ("resolution_state", "authority_evidence_message_ids"))

    statuses = [item.status for item in audit.decision_coverage]
    if DecisionCoverageStatus.UNCERTAIN in statuses:
        add(VerificationCategory.RESOLUTION, "At least one requested decision has uncertain answer coverage.",
            root_ids, ("resolution_state", "resolution_rationale"))
    elif statuses:
        if all(status == DecisionCoverageStatus.ANSWERED for status in statuses):
            expected_resolution = ResolutionState.RESOLVED_IN_THREAD
        elif all(status == DecisionCoverageStatus.UNANSWERED for status in statuses):
            expected_resolution = ResolutionState.UNRESOLVED
        else:
            expected_resolution = ResolutionState.PARTIALLY_RESOLVED
        if interpretation.resolution_state != expected_resolution:
            add(VerificationCategory.RESOLUTION,
                f"Independent decision coverage establishes {expected_resolution.value}; interpretation reports {interpretation.resolution_state.value}. "
                + " ".join(item.rationale for item in audit.decision_coverage),
                [item.message_id for item in audit.reply_assessments], ("resolution_state", "resolution_rationale"))

    messages = {message.message_id: message for message in thread.messages}
    eligible = get_authority_eligible_message_ids(thread) - {thread.thread_id}
    authority_answers = set()
    uncertain_engineers = set()
    for item in audit.reply_assessments:
        if item.contribution not in ANSWER_TYPES or item.message_id not in eligible:
            continue
        if messages[item.message_id].author_role == Role.ENGINEER:
            if item.technical_scope is None:
                uncertain_engineers.add(item.message_id)
            if item.technical_scope is not True:
                continue
        authority_answers.add(item.message_id)
    # Uncited uncertainty cannot change an authority flag already established
    # by cited, known authoritative guidance. Missing all known evidence or
    # citing the uncertain engineer still requires a concrete finding.
    if uncertain_engineers.intersection(cited) or (uncertain_engineers and not authority_answers):
        add(VerificationCategory.AUTHORITY, "Engineer answer has unverified technical scope; role eligibility alone is insufficient.",
            sorted(uncertain_engineers), ("authoritative_response_present", "authority_evidence_message_ids"))
    unsupported = set(cited) - authority_answers
    if unsupported:
        add(VerificationCategory.AUTHORITY,
            f"Cited messages {sorted(unsupported)} are not substantive answers with eligible authority and, for engineers, technical relevance.",
            sorted(unsupported), ("authoritative_response_present", "authority_evidence_message_ids"))
    if authority_answers and not set(cited).intersection(authority_answers):
        add(VerificationCategory.AUTHORITY, "The audit found substantive metadata-backed authoritative guidance omitted from authority evidence.",
            sorted(authority_answers), ("authoritative_response_present", "authority_evidence_message_ids"))
    return findings
