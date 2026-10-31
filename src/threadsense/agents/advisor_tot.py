"""Conditional shallow Tree-of-Thought: one structured comparison call, 2-3 candidate actions.

Runs only on conflict, low-confidence, open-confirmation or action-choice paths, before the final grounding
call (which stays reserved). Candidates are checked against the evidence ledger: unknown
evidence makes a candidate invalid, and claimed applicability is compared with the cited
items' recorded use. Valid candidates are then judged as statements of their own by the final
grounding call; no draft verdict carries over to them. A candidate is preferred only if it is
valid and SUPPORTED. The comparison never adds evidence and never clears a review reason. Candidate
prose gets the card's presentation checks (roles, not names). When the draft action is withheld, an
already-reviewed candidate may become the card action (`fallback`), only if its exact text was judged
SUPPORTED, its essential premises passed the same sufficiency validation, and it has no issue.

v3 (`select`): the draft's action is the incumbent candidate (copied verbatim); a clearly preferred, valid candidate
may replace it before the final grounding (exact text, evidence, premises and intervention need move together), which
then judges the selected action and every remaining valid candidate, the displaced incumbent included. A close call
keeps the incumbent; historical-only support never becomes a current operational action; selecting NO_ACTION removes
the operational action but routing (inherited flags, other review reasons) is unchanged. Recorded v2 comparisons keep
the original `adopt` behaviour.
"""
from threadsense.agents.advice_contracts import LOW_CONFIDENCE_BELOW
from threadsense.agents.advisor_checks import CURRENT_USES, KNOWLEDGE_USES, display_issues, prose_issues
from threadsense.agents.advisor_contracts import ToTComparison

RULES = (
    'Compare 2-3 materially different candidate actions for this topic. If the draft proposes an action, include it '
    'as the incumbent candidate (incumbent true) with its action_type, instruction, draft_text and rationale copied '
    'exactly; include NO_ACTION when observing is plausible. For each operational candidate state intervention_need '
    '(kind, why intervening now is needed, evidence) and rate need_strength, temporal_scope (does every current claim rest '
    'on current, in-scope sources?), proportionality (is the step proportionate to the evidence and impact?) and list '
    'unresolved_assumptions. A source need not literally prescribe a recommendation; a clarification or referral is '
    'not wrong merely because questions remain. Set decision: KEEP_INCUMBENT, REPLACE_INCUMBENT (prefer a different '
    'candidate that is clearly better) or CLOSE_CALL (close_call true; no winner). '
    'For each, cite only evidence_ids present in the evidence provided, and rate evidence support, applicability '
    '(current versus historical-only sources) and fit with the assessed severity. Do not invent evidence, outcomes or '
    'causes. Refer to people by role (a tutor, the team lead), never by name. Write instruction (one concrete sentence '
    'telling the team lead what to do), draft_text (the copyable draft) and rationale (why it helps) in plain words, '
    'with no evidence IDs or field names. Name a preferred candidate only if it is '
    'clearly better; otherwise set close_call true. Your selection does not resolve the review triggers listed; a '
    'team lead decides.')


def choice_trigger(draft, ledger=None):
    """ACTION_CHOICE only for a stated choice between different action types, with a tradeoff, citing evidence in
    the ledger, and including the draft's own action when it proposes one."""
    choice = getattr(draft, 'action_choice', None)
    if choice is None or len(set(choice.competing_actions)) < 2:
        return False
    if ledger is not None and not all(e in ledger for e in choice.evidence_ids):
        return False
    action = draft.proposed_action
    return action is None or action.action_type in choice.competing_actions


def triggers(draft, temporal, ledger=None):
    """Why a comparison is warranted; empty on an ordinary supported, confident path."""
    found = []
    if temporal and temporal['status'] == 'DETECTED':
        found.append('TEMPORAL_CONFLICT')
    if draft.confidence < LOW_CONFIDENCE_BELOW:
        found.append('LOW_CONFIDENCE')
    if draft.open_confirmation == 'OPEN':
        found.append('OPEN_CONFIRMATION')
    if choice_trigger(draft, ledger):
        found.append('ACTION_CHOICE')
    return found


