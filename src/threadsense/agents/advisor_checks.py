"""Deterministic Advisor checks; no model calls.

- structural pre-checks: cited IDs exist, claim kinds use the right evidence (incident facts
  from member messages, current guidance from current sources or established announcements),
  quotes are verbatim, documentation targets are real and not already current, resolution
  rests on the member's own thread;
- final statements: every statement that can reach a card (claims, summary, action,
  announcement handling, member resolution, severity rationale and signals, affected
  reporters) plus ToT alternatives, judged by ONE final semantic grounding call;
- authorization: the card is assembled only from statements whose verdict (after
  dependencies) is SUPPORTED; everything else is withheld and kept in diagnostics;
- temporal priority from recorded supersession; severity bound to the unchanged rubric;
  Agent 1 resolution states are attributed inputs, never evidence.
Nothing runs after the final grounding call except this authorization, which only removes.
"""
from collections import Counter

from pydantic import ValidationError

from threadsense.agents.advice_contracts import (
    AdviceCard, CountEvidence, EvidenceRef, InheritedFlag, OccurrenceEvidence, ReviewReason, SeverityAssessment,
    SignalMatch, ThreadRef, stable_id, unassessed_severity,
)
from threadsense.agents.advice_inputs import structural_occurrence
from threadsense.severity_rubric import signal_reference_issues

CURRENT_USES = {'CURRENT_GUIDANCE', 'CURRENT_HANDLING'}
STALE_USES = {'HISTORY_ONLY', 'UNRESOLVED_VERSION'}
KNOWLEDGE_USES = CURRENT_USES | STALE_USES | {'ANNOUNCEMENT', 'PRIOR_DECISION'}
BANNERED_USES = STALE_USES | {'ANNOUNCEMENT', 'PRIOR_DECISION'}
RESOLUTION_STATES = ('UNRESOLVED', 'PARTIALLY_RESOLVED', 'RESOLVED_IN_THREAD')


def _norm(text):
    return ' '.join(text.split()).casefold()


def source_text(item):
    """Excerpt without the status banner the pilot added (quotes must come from the source)."""
    if item['use'] in BANNERED_USES and item['excerpt'].startswith('['):
        return item['excerpt'].split('\n', 1)[1] if '\n' in item['excerpt'] else ''
    return item['excerpt']


def _verbatim(quote, items):
    return any(_norm(quote) in _norm(source_text(item)) for item in items)


def _issue(claim_id, code, detail):
    return {'claim_id': claim_id, 'code': code, 'detail': detail}


def established(draft, ledger):
    """Announcements the draft shows to be relevant directives (verbatim quote); grounding still verifies them."""
    return {a.evidence_id for a in draft.announcement_assessments
            if a.relevant and a.directive and ledger.get(a.evidence_id, {}).get('use') == 'ANNOUNCEMENT'
            and _verbatim(a.directive_quote, [ledger[a.evidence_id]])}


def claim_issues(draft, ledger):
    """Structural grounding failures; any one makes grounding FAILED without a semantic call."""
    issues, handling = [], established(draft, ledger)
    for claim in draft.claims:
        unknown = [i for i in claim.evidence_ids if i not in ledger]
        if unknown:
            issues.append(_issue(claim.claim_id, 'UNKNOWN_EVIDENCE', f'Cites evidence not in the ledger: {unknown}.'))
            continue
        items = [ledger[i] for i in claim.evidence_ids]
        uses = {item['use'] for item in items}
        if claim.material and not items:
            issues.append(_issue(claim.claim_id, 'NO_CITATION', 'Material claim cites no evidence.'))
        if claim.kind == 'INCIDENT_FACT' and uses - {'MEMBER_REPORT'}:
            issues.append(_issue(claim.claim_id, 'INCIDENT_FACT_NEEDS_MEMBER_EVIDENCE',
                                 'Incident facts must come from member messages, not retrieved sources.'))
        if claim.kind == 'GUIDANCE':
            if not (uses & CURRENT_USES or handling & set(claim.evidence_ids)):
                announced = [i for i in claim.evidence_ids if ledger[i]['use'] == 'ANNOUNCEMENT']
                issues.append(_issue(claim.claim_id, 'ANNOUNCEMENT_NOT_ESTABLISHED_AS_HANDLING', 'Cited announcements '
                                     f'{announced} are not assessed as relevant directives for this topic.') if announced else
                              _issue(claim.claim_id, 'GUIDANCE_WITHOUT_CURRENT_SOURCE',
                                     'Guidance must cite a current guideline or FAQ, or an established announcement.'))
            stale = [item['evidence_id'] for item in items if item['use'] in STALE_USES]
            if stale:
                issues.append(_issue(claim.claim_id, 'HISTORICAL_SOURCE_AS_CURRENT_GUIDANCE',
                                     f'Historical or unresolved sources cannot support current guidance: {stale}.'))
        if claim.kind == 'HISTORY' and not uses & KNOWLEDGE_USES:
            issues.append(_issue(claim.claim_id, 'HISTORY_WITHOUT_RECORD', 'History claims cite retrieved records.'))
        if claim.quote and not _verbatim(claim.quote, items):
            issues.append(_issue(claim.claim_id, 'QUOTE_NOT_VERBATIM', 'Quote is not verbatim in any cited excerpt.'))
    return issues


