"""Single-request inventory consolidation with deterministic v5 compatibility exports."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import json
import re

from threadsense.agents.topic_contracts import (
    TopicConsolidation, ResponseEnvelope, InventoryTopic, ImpactProposal,
)
from threadsense.agents.topic_diagnostics import ConsolidationValidationError, describe_exception, diagnostic
from threadsense.agents.topic_evidence import evidence_catalog, resolve_cited_fields, resolve_reference, tl_endorsements
from threadsense.agents.operational_severity import (
    CRITERIA_V2 as CRITERIA, RUBRIC_V2 as RUBRIC, RUBRIC_VERSION_V2 as RUBRIC_VERSION,
)
from threadsense.agents.topic_requests import request_body
from threadsense.handoff_inputs import IDENTITY, identity, member_id, digest
from threadsense.models import Thread

PROMPT_VERSION = 'agent2-inventory-v6'
EXPORT_ADAPTER_VERSION = 'inventory-to-display-v3'
RULES = """Consolidate factual topics from original Slack messages and the approved glossary.
Assign every member alias exactly once; split unrelated topics. Cite only exact
topic-local evidence IDs. Traceable IDs alone do not establish support for a claim.
Keep a concise shared issue and supported differences; invent no causal explanation,
policy precedence, attempted/failed workaround, impact, or harmful-content contrast.
Omit exact counts of threads with answers or guidance from generated synthesis and
differences. Python derives these counts from distinct original member identities
in the validated inventory, not the number of items or messages. Describe the actual
supported difference and preserve its conditions without an unnecessary exact count.

Record substantive content ONCE in inventory. Each item has a topic-local item_id
and one evidence_id. Do not copy source quotations into inventory: Python supplies
the full original message and its qualifiers, identities, authors and reactions.
Only synthesis, differences, uncertainty notes and impact observations require generated prose.
A message may supply multiple items, e.g. diagnostic request and submission condition.
Distinguish QUESTION (actual handling/information question), DIAGNOSTIC_REQUEST
(request for checks/details, not an answer), ANSWER (scoped substantive reply),
INSTRUCTION, FACT (reported, not independently confirmed), ANNOUNCEMENT and CONTEXT.
An actual request for handling or a decision is QUESTION, not FACT or a request
for diagnostics. A diagnostic asks for checks/details; retain the original handling
question independently. Context describing the task is not an ANSWER about handling.
ANSWER requires an explicit substantive response. Set answer_status=TENTATIVE for
unconfirmed advice or DIRECT for an explicit scoped answer; all other kinds use null.
Question links to tentative advice remain PARTIAL, never ANSWERED.
Quoted or rhetorical questions are not automatically genuine questions. Never invent
questions from a factual incident or diagnostic. Announcements can contain instructions
without questions. Do not repeat items in independent answer/guidance/question lists.
Classify announced information as ANNOUNCEMENT from its content, not its channel.
Record an announced instruction as an additional INSTRUCTION item on that source.
One message can report a fact, issue an instruction and state its condition.
Do not make a reply question into a root question.

Every member needs substantive inventory content, not just context or raw retention.
Account for every message with one or more items OR an explicit NON_SUBSTANTIVE or
UNCERTAIN disposition with reason. Uncertain meaning must remain visible, never default
to NONE. Preserve all actual unanswered questions and scoped TL instructions, including
those in replies. Question items require OPEN with no answer links, or PARTIAL/ANSWERED
with answer_item_ids pointing to ANSWER items in that SAME member conversation.
Diagnostics cannot close questions. An answer to a narrower task cannot resolve a
broader question in another thread. Tentative advice must remain tentative and PARTIAL.
For every PARTIAL/ANSWERED link, check the target item_id, its ANSWER kind, its
original member conversation and the substance of its reply. FACT, CONTEXT,
DIAGNOSTIC_REQUEST and INSTRUCTION items cannot satisfy an answer link. One source
message may have several roles: link its substantive ANSWER item, not another item
that happens to reference the same message. Never relabel an item ANSWER solely to
make a link pass. Diagnostics may coexist with a valid partial answer; retain both
without letting diagnostic requests supply the answer. A related answer in another
thread may be relevant context but cannot establish that this thread was answered.
When no eligible answer supports resolution, keep the question OPEN with no links
and retain useful guidance separately. Do not delete an unanswered handling question.
Compare the full scope of each question with what the reply actually settles.
ANSWERED requires an explicit substantive answer covering the complete question
within the reply's stated conditions. PARTIAL requires a substantive component
answered while another remains unresolved; OPEN applies when no substantive
component is answered. Reporting instructions or troubleshooting may be useful
guidance without deciding the requested handling or policy choice. A request to
collect information or a statement withholding a decision is procedural guidance,
not itself an ANSWER to that decision. Do not treat a related next step as implicit
permission or a completed decision. Retain genuine scoped answers, tentative advice,
TL endorsements and conditions; a reply can contain both guidance and an answer.
Retain relevant differences between reported symptoms, and distinguish task labels
from operational impact. Use glossary meanings consistently.