def _applicability(items, handling):
    uses = {'CURRENT_HANDLING' if item['evidence_id'] in handling else item['use'] for item in items
            if item['use'] in KNOWLEDGE_USES}
    if not uses:
        return 'UNCLEAR'
    if uses <= CURRENT_USES:
        return 'CURRENT'
    return 'MIXED' if uses & CURRENT_USES else 'HISTORICAL_ONLY'


def premises(evidence_ids, draft):
    """A candidate's premises: the draft claims that share its evidence."""
    return [c.claim_id for c in draft.claims if set(c.evidence_ids) & set(evidence_ids)]


def check_candidates(comparison, ledger, handling=frozenset(), draft=None):
    checked = []
    for c in comparison.candidates:
        unknown = [e for e in c.evidence_ids if e not in ledger]
        items = [ledger[e] for e in c.evidence_ids if e in ledger]
        recorded = _applicability(items, handling)
        text = ' '.join(x for x in (c.instruction, c.draft_text, c.rationale) if x)
        issues = (['CITES_UNKNOWN_EVIDENCE'] if unknown else []) + \
            (['SUPPORT_WITHOUT_EVIDENCE'] if c.evidence_support in {'STRONG', 'PARTIAL'} and not items else []) + \
            (['APPLICABILITY_OVERSTATED'] if c.applicability == 'CURRENT' and recorded != 'CURRENT' else []) + \
            sorted({code for code, _ in prose_issues(text, items, ledger) + display_issues(text, items)})
        if comparison.contract_version != 'agent3-tot-comparison-v2':
            operational = c.action_type != 'NO_ACTION'
            if c.incumbent and not _is_incumbent(c, draft):
                issues.append('INCUMBENT_NOT_VERBATIM')
            if operational and c.intervention_need is None:
                issues.append('NO_INTERVENTION_NEED_STATED')
            if operational and recorded == 'HISTORICAL_ONLY':
                issues.append('HISTORICAL_ONLY_SUPPORT')  # History cannot become current policy through scoring.
        checked.append({**c.model_dump(), 'recorded_applicability': recorded, 'unknown_evidence_ids': unknown,
                        'premise_ids': premises(c.evidence_ids, draft) if draft is not None else [],
                        'issues': issues, 'valid': not unknown and 'SUPPORT_WITHOUT_EVIDENCE' not in issues})
    return checked


def _is_incumbent(candidate, draft):
    action = draft.proposed_action if draft is not None else None
    return (action is not None and candidate.action_type == action.action_type
            and (candidate.draft_text or '').strip() == (action.draft_text or '').strip()
            and (candidate.instruction or '').strip() == (action.instruction or '').strip())


def compare(call, *, draft, temporal, ledger, payload, handling=frozenset(), skip=None):
    """At most one model call, reserving the final grounding call. `call(stage, payload, schema, reserve=)`
    charges the budget and records failures. `skip` names a reason not to compare (e.g. structural failure)."""
    found = triggers(draft, temporal, ledger)
    if not found:
        return {'status': 'NOT_TRIGGERED', 'triggers': []}
    if skip:
        return {'status': 'NOT_RUN', 'triggers': found, 'note': skip}
    comparison = call('tot', {**payload, 'rules': RULES, 'triggers': found,
                              'incumbent': draft.proposed_action.model_dump() if draft.proposed_action else None,
                              'action_choice': draft.action_choice.model_dump() if getattr(draft, 'action_choice', None) else None},
                      ToTComparison, reserve=1)
    if comparison is None:
        return {'status': 'UNAVAILABLE', 'triggers': found,
                'note': 'Comparison call failed, exceeded its budget or would consume the reserved grounding call; '
                        'review reasons are unchanged.'}
    return {'status': 'COMPARED', 'triggers': found, 'candidates': check_candidates(comparison, ledger, handling, draft),
            'model_preferred_candidate_id': comparison.preferred_candidate_id, 'close_call': comparison.close_call,
            'rationale': comparison.rationale, 'contract_version': comparison.contract_version,
            'decision': comparison.decision}


