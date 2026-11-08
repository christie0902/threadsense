"""ToT comparison policies: the production policy and an opt-in shadow check (never routes).

Production (`advisor_tot.select`, controller `agent3-tot-controller-v2`): the comparison model's categorical decision
plus deterministic eligibility gates; an explicit REPLACE_INCUMBENT naming an eligible candidate replaces the incumbent.

Shadow (`agent3-tot-shadow-partial-order-v1`, `advise(tot_shadow=True)`): for an explicit proposed replacement only, a
conservative check of the challenger against the incumbent on the comparison's own categorical ratings, as a partial
order with no numerical score. It never invents a challenger, never turns a close call into a preference, never
replaces anything and never changes the card, routing or a request; it records what it would have done.

Per-dimension relation (CHALLENGER_BETTER, INCUMBENT_BETTER, EQUAL, UNRESOLVED):
- evidence_support, need_strength: STRONG > PARTIAL > WEAK > NONE. need_strength compares two operational candidates
  only: intervening versus observing (NO_ACTION) is settled by the final grounding of the incumbent's intervention need
  (`action:need`), so that pair is UNRESOLVED.
- severity_fit: FITS > PARTIAL > POOR; UNKNOWN is unresolved.
- temporal_scope: CONSISTENT > ISSUE; UNCLEAR is unresolved.
- proportionality: FITS beats EXCESSIVE and INSUFFICIENT; EXCESSIVE versus INSUFFICIENT are different problems
  (UNRESOLVED); UNCLEAR is unresolved; the same rating on both sides is EQUAL.
- applicability is an eligibility gate, not a preference: the existing checks already bar historical-only support for an
  operational action and claimed-current applicability the ledger does not record. Mixed current and historical evidence
  is not ranked below current-only evidence.
- A missing rating on either side is UNRESOLVED: it cannot show that a candidate is at least as good.

Assessment of an explicit proposed replacement:
- INELIGIBLE: the existing validity, issue, premise or action-contract checks reject the challenger.
- TRADE_OFF: each candidate is better on at least one dimension.
- INSUFFICIENT_COMPARISON: an unresolved dimension prevents a conclusion.
- CLEAR_ADVANTAGE: the challenger is better on at least one dimension and no worse on any, with nothing unresolved.
- INCUMBENT_ADVANTAGE: the incumbent is better on at least one dimension and no worse on any.
- RATING_TIE: no difference on any dimension.
Only CLEAR_ADVANTAGE would let the replacement stand on its own; otherwise the post-grounding viability rules decide.
"""
from hashlib import sha256
import inspect
from types import SimpleNamespace

from threadsense.agents.advisor_checks import CURRENT_USES, STALE_USES
from threadsense.agents.advisor_tot import _same_action

SHADOW_POLICY_VERSION = 'agent3-tot-shadow-partial-order-v1'
LEVELS = ('NONE', 'WEAK', 'PARTIAL', 'STRONG')
FIT = ('POOR', 'PARTIAL', 'FITS')
DIMENSIONS = ('evidence_support', 'need_strength', 'severity_fit', 'temporal_scope', 'proportionality')
APPLICABLE_USES = CURRENT_USES | {'ANNOUNCEMENT'}
GUIDANCE_KINDS = {'GUIDANCE', 'THREAD_INSTRUCTION', 'CAUSE'}
DESCRIPTIVE_KINDS = {'HISTORY', 'SOURCE_FACT'}


def _ranked(order, a, b):
    if a not in order or b not in order:
        return 'UNRESOLVED', 'MISSING' if a is None or b is None else 'UNKNOWN'
    i, c = order.index(a), order.index(b)
    return ('EQUAL' if i == c else 'CHALLENGER_BETTER' if c > i else 'INCUMBENT_BETTER'), None