def announcement_issues(draft, ledger):
    issues = []
    for a in draft.announcement_assessments:
        sid, item = f'announcement:{a.evidence_id}', ledger.get(a.evidence_id)
        if item is None:
            issues.append(_issue(sid, 'UNKNOWN_EVIDENCE', 'Assessed announcement is not in the ledger.'))
        elif item['use'] != 'ANNOUNCEMENT':
            issues.append(_issue(sid, 'NOT_A_CURRENT_ANNOUNCEMENT', f"Assessed item is {item['use']}, not a current announcement."))
        elif a.relevant and a.directive and not _verbatim(a.directive_quote, [item]):
            issues.append(_issue(sid, 'QUOTE_NOT_VERBATIM', 'Directive quote is not verbatim in the announcement.'))
    return issues


def resolution_issues(draft, ledger, member_ids):
    """A member's state rests on its own thread messages; current sources may add support; history may not."""
    issues = []
    for r in draft.resolution:
        sid = f'resolution:{r.member_id}'
        if r.member_id not in member_ids:
            issues.append(_issue(sid, 'UNKNOWN_MEMBER', 'Resolution names a member outside this topic.'))
            continue
        if r.state == 'UNKNOWN':
            continue
        items = [ledger.get(e) for e in r.evidence_ids]
        if None in items:
            issues.append(_issue(sid, 'UNKNOWN_EVIDENCE', 'Resolution cites evidence not in the ledger.'))
            continue
        if not any(i['use'] == 'MEMBER_REPORT' and i['member_id'] == r.member_id for i in items):
            issues.append(_issue(sid, 'RESOLUTION_NEEDS_THREAD_EVIDENCE', "A resolution state cites the member's own thread."))
        if any(i['use'] in STALE_USES for i in items):
            issues.append(_issue(sid, 'RESOLUTION_FROM_HISTORICAL_SOURCE', 'Historical or unresolved sources cannot resolve a thread.'))
    return issues


def _conflicted(draft):
    return {e for c in draft.source_conflicts for e in c.evidence_ids}


def action_issues(draft, ledger):
    action = draft.proposed_action
    if action is None or action.action_type == 'NO_ACTION':
        return []
    claims = {c.claim_id: c for c in draft.claims}
    support = [claims[i] for i in action.support_claim_ids]
    if not support:
        return ['ACTION_WITHOUT_SUPPORT_CLAIMS']
    issues = []
    applicable = any(c.kind == 'GUIDANCE' or c.kind == 'HISTORY' and any(
        ledger.get(e, {}).get('use') == 'PRIOR_DECISION' for e in c.evidence_ids) for c in support)
    if not applicable:
        issues.append('ACTION_WITHOUT_APPLICABLE_SOURCE')
    allowed = {'UPDATE_FAQ': {'faq'}, 'UPDATE_DOCUMENTATION': {'guideline', 'faq'}}.get(action.action_type)
    for t in action.targets:
        item = ledger.get(t.evidence_id)
        if item is None or item['origin'] != 'retrieved_source':
            issues.append(f'ACTION_TARGET_UNKNOWN: {t.evidence_id}')
            continue
        if allowed and item['source_type'] not in allowed:
            issues.append(f"ACTION_TARGET_WRONG_TYPE: {t.evidence_id} is a {item['source_type']}")
        if t.section and t.section not in (item['citation']['sections'] or []):
            issues.append(f'ACTION_TARGET_SECTION_NOT_CITED: {t.section!r} is not a section of {t.evidence_id}')
        # Correcting current guidance implies it still holds stale wording; that needs a reported conflict.
        if t.change != 'ADD' and item['use'] in CURRENT_USES and t.evidence_id not in _conflicted(draft):
            issues.append(f'ACTION_TARGET_ALREADY_CURRENT: {t.evidence_id} is current guidance with no reported conflict')
    return issues


