"""Rebuild one topic's revision request from a saved overnight run and count it exactly, zero model calls.

The recorded draft is replayed through the current Advisor (same snapshot, same retrieval expansion setting, so the
same follow-up research runs). When the revision stage is reached, its task is built by the live CrewAI client with
the run's recorded settings and sent to a fake transport inside this process (outbound sockets refused, dummy key):
the captured HTTP body is counted with RequestGuard's own rule (o200k_base per message + 8). Nothing is sent and the
input-token limit is not changed; the count is compared with it. Also reports what each part of the request costs.

  uv run --locked python scripts/measure_revision_request.py --run data/experiments/agent3_summary_eval_v1 \
      --work gap:routed_440e64c7fbdcc49f [--write <new path>]
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys


class Captured(Exception):
    """The revision request was captured; the replay records it as a failed stage (nothing generated)."""


def exact_request(payload, schema, settings):
    """The HTTP body the live client would send for this stage, captured at the transport (never sent)."""
    import httpx
    from threadsense.agents import advisor_pilot as pilot
    body, connect = {}, socket.socket.connect

    def refuse(sock, address, *args, **kwargs):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            raise OSError(f'network blocked while measuring: {address[0]}')
        return connect(sock, address, *args, **kwargs)

    def capture(transport, request):
        body.update(json.loads(request.content))
        raise Captured()
    original, key = httpx.HTTPTransport.handle_request, os.environ.get('OPENAI_API_KEY')
    socket.socket.connect, httpx.HTTPTransport.handle_request = refuse, capture
    os.environ['OPENAI_API_KEY'] = 'sk-offline-measurement'  # Never the real key: nothing leaves the process.
    try:
        client = pilot.CrewAIClient({**settings, 'input_token_limit': None})
        try:
            client.complete('revision', payload, schema)
        except Exception:  # noqa: BLE001 - the capture ends the call by design
            pass
    finally:
        socket.socket.connect, httpx.HTTPTransport.handle_request = connect, original
        if key is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = key
    if not body:
        raise RuntimeError('No request reached the transport.')
    return body


def count(messages):
    """RequestGuard's count of an HTTP body's messages."""
    from threadsense.agents.advisor_pilot import estimate_tokens
    return sum(estimate_tokens(m['content'] if isinstance(m.get('content'), str) else json.dumps(m.get('content'))) + 8
               for m in messages)


def breakdown(payload, schema, messages):
    """Tokens per part. Payload parts are counted as serialized in the task text; overhead is the rest of the body."""
    from threadsense.agents.advisor_pilot import estimate_tokens, task_description
    tok = lambda value: estimate_tokens(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))  # noqa: E731
    parts = {'instructions (rules)': tok(payload['rules']), 'output schema': tok(payload['output_schema'])}
    groups = {'member threads': ['member_evidence'], 'retrieved evidence': ['retrieved_evidence'],
              'prior draft': ['previous_draft'], 'follow-up results': ['follow_ups'],
              'retrieval notes': ['retrieval_notes'], 'rubric': ['rubric'], 'agent 1 interpretations': ['agent1_interpretations'],
              'topic and limits': ['topic', 'limits', 'scenario_id', 'stage']}
    for name, keys in groups.items():
        parts[name] = sum(tok(payload[k]) for k in keys if k in payload)
    task = estimate_tokens(task_description(payload, schema))
    total = count(messages)
    parts['framework (system prompt, task wrapper, message overhead)'] = total - task + (task - sum(parts.values()))
    retrieved = payload.get('retrieved_evidence') or []
    excerpts = sum(tok(i.get('excerpt') or '') for i in retrieved)
    detail = {'retrieved items': len(retrieved), 'retrieved excerpt text': excerpts,
              'retrieved metadata (citation, applicability, states, ids)': parts['retrieved evidence'] - excerpts,
              'member messages': len(payload.get('member_evidence') or []),
              'member excerpt text': sum(tok(i.get('excerpt') or '') for i in payload.get('member_evidence') or [])}
    return total, parts, detail


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--write', type=Path, help='New path for the JSON report (includes the captured body).')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    report = measure(args.run, args.work)
    print(json.dumps({k: v for k, v in report.items() if k != 'body'}, ensure_ascii=False, indent=1))
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0


def measure(run, work):
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    from threadsense.agents import overnight
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import Budget
    from threadsense.handoff_inputs import ROOT, read_json
    from threadsense.severity_rubric import load_rubric
    manifest = read_json(Path(run)/'run_manifest.json')
    fingerprints = manifest['fingerprints']
    settings = fingerprints['semantic_client']['settings']
    retriever = overnight.open_snapshot(ROOT/(fingerprints['index'].get('index_dir') or '.index/retrieval'))
    if retriever.manifest['build_fingerprint'] != fingerprints['index']['build_fingerprint']:
        raise SystemExit('The recorded snapshot is no longer the one at that path.')
    view = load_effective_view(ROOT/fingerprints['handoff']['run'])
    item = next(w for w in overnight.plan(view) if w['work_id'] == work)
    scenario = {'id': work, 'candidate_group_id': item['candidate_group_id'], 'focus': item['topic_name'] or 'projection gap',
                **({'topic_id': item['topic_id']} if item['topic_id'] else {})}
    seen = {}

    class Measuring(pilot.ReplayClient):
        def complete(self, stage, payload, schema):
            if stage == 'revision' and not seen:
                seen.update(payload=payload, schema=schema)
                raise pilot.RecordedFailure('RESOURCE', 'measured offline; not sent')
            return super().complete(stage, payload, schema)
    pilot.advise(scenario, view=view, retriever=retriever, client=Measuring(run), budget=Budget(overnight.PER_TOPIC),
                 rubric=load_rubric(None), run_id=manifest['run_id'], as_of=retriever.manifest['cutoff'])
    if not seen:
        return {'run': str(run), 'work_id': work, 'revision_requested': False}
    body = exact_request(seen['payload'], seen['schema'], settings)
    total, parts, detail = breakdown(seen['payload'], seen['schema'], body['messages'])
    limit = settings['input_token_limit']
    return {'run': str(run), 'work_id': work, 'revision_requested': True, 'prompt_version': pilot.PROMPT_VERSION,
            'counter': 'RequestGuard: o200k_base per message + 8', 'input_tokens': total, 'input_token_limit': limit,
            'headroom': limit - total, 'fits': total <= limit, 'parts': parts, 'detail': detail,
            'messages': [{'role': m['role'], 'tokens': count([m])} for m in body['messages']], 'body': body}


if __name__ == '__main__':
    sys.exit(main())
