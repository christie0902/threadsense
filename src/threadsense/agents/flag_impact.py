"""Flag-impact assessment in the final grounding call (opt-in shadow evaluation; routing does not read it).

prepare() turns each inherited flag's provenance and card dependencies (agents/flag_provenance) into the
`flag_impacts` input the judge receives beside the statements, with a stable flag_id. Each flag carries its open
findings (F1, F2, ...: the kept attempt's and the discarded attempt's OPEN or UNCERTAIN ones), the resolved ones as
context (R1, ...: CORRECTED or SUPERSEDED, with the recorded basis), its attempt errors and its references. The judge
returns one FlagImpactJudgmentV2 per flag in the same call (GroundingJudgmentV7), so the reserved grounding request
and the four-request topic ceiling are unchanged.

catalogue() is the one element vocabulary: the judged statements, every member's resolution, the card-level elements
and every element_id the references send (for example action:context). prepare() builds the references and the
catalogue together and validate() accepts exactly that catalogue, so an ID the system sent is never rejected and any
other ID is. validate() is deterministic and conservative:

- a projection gap is never sent and keeps its own review requirement (GROUPING_RULE);
- a missing, duplicated or malformed judgment, an unknown element or finding ID, or an unavailable finding is UNKNOWN;
- INDEPENDENT also needs a narrowed finding, an independence basis, no UNCERTAIN finding, every open finding among
  finding_ids, no record gap, and every displayed reference (DIRECT, DERIVED or NOT_ESTABLISHED) among element_ids;
  a disputed member resolution the card counts in its thread status is AFFECTS even when the topic state is
  invariant, and a member state kept only in diagnostics may be INDEPENDENT only if the judgment assesses that
  member's resolution itself (topic-resolution invariance alone is not independence);
- AFFECTS and UNKNOWN retain review. The deterministic references are kept beside every judgment
  (reference_ids, unassessed_reference_ids): an AFFECTS element list names known effects and is not exhaustive.

record() binds the assessments to the exact judged inputs (statements, evidence, provenance, flag inputs) and to the
assembled card text; a replay reuses a recorded judgment only when inputs_digest() is unchanged.
"""
import json
from hashlib import sha256

from pydantic import ValidationError

from threadsense.agents.advice_contracts import (FlagImpactAssessmentV2 as FlagImpactAssessment,
                                                 FlagImpactRecordV2 as FlagImpactRecord, stable_id)
from threadsense.agents.advisor_checks import topic_resolution
from threadsense.agents.advisor_contracts import FlagImpactJudgmentV2 as FlagImpactJudgment
from threadsense.agents.flag_provenance import dependencies

