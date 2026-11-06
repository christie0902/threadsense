"""What the team lead needs to check on one saved card, built from saved data only (no model call, nothing written).

Every entry comes from the card's final review reasons and the saved topic result: the reason itself, the field or
thread it concerns, what to check, and links to the saved evidence, related threads or Model Review Queue items.
Nothing is reworded from model text except by quoting saved fields; withheld statements are described by field and
verdict and never shown as fact. When a run did not save a detail (older runs, the hand-written fixture), the entry
says it is unavailable instead of guessing.

Categories keep apart why review is needed: MANDATORY (high severity: required even when the recommendation is
supported), DISPUTED (statements the final evidence check did not support), MISSING (a fact or step the run could
not establish), INHERITED (upstream flags still open), CONFLICT (sources disagree or were replaced), DECISION (a
handling question or a close choice for the team lead) and OTHER.
"""
import re

from threadsense.agents.advice_contracts import GROUPING_LABEL
from threadsense.dashboard.checks import build_checks

REVIEW_VIEW_VERSION = 'dashboard-review-view-v3'
STEP_ITEMS = {'OPEN_FOLLOW_UP': ('MISSING', 'A related thread is still open', 'Related threads'),
              'NO_ACTION_NOT_SUPPORTED': ('DISPUTED', 'No-action choice needs review', 'Next step'),
              'RECOMMENDATION_WITHHELD': ('DISPUTED', 'Recommendation needs review', 'Recommended action'),
              'NO_RECOMMENDATION': ('MISSING', 'No recommendation available', 'Next step')}
REVIEW_NOTE_PREFIX = 'Still needs review: '

# Plain-language notes that assemble_card adds for each review reason (advisor_checks.assemble_card). They repeat the
# reason, so the review view shows the reason once instead of listing these again.
REASON_NOTES = (
    r"The advisor's confidence is low\.$", r'The advisor produced no usable draft',
    r'Severity is high under the team rubric\.$', r'\d+ earlier review flags? (are|is) still open on these threads\.',
    r'Topic grouping needs review: these threads have no assigned topic\.$',
    r'Sources disagree on a point, and the records do not settle which applies', r'Some advisor statements were not supported',
    r"The advisor's statements could not be checked against the evidence", r'Open question: ',
    r'The evidence supports more than one option and none is clearly better', r'Research on ', r'The advisor did not fully check ',
    r'No-action choice needs review: ', r'Recommendation needs review: ', r'No recommendation is available for this topic\.$',
    r'A related thread is still open; see the (?:outstanding step|pending follow-up)\.$',
    r'The evidence is not enough to recommend an action\.$', r'Some evidence the advisor needed is missing\.$',
    r'Severity could not be established from the supported evidence\.$', r'The [a-z ]+ step did not complete',
    r'Some card text contains a name or internal identifier',
)
# Notes assemble_card adds without a review reason of their own; shown as "also noted".
EXTRA_NOTES = (r'The final evidence check found that current sources differ on', r'The advisor proposed "',
               r"The advisor's first proposal was not supported")

VERDICTS = {
    'UNSUPPORTED': 'the evidence check found no support for it in the cited evidence',
    'PARTIALLY_SUPPORTED': 'the evidence check found it only partly supported',
    'CONTRADICTED': 'the evidence check found it contradicted by the evidence',
    'NO_INTERVENTION_NEED': 'the evidence did not show a need to intervene now',
    'NOT_JUDGED': 'the evidence check did not judge it', 'PENDING': 'not judged (replay)',
    'NOT_SENT': 'it was not sent to the evidence check', 'REJECTED': 'it failed a deterministic check before the evidence check',
}
FLAG_CHECKS = {
    'inherited_agent1_review': "Agent 1's reading of this thread was not verified. Read the thread itself before relying on "
                               'its summary.',
    'inherited_agent1_review_announcement_route': "Agent 1's reading of this announcement-route thread was not verified. "
                                                  'Read it before relying on its summary.',
    'projection_gap': 'Agent 2 did not assign these threads to a topic; the projection grouped them. Check that they '
                      'belong together. This is a grouping condition on the card, not an Agent 1/2 review obligation.',
    'assisted_content_review': 'An assisted content review raised a finding on this group; check it.',
}
FLAG_LABELS = {'inherited_agent1_review': 'Agent 1 interpretation not verified',
               'inherited_agent1_review_announcement_route': 'Agent 1 interpretation not verified (announcement route)',
               'projection_gap': GROUPING_LABEL, 'assisted_content_review': 'Assisted content review finding'}
