"""Agent 2 candidates joined directly to the finalized canonical handoff."""
from copy import deepcopy
from pathlib import Path
from threadsense.handoff_inputs import (
    CANONICAL, GROUPING, load_handoff, read_json, file_hash, identity, review_provenance,
)

def load_candidate_payloads(grouping_path=GROUPING, canonical_path=CANONICAL):
    members = load_handoff(canonical_path)
    by_key = {identity(m):m for m in members}
    grouping = read_json(grouping_path)
    if grouping.get('format_version') != 2 or grouping['input_sha256'] != file_hash(canonical_path):
        raise ValueError('Grouping is stale or uses the legacy handoff. Refresh candidates from finalized input.')
    if grouping['review_evidence'] != review_provenance():
        raise ValueError('Grouping review provenance differs from the saved registries.')
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
    return payloads