def relation(dimension, incumbent, challenger):
    """(relation, reason) for one dimension; incumbent and challenger are saved candidate dicts."""
    a, b = incumbent.get(dimension), challenger.get(dimension)
    if dimension == 'evidence_support':
        return _ranked(LEVELS, a, b)
    if dimension == 'need_strength':
        if 'NO_ACTION' in (incumbent['action_type'], challenger['action_type']):
            return 'UNRESOLVED', 'INTERVENTION_VS_OBSERVATION'
        return _ranked(LEVELS, a, b)
    if dimension == 'severity_fit':
        return _ranked(FIT, a, b)
    if dimension == 'temporal_scope':
        return _ranked(('ISSUE', 'CONSISTENT'), a, b)
    if a is None or b is None:  # proportionality
        return 'UNRESOLVED', 'MISSING'
    if 'UNCLEAR' in (a, b):
        return 'UNRESOLVED', 'UNKNOWN'
    if a == b:
        return 'EQUAL', None
    if 'FITS' in (a, b):
        return ('CHALLENGER_BETTER' if b == 'FITS' else 'INCUMBENT_BETTER'), None
    return 'UNRESOLVED', 'INCOMPARABLE'  # EXCESSIVE versus INSUFFICIENT


def eligibility(challenger):
    """The existing gates `select` applies before a replacement (reason, or None when eligible)."""
    from threadsense.agents.advisor_contracts import ActionProposal, InterventionNeed
    if not challenger['valid']:
        return 'not valid (unknown evidence or support claimed without evidence)'
    if challenger['issues']:
        return f"candidate issues {challenger['issues']}"
    if not challenger.get('premise_ids'):
        return 'no draft claim shares its evidence'
    need = challenger.get('intervention_need')
    try:
        ActionProposal(action_type=challenger['action_type'], instruction=challenger.get('instruction'),
                       draft_text=challenger['draft_text'], rationale=challenger['rationale'],
                       support_claim_ids=challenger['premise_ids'],
                       intervention_need=InterventionNeed.model_validate(need) if need and challenger['action_type'] != 'NO_ACTION'
                       else None)
    except ValueError as error:  # e.g. a documentation action: candidates carry no targets
        return f'action contract: {str(error).splitlines()[-1][:160]}'
    return None


def assess(incumbent, challenger):
    """Assessment of `challenger` replacing `incumbent` (saved candidate dicts after check_candidates)."""
    reason = eligibility(challenger)
    if reason:
        return {'assessment': 'INELIGIBLE', 'ineligible_reason': reason, 'dimensions': [], 'supporting': [], 'opposing': [],
                'unresolved': []}
    dims = []
    for d in DIMENSIONS:
        rel, why = relation(d, incumbent, challenger)
        dims.append({'dimension': d, 'incumbent': incumbent.get(d), 'challenger': challenger.get(d), 'relation': rel,
                     **({'reason': why} if why else {})})
    better = [d['dimension'] for d in dims if d['relation'] == 'CHALLENGER_BETTER']
    worse = [d['dimension'] for d in dims if d['relation'] == 'INCUMBENT_BETTER']
    unresolved = [d['dimension'] for d in dims if d['relation'] == 'UNRESOLVED']
    verdict = ('TRADE_OFF' if better and worse else 'INSUFFICIENT_COMPARISON' if unresolved else 'CLEAR_ADVANTAGE' if better
               else 'INCUMBENT_ADVANTAGE' if worse else 'RATING_TIE')
    return {'assessment': verdict, 'dimensions': dims, 'supporting': better, 'opposing': worse, 'unresolved': unresolved,
            'applicability': {'incumbent': incumbent.get('recorded_applicability'),
                              'challenger': challenger.get('recorded_applicability'), 'role': 'ELIGIBILITY_GATE'}}


def proposal(tot):
    """(kind, incumbent, challenger). Only EXPLICIT_REPLACEMENT is assessed; every other kind keeps production handling."""
    cands = tot.get('candidates') or []
    incumbent = next((c for c in cands if c.get('incumbent')), None)
    preferred = next((c for c in cands if c['candidate_id'] == tot.get('model_preferred_candidate_id')), None)
    if tot.get('contract_version', 'agent3-tot-comparison-v2') == 'agent3-tot-comparison-v2':
        return 'LEGACY_V2', incumbent, None
    if tot.get('close_call') or tot.get('decision') == 'CLOSE_CALL':
        return 'CLOSE_CALL', incumbent, None
    if tot.get('decision') != 'REPLACE_INCUMBENT':
        return ('KEEP_INCUMBENT' if tot.get('decision') == 'KEEP_INCUMBENT' else 'NO_DECISION'), incumbent, None
    if preferred is None or preferred.get('incumbent'):
        return 'INCONSISTENT_REPLACE', incumbent, None
    if incumbent is None:
        return 'NO_INCUMBENT', None, preferred
    return 'EXPLICIT_REPLACEMENT', incumbent, preferred


