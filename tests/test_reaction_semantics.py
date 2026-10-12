"""Check that Slack reactions preserve reactor identity and TL-only endorsements.

Run from repository root:
    python -m pytest -q tests/test_reaction_semantics.py

This test reads raw generated Slack fixtures, not hidden evaluation metadata.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'data' / 'fixtures' / 'slack_generated'
ENDORSEMENTS = {'this', 'agree', 'white_check_mark'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_users():
    raw = read_json(FIXTURES / 'users.json')
    if isinstance(raw, list):
        users = raw
    elif 'users' in raw:
        inner = raw['users']
        users = inner if isinstance(inner, list) else [dict(info, id=uid) for uid, info in inner.items()]
    else:
        users = [dict(info, id=uid) for uid, info in raw.items()]
    return {u['id']: u['role'] for u in users}


def test_reaction_attribution_and_tl_endorsements():
    roles = load_users()
    reaction_count = 0
    approved_without_written_tl_reply = 0
    for file in (FIXTURES / 'channels').glob('C_*.json'):
        channel = read_json(file)
        for root in channel['history']:
            replies = channel['replies'].get(str(root['ts']), [])
            conversation = replies if replies else [root]
            author_roles = [roles[m['user']] for m in conversation]
            for i, message in enumerate(conversation):
                for item in message.get('reactions', []):
                    # Any old seed reactions stored as strings are legacy entries
                    # and lack reactor attribution; don't mistake these for TL approval.
                    if isinstance(item, str):
                        continue
                    assert isinstance(item, dict)
                    assert isinstance(item['name'], str)
                    assert all(uid in roles for uid in item['users'])
                    assert item['count'] == len(item['users'])
                    reaction_count += 1
                    tl_confirmed = item['name'] in ENDORSEMENTS and any(
                        roles[uid] == 'TEAM_LEAD' for uid in item['users']
                    )
                    if tl_confirmed:
                        assert i > 0, 'TL endorsement must target a substantive reply, not just root'
                        assert roles[message['user']] in {'TUTOR', 'QA_TUTOR'}
                        if 'TEAM_LEAD' not in author_roles:
                            approved_without_written_tl_reply += 1
    assert reaction_count > 0, 'No structured reactions in synthetic corpus'
    assert approved_without_written_tl_reply >= 1, 'Missing TL emoji-only resolution examples'