def structural_issues(draft, ledger, member_ids):
    return claim_issues(draft, ledger) + announcement_issues(draft, ledger) + resolution_issues(draft, ledger, member_ids)


def target_text(action, ledger):
    parts = []
    for t in action.targets:
        item = ledger.get(t.evidence_id, {})
        authoring = (item.get('citation') or {}).get('authoring') or t.evidence_id
        state = item.get('use', 'unknown')
        if (item.get('applicability') or {}).get('state') == 'SECTION_SUPERSEDED':
            state = 'superseded section, stale copy'
        parts.append(f"{t.change} {authoring}" + (f" section '{t.section}'" if t.section else '') + f' ({state})')
    return '; '.join(parts)


def _action_text(action, ledger):
    text = f'{action.action_type}: {action.draft_text or ""}'.strip()
    if action.scope_note:
        text += f' Scope: {action.scope_note}'
    if action.targets:
        text += f' Targets: {target_text(action, ledger)}. Only these targets need changing.'
    return text


def statements(draft, ledger, *, severity=None, alternatives=()):
    """Every statement that can reach the card or a reviewer, with the evidence it cites (ledger IDs only)."""
    out, seen = [], Counter()

    def add(sid, kind, text, ids, blocking=True):
        seen[sid] += 1
        sid = sid if seen[sid] == 1 else f'{sid}#{seen[sid]}'
        out.append({'statement_id': sid, 'kind': kind, 'text': text, 'blocking': blocking,
                    'evidence_ids': list(dict.fromkeys(i for i in ids if i in ledger))})
    for c in draft.claims:
        add(f'claim:{c.claim_id}', f'CLAIM_{c.kind}', c.text + (f' Quote: "{c.quote}"' if c.quote else ''),
            c.evidence_ids, c.material)
    add('summary', 'SUMMARY', draft.summary, [e for c in draft.claims if c.material for e in c.evidence_ids])
    action = draft.proposed_action
    # A bare NO_ACTION (no text) states nothing to judge; anything with text or an operation is judged.
    if action is not None and draft.evidence_sufficiency != 'UNSUPPORTED' and (action.action_type != 'NO_ACTION' or action.draft_text):
        support = [e for c in draft.claims if c.claim_id in action.support_claim_ids for e in c.evidence_ids]
        add('action', 'ACTION', _action_text(action, ledger), support + [t.evidence_id for t in action.targets])
    for a in draft.announcement_assessments:
        if a.relevant and a.directive:
            add(f'announcement:{a.evidence_id}', 'ANNOUNCEMENT_HANDLING', 'This announcement applies to this topic and '
                f'directs current handling: "{a.directive_quote}". {a.rationale}', [a.evidence_id])
    for r in draft.resolution:
        if r.state != 'UNKNOWN':
            add(f'resolution:{r.member_id}', 'RESOLUTION', f'Member thread {r.member_id} is {r.state}: {r.basis}', r.evidence_ids)
    if severity is not None and severity.assessment_status == 'ASSESSED':
        p = draft.severity
        incident = [e for c in draft.claims if c.kind == 'INCIDENT_FACT' for e in c.evidence_ids]
        add('severity:rationale', 'SEVERITY_RATIONALE', f'Severity {p.level}: {p.rationale}',
            [e for s in p.signals for e in s.evidence_ids] + [r.evidence_id for r in p.affected_reporters] + incident)
        for s in p.signals:
            add(f'severity:signal:{s.level}[{s.signal_index}]', 'SEVERITY_SIGNAL',
                f'Rubric signal met - "{s.signal_text}": {s.support}', s.evidence_ids)
        for author in dict.fromkeys(r.author_id for r in p.affected_reporters):
            ids = [r.evidence_id for r in p.affected_reporters if r.author_id == author]
            add(f'reporter:{author}', 'AFFECTED_REPORTER',
                f'{author} reports, in their own cited message, being affected by this problem.', ids)
    for c in alternatives:
        add(f"alternative:{c['candidate_id']}", 'ALTERNATIVE',
            f"{c['action_type']}: {c['draft_text']} Rationale: {c['rationale']}", c['evidence_ids'], blocking=False)
    return out


