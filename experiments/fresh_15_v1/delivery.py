"""Direct delivery for the fresh-15 experiment.

The pipeline builds OpenAI-format chat requests on its existing `openrouter/...` route (the only non-OpenAI route its
fingerprinted transports support). The experiment intercepts each one at the transport and delivers it to the model's
own provider instead; nothing reaches openrouter.ai or api.openai.com:

  anthropic/claude-sonnet-5.5 -> POST api.anthropic.com/v1/messages, model claude-sonnet-5-5: native Messages API through
                                 the official SDK (anthropic==2.4.0), credentials from the `ant auth login` profile
  x-ai/grok-4.7               -> POST api.x.ai/v1/chat/completions, model grok-4.7: xAI's OpenAI-format API, XAI_API_KEY

Every delivered request goes through the existing guard (Execution.execute): its exact body is stored, its maximum cost
reserved against the hard ceiling, it is sent once, and the raw response is stored before parsing and settled from the
provider's usage. Cache keys are the delivered bodies, so Run B is served Run A's saved Sonnet responses.

Translation (chat -> Messages API): system messages -> `system`; user/assistant text unchanged; max_tokens or
max_completion_tokens -> max_tokens; stop -> stop_sequences; a strict json_schema response_format -> native structured
outputs (output_config.format); json_object has no native equivalent and is dropped (the prompt asks for JSON and the
pipeline validates locally, as before); temperature is dropped (Sonnet 5.5 rejects non-default sampling). Thinking:
Agent 3 runs adaptive at effort medium (the standard workflow's medium reasoning); Agents 1-2 run with thinking off
(`between_tools`), as their reviewed models had no reasoning. Grok receives the same OpenAI body with reasoning_effort
medium for Agent 3, and without `stop` (unsupported by xAI reasoning models).
"""
import json
import os

ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
XAI_URL = 'https://api.x.ai/v1/chat/completions'
SDK_VERSION = '2.4.0'
# One read timeout for both providers (the repository's single-POST transport fixes 120 s, which Grok's medium reasoning
# exceeded on every Agent 3 draft in B_grok_v1; Sonnet's slowest request in A_sonnet_v1 took 23 s).
TIMEOUT_SECONDS = 600
DELIVERY = {'anthropic/claude-sonnet-5.5': ('anthropic', 'claude-sonnet-5-5'), 'x-ai/grok-4.7': ('xai', 'grok-4.7')}
FINISH = {'end_turn': 'stop', 'stop_sequence': 'stop', 'max_tokens': 'length', 'refusal': 'content_filter',
          'pause_turn': 'length', 'tool_use': 'tool_calls'}
ROLE_SETTINGS = {
    'anthropic': {'agent3': {'thinking': {'type': 'adaptive'}, 'effort': 'medium'},
                  'other': {'thinking': {'type': 'between_tools'}}},
    'xai': {'agent3': {'reasoning_effort': 'medium'}, 'other': {}},
}


class RouteRefused(BaseException):
    """A request outside the experiment's route allowlist; nothing is reserved or sent."""


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def text(content):
    if isinstance(content, str):
        return content
    return ''.join(p.get('text', '') for p in content or [] if isinstance(p, dict) and p.get('type') == 'text')


def to_anthropic(chat, agent):
    system, messages = [], []
    for m in chat.get('messages') or []:
        role = m.get('role')
        if role in ('system', 'developer'):
            system.append(text(m.get('content')))
        elif role in ('user', 'assistant'):
            messages.append({'role': role, 'content': text(m.get('content'))})
        else:
            raise RouteRefused(f'Message role {role!r} has no translation in this experiment.')
    native = {'model': DELIVERY[chat['model']][1], 'messages': messages,
              'max_tokens': int(chat.get('max_tokens') or chat.get('max_completion_tokens'))}
    if system:
        native['system'] = '\n\n'.join(system)
    stops = [s for s in (chat.get('stop') or []) if isinstance(s, str) and s.strip()]
    if stops:
        native['stop_sequences'] = stops
    fmt = chat.get('response_format') or {}
    output = {}
    if fmt.get('type') == 'json_schema':
        output['format'] = {'type': 'json_schema', 'schema': fmt['json_schema']['schema']}
    setting = ROLE_SETTINGS['anthropic']['agent3' if agent == 'agent3' else 'other']
    native['thinking'] = setting['thinking']
    if setting.get('effort'):
        output['effort'] = setting['effort']
    if output:
        native['output_config'] = output
    return native