CARD_ELEMENTS = ('title', 'thread_status', 'topic_resolution')
RESOLUTION_FIELDS = {'resolution_state', 'resolution_rationale'}
REFERENCES = {'DIRECT', 'DERIVED'}
COVERED = REFERENCES | {'NOT_ESTABLISHED'}  # Displayed references an INDEPENDENT judgment must assess.
NOT_SENT = ('DRAFT_INPUT', 'RETRIEVAL_QUERY')  # Inputs to drafting and retrieval, not card elements.
NOT_ASSESSED_NOTE = 'This run predates flag-impact assessment; no flag was assessed.'
FLAG_IMPACT_RULES = (
    'Flag impact. flag_impacts lists the upstream review flags still open on these threads. Each has findings (what '
    'an earlier check disputed and that is still unresolved: finding_id, fields, messages and the verbatim '
    'explanation; status OPEN, or UNCERTAIN when the record cannot tell whether a later attempt corrected it), '
    'resolved_findings (recorded as CORRECTED or SUPERSEDED, with the basis; context, not a dispute), attempt_errors '
    '(a failed revision or a failed check; never the dispute) and references (which elements cite the disputed '
    'messages or assess the disputed fields: DIRECT and DERIVED are references, not effects; SAME_THREAD cites the '
    'thread only and is not a dependence; INVARIANT is the exact topic-resolution aggregation; NOT_ESTABLISHED means '
    'the records cannot tell). These findings are disputed audit input, not evidence. Return one flag_impacts entry '
    'per flag: flag_id; impact AFFECTS if correcting any open finding could change any element you judge (title, '
    'summary sentences, the action, its need, premises and context, counts, reporters, severity, member or topic '
    'resolution, thread status) or make an omission decision-relevant; INDEPENDENT only if every open finding states '
    'what is disputed and every referenced element would stay justified with each disputed reading corrected; '
    'UNKNOWN when a finding or the evidence is too coarse to decide. finding_ids: the open findings you assessed '
    '(INDEPENDENT: all of them). element_ids: the elements affected (AFFECTS: those you identified) or assessed '
    '(INDEPENDENT: every element_id in references other than SAME_THREAD and INVARIANT), as statement IDs, reference '
    'element_ids, or title, thread_status, topic_resolution. explanation: one or two sentences drawn from the findings '
    'and the cited evidence. independence_basis (INDEPENDENT only): why correcting each disputed interpretation leaves '
    'each displayed conclusion and the recommendation justified. Agreement with current guidance alone is not '
    'independence when another element adopts the disputed reading. A member resolution the card counts in its thread '
    'status stays relevant even when the topic state would not change; topic-resolution invariance alone is not '
    'independence. Never change a statement verdict because of a flag.')


def flag_id(flag):
    """Stable identity of an inherited flag (origin, kind, group, members, obligation)."""
    f = flag if isinstance(flag, dict) else flag.model_dump()
    return stable_id('flag', {'origin': f['origin'], 'kind': f['kind'], 'candidate_group_id': f['candidate_group_id'],
                              'member_ids': sorted(f.get('member_ids') or []), 'obligation_id': f.get('obligation_id')})


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def inputs_digest(payload):
    """What a flag judgment depends on, read from the grounding payload exactly as sent."""
    return digest({'flags': payload.get('flag_impacts'), 'statements': payload.get('statements'),
                   'member_threads': payload.get('member_threads'), 'retrieved_sources': payload.get('retrieved_sources')})


def elements(statements, member_ids):
    """The fixed part of the catalogue: judged statements, every member's resolution, and the card-level elements."""
    return sorted({s['statement_id'] for s in statements} | {f'resolution:{m}' for m in member_ids} | set(CARD_ELEMENTS))


def sent_references(deps):
    """The dependency links a flag input carries (everything but drafting and retrieval inputs)."""
    return [l for l in deps['links'] if l['element'] not in NOT_SENT]


def catalogue(statements, member_ids, dependencies_list):
    """The one element vocabulary sent to grounding and accepted by validation: the fixed elements plus every
    element_id the references send."""
    return sorted(set(elements(statements, member_ids)) |
                  {l['element_id'] for d in dependencies_list for l in sent_references(d)})


def findings(prov):
    """(open, resolved) findings of one flag with their stable per-flag IDs: open F1.. are the kept attempt's findings
    then the prior OPEN and UNCERTAIN ones; resolved R1.. are the prior CORRECTED and SUPERSEDED ones."""
    history = prov.get('finding_history') or []
    open_ = [{**f, 'status': 'OPEN', 'attempt_kept': True} for f in prov['findings']] + \
        [{**h['finding'], 'status': h['status'], 'attempt_kept': False, 'basis': h['basis']}
         for h in history if h['status'] in ('OPEN', 'UNCERTAIN')]
    resolved = [{**h['finding'], 'status': h['status'], 'basis': h['basis']} for h in history
                if h['status'] in ('CORRECTED', 'SUPERSEDED')]
    return ([{**f, 'finding_id': f'F{n}'} for n, f in enumerate(open_, 1)],
            [{**f, 'finding_id': f'R{n}'} for n, f in enumerate(resolved, 1)])