def _effective(draft, ledger, verdicts):
    """Verdicts after dependencies: guidance resting only on announcements needs a verified announcement;
    an action needs every support claim; nothing borrows another statement's SUPPORTED verdict."""
    out = dict(verdicts)
    verified = {e for e in established(draft, ledger) if verdicts.get(f'announcement:{e}') == 'SUPPORTED'}
    claims = {c.claim_id: c for c in draft.claims}
    for c in draft.claims:
        sid = f'claim:{c.claim_id}'
        if c.kind == 'GUIDANCE' and out.get(sid) == 'SUPPORTED' and not (
                {ledger[e]['use'] for e in c.evidence_ids} & CURRENT_USES or verified & set(c.evidence_ids)):
            out[sid] = 'ANNOUNCEMENT_NOT_VERIFIED'
    if out.get('action') == 'SUPPORTED' and draft.proposed_action and any(
            out.get(f'claim:{i}') != 'SUPPORTED' for i in draft.proposed_action.support_claim_ids if i in claims):
        out['action'] = 'SUPPORT_CLAIM_WITHHELD'
    return out


def grounding_result(draft, ledger, stmts, *, structural=(), actions=(), judgment=None, ran=False, reason=None):
    """PASSED only when structural checks pass and every blocking statement is SUPPORTED after dependencies.
    Statements citing nothing are never sent and count as NO_EVIDENCE."""
    result = {'structural_issues': list(structural), 'action_issues': list(actions), 'unsupported': [], 'unjudged': [],
              'extraneous_verdicts': []}
    if structural or actions:
        return {**result, 'status': 'FAILED', 'basis': 'STRUCTURAL',
                'statements': [{**s, 'verdict': 'NOT_JUDGED', 'rationale': None} for s in stmts]}
    if not ran:
        return {**result, 'status': 'NOT_RUN', 'basis': reason or 'SEMANTIC_JUDGMENT_UNAVAILABLE',
                'statements': [{**s, 'verdict': 'NOT_JUDGED', 'rationale': None} for s in stmts]}
    given = {v.statement_id: v for v in judgment.verdicts}
    raw = {s['statement_id']: ('NO_EVIDENCE' if not s['evidence_ids'] else given[s['statement_id']].verdict
                               if s['statement_id'] in given else 'NOT_JUDGED') for s in stmts}
    effective = _effective(draft, ledger, raw)
    judged = [{**s, 'verdict': effective[s['statement_id']], 'model_verdict': raw[s['statement_id']],
               'rationale': given[s['statement_id']].rationale if s['statement_id'] in given else None} for s in stmts]
    blocking = [s for s in judged if s['blocking']]
    unjudged = [s['statement_id'] for s in blocking if s['verdict'] == 'NOT_JUDGED']
    unsupported = [s['statement_id'] for s in blocking if s['verdict'] not in ('SUPPORTED', 'NOT_JUDGED')]
    return {**result, 'status': 'FAILED' if unjudged or unsupported else 'PASSED', 'basis': 'SEMANTIC',
            'statements': judged, 'unsupported': unsupported, 'unjudged': unjudged,
            'extraneous_verdicts': sorted(set(given) - set(raw))}


def _explained(old, new):
    """True when recorded supersession says `new` replaced (part of) `old`."""
    new_authoring = new['citation']['authoring']
    if new_authoring and any(r['replaced_by'] == new_authoring for r in old['applicability']['replaced_by']):
        return True
    old_authoring = (old['citation']['authoring'] or '@').split('@')
    return any([s['document_id'], s['version']] == old_authoring for s in new['applicability']['supersedes'])


