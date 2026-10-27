"""Read-only, taxonomy-scoped inspection of saved v7 output and canonical input."""
import json
from pathlib import Path
import sys

rows = []
for name in ('agent2_taxonomy_pilot_v7', 'agent2_taxonomy_remaining_v7'):
    for file in (Path('data/processed') / name / 'records').glob('*/result.json'):
        r = json.loads(file.read_text(encoding='utf-8'))
        if r['project_id'] != sys.argv[1]:
            continue
        indices = {m['member_id']: i + 1 for i, m in enumerate(r['members'])}
        rows.append(dict(group=r['candidate_group_id'], state=r['processing_state'],
            flags=len(r['inherited_review_obligations']),
            topics=[dict(name=t['topic_name'], members=[indices[x] for x in t['member_ids']],
                         rationale=t['rationale']) for t in r['topics']],
            rejected=[indices[x] for x in r['rejected_member_ids']],
            canonical=[dict(m=i+1, summary=m['agent1_record']['interpretation']['summary'],
                            question=m['agent1_record']['interpretation']['central_question'])
                       for i,m in enumerate(r['members'])]))
rows.sort(key=lambda r:r['group'])
for r in rows[int(sys.argv[2]):int(sys.argv[3])]:
    print(json.dumps(r, ensure_ascii=False))