def viable(candidate):
    """Post-grounding viability (as advisor_tot.choice_after_grounding): valid, issue-free, its exact text SUPPORTED,
    and its sufficiency check passed (NO_ACTION needs no sufficiency)."""
    sufficient = candidate['action_type'] == 'NO_ACTION' or (candidate.get('sufficiency') or {}).get('check') == 'SUPPORTED'
    return bool(candidate['valid'] and not candidate['issues'] and candidate.get('grounding') == 'SUPPORTED' and sufficient)


def outcome(assessed, incumbent, challenger, card_link):
    """What the shadow policy would show after the final grounding, from the saved verdicts. The challenger is viable only
    if it reached the card as the selected action (production judged it as `action`); the displaced incumbent was judged
    as an alternative."""
    challenger_ok = bool(card_link and card_link.get('basis') == 'SELECTED'
                         and card_link.get('candidate_id') == challenger['candidate_id'])
    incumbent_ok = viable(incumbent)
    options = [c['candidate_id'] for c, ok in ((challenger, challenger_ok), (incumbent, incumbent_ok)) if ok]
    if assessed == 'INELIGIBLE':
        status, text = 'PRODUCTION_ALSO_KEEPS', 'The existing gates reject the challenger; production keeps the incumbent too.'
    elif assessed == 'CLEAR_ADVANTAGE' and challenger_ok:
        status, text = 'REPLACEMENT_STANDS', 'The ratings establish the replacement and the final grounding supported it.'
    elif challenger_ok and incumbent_ok and challenger['action_type'] != incumbent['action_type']:
        status, text = 'TL_CHOICE', ('The ratings do not establish the replacement and both actions remain eligible after the '
                                     'final grounding: show both, neither preferred, for the team lead to choose.')
    elif challenger_ok and incumbent_ok:
        status, text = 'INCUMBENT_KEPT', ('The ratings do not establish the replacement; both are wordings of the same action '
                                          'type, so the incumbent would be kept and no unresolved choice created.')
    elif len(options) == 1:
        status, text = 'SINGLE_ELIGIBLE_ACTION', (f'Only {options[0]} remains eligible after the final grounding; it stands '
                                                  'and no unresolved choice is created.')
    else:
        status, text = 'NO_ELIGIBLE_ACTION', 'Neither action remains eligible after the final grounding.'
    return {'status': status, 'eligible_after_grounding': options, 'explanation': text}