TEMPORAL_CODES = {'SUPERSEDED_GUIDANCE': 'A cited source has been replaced', 'SOURCE_CONFLICT': 'Current sources disagree',
                  'UNRESOLVED_VERSION': 'Competing revisions could not be ordered'}


def _words(s):
    return (s or '').replace('_', ' ').lower()


def matches(note, patterns):
    return any(re.match(p, note) for p in patterns)


class Links:
    """Resolve saved evidence IDs, threads and queue items to link entries; unknown IDs are reported, not dropped."""

    def __init__(self, card, ledger, queue):
        self.card, self.ledger, self.queue = card, ledger or {}, list(queue or [])
        self.threads = {t['thread_id']: t for t in card['related_threads']}
        self.by_member = {t['member_id']: t for t in card['related_threads']}

    def evidence(self, evidence_id):
        e = self.ledger.get(evidence_id)
        if e is None:
            return {'kind': 'evidence', 'id': evidence_id, 'label': evidence_id, 'available': False}
        if e.get('origin') == 'member_message':
            thread = self.threads.get(e.get('thread_id'))
            role = (_words(e.get('author_role')) or 'participant').replace('qa ', 'QA ')
            where = f" in {thread['label']}" if thread else ''
            article = 'an' if role[0] in 'aeiou' else 'a'
            return {'kind': 'evidence', 'id': evidence_id, 'label': f'Message by {article} {role}{where}', 'available': True}
        c = e.get('citation') or {}
        sections = ', '.join(c.get('sections') or [])
        return {'kind': 'evidence', 'id': evidence_id, 'available': True,
                'label': f"{c.get('title') or c.get('authoring') or evidence_id}{f' - {sections}' if sections else ''}"}

    def evidence_list(self, ids, skip=()):
        return [self.evidence(i) for i in dict.fromkeys(i for i in ids or [] if i and i not in skip)]

    def thread_of_member(self, member_id):
        t = self.by_member.get(member_id)
        return {'kind': 'thread', 'channel': t['channel_id'], 'thread': t['thread_id'], 'label': t['label']} if t else None

    def queue_items(self, flag):
        """Model Review Queue items for one inherited flag: the same obligation, or the same kind on the same members."""
        members = set(flag.get('member_ids') or [])
        found = [i for i in self.queue if (flag.get('obligation_id') and i.get('obligation_id') == flag['obligation_id'])
                 or (i.get('kind') == flag['kind'] and members and members <= set(i.get('member_ids') or []))]
        return [{'kind': 'queue', 'item_id': i['item_id'], 'label': f"Model Review Queue: {_words(i['kind'])}"} for i in found]


def _field(statement_id, kind, links, alternatives):
    """The card field a statement fills, in team lead words, plus a link when the statement concerns one source."""
    sid = statement_id or ''
    if sid == 'action':
        return 'Recommended action', []
    if sid.startswith('action:'):
        return {'action:rationale': 'Why the action helps', 'action:need': 'Why intervening now is needed',
                'action:choice': 'Choice between actions',
                'action:no_action': 'Why no action is needed'}.get(sid, 'Recommended action'), []
    if m := re.fullmatch(r'summary:s(\d+)', sid):
        return f'Summary, sentence {m.group(1)}', []
    if m := re.fullmatch(r'detail:d(\d+)', sid):
        return f'What happened, sentence {m.group(1)}', []
    if sid.startswith('claim:'):
        return f"Finding ({_words((kind or 'claim').replace('CLAIM_', ''))})", []
    if sid == 'review_note':
        return "Advisor's review note", []
    if sid == 'open_question':
        return 'Open question', []
    if sid.startswith('announcement:'):
        return 'How an announcement applies to this topic', [links.evidence(sid.split(':', 1)[1])]
    if sid.startswith('alternative:'):
        label = alternatives.get(sid.split(':', 1)[1])
        return f'Alternative option{f" ({label})" if label else ""}', []
    if sid.startswith('severity:'):
        return 'Severity', []
    if sid.startswith('resolution:'):
        t = links.thread_of_member(sid.split(':', 1)[1])
        return 'Thread status', [t] if t else []
    if sid.startswith('reporter:'):
        return 'Whether a reporter was personally affected', []
    return _words(kind) or sid, []