BEGIN SYNTHETIC QUESTION-SCOPE CONTRAST (illustration only, not source evidence)
The SYNTH_* references below are fictional and must never appear in your response;
use only evidence IDs from the actual input evidence_catalog.
Same reply in two separate hypothetical conversations: "Send the task ID and error
screenshot to the tool-support queue."
A. Question: "Where should I report an export failure?" The reply settles the
requested reporting location. Existing inventory representation:
[{"item_id":"SYNTH_Q","evidence_id":"SYNTH_E_Q","kind":"QUESTION","answer_status":null,"question":{"status":"ANSWERED","answer_item_ids":["SYNTH_A"]}},
 {"item_id":"SYNTH_A","evidence_id":"SYNTH_E_R","kind":"ANSWER","answer_status":"DIRECT","question":null}]
B. Question: "May I submit the incomplete export?" The same reply gives reporting
guidance but no submission decision; no substantive component of this question is
answered. Existing inventory representation:
[{"item_id":"SYNTH_Q","evidence_id":"SYNTH_E_Q","kind":"QUESTION","answer_status":null,"question":{"status":"OPEN","answer_item_ids":[]}},
 {"item_id":"SYNTH_G","evidence_id":"SYNTH_E_R","kind":"INSTRUCTION","answer_status":null,"question":null}]
PARTIAL requires an actual substantive component of the question to be answered,
not merely helpful procedure. ANSWERED requires the complete requested decision or
information to be settled within the reply's conditions. An indirect but unambiguous
answer can suffice; exact keyword repetition is unnecessary. Guidance and authority
alone do not establish complete resolution. Do not reopen genuinely complete answers.
END SYNTHETIC QUESTION-SCOPE CONTRAST

QUESTION UNCERTAINTY HANDOFF (response v6)
For each QUESTION, retain its chosen status and answer links. Also provide
resolution_confidence (0 to 1, or null if unassessed) and uncertainty_note (cited
text, or null when no specific uncertainty is identified). Confidence concerns
your judgment of the question's resolution, independently of operational severity
and inherited Agent 1 reliability. It is an uncalibrated self-assessment, not a
measured probability; do not derive it from review flags or count of messages.
When scope or meaning is ambiguous, you may choose the most plausible supported
interpretation, with appropriately lower confidence and a brief specific note
stating what remains uncertain or needs research. This also applies to ANSWERED:
that label must not hide a remaining decision. Cite exact evidence IDs from that
question's own member conversation, including relevant reply guidance. Do not
force every ambiguous case OPEN; retain genuinely complete scoped answers.
Uncertainty does not supply evidence: unsupported decisions, false authority or
invented consequences remain unsupported even at low confidence. Existing answer
link, membership, guidance, condition and severity requirements still apply.
The synthetic examples above illustrate status/links only; actual questions must
also include both v6 uncertainty fields. Downstream research receives every question,
its original sources, raw judgment and review obligations, including ANSWERED items.

Do not generate authority labels. Python supplies author roles and eligible TL reaction
users/targets. Endorsement applies only to that reply with its conditions; eyes is not
approval. Inherited disputes remain provisional; repeated claims cannot clear them.

