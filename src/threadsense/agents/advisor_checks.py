"""Deterministic Advisor checks; no model calls.

- structural pre-checks, per statement: cited IDs exist, claim kinds use the right evidence
  (incident facts from member messages, verified causes from records or a team lead/engineer,
  current guidance from current sources or established announcements), quotes marked verbatim
  are verbatim, documentation targets are real and not already current, resolution rests on the
  member's own thread. A failure rejects only that statement and the statements that depend on it;
  the rest still go to the semantic judge;
- presentation and attribution: generated prose refers to people by role, never by name; role wording
  ("the team lead instructs") must match a cited author's role, plural wording ("three tutors report")
  needs that many distinct cited authors, and canonical-ID attributions must hold: AUTHOR wrote the cited
  message, THREAD_STARTER started its thread, PARTICIPANT posted in it (participation claims only). A
  name found in prose is checked the same way, then rejected as a name (cards use roles); quotations
  are source text, exempt from role rules and never changed;
- display text (summary, claims, action instruction/rationale/draft, review note, open question, severity
  rationale) carries no raw IDs, enum names or "Essential premises", and every double-quoted passage of
  five or more words must match a cited source exactly. Card v3 shows the team lead what happened, what to
  do, why, and what still needs review; enums, IDs, premises and processing errors stay structured;
- final statements: every statement that can reach a card (claims, summary, action,
  announcement handling, member resolution, severity rationale and signals, affected
  reporters) plus ToT alternatives, judged by ONE final semantic grounding call;
- normalization before checks: a GUIDANCE label on content that rests only on a team lead's thread
  messages is corrected to the scoped THREAD_INSTRUCTION role (recorded), and members' "happening
  again" messages cited as historical recurrence become reported recurrence;
- dependency order: announcement applicability -> final premise status -> action sufficiency. The judge
  sees each premise as pending its own verdict, with the announcement it depends on; essential premises
  are validated against the final supported set (a premise its dependency voids is not supported). The
  same sufficiency judgment covers reviewed ToT alternatives, so one may replace a withheld draft action;
- authorization: the card is assembled only from statements whose verdict (after
  dependencies) is SUPPORTED; everything else is withheld and kept in diagnostics. Severity is
  rebound to the unchanged rubric from the signals, reporters and recurrence that passed;
- temporal priority from recorded supersession: one current source explains a superseded section by record;
  several applicable current sources do so only if the final grounding judges that they agree; severity
  bound to the unchanged rubric;
  Agent 1 resolution states are attributed inputs, never evidence.
Nothing runs after the final grounding call except this authorization, which only removes.
"""
from collections import Counter
import re

from pydantic import ValidationError

from threadsense.agents.advice_contracts import (
    ACTION_LABELS, AdviceCardV3, CountEvidence, EvidenceRef, InheritedFlag, OccurrenceEvidence, RelatedThreadV2,
    ReviewReason, SeverityAssessment, SignalMatch, stable_id, unassessed_severity,
)
from threadsense.agents.advice_inputs import structural_occurrence
from threadsense.agents.advisor_evidence import user_directory
from threadsense.severity_rubric import signal_reference_issues

CURRENT_USES = {'CURRENT_GUIDANCE', 'CURRENT_HANDLING'}
STALE_USES = {'HISTORY_ONLY', 'UNRESOLVED_VERSION'}
KNOWLEDGE_USES = CURRENT_USES | STALE_USES | {'ANNOUNCEMENT', 'PRIOR_DECISION'}
BANNERED_USES = STALE_USES | {'ANNOUNCEMENT', 'PRIOR_DECISION'}
RESOLUTION_STATES = ('UNRESOLVED', 'PARTIALLY_RESOLVED', 'RESOLVED_IN_THREAD')
VERIFYING_ROLES = {'TEAM_LEAD', 'ENGINEER'}
COVERAGE_USES = {'CURRENT_GUIDANCE': CURRENT_USES, 'ANNOUNCEMENTS': {'ANNOUNCEMENT'},
                 'PRIOR_DECISIONS': {'PRIOR_DECISION', 'HISTORY_ONLY'}, 'MEMBER_QUESTIONS': {'MEMBER_REPORT'}}


def _norm(text):
    return ' '.join(text.split()).casefold()


def source_text(item):
    """Excerpt without the status banner the pilot added (quotes must come from the source)."""
    if item['use'] in BANNERED_USES and item['excerpt'].startswith('['):
        return item['excerpt'].split('\n', 1)[1] if '\n' in item['excerpt'] else ''
    return item['excerpt']


def _verbatim(quote, items):
    return any(_norm(quote) in _norm(source_text(item)) for item in items)


def _issue(claim_id, code, detail, statement_id=None):
    return {'claim_id': claim_id, 'statement_id': statement_id or claim_id, 'code': code, 'detail': detail}


SPEECH = (r'(?:reports?|reported|asks?|asked|says?|said|states?|stated|notes?|noted|confirms?|confirmed|instructs?|'
          r'instructed|requests?|requested|writes?|wrote|replies|replied|suggests?|suggested|explains?|explained|recalls?|'
          r'recalled|adds?|added|approves?|approved|describes?|described|mentions?|mentioned|clarifies|clarified|warns?|warned)')