def withheld(result, links):
    """Statements kept off the card, by field and verdict. The judge's recorded reason is an assessment, labelled as such;
    the withheld text itself is not returned."""
    if not result:
        return None  # Not saved for this run.
    labels = {c['candidate_id']: _words(c['action_type']) for c in (result.get('tot') or {}).get('candidates') or []}
    entries, seen = [], set()
    diagnostics = [d for d in result.get('diagnostics') or [] if d.get('code') in ('WITHHELD_STATEMENT', 'ALTERNATIVE_NOT_GROUNDED')]
    statements = (result.get('grounding') or {}).get('statements') or []
    source = diagnostics or [s for s in statements if s.get('verdict') not in (None, 'SUPPORTED')]
    cited = {s['statement_id']: s.get('evidence_ids') for s in statements}  # Diagnostics do not repeat evidence IDs.
    for s in source:
        sid = s['statement_id']
        if sid in seen:
            continue
        seen.add(sid)
        field, extra = _field(sid, s.get('kind'), links, labels)
        verdict = s.get('verdict') or 'NOT_JUDGED'
        entries.append({'statement_id': sid, 'field': field, 'verdict': verdict,
                        'why': VERDICTS.get(verdict, _words(verdict)), 'checker_reason': s.get('rationale') or None,
                        'blocking': bool(s.get('blocking', True)),
                        'links': extra + links.evidence_list(s.get('evidence_ids') or cited.get(sid), skip={x.get('id') for x in extra})[:4]})
    return entries


def _severity_item(card, links):
    sev = card['severity']
    signals = [{'text': m['signal_text'], 'support': m.get('support'),
                'links': links.evidence_list(_ref_ids(m.get('evidence')))} for m in sev.get('matched_signals') or []]
    return {'category': 'MANDATORY', 'title': 'High severity',
            'field': 'Severity', 'check': 'Severity was assessed high under the team rubric. High severity always goes to a '
                                          'team lead, even when the recommendation is supported. The signals it met:',
            'signals': signals, 'unavailable': None if signals else "This run did not save the matched rubric signals."}


def _ref_ids(refs):
    return [(r.get('note') or '').split(' ')[0] for r in refs or [] if r.get('note')]


def _finding_view(prov):
    """The upstream finding behind a flag (agents/flag_provenance), kept apart from revision errors."""
    if prov is None:
        return None
    return {'recovery': prov['recovery'], 'note': prov.get('recovery_note'), 'card_detail_is': prov.get('card_detail_is'),
            'findings': [{'category': f['category'], 'nature': f['nature'], 'fields': f['disputed_fields'],
                          'text': f['explanation'], 'source': f['source']['path']} for f in prov['findings']],
            'attempt_errors': [{'stage': e['stage'], 'text': e['text']} for e in prov['attempt_errors']],
            'earlier': [{'status': h['status'], 'fields': h['finding']['disputed_fields'], 'text': h['finding']['explanation'],
                         'basis': h['basis']} for h in prov.get('finding_history') or []]}


