"""Zero-call Agent 3 input checks: Agent 2 handoff accounting, review items,
structural occurrence counts and historical decision records.

Nothing here assesses severity, grounds claims or chooses a card line.
"""
from collections import Counter
from pathlib import Path

from threadsense.agents.advice_contracts import (
    DecisionRecord, EvidenceRef, ModelReviewItem, OccurrenceEvidence, stable_id,
)
from threadsense.handoff_inputs import ROOT, file_hash, read_json
from threadsense.routing import slack_datetime

REGISTRY = ROOT/'data/metadata/agent2-review-supplements.json'
HISTORICAL_V7 = ROOT/'data/processed/agent2_taxonomy_final_v7'


def code_contract():
    """What the current Agent 2 code would export, read from the code itself (zero calls)."""
    from threadsense.agents import topic_pipeline, topic_taxonomy
    from threadsense.agents.topic_effective import taxonomy_handoff
    config = topic_pipeline.configuration([], 'openai/gpt-4o-mini')
    row = {'schema_version': config['schema_version'], 'candidate_group_id': '', 'processing_state': '',
           'topics': [], 'members': [], 'member_dispositions': [], 'rejected_member_ids': [],
           'unassigned_member_ids': [], 'review_obligations': [], 'review_evidence': [],
           'grouping_file': '', 'grouping_sha256': ''}
    return {'response_schema_version': config['response_schema_version'], 'export_schema_version': config['schema_version'],
            'export_adapter_version': config['export_adapter_version'], 'prompt_version': topic_taxonomy.PROMPT_VERSION,
            'rubric_version': config['rubric_version'], 'handoff_contract': taxonomy_handoff(row)['contract_version']}


def find_exports(root=ROOT/'data/processed'):
    """Every Agent 2 consolidations.json in the repository, by export schema version."""
    found = []
    for path in sorted(Path(root).glob('*/consolidations.json')):
        try:
            versions = sorted({r.get('schema_version') for r in read_json(path)}, key=str)
        except (ValueError, OSError, AttributeError, TypeError) as error:
            versions = [f'unreadable: {error}']
        found.append({'run': path.parent.relative_to(ROOT).as_posix(), 'schema_versions': versions})
    return found


def registry_status(run_dir, registry=REGISTRY):
    """Registered supplements for this run (hash-checked) and entries whose run is absent."""
    run = Path(run_dir).resolve()
    own, absent = [], []
    for entry in read_json(registry)['supplements']:
        target = (ROOT/entry['run']).resolve()
        if target == run:
            path = ROOT/entry['path']
            try:
                actual = file_hash(path)
            except OSError:
                actual = None
            own.append({'path': entry['path'], 'exists': actual is not None, 'sha256_matches': actual == entry['sha256']})
        elif not target.exists():
            absent.append(entry['run'])
    return {'registry': Path(registry).relative_to(ROOT).as_posix(), 'entries_for_run': own,
            'entries_for_missing_runs': sorted(set(absent))}


def accounting_issues(view):
    """Members, dispositions and obligations must survive exactly once."""
    issues, seen = [], Counter()
    for row in view['records']:
        gid, members = row['candidate_group_id'], {m['member_id']: m for m in row['members']}
        seen.update(m['member_id'] for m in row['members'])
        dispositions = {d['member_id']: d for d in row['member_dispositions']}
        if set(dispositions) != set(members) or len(dispositions) != len(row['member_dispositions']):
            issues.append(f'{gid}: dispositions do not cover each member exactly once.')
        topic_of = Counter(mid for t in row['topics'] for mid in t['member_ids'])
        for mid, d in dispositions.items():
            expected = {'ASSIGNED': topic_of[mid] == 1, 'REJECTED': mid in row['rejected_member_ids'] and not topic_of[mid],
                        'UNASSIGNED': mid in row['unassigned_member_ids'] and not topic_of[mid]}.get(d['disposition'], False)
            if not expected:
                issues.append(f"{gid}: member {mid} disposition {d['disposition']} is inconsistent.")
        flagged = {mid for mid, m in members.items() if m['agent1_record']['review_required']}
        inherited = [o['member_id'] for o in row['inherited_review_obligations']]
        if sorted(inherited) != sorted(flagged):
            issues.append(f'{gid}: inherited obligations differ from review-required members.')
    issues += [f'Member {mid} appears {n} times.' for mid, n in seen.items() if n != 1]
    return issues, len(seen)