PARTICIPATION = r'(?:participat\w*|joined|joins|took part|takes part|reacted|reacts)'
ROLE_WORDS = {'team lead': {'TEAM_LEAD'}, 'engineer': {'ENGINEER'}, 'qa tutor': {'QA_TUTOR'}, 'tutor': {'TUTOR', 'QA_TUTOR'}}
ROLE_ACTOR = re.compile(rf'\b(team lead|engineer|qa tutor|tutor)s?\s+(?:also\s+|then\s+|later\s+|again\s+)?{SPEECH}\b', re.I)
COUNTS = {'several': 2, 'multiple': 2, 'many': 2, 'both': 2, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
          'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
PEOPLE = r'(?:tutors|team\s+leads|engineers|members|annotators|reporters|people|users|raters|colleagues)'
PLURAL = re.compile(rf'\b(several|multiple|many|both|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+'
                    rf'(?:(?:different|distinct|separate|other)\s+)?(?:qa\s+)?{PEOPLE}\b'
                    rf'|\b{PEOPLE}\s+(?:all\s+|also\s+|each\s+)?{SPEECH}\b', re.I)


RAW_ID = re.compile(r'\b[mk]:[A-Za-z0-9_.:@-]+|\bclaim:\w+|\bmember_[0-9a-f]{8,}|\bcard_[0-9a-f]{8,}|\bU\d{3}\b'
                    r'|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b|\b[Ee]ssential premises?\b')
QUOTED = re.compile(r'"([^"]+)"|\u201c([^\u201d]+)\u201d')
QUOTE_MIN_WORDS = 5
# Words that present the next quotation as someone's or something's exact words ("the team lead wrote: ...").
ATTRIBUTION_CUE = re.compile(r'(?:\b(?:says?|said|writes?|wrote|states?|stated|asks?|asked|instructs?|instructed|replies|'
                             r'replied|reads?|notes?|noted|posts?|posted|announces?|announced|quotes?|quoted|calls? it|'
                             r'called it)\b[^"“.]{0,15}|:\s*)$', re.I)


def display_issues(text, items):
    """Team lead-facing text: no raw evidence/claim/user/member IDs, enum names or premise lists outside quotations.
    A quoted passage of five or more words, or any quotation explicitly attributed to a person or source ("the team lead
    wrote: ..."), is a source quotation and must match a cited item exactly."""
    issues, cited = [], [i for i in items if i]
    found = sorted(set(RAW_ID.findall(_unquoted(text))))
    if found:
        issues.append(('RAW_ID_IN_PROSE', f'Internal identifiers in display text: {found}.'))
    for match in QUOTED.finditer(text or ''):
        quote = match.group(1) or match.group(2)
        attributed = bool(ATTRIBUTION_CUE.search(text[:match.start()]))
        if (attributed or len(quote.split()) >= QUOTE_MIN_WORDS) and not _verbatim(quote.strip(' .,;:'), cited):
            issues.append(('QUOTE_NOT_IN_SOURCE', f'Quoted passage is not verbatim in a cited source: "{quote}".'))
            break
    return issues


def _unquoted(text):
    """Prose outside quotation marks: quoted source text is never checked or changed."""
    return re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d', ' ', text or '')


def _directory_names():
    out = {}
    for user_id, user in user_directory().items():
        out.setdefault(user['name'], set()).add(user_id)
    return out


def relation_holds(user_id, relation, item, ledger):
    """AUTHOR wrote the message; THREAD_STARTER started its thread; PARTICIPANT posted anywhere in that thread. For a
    retrieved record, AUTHOR holds only for a Slack message record, whose recorded actor is the message's author; a
    manual record's actor is its approving authority, and approving a record does not establish authorship."""
    if item and item.get('origin') == 'retrieved_source':
        return (relation == 'AUTHOR' and ((item.get('citation') or {}).get('source') or {}).get('system') == 'slack'
                and (item.get('authority') or {}).get('actor') == user_id)
    if not item or item.get('origin') != 'member_message':
        return False
    if relation == 'AUTHOR':
        return item['author_id'] == user_id
    if relation == 'THREAD_STARTER':
        return item.get('thread_starter_id') == user_id
    return any(i.get('origin') == 'member_message' and i['thread_id'] == item['thread_id'] and i['author_id'] == user_id
               for i in ledger.values())


def _required_relation(after):
    """The relation a mention asserts, from the words after the name."""
    if re.match(r"['\u2019]s\s+(?:own\s+)?(?:\w+\s+)?thread\b", after):
        return ('THREAD_STARTER',)
    if re.match(rf'\s+(?:also\s+|then\s+|later\s+|again\s+)?{SPEECH}\b', after, re.I):
        return ('AUTHOR',)
    if re.match(rf'\s+(?:also\s+)?{PARTICIPATION}', after, re.I):
        return ('PARTICIPANT',)  # Participation membership supports only a participation claim.
    return ('AUTHOR', 'THREAD_STARTER')


def prose_issues(text, items, ledger, attributions=()):
    """(code, detail) presentation and attribution failures of one piece of generated prose citing `items`."""
    issues, prose = [], _unquoted(text)
    for name, ids in _directory_names().items():
        for match in re.finditer(rf'\b{re.escape(name)}\b', prose):
            relations = _required_relation(prose[match.end():match.end() + 60])
            valid = any(relation_holds(u, r, i, ledger) for u in ids for r in relations for i in items)
            issues.append(('PERSONAL_NAME_IN_PROSE', f'Names {name} ({", ".join(sorted(ids))}); the relation '
                           f'{"/".join(relations)} holds, but card prose uses roles.') if valid else
                          ('NAME_RELATION_INVALID', f'Names {name} ({", ".join(sorted(ids))}) as '
                           f'{"/".join(relations)} of no cited message.'))
            break
    cited = [i for i in items if i]
    roles = {i.get('author_role') for i in cited if i.get('origin') == 'member_message'} | {
        (i.get('authority') or {}).get('role') for i in cited if i.get('origin') == 'retrieved_source'}
    for match in ROLE_ACTOR.finditer(prose):
        if not ROLE_WORDS[match.group(1).lower()] & roles:
            issues.append(('ROLE_NOT_IN_CITED_EVIDENCE', f'"{match.group(0)}" but no cited message or source is by a '
                           f'{match.group(1).lower()}.'))
            break
    # Counted against the cited authors; prose citing no member message (e.g. about an announcement) is counted
    # against the topic's distinct thread starters (its reporters).
    # A possessive plural ("two tutors' threads") is about the threads' starters; anything else about the authors.
    messages = [i for i in cited if i.get('origin') == 'member_message']
    topic = {i.get('thread_starter_id') for i in ledger.values() if i.get('origin') == 'member_message'} - {None}
    authors = {i['author_id'] for i in messages} or topic
    starters = {i.get('thread_starter_id') for i in messages} - {None} or topic
    for match in PLURAL.finditer(prose):
        word = (match.group(1) or '').lower()
        needed = int(word) if word.isdigit() else COUNTS.get(word, 2)
        people = starters if prose[match.end():match.end() + 1] in "'’" else authors
        if needed > len(people):
            issues.append(('PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS',
                           f'"{match.group(0)}" implies {needed} people; the evidence has {len(people)} distinct '
                           + ('thread starter(s).' if people is starters else 'author(s).')))
            break
    directory = user_directory()
    for a in attributions:
        item = ledger.get(a.evidence_id)
        if a.evidence_id not in {i.get('evidence_id') for i in cited}:
            issues.append(('ATTRIBUTION_NOT_CITED', f'{a.user_id} {a.relation} rests on uncited {a.evidence_id}.'))
        elif a.user_id not in directory:
            issues.append(('UNKNOWN_PERSON', f'{a.user_id} is not in the user directory.'))
        elif not relation_holds(a.user_id, a.relation, item, ledger):
            held = [r for r in ('AUTHOR', 'THREAD_STARTER', 'PARTICIPANT') if relation_holds(a.user_id, r, item, ledger)]
            approver = (item or {}).get('origin') == 'retrieved_source' and (item.get('authority') or {}).get('actor') == a.user_id
            issues.append(('ATTRIBUTION_INVALID', f'{a.user_id} is not {a.relation} of {a.evidence_id}'
                           + (f' (only {", ".join(held)})' if held else '')
                           + (' (the recorded approving authority, which does not establish authorship)' if approver else '')
                           + '.'))
    return issues


def established(draft, ledger):
    """Announcements the draft shows to be relevant directives (verbatim quote); grounding still verifies them."""
    return {a.evidence_id for a in draft.announcement_assessments
            if a.relevant and a.directive and ledger.get(a.evidence_id, {}).get('use') == 'ANNOUNCEMENT'
            and _verbatim(a.directive_quote, [ledger[a.evidence_id]])}


def normalize(draft, ledger):
    """Deterministic corrections before checking, each recorded: (1) a GUIDANCE claim with no current source or
    established announcement whose cited evidence is all member messages including a team lead's is relabelled
    THREAD_INSTRUCTION (scoped to its thread; still judged); tutor-only "guidance" is left to fail. (2) member
    messages cited as historical recurrence move to reported recurrence; records stay historical."""
    notes, claims, handling = [], [], established(draft, ledger)
    for c in draft.claims:
        items = [ledger.get(e) for e in c.evidence_ids]
        if (c.kind == 'GUIDANCE' and items and None not in items and all(i['origin'] == 'member_message' for i in items)
                and not handling & set(c.evidence_ids) and any(i.get('author_role') == 'TEAM_LEAD' for i in items)):
            notes.append({'code': 'ROLE_LABEL_CORRECTED', 'statement_id': f'claim:{c.claim_id}', 'from': 'GUIDANCE',
                          'to': 'THREAD_INSTRUCTION', 'detail': 'Cites only thread messages, including a team lead\'s.'})
            c = c.model_copy(update={'kind': 'THREAD_INSTRUCTION'})
        claims.append(c)
    s = draft.severity
    members = [e for e in s.recurrence_evidence_ids if ledger.get(e, {}).get('origin') == 'member_message']
    records = [e for e in s.recurrence_evidence_ids if e not in members]
    reported = [e for e in s.reported_recurrence_evidence_ids if ledger.get(e, {}).get('origin') == 'member_message']
    if members or len(reported) != len(s.reported_recurrence_evidence_ids):
        notes.append({'code': 'RECURRENCE_RECLASSIFIED', 'statement_id': 'severity:recurrence', 'detail':
                      f'Member messages {members} are reported recurrence, not historical records'
                      + (f'; dropped non-member reported evidence {sorted(set(s.reported_recurrence_evidence_ids) - set(reported))}'
                         if len(reported) != len(s.reported_recurrence_evidence_ids) else '') + '.'})
        s = s.model_copy(update={'reported_recurrence_evidence_ids': list(dict.fromkeys(reported + members)),
                                 'recurrence_evidence_ids': records,
                                 'recurrence': s.recurrence if records or s.recurrence != 'FOUND' else 'NOT_CHECKED'})
    return draft.model_copy(update={'claims': claims, 'severity': s}), notes


def claim_issues(draft, ledger):
    """Structural failures per claim; each rejects that claim (and what depends on it), never the whole draft."""
    issues, handling = [], established(draft, ledger)

    def issue(claim, code, detail):
        issues.append(_issue(claim.claim_id, code, detail, f'claim:{claim.claim_id}'))
    for claim in draft.claims:
        unknown = [i for i in claim.evidence_ids if i not in ledger]
        if unknown:
            issue(claim, 'UNKNOWN_EVIDENCE', f'Cites evidence not in the ledger: {unknown}.')
            continue
        items = [ledger[i] for i in claim.evidence_ids]
        uses = {item['use'] for item in items}
        if claim.material and not items:
            issue(claim, 'NO_CITATION', 'Material claim cites no evidence.')
        if claim.kind == 'INCIDENT_FACT' and uses - {'MEMBER_REPORT'}:
            issue(claim, 'INCIDENT_FACT_NEEDS_MEMBER_EVIDENCE', 'Incident facts must come from member messages, not retrieved sources.')
        if claim.kind == 'CAUSE' and not (uses & (CURRENT_USES | {'PRIOR_DECISION'}) or any(
                i['use'] == 'MEMBER_REPORT' and i.get('author_role') in VERIFYING_ROLES for i in items)):
            issue(claim, 'CAUSE_WITHOUT_VERIFICATION', 'A cause needs a retrieved record or a team lead/engineer message; '
                                                       'member reports are symptoms.')
        for code, detail in prose_issues(claim.text, items, ledger, claim.attributions) + display_issues(claim.text, items):
            issue(claim, code, detail)
        if claim.kind == 'GUIDANCE':
            if not (uses & CURRENT_USES or handling & set(claim.evidence_ids)):
                announced = [i for i in claim.evidence_ids if ledger[i]['use'] == 'ANNOUNCEMENT']
                if announced:
                    issue(claim, 'ANNOUNCEMENT_NOT_ESTABLISHED_AS_HANDLING',
                          f'Cited announcements {announced} are not assessed as relevant directives for this topic.')
                else:
                    issue(claim, 'GUIDANCE_WITHOUT_CURRENT_SOURCE',
                          'Guidance must cite a current guideline or FAQ, or an established announcement.')
            stale = [item['evidence_id'] for item in items if item['use'] in STALE_USES]
            if stale:
                issue(claim, 'HISTORICAL_SOURCE_AS_CURRENT_GUIDANCE',
                      f'Historical or unresolved sources cannot support current guidance: {stale}.')
        if claim.kind == 'THREAD_INSTRUCTION' and not any(
                i['origin'] == 'member_message' and i.get('author_role') == 'TEAM_LEAD' for i in items):
            issue(claim, 'THREAD_INSTRUCTION_WITHOUT_TEAM_LEAD', "A thread instruction cites the team lead's own message.")
        if claim.kind == 'HISTORY' and not uses & KNOWLEDGE_USES:
            issue(claim, 'HISTORY_WITHOUT_RECORD', 'History claims cite retrieved records.')
        # A paraphrase is judged semantically; only a quote presented as verbatim must match exactly.
        if claim.quote and claim.quote_kind == 'VERBATIM' and not _verbatim(claim.quote, items):
            issue(claim, 'QUOTE_NOT_VERBATIM', 'Quote presented as verbatim is not in any cited excerpt.')
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
    if draft.open_confirmation == 'OPEN':
        unknown = [e for e in draft.open_question_evidence_ids if e not in ledger]
        if unknown:
            issues.append(_issue('open_question', 'UNKNOWN_EVIDENCE', f'Open question cites evidence not in the ledger: {unknown}.'))
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
    # Whether the premises make the action applicable is judged semantically; no source must prescribe it.
    issues = []
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


def presentation_issues(draft, ledger):
    """Prose checks for every non-claim statement that can reach the card (claims are checked in claim_issues)."""
    claims = {c.claim_id: c for c in draft.claims}

    def cited(ids):
        return [ledger.get(e) for e in ids if e in ledger]
    material = [e for c in draft.claims if c.material for e in c.evidence_ids]
    # (statement, text, cited evidence, shown to the team lead as written)
    texts = [('summary', draft.summary, material, True)]
    action = draft.proposed_action
    if action is not None:
        support = [e for i in action.support_claim_ids if i in claims for e in claims[i].evidence_ids] + [
            t.evidence_id for t in action.targets]
        texts.append(('action', ' '.join(x for x in (action.instruction, action.draft_text, action.scope_note) if x),
                      support, True))
        if action.rationale:
            texts.append(('action:rationale', action.rationale, support, True))
    if draft.review_note:
        texts.append(('review_note', draft.review_note, _review_note_evidence(draft), True))
    texts += [(f'announcement:{a.evidence_id}', a.rationale, [a.evidence_id], False) for a in draft.announcement_assessments]
    texts += [(f'resolution:{r.member_id}', r.basis, r.evidence_ids, False) for r in draft.resolution]
    if draft.open_confirmation == 'OPEN':
        texts.append(('open_question', draft.open_question, draft.open_question_evidence_ids, True))
    p = draft.severity
    texts.append(('severity:rationale', p.rationale, [e for s in p.signals for e in s.evidence_ids]
                  + [r.evidence_id for r in p.affected_reporters] + material, True))
    texts += [(f'severity:signal:{s.level}[{s.signal_index}]', s.support, s.evidence_ids, False) for s in p.signals]
    return [_issue(sid, code, detail) for sid, text, ids, shown in texts for code, detail in
            prose_issues(text, cited(ids), ledger) + (display_issues(text, cited(ids)) if shown else [])]


def _review_note_evidence(draft):
    return [e for c in draft.claims if c.material for e in c.evidence_ids] + list(draft.open_question_evidence_ids)


def structural_issues(draft, ledger, member_ids):
    return (claim_issues(draft, ledger) + announcement_issues(draft, ledger) + resolution_issues(draft, ledger, member_ids)
            + presentation_issues(draft, ledger))


def dependencies(draft, ledger):
    """Claim statement -> the announcement-handling statements it depends on: GUIDANCE with no current source rests on
    the announcements it cites, and stands only if those are verified for this topic."""
    handling, out = established(draft, ledger), {}
    for c in draft.claims:
        if c.kind == 'GUIDANCE' and all(e in ledger for e in c.evidence_ids) and not (
                {ledger[e]['use'] for e in c.evidence_ids} & CURRENT_USES):
            depends = [f'announcement:{e}' for e in c.evidence_ids if e in handling]
            if depends:
                out[f'claim:{c.claim_id}'] = depends
    return out


def coverage_issues(draft, ledger, follow_ups=None, revision=None):
    """The draft's evidence-coverage assessment: every need assessed, COVERED by evidence of the right use,
    MISSING tied to a follow-up request. A MISSING need distinguishes evidence not found from evidence retrieved but
    not incorporated because the revision did not run (`follow_ups`: the executed searches; `revision`: the revision
    stage's log entry, None if none was attempted). Reported on the card, never repaired."""
    issues, assessed = [], {c.need: c for c in draft.coverage}
    gaps = {g.gap_id: g for g in draft.gaps}
    searched = {f['gap_id']: f for f in follow_ups or []}
    revised = revision is not None and revision.get('status') == 'OK'
    for need, uses in COVERAGE_USES.items():
        item = assessed.get(need)
        if item is None:
            issues.append(f'{need}: not assessed')
        elif item.status == 'COVERED' and not any(ledger.get(e, {}).get('use') in uses for e in item.evidence_ids):
            issues.append(f'{need}: marked COVERED without evidence of that kind')
        elif item.status == 'MISSING':
            gap, search = gaps.get(item.gap_id or ''), searched.get(item.gap_id or '')
            if search is None:
                issues.append(f'{need}: missing' + (' (follow-up requested, not run)' if gap and gap.follow_up else
                                                    ' and not researched'))
            elif search['status'] != 'DONE':
                issues.append(f"{need}: missing; follow-up not run ({search['status']})")
            elif not search.get('new_evidence_ids'):
                issues.append(f'{need}: missing; follow-up search found no new evidence')
            elif revised:
                issues.append(f'{need}: missing; still missing after the revision used the follow-up evidence')
            else:
                why = (f"revision {revision['status']}" + (f" ({revision.get('failure_class')})" if revision.get('failure_class')
                                                            else '')) if revision else 'no revision ran'
                issues.append(f"{need}: missing; follow-up retrieved {len(search['new_evidence_ids'])} item(s) but they were "
                              f'not incorporated ({why})')
    return issues


def display_targets(action, ledger):
    """Documentation targets as the team lead sees them: document title and section (evidence ID kept structured)."""
    out = []
    for t in action.targets:
        citation = (ledger.get(t.evidence_id) or {}).get('citation') or {}
        out.append({'evidence_id': t.evidence_id, 'title': citation.get('title') or citation.get('authoring') or t.evidence_id,
                    'section': t.section, 'change': t.change})
    return out


def _target_phrase(target):
    return f"{target['change'].lower()} {target['title']}" + (f", section '{target['section']}'" if target['section'] else '')


def _action_text(action, ledger):
    """Exactly what the card shows for the action (the judged text), in display order."""
    parts = [f'{ACTION_LABELS[action.action_type]}.']
    if action.instruction:
        parts.append(f'Instruction: {action.instruction}')
    if action.draft_text:
        parts.append(f'Draft to copy: {action.draft_text}')
    if action.scope_note:
        parts.append(f'Scope: {action.scope_note}')
    if action.targets:
        parts.append('Changes (only these): ' + '; '.join(_target_phrase(t) for t in display_targets(action, ledger)) + '.')
    return ' '.join(parts)


def statements(draft, ledger, *, severity=None, alternatives=(), handling=None):
    """Every statement that can reach the card or a reviewer, with the evidence it cites (ledger IDs only)."""
    out, seen = [], Counter()

    def add(sid, kind, text, ids, blocking=True):
        seen[sid] += 1
        sid = sid if seen[sid] == 1 else f'{sid}#{seen[sid]}'
        out.append({'statement_id': sid, 'kind': kind, 'text': text, 'blocking': blocking,
                    'evidence_ids': list(dict.fromkeys(i for i in ids if i in ledger))})
    for c in draft.claims:
        quote = (f' Verbatim quote: "{c.quote}"' if c.quote_kind == 'VERBATIM' else f' Paraphrase: "{c.quote}"') if c.quote else ''
        add(f'claim:{c.claim_id}', f'CLAIM_{c.kind}', c.text + quote, c.evidence_ids, c.material)
        if c.attributions:
            directory = user_directory()
            out[-1]['attributions'] = [{**a.model_dump(), 'role': (directory.get(a.user_id) or {}).get('role')}
                                       for a in c.attributions]
    add('summary', 'SUMMARY', draft.summary, [e for c in draft.claims if c.material for e in c.evidence_ids])
    action = draft.proposed_action
    # A bare NO_ACTION (no text) states nothing to judge; anything with text or an operation is judged.
    if action is not None and draft.evidence_sufficiency != 'UNSUPPORTED' and (action.action_type != 'NO_ACTION' or action.draft_text):
        support = [e for c in draft.claims if c.claim_id in action.support_claim_ids for e in c.evidence_ids]
        add('action', 'ACTION', _action_text(action, ledger), support + [t.evidence_id for t in action.targets])
        out[-1]['premises'] = [f'claim:{i}' for i in action.support_claim_ids]
        if action.rationale:
            add('action:rationale', 'ACTION_RATIONALE', f'Why this helps: {action.rationale}',
                support + [t.evidence_id for t in action.targets], blocking=False)
    if draft.review_note:
        add('review_note', 'REVIEW_NOTE', f'Still needs review: {draft.review_note}', _review_note_evidence(draft),
            blocking=False)
    for a in draft.announcement_assessments:
        if a.relevant and a.directive:
            add(f'announcement:{a.evidence_id}', 'ANNOUNCEMENT_HANDLING', 'This announcement applies to this topic and '
                f'directs current handling: "{a.directive_quote}". {a.rationale}', [a.evidence_id])
    for r in draft.resolution:
        if r.state != 'UNKNOWN':
            add(f'resolution:{r.member_id}', 'RESOLUTION', f'Member thread {r.member_id} is {r.state}: {r.basis}', r.evidence_ids)
    if draft.open_confirmation == 'OPEN':
        add('open_question', 'OPEN_QUESTION', f'The cited evidence leaves this specific question unsettled: {draft.open_question}',
            draft.open_question_evidence_ids)
    if severity is not None and severity.assessment_status == 'ASSESSED':
        p = draft.severity
        incident = [e for c in draft.claims if c.kind == 'INCIDENT_FACT' for e in c.evidence_ids]
        add('severity:rationale', 'SEVERITY_RATIONALE', f'Severity {p.level}: {p.rationale}',
            [e for s in p.signals for e in s.evidence_ids] + [r.evidence_id for r in p.affected_reporters] + incident)
        for s in p.signals:
            add(f'severity:signal:{s.level}[{s.signal_index}]', 'SEVERITY_SIGNAL',
                f'Rubric signal met - "{s.signal_text}": {s.support}', s.evidence_ids)
        if p.recurrence == 'FOUND':
            add('severity:recurrence', 'HISTORICAL_RECURRENCE', 'Retrieved records show this problem occurred before.',
                p.recurrence_evidence_ids)
        if p.reported_recurrence_evidence_ids:
            add('severity:reported_recurrence', 'REPORTED_RECURRENCE', 'Members report that this is happening again '
                '(their report; not corroborated history).', p.reported_recurrence_evidence_ids, blocking=False)
        for author in dict.fromkeys(r.author_id for r in p.affected_reporters):
            ids = [r.evidence_id for r in p.affected_reporters if r.author_id == author]
            add(f'reporter:{author}', 'AFFECTED_REPORTER',
                f'{author} reports, in their own cited message, being affected by this problem.', ids)
    for c in alternatives:
        add(f"alternative:{c['candidate_id']}", 'ALTERNATIVE', f"{ACTION_LABELS[c['action_type']]}."
            + (f" Instruction: {c['instruction']}" if c.get('instruction') else '')
            + f" Draft to copy: {c['draft_text']} Why this helps: {c['rationale']}", c['evidence_ids'], blocking=False)
        if c['action_type'] != 'NO_ACTION':
            out[-1]['premises'] = [f'claim:{i}' for i in c.get('premise_ids', [])]
    for i, current, older, conflict in agreement_candidates(draft, ledger, handling):
        add(f'temporal:conflict[{i}]', 'SOURCE_AGREEMENT',
            f"The current sources {', '.join(current)} agree with each other on the point in conflict; the conflict is only "
            f"with superseded material ({', '.join(older)}) that recorded supersession replaced. Reported conflict: "
            f'{conflict.description}', conflict.evidence_ids, blocking=False)
    return out


def sufficiency_verdict(premises, sufficiency, raw, final, pending=False):
    """A recommendation the judge supported stands only with a SUFFICIENT judgment whose essential premises are
    premises of it and are in the FINAL supported set (after announcement dependencies); a rejected optional premise
    does not block it. An essential premise the judge supported but its dependency voided is reported as such."""
    if sufficiency is None:
        return 'PENDING' if pending else 'SUFFICIENCY_NOT_JUDGED'
    essential = set(sufficiency.essential_statement_ids)
    if sufficiency.verdict != 'SUFFICIENT':
        return 'INSUFFICIENT_PREMISES'
    if not essential:
        return 'NO_ESSENTIAL_PREMISE_NAMED'
    if essential - set(premises):
        return 'ESSENTIAL_ID_NOT_A_PREMISE'
    if any(final.get(e) != 'SUPPORTED' and raw.get(e) == 'SUPPORTED' for e in essential):
        return 'ESSENTIAL_PREMISE_VOIDED_BY_DEPENDENCY'
    if any(final.get(e) != 'SUPPORTED' for e in essential):
        return 'ESSENTIAL_PREMISE_NOT_PASSED'
    return 'SUPPORTED'


def _effective(draft, ledger, verdicts, sufficiency=None, pending=False):
    """Verdicts after dependencies, in order: (1) announcement applicability; (2) final premise status - guidance
    resting only on announcements needs a verified announcement; (3) action sufficiency over the final statuses.
    Nothing borrows another statement's SUPPORTED verdict."""
    out = dict(verdicts)
    verified = {e for e in established(draft, ledger) if verdicts.get(f'announcement:{e}') == 'SUPPORTED'}
    for c in draft.claims:
        sid = f'claim:{c.claim_id}'
        if c.kind == 'GUIDANCE' and out.get(sid) == 'SUPPORTED' and not (
                {ledger[e]['use'] for e in c.evidence_ids} & CURRENT_USES or verified & set(c.evidence_ids)):
            out[sid] = 'ANNOUNCEMENT_NOT_VERIFIED'
    if 'action' in out and draft.proposed_action and out['action'] == 'SUPPORTED':
        premises = [f'claim:{i}' for i in draft.proposed_action.support_claim_ids]
        out['action'] = sufficiency_verdict(premises, sufficiency, verdicts, out, pending)
    return out


def rejected_statements(draft, stmts, structural=(), actions=()):
    """Statement ID -> structural rejection, including dependents: an action resting on a rejected claim."""
    out = {}
    for i in structural:
        out.setdefault(i['statement_id'], f"REJECTED_{i['code']}")
    if actions:
        out.setdefault('action', 'REJECTED_' + actions[0].split(':')[0])
    ids = {s['statement_id'] for s in stmts}
    return {k: v for k, v in out.items() if k in ids}


def sendable(stmts, rejected):
    """Statements the semantic judge sees: cited and not structurally rejected."""
    return [s for s in stmts if s['evidence_ids'] and s['statement_id'] not in rejected]


def grounding_result(draft, ledger, stmts, *, structural=(), actions=(), judgment=None, ran=False, reason=None,
                     pending=False):
    """PASSED only when every blocking statement is SUPPORTED after structural rejection and dependencies.
    Structurally rejected statements and statements citing nothing (NO_EVIDENCE) are never sent. `pending` (offline
    replay): a judgment not available for unchanged content is PENDING, never assumed."""
    rejected = rejected_statements(draft, stmts, structural, actions)
    unjudged_label = 'PENDING' if pending else 'NOT_JUDGED'
    result = {'structural_issues': list(structural), 'action_issues': list(actions), 'unsupported': [], 'unjudged': [],
              'extraneous_verdicts': [], 'rejected': rejected, 'pending': [],
              'action_sufficiency': judgment.action_sufficiency.model_dump() if ran and judgment.action_sufficiency else None}
    given = {v.statement_id: v for v in judgment.verdicts} if ran else {}
    raw = {s['statement_id']: rejected.get(s['statement_id']) or ('NO_EVIDENCE' if not s['evidence_ids'] else
           given[s['statement_id']].verdict if s['statement_id'] in given else unjudged_label) for s in stmts}
    effective = _effective(draft, ledger, raw, judgment.action_sufficiency if ran else None, pending)
    given_alt = {a.statement_id: a for a in judgment.alternative_sufficiency} if ran else {}
    result['alternative_sufficiency'] = {
        s['statement_id']: {**(given_alt[s['statement_id']].model_dump() if s['statement_id'] in given_alt else {}),
                            'check': sufficiency_verdict(s['premises'], given_alt.get(s['statement_id']), raw, effective, pending)
                            if raw[s['statement_id']] == 'SUPPORTED' else raw[s['statement_id']]}
        for s in stmts if s['kind'] == 'ALTERNATIVE' and 'premises' in s}
    judged = [{**s, 'verdict': effective[s['statement_id']], 'model_verdict': raw[s['statement_id']],
               'rationale': given[s['statement_id']].rationale if s['statement_id'] in given else None} for s in stmts]
    blocking = [s for s in judged if s['blocking']]
    waiting = [s['statement_id'] for s in blocking if s['verdict'] == 'PENDING']
    unjudged = [s['statement_id'] for s in blocking if s['verdict'] == 'NOT_JUDGED']
    unsupported = [s['statement_id'] for s in blocking if s['verdict'] not in ('SUPPORTED', 'NOT_JUDGED', 'PENDING')]
    result['pending'] = [s['statement_id'] for s in judged if s['verdict'] == 'PENDING']
    if not ran:
        failed = [s for s in unsupported if s in rejected]
        return {**result, 'statements': judged, 'unsupported': failed, 'unjudged': unjudged,
                'status': 'FAILED' if failed else 'NOT_RUN',
                'basis': 'STRUCTURAL' if failed else reason or 'SEMANTIC_JUDGMENT_UNAVAILABLE'}
    if waiting and not (unjudged or unsupported):
        return {**result, 'status': 'NOT_RUN', 'basis': 'PENDING_SEMANTIC_JUDGMENTS', 'statements': judged,
                'unsupported': unsupported, 'unjudged': unjudged, 'extraneous_verdicts': sorted(set(given) - set(raw))}
    return {**result, 'status': 'FAILED' if unjudged or unsupported else 'PASSED',
            'basis': 'STRUCTURAL+SEMANTIC' if rejected else 'SEMANTIC',
            'statements': judged, 'unsupported': unsupported, 'unjudged': unjudged,
            'extraneous_verdicts': sorted(set(given) - set(raw))}


def _explained(old, new):
    """True when recorded supersession says `new` replaced (part of) `old`."""
    new_authoring = new['citation']['authoring']
    if new_authoring and any(r['replaced_by'] == new_authoring for r in old['applicability']['replaced_by']):
        return True
    old_authoring = (old['citation']['authoring'] or '@').split('@')
    return any([s['document_id'], s['version']] == old_authoring for s in new['applicability']['supersedes'])


def _uncertain(item):
    """Applicability that recorded metadata cannot settle: unresolved or unverified revisions, upstream review."""
    return (item['use'] == 'UNRESOLVED_VERSION' or bool((item.get('applicability') or {}).get('unverified_supersession'))
            or bool(item.get('upstream_review')))


def _superseded_conflict(conflict, ledger, handling):
    """(current, older) when every older item in the conflict is HISTORY_ONLY material that a current, applicable item
    replaced by record and no item's applicability is uncertain; otherwise None."""
    items = [ledger.get(i) for i in conflict.evidence_ids]
    if any(item is None for item in items):
        return None
    current = [i for i in items if i['use'] in CURRENT_USES or i['evidence_id'] in handling]
    older = [i for i in items if i['use'] == 'HISTORY_ONLY']
    rest = [i for i in items if i not in current and i not in older]
    if not (current and older) or rest or any(_uncertain(i) for i in items):
        return None
    if not all(any(_explained(o, c) for c in current) for o in older):
        return None
    return current, older


def agreement_candidates(draft, ledger, handling=None):
    """Conflicts that recorded supersession would explain if their several current sources agree: (index, current IDs,
    older IDs, conflict). With one current source the record settles it; with several, the final grounding judges
    agreement (a SOURCE_AGREEMENT statement)."""
    handling = established(draft, ledger) if handling is None else handling
    out = []
    for i, conflict in enumerate(draft.source_conflicts):
        found = _superseded_conflict(conflict, ledger, handling)
        if found and len(found[0]) > 1:
            out.append((i, [c['evidence_id'] for c in found[0]], [o['evidence_id'] for o in found[1]], conflict))
    return out


def temporal_check(draft, ledger, handling=None, verdicts=None):
    """Temporal priority from recorded dates/supersession only; never resolves by itself. `handling`: the
    announcements accepted as current (defaults to those the draft establishes, before grounding). `verdicts`: final
    statement verdicts; several agreeing current sources explain a superseded section only if their SOURCE_AGREEMENT
    statement is SUPPORTED. Real disagreement or uncertain applicability stays DETECTED (reviewable)."""
    handling = established(draft, ledger) if handling is None else handling
    findings = []
    for index, conflict in enumerate(draft.source_conflicts):
        items = [ledger.get(i) for i in conflict.evidence_ids]
        if any(item is None for item in items):
            findings.append({'status': 'DETECTED', 'code': 'CONFLICT_CITES_UNKNOWN_EVIDENCE',
                             'evidence_ids': conflict.evidence_ids, 'detail': conflict.description})
            continue
        found = _superseded_conflict(conflict, ledger, handling)
        base = {'evidence_ids': conflict.evidence_ids, 'detail': conflict.description}
        if found is None:
            findings.append({'status': 'DETECTED', 'code': 'UNEXPLAINED_SOURCE_CONFLICT', **base})
            continue
        current = [c['evidence_id'] for c in found[0]]
        agreement = None if len(current) == 1 else (verdicts or {}).get(f'temporal:conflict[{index}]', 'NOT_YET_JUDGED')
        if agreement in (None, 'SUPPORTED'):
            findings.append({'status': 'RESOLVED_BY_RECORDED_SUPERSESSION', 'code': 'SUPERSEDED_SOURCE_EXPLAINS_CONFLICT',
                             **base, 'current': current if len(current) > 1 else current[0],
                             **({'agreement': 'SUPPORTED'} if agreement else {})})
        else:
            findings.append({'status': 'DETECTED', 'code': 'CURRENT_SOURCE_AGREEMENT_' + (
                agreement if agreement in ('PENDING', 'NOT_YET_JUDGED') else 'NOT_ESTABLISHED'), **base,
                'current': current, 'agreement': agreement})
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


def build_severity(proposal, ledger, packet, rubric, notes=None):
    """Bind a proposed severity to the rubric; an unsupported signal or recurrence leaves it UNASSESSED. A reporter
    not backed by their own message is dropped from the lower-bound count and recorded in `notes`."""
    issues, signals, notes = [], [], [] if notes is None else notes
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
            notes.append(f'Affected reporter {r.author_id} dropped: the cited message is '
                         + (f"by {item['author_id']}." if item and item.get('author_id') else 'not a member message.'))
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


def _plain(value):
    return str(value).replace('_', ' ').lower()


def _attributed_note(attributed):
    states = Counter(a['state'] for a in attributed)
    unverified = sum(1 for a in attributed if a['agent1_verification_status'] == 'NEEDS_REVIEW')
    return ("Agent 1's earlier labels (an input, not evidence): " + ', '.join(f'{_plain(k)} \u00d7{n}' for k, n in
                                                                          sorted(states.items(), key=str))
            + (f'; {unverified} of {len(attributed)} were not verified by Agent 1.' if unverified else '.'))


def authorize(draft, grounding, ledger, packet, *, severity, severity_issues, rubric, severity_notes=()):
    """What the card may say: only statements whose final verdict is SUPPORTED. Removes, never adds."""
    verdict = {s['statement_id']: s['verdict'] for s in grounding['statements']}
    ok = lambda sid: verdict.get(sid) == 'SUPPORTED'  # noqa: E731
    claims = [c for c in draft.claims if ok(f'claim:{c.claim_id}')]
    handling = {e for e in established(draft, ledger) if ok(f'announcement:{e}')}
    action = draft.proposed_action if ok('action') else None
    notes, issues = list(severity_notes), list(severity_issues)
    waiting = [sid for sid, v in verdict.items() if v == 'PENDING' and sid.startswith(('severity:', 'reporter:'))]
    if severity.assessment_status == 'ASSESSED' and waiting:  # Replay: unjudged is not unsupported.
        severity, issues = unassessed_severity(packet.get('preliminary_severity')), issues + [
            f'Severity pending semantic judgment of {", ".join(waiting)}; left UNASSESSED until judged.']
    elif severity.assessment_status == 'ASSESSED':
        severity, issues, notes = _reassess(draft.severity, ok, ledger, packet, rubric, severity, issues, notes)
    states = {r.member_id: r.state for r in draft.resolution if ok(f'resolution:{r.member_id}')}
    resolution = topic_resolution(packet['member_ids'], states)
    withheld = [s for s in grounding['statements'] if s['verdict'] != 'SUPPORTED']
    return {'claims': claims, 'action': action, 'handling': handling, 'severity': severity, 'severity_issues': issues,
            'severity_notes': notes, 'summary': draft.summary if ok('summary') else None, 'resolution': resolution,
            'action_rationale': action.rationale if action and ok('action:rationale') else None,
            'review_note': draft.review_note if ok('review_note') else None,
            'open_question_supported': ok('open_question') if draft.open_confirmation == 'OPEN' else None,
            'open_question_verdict': verdict.get('open_question'),
            'member_resolution': {m: states.get(m, 'UNKNOWN') for m in packet['member_ids']},
            'withheld': [{'statement_id': s['statement_id'], 'kind': s['kind'], 'text': s['text'], 'verdict': s['verdict'],
                          'rationale': s.get('rationale'), 'blocking': s['blocking']} for s in withheld]}


def _signal_id(s):
    return f'severity:signal:{s.level}[{s.signal_index}]'


def _reassess(p, ok, ledger, packet, rubric, severity, issues, notes):
    """Rebind the proposed level to the unchanged rubric using only what passed: unsupported historical recurrence,
    signals and reporters are removed; independent supported signals and reporters stay. An unsupported rationale is
    replaced by the supported signals' own wording. The level is never lowered or defaulted: if it no longer has
    support, severity is UNASSESSED and the supported lower-level signals are named."""
    update, changed = {}, []
    kept = [s for s in p.signals if ok(_signal_id(s))]
    if len(kept) != len(p.signals):
        update['signals'] = kept
        changed.append('signals ' + ', '.join(_signal_id(s) for s in p.signals if s not in kept))
    reporters = [r for r in p.affected_reporters if ok(f'reporter:{r.author_id}')]
    if len(reporters) != len(p.affected_reporters):
        update['affected_reporters'] = reporters
        changed.append('reporters ' + ', '.join(sorted({r.author_id for r in p.affected_reporters} - {r.author_id for r in reporters})))
    if p.recurrence == 'FOUND' and not ok('severity:recurrence'):
        update.update(recurrence='NOT_CHECKED', recurrence_evidence_ids=[])
        changed.append('historical recurrence (not corroborated)')
    if not ok('severity:rationale'):
        if not kept:
            return unassessed_severity(packet.get('preliminary_severity')), issues + [
                'Severity rationale not supported and no rubric signal passed; severity left UNASSESSED.'], notes
        update['rationale'] = 'Supported rubric signals: ' + '; '.join(f'{_signal_id(s)[9:]} {s.support}' for s in kept)
        changed.append('rationale (replaced by the supported signals)')
    if not changed:
        return severity, issues, notes
    notes = notes + ['Removed from severity after final grounding: ' + '; '.join(changed) + '.']
    rebound, problems = build_severity(p.model_copy(update=update), ledger, packet, rubric)
    if problems:
        lower = [_signal_id(s)[9:] for s in kept if s.level != p.level]
        return rebound, issues + problems + [f'{p.level} is no longer supported' + (
            f'; supported lower-level signals: {", ".join(lower)} (level not lowered automatically)' if lower else '')], notes
    return rebound, issues, notes


def unauthorized(packet, severity_issues=()):
    """Nothing authorized (no draft): the card carries members and obligations only."""
    return {'claims': [], 'action': None, 'handling': set(), 'severity': unassessed_severity(packet.get('preliminary_severity')),
            'severity_issues': list(severity_issues), 'severity_notes': [], 'summary': None, 'resolution': 'UNKNOWN',
            'open_question_supported': None, 'open_question_verdict': None, 'action_rationale': None, 'review_note': None,
            'member_resolution': {m: 'UNKNOWN' for m in packet['member_ids']}, 'withheld': []}


def inherited_flags(record, member_ids, *, projection_gap=None):
    """Every upstream obligation touching these members (and group-level ones) stays attached."""
    gid, members, flags = record['candidate_group_id'], set(member_ids), []
    for o in record.get('inherited_review_obligations', []):
        if o['member_id'] in members:
            flags.append(InheritedFlag(origin='agent1', kind='inherited_agent1_review', candidate_group_id=gid,
                                       member_ids=[o['member_id']], detail=o['agent1_record'].get('review_reason') or None))
    for o in record.get('agent2_review_obligations', []):
        ids = sorted(set(o.get('member_ids', [])) & members) or sorted(members)
        flags.append(InheritedFlag(origin='agent2', kind=o['kind'], candidate_group_id=gid, member_ids=ids))
    for o in record.get('content_review_obligations', []):
        finding = o.get('finding') or {}
        flags.append(InheritedFlag(origin='assisted_content_review', kind='assisted_content_review', candidate_group_id=gid,
                                   obligation_id=o['obligation_id'],
                                   detail=str(finding.get('summary') or finding.get('issue') or '') or None))
    if projection_gap:
        flags.append(InheritedFlag(origin='agent2', kind='projection_gap', candidate_group_id=gid,
                                   member_ids=sorted(members), detail=projection_gap))
    return flags


def _reason(code, detail, **extra):
    return ReviewReason(code=code, detail=detail, **extra)


def _reasoning(final, packet):
    """Plain-language reasoning from what passed grounding; statement IDs and verdicts stay in diagnostics."""
    lines = [c.text for c in final['claims']]
    counts = Counter(final['member_resolution'].values())
    withheld = [w for w in final['withheld'] if w['kind'] != 'ALTERNATIVE']
    parts = ['What the evidence shows: ' + ' '.join(lines) if lines else 'No advisor finding was supported by the evidence.',
             "Thread status, read from each thread's own messages: "
             + ', '.join(f'{_plain(k)} \u00d7{n}' for k, n in sorted(counts.items())) + '.',
             _attributed_note(packet['agent1_resolution'])]
    if final['severity_notes']:
        parts.append('Severity was recalculated from the supported evidence only.')
    if withheld:
        parts.append(f'{len(withheld)} advisor statement{"s were" if len(withheld) != 1 else " was"} not supported by the '
                     'evidence and not shown.')
    return ' '.join(parts)


def _coverage_note(issue):
    need, _, state = issue.partition(': ')
    what = {'CURRENT_GUIDANCE': 'current guidance', 'ANNOUNCEMENTS': 'announcements',
            'PRIOR_DECISIONS': 'earlier decisions and their outcomes', 'MEMBER_QUESTIONS': "members' questions"}.get(need, need)
    if 'not incorporated' in state:
        return (f'Research on {what}: relevant records were found but not used, because the revision step did not run. '
                'Check them before acting.')
    if 'found no new evidence' in state or 'still missing' in state:
        return f'Research on {what}: nothing further was found.'
    if 'not run' in state or 'not researched' in state:
        return f'Research on {what} was not completed.'
    return f'The advisor did not fully check {what}.'


def _stage_note(failure):
    stage = {'draft': 'drafting', 'revision': 'revision', 'tot': 'option comparison', 'grounding': 'evidence check'}.get(
        failure['stage'], failure['stage'])
    cause = {'RESOURCE': ' (a request limit was reached)', 'CONFIGURATION': ' (a configuration problem)',
             'SCHEMA': ' (the response was not valid)'}.get(failure.get('failure_class'), '')
    return f'The {stage} step did not complete{cause}; details are in the diagnostics.'


def assemble_card(outcome, packet, *, run_id):
    """Route to a card line from final validated results. Each review reason (structured, internal codes) has a
    plain-language review note; an open question is a reason only if the final grounding supported it."""
    draft, grounding, temporal, final = outcome.get('draft'), outcome['grounding'], outcome.get('temporal'), outcome['final']
    severity, flags = final['severity'], outcome['inherited_flags']
    confidence = draft.confidence if draft else 0.0
    reasons, notes = [], [final['review_note']] if final.get('review_note') else []

    def reason(code, detail, note, **extra):
        reasons.append(_reason(code, detail, **extra))
        if note:
            notes.append(note)
    if confidence < 0.60:
        reason('LOW_CONFIDENCE', f'Advisor confidence {confidence:.2f} is below 0.60.' if draft else
               'No valid Advisor draft; confidence recorded as 0.', "The advisor's confidence is low." if draft else
               'The advisor produced no usable draft; the threads are listed for review.')
    if severity.level == 'HIGH':
        reason('HIGH_SEVERITY', 'Assessed HIGH under the shared default rubric.', 'Severity is high under the team rubric.')
    if flags:
        kinds = Counter(f.kind for f in flags)
        reason('INHERITED_FLAG', 'Upstream obligations remain open: ' + ', '.join(f'{k} x{n}' for k, n in sorted(kinds.items())),
               f'{len(flags)} earlier review flag{"s are" if len(flags) != 1 else " is"} still open on these threads.',
               obligation_ids=sorted({f.obligation_id for f in flags if f.obligation_id}))
    if temporal and temporal['status'] == 'DETECTED':
        reason('TEMPORAL_CONFLICT', '; '.join(f"{f['code']}: {f['detail']}" for f in temporal['findings'] if f['status'] == 'DETECTED'),
               'Sources disagree on a point, and the records do not settle which applies; confirm before acting.')
    if grounding['status'] == 'FAILED':
        detail = [f"{s['statement_id']}: {s['verdict']}" for s in grounding['statements']
                  if s['blocking'] and s['statement_id'] in grounding['unsupported'] + grounding['unjudged']]
        reason('GROUNDING_FAILURE', 'Withheld from this card: ' + ('; '.join(detail) or 'grounding failed.'),
               'Some advisor statements were not supported by the evidence and are not shown.')
    elif grounding['status'] == 'NOT_RUN':
        reason('GROUNDING_NOT_RUN', f"Grounding not run: {grounding['basis']}; no Advisor statement is shown as established.",
               "The advisor's statements could not be checked against the evidence, so none is shown as established.")
    verdict = final.get('open_question_verdict')
    if draft and draft.open_confirmation == 'OPEN' and final['open_question_supported']:
        reason('OPEN_CONFIRMATION', draft.open_question, f'Open question: {draft.open_question}')
    open_check = ('OPEN' if final['open_question_supported'] else 'NOT_CHECKED' if verdict in ('PENDING', 'NOT_JUDGED')
                  else 'NONE') if draft and draft.open_confirmation == 'OPEN' else (draft.open_confirmation if draft else 'NOT_CHECKED')
    for issue in outcome.get('coverage_issues') or []:
        reason('OTHER', f'Evidence coverage incomplete: {issue}', _coverage_note(issue))
    sufficiency = outcome.get('evidence_sufficiency')
    if sufficiency in {'INSUFFICIENT', 'UNSUPPORTED'}:
        gaps = [g.description for g in draft.gaps] if draft else []
        reason('OTHER', f'Evidence {sufficiency.lower()}: ' + ('; '.join(gaps) or 'no applicable source found.'),
               'The evidence is not enough to recommend an action.' if sufficiency == 'UNSUPPORTED' else
               'Some evidence the advisor needed is missing.')
    if final['severity_issues']:
        reason('OTHER', 'Severity not established: ' + '; '.join(final['severity_issues']),
               'Severity could not be established from the supported evidence.')
    for failure in outcome['failures']:
        reason('OTHER', f"{failure['stage']}: {failure['status']} ({failure.get('error', '')})", _stage_note(failure))
    action = final['action'] if sufficiency != 'UNSUPPORTED' else None
    if action is not None and final.get('essential') is not None:
        notes.append("The advisor's first proposal was not supported; this action is a reviewed alternative that passed "
                     'the same checks.')
    operational = action is not None and action.action_type != 'NO_ACTION'
    line = 'NEEDS_REVIEW' if reasons else 'RECOMMENDED_ACTION' if operational else 'OBSERVATION'
    ledger = outcome['ledger']
    cited = [e for c in final['claims'] for e in c.evidence_ids] + sorted(final['handling'])
    if action:
        cited += [t.evidence_id for t in action.targets] + list(final.get('fallback_evidence') or [])
    cited = list(dict.fromkeys(e for e in cited if e in ledger))
    cited.sort(key=lambda e: ledger[e]['origin'] != 'retrieved_source')
    essential = final.get('essential') if final.get('essential') is not None else (
        (grounding.get('action_sufficiency') or {}).get('essential_statement_ids') or [])
    data = {
        'card_id': stable_id('card', {'run': run_id, 'group': packet['candidate_group_id'], 'topic': packet['topic_id'],
                                      'members': sorted(packet['member_ids'])}),
        'project_id': packet['project_id'], 'topic_name': packet['topic_label'], 'card_line': line,
        'summary': final['summary'] or ("The advisor's summary is not shown because the evidence did not support it; see the "
                                        'related threads.' if draft else
                                        'No advisor draft is available; the threads and open review flags are listed.'),
        'severity': severity.model_dump(mode='json'), 'severity_is_provisional': severity.assessment_status == 'UNASSESSED',
        'resolution_status': final['resolution'],
        'recommended_action': {'action_type': action.action_type, 'label': ACTION_LABELS[action.action_type],
                               'instruction': action.instruction, 'rationale': final.get('action_rationale'),
                               'draft_text': action.draft_text, 'scope_note': action.scope_note,
                               'targets': display_targets(action, ledger), 'essential_premise_ids': list(essential),
                               'source': 'TOT_FALLBACK' if final.get('essential') is not None else outcome.get('action_source') or 'DRAFT'}
        if action else None,
        'reasoning': _reasoning(final, packet) if draft else 'No advisor reasoning is available. ' + _attributed_note(packet['agent1_resolution']),
        'supporting_sources': [evidence_ref(ledger[e], packet, final['handling']).model_dump(mode='json') for e in cited],
        'related_threads': [related_thread(m, packet).model_dump(mode='json') for m in packet['members']],
        'confidence': confidence, 'needs_review_reasons': [r.model_dump(mode='json') for r in reasons],
        'review_notes': list(dict.fromkeys(notes)),
        'inherited_flags': [f.model_dump(mode='json') for f in flags],
        'checks': {'grounding': grounding['status'],
                   'temporal_conflict': temporal['status'] if temporal else 'NOT_CHECKED',
                   'open_confirmation': open_check},
        'lineage': {'agent3_run_id': run_id, 'handoff_contract': packet['handoff_contract'],
                    'agent2_export_sha256': packet['export_sha256'], 'agent2_schema_version': packet['schema_version'],
                    'candidate_group_id': packet['candidate_group_id'], 'topic_id': packet['topic_id'],
                    'member_ids': packet['member_ids'], 'project_id': packet['project_id'], 'batch_id': packet['batch_id']},
    }
    leaks = card_names(data) + card_ids(data)
    if leaks:  # Guard: display text uses roles and plain words; a leak is reported, never rewritten.
        data['needs_review_reasons'].append(_reason('OTHER', 'Internal identifier or personal name in card text: '
                                                    + '; '.join(leaks)).model_dump(mode='json'))
        data['review_notes'].append('Some card text contains a name or internal identifier; check the wording.')
        data['card_line'] = 'NEEDS_REVIEW'
    return AdviceCardV3.model_validate(data)


def _display_fields(data):
    action = data.get('recommended_action') or {}
    return {'topic_name': data['topic_name'], 'summary': data['summary'], 'reasoning': data['reasoning'],
            'action': ' '.join(action.get(k) or '' for k in ('instruction', 'rationale', 'draft_text', 'scope_note')),
            'review_notes': ' '.join(data.get('review_notes') or [])}


def card_ids(data):
    """Raw IDs or enum names in the card's display text, outside quotations."""
    return [f'{field}: {", ".join(sorted(set(found)))}' for field, text in _display_fields(data).items()
            if (found := RAW_ID.findall(_unquoted(text)))]


def card_names(data):
    """Directory names in the card's display text (title, summary, reasoning, action, review notes), outside quotations."""
    return [f'{field}: {name}' for field, text in _display_fields(data).items() for name in _directory_names()
            if re.search(rf'\b{re.escape(name)}\b', _unquoted(text))]


LABEL_SENTENCE_MAX = 100


def thread_label(thread):
    """Short label for a related problem thread: channel, date, starter's role and, when it is short, the opening
    message's first complete sentence quoted unchanged. Never cut mid-sentence; the full opening message is stored
    alongside (RelatedThreadV2.opening_text)."""
    root = next((m for m in thread['messages'] if m['message_id'] == thread['thread_id']), thread['messages'][0])
    lines = [line.strip() for line in root['text'].splitlines() if line.strip() and not re.fullmatch(r'\[[^\]]*\]', line.strip())]
    text = ' '.join(' '.join(lines).split())
    first = re.match(r'.+?[.?!](?=\s|$)', text)
    sentence = first.group(0) if first else text
    role = (root.get('author_role') or 'member').replace('_', ' ').lower().replace('qa ', 'QA ')
    date, article = (thread.get('created_at') or '')[:10], 'an' if role[0] in 'aeiou' else 'a'
    label = f"#{thread.get('channel_name') or thread['channel_id']}{', ' + date if date else ''}, started by {article} {role}"
    return label + (f': "{sentence}"' if len(sentence) <= LABEL_SENTENCE_MAX else '')


def related_thread(member, packet):
    thread = member['original_thread']
    root = next((m for m in thread['messages'] if m['message_id'] == thread['thread_id']), {})
    permalink = thread.get('permalink') or root.get('permalink')
    return RelatedThreadV2(project_id=packet['project_id'], batch_id=packet['batch_id'], channel_id=member['channel_id'],
                           thread_id=member['thread_id'], member_id=member['member_id'], permalink=permalink,
                           display_reference=permalink or member['thread_id'], label=thread_label(thread),
                           opening_text=root.get('text') or thread['messages'][0]['text'])
