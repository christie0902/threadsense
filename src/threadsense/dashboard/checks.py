"""What to check: the reader-first list a team lead sees when they open a card (built from dashboard.review's view).

Headings, link labels and status lines are fixed UI copy (text_origin UI). Questions, the advisor's note and severity
support are saved text shown verbatim (text_origin SAVED); nothing saved is reworded here. Items are grouped only where
saved evidence links them: a research gap joins the open question when evidence its follow-up recovered is cited by the
question; the advisor's note joins the question when both cite the same retrieved source, or a flag when the note
cites a message in that flagged thread. Every original reason, verdict and link stays in the review view's `items`.
"""
from threadsense.agents.advice_contracts import GROUPING_LABEL

COVERAGE_WORDS = {'PRIOR_DECISIONS': 'earlier decisions and their outcomes', 'CURRENT_GUIDANCE': 'current guidance',
                  'ANNOUNCEMENTS': 'announcements', 'MEMBER_QUESTIONS': "members' questions"}
ORDER = ('QUESTION', 'CHOICE', 'CONFLICT', 'WITHHELD', 'FLAG', 'GAP', 'STEP', 'WORDING', 'CONFIDENCE', 'SEVERITY', 'NOTE')


def is_message(link):
    return link['kind'] == 'evidence' and link['label'].startswith('Message by')


SOURCE_VERBS = {'decision': 'View the record', 'guideline': 'Open the instructions', 'faq': 'Open the FAQ',
                'announcement': 'Open the announcement'}
FLAG_TEXT = {
    'inherited_agent1_review': ('Flagged thread', 'An earlier automated summary of this thread was not verified. Read the '
                                'thread itself before relying on it.'),
    'inherited_agent1_review_announcement_route': ('Flagged thread', 'An earlier automated summary of this announcement '
                                                   'thread was not verified. Read it before relying on it.'),
    'projection_gap': (GROUPING_LABEL, 'These threads were grouped without an assigned topic. Check that they belong '
                       'together; this is not an upstream review obligation.'),
    'assisted_content_review': ('Content finding', 'A content review raised a finding on this group.'),
}


def labelled(link, verb=None, ledger=None):
    """A link labelled by what it opens; the saved label becomes its detail line."""
    if verb is None and ledger is not None and link['kind'] == 'evidence' and not is_message(link):
        verb = SOURCE_VERBS.get((ledger.get(link['id']) or {}).get('source_type'))
    if link['kind'] == 'queue':
        return {**link, 'label': 'Open its Model Review Queue item', 'detail': None}
    if link['kind'] == 'thread':
        return {**link, 'label': verb or 'Open thread', 'detail': link['label']}
    if is_message(link):
        return {**link, 'label': verb or 'Open message', 'detail': link['label'].removeprefix('Message by ')}
    return {**link, 'label': verb or 'Open source', 'detail': link['label']}


def checked_parts(card, result):
    """What the saved statement verdicts show passed on this card, or None when they cannot establish it: 'SUMMARY'
    when the displayed summary is exactly its SUPPORTED summary sentences; 'NO_ACTION' when, in addition, a supported
    reason for no action is displayed; 'RECOMMENDATION' when, in addition, a displayed operational action has its own
    SUPPORTED verdict (a reviewed alternative: its own supported, sufficient judgment). Never from the overall grounding
    status alone; an unvalidated NO_ACTION, a withheld or an unavailable recommendation adds nothing."""
    statements = ((result or {}).get('grounding') or {}).get('statements') or []
    verdict = {x['statement_id']: x.get('verdict') for x in statements}
    summary = [x for x in statements if x['statement_id'] == 'summary' or x['statement_id'].startswith('summary:s')]
    shown = ' '.join(x['text'] for x in summary if x.get('verdict') == 'SUPPORTED')
    if not summary or not shown or ' '.join(card['summary'].split()) != ' '.join(shown.split()):
        return None
    action = card.get('recommended_action') or {}
    if action and action.get('action_type') != 'NO_ACTION':
        if action.get('source', 'DRAFT') == 'DRAFT':
            ok = verdict.get('action') == 'SUPPORTED'
        else:
            judged = ((result or {}).get('grounding') or {}).get('alternative_sufficiency') or {}
            ok = any(verdict.get(sid) == 'SUPPORTED' and (j or {}).get('check') == 'SUPPORTED' for sid, j in judged.items())
        return 'RECOMMENDATION' if ok else 'SUMMARY'
    step = card.get('next_step') or {}
    if action.get('action_type') == 'NO_ACTION' and verdict.get('action') == 'SUPPORTED':
        return 'NO_ACTION'
    if step.get('status') == 'NO_ACTION_NEEDED' and step.get('rationale') and verdict.get('action:no_action') == 'SUPPORTED':
        return 'NO_ACTION'
    return 'SUMMARY'