def load_effective_view(run_dir):
    """Effective view plus a projection's own carried-caution supplement, if hash-valid."""
    from threadsense.agents.topic_effective import load_effective_output
    run, extra = Path(run_dir).resolve(), ()
    if (run/'projection_manifest.json').is_file():
        manifest = read_json(run/'projection_manifest.json')
        path = ROOT/manifest['carried_review_supplement']
        if file_hash(path) != manifest['carried_review_supplement_sha256']:
            raise ValueError('Carried review supplement changed since projection.')
        extra = (path,)
    return load_effective_output(run, additional_supplements=extra)


def inspect_handoff(run_dir=None):
    """Report the active export gap or the inspected run's accounting; never substitutes runs."""
    exports = find_exports()
    active = [e for e in exports if 8 in e['schema_versions']]
    report = {'code_contract': code_contract(), 'agent2_exports_in_repository': exports,
              'active_schema8_exports': [e['run'] for e in active],
              'active_export_status': 'FOUND' if active else 'UNAVAILABLE'}
    if run_dir is None:
        return report
    run = Path(run_dir).resolve()
    inspected = {'run': run.relative_to(ROOT).as_posix() if run.is_relative_to(ROOT) else str(run),
                 'registry': registry_status(run)}
    report['inspected_run'] = inspected
    try:
        view = load_effective_view(run)
    except (ValueError, OSError, KeyError) as error:
        inspected['error'] = f'{type(error).__name__}: {error}'
        return report
    if (run/'projection_manifest.json').is_file():
        manifest = read_json(run/'projection_manifest.json')
        inspected['projection'] = {k: manifest[k] for k in (
            'projection_version', 'fresh_taxonomy_run', 'source_release', 'source_handoff_contract', 'group_methods',
            'carried_naming_cautions', 'unresolved_naming_cautions')}
    if (run/'routing_manifest.json').is_file():
        sources = read_json(run/'routing_manifest.json')['announcement_sources']
        inspected['announcement_route'] = {
            'members': len(sources), 'inherited_agent1_obligations': sum(m['agent1_record']['review_required'] for m in sources)}
    versions = sorted({r.get('schema_version') for r in view['records']})
    contracts = sorted({r['taxonomy_handoff']['contract_version'] for r in view['records'] if 'taxonomy_handoff' in r})
    issues, members = accounting_issues(view)
    dispositions = Counter(d['disposition'] for r in view['records'] for d in r['member_dispositions'])
    inspected.update({
        'schema_versions': versions, 'handoff_contracts': contracts,
        'matches_current_code_contract': contracts == [report['code_contract']['handoff_contract']],
        'groups': len(view['records']), 'topics': sum(len(r['topics']) for r in view['records']),
        'members': members, 'member_dispositions': dict(sorted(dispositions.items())),
        'inherited_agent1_obligations': len(view['member_review_queue']),
        'agent2_obligations': sum(len(r.get('agent2_review_obligations', [])) for r in view['records']),
        'applied_content_obligations': len(view['applied_content_obligations']),
        'unapplied_findings': len(view['unapplied_findings']),
        'review_binding_status': view['review_binding_status'],
        'effective_review_groups': len(view['review_queue']), 'accounting_issues': issues})
    return report


def review_items_from_view(view):
    """One ModelReviewItem per upstream obligation, each keeping a verbatim source copy."""
    items = []
    for row in view['records']:
        base = {'project_id': row['project_id'], 'batch_id': row.get('batch_id'), 'candidate_group_id': row['candidate_group_id']}
        topic_of = {mid: t['topic_id'] for t in row['topics'] for mid in t['member_ids']}
        for o in row.get('inherited_review_obligations', []):
            items.append({**base, 'origin': 'agent1', 'kind': 'inherited_agent1_review', 'member_ids': [o['member_id']],
                          'topic_id': topic_of.get(o['member_id']),
                          'reason': o['agent1_record'].get('review_reason') or 'Inherited Agent 1 review obligation.',
                          'source_obligation': o})
        for o in row.get('agent2_review_obligations', []):
            items.append({**base, 'origin': 'agent2', 'kind': o['kind'], 'member_ids': list(o.get('member_ids', [])),
                          'reason': f"Agent 2 {o['kind']}.", 'source_obligation': o})
        for o in row.get('content_review_obligations', []):
            finding = o.get('finding') or {}
            items.append({**base, 'origin': 'assisted_content_review', 'kind': 'assisted_content_review',
                          'obligation_id': o['obligation_id'],
                          'reason': str(finding.get('summary') or finding.get('issue') or finding)[:2000],
                          'source_obligation': o})
    return [ModelReviewItem(item_id=stable_id('review', {k: item.get(k) for k in (
        'origin', 'kind', 'candidate_group_id', 'member_ids', 'obligation_id')}), **item) for item in items]