def _input(prov, deps):
    open_, resolved = findings(prov)
    return {'flag_id': prov['flag_id'], 'kind': prov['kind'], 'label': prov['label'], 'member_ids': prov['member_ids'],
            'finding_status': prov['recovery'], 'finding_note': prov['recovery_note'],
            'findings': [{'finding_id': f['finding_id'], 'status': f['status'], 'category': f['category'],
                          'nature': f['nature'], 'disputed_fields': f['disputed_fields'], 'message_ids': f['message_ids'],
                          'explanation': f['explanation'],
                          **({} if f['attempt_kept'] else {'from_discarded_attempt': f['basis']})} for f in open_],
            'resolved_findings': [{'finding_id': f['finding_id'], 'status': f['status'], 'category': f['category'],
                                   'disputed_fields': f['disputed_fields'], 'basis': f['basis']} for f in resolved],
            'attempt_errors': [{'stage': e['stage'], 'text': e['text']} for e in prov['attempt_errors']],
            'references': [{'element_id': l['element_id'], 'relation': l['relation'], 'via': l['via'], 'note': l['note']}
                           for l in sent_references(deps)],
            'member_states': [r for r in deps['resolution_inputs'] if r['flagged']]}


def prepare(source, flags, *, packet, draft, stmts, ledger, topic, query, agent1_context):
    """Flag inputs for the grounding call plus what validation needs. Dependencies are traced over the proposed
    statements (no verdict yet), the draft's member states and the recorded Agent 1 context."""
    states = {r.member_id: r.state for r in draft.resolution}
    card = {'card_id': None, 'topic_name': packet['topic_name'] or packet['topic_label'],
            'lineage': {'member_ids': packet['member_ids'], 'topic_id': packet['topic_id']},
            'recommended_action': draft.proposed_action.model_dump() if draft.proposed_action else None,
            'severity': {}, 'inherited_flags': [f.model_dump() for f in flags]}
    result = {'evidence_ledger': ledger, 'drafts': {'final': draft.model_dump()}, 'grounding': {'statements': stmts},
              'resolution': {'members': states, 'topic': topic_resolution(packet['member_ids'], states)},
              'topic': {**topic, 'initial_query': query}, 'action_source': 'DRAFT', 'agent1_context': agent1_context}
    provs, deps = [], []
    for p in source.provenance(card):
        provs.append({**p.model_dump(mode='json'), 'flag_id': flag_id(p.model_dump())})
        deps.append(dependencies(card, result, p, source).model_dump(mode='json'))
    inputs = [_input(p, d) for p, d in zip(provs, deps) if p['category'] != 'TOPIC_GROUPING']
    return {'inputs': inputs, 'provenance': provs, 'dependencies': deps,
            'element_ids': catalogue(stmts, packet['member_ids'], deps)}


def prepare_saved(card, result, source):
    """The same inputs for a saved card (offline evaluation): its judged statements, saved member states and
    recorded dependencies. Returns the prepared inputs, the final verdicts and the displayed member states."""
    provs, deps = [], []
    for p in source.provenance(card):
        provs.append({**p.model_dump(mode='json'), 'flag_id': flag_id(p.model_dump())})
        deps.append(dependencies(card, result, p, source).model_dump(mode='json'))
    statements = (result.get('grounding') or {}).get('statements') or []
    prepared = {'inputs': [_input(p, d) for p, d in zip(provs, deps) if p['category'] != 'TOPIC_GROUPING'],
                'provenance': provs, 'dependencies': deps,
                'element_ids': catalogue(statements, card['lineage'].get('member_ids') or [], deps)}
    return prepared, {s['statement_id']: s.get('verdict') for s in statements}, (result.get('resolution') or {}).get('members') or {}


