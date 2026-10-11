"""Verify generated Slack fixtures against hidden ThreadSense blueprint.

Run: python scripts/validate_slack_fixtures.py

This script may read hidden evaluation labels. The application/agents MUST NOT.
"""
from collections import Counter
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / 'data/evaluation/thread_blueprint_200.json'
GENERATED = ROOT / 'data/fixtures/slack_generated'
CHANNELS = GENERATED / 'channels'


def get(path):
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}. Run the generator from Step 24 first.')
    return json.loads(path.read_text(encoding='utf-8'))


def user_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('users'), list):
        return data['users']
    if isinstance(data, dict) and isinstance(data.get('users'), dict):
        return [dict(v, id=k) for k, v in data['users'].items()]
    return [dict(v, id=k) for k, v in data.items()]


def main():
    blueprint = get(BP)
    user_ids = {str(u['id']) for u in user_list(get(GENERATED / 'users.json'))}
    assert len(blueprint) == 200, 'Expected 200 blueprint records'
    expected = {r['thread_id']: r for r in blueprint}
    assert len(expected) == 200, 'Duplicate blueprint thread IDs'
    files = sorted(CHANNELS.glob('C_*.json'))
    assert len(files) == 12, f'Expected 12 channel files, found {len(files)}'

    observed = {}
    replies_count = 0
    text_counts = Counter()
    for file in files:
        d = get(file)
        ch = d['channel']
        assert ch['id'] == file.stem, f'File/channel mismatch: {file}'
        assert ch['channel_type'] in {'GENERAL','QA','ANNOUNCEMENTS'}
        assert isinstance(d['history'], list) and isinstance(d['replies'], dict)
        for root in d['history']:
            tid = str(root['ts'])
            assert tid not in observed, f'Duplicate root {tid}'
            assert tid in expected, f'Unexpected root {tid}'
            target = expected[tid]
            assert target['channel_id'] == ch['id'], f'Wrong channel: {tid}'
            assert target['project_id'] == ch['project_id'], f'Wrong project: {tid}'
            assert target['batch_id'] == ch['batch_id'], f'Wrong batch: {tid}'
            assert str(root['user']) in user_ids, f'Unknown author: {tid}'
            assert isinstance(root['text'], str) and root['text'].strip(), f'Empty root: {tid}'
            assert root.get('source','USER') in {'USER','WORKFLOW','BOT'}, f'Invalid source: {tid}'
            if target.get('language'):
                assert root.get('language') == target['language'], f'Language lost: {tid}'
            text_counts[root['text']] += 1
            messages = d['replies'].get(tid, [])
            n = int(root.get('reply_count',0))
            if messages:
                assert messages[0] == root, f'Replies first item differs from root: {tid}'
                assert len(messages)-1 == n, f'Reply count mismatch: {tid}'
                assert [float(m['ts']) for m in messages] == sorted(float(m['ts']) for m in messages), f'Nonchronological replies: {tid}'
            else:
                assert n == 0, f'Missing replies for {tid}'
            for m in messages[1:]:
                assert str(m['user']) in user_ids, f'Unknown reply author: {tid}'
                assert str(m.get('thread_ts', tid)) == tid, f'Wrong thread pointer: {tid}'
                assert isinstance(m.get('text'),str) and m['text'].strip(), f'Empty reply in {tid}'
                assert float(m['ts']) > float(tid), f'Nonpositive reply time in {tid}'
            replies_count += n
            observed[tid] = target
        assert set(d['replies']).issubset({str(r['ts']) for r in d['history']}), f'Orphan replies in {file}'

    assert set(observed) == set(expected), f'Missing={set(expected)-set(observed)}; extra={set(observed)-set(expected)}'
    print('PASS: all 200 thread IDs, roles, channels, batch IDs, and replies validated')
    print('Project counts:', dict(Counter(r['project_id'] for r in observed.values())))
    print('Resolution targets:', dict(Counter(r['resolution_state'] for r in observed.values())))
    print(f'Channels: {len(files)} | Users: {len(user_ids)} | Replies: {replies_count}')
    dupes = sum(n-1 for n in text_counts.values() if n > 1)
    print(f'Exact repeated root texts: {dupes} (review if high)')
    # Sanity check that the private metadata wasn't accidentally attached to input messages.
    for file in files:
        raw = file.read_text(encoding='utf-8')
        for key in ('latent_topic', 'expected_action', 'temporal_case', 'resolution_state', 'expected_evidence_sources'):
            assert not re.search(r'"' + key + r'"\s*:', raw), f'Hidden field leaked in {file}: {key}'
    print('PASS: hidden ground-truth fields excluded from Slack fixtures')


if __name__ == '__main__':
    main()