def incumbent_issues(result):
    """Disposition of each issue recorded on a kept incumbent that is the card action, from saved records only (no new
    verdict, no relabelling). LABEL_OVERSTATEMENT: the action passed the final grounding and sufficiency and every
    essential premise is SUPPORTED and rests on applicable evidence (or describes a historical item as history); the
    non-current items the candidate cites are documentation targets, historical premises or comparison context.
    MATERIAL_CONCERN: an essential premise is not SUPPORTED, or a guidance-type essential premise rests only on non-current
    evidence (named in affected_premises). NOT_THE_CARD_ACTION: preserved, does not affect the card."""
    tot = result.get('tot') or {}
    incumbent = next((c for c in tot.get('candidates') or [] if c.get('incumbent')), None)
    if incumbent is None or not incumbent['issues']:
        return []
    link = tot.get('card_action') or {}
    base = {'candidate_id': incumbent['candidate_id'], 'issues': list(incumbent['issues']),
            'claimed_applicability': incumbent.get('applicability'), 'recorded_applicability': incumbent.get('recorded_applicability')}
    action = (result.get('card') or {}).get('recommended_action')
    if not action or not _same_action(incumbent, SimpleNamespace(**action)) or link.get('basis') not in (None, 'INCUMBENT'):
        return [{**base, 'disposition': 'NOT_THE_CARD_ACTION'}]
    ledger, grounding = result['evidence_ledger'], result['grounding']
    verdicts = {s['statement_id']: s['verdict'] for s in grounding['statements']}
    sufficiency = grounding.get('action_sufficiency') or {}
    claims = {c['claim_id']: c for c in (result['drafts']['final'] or {}).get('claims', [])}
    essential = [s.split(':', 1)[1] for s in sufficiency.get('essential_statement_ids') or [] if s.startswith('claim:')]
    affected = []
    for cid in essential:
        claim, uses = claims.get(cid), None
        if claim is None or verdicts.get(f'claim:{cid}') != 'SUPPORTED':
            affected.append({'premise': f'claim:{cid}', 'reason': f"verdict {verdicts.get(f'claim:{cid}')}"})
            continue
        uses = {ledger[e]['use'] for e in claim['evidence_ids'] if e in ledger}
        if claim['kind'] in GUIDANCE_KINDS and not uses & APPLICABLE_USES:
            affected.append({'premise': f'claim:{cid}', 'reason': f"{claim['kind']} resting only on {sorted(uses)}"})
    targets = {t['evidence_id'] for t in action.get('targets') or []}
    history_premises = {e for cid in essential if cid in claims and claims[cid]['kind'] in DESCRIPTIVE_KINDS
                        for e in claims[cid]['evidence_ids']}
    noncurrent = [{'evidence_id': e, 'use': ledger[e]['use'],
                   'role': 'DOCUMENTATION_TARGET' if e in targets else 'HISTORICAL_PREMISE' if e in history_premises
                   else 'COMPARISON_CONTEXT'}
                  for e in incumbent['evidence_ids'] if e in ledger and ledger[e]['use'] in STALE_USES | {'PRIOR_DECISION'}]
    passed = verdicts.get('action') == 'SUPPORTED' and sufficiency.get('verdict') == 'SUFFICIENT'
    if not passed:
        affected.append({'premise': 'action', 'reason': f"action {verdicts.get('action')}, sufficiency {sufficiency.get('verdict')}"})
    return [{**base, 'disposition': 'MATERIAL_CONCERN' if affected else 'LABEL_OVERSTATEMENT',
             'action_verdict': verdicts.get('action'), 'sufficiency': sufficiency.get('verdict'),
             'essential_premises': [f'claim:{c}' for c in essential], 'affected_premises': affected,
             'non_current_citations': noncurrent}]


def shadow(result):
    """The shadow record for one saved topic result (None when no comparison ran). Never read by routing."""
    tot = result.get('tot') or {}
    if tot.get('status') != 'COMPARED':
        return None
    kind, incumbent, challenger = proposal(tot)
    record = {'policy': SHADOW_POLICY_VERSION, 'proposal': kind,
              'model': {'decision': tot.get('decision'), 'close_call': tot.get('close_call'),
                        'preferred_candidate_id': tot.get('model_preferred_candidate_id'), 'rationale': tot.get('rationale')},
              'production_card_action': tot.get('card_action')}
    if kind == 'EXPLICIT_REPLACEMENT':
        assessed = assess(incumbent, challenger)
        record.update(challenger_id=challenger['candidate_id'], incumbent_id=incumbent['candidate_id'], **assessed,
                      agrees_with_model=assessed['assessment'] == 'CLEAR_ADVANTAGE',
                      outcome=outcome(assessed['assessment'], incumbent, challenger, tot.get('card_action')))
        if not record['agrees_with_model']:
            record['note'] = (f"The comparison model proposed replacing {incumbent['candidate_id']} with "
                              f"{challenger['candidate_id']}; the ratings give {assessed['assessment']}, so the shadow "
                              "policy would not let that preference stand on its own.")
    else:
        record['outcome'] = {'status': 'SAME_AS_PRODUCTION', 'eligible_after_grounding': [],
                             'explanation': f'No explicit proposed replacement ({kind}); production handling applies unchanged.'}
    if incumbent is not None:  # Informational: how each unproposed candidate's ratings relate to the incumbent's.
        record['unproposed_relations'] = [
            {'candidate_id': c['candidate_id'], 'action_type': c['action_type'], **{k: v for k, v in assess(incumbent, c).items()
                                                                                    if k in ('assessment', 'ineligible_reason', 'supporting', 'opposing', 'unresolved')}}
            for c in tot['candidates'] if not c.get('incumbent') and (challenger is None or c is not challenger)]
    record['incumbent_issues'] = incumbent_issues(result)
    return record


def fingerprint():
    source = inspect.getsource(inspect.getmodule(fingerprint)).replace('\r\n', '\n')
    return {'version': SHADOW_POLICY_VERSION, 'sha256': sha256(source.encode('utf-8')).hexdigest()}