def _flags_item(card, links, provenance=None):
    flags = card.get('inherited_flags') or []
    entries = []
    for i, f in enumerate(flags):
        prov = (provenance or [None] * len(flags))[i] if provenance and len(provenance) == len(flags) else None
        threads = [t for t in (links.thread_of_member(m) for m in f.get('member_ids') or []) if t]
        queue = links.queue_items(f)
        gap = f['kind'] == 'projection_gap'
        entries.append({'kind': f['kind'], 'label': FLAG_LABELS.get(f['kind'], _words(f['kind'])), 'grouping': gap,
                        'check': FLAG_CHECKS.get(f['kind'], 'An upstream review flag is still open; check it.'),
                        'links': threads + queue, 'upstream_detail': f.get('detail'), 'finding': _finding_view(prov),
                        'queue_note': None if queue else 'No Model Review Queue item: a grouping condition carried on the card '
                                      'only.' if gap else 'No Model Review Queue item: this flag is carried on the card only.'})
    n = sum(not e['grouping'] for e in entries)
    parts = [f'{n} earlier review flag{"s are" if n != 1 else " is"} still open'] if n else []
    parts += [GROUPING_LABEL.lower() if parts else GROUPING_LABEL] if any(e['grouping'] for e in entries) else []
    return {'category': 'INHERITED', 'title': '; '.join(parts) if parts else 'Earlier review flags are still open',
            'field': 'Related threads',
            'check': 'Upstream checks on these threads were not completed. The card does not clear them.',
            'flags': entries, 'unavailable': None if flags else 'This run did not save which flags are open.'}


def _grounding_item(reason, withheld_entries, links):
    blocked = [w for w in withheld_entries or [] if w['blocking']]
    ids = re.findall(r'(\S+): [A-Z_]+(?:;|$)', reason['detail'].removeprefix('Withheld from this card: '))
    if withheld_entries is None:
        entries, unavailable = [], 'This run did not save which statements were withheld.'
    else:
        entries = [w for w in blocked if not ids or w['statement_id'] in ids] or blocked
        unavailable = None if entries else 'The saved result does not say which statements were withheld.'
    return {'category': 'DISPUTED', 'title': 'Some content was withheld because the evidence did not support it',
            'field': ', '.join(dict.fromkeys(w['field'] for w in entries)) or 'Card statements',
            'check': 'Check the withheld fields against their sources before acting. Their wording is not shown and is not '
                     'established.', 'withheld': entries, 'unavailable': unavailable}


def _temporal_item(reason, result, links):
    findings = [f for f in ((result or {}).get('temporal') or {}).get('findings') or [] if f.get('status') == 'DETECTED']
    entries = [{'what': TEMPORAL_CODES.get(f.get('code'), _words(f.get('code'))), 'detail': f.get('detail'),
                'scope': f.get('scope'), 'links': links.evidence_list(f.get('evidence_ids'))} for f in findings]
    if not entries:  # Fall back to the reason's own detail (CODE: detail; ...).
        entries = [{'what': TEMPORAL_CODES.get(code, _words(code)), 'detail': detail, 'scope': None, 'links': []}
                   for code, _, detail in (part.partition(': ') for part in reason['detail'].split('; ') if part)]
    return {'category': 'CONFLICT', 'title': 'Sources disagree, or a cited source was replaced', 'field': 'Sources',
            'check': 'Confirm which source applies before acting; the records do not settle it.', 'findings': entries,
            'unavailable': None}


def _open_question_item(reason, result, links):
    draft = ((result or {}).get('drafts') or {}).get('final') or {}
    ids = draft.get('open_question_evidence_ids') or []
    return {'category': 'DECISION', 'title': 'A handling question for you to settle', 'field': 'Open question',
            'check': reason['detail'], 'links': links.evidence_list(ids),
            'unavailable': None if result else 'This run did not save the evidence for the open question.'}