PASSED_WORDS = {'RECOMMENDATION': ('The summary and recommendation passed', 'the recommendation'),
                'NO_ACTION': ('The summary and the reason for no action passed', 'either of them'),
                'SUMMARY': ('The summary passed', 'the summary')}


def build_checks(card, result, ledger, view):
    items = view['items']
    by_code = {}
    for item in items:
        by_code.setdefault(item['code'], []).append(item)
    draft = ((result or {}).get('drafts') or {}).get('final') or {}
    question_ids = set(draft.get('open_question_evidence_ids') or [])
    recovered = {f['gap_id']: set(f.get('new_evidence_ids') or []) for f in (result or {}).get('follow_ups') or []}
    gap_of_need = {c['need']: c.get('gap_id') for c in draft.get('coverage') or []}
    note = view['advisor_note']
    note_ids = {l['id'] for l in (note or {}).get('links', []) if l['kind'] == 'evidence'}
    checks, grouped, placed = [], set(), False

    for item in by_code.get('OPEN_CONFIRMATION', []):
        sources = [l for l in item['links'] if l['kind'] == 'evidence' and not is_message(l)]
        check = {'kind': 'QUESTION', 'heading': 'Question for you', 'text': item['check'], 'text_origin': 'SAVED',
                 'links': [labelled(l, ledger=ledger) for l in sources[:3]], 'related': []}
        for i, gap in enumerate(items):
            need = gap.get('need') if gap['code'] == 'OTHER' else None
            if need and recovered.get(gap_of_need.get(need), set()) & question_ids:
                check['related'].append(f"This run's searches did not find a recorded answer on {COVERAGE_WORDS[need]}.")
                grouped.add(i)
        if note and note_ids & {l['id'] for l in sources}:
            check['note'], placed = note['text'], True
        checks.append(check)

    for item in by_code.get('TEMPORAL_CONFLICT', []):
        for f in item.get('findings') or []:
            checks.append({'kind': 'CONFLICT', 'heading': 'Sources disagree', 'text_origin': 'UI',
                           'text': f"{f.get('what') or 'Sources disagree'}{' (' + f['scope'] + ')' if f.get('scope') else ''}. "
                                   'Confirm which one applies before acting.',
                           'links': [labelled(l, ledger=ledger) for l in f.get('links') or []][:3]})
    for item in by_code.get('GROUNDING_FAILURE', []):
        for w in item.get('withheld') or []:
            sources = [l for l in w['links'] if l['kind'] == 'evidence']
            checks.append({'kind': 'WITHHELD', 'heading': 'Not shown on this card', 'text_origin': 'UI',
                           'text': f"{w['field']}: not shown, because {w['why']}. The withheld wording is not established.",
                           'links': [labelled(l, 'Open the source it was about') for l in sources[:1]]})
        if not item.get('withheld'):
            checks.append({'kind': 'WITHHELD', 'heading': 'Not shown on this card', 'text_origin': 'UI', 'links': [],
                           'text': "Part of the advisor's text was withheld because the evidence did not support it. This run "
                                   'did not save which part.'})
    for item in by_code.get('GROUNDING_NOT_RUN', []):
        checks.append({'kind': 'WITHHELD', 'heading': 'Not checked against the evidence', 'text_origin': 'UI', 'links': [],
                       'text': "None of the advisor's statements on this card were checked, so none is shown as established."})
    passed = checked_parts(card, result)
    for item in by_code.get('INHERITED_FLAG', []):
        kinds = {}
        for f in item.get('flags') or []:  # Flags of the same recorded kind are one check, each thread listed.
            kinds.setdefault(f['kind'], []).append(f)
        upstream = [f for f in item.get('flags') or [] if f['kind'] != 'projection_gap']  # Grouping is not a reading.
        flagged_all = {l['thread'] for f in upstream for l in f['links'] if l['kind'] == 'thread'}
        for n, (kind, flags) in enumerate(kinds.items()):
            heading, text = FLAG_TEXT.get(kind, ('Flagged upstream', 'An earlier review flag is still open here.'))
            threads = [l for f in flags for l in f['links'] if l['kind'] == 'thread']
            single = all(len([l for l in f['links'] if l['kind'] == 'thread']) == 1 for f in flags)
            if single and len(flags) > 1:
                heading = f'{heading}s ({len(flags)})'
                text = text.replace('this thread', 'each thread').replace('Read the thread itself', 'Read each thread')
            links = []
            for f in flags:
                own = [l for l in f['links'] if l['kind'] == 'thread']
                links += [labelled(l, 'Open flagged thread' if single else 'Open thread') for l in own[:3]]
                links += [labelled(l) for l in f['links'] if l['kind'] == 'queue']
            check = {'kind': 'FLAG', 'heading': heading, 'text': text, 'text_origin': 'UI', 'links': links,
                     'more_links': 0 if single else max(0, len(threads) - 3), 'related': []}
            if passed and upstream and kind == upstream[0]['kind']:
                total = len(upstream)
                subject, what = PASSED_WORDS[passed]
                check['related'].append(f'{subject} the evidence check; '
                                        + ('the flags concern' if total > 1 else 'the flag concerns')
                                        + " an earlier step's reading of "
                                        + ('this thread' if len(flagged_all) == 1 else 'these threads') + f', not {what}.')
            flagged = {l['thread'] for l in threads}
            if note and not placed and any((ledger.get(i) or {}).get('thread_id') in flagged for i in note_ids):
                check['note'], placed = note['text'], True
            checks.append(check)
        if not item.get('flags'):
            checks.append({'kind': 'FLAG', 'heading': 'Flagged upstream', 'text_origin': 'UI', 'links': [],
                           'text': 'Earlier review flags are still open on these threads; this run did not save which.'})
    for i, item in enumerate(items):
        if item['code'] != 'OTHER' or i in grouped:
            continue
        if item['title'].startswith('Choose between'):
            checks.append({'kind': 'CHOICE', 'heading': 'Choose between the options', 'text_origin': 'UI', 'links': [],
                           'text': 'The evidence supports more than one option and neither is preferred. Both are under '
                                   'Action & draft.'})
        elif item['title'].startswith('Research incomplete'):
            words = COVERAGE_WORDS.get(item.get('need'), 'this topic')
            checks.append({'kind': 'GAP', 'heading': 'Research gap', 'text_origin': 'UI', 'links': [],
                           'text': f"This run's searches found nothing further on {words}. That does not show that no record exists."})
        elif item['field'] == 'Processing':
            checks.append({'kind': 'STEP', 'heading': 'A step did not complete', 'text_origin': 'UI', 'links': [],
                           'text': f"{item['title']}. The card shows only what passed the checks."})
        elif item['title'] == 'Check the wording':
            checks.append({'kind': 'WORDING', 'heading': 'Check the wording', 'text': item['check'], 'text_origin': 'UI', 'links': []})
        else:
            checks.append({'kind': 'GAP', 'heading': item['title'], 'text_origin': 'UI', 'links': [],
                           'text': 'Details are under "All review reasons and evidence".'})
    for item in by_code.get('LOW_CONFIDENCE', []):
        checks.append({'kind': 'CONFIDENCE', 'heading': 'Low confidence', 'text_origin': 'UI', 'links': [],
                       'text': "The advisor's confidence in this card was low."})
    for item in by_code.get('HIGH_SEVERITY', []):
        signals = item.get('signals') or []
        messages = list({l['id']: l for s in signals for l in s['links']}.values())
        support = ' '.join(dict.fromkeys(s['support'] for s in signals if s.get('support')))
        checks.append({'kind': 'SEVERITY', 'heading': 'High severity', 'text_origin': 'SAVED' if support else 'UI',
                       'text': support or 'Assessed high under the team rubric. This run did not save the supporting signals.',
                       'links': [labelled(l, 'Open a report behind it') for l in messages[:2]],
                       'more_links': max(0, len(messages) - 2)})
    if note and not placed:
        checks.append({'kind': 'NOTE', 'heading': "Advisor's note", 'text': note['text'], 'text_origin': 'SAVED',
                       'links': [labelled(l, ledger=ledger) for l in note['links'][:2]]})
    # High severity leads when nothing else needs checking (an unattached note follows it); otherwise it follows the
    # specific items.
    alone = {c['kind'] for c in checks} <= {'SEVERITY', 'NOTE'}
    checks.sort(key=lambda c: (0 if alone and c['kind'] == 'SEVERITY' else 1, ORDER.index(c['kind'])))
    return checks