def select(tot, draft):
    """Choose the action that goes to the final grounding. Recorded v2 comparisons: `adopt` (fills a missing
    operational action only). v3: keep the incumbent unless a clearly preferred candidate is valid, has no issue, is
    temporally eligible and shares evidence with the draft's claims; then it replaces the incumbent with its exact
    text, evidence, premises and need. Review reasons are untouched. Returns (draft, note or None)."""
    from threadsense.agents.advisor_contracts import ActionProposal, InterventionNeed
    if tot['status'] != 'COMPARED':
        return draft, None
    if tot.get('contract_version', 'agent3-tot-comparison-v2') == 'agent3-tot-comparison-v2':
        return adopt(tot, draft)
    chosen = next((c for c in tot['candidates'] if c['candidate_id'] == tot['model_preferred_candidate_id']), None)
    if tot['close_call'] or tot.get('decision') == 'CLOSE_CALL':
        return draft, 'Close call: the draft action is kept; the reviewed alternatives stay visible for the team lead.'
    if chosen is None or chosen.get('incumbent') or tot.get('decision') == 'KEEP_INCUMBENT':
        return draft, 'ToT kept the draft action (incumbent).' if draft.proposed_action else None
    support = premises(chosen['evidence_ids'], draft)
    operational = chosen['action_type'] != 'NO_ACTION'
    reason = ('not valid' if not chosen['valid'] else f"candidate issues {chosen['issues']}" if chosen['issues'] else
              'no draft claim shares its evidence' if not support else None)
    if reason:
        return draft, f"ToT candidate {chosen['candidate_id']} not adopted: {reason}."
    try:
        need = chosen.get('intervention_need')
        action = ActionProposal(action_type=chosen['action_type'], instruction=chosen.get('instruction'),
                                draft_text=chosen['draft_text'], support_claim_ids=support, rationale=chosen['rationale'],
                                intervention_need=InterventionNeed.model_validate(need) if need and operational else None)
    except ValueError as error:  # e.g. a documentation action without targets
        return draft, f"ToT candidate {chosen['candidate_id']} not adopted: {str(error).splitlines()[-1][:200]}"
    replaced = draft.proposed_action.action_type if draft.proposed_action else 'none'
    tot['selected_candidate_id'] = chosen['candidate_id']
    return (draft.model_copy(update={'proposed_action': action}),
            f"Action selected from ToT candidate {chosen['candidate_id']} (replaces the draft's {replaced}); the final "
            'grounding judges it like any action.')


def adopt(tot, draft):
    """A selected candidate may become the proposed action before final grounding: only when the draft has no
    operational action, the model preferred one candidate (not a close call), it is valid, operational, has no
    applicability issue, and shares evidence with at least one draft claim (its premises). The final grounding then
    judges it like any action. Review reasons are untouched. Returns (draft, note or None)."""
    from threadsense.agents.advisor_contracts import ActionProposal
    current = draft.proposed_action
    if tot['status'] != 'COMPARED' or (current and current.action_type != 'NO_ACTION'):
        return draft, None
    chosen = next((c for c in tot['candidates'] if c['candidate_id'] == tot['model_preferred_candidate_id']), None)
    if chosen is None or tot['close_call']:
        return draft, None
    support = premises(chosen['evidence_ids'], draft)
    reason = ('not valid' if not chosen['valid'] else 'not operational' if chosen['action_type'] == 'NO_ACTION' else
              f"candidate issues {chosen['issues']}" if chosen['issues'] else 'no draft claim shares its evidence' if not support
              else None)
    if reason:
        return draft, f"ToT candidate {chosen['candidate_id']} not adopted: {reason}."
    try:
        action = ActionProposal(action_type=chosen['action_type'], instruction=chosen.get('instruction'),
                                draft_text=chosen['draft_text'], support_claim_ids=support,
                                rationale=chosen['rationale'])  # The source is recorded structurally (action_source TOT).
    except ValueError as error:  # e.g. a documentation action without targets
        return draft, f"ToT candidate {chosen['candidate_id']} not adopted: {str(error).splitlines()[-1][:200]}"
    return draft.model_copy(update={'proposed_action': action}), f"Action selected from ToT candidate {chosen['candidate_id']}."


def alternatives(tot):
    """Candidates the final grounding call judges (invalid ones are never presented as grounded). A candidate already
    selected as the action is judged as the action, not twice."""
    return [c for c in tot.get('candidates', []) if c['valid'] and c['candidate_id'] != tot.get('selected_candidate_id')]