def review_items_from_announcement_route(sources):
    """Agent 1 obligations on announcement members routed out of Agent 2 groups."""
    return [ModelReviewItem(
        item_id=stable_id('review', {'origin': 'agent1', 'route': 'announcement', 'member_id': m['member_id']}),
        origin='agent1', kind='inherited_agent1_review_announcement_route', project_id=m['project_id'],
        batch_id=m.get('batch_id'), candidate_group_id='announcement_route', member_ids=[m['member_id']],
        reason=m['agent1_record'].get('review_reason') or 'Inherited Agent 1 review obligation.', source_obligation=m)
        for m in sources if m['agent1_record']['review_required']]


def obligation_keys(view):
    keys = set()
    for row in view['records']:
        keys |= {('agent1', o['member_id']) for o in row.get('inherited_review_obligations', [])}
        keys |= {('agent2', row['candidate_group_id'], o['kind']) for o in row.get('agent2_review_obligations', [])}
        keys |= {('content', o['obligation_id']) for o in row.get('content_review_obligations', [])}
    return keys


def coverage(view, cards=(), review_items=()):
    """Members and obligations not carried by any card lineage, inherited flag or review item."""
    members = {m['member_id'] for row in view['records'] for m in row['members']}
    carried_members, carried = set(), set()
    for card in cards:
        carried_members |= set(card.lineage.member_ids)
        for flag in card.inherited_flags:
            carried |= _keys(flag.origin, flag.candidate_group_id, flag.kind, flag.member_ids, flag.obligation_id)
    for item in review_items:
        carried_members |= set(item.member_ids)
        carried |= _keys(item.origin, item.candidate_group_id, item.kind, item.member_ids, item.obligation_id)
    return {'missing_members': sorted(members - carried_members),
            'missing_obligations': sorted(map(list, obligation_keys(view) - carried))}


def _keys(origin, gid, kind, member_ids, obligation_id):
    if origin == 'agent1':
        return {('agent1', mid) for mid in member_ids}
    if origin == 'agent2':
        return {('agent2', gid, kind)}
    return {('content', obligation_id)} if obligation_id else set()


def _messages(thread):
    for m in thread.get('messages', []):
        yield m.get('ts', m.get('message_id')), m.get('user', m.get('author_id'))


def structural_occurrence(threads, *, computed_from):
    """Mechanical counts only. Affected reporters/tasks stay UNKNOWN for semantic review."""
    seen_threads, seen_messages, participants, times, refs = set(), set(), set(), [], []
    duplicate_threads = duplicate_messages = 0
    for thread in threads:
        key = (thread['channel_id'], thread['thread_id'])
        if key in seen_threads:
            duplicate_threads += 1
            continue
        seen_threads.add(key)
        refs.append({k: thread.get(k) for k in ('project_id', 'batch_id', 'channel_id', 'thread_id', 'member_id')})
        for ts, user in _messages(thread):
            if (thread['channel_id'], ts) in seen_messages:
                duplicate_messages += 1
                continue
            seen_messages.add((thread['channel_id'], ts))
            participants.add(user)
            times.append(slack_datetime(ts))
    return OccurrenceEvidence(relevant_threads=refs, reporting_window={
        'start': min(times).isoformat(), 'end': max(times).isoformat()} if times else None,
        structural={'threads': len(seen_threads), 'messages': len(seen_messages),
                    'distinct_participants': len(participants - {None}),
                    'duplicate_threads_ignored': duplicate_threads, 'duplicate_messages_ignored': duplicate_messages,
                    'computed_from': computed_from})


