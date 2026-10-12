"""Step 24 — verify generated Slack fixtures against hidden ThreadSense blueprint.

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
SEED_CHANNELS = ROOT / 'data/fixtures/slack/channels'


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
    # The original hand-authored fixtures may have emoji counts but no reactor IDs.
    # Only those known seed threads may use legacy, unattributed reactions.
    seed_thread_ids = {
        str(root['ts'])
        for seed_file in SEED_CHANNELS.glob('*.json')
        for root in get(seed_file)['history']
    }
    assert len(expected) == 200, 'Duplicate blueprint thread IDs'
    files = sorted(CHANNELS.glob('C_*.json'))
    assert len(files) == 12, f'Expected 12 channel files, found {len(files)}'

    observed = {}
    replies_count = 0
    text_counts = Counter()
    root_snapshot_differences = 0
    structured_reactions = 0
    legacy_unattributed_reactions = 0
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
                # Slack history and replies return separate snapshots of the root.
                # Metadata (e.g., reply_count, thread_ts, reactions) can differ;
                # stable message identity and content must still agree.
                reply_root = messages[0]
                for field in ('ts', 'user', 'text'):
                    assert str(reply_root.get(field)) == str(root.get(field)), (
                        f'Root mismatch for {tid}, field={field}: '
                        f'history={root.get(field)!r}, replies={reply_root.get(field)!r}'
                    )
                if reply_root != root:
                    root_snapshot_differences += 1
                assert len(messages)-1 == n, f'Reply count mismatch: {tid}'
                assert [float(m['ts']) for m in messages] == sorted(float(m['ts']) for m in messages), f'Nonchronological replies: {tid}'
            else:
                assert n == 0, f'Missing replies for {tid}'
            # Verify reactor attribution without requiring historical seed
            # messages to use the new structured reaction format.
            for m in [root] + messages:
                for reaction in m.get('reactions', []):
                    if isinstance(reaction, str):
                        continue  # Legacy samples may still contain emoji strings.
                    assert isinstance(reaction, dict), f'Invalid reaction: {tid}'
                    assert isinstance(reaction.get('name'), str) and reaction['name'], f'Reaction missing name: {tid}'
                    reactors = reaction.get('users')
                    count = reaction.get('count')
                    is_seed = tid in seed_thread_ids
                    if reactors is None:
                        # Legacy seed reactions may omit both users and count.
                        # Missing attribution is unknown, NEVER a TL endorsement.
                        assert is_seed, f'Generated reaction missing users: {tid} {reaction!r}'
                        if count is not None:
                            assert type(count) is int and count >= 0, (
                                f'Invalid legacy reaction count: {tid} {reaction!r}'
                            )
                        legacy_unattributed_reactions += 1
                        continue
                    assert isinstance(reactors, list), f'Reaction users must be a list: {tid} {reaction!r}'
                    assert all(isinstance(uid, str) and uid in user_ids for uid in reactors), (
                        f'Unknown reactor: {tid} {reaction!r}'
                    )
                    assert len(set(reactors)) == len(reactors), f'Duplicate reactor: {tid} {reaction!r}'
                    if count is None:
                        # Also allow count to be omitted on manually written seed fixtures.
                        assert is_seed, f'Generated reaction missing count: {tid} {reaction!r}'
                    else:
                        assert type(count) is int and count >= len(reactors), (
                            f'Reaction count too small/invalid: {tid} {reaction!r}'
                        )
                        if not is_seed:
                            assert count == len(reactors), (
                                f'Generated reaction count mismatch: {tid} {reaction!r}'
                            )
                    structured_reactions += 1
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
    print(f'Root snapshot metadata differences: {root_snapshot_differences} (permitted when ID/author/text match)')
    print(f'Structured reactions: {structured_reactions}')
    print(f'Legacy unattributed reactions: {legacy_unattributed_reactions} (seed threads only)')
    # Sanity check that the private metadata wasn't accidentally attached to input messages.
    for file in files:
        raw = file.read_text(encoding='utf-8')
        for key in ('latent_topic', 'expected_action', 'temporal_case', 'resolution_state', 'expected_evidence_sources'):
            assert not re.search(r'"' + key + r'"\s*:', raw), f'Hidden field leaked in {file}: {key}'
    print('PASS: hidden ground-truth fields excluded from Slack fixtures')


if __name__ == '__main__':
    main()