def finalize(tot, grounding):
    """Attach each candidate's own final verdict and sufficiency check; prefer only a valid, SUPPORTED candidate."""
    if tot['status'] != 'COMPARED':
        return tot
    verdicts = {s['statement_id']: s['verdict'] for s in grounding['statements']}
    sufficiency = grounding.get('alternative_sufficiency') or {}
    candidates = [{**c, 'grounding': verdicts.get(f"alternative:{c['candidate_id']}", 'NOT_JUDGED') if c['valid']
                   else 'NOT_PRESENTED_INVALID', 'sufficiency': sufficiency.get(f"alternative:{c['candidate_id']}")}
                  for c in tot['candidates']]
    grounded = {c['candidate_id'] for c in candidates if c['grounding'] == 'SUPPORTED'}
    preferred = tot['model_preferred_candidate_id'] if tot['model_preferred_candidate_id'] in grounded else None
    return {**tot, 'candidates': candidates, 'preferred_candidate_id': preferred, 'grounded_candidate_ids': sorted(grounded),
            'presentation': 'PREFERRED_WITH_ALTERNATIVES' if preferred and not tot['close_call'] else
            'SURFACE_GROUNDED_ALTERNATIVES' if grounded else 'NO_GROUNDED_ALTERNATIVES',
            'note': 'Alternatives for the reviewer, each with its own grounding verdict; the card action and review '
                    'reasons are unchanged by this comparison.'}


def fallback(tot, draft, verdict):
    """After final validation, when the draft action did not reach the card: the model's preferred, already-reviewed
    candidate may replace it, only if it is operational and valid with no issue, not a close call, its exact text was
    judged SUPPORTED, and its sufficiency check passed (essential premises in the final supported set). Nothing is
    rewritten; review reasons are untouched. Returns (action or None, essential premise IDs, note or None)."""
    from threadsense.agents.advisor_contracts import ActionProposal
    if tot['status'] != 'COMPARED' or draft.proposed_action is None or draft.proposed_action.action_type == 'NO_ACTION':
        return None, None, None
    if verdict == 'NO_INTERVENTION_NEED':  # No intervention is justified; another action would not change that.
        return None, None, 'No ToT fallback: the evidence did not show a need to intervene.'
    if tot.get('selected_candidate_id') and tot['selected_candidate_id'] == tot['model_preferred_candidate_id']:
        return None, None, 'No ToT fallback: the preferred candidate was already the action and was withheld.'
    chosen = next((c for c in tot['candidates'] if c['candidate_id'] == tot['model_preferred_candidate_id']), None)
    if chosen is None:
        return None, None, 'No ToT fallback: no preferred candidate.'
    check = (chosen.get('sufficiency') or {}).get('check')
    reason = ('close call' if tot['close_call'] else 'not operational' if chosen['action_type'] == 'NO_ACTION' else
              'not valid' if not chosen['valid'] else f"issues {chosen['issues']}" if chosen['issues'] else
              f"text judged {chosen['grounding']}" if chosen['grounding'] != 'SUPPORTED' else
              f'sufficiency check {check}' if check != 'SUPPORTED' else None)
    if reason:
        return None, None, f"No ToT fallback: preferred candidate {chosen['candidate_id']}: {reason}."
    try:
        from threadsense.agents.advisor_contracts import InterventionNeed
        need = chosen.get('intervention_need')
        action = ActionProposal(action_type=chosen['action_type'], instruction=chosen.get('instruction'),
                                draft_text=chosen['draft_text'], rationale=chosen['rationale'],
                                support_claim_ids=chosen['premise_ids'],
                                intervention_need=InterventionNeed.model_validate(need) if need else None)
    except ValueError as error:  # e.g. a documentation action without targets
        return None, None, f"No ToT fallback: candidate {chosen['candidate_id']}: {str(error).splitlines()[-1][:200]}"
    essential = chosen['sufficiency']['essential_statement_ids']
    return action, essential, (f"Draft action withheld ({verdict}); card action is reviewed ToT candidate "
                               f"{chosen['candidate_id']}, judged SUPPORTED with sufficient final premises.")