def temporal_check(draft, ledger, handling=None):
    """Temporal priority from recorded dates/supersession only; never resolves by itself. `handling`: the
    announcements accepted as current (defaults to those the draft establishes, before grounding)."""
    handling = established(draft, ledger) if handling is None else handling
    findings = []
    for conflict in draft.source_conflicts:
        items = [ledger.get(i) for i in conflict.evidence_ids]
        if any(item is None for item in items):
            findings.append({'status': 'DETECTED', 'code': 'CONFLICT_CITES_UNKNOWN_EVIDENCE',
                             'evidence_ids': conflict.evidence_ids, 'detail': conflict.description})
            continue
        current = [i for i in items if i['use'] in CURRENT_USES or i['evidence_id'] in handling]
        older = [i for i in items if i['use'] == 'HISTORY_ONLY']
        if current and older and all(any(_explained(o, c) for c in current) for o in older) and len(current) == 1:
            findings.append({'status': 'RESOLVED_BY_RECORDED_SUPERSESSION', 'code': 'SUPERSEDED_SOURCE_EXPLAINS_CONFLICT',
                             'evidence_ids': conflict.evidence_ids, 'detail': conflict.description,
                             'current': current[0]['evidence_id']})
        else:
            findings.append({'status': 'DETECTED', 'code': 'UNEXPLAINED_SOURCE_CONFLICT',
                             'evidence_ids': conflict.evidence_ids, 'detail': conflict.description})
    cited = {e for c in draft.claims for e in c.evidence_ids if e in ledger}
    for evidence_id in sorted(cited):
        item = ledger[evidence_id]
        if item['use'] == 'UNRESOLVED_VERSION':
            findings.append({'status': 'DETECTED', 'code': 'UNRESOLVED_VERSION_CITED', 'evidence_ids': [evidence_id],
                             'detail': 'Competing revisions could not be ordered from recorded metadata.'})
        if item.get('applicability', {}).get('unverified_supersession'):
            findings.append({'status': 'DETECTED', 'code': 'UNVERIFIED_SUPERSESSION_CITED', 'evidence_ids': [evidence_id],
                             'detail': str(item['applicability']['unverified_supersession'])})
    return {'status': 'DETECTED' if any(f['status'] == 'DETECTED' for f in findings) else 'NONE_FOUND',
            'findings': findings,
            'ignored_revision_states': 'NOT_YET_EFFECTIVE and NOT_APPROVED revisions never compete with applicable guidance.'}


def evidence_ref(item, packet, handling=()):
    if item['origin'] == 'member_message':
        return EvidenceRef(kind='slack_message', project_id=packet['project_id'], batch_id=packet['batch_id'], scope='project',
                           channel_id=item['channel_id'], thread_id=item['thread_id'], message_id=item['message_id'],
                           member_id=item['member_id'], note=item['evidence_id'])
    citation, scope = item['citation'], item['scope']
    authoring = (citation['authoring'] or '').split('@') if citation['authoring'] else [None, None]
    use = 'CURRENT_HANDLING (announcement verified for this topic)' if item['evidence_id'] in handling else item['use']
    return EvidenceRef(kind='knowledge_source', project_id=scope['project_id'], batch_id=scope['batch_id'],
                       scope=scope['scope'], document_id=citation['document_id'], version_id=citation['version_id'],
                       authoring_document_id=authoring[0], authoring_version=authoring[1],
                       section=(citation['sections'] or [None])[0], chunk_id=citation['chunk_id'],
                       note=f"{item['evidence_id']} ({use}; {item['applicability']['state']})")


def build_severity(proposal, ledger, packet, rubric):
    """Bind a proposed severity to the rubric; any unsupported element leaves it UNASSESSED."""
    issues, signals = [], []
    inherited = packet.get('preliminary_severity')
    if proposal is None:
        return unassessed_severity(inherited), ['NO_SEVERITY_PROPOSAL']
    for s in proposal.signals:
        cited = [ledger.get(i) for i in s.evidence_ids]
        if None in cited:
            issues.append(f'{s.level}[{s.signal_index}] cites unknown evidence.')
            continue
        if not any(c['use'] == 'MEMBER_REPORT' for c in cited):
            issues.append(f'{s.level}[{s.signal_index}] has no member-message evidence; incident facts come from members.')
            continue
        signals.append(SignalMatch(level=s.level, signal_index=s.signal_index, signal_text=s.signal_text, support=s.support,
                                   evidence=[evidence_ref(c, packet) for c in cited]))
    reporters, reporter_refs = [], []
    for r in proposal.affected_reporters:
        item = ledger.get(r.evidence_id)
        if item is None or item['use'] != 'MEMBER_REPORT' or item['author_id'] != r.author_id:
            issues.append(f'Affected reporter {r.author_id} is not supported by their own cited message.')
        elif r.author_id not in reporters:
            reporters.append(r.author_id)
            reporter_refs.append(evidence_ref(item, packet))
    recurrence = {'status': proposal.recurrence}
    if proposal.recurrence == 'FOUND':
        cited = [ledger.get(i) for i in proposal.recurrence_evidence_ids]
        if not cited or None in cited or any(c['use'] not in KNOWLEDGE_USES for c in cited):
            issues.append('Historical recurrence must cite retrieved historical records.')
        else:
            recurrence['sources'] = [evidence_ref(c, packet) for c in cited]
    elif proposal.recurrence_evidence_ids:
        issues.append('Only FOUND recurrence cites historical records.')
    if issues:
        return unassessed_severity(inherited), issues
    structural = structural_occurrence(packet['threads'], computed_from='topic member threads (original Slack messages)')
    occurrence = {**structural.model_dump(mode='json'), 'semantic_identification': 'ASSESSED',
                  'historical_recurrence': recurrence,
                  'affected_reporters': {'status': 'LOWER_BOUND', 'count': len(reporters), 'ids': reporters,
                                         'basis': 'Distinct authors whose own cited message reports the problem; '
                                                  'other participants are not counted.',
                                         'evidence': [r.model_dump(mode='json') for r in reporter_refs]}
                      if reporters else CountEvidence().model_dump(mode='json')}
    try:
        assessment = SeverityAssessment(
            level=proposal.level, assessment_status='ASSESSED', rubric_version=rubric['version'],
            rubric_content_sha256=rubric['content_sha256'], rubric_project_id=rubric['rubric_project_id'],
            rubric_scope=rubric['rubric_scope'], rationale=proposal.rationale, matched_signals=signals,
            evidence=[r for s in signals for r in s.evidence], occurrence=OccurrenceEvidence.model_validate(occurrence),
            inherited_from=inherited)
    except ValidationError as error:
        return unassessed_severity(inherited), [f'Severity contract: {e["msg"]}' for e in error.errors()]
    problems = signal_reference_issues(assessment, rubric)
    return (unassessed_severity(inherited), problems) if problems else (assessment, [])


