"""Synthetic contract examples, never runtime knowledge or model accuracy evidence.

Reviewed inventory assignments below use the six frozen sources. They are newly
constructed expected outputs, NOT migrated/repaired historical model responses.
"""
from threadsense.handoff_inputs import ROOT, read_json
from threadsense.legacy.agent2.topic_evidence import evidence_catalog

FROZEN = ROOT / 'data/processed/agent2_revalidation_v3_2'
GIDS = [c['candidate_group_id'] for c in read_json(ROOT / 'docs/agent2-revalidation-v3-2.json')['cases']]


def payload(gid):
    return read_json(FROZEN / 'records' / gid / 'input.json')


def impact(eid, criterion='insufficient_impact_evidence', basis='INSUFFICIENT_EVIDENCE', text='Synthetic assessment: operational impact is not established.'):
    return {'criteria': [{'criterion': criterion, 'basis': basis,
                          'observation': {'text': text, 'evidence_ids': [eid]}}], 'affected_scope': None}


def wiring_draft(p):
    """Deliberately structure-only stub; lexical warnings must remain reviewable."""
    aliases, catalog = evidence_catalog(p)
    return {'schema_version': 4, 'topics': [{
        'topic_name': 'Synthetic wiring fixture', 'member_ids': list(aliases),
        'shared_issue': {'text': 'Synthetic wiring example, not a factual assessment.', 'evidence_ids': list(catalog)[:1]},
        'relevant_differences': [],
        'inventory': [{'item_id': eid, 'evidence_id': eid, 'kind': 'FACT', 'text': e['quote'], 'question': None}
                      for eid, e in catalog.items()],
        'dispositions': [], 'impact': impact(next(iter(catalog))),
    }]}


