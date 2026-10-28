"""Agent 2 candidates joined directly to the finalized canonical handoff."""
from copy import deepcopy
from pathlib import Path
from threadsense.models import Thread
from threadsense.handoff_inputs import (
    CANONICAL, GROUPING, load_handoff, read_json, file_hash, identity, review_provenance, member_id, digest,
)


def routing_manifest_for_payloads(payloads):
    """Resolve and verify the complete partition before publishing projected groups."""
    from threadsense.routing import partition, digest
    marked = [p for p in payloads if p.get('routing_manifest')]
    if not marked:
        return None  # Explicit historical inputs have no prospective routing receipt.
    if len(marked) != len(payloads):
        raise ValueError('Mixed historical and prospective inputs.')
    paths = {m['agent1_export_file'] for p in payloads for m in p['members']}
    if len(paths) != 1:
        raise ValueError('Projected inputs require one canonical source partition.')
    _, _, routing = partition(load_handoff(next(iter(paths))))
    if any(p['routing_manifest']['sha256'] != digest(routing) for p in payloads):
        raise ValueError('Prospective routing receipt no longer matches canonical inputs.')
    return routing

def load_candidate_payloads(grouping_path=GROUPING, canonical_path=CANONICAL, *, historical=False):
    from threadsense.routing import partition, digest
    members = load_handoff(canonical_path)
    eligible, announcements, routing = partition(members) if not historical else (members,[],None)
    all_members = members
    by_key = {identity(m):m for m in members}
    grouping = read_json(grouping_path)
    if grouping.get('format_version') not in {2, 3} or grouping['input_sha256'] != file_hash(canonical_path):
        raise ValueError('Grouping is stale or uses the legacy handoff. Refresh candidates from finalized input.')
    if grouping['review_evidence'] != review_provenance():
        raise ValueError('Grouping review provenance differs from the saved registries.')
    if grouping['format_version']==3:
        if historical:eligible,announcements,routing=partition(members)
        if grouping.get('routing_manifest')!=routing:
            raise ValueError('Grouping routing manifest differs from the complete canonical partition.')
        members=eligible
        by_key={identity(m):m for m in members}
    payloads, assigned, group_ids = [], [], set()
    grouping_hash = file_hash(grouping_path)
    for group in grouping['clusters']:
        if group['cluster_id'] in group_ids:
            raise ValueError('Duplicate candidate group identity.')
        group_ids.add(group['cluster_id'])
        selected = []
        for row in group['threads']:
            key = identity(row)
            if key not in by_key or key in assigned:
                raise ValueError('Missing, invented, or duplicate grouped identity.')
            member = by_key[key]
            if (group['project_id'], group['batch_id']) != key[:2]:
                raise ValueError('Grouping crossed project/batch scope.')
            if row != member['agent1_record']:
                raise ValueError('Grouping member metadata differs from canonical export.')
            # Re-read canonical metadata and source; do not use grouping copies as truth.
            selected.append(deepcopy(member))
            assigned.append(key)
        if not selected:
            raise ValueError('Empty candidate group.')
        payloads.append({'schema_version':2, 'candidate_group_id':group['cluster_id'],
                         'project_id':group['project_id'], 'batch_id':group['batch_id'],
                         'members':selected, 'grouping_file':str(Path(grouping_path).resolve()),
                         'grouping_sha256':grouping_hash,
                         'review_evidence':deepcopy(grouping['review_evidence'])})
    if set(assigned) != set(by_key) or len(assigned) != grouping['thread_count']:
        raise ValueError('Grouping does not account for every canonical identity.')
    if len(payloads) != grouping['cluster_count'] or sum(m['agent1_record']['review_required'] for m in members) != grouping['review_member_count']:
        raise ValueError('Grouping counts or review obligations differ.')
    if historical:
        return payloads
    # Old exports can be inspected prospectively without new embeddings. This is
    # an explicit membership projection, not a fresh clustering or a frozen run.
    prospective=[]; eligible_ids={identity(m) for m in eligible}
    for p in payloads:
        selected=[m for m in p['members'] if identity(m) in eligible_ids]
        if not selected:continue
        p=deepcopy(p)
        original_id=p['candidate_group_id']
        if len(selected)!=len(p['members']):
            p['candidate_group_id']='routed_'+digest([original_id,[identity(m) for m in selected]])[:16]
        p['members']=selected
        p['routing_manifest']={'version':routing['routing_version'],'sha256':digest(routing),
            'input_threads':len(all_members),'eligible_threads':len(eligible),
            'announcement_threads':len(announcements),'parent_candidate_group_id':original_id,
            'selection_method':'existing_candidate_membership_projection' if grouping['format_version']==2 else 'routed_local_clustering'}
        prospective.append(p)
    actual=[identity(m) for p in prospective for m in p['members']]
    if len(actual)!=len(set(actual)) or set(actual)!=eligible_ids:
        raise ValueError('Prospective groups do not match the routing manifest eligibility set.')
    return prospective


def validate_input(payload):
    if payload.get('schema_version') != 2 or not payload.get('members'):
        raise ValueError('Expected a nonempty schema v2 canonical candidate.')
    seen = set()
    for member in payload['members']:
        key = identity(member)
        if key in seen or member['member_id'] != member_id(member):
            raise ValueError('Duplicate or mismatched full member identity.')
        seen.add(key)
        record, source = member['agent1_record'], member['original_thread']
        Thread.model_validate(source)
        if identity(record) != key or identity(source) != key:
            raise ValueError('Source/candidate/member identity mismatch.')
        if key[:2] != (payload['project_id'], payload['batch_id']):
            raise ValueError('Candidate crosses project/batch scope.')
        if digest(record['interpretation']) != record['candidate_sha256'] or digest(source) != record['input_sha256']:
            raise ValueError('Member candidate/source fingerprint mismatch.')
        ids = [m['message_id'] for m in source['messages']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate source message identity.')
    return payload['members']
