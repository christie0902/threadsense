"""Single-request inventory consolidation with deterministic v4 compatibility exports."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import json
import re

from threadsense.legacy.agent2.topic_contracts_v4 import (
    TopicConsolidation, ResponseEnvelope, InventoryTopic, ImpactProposal,
)
from threadsense.agents.topic_diagnostics import ConsolidationValidationError, describe_exception, diagnostic
from threadsense.legacy.agent2.topic_evidence import evidence_catalog, resolve_cited_fields, resolve_reference, tl_endorsements
from threadsense.legacy.agent2.operational_severity import CRITERIA, RUBRIC, RUBRIC_VERSION
from threadsense.agents.verification_requests import request_body
from threadsense.handoff_inputs import IDENTITY, identity, member_id, digest
from threadsense.models import Thread

PROMPT_VERSION = 'agent2-inventory-v4.0'
RULES = """Consolidate factual topics from original Slack messages and the approved glossary.
Assign every member alias exactly once; split unrelated topics. Cite only exact
topic-local evidence IDs. Traceable IDs alone do not establish support for a claim.
Keep a concise shared issue and supported differences; invent no causal explanation,
policy precedence, attempted/failed workaround, impact, or harmful-content contrast.

Record substantive content ONCE in inventory. Each item has a topic-local item_id,
one evidence_id, and an EXACT contiguous source excerpt in text. Preserve qualifiers;
for guidance include its stated scope and conditions in the excerpt. Python retains
the full original message alongside every item, plus identities/authors/reactions.
A message may supply multiple items, e.g. diagnostic request and submission condition.
Distinguish QUESTION (actual handling/information question), DIAGNOSTIC_REQUEST
(request for checks/details, not an answer), ANSWER (scoped substantive reply),
INSTRUCTION, FACT (reported, not independently confirmed), ANNOUNCEMENT and CONTEXT.
Quoted or rhetorical questions are not automatically genuine questions. Never invent
questions from a factual incident or diagnostic. Announcements can contain instructions
without questions. Do not repeat items in independent answer/guidance/question lists.

Every member needs substantive inventory content, not just context or raw retention.
Account for every message with one or more items OR an explicit NON_SUBSTANTIVE or
UNCERTAIN disposition with reason. Uncertain meaning must remain visible, never default
to NONE. Preserve all actual unanswered questions and scoped TL instructions, including
those in replies. Question items require OPEN with no answer links, or PARTIAL/ANSWERED
with answer_item_ids pointing to ANSWER items in that SAME member conversation.
Diagnostics cannot close questions. An answer to a narrower task cannot resolve a
broader question in another thread. Tentative advice must remain tentative and PARTIAL.
Retain relevant differences between reported symptoms, and distinguish task labels
from operational impact. Use glossary meanings consistently.

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
For substantial_blockage cite inability to perform/submit work; quality/safety risk
requires actual operational evidence beyond task vocabulary. Review flags, unanswered
questions, number of members and minor/major task categories do not set severity.
HIGH routes to nonblocking review; LOW/N/A cannot clear flags. Agent 3 may later record
a separate researched assessment. No research, actionability or recommendations.
One independent request, no tools, verifier, retries or repair. Return schema v4 JSON:
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
    return request_body(model, f'Prompt version: {PROMPT_VERSION}\n' + RULES + json.dumps(TopicConsolidation.model_json_schema()), {
        'schema_version': 4, 'candidate_group_id': payload['candidate_group_id'],
        'project_id': payload['project_id'], 'batch_id': payload['batch_id'],
        'approved_glossary': dict(glossary), 'provisional_operational_severity_rubric': RUBRIC,
        'members': [{'member_id': alias, **{k: m[k] for k in IDENTITY},
                     'interpretation_reliability': m['agent1_record']['verification_status'],
                     'review_required': m['agent1_record']['review_required'],
                     'disputed_fields': m['agent1_record']['provisional_fields']}
                    for alias, m in aliases.items()],
        'evidence_catalog': [{**{k: v for k, v in e.items() if k != 'canonical_member_id'},
                              'eligible_tl_endorsements': tl_endorsements(e)} for e in catalog.values()],
    }, max_tokens=8192)


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
        signatures = [(i.evidence_id, i.kind, i.text) for i in topic.inventory]
        if len(set(signatures)) != len(signatures):
            fail('inventory', 'Repeated substantive item.', (*path, 'inventory'))
        substantive, covered = set(), set()
        for index, item in enumerate(topic.inventory):
            loc = (*path, 'inventory', index)
            entry = check_reference(item.evidence_id, topic, catalog, loc)
            if item.text not in entry['quote']:
                fail('quotation_mismatch', 'Inventory text must be an exact source excerpt.', (*loc, 'text'), entry)
            covered.add(item.evidence_id)
            if item.kind != 'CONTEXT':
                substantive.add(entry['member_id'])
            if item.kind == 'ANSWER' and not entry['is_reply']:
                fail('answer_evidence', 'An ANSWER requires a source reply.', loc, entry)
            for link in item.question.answer_item_ids if item.question else []:
                answer = items.get(link)
                if (not answer or answer.kind != 'ANSWER' or answer.evidence_id not in catalog
                        or catalog[answer.evidence_id]['member_id'] != entry['member_id']):
                    fail('answer_evidence', 'Question links require scoped ANSWER items in the same thread.', loc, entry)
        if substantive != set(topic.member_ids):
            fail('membership', 'Every member needs substantive inventory representation.', path)
        dispositions = [d.evidence_id for d in topic.dispositions]
        for index, eid in enumerate(dispositions):
            check_reference(eid, topic, catalog, (*path, 'dispositions', index))
        expected = {eid for eid, e in catalog.items() if e['member_id'] in topic.member_ids}
        if len(set(dispositions)) != len(dispositions) or covered & set(dispositions) or covered | set(dispositions) != expected:
            fail('source_coverage', 'Every message needs items OR one explicit disposition; no missing or contradictory treatment.', path)
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


def parse_response(payload, raw):
    validate_input(payload)
    envelope = ResponseEnvelope.model_validate_json(raw)
    topics = [InventoryTopic.model_validate({k: v for k, v in t.items() if k != 'impact'}) for t in envelope.topics]
    validate_facts(payload, topics)  # Severity cannot make invalid facts accepted.
    _, catalog = evidence_catalog(payload)
    severities, proposals, errors, warnings = [], [], [], []
    for ti, (topic, original) in enumerate(zip(topics, envelope.topics)):
        proposal = original.get('impact')
        proposals.append(deepcopy(proposal))
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


def compatibility_topic(topic, catalog):
    """Explicit export adapter. Never sent to the model or reparsed as a response."""
    inventory, questions, guidance, answers = [], [], [], []
    for item in topic.inventory:
        entry = catalog[item.evidence_id]
        content = {**item.model_dump(), 'evidence_ids': [item.evidence_id]}
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
            'source_coverage': coverage, 'export_adapter_version': 'inventory-to-display-v1'}


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
                       'factual_validity': 'VALID', 'severity_validity': 'INVALID' if severity_errors else 'VALID',
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
    factual_invalid = any(d.get('stage') not in {'processing', 'severity'} for d in (diagnostics or []))
    return {'schema_version': 4, 'candidate_group_id': payload['candidate_group_id'],
            'project_id': payload['project_id'], 'batch_id': payload['batch_id'],
            'processing_state': state, 'factual_validity': 'VALID' if analysis else 'INVALID' if factual_invalid else 'UNASSESSED',
            'severity_validity': ('INVALID' if any(analysis.severity_diagnostics) else 'VALID') if analysis else 'UNASSESSED',
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