def reviewed_draft(gid):
    p = payload(gid)
    draft = wiring_draft(p)
    topic = draft['topics'][0]
    _, catalog = evidence_catalog(p)
    topic['inventory'] = []

    def add(eid, kind, text=None, *, status='OPEN', answers=()):
        item_id = f'{eid}_{kind}'
        topic['inventory'].append({'item_id': item_id, 'evidence_id': eid, 'kind': kind,
            'text': text or catalog[eid]['quote'],
            'question': {'status': status, 'answer_item_ids': list(answers)} if kind == 'QUESTION' else None})

    def difference(text, ids):
        topic['relevant_differences'].append({'text': text, 'evidence_ids': ids})

    if gid == GIDS[0]:
        topic['topic_name'] = 'Conflicting document guidance'
        topic['shared_issue'] = {'text': 'The later announcement and older guidance appear inconsistent; precedence remains unconfirmed.', 'evidence_ids': ['E001', 'E002', 'E004']}
        add('E001', 'QUESTION', 'Can we check whether the later announcement replaces the older note?')
        add('E002', 'QUESTION', 'Can we check whether the later announcement replaces the older note?')
        add('E003', 'DIAGNOSTIC_REQUEST')
        add('E004', 'INSTRUCTION')
    elif gid == GIDS[1]:
        topic['topic_name'] = 'Audio evaluation and playback problems'
        topic['shared_issue'] = {'text': 'Tutors ask how to handle silent output or playback failure. Current applicability of a remembered workaround is unconfirmed.', 'evidence_ids': ['E001', 'E004', 'E007', 'E011']}
        for eid in ('E001', 'E011'):
            add(eid, 'QUESTION')
        for eid in ('E004', 'E008', 'E014', 'E016'):
            source = catalog[eid]['quote']
            start = source.index('Player never') if 'Player never' in source else 0
            q = source[start:source.index('?', start)+1]
            linked = {'E014': 'E015_ANSWER', 'E016': 'E019_ANSWER'}.get(eid)
            add(eid, 'QUESTION', q, status='PARTIAL' if linked else 'OPEN', answers=[linked] if linked else [])
            add(eid, 'FACT', source[source.index('I thought'):])
        for eid in ('E002', 'E005', 'E009', 'E013'):
            add(eid, 'DIAGNOSTIC_REQUEST')
        for eid in ('E003', 'E006', 'E007', 'E017'):
            add(eid, 'INSTRUCTION')
        add('E010', 'INSTRUCTION', catalog['E010']['quote'].split(' Could')[0])
        add('E010', 'DIAGNOSTIC_REQUEST', 'Could' + catalog['E010']['quote'].split(' Could')[1])
        add('E012', 'FACT')
        add('E018', 'FACT', catalog['E018']['quote'].split(' Could')[0])
        add('E018', 'DIAGNOSTIC_REQUEST', 'Could' + catalog['E018']['quote'].split(' Could')[1])
        for eid in ('E015', 'E019'):
            text = catalog[eid]['quote']
            add(eid, 'ANSWER', text.split(' Report')[0])
            add(eid, 'INSTRUCTION', 'Report' + text.split(' Report')[1])
        difference('Silent output with a waveform differs from a player that never loads; neither alone establishes the underlying recording content.', ['E011', 'E014', 'E015'])
    elif gid == GIDS[2]:
        topic['topic_name'] = 'Quarantine questions about age mentions'
        topic['shared_issue'] = {'text': 'Questions ask whether an age mention alone requires Quarantine. A scoped school-context answer does not resolve every broader case.', 'evidence_ids': ['E001', 'E002', 'E003', 'E005']}
        add('E001', 'QUESTION', status='PARTIAL', answers=['E002_ANSWER'])
        add('E002', 'ANSWER')
        for eid in ('E003', 'E005', 'E007'):
            add(eid, 'QUESTION')
        for eid in ('E004', 'E006'):
            add(eid, 'FACT')
        difference('Examples describe a school schedule/story and a family anecdote, not a demonstrated harmful-content example.', ['E004', 'E005', 'E006'])
    elif gid == GIDS[3]:
        topic['topic_name'] = 'Team avatar location'
        topic['shared_issue'] = {'text': 'The avatar image location is unconfirmed; a reply tentatively points to design assets and pinned files.', 'evidence_ids': ['E001', 'E002']}
        add('E001', 'QUESTION', status='PARTIAL', answers=['E002_ANSWER'])
        add('E002', 'ANSWER')
        topic['impact'] = impact('E001', 'non_operational', 'NON_OPERATIONAL', 'A team avatar location question has no operational incident described.')
    elif gid == GIDS[4]:
        topic['topic_name'] = 'Submission control failures'
        topic['shared_issue'] = {'text': 'Reported submission controls fail in different ways. Actual submission status and the wider cause remain unconfirmed.', 'evidence_ids': ['E001', 'E006', 'E007', 'E012']}
        add('E001', 'ANNOUNCEMENT', catalog['E001']['quote'].split(' Please')[0])
        add('E001', 'INSTRUCTION', 'Please' + catalog['E001']['quote'].split(' Please')[1])
        for eid in ('E002', 'E003', 'E007', 'E010', 'E014', 'E015'):
            add(eid, 'FACT')
        for eid in ('E004', 'E008', 'E011', 'E016'):
            add(eid, 'DIAGNOSTIC_REQUEST', catalog[eid]['quote'].split('?')[0] + '?')
            if eid == 'E008':
                add(eid, 'INSTRUCTION', catalog[eid]['quote'].split('? ')[1])
        for eid in ('E005', 'E006', 'E009', 'E012', 'E013', 'E017'):
            add(eid, 'INSTRUCTION')
        difference('Some reports describe a disabled grey button; another describes clicking Submit with no effect.', ['E003', 'E007'])
        topic['impact'] = impact('E001', 'substantial_blockage', 'REPORTED_RISK', 'The batch note reports inability to complete labeled tasks across projects; exact scope remains under investigation.')
    else:
        topic['topic_name'] = 'Submission incident announcement'
        topic['shared_issue'] = {'text': 'A submission blockage is announced with a request for affected references; no policy change is announced.', 'evidence_ids': ['E001']}
        add('E001', 'ANNOUNCEMENT', catalog['E001']['quote'].split(' Add')[0])
        add('E001', 'INSTRUCTION', 'Add' + catalog['E001']['quote'].split(' Add')[1])
        add('E002', 'QUESTION', catalog['E002']['quote'].split('?')[0] + '?')
        add('E002', 'INSTRUCTION', catalog['E002']['quote'].split('? ')[1])
        topic['impact'] = impact('E001', 'substantial_blockage', 'REPORTED_RISK', 'The announcement reports inability to complete labeled tasks across projects; exact extent is unconfirmed.')
    return draft
