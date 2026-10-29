"""Conditional shallow Tree-of-Thought: one structured comparison call, 2-3 candidate actions.

Runs only on conflict, low-confidence or open-confirmation paths, before the final grounding
call (which stays reserved). Candidates are checked against the evidence ledger: unknown
evidence makes a candidate invalid, and claimed applicability is compared with the cited
items' recorded use. Valid candidates are then judged as statements of their own by the final
grounding call; no draft verdict carries over to them. A candidate is preferred only if it is
valid and SUPPORTED. The comparison never adds evidence, never changes the card action and
never clears a review reason.
"""
from threadsense.agents.advice_contracts import LOW_CONFIDENCE_BELOW
from threadsense.agents.advisor_checks import CURRENT_USES, KNOWLEDGE_USES
from threadsense.agents.advisor_contracts import ToTComparison

RULES = (
    'Compare 2-3 distinct candidate actions for this topic (NO_ACTION or waiting for TL confirmation may be one). '
    'For each, cite only evidence_ids present in the evidence provided, and rate evidence support, applicability '
    '(current versus historical-only sources) and fit with the assessed severity. Do not invent evidence, outcomes or '
    'causes. Name a preferred candidate only if it is clearly better; otherwise set close_call true. '
    'Your selection does not resolve the review triggers listed; a team lead decides.')


def triggers(draft, temporal):
    """Why a comparison is warranted; empty on an ordinary supported, confident path."""
    found = []
    if temporal and temporal['status'] == 'DETECTED':
        found.append('TEMPORAL_CONFLICT')
    if draft.confidence < LOW_CONFIDENCE_BELOW:
        found.append('LOW_CONFIDENCE')
    if draft.open_confirmation == 'OPEN':
        found.append('OPEN_CONFIRMATION')
    return found


def _applicability(items, handling):
    uses = {'CURRENT_HANDLING' if item['evidence_id'] in handling else item['use'] for item in items
            if item['use'] in KNOWLEDGE_USES}
    if not uses:
        return 'UNCLEAR'
    if uses <= CURRENT_USES:
        return 'CURRENT'
    return 'MIXED' if uses & CURRENT_USES else 'HISTORICAL_ONLY'


def check_candidates(comparison, ledger, handling=frozenset()):
    checked = []
    for c in comparison.candidates:
        unknown = [e for e in c.evidence_ids if e not in ledger]
        items = [ledger[e] for e in c.evidence_ids if e in ledger]
        recorded = _applicability(items, handling)
        issues = (['CITES_UNKNOWN_EVIDENCE'] if unknown else []) + \
            (['SUPPORT_WITHOUT_EVIDENCE'] if c.evidence_support in {'STRONG', 'PARTIAL'} and not items else []) + \
            (['APPLICABILITY_OVERSTATED'] if c.applicability == 'CURRENT' and recorded != 'CURRENT' else [])
        checked.append({**c.model_dump(), 'recorded_applicability': recorded, 'unknown_evidence_ids': unknown,
                        'issues': issues, 'valid': not unknown and 'SUPPORT_WITHOUT_EVIDENCE' not in issues})
    return checked


def compare(call, *, draft, temporal, ledger, payload, handling=frozenset(), skip=None):
    """At most one model call, reserving the final grounding call. `call(stage, payload, schema, reserve=)`
    charges the budget and records failures. `skip` names a reason not to compare (e.g. structural failure)."""
    found = triggers(draft, temporal)
    if not found:
        return {'status': 'NOT_TRIGGERED', 'triggers': []}
    if skip:
        return {'status': 'NOT_RUN', 'triggers': found, 'note': skip}
    comparison = call('tot', {**payload, 'rules': RULES, 'triggers': found}, ToTComparison, reserve=1)
    if comparison is None:
        return {'status': 'UNAVAILABLE', 'triggers': found,
                'note': 'Comparison call failed, exceeded its budget or would consume the reserved grounding call; '
                        'review reasons are unchanged.'}
    return {'status': 'COMPARED', 'triggers': found, 'candidates': check_candidates(comparison, ledger, handling),
            'model_preferred_candidate_id': comparison.preferred_candidate_id, 'close_call': comparison.close_call,
            'rationale': comparison.rationale}


def alternatives(tot):
    """Candidates the final grounding call judges (invalid ones are never presented as grounded)."""
    return [c for c in tot.get('candidates', []) if c['valid']]


def finalize(tot, grounding):
    """Attach each candidate's own final verdict; prefer only a valid, SUPPORTED candidate."""
    if tot['status'] != 'COMPARED':
        return tot
    verdicts = {s['statement_id']: s['verdict'] for s in grounding['statements']}
    candidates = [{**c, 'grounding': verdicts.get(f"alternative:{c['candidate_id']}", 'NOT_JUDGED') if c['valid']
                   else 'NOT_PRESENTED_INVALID'} for c in tot['candidates']]
    grounded = {c['candidate_id'] for c in candidates if c['grounding'] == 'SUPPORTED'}
    preferred = tot['model_preferred_candidate_id'] if tot['model_preferred_candidate_id'] in grounded else None
    return {**tot, 'candidates': candidates, 'preferred_candidate_id': preferred, 'grounded_candidate_ids': sorted(grounded),
            'presentation': 'PREFERRED_WITH_ALTERNATIVES' if preferred and not tot['close_call'] else
            'SURFACE_GROUNDED_ALTERNATIVES' if grounded else 'NO_GROUNDED_ALTERNATIVES',
            'note': 'Alternatives for the reviewer, each with its own grounding verdict; the card action and review '
                    'reasons are unchanged by this comparison.'}