def from_anthropic(status, raw):
    """A native Messages API response as the chat-completions JSON the pipeline parses (the stored raw bytes stay native)."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not 200 <= status < 300:
        err = data.get('error') or {}
        return dumps({'error': {'message': err.get('message'), 'type': err.get('type'), 'param': None, 'code': err.get('type'),
                                'native': data}})
    usage = data.get('usage') or {}
    prompt = sum(usage.get(k) or 0 for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
    content = ''.join(b.get('text', '') for b in data.get('content') or [] if b.get('type') == 'text')
    return dumps({'id': data.get('id'), 'object': 'chat.completion', 'created': 0, 'model': data.get('model'),
                  'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content, 'refusal': None},
                               'finish_reason': FINISH.get(data.get('stop_reason'), 'stop')}],
                  'usage': {'prompt_tokens': prompt, 'completion_tokens': usage.get('output_tokens') or 0,
                            'total_tokens': prompt + (usage.get('output_tokens') or 0)},
                  'native_stop': {'stop_reason': data.get('stop_reason'), 'stop_details': data.get('stop_details')}})


def to_xai(chat, agent):
    body = {k: v for k, v in chat.items() if k not in ('provider', 'usage', 'stop', 'max_completion_tokens')}
    body['model'] = DELIVERY[chat['model']][1]
    body['max_tokens'] = int(chat.get('max_tokens') or chat.get('max_completion_tokens'))
    body.update(ROLE_SETTINGS['xai']['agent3' if agent == 'agent3' else 'other'])
    if XAI_STREAM[0]:
        body.update(stream=True, stream_options={'include_usage': True})
    return body


# Opt-in (run_experiment.py agent3 --xai-stream, B3 onward): deliver Grok requests streamed. Diagnosis 2026-11-16
# (diagnostics/grok_probe_v1): a B2 request streamed finished in 238 s with valid JSON (15,842 reasoning tokens, first
# content token at 219 s) at the cost xAI billed for each timed-out request, so B/B2 lost completed responses while the
# non-streamed connection sat idle. Streaming changes only the transport; the pipeline receives the assembled
# chat-completions JSON and the guard stores that assembled response.
XAI_STREAM = [False]


def assemble_stream(lines):
    """Server-sent chat.completion.chunk events -> one chat.completion JSON (content, finish reason, usage, id, model)."""
    content, finish, usage, ident, model, events = [], None, None, None, None, 0
    for line in lines:
        line = line.strip()
        if not line.startswith(b'data:'):
            continue
        payload = line[5:].strip()
        if payload == b'[DONE]':
            break
        ev = json.loads(payload)
        events += 1
        ident, model = ev.get('id') or ident, ev.get('model') or model
        usage = ev.get('usage') or usage
        for ch in ev.get('choices') or []:
            content.append((ch.get('delta') or {}).get('content') or '')
            finish = ch.get('finish_reason') or finish
    return dumps({'id': ident, 'object': 'chat.completion', 'created': 0, 'model': model,
                  'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': ''.join(content), 'refusal': None},
                               'finish_reason': finish}],
                  'usage': usage, 'delivery': {'assembled_from_stream': True, 'events': events}})


_client = None


def anthropic_client():
    """The official SDK on the `ant auth login` profile. An empty ANTHROPIC_API_KEY/AUTH_TOKEN (the repository's .env has
    an empty ANTHROPIC_API_KEY, which load_dotenv copies into the environment) would outrank the profile, so empty ones are
    removed first. No retries; the guard owns the single attempt."""
    global _client
    import anthropic
    if anthropic.__version__ != SDK_VERSION:
        raise RouteRefused(f'anthropic=={SDK_VERSION} expected (run with: uv run --locked --with anthropic=={SDK_VERSION} ...).')
    for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'):
        if not os.environ.get(name, '').strip():
            os.environ.pop(name, None)
    if _client is None:
        _client = anthropic.Anthropic(max_retries=0, timeout=float(TIMEOUT_SECONDS))
    return _client


def send_anthropic(native):
    import anthropic
    client = anthropic_client()
    try:
        response = client.messages.with_raw_response.create(**native)
        return response.status_code, response.read(), dict(response.headers), None
    except anthropic.APIStatusError as error:
        return error.status_code, error.response.content, dict(error.response.headers), None


def send_xai(payload, key):
    """One POST to api.x.ai (same semantics as the repository's single-POST transport: no retry, no redirect, partial
    bodies kept) with the shared timeout."""
    import http.client
    from urllib.parse import urlsplit
    url = urlsplit(XAI_URL)
    connection = http.client.HTTPSConnection(url.hostname, timeout=TIMEOUT_SECONDS)
    try:
        connection.request('POST', url.path, body=payload, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
        response = connection.getresponse()
        if XAI_STREAM[0] and response.status == 200:
            try:
                return response.status, assemble_stream(response), None
            except (http.client.IncompleteRead, ValueError, OSError) as error:
                return response.status, b'', f'Stream interrupted ({type(error).__name__}); no retry.'
        try:
            return response.status, response.read(), None
        except http.client.IncompleteRead as error:
            return response.status, error.partial, 'Incomplete HTTP response; no retry.'
    finally:
        connection.close()


class Delivery:
    """Intercepts the pipeline's OpenAI-format requests and delivers them under the guard (xAI through send_xai, which is
    not re-intercepted). `send_once` is kept for the caller's signature."""

    def __init__(self, execution, send_once, xai_key):
        self.ex, self.send_once, self.xai_key = execution, send_once, xai_key

    def __call__(self, body):
        chat = json.loads(body)
        target = DELIVERY.get(chat.get('model'))
        if target is None:
            raise RouteRefused(f"Model {chat.get('model')!r} has no direct delivery in this experiment.")
        provider, _ = target
        agent = getattr(self.ex, 'agent', None)
        if provider == 'anthropic':
            native = to_anthropic(chat, agent)
            status, raw, headers = self.ex.execute(method='POST', url=ANTHROPIC_URL, body=dumps(native),
                                                   send=lambda: send_anthropic(native))
            return status, from_anthropic(status, raw), headers
        if not self.xai_key.startswith('xai-'):
            raise RouteRefused('XAI_API_KEY is missing; nothing was sent.')
        payload = dumps(to_xai(chat, agent))

        def send():
            status, raw, failure = send_xai(payload, self.xai_key)
            return status, raw, ({'x-transport-failure': failure} if failure else {}), failure
        status, raw, headers = self.ex.execute(method='POST', url=XAI_URL, body=payload, send=send)
        return status, raw, headers