def _assessment(prov, status, impact, *, judgment=None, issues=(), source='NONE', coverage=None):
    return FlagImpactAssessment(flag_id=prov['flag_id'], kind=prov['kind'], status=status, impact=impact,
                                model_impact=judgment.impact if judgment else None,
                                element_ids=judgment.element_ids if judgment else [],
                                finding_ids=judgment.finding_ids if judgment else [],
                                explanation=judgment.explanation if judgment else None,
                                independence_basis=judgment.independence_basis if judgment else None,
                                validation_issues=list(issues), judgment_source=source if judgment else 'NONE',
                                retains_review=impact != 'INDEPENDENT' or status == 'GROUPING_RULE', **(coverage or {}))


def _coverage(prov, deps, shown, judgment):
    """The deterministic side kept beside every judgment: open and uncertain findings, displayed references, and the
    references the judgment did not name."""
    open_, _ = findings(prov)
    refs = sorted({l['element_id'] for l in sent_references(deps) if l['relation'] in COVERED and l['element_id'] in shown})
    named = set(judgment.element_ids) if judgment else set()
    return {'open_finding_ids': [f['finding_id'] for f in open_],
            'uncertain_finding_ids': [f['finding_id'] for f in open_ if f['status'] == 'UNCERTAIN'],
            'reference_ids': refs, 'unassessed_reference_ids': [r for r in refs if r not in named]}


def validate(raw, prepared, *, verdicts, member_states, source):
    """Validated assessments, one per flag (see the module docstring). `verdicts`: final statement verdicts;
    `member_states`: the member resolution the card shows (UNKNOWN when not displayed)."""
    shown = {sid for sid, v in verdicts.items() if v == 'SUPPORTED'} | {'title'}
    # Displayed elements that are not judged statements (action:context, the whole summary, severity signals).
    shown |= {l['element_id'] for d in prepared['dependencies'] for l in d['links'] if l['displayed'] and l['element_id'] not in verdicts}
    if any(s != 'UNKNOWN' for s in member_states.values()):
        shown.add('thread_status')
    shown.add('topic_resolution')
    allowed, out = set(prepared['element_ids']), []
    for prov, deps in zip(prepared['provenance'], prepared['dependencies']):
        if prov['category'] == 'TOPIC_GROUPING':
            out.append(_assessment(prov, 'GROUPING_RULE', 'UNKNOWN', issues=['Projection gap: its own review requirement applies.']))
            continue
        items = [i for i in raw or [] if isinstance(i, dict) and i.get('flag_id') == prov['flag_id']]
        if len(items) != 1:
            out.append(_assessment(prov, 'NOT_ASSESSED', 'UNKNOWN', coverage=_coverage(prov, deps, shown, None),
                                   issues=['No judgment returned for this flag.' if not items else 'More than one judgment for this flag.']))
            continue
        try:
            judgment = FlagImpactJudgment.model_validate(items[0])
        except ValidationError as error:
            out.append(_assessment(prov, 'NOT_ASSESSED', 'UNKNOWN', coverage=_coverage(prov, deps, shown, None),
                                   issues=[f'Invalid judgment: {error.errors()[0]["msg"]}']))
            continue
        coverage = _coverage(prov, deps, shown, judgment)
        issues, impact = [], judgment.impact
        unknown = sorted(set(judgment.element_ids) - allowed)
        if unknown:
            issues.append(f'Unknown element IDs: {", ".join(unknown)}.')
            impact = 'UNKNOWN'
        stray = sorted(set(judgment.finding_ids) - set(coverage['open_finding_ids']))
        if stray:
            issues.append(f'Unknown finding IDs: {", ".join(stray)}.')
            impact = 'UNKNOWN'
        if prov['recovery'] == 'UNAVAILABLE':
            issues.append('The upstream finding is unavailable.')
            impact = 'UNKNOWN'
        if impact == 'AFFECTS' and coverage['unassessed_reference_ids']:
            issues.append('Known effects only; references not named: ' + ', '.join(coverage['unassessed_reference_ids']) + '.')
        if impact == 'INDEPENDENT':
            impact = _independent(prov, deps, judgment, coverage, member_states, issues)
        out.append(_assessment(prov, 'ASSESSED', impact, judgment=judgment, issues=issues, source=source, coverage=coverage))
    return out