def _other_item(reason):
    detail = reason['detail']
    if detail.startswith('Evidence coverage incomplete: '):
        need, _, state = detail.removeprefix('Evidence coverage incomplete: ').partition(': ')
        return {'category': 'MISSING', 'title': f'Research incomplete: {_words(need)}', 'field': 'Research', 'need': need,
                'check': f'{state[:1].upper()}{state[1:]}. A search that found nothing does not show that no record exists.'}
    if detail.startswith(('Evidence insufficient: ', 'Evidence unsupported: ')):
        return {'category': 'MISSING', 'title': 'Evidence the advisor needed is missing', 'field': 'Evidence',
                'check': detail.split(': ', 1)[1]}
    if detail.startswith('Severity not established: '):
        return {'category': 'MISSING', 'title': 'Severity could not be established', 'field': 'Severity',
                'check': detail.removeprefix('Severity not established: ')}
    if detail.startswith('Unresolved action choice'):
        return {'category': 'DECISION', 'title': 'Choose between closely matched options', 'field': 'Recommended action',
                'check': 'The evidence supports more than one option and neither is preferred; the options are shown together.'}
    if detail.startswith('Observation not established: '):
        return {'category': 'DECISION', 'title': 'No supported next step', 'field': 'Next step',
                'check': "The card cannot be an observation without a supported no-action reason; decide the next step."}
    if detail.startswith('Internal identifier or personal name'):
        return {'category': 'OTHER', 'title': 'Check the wording', 'field': 'Card text',
                'check': 'Some card text contains a name or internal identifier.'}
    if m := re.match(r'(draft|revision|tot|grounding|card_assembly): (\w+)', detail):
        step = {'draft': 'drafting', 'revision': 'revision', 'tot': 'option comparison', 'grounding': 'evidence check',
                'card_assembly': 'card assembly'}[m.group(1)]
        return {'category': 'MISSING', 'title': f'The {step} step did not complete', 'field': 'Processing',
                'check': f'Status {_words(m.group(2))}; the card shows only what passed the checks.'}
    return {'category': 'OTHER', 'title': 'Other review reason', 'field': None, 'check': detail}


def review_view(card, result=None, queue=(), provenance=None):
    """The card's review panel: one entry per final review reason, the advisor's own review note (if the final
    evidence check supported it), withheld statements, and notes that are not tied to a reason."""
    links = Links(card, (result or {}).get('evidence_ledger'), queue)
    held = withheld(result, links)
    items = []
    for reason in card['needs_review_reasons']:
        code = reason['code']
        if code == 'HIGH_SEVERITY':
            item = _severity_item(card, links)
        elif code == 'INHERITED_FLAG':
            item = _flags_item(card, links, provenance)
        elif code == 'GROUNDING_FAILURE':
            item = _grounding_item(reason, held, links)
        elif code == 'GROUNDING_NOT_RUN':
            item = {'category': 'DISPUTED', 'title': 'Nothing on this card was checked against the evidence',
                    'field': 'All statements', 'check': reason['detail']}
        elif code == 'TEMPORAL_CONFLICT':
            item = _temporal_item(reason, result, links)
        elif code == 'OPEN_CONFIRMATION':
            item = _open_question_item(reason, result, links)
        elif code == 'LOW_CONFIDENCE':
            item = {'category': 'OTHER', 'title': "The advisor's confidence is low", 'field': 'Whole card', 'check': reason['detail']}
        elif code in STEP_ITEMS:  # briefing_policy (AdviceCard v5): why a card without a supported next step stays here.
            category, title, field = STEP_ITEMS[code]
            item = {'category': category, 'title': title, 'field': field, 'check': reason['detail']}
        else:
            item = _other_item(reason)
        items.append({'code': code, 'links': [], 'unavailable': None, **item})
    note = None
    statement = next((s for s in ((result or {}).get('grounding') or {}).get('statements') or []
                      if s['statement_id'] == 'review_note'), None)
    if statement and statement.get('verdict') == 'SUPPORTED':
        text = statement['text'].removeprefix(REVIEW_NOTE_PREFIX)
        if text in card['review_notes']:
            note = {'text': text, 'links': links.evidence_list(statement.get('evidence_ids'))}
    shown = {note['text']} if note else set()
    other = [n for n in card['review_notes'] if n not in shown and not matches(n, REASON_NOTES)]
    view = {'version': REVIEW_VIEW_VERSION, 'items': items, 'advisor_note': note, 'withheld': held,
            'other_notes': other, 'saved_result': result is not None}
    view['checks'] = build_checks(card, result, links.ledger, view)
    return view