def agent1_resolution(members):
    """Agent 1's per-member resolution labels, attributed with their verification status (inputs, not evidence)."""
    return [{'member_id': m['member_id'], 'state': m['agent1_record']['interpretation'].get('resolution_state'),
             'agent1_verification_status': m['agent1_record'].get('verification_status'),
             'agent1_review_required': m['agent1_record'].get('review_required')} for m in members]


def topic_resolution(member_ids, states):
    """Topic state from per-member states: one resolved member never resolves the topic.
    Any member without a supported state makes the topic UNKNOWN unless known states already differ."""
    values = [states.get(m, 'UNKNOWN') for m in member_ids]
    known = {v for v in values if v != 'UNKNOWN'}
    if len(known) > 1:
        return 'MIXED'
    if not values or 'UNKNOWN' in values:
        return 'UNKNOWN'
    return values[0]


def _attributed_note(attributed):
    states = Counter(a['state'] for a in attributed)
    unverified = sum(1 for a in attributed if a['agent1_verification_status'] == 'NEEDS_REVIEW')
    return ('Agent 1 recorded (attributed input, not evidence): ' + ', '.join(f'{k} x{n}' for k, n in sorted(states.items(), key=str))
            + (f'; {unverified} of {len(attributed)} unverified (Agent 1 NEEDS_REVIEW).' if unverified else '.'))


def authorize(draft, grounding, ledger, packet, *, severity, severity_issues, rubric):
    """What the card may say: only statements whose final verdict is SUPPORTED. Removes, never adds."""
    verdict = {s['statement_id']: s['verdict'] for s in grounding['statements']}
    ok = lambda sid: verdict.get(sid) == 'SUPPORTED'  # noqa: E731
    claims = [c for c in draft.claims if ok(f'claim:{c.claim_id}')]
    handling = {e for e in established(draft, ledger) if ok(f'announcement:{e}')}
    action = draft.proposed_action if ok('action') else None
    notes, issues = [], list(severity_issues)
    if severity.assessment_status == 'ASSESSED':
        p = draft.severity
        failed = [sid for sid in ['severity:rationale', *(f'severity:signal:{s.level}[{s.signal_index}]' for s in p.signals)]
                  if not ok(sid)]
        if failed:
            severity, issues = unassessed_severity(packet.get('preliminary_severity')), issues + [
                f'Final grounding did not support {", ".join(failed)}; severity left UNASSESSED.']
        else:
            kept = [r for r in p.affected_reporters if ok(f'reporter:{r.author_id}')]
            if len(kept) != len(p.affected_reporters):
                dropped = sorted({r.author_id for r in p.affected_reporters} - {r.author_id for r in kept})
                notes.append(f'Affected reporters withheld (not supported): {", ".join(dropped)}.')
                severity, rebind = build_severity(p.model_copy(update={'affected_reporters': kept}), ledger, packet, rubric)
                issues += rebind
    states = {r.member_id: r.state for r in draft.resolution if ok(f'resolution:{r.member_id}')}
    resolution = topic_resolution(packet['member_ids'], states)
    withheld = [s for s in grounding['statements'] if s['verdict'] != 'SUPPORTED']
    return {'claims': claims, 'action': action, 'handling': handling, 'severity': severity, 'severity_issues': issues,
            'severity_notes': notes, 'summary': draft.summary if ok('summary') else None, 'resolution': resolution,
            'member_resolution': {m: states.get(m, 'UNKNOWN') for m in packet['member_ids']},
            'withheld': [{'statement_id': s['statement_id'], 'kind': s['kind'], 'text': s['text'], 'verdict': s['verdict'],
                          'rationale': s.get('rationale'), 'blocking': s['blocking']} for s in withheld]}


