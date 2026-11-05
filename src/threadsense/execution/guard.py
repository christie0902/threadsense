"""The shared transport hook: every provider request from any agent passes through Execution.execute.

Order for one request: look up its cache key (the exact semantic request: method, endpoint and canonical JSON body;
credentials and headers excluded) -> serve a saved successful response (this run, then explicitly named parent runs) ->
otherwise, in LIVE mode only: save the exact body, reserve its maximum charge in the ledger (hard ceiling checked
atomically), mark it SENT, send once, save the raw response bytes before anything parses them, settle the reported cost.

Never resent: a key whose earlier attempt is RESERVED, SENT or UNCERTAIN (interrupted), or ended without a successful
response (an SDK retry of a failed attempt is refused here). REPLAY mode disables the network (provider hosts and every
non-loopback socket); a missing response stops the run instead of being regenerated. Stop conditions derive from
BaseException so agent code that catches Exception cannot turn them into an ordinary per-item failure.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import socket

from threadsense.execution import pricing
from threadsense.execution.ledger import Ledger
from threadsense.execution.store import PersistenceFailure, Store

PROVIDER_HOSTS = {'api.openai.com', 'openrouter.ai'}
LOOPBACK = {'127.0.0.1', '::1', 'localhost', 'testserver'}


class NetworkDisabled(BaseException):
    """Replay needed a response that is not saved (or tried to reach the network); nothing is generated."""


class UncertainRequest(BaseException):
    """An earlier attempt with this exact request has an unknown or unsuccessful outcome; it is never resent."""


def cache_key(method, url, body):
    from urllib.parse import urlsplit
    parts = urlsplit(str(url))
    try:
        canonical = json.dumps(json.loads(body), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    except (ValueError, TypeError):
        canonical = 'bytes:' + sha256(bytes(body or b'')).hexdigest()
    return sha256(f'{method.upper()} {parts.hostname}{parts.path}\n{canonical}'.encode('utf-8')).hexdigest()


def _summary(raw):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None, None, None
    return (data.get('usage') if isinstance(data, dict) else None, data.get('model') if isinstance(data, dict) else None,
            data.get('id') if isinstance(data, dict) else None)


class Execution:
    """One run's execution context. mode LIVE (network allowed for misses, budget enforced) or REPLAY (network off)."""

    def __init__(self, run_dir, *, mode, limit_usd=None, parents=()):
        if mode not in ('LIVE', 'REPLAY'):
            raise ValueError(f'Unknown mode {mode}')
        self.run_dir, self.mode = Path(run_dir), mode
        self.ledger = Ledger(self.run_dir/'ledger.sqlite3', limit_usd)
        self.store = Store(self.run_dir/'objects')
        self.parent_dirs = [Path(p) for p in parents]
        self.parents = [(Path(p).name, Ledger(Path(p)/'ledger.sqlite3', readonly=True), Store(Path(p)/'objects')) for p in parents]
        self.stage_name, self.agent = None, None

    @contextmanager
    def stage(self, name, agent):
        previous = self.stage_name, self.agent
        self.stage_name, self.agent = name, agent
        try:
            yield self
        finally:
            self.stage_name, self.agent = previous

    def _successful(self, rows):
        return [r for r in rows if r['state'] in ('SETTLED', 'REUSED') and r['response_sha'] and r['http_status']
                and 200 <= r['http_status'] < 300]

    def execute(self, *, method, url, body, send):
        """Returns (http_status, raw_bytes, headers). `send` performs the one network attempt."""
        body = bytes(body or b'')
        key = cache_key(method, url, body)
        own = self.ledger.rows(key)
        done = self._successful(own)
        if done:  # Resume: this run already has the response.
            hit = done[-1]
            raw = self.store.get(hit['response_sha'])
            self.ledger.record_reuse(cache_key=key, stage=self.stage_name, agent=self.agent, endpoint=str(url), model=hit['model'],
                                     origin='REUSED_RUN', request_sha=hit['request_sha'], response_sha=hit['response_sha'],
                                     http_status=hit['http_status'], usage=hit['usage'])
            return hit['http_status'], raw, {'content-type': 'application/json'}
        blocked = [r for r in own if r['state'] in ('RESERVED', 'SENT', 'UNCERTAIN', 'SETTLED')]
        if blocked:
            r = blocked[-1]
            raise UncertainRequest(f'{self.stage_name}: request {key[:12]} already attempted ({r["state"]}, HTTP {r["http_status"]}); '
                                   'it is not resent automatically.')
        for name, ledger, store in self.parents:
            found = self._successful(ledger.rows(key))
            if found:
                hit = found[-1]
                raw = store.get(hit['response_sha'])
                self.store.put(raw)
                request_sha = self.store.put(store.get(hit['request_sha'])) if hit['request_sha'] else None
                self.ledger.record_reuse(cache_key=key, stage=self.stage_name, agent=self.agent, endpoint=str(url),
                                         model=hit['model'], origin=f'REUSED_PARENT:{name}', request_sha=request_sha,
                                         response_sha=hit['response_sha'], http_status=hit['http_status'], usage=hit['usage'])
                return hit['http_status'], raw, {'content-type': 'application/json'}
        if self.mode == 'REPLAY':
            raise NetworkDisabled(f'{self.stage_name}: no saved response for request {key[:12]}; replay does not call the network.')
        model, input_tokens, cap = pricing.body_fields(body)
        reserved = pricing.reservation(model, input_tokens, cap)
        request_sha = self.store.put(body)  # The exact outgoing payload; credentials live in headers, never stored.
        request_id = self.ledger.reserve(cache_key=key, stage=self.stage_name, agent=self.agent, endpoint=str(url), model=model,
                                         reserved_usd=reserved, request_sha=request_sha)
        self.ledger.mark_sent(request_id)
        try:
            status, raw, headers, failure = send()
        except BaseException as error:
            self.ledger.mark_uncertain(request_id, f'{type(error).__name__}: {str(error)[:500]}')
            raise
        try:
            response_sha = self.store.put(raw)  # Saved on receipt, before any parsing.
        except BaseException as error:
            self.ledger.mark_uncertain(request_id, f'response not saved: {error}')
            raise
        usage, returned_model, response_id = _summary(raw)
        cost = pricing.settled_cost(model, usage) if 200 <= status < 300 and not failure else None
        self.ledger.settle(request_id, http_status=status, response_sha=response_sha, usage=usage, charged_usd=cost,
                           returned_model=returned_model,
                           provider_request_id=(headers or {}).get('x-request-id') or response_id,
                           savings_usd=pricing.cache_savings(model, usage) if cost is not None else 0.0)
        return status, raw, headers or {}

    def close(self):
        self.ledger.close()
        for _, ledger, _ in self.parents:
            ledger.close()


