"""Grok diagnosis probe (PAID, about $0.15 at most): why did every Agent 3 request in B_grok_v1 / B2_grok_agent3_v1 time
out with no response?

  1. tiny   one short request with the same settings (grok-4.7, reasoning_effort medium, json_object, temperature 0),
            max_tokens 300, not streamed: basic latency and whether the API answers at all
  2. real   the smallest saved B2 Agent 3 request body, byte-for-byte except stream=true (+ usage in the stream): when the
            first byte / first content token arrive, token rate, finish reason, reasoning tokens and the reported cost

Writes experiments/fresh_15_v1/diagnostics/<out>/probe.json (timings, usage, finish reasons) and the streamed content.
The key is read from .env and never printed or stored. Not part of either run's ledger.

    uv run --locked python experiments/fresh_15_v1/grok_probe.py --run [--model grok-4.7] [--effort medium] --out grok_probe_v1
"""
import argparse
import gzip
import http.client
import json
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
B2 = HERE/'runs/B2_grok_agent3_v1'
HOST, PATH = 'api.x.ai', '/v1/chat/completions'
READ_TIMEOUT = 1800  # per socket read; streaming keeps reads short once tokens flow


def key():
    from dotenv import dotenv_values
    k = (dotenv_values(ROOT/'.env', encoding='utf-8-sig').get('XAI_API_KEY') or '').strip()
    if not k.startswith('xai-'):
        raise SystemExit('XAI_API_KEY missing; nothing was sent.')
    return k


def smallest_b2_body():
    con = sqlite3.connect(f"file:{(B2/'ledger.sqlite3').as_posix()}?mode=ro", uri=True)
    shas = [r[0] for r in con.execute("select request_sha from requests where stage='agent3'")]
    con.close()
    bodies = []
    for sha in shas:
        path = next((B2/'objects').rglob(f'{sha}*'))
        raw = path.read_bytes()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        bodies.append((len(raw), sha, json.loads(raw)))
    return min(bodies, key=lambda b: b[0])


def post(body, k, stream, keepalive=False):
    c = http.client.HTTPSConnection(HOST, timeout=READ_TIMEOUT)
    if keepalive:  # TCP keepalive probes every 15 s while the socket is idle (Windows SIO_KEEPALIVE_VALS, else SO_KEEPALIVE).
        import socket
        c.connect()
        sock = c.sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 15000, 5000))
    t0 = time.perf_counter()
    c.request('POST', PATH, body=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {k}'})
    r = c.getresponse()
    first_byte = time.perf_counter() - t0
    out = {'http_status': r.status, 'seconds_to_headers': round(first_byte, 2)}
    if not stream:
        data = json.loads(r.read())
        out['seconds_total'] = round(time.perf_counter() - t0, 2)
        ch = (data.get('choices') or [{}])[0]
        out.update({'finish_reason': ch.get('finish_reason'), 'content': (ch.get('message') or {}).get('content'),
                    'usage': data.get('usage'), 'error': data.get('error') or data.get('code')})
        c.close()
        return out
    content, reasoning_chars, first_content, first_reasoning, finish, usage, events, last = [], 0, None, None, None, None, 0, None
    marks = []
    for line in r:
        line = line.strip()
        if not line.startswith(b'data:'):
            continue
        payload = line[5:].strip()
        if payload == b'[DONE]':
            break
        ev = json.loads(payload)
        events += 1
        now = time.perf_counter() - t0
        if ev.get('usage'):
            usage = ev['usage']
        for ch in ev.get('choices') or []:
            d = ch.get('delta') or {}
            if d.get('reasoning_content'):
                reasoning_chars += len(d['reasoning_content'])
                first_reasoning = first_reasoning or now
            if d.get('content'):
                content.append(d['content'])
                first_content = first_content or now
            finish = ch.get('finish_reason') or finish
        if last is None or now - last >= 60:
            last = now
            marks.append({'seconds': round(now, 1), 'events': events, 'content_chars': sum(map(len, content)),
                          'reasoning_chars': reasoning_chars})
            print(json.dumps(marks[-1]), flush=True)
    c.close()
    out.update({'seconds_total': round(time.perf_counter() - t0, 2), 'events': events,
                'seconds_to_first_reasoning_delta': round(first_reasoning, 2) if first_reasoning else None,
                'seconds_to_first_content_delta': round(first_content, 2) if first_content else None,
                'finish_reason': finish, 'usage': usage, 'content_chars': sum(map(len, content)),
                'reasoning_chars_streamed': reasoning_chars, 'progress': marks, 'content': ''.join(content)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--model', default='grok-4.7')
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--skip-tiny', action='store_true')
    ap.add_argument('--nonstream-keepalive', action='store_true',
                    help='Send the real request NOT streamed, with TCP keepalive (tests an idle-connection drop).')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    size, sha, body = smallest_b2_body()
    plan = {'b2_request_sha': sha, 'b2_body_bytes': size, 'b2_settings': {x: body.get(x) for x in body if x != 'messages'},
            'model': a.model, 'effort': a.effort}
    if not a.run:
        print(json.dumps(plan, indent=1))
        return 0
    k = key()
    out_dir = HERE/'diagnostics'/a.out
    out_dir.mkdir(parents=True, exist_ok=False)
    report = {'plan': plan, 'clock': 'time.perf_counter', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if not a.skip_tiny:
        tiny = {'model': a.model, 'reasoning_effort': a.effort, 'response_format': {'type': 'json_object'}, 'temperature': 0.0,
                'max_tokens': 300, 'stream': False,
                'messages': [{'role': 'user', 'content': 'Return exactly this JSON object and nothing else: {"ok": true}'}]}
        report['tiny'] = post(tiny, k, stream=False)
        print('tiny', json.dumps({x: report['tiny'][x] for x in report['tiny'] if x != 'content'}), flush=True)
    if a.nonstream_keepalive:
        real = dict(body, model=a.model, reasoning_effort=a.effort)
        try:
            result = post(real, k, stream=False, keepalive=True)
        except Exception as e:  # noqa: BLE001 - the outcome is the finding
            result = {'error': f'{type(e).__name__}: {e}', 'content': ''}
        result['mode'] = 'not streamed, TCP keepalive 15 s'
    else:
        real = dict(body, model=a.model, reasoning_effort=a.effort, stream=True, stream_options={'include_usage': True})
        result = post(real, k, stream=True)
        result['mode'] = 'streamed'
    (out_dir/'real_content.txt').write_text(result.pop('content') or '', encoding='utf-8')
    try:
        json.loads((out_dir/'real_content.txt').read_text(encoding='utf-8'))
        result['content_is_json'] = True
    except ValueError:
        result['content_is_json'] = False
    report['real'] = result
    (out_dir/'probe.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({x: result[x] for x in result if x != 'progress'}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