def unauthorized(packet, severity_issues=()):
    """Nothing authorized (no draft): the card carries members and obligations only."""
    return {'claims': [], 'action': None, 'handling': set(), 'severity': unassessed_severity(packet.get('preliminary_severity')),
            'severity_issues': list(severity_issues), 'severity_notes': [], 'summary': None, 'resolution': 'UNKNOWN',
            'member_resolution': {m: 'UNKNOWN' for m in packet['member_ids']}, 'withheld': []}


def inherited_flags(record, member_ids, *, projection_gap=None):
    """Every upstream obligation touching these members (and group-level ones) stays attached."""
    gid, members, flags = record['candidate_group_id'], set(member_ids), []
    for o in record.get('inherited_review_obligations', []):
        if o['member_id'] in members:
            flags.append(InheritedFlag(origin='agent1', kind='inherited_agent1_review', candidate_group_id=gid,
                                       member_ids=[o['member_id']], detail=(o['agent1_record'].get('review_reason') or '')[:600] or None))
    for o in record.get('agent2_review_obligations', []):
        ids = sorted(set(o.get('member_ids', [])) & members) or sorted(members)
        flags.append(InheritedFlag(origin='agent2', kind=o['kind'], candidate_group_id=gid, member_ids=ids))
    for o in record.get('content_review_obligations', []):
        finding = o.get('finding') or {}
        flags.append(InheritedFlag(origin='assisted_content_review', kind='assisted_content_review', candidate_group_id=gid,
                                   obligation_id=o['obligation_id'],
                                   detail=str(finding.get('summary') or finding.get('issue') or '')[:600] or None))
    if projection_gap:
        flags.append(InheritedFlag(origin='agent2', kind='projection_gap', candidate_group_id=gid,
                                   member_ids=sorted(members), detail=projection_gap[:600]))
    return flags


def _reason(code, detail, **extra):
    return ReviewReason(code=code, detail=detail, **extra)


def _reasoning(final, packet):
    lines = [f"{c.kind.replace('_', ' ').lower()}: {c.text}" for c in final['claims']]
    counts = Counter(final['member_resolution'].values())
    parts = ['Grounded findings: ' + ' | '.join(lines) if lines else 'No Advisor finding passed grounding.',
             f"Resolution ({final['resolution']}) from grounded per-member states: "
             + ', '.join(f'{k} x{n}' for k, n in sorted(counts.items())) + '.',
             _attributed_note(packet['agent1_resolution']), *final['severity_notes']]
    blocked = [w['statement_id'] for w in final['withheld'] if w['kind'] != 'ALTERNATIVE']
    if blocked:
        parts.append(f'Withheld as not established by cited evidence (see diagnostics): {", ".join(blocked)}.')
    return ' '.join(parts)