Provide preliminary impact in the SAME response. Cite each applicable rubric criterion
and its observation once; Python derives the level, rubric version and provisional
metadata. Criteria must imply one unambiguous level. Retain affected_scope only where
evidenced, otherwise null. REPORTED_RISK differs from OBSERVED_OUTCOME; actual scope
must not expand to all users. limited_demonstrated_consequence requires OBSERVED_OUTCOME
of limited OPERATIONAL impact, not harmless task content. insufficient_impact_evidence
uses INSUFFICIENT_EVIDENCE and explains what is unknown; non_operational uses
NON_OPERATIONAL, only for clearly non-operational content. Neither is an empty list.
Use impact=null for an explicitly unassessed section. A reported conflict or request
for clarification does not establish an observed operational outcome.
For substantial_blockage cite inability to perform/submit work; quality/safety risk
requires actual operational evidence beyond task vocabulary. Review flags, unanswered
questions, number of members and minor/major task categories do not set severity.
Before selecting a lower-impact criterion, evaluate explicit inability to perform
or complete assigned work against substantial_blockage. Unknown root cause or
unknown extent does not erase an explicitly reported blockage. Use only the actual
reported scope; isolated keywords do not establish HIGH, and do not invent broader
scope or quality/safety consequences. Distinguish attributed reports of impact from
independently confirmed outcomes: OBSERVED_OUTCOME requires a concrete effect the
source describes as having occurred, with attribution preserved. REPORTED_RISK
requires an evidenced prospective risk, not a speculative hypothetical consequence.
A handling question or reported document disagreement does not automatically
establish operational impact. Missing impact evidence may yield UNKNOWN with
insufficient_impact_evidence; never fill the gap with speculative harm.
Select the controlling rubric level supported by the source, then include only
supported criteria consistent with that one level. Do not combine levels to express
uncertainty about cause, extent or lesser observations. Preserve relevant lesser
observations in shared_issue or relevant_differences where supported, and describe
unknown cause/scope in the observation or affected_scope=null without erasing known
impact. If no operational level is supported, use UNKNOWN rather than guessing.
In each criterion's existing observation.text, identify the operational consequence
or supported risk, cite the original evidence_ids, and explain how that effect and
its scope meet the selected criterion. Do not merely restate the topic or that
clarification is requested. Document disagreement, an open question, or a request
to check versions does not by itself establish delay, rework, incorrect labeling or
blocked work. If the source does not establish sufficient impact, preserve UNKNOWN.
For prospective risk, state the source-supported mechanism connecting the issue to
the operational consequence; observed harm is not required, but a plausible invented
mechanism is not evidence. Preserve HIGH for explicit substantial blockage even if
cause, volume or broader extent is unknown. These are semantic judgments: valid
citations and consistent criteria do not prove the quoted evidence supports them.
HIGH routes to nonblocking review; LOW/N/A cannot clear flags. Agent 3 may later record
a separate researched assessment. No research, actionability or recommendations.
One independent request, no tools, verifier, retries or repair. Return JSON matching
the API response_format. Do not output schema_version or other fixed metadata;
Python supplies version 6 from trusted configuration.
"""


def validate_input(payload):
    if payload.get('schema_version') != 2 or not payload.get('members'):
        raise ValueError('Expected a nonempty schema v2 canonical candidate.')
    seen = set()
    for member in payload['members']:
        key = identity(member)
        if key in seen or member['member_id'] != member_id(member):
            raise ValueError('Duplicate or mismatched full member identity.')
        seen.add(key)
        record, source = member['agent1_record'], member['original_thread']
        Thread.model_validate(source)
        if identity(record) != key or identity(source) != key:
            raise ValueError('Source/candidate/member identity mismatch.')
        if key[:2] != (payload['project_id'], payload['batch_id']):
            raise ValueError('Candidate crosses project/batch scope.')
        if digest(record['interpretation']) != record['candidate_sha256'] or digest(source) != record['input_sha256']:
            raise ValueError('Member candidate/source fingerprint mismatch.')
        ids = [m['message_id'] for m in source['messages']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate source message identity.')
    return payload['members']


def build_request(payload, glossary, model):
    validate_input(payload)
    aliases, catalog = evidence_catalog(payload)
    return request_body(model, f'Prompt version: {PROMPT_VERSION}\n' + RULES, {
        'schema_version': 6, 'candidate_group_id': payload['candidate_group_id'],
        'project_id': payload['project_id'], 'batch_id': payload['batch_id'],
        'approved_glossary': dict(glossary), 'provisional_operational_severity_rubric': RUBRIC,
        'members': [{'member_id': alias, **{k: m[k] for k in IDENTITY},
                     'interpretation_reliability': m['agent1_record']['verification_status'],
                     'review_required': m['agent1_record']['review_required'],
                     'disputed_fields': m['agent1_record']['provisional_fields']}
                    for alias, m in aliases.items()],
        'evidence_catalog': [{**{k: v for k, v in e.items() if k != 'canonical_member_id'},
                              'eligible_tl_endorsements': tl_endorsements(e)} for e in catalog.values()],
    }, response_schema_version=6)


def cited_units(value, path=()):
    if isinstance(value, dict):
        if 'evidence_ids' in value:
            yield path, value
        for key, item in value.items():
            yield from cited_units(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from cited_units(item, (*path, index))


def fail(category, message, path=(), entry=None):
    raise ConsolidationValidationError(category, message, path, evidence_reference=entry,
                                       member_id=entry.get('canonical_member_id') if entry else None)


def check_reference(eid, topic, catalog, path):
    if eid not in catalog:
        fail('invalid_evidence_reference', 'Unknown evidence ID.', path, {'evidence_id': eid})
    entry = catalog[eid]
    if entry['member_id'] not in topic.member_ids:
        fail('cross_topic_evidence', 'Citation crosses topic membership.', path, entry)
    return entry


def check_citations(value, topic, catalog, path):
    for loc, unit in cited_units(value, path):
        if len(unit['evidence_ids']) != len(set(unit['evidence_ids'])):
            fail('duplicate_evidence', 'Duplicate evidence IDs.', loc)
        for i, eid in enumerate(unit['evidence_ids']):
            check_reference(eid, topic, catalog, (*loc, 'evidence_ids', i))


def validate_facts(payload, topics):
    aliases, catalog = evidence_catalog(payload)
    if Counter(mid for t in topics for mid in t.member_ids) != Counter(aliases.keys()):
        fail('membership', 'Assign every member exactly once.', ('topics',))
    for ti, topic in enumerate(topics):
        path = ('topics', ti)
        check_citations(topic.model_dump(), topic, catalog, path)
        items = {item.item_id: item for item in topic.inventory}
        if len(items) != len(topic.inventory):
            fail('inventory', 'Duplicate item IDs.', (*path, 'inventory'))
        substantive, covered = set(), set()
        for index, item in enumerate(topic.inventory):
            loc = (*path, 'inventory', index)
            entry = check_reference(item.evidence_id, topic, catalog, loc)
            covered.add(item.evidence_id)
            if item.kind != 'CONTEXT':
                substantive.add(entry['member_id'])
            if item.kind == 'ANSWER' and not entry['is_reply']:
                fail('answer_evidence', 'An ANSWER requires a source reply.', loc, entry)
            note = getattr(item.question, 'uncertainty_note', None)
            if note:
                for eid in note.evidence_ids:
                    if catalog[eid]['member_id'] != entry['member_id']:
                        fail('question_uncertainty', 'Question uncertainty must cite its own member conversation.', loc, entry)
            for link in item.question.answer_item_ids if item.question else []:
                answer = items.get(link)
                if (not answer or answer.kind != 'ANSWER' or answer.evidence_id not in catalog
                        or catalog[answer.evidence_id]['member_id'] != entry['member_id']):
                    fail('answer_evidence', 'Question links require scoped ANSWER items in the same thread.', loc, entry)
                if item.question.status == 'ANSWERED' and answer.answer_status == 'TENTATIVE':
                    fail('answer_evidence', 'Tentative advice cannot establish confirmed resolution; retain PARTIAL.', loc, entry)
        dispositions = [d.evidence_id for d in topic.dispositions]
        for index, eid in enumerate(dispositions):
            check_reference(eid, topic, catalog, (*path, 'dispositions', index))
        expected = {eid for eid, e in catalog.items() if e['member_id'] in topic.member_ids}
        missing = sorted(expected - covered - set(dispositions))
        missing_members = sorted(set(topic.member_ids) - substantive)
        detail = {'missing_evidence_ids': missing, 'missing_member_aliases': missing_members,
                  'missing_member_ids': [aliases[mid]['member_id'] for mid in missing_members],
                  'missing_sources': [resolve_reference(catalog[eid]) for eid in missing]}
        if missing_members:
            fail('membership', f"Every member needs substantive inventory representation; missing members {missing_members}; unaccounted evidence {missing}.", path, detail)
        if len(set(dispositions)) != len(dispositions) or covered & set(dispositions) or covered | set(dispositions) != expected:
            detail['contradictory_evidence_ids'] = sorted(covered & set(dispositions))
            fail('source_coverage', f"Every message needs items OR one explicit disposition; unaccounted evidence {missing}; no inferred dispositions.", path, detail)
    return topics


# These lexical cues only raise review flags; they establish no meaning/authority.
DIRECTIVE = re.compile(
    r'\b(?:please|must|do not|should|need to|make sure)\b|(?:^|[.!?]\s+)(?:add|keep|report|check|capture|attach|verify|provide|send)\b',
    re.IGNORECASE,
)


def coverage_warnings(payload, topic, ti, catalog):
    warnings = []
    for eid, entry in catalog.items():
        if entry['member_id'] not in topic.member_ids:
            continue
        kinds = {i.kind for i in topic.inventory if i.evidence_id == eid}
        reasons = []
        if '?' in entry['quote'] and not kinds & {'QUESTION', 'DIAGNOSTIC_REQUEST'}:
            reasons.append('Question punctuation without a question/diagnostic item; inspect quoted or rhetorical context.')
        if not entry['is_reply'] and '?' in entry['quote'] and 'DIAGNOSTIC_REQUEST' in kinds and 'QUESTION' not in kinds:
            reasons.append('Root question classified only as diagnostic; inspect whether a handling/information question was omitted.')
        answers = {i.item_id for i in topic.inventory if i.evidence_id == eid and i.kind == 'ANSWER'}
        links = {link for i in topic.inventory if i.question for link in i.question.answer_item_ids}
        if answers - links:
            reasons.append('Unlinked answer item; inspect whether this is context or tentative advice rather than a substantive answer.')
        if DIRECTIVE.search(entry['quote']) and not kinds & {'INSTRUCTION', 'DIAGNOSTIC_REQUEST', 'ANSWER'}:
            reasons.append('Directive cue without guidance treatment; source meaning needs review.')
        if any(d.evidence_id == eid and d.disposition == 'UNCERTAIN' for d in topic.dispositions):
            reasons.append('Explicit uncertain source disposition.')
        for reason in reasons:
            warnings.append(diagnostic(payload, 'coverage_review', reason, ('topics', ti, 'inventory'),
                                       evidence_reference=entry, member_id=entry['canonical_member_id']))
    return warnings


def unknown_severity(reason):
    return {'level': 'UNKNOWN', 'rubric_version': RUBRIC_VERSION, 'severity_is_provisional': True,
            'assessor': 'agent2', 'assessment_status': 'UNASSESSED', 'reason': reason,
            'matched_criteria': [], 'rationale': None, 'work_blockage': None, 'affected_scope': None,
            'quality_or_safety_consequences': None, 'evidence_basis': 'INSUFFICIENT_EVIDENCE'}


def derive_severity(raw, topic, catalog, ti):
    proposal = ImpactProposal.model_validate(raw)
    path = ('topics', ti, 'impact')
    check_citations(proposal.model_dump(), topic, catalog, path)
    criteria = [c.criterion for c in proposal.criteria]
    levels = {CRITERIA[c]['level'] for c in criteria}
    if len(criteria) != len(set(criteria)) or len(levels) != 1:
        fail('severity_consistency', 'Criteria must be unique and imply one unambiguous rubric level.', path)
    level = levels.pop()
    for criterion in proposal.criteria:
        required = {'UNKNOWN': {'INSUFFICIENT_EVIDENCE'}, 'N/A': {'NON_OPERATIONAL'},
                    'LOW': {'OBSERVED_OUTCOME'}}.get(level, {'REPORTED_RISK', 'OBSERVED_OUTCOME'})
        if criterion.basis not in required:
            fail('severity_consistency', 'Impact basis contradicts the rubric criterion.', path)
    def combine(entries):
        if not entries:
            return None
        return {'text': ' '.join(e.observation.text for e in entries),
                'evidence_ids': list(dict.fromkeys(eid for e in entries for eid in e.observation.evidence_ids))}
    bases = list(dict.fromkeys(c.basis for c in proposal.criteria))
    return {'level': level, 'rubric_version': RUBRIC_VERSION, 'severity_is_provisional': True,
            'assessor': 'agent2', 'assessment_status': 'ASSESSED', 'matched_criteria': criteria,
            'rationale': combine(proposal.criteria),
            'work_blockage': combine([c for c in proposal.criteria if c.criterion == 'substantial_blockage']),
            'quality_or_safety_consequences': combine([c for c in proposal.criteria if c.criterion in {'material_quality_risk', 'material_safety_risk'}]),
            'affected_scope': proposal.affected_scope.model_dump() if proposal.affected_scope else None,
            'evidence_basis': bases[0] if len(bases) == 1 else 'MIXED', 'criterion_evidence': proposal.model_dump()['criteria']}


@dataclass
class ParsedConsolidation:
    topics: list
    severities: list
    severity_proposals: list
    severity_diagnostics: list
    coverage_diagnostics: list


def validate_output(payload, analysis):
    validate_input(payload)
    validate_facts(payload, analysis.topics)
    return analysis


def parse_response(payload, raw, *, response_schema_version=6):
    validate_input(payload)
    if response_schema_version not in {5, 6}:
        raise ValueError('Unsupported response version; historical replay must be explicit.')
    contract = InventoryTopic
    if response_schema_version == 5:
        from threadsense.agents.topic_contracts_v5 import InventoryTopic as contract
    envelope = ResponseEnvelope.model_validate_json(raw)
    topics = [contract.model_validate({k: v for k, v in t.items() if k != 'impact'}) for t in envelope.topics]
    validate_facts(payload, topics)  # Severity cannot make invalid facts accepted.
    _, catalog = evidence_catalog(payload)
    severities, proposals, errors, warnings = [], [], [], []
    for ti, (topic, original) in enumerate(zip(topics, envelope.topics)):
        proposal = original.get('impact')
        proposals.append(deepcopy(proposal))
        if 'impact' in original and proposal is None:
            severities.append(unknown_severity('Explicitly unassessed impact.'))
            errors.append([diagnostic(payload, 'severity_unassessed', 'Impact explicitly unassessed; retain for review.', ('topics', ti, 'impact'))])
            warnings.append(coverage_warnings(payload, topic, ti, catalog))
            continue
        try:
            severities.append(derive_severity(proposal, topic, catalog, ti))
            errors.append([])
        except ValueError as error:
            details = describe_exception(payload, error)
            for detail in details:
                if detail['field_path'][:3] != ['topics', ti, 'impact']:
                    detail['field_path'] = ['topics', ti, 'impact', *detail['field_path']]
                detail['stage'] = 'severity'
            errors.append(details)
            severities.append(unknown_severity('Impact proposal rejected; factual consolidation retained.'))
        warnings.append(coverage_warnings(payload, topic, ti, catalog))
    return ParsedConsolidation(topics, severities, proposals, errors, warnings)


def inventory_member_counts(topic, catalog):
    """Count classified source conversations, not items or semantic truth."""
    counts = {}
    for name, kinds in (
        ('answers', {'ANSWER'}),
        ('guidance', {'ANSWER', 'INSTRUCTION', 'DIAGNOSTIC_REQUEST'}),
    ):
        evidence_ids = sorted({i.evidence_id for i in topic.inventory if i.kind in kinds})
        members = sorted({catalog[eid]['canonical_member_id'] for eid in evidence_ids})
        counts[name] = {'kinds': sorted(kinds), 'member_count': len(members),
                        'member_ids': members, 'evidence_ids': evidence_ids}
    return {'origin': 'python_distinct_original_member_identities',
            'meaning': 'Counts inventory classifications, not confirmed resolution or reliability.',
            **counts}


def compatibility_topic(topic, catalog):
    """Explicit export adapter. Never sent to the model or reparsed as a response."""
    inventory, questions, guidance, answers = [], [], [], []
    for item in topic.inventory:
        entry = catalog[item.evidence_id]
        content = {**item.model_dump(), 'text': entry['quote'], 'text_origin': 'python_original_message',
                   'evidence_ids': [item.evidence_id]}
        content = resolve_cited_fields(content, catalog)
        inventory.append(content)
        if item.kind == 'QUESTION':
            questions.append(content)
        if item.kind in {'ANSWER', 'INSTRUCTION', 'DIAGNOSTIC_REQUEST'}:
            # Scope is the exact full message, never a separately generated paraphrase.
            value = {**content, 'kind': {'ANSWER': 'SCOPED_ANSWER', 'INSTRUCTION': 'HANDLING_INSTRUCTION',
                                       'DIAGNOSTIC_REQUEST': 'DIAGNOSTIC_REQUEST'}[item.kind],
                     'authority': 'TEAM_LEAD' if entry['author_role'] == 'TEAM_LEAD' else
                                  'TL_ENDORSED' if entry['is_reply'] and tl_endorsements(entry) else 'SOURCE_REPLY',
                     'scope': resolve_cited_fields({'text': entry['quote'], 'evidence_ids': [item.evidence_id]}, catalog),
                     'limitations': [], 'conditions_representation': 'verbatim_full_message_in_scope_not_extracted'}
            (answers if item.kind == 'ANSWER' else guidance).append(value)
    has_announcement = any(i.kind == 'ANNOUNCEMENT' for i in topic.inventory)
    roots = [q for q in questions if not catalog[q['evidence_id']]['is_reply']]
    # An announcement's reply question remains open without inventing a root question.
    representative = roots[0] if roots else None if has_announcement else next(iter(questions), None)
    dispositions = {d.evidence_id: d for d in topic.dispositions}
    coverage = [{'evidence_id': eid, 'item_ids': [i.item_id for i in topic.inventory if i.evidence_id == eid],
                 'disposition': dispositions[eid].model_dump() if eid in dispositions else None}
                for eid, e in catalog.items() if e['member_id'] in topic.member_ids]
    uncertainty = [resolve_cited_fields({'text': d.reason, 'evidence_ids': [d.evidence_id]}, catalog)
                   for d in topic.dispositions if d.disposition == 'UNCERTAIN']
    return {**resolve_cited_fields(topic.model_dump(), catalog), 'inventory': inventory,
            'conversation_kind': ('MIXED' if questions else 'ANNOUNCEMENT') if has_announcement else 'DISCUSSION',
            'representative_question': representative,
            'open_questions': [q for q in questions if q['question']['status'] in {'OPEN', 'PARTIAL'}],
            'guidance': guidance, 'supported_answers': answers, 'uncertainties': uncertainty,
            'source_coverage': coverage, 'inventory_counts': inventory_member_counts(topic, catalog),
            'export_adapter_version': EXPORT_ADAPTER_VERSION}


def export_result(payload, analysis=None, *, state='NOT_RUN', error=None, diagnostics=None):
    validate_input(payload)
    aliases, catalog = evidence_catalog(payload)
    members = {m['member_id']: deepcopy(m) for m in payload['members']}
    if analysis:
        validate_output(payload, analysis)
    obligations = [{'origin': 'agent1', 'member_id': m['member_id'], **{k: m[k] for k in IDENTITY},
                    'candidate_group_id': payload['candidate_group_id'],
                    'candidate_sha256': m['agent1_record']['candidate_sha256'],
                    'source_sha256': m['agent1_record']['input_sha256'], 'agent1_record': deepcopy(m['agent1_record']),
                    'agent1_export_file': m['agent1_export_file'], 'agent1_export_sha256': m['agent1_export_sha256'],
                    'agent1_lineage_base': m['agent1_lineage_base']}
                   for m in members.values() if m['agent1_record']['review_required']]
    topics, morning, agent2_obligations = [], [], []
    details = deepcopy(diagnostics or [])
    for ti, topic in enumerate(analysis.topics if analysis else []):
        topic_id = f"{payload['candidate_group_id']}/topic_{ti+1}"
        mids = [aliases[mid]['member_id'] for mid in topic.member_ids]
        flagged = [mid for mid in mids if members[mid]['agent1_record']['review_required']]
        warnings = analysis.coverage_diagnostics[ti]
        severity_errors = analysis.severity_diagnostics[ti]
        details.extend(warnings + severity_errors)
        provisional = bool(flagged or warnings)
        reliability = 'PROVISIONAL' if provisional else 'SOURCE_CITED_NOT_INDEPENDENTLY_VERIFIED'
        content = compatibility_topic(topic, catalog)
        for _, unit in cited_units(content):
            unit['reliability'] = reliability
        content['member_aliases'], content['member_ids'] = content['member_ids'], mids
        content['provisional_answers'] = content['supported_answers'] if provisional else []
        if provisional:
            content['supported_answers'] = []
        severity = resolve_cited_fields(analysis.severities[ti], catalog)
        high = severity['level'] == 'HIGH'
        if high:
            morning.append({'topic_id': topic_id, 'reason': 'HIGH provisional operational severity; nonblocking morning review.', 'assessment': severity})
        for kind, values in [('coverage', warnings), ('severity', severity_errors)]:
            if values:
                agent2_obligations.append({'origin': 'agent2', 'topic_id': topic_id,
                                          'kind': kind, 'diagnostics': deepcopy(values)})
        topics.append({**content, 'topic_id': topic_id, 'review_required': bool(provisional or high or severity_errors),
                       'factual_validity': 'VALID', 'severity_validity': ('UNASSESSED' if severity_errors[0]['category'] == 'severity_unassessed' else 'INVALID') if severity_errors else 'VALID',
                       'preliminary_severity': severity, 'severity_proposal': analysis.severity_proposals[ti],
                       'rejected_severity_proposal': analysis.severity_proposals[ti] if severity_errors else None,
                       'severity_diagnostics': severity_errors, 'coverage_diagnostics': warnings,
                       'morning_review_required': high, 'flagged_member_ids': flagged,
                       'claim_reliability': reliability, 'answer_reliability': reliability,
                       'members': [deepcopy(members[mid]) for mid in mids]})
    reasons = ([error] if error else [])
    if obligations:
        reasons.append('Inherited Agent 1 disputes remain open; consolidation cannot clear them.')
    if agent2_obligations:
        reasons.append('Inspect retained coverage/severity diagnostics; processing is nonblocking.')
    if morning:
        reasons.append('HIGH provisional operational severity requires nonblocking morning review.')
    severity_state = ('UNASSESSED' if all(analysis.severity_diagnostics) else
                      'PARTIALLY_UNASSESSED' if any(analysis.severity_diagnostics) else 'ASSESSED_PER_TOPIC') if analysis else 'UNASSESSED'
    # A timeout or configuration failure is not a verdict on factual content.
    factual_invalid = any(d.get('stage') not in {'processing', 'severity', 'refusal', 'incomplete_response', 'incomplete_output', 'unsupported_schema', 'configuration'} for d in (diagnostics or []))
    severity_validity = 'INVALID' if any(t['severity_validity'] == 'INVALID' for t in topics) else 'UNASSESSED' if not topics or any(t['severity_validity'] == 'UNASSESSED' for t in topics) else 'VALID'
    return {'schema_version': 6, 'candidate_group_id': payload['candidate_group_id'],
            'project_id': payload['project_id'], 'batch_id': payload['batch_id'],
            'processing_state': state, 'factual_validity': 'VALID' if analysis else 'INVALID' if factual_invalid else 'UNASSESSED',
            'severity_validity': severity_validity,
            'review_required': bool(reasons or state in {'FAILED', 'INTERRUPTED'}), 'review_reasons': reasons,
            'inherited_review_obligations': obligations, 'agent2_review_obligations': agent2_obligations,
            'agent2_review_reasons': [r for r in reasons if not r.startswith('Inherited')],
            'morning_review_obligations': morning, 'validation_diagnostics': details,
            'members': list(members.values()), 'topics': topics, 'severity_assessment_status': severity_state,
            'unassessed_severity': None if analysis else unknown_severity('No valid factual consolidation.'),
            'is_coherent': len(topics) == 1 if analysis else None,
            'coherence_rationale': 'Derived from validated topic assignment; no independent semantic guarantee.' if analysis else None,
            'interpretation_reliability_is_not_slack_resolution': True,
            'review_evidence': deepcopy(payload['review_evidence']),
            'grouping_file': payload['grouping_file'], 'grouping_sha256': payload['grouping_sha256']}