# Recorded authoring statuses -> contract states. Unknown values fail loudly.
TL_OUTCOMES = {'tl_approved': 'APPROVED', 'tl_rejected': 'REJECTED', 'tl_deferred': 'DEFERRED', 'tl_overridden': 'OVERRIDDEN'}
TL_RESPONSE_OUTCOMES = {'approved': 'APPROVED', 'approved_with_edits': 'APPROVED_WITH_EDITS',
                        'rejected': 'REJECTED', 'deferred': 'DEFERRED', 'overridden': 'OVERRIDDEN'}
EXECUTION_STATES = {
    'not_yet_executed': 'NOT_EXECUTED', 'not_executed': 'NOT_EXECUTED', 'pending_scheduling': 'PENDING',
    'pending_post': 'PENDING', 'pending_document_updates': 'PENDING', 'evidence_requested': 'PENDING',
    'routed': 'IN_PROGRESS', 'handoff_recorded': 'IN_PROGRESS', 'assessment_recorded': 'COMPLETED',
    'review_recorded': 'COMPLETED', 'posted': 'COMPLETED', 'trial_completed': 'COMPLETED',
    'diagnostic_completed': 'COMPLETED', 'calibration_completed': 'COMPLETED',
    'fix_verified_in_sample': 'COMPLETED', 'partially_completed': 'PARTIALLY_COMPLETED'}
OUTCOME_STATES = {
    'not_observed': 'NOT_OBSERVED', 'open': 'OPEN', 'pending_expert_review': 'OPEN', 'awaiting_context': 'OPEN',
    'stale_copy_remains': 'OPEN', 'undetermined': 'UNDETERMINED', 'improved_in_sample': 'IMPROVED',
    'unsuccessful_in_sample': 'UNSUCCESSFUL', 'resolved_for_scoped_case': 'RESOLVED',
    'resolved_in_checked_tasks': 'RESOLVED', 'resolved_in_checked_rows': 'RESOLVED',
    'resolved_by_record_reconciliation': 'RESOLVED', 'no_operational_issue_for_case': 'NO_ISSUE_FOUND',
    'no_policy_change': 'NO_CHANGE'}
DECISION_KINDS = {'advice_review', 'expert_referral', 'expert_review', 'escalation_receipt'}


def _state(table, value, field):
    if value not in table:
        raise ValueError(f'Unmapped {field} {value!r}; add an explicit mapping.')
    return table[value]


def decision_record_from_source(record):
    """Historical TL decision (advice_review/referral/expert review/escalation) -> DecisionRecord."""
    front = record.source_metadata['authoring']
    if front.get('record_kind') not in DECISION_KINDS:
        raise ValueError('Only TL decision records map to DecisionRecord; follow-ups and posts stay sources.')
    outcome = _state(TL_OUTCOMES, front['decision_status'], 'decision_status')
    response = front.get('tl_response') or {}
    if response:
        stated = _state(TL_RESPONSE_OUTCOMES, response['outcome'], 'tl_response.outcome')
        if stated.split('_WITH_')[0] != outcome:
            raise ValueError('tl_response outcome disagrees with decision_status.')
        outcome = stated
    actions = front.get('approved_actions') or ([front['approved_action']] if front.get('approved_action') else [])
    advice, override = front.get('originating_advice'), front.get('severity_override')
    source = EvidenceRef(kind='knowledge_source', project_id=record.source.project_id, batch_id=record.source.batch_id,
                         scope=record.scope, document_id=record.record_id, version_id=record.version_id,
                         authoring_document_id=front['document_id'], authoring_version=front['version'])
    return DecisionRecord(
        decision_id=front.get('decision_id') or front['document_id'], project_id=front['project_id'],
        batch_id=front.get('batch_id'), event_series_id=front.get('event_series_id'),
        original_advice=None if advice is None else {**advice, 'proposed_severity': (override or {}).get('proposed')},
        tl_response={'outcome': outcome, 'actor_id': response.get('actor_id') or record.authority.get('actor_id'),
                     'actor_role': record.authority.get('recorded_role'), 'reviewed_at': response.get('reviewed_at'),
                     'text': response.get('text'), 'approved_actions': actions, 'severity_override': override},
        execution={'state': _state(EXECUTION_STATES, front['execution_status'], 'execution_status'),
                   'source_status': front['execution_status']},
        outcome={'state': _state(OUTCOME_STATES, front['outcome_status'], 'outcome_status'),
                 'source_status': front['outcome_status']},
        applicability=front.get('applicability') or front.get('applicability_note'),
        valid_until=front.get('valid_until'), review_due_at=front.get('review_due_at'), source=source)