def assemble_card(outcome, packet, *, run_id):
    """Route to a card line from recorded checks; review reasons are never cleared by a choice."""
    draft, grounding, temporal, final = outcome.get('draft'), outcome['grounding'], outcome.get('temporal'), outcome['final']
    severity, flags = final['severity'], outcome['inherited_flags']
    confidence = draft.confidence if draft else 0.0
    reasons = []
    if confidence < 0.60:
        reasons.append(_reason('LOW_CONFIDENCE', f'Advisor confidence {confidence:.2f} is below 0.60.'
                               if draft else 'No valid Advisor draft; confidence recorded as 0.'))
    if severity.level == 'HIGH':
        reasons.append(_reason('HIGH_SEVERITY', 'Assessed HIGH under the shared default rubric.'))
    if flags:
        kinds = Counter(f.kind for f in flags)
        reasons.append(_reason('INHERITED_FLAG', 'Upstream obligations remain open: ' + ', '.join(f'{k} x{n}' for k, n in sorted(kinds.items())),
                               obligation_ids=sorted({f.obligation_id for f in flags if f.obligation_id})))
    if temporal and temporal['status'] == 'DETECTED':
        reasons.append(_reason('TEMPORAL_CONFLICT', '; '.join(f"{f['code']}: {f['detail']}"[:300] for f in temporal['findings']
                                                         if f['status'] == 'DETECTED')))
    if grounding['status'] == 'FAILED':
        detail = [f"{i['claim_id']}: {i['code']}" for i in grounding['structural_issues']] + grounding['action_issues'] + \
            [f"{s['statement_id']}: {s['verdict']}" for s in grounding['statements']
             if s['blocking'] and s['statement_id'] in grounding['unsupported'] + grounding['unjudged']]
        reasons.append(_reason('GROUNDING_FAILURE', 'Withheld from this card: ' + ('; '.join(detail) or 'grounding failed.')))
    elif grounding['status'] == 'NOT_RUN':
        reasons.append(_reason('GROUNDING_NOT_RUN', f"Grounding not run: {grounding['basis']}; no Advisor statement is shown as established."))
    if draft and draft.open_confirmation == 'OPEN':
        reasons.append(_reason('OPEN_CONFIRMATION', draft.open_confirmation_detail))
    sufficiency = outcome.get('evidence_sufficiency')
    if sufficiency in {'INSUFFICIENT', 'UNSUPPORTED'}:
        gaps = [g.description for g in draft.gaps] if draft else []
        reasons.append(_reason('OTHER', f'Evidence {sufficiency.lower()}: ' + ('; '.join(gaps) or 'no applicable source found.')))
    if final['severity_issues']:
        reasons.append(_reason('OTHER', 'Severity not established: ' + '; '.join(final['severity_issues'])[:900]))
    for failure in outcome['failures']:
        reasons.append(_reason('OTHER', f"{failure['stage']}: {failure['status']} ({failure.get('error', '')})"[:900]))
    action = final['action'] if sufficiency != 'UNSUPPORTED' else None
    operational = action is not None and action.action_type != 'NO_ACTION'
    line = 'NEEDS_REVIEW' if reasons else 'RECOMMENDED_ACTION' if operational else 'OBSERVATION'
    ledger = outcome['ledger']
    cited = [e for c in final['claims'] for e in c.evidence_ids] + sorted(final['handling'])
    if action:
        cited += [t.evidence_id for t in action.targets]
    cited = list(dict.fromkeys(e for e in cited if e in ledger))
    cited.sort(key=lambda e: ledger[e]['origin'] != 'retrieved_source')
    scope = ' '.join(x for x in ((action.scope_note if action else None),
                                 (f'Targets: {target_text(action, ledger)}.' if action and action.targets else None)) if x)
    data = {
        'card_id': stable_id('card', {'run': run_id, 'group': packet['candidate_group_id'], 'topic': packet['topic_id'],
                                      'members': sorted(packet['member_ids'])}),
        'project_id': packet['project_id'], 'topic_name': packet['topic_label'], 'card_line': line,
        'summary': final['summary'] or (f"Advisor summary withheld (grounding {grounding['status']}); see member threads."
                                        if draft else 'Advisor draft unavailable; members and obligations are carried for review.'),
        'severity': severity.model_dump(mode='json'), 'severity_is_provisional': severity.assessment_status == 'UNASSESSED',
        'resolution_status': final['resolution'],
        'recommended_action': {'action_type': action.action_type, 'draft_text': action.draft_text, 'scope_note': scope or None}
        if action else None,
        'reasoning': _reasoning(final, packet) if draft else 'No model reasoning available. ' + _attributed_note(packet['agent1_resolution']),
        'supporting_sources': [evidence_ref(ledger[e], packet, final['handling']).model_dump(mode='json') for e in cited],
        'related_threads': [ThreadRef(project_id=packet['project_id'], batch_id=packet['batch_id'], channel_id=m['channel_id'],
                                      thread_id=m['thread_id'], member_id=m['member_id']).model_dump(mode='json')
                            for m in packet['members']],
        'confidence': confidence, 'needs_review_reasons': [r.model_dump(mode='json') for r in reasons],
        'inherited_flags': [f.model_dump(mode='json') for f in flags],
        'checks': {'grounding': grounding['status'],
                   'temporal_conflict': temporal['status'] if temporal else 'NOT_CHECKED',
                   'open_confirmation': draft.open_confirmation if draft else 'NOT_CHECKED'},
        'lineage': {'agent3_run_id': run_id, 'handoff_contract': packet['handoff_contract'],
                    'agent2_export_sha256': packet['export_sha256'], 'agent2_schema_version': packet['schema_version'],
                    'candidate_group_id': packet['candidate_group_id'], 'topic_id': packet['topic_id'],
                    'member_ids': packet['member_ids'], 'project_id': packet['project_id'], 'batch_id': packet['batch_id']},
    }
    return AdviceCard.model_validate(data)