def _independent(prov, deps, judgment, coverage, member_states, issues):
    if prov['recovery'] != 'RECOVERED':
        issues.append('The finding does not narrow the dispute; independence cannot be established.')
        return 'UNKNOWN'
    if not (judgment.independence_basis or '').strip() or not judgment.element_ids:
        issues.append('INDEPENDENT needs assessed elements and an independence basis.')
        return 'UNKNOWN'
    if coverage['uncertain_finding_ids']:
        issues.append('The record cannot establish whether an earlier finding was corrected: '
                      + ', '.join(coverage['uncertain_finding_ids']) + '.')
        return 'UNKNOWN'
    missing = [f for f in coverage['open_finding_ids'] if f not in judgment.finding_ids]
    if missing:
        issues.append(f'Open findings not accounted for: {", ".join(missing)}.')
        return 'UNKNOWN'
    if deps.get('record_gaps'):
        issues.append('Dependency coverage is incomplete: ' + '; '.join(deps['record_gaps']))
        return 'UNKNOWN'
    if coverage['unassessed_reference_ids']:
        issues.append(f'Displayed references not assessed: {", ".join(coverage["unassessed_reference_ids"])}.')
        return 'UNKNOWN'
    fields = {d for f in findings(prov)[0] if f['nature'] == 'SUBSTANTIVE' for d in f['disputed_fields']}
    if fields & RESOLUTION_FIELDS:
        for member in prov['member_ids']:
            state = member_states.get(member, 'UNKNOWN')
            if state != 'UNKNOWN':
                issues.append(f'The card counts this member\'s disputed resolution ({state}) in its thread status.')
                return 'AFFECTS'
            if f'resolution:{member}' not in judgment.element_ids:  # Topic invariance alone is not independence.
                issues.append("The member state kept in diagnostics was not assessed (resolution:<member>).")
                return 'UNKNOWN'
    return 'INDEPENDENT'


def card_text(card):
    """The displayed text of an assembled card that a flag judgment is bound to."""
    action = card.get('recommended_action') or {}
    return digest({'topic_name': card['topic_name'], 'summary': card['summary'], 'reasoning': card['reasoning'],
                   'action': {k: action.get(k) for k in ('action_type', 'instruction', 'rationale', 'draft_text', 'scope_note')},
                   'severity': {k: card['severity'].get(k) for k in ('level', 'rationale')},
                   'resolution_status': card['resolution_status'], 'review_notes': card['review_notes'],
                   # v4 cards also display details and the next-step reason (v3 digests unchanged).
                   **({'details': card['details'], 'next_step': card['next_step']} if 'next_step' in card else {})})


def record(assessments, prepared, *, payload, ledger, card):
    return FlagImpactRecord(status='ASSESSED', card_id=card['card_id'], inputs_sha256=inputs_digest(payload),
                            evidence_sha256=digest(ledger), provenance_sha256=digest(prepared['provenance']),
                            card_text_sha256=card_text(card), assessments=assessments)


def not_assessed(note=NOT_ASSESSED_NOTE):
    return FlagImpactRecord(status='NOT_ASSESSED', note=note)


def recorded_judgments(saved):
    """The judge's own entries from a saved record, for replay reuse (validated again on reuse)."""
    return [{'flag_id': a['flag_id'], 'impact': a['model_impact'], 'element_ids': a['element_ids'],
             'finding_ids': a.get('finding_ids') or [], 'explanation': a['explanation'],
             'independence_basis': a['independence_basis']}
            for a in (saved or {}).get('assessments') or [] if a['status'] == 'ASSESSED' and a['model_impact']]
