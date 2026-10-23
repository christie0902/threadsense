"""Single-attempt verification transport with persistence before parsing.

No SDK/CrewAI retry policy, redirects, fallback models, or conversation history.
The original interpreter and Agent 2 transports are unchanged.
"""

import http.client
import json
from urllib.parse import urlsplit

from threadsense.config import get_api_key


class EvidencePersistenceError(RuntimeError):
    """Abort model work when a request or response cannot be retained."""


class VerificationConfigurationError(RuntimeError):
    """Stop the run on incompatible request/model configuration or credentials."""


def persist(callback, *args):
    if callback is not None:
        try:
            callback(*args)
        except Exception as error:
            raise EvidencePersistenceError("Cannot persist verification evidence.") from error


def request_body(model, system, inputs, *, max_tokens):
    provider, separator, name = model.partition("/")
    if not separator or provider not in {"openai", "openrouter"} or not name:
        raise ValueError("Verification requires an openai/ or openrouter/ model route.")
    return {
        "model": name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(inputs, ensure_ascii=False, allow_nan=False)},
        ],
        "temperature": 0, "max_tokens": max_tokens,
    }


def send_once(endpoint, body, api_key):
    """One POST, including on HTTP 429/5xx; preserve partial bodies."""
    url = urlsplit(endpoint)
    connection = http.client.HTTPSConnection(url.hostname, timeout=120)
    try:
        connection.request("POST", url.path, body=body, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {api_key}",
        })
        response = connection.getresponse()
        try:
            return response.status, response.read(), None
        except http.client.IncompleteRead as error:
            return response.status, error.partial, "Incomplete HTTP response; no retry."
    finally:
        connection.close()


def complete_once(model, key_name, request, *, on_raw_output=None, on_artifact=None):
    """Persist exact request bytes and raw HTTP body before any interpretation."""
    endpoint = ("https://openrouter.ai/api/v1/chat/completions" if model.startswith("openrouter/")
                else "https://api.openai.com/v1/chat/completions")
    key = get_api_key(key_name)
    body = (json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    persist(on_artifact, "request.json", body)
    # The marker precedes the only network attempt. No credential is persisted.
    persist(on_artifact, "call.json", json.dumps({"endpoint": endpoint, "attempt": 1}).encode())
    try:
        status, response, failure = send_once(endpoint, body, key)
    except (Exception, KeyboardInterrupt) as error:
        persist(on_artifact, "failure.json", json.dumps({"error_type": type(error).__name__,
                "error": str(error).replace(key, "[redacted]")[:2000]}).encode())
        raise
    persist(on_artifact, "response.raw.bin", response)
    persist(on_artifact, "response.json", json.dumps({"http_status": status, "failure": failure}).encode())
    if status in {400, 401, 403, 404, 422}:
        raise VerificationConfigurationError(
            f"Verification configuration rejected (HTTP {status}); raw response retained. Stop without model substitution."
        )
    if failure or not 200 <= status < 300:
        raise RuntimeError(f"Verification request failed (HTTP {status}); raw response retained; no retry.")
    payload = json.loads(response)
    choices = payload.get("choices", [])
    if len(choices) != 1:
        raise ValueError("Expected exactly one model response choice.")
    raw = choices[0].get("message", {}).get("content")
    persist(on_raw_output, raw if isinstance(raw, str) else "")
    if choices[0].get("finish_reason") != "stop":
        raise ValueError("Model output did not finish normally; incomplete evidence cannot pass.")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Model returned no text output.")
    return raw
