"""One-off converter: threadsense_fresh_15_v1 portable JSON -> this repository's Slack fixture and knowledge Markdown.

Reads source/threadsense_fresh_15_fixture.json only (never the answer key) and writes:
  inputs/slack/users.json, inputs/slack/channels/<channel>.json   (adapters/mock_slack.py format)
  inputs/knowledge/{instructions,faq}/*.md                        (mock-knowledge-markdown-v1, knowledge_markdown.py)
  id_map.json                                                     T01-T15 and PILOT-K01-K06 -> runtime IDs

Source text, user roles, timestamps, projects, batches, channel types and reactions are copied unchanged. Two mapping
choices are forced by the existing loaders and recorded in id_map.json:
  - channel IDs gain a "C_" prefix (every loader selects channels/C_*.json);
  - knowledge dates become midnight UTC timestamps (effective_at needs a time).
Refuses to overwrite existing outputs.

    uv run --locked python experiments/fresh_15_v1/convert_fixture.py
"""
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE/'source/threadsense_fresh_15_fixture.json'
SLACK, KNOWLEDGE, ID_MAP = HERE/'inputs/slack', HERE/'inputs/knowledge', HERE/'id_map.json'
# One logical document per title; the two alignment-guide versions share an identity.
DOCUMENT_IDS = {'Audio incident triage': 'pilot-audio-incident-triage',
                'Media-input quality FAQ': 'pilot-media-input-quality-faq',
                'Multilingual alignment review guide': 'pilot-multilingual-alignment-review-guide',
                'Response preference scoring guide': 'pilot-response-preference-scoring-guide',
                'Review export troubleshooting': 'pilot-review-export-troubleshooting'}
TYPES = {'instruction': 'instructions', 'faq': 'faq'}


def runtime_channel(channel_id):
    return channel_id if channel_id.startswith('C_') else f'C_{channel_id[1:]}'


def message(raw, channel_id, root, reply_count):
    out = {'ts': raw['ts'], 'user': raw['user_id'], 'text': raw['text'], 'source': 'USER',
           'reactions': [{'name': r['name'], 'users': list(r['user_ids']), 'count': len(r['user_ids'])}
                         for r in raw.get('reactions') or []]}
    if root:
        out['reply_count'] = reply_count
    else:
        out['thread_ts'] = raw['thread_ts']
    return out


def markdown(doc, fixture_id):
    document_id = DOCUMENT_IDS[doc['title']]
    effective = f"{doc['effective_from']}T00:00:00Z"
    front = [
        '---', 'authoring_schema: mock-knowledge-markdown-v1', f'document_id: {document_id}',
        f"document_type: {TYPES[doc['kind']]}", f"project_id: {doc['project_id']}", 'scope: project', 'batch_id: null',
        f"version: '{doc['version']}'", f"effective_at: '{effective}'", f"last_updated: '{effective}'", 'status: approved',
        'authority:', '  approved_by: fixture', '  role: TEAM_LEAD', '  provenance: synthetic_fixture_record',
        'source:', '  system: manual', f'  manual_key: {document_id}', 'synthetic: true',
        f'fixture_id: {fixture_id}', f"fixture_source_id: {doc['source_id']}",
        f"fixture_superseded_on: {json.dumps(doc['superseded_on'])}", '---', '']
    body = [f"# {doc['title']} (v{doc['version']})", '', f"## {doc['section']}", doc['text'], '']
    return '\n'.join(front + body), document_id


def main():
    if any(p.exists() for p in (SLACK, KNOWLEDGE, ID_MAP)):
        sys.exit('Outputs exist; this converter never overwrites (delete them deliberately to regenerate).')
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    channels = {c['channel_id']: c for c in data['channels']}
    (SLACK/'channels').mkdir(parents=True)
    users = [{'id': u['user_id'], 'name': u['name'], 'role': u['role']} for u in data['users']]
    (SLACK/'users.json').write_text(json.dumps({'users': users}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    by_channel, threads = {}, {}
    for t in data['threads']:
        msgs = sorted(t['messages'], key=lambda m: float(m['ts']))
        assert msgs[0]['ts'] == t['thread_ts'] and all(m['thread_ts'] == t['thread_ts'] for m in msgs)
        cid = runtime_channel(t['channel_id'])
        slot = by_channel.setdefault(cid, {'history': [], 'replies': {}})
        root = message(msgs[0], cid, True, len(msgs) - 1)
        slot['history'].append(root)
        if len(msgs) > 1:
            slot['replies'][t['thread_ts']] = [message(msgs[0], cid, False, 0) | {'reply_count': len(msgs) - 1}] + [
                message(m, cid, False, 0) for m in msgs[1:]]
        threads[t['fixture_thread_id']] = {'channel_id': cid, 'fixture_channel_id': t['channel_id'],
                                           'thread_id': t['thread_ts'], 'messages': [m['ts'] for m in msgs],
                                           'channel_type': channels[t['channel_id']]['channel_type']}
    for fid, ch in channels.items():
        cid = runtime_channel(fid)
        slot = by_channel.get(cid, {'history': [], 'replies': {}})
        slot['history'].sort(key=lambda m: -float(m['ts']))  # Newest first, as Slack history pages are.
        out = {'channel': {'id': cid, 'name': ch['name'], 'project_id': ch['project_id'], 'batch_id': ch['batch_id'],
                           'channel_type': ch['channel_type']}, **slot}
        (SLACK/'channels'/f'{cid}.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    knowledge = {}
    for doc in data['knowledge_documents']:
        text, document_id = markdown(doc, data['fixture_id'])
        name = f"{document_id}_v{doc['version']}.md"
        path = KNOWLEDGE/TYPES[doc['kind']]/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        knowledge[doc['source_id']] = {'document_id': document_id, 'version': doc['version'],
                                       'file': path.relative_to(HERE).as_posix(), 'section': doc['section'],
                                       'effective_at': f"{doc['effective_from']}T00:00:00Z", 'superseded_on': doc['superseded_on'],
                                       'runtime_evidence_id': 'assigned at index build: k:<document_id>@<version>:<hash>'}
    id_map = {'fixture_id': data['fixture_id'], 'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
              'snapshot': data['snapshot'], 'cutoff': data['snapshot']['cutoff_exclusive'],
              'channels': {fid: runtime_channel(fid) for fid in channels}, 'threads': threads, 'knowledge': knowledge,
              'mapping_choices': ['channel IDs gain a C_ prefix: every loader selects channels/C_*.json',
                                  'thread and message IDs are the fixture timestamps, unchanged',
                                  'knowledge dates become midnight UTC (effective_at needs a timestamp)',
                                  'PILOT-K03 and PILOT-K04 share document_id pilot-multilingual-alignment-review-guide; '
                                  'ordering by effective_at makes v2.0 current and v1.4 a superseded revision from 2026-10-14',
                                  'archive applicability of v1.4 (multi_batch_09 exports) has no structured field; it stays in '
                                  'the source text of both versions and of T15']}
    ID_MAP.write_text(json.dumps(id_map, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'channels': len(channels), 'threads': len(threads), 'knowledge_documents': len(knowledge)}))


if __name__ == '__main__':
    main()