class Guard:
    """Install the hook for one process: httpx (CrewAI, LiteLLM, OpenAI SDK) and the single-attempt verification
    transport; async provider calls are refused (no unguarded path); REPLAY also blocks non-loopback sockets."""

    def __init__(self, execution):
        self.ex = execution

    def __enter__(self):
        import httpx
        from threadsense.agents import verification_requests as vr
        ex = self
        self._httpx, self._async, self._send_once, self._connect = (
            httpx.HTTPTransport.handle_request, httpx.AsyncHTTPTransport.handle_async_request, vr.send_once, socket.socket.connect)
        original = self._httpx

        def handle(transport, request):
            host = request.url.host
            if host not in PROVIDER_HOSTS:
                if ex.ex.mode == 'REPLAY' and host not in LOOPBACK:
                    raise NetworkDisabled(f'Replay refused a request to {host}.')
                return original(transport, request)

            def send():
                response = original(transport, request)
                response.read()
                return response.status_code, response.content, dict(response.headers), None
            status, raw, headers = ex.ex.execute(method=request.method, url=str(request.url), body=request.content, send=send)
            keep = {k: v for k, v in headers.items() if k.lower() in ('content-type', 'x-request-id')}
            keep.setdefault('content-type', 'application/json')
            return httpx.Response(status, headers=keep, content=raw, request=request)

        async def handle_async(transport, request):
            if request.url.host in PROVIDER_HOSTS:
                raise NetworkDisabled('Asynchronous provider requests are not guarded; refused.')
            if ex.ex.mode == 'REPLAY' and request.url.host not in LOOPBACK:
                raise NetworkDisabled(f'Replay refused a request to {request.url.host}.')
            return await ex._async(transport, request)

        def send_once(endpoint, body, api_key):
            def send():
                status, raw, failure = ex._send_once(endpoint, body, api_key)
                return status, raw, ({'x-transport-failure': failure} if failure else {}), failure
            status, raw, headers = ex.ex.execute(method='POST', url=endpoint, body=body, send=send)
            return status, raw, headers.get('x-transport-failure')  # A partial read stays a failure (never reused).

        def connect(sock, address, *args, **kwargs):
            if isinstance(address, tuple) and address[0] not in LOOPBACK:
                raise NetworkDisabled(f'Replay refused a connection to {address[0]}.')
            return ex._connect(sock, address, *args, **kwargs)

        httpx.HTTPTransport.handle_request = handle
        httpx.AsyncHTTPTransport.handle_async_request = handle_async
        vr.send_once = send_once
        if self.ex.mode == 'REPLAY':
            socket.socket.connect = connect
        return self

    def __exit__(self, *exc):
        import httpx
        from threadsense.agents import verification_requests as vr
        httpx.HTTPTransport.handle_request, httpx.AsyncHTTPTransport.handle_async_request = self._httpx, self._async
        vr.send_once = self._send_once
        socket.socket.connect = self._connect
        return False


__all__ = ['Execution', 'Guard', 'NetworkDisabled', 'UncertainRequest', 'PersistenceFailure', 'cache_key', 'Store']
