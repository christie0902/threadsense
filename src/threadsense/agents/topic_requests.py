"""Agent 2 strict Chat Completions requests; reuse the unchanged one-POST transport.

Provider schema is generated from local contracts. Local semantic/cross-field
checks remain authoritative. No SDK, retry, fallback, tool or model repair.
"""
from copy import deepcopy
import json
import os
import time

from threadsense.agents import verification_requests as transport
from threadsense.agents.topic_contracts import TopicTaxonomy
from threadsense.agents.topic_diagnostics import ConsolidationValidationError

BASELINE_MODEL = 'openai/gpt-4o-mini-2024-07-18'
COMPARISON_MODEL = 'openai/gpt-5.4-2026-03-05'
MAX_COMPLETION_TOKENS = 8192
REASONING_ENV = 'THREADSENSE_AGENT2_REASONING_EFFORT'
RESPONSE_SCHEMA_VERSION = 7


def model_parameters(model):
    if model not in {'openai/gpt-4o-mini', BASELINE_MODEL, COMPARISON_MODEL}:
        raise ValueError('Unreviewed Agent 2 model configuration; no automatic model substitution.')
    effort = os.environ.get(REASONING_ENV, 'none')
    if effort not in {'none', 'low'} or (effort != 'none' and model != COMPARISON_MODEL):
        raise ValueError('Agent 2 reasoning must be none, or low with the reviewed GPT-5.4 snapshot.')
    result = {'temperature': 0, 'max_completion_tokens': MAX_COMPLETION_TOKENS}
    if model == COMPARISON_MODEL:
        # GPT-5.4 supports temperature only at reasoning_effort=none.
        result['reasoning_effort'] = effort
        if effort == 'low':
            result.pop('temperature')
    return result


def provider_schema(response_schema_version=None):
    """Use the documented strict subset; minLength remains enforced locally.

    Every property is required, nullable fields use anyOf, and every object is
    closed. Refuse unsupported new constructs rather than silently widening them.
    """
    version = RESPONSE_SCHEMA_VERSION if response_schema_version is None else response_schema_version
    if version not in {6, 7}:
        raise ValueError('Unsupported request schema version; historical parsers remain separate.')
    contract = TopicTaxonomy
    if version == 6:
        from threadsense.legacy.agent2.topic_contracts_v6 import TopicConsolidation
        contract = TopicConsolidation
    schema = deepcopy(contract.model_json_schema())
    def visit(node):
        if not isinstance(node, dict):
            return
        node.pop('title', None)
        node.pop('minLength', None)
        if any(k in node for k in ('allOf', 'not', 'if', 'then', 'else', 'default', 'patternProperties')):
            raise ValueError('Unsupported provider schema construct.')
        if node.get('type') == 'object':
            if node.get('additionalProperties') is not False:
                raise ValueError('Structured-output objects must be closed.')
            if set(node.get('required', [])) != set(node.get('properties', {})):
                raise ValueError('All provider fields must be required; use null for unknown values.')
        for key in ('$defs', 'properties'):
            for child in node.get(key, {}).values():
                visit(child)
        visit(node.get('items'))
        for child in node.get('anyOf', []):
            visit(child)
    visit(schema)
    return schema


def response_format(response_schema_version=None):
    version = RESPONSE_SCHEMA_VERSION if response_schema_version is None else response_schema_version
    return {'type': 'json_schema', 'json_schema': {
        'name': 'threadsense_agent2_taxonomy_v7' if version == 7 else 'threadsense_agent2_inventory_v6',
        'strict': True, 'schema': provider_schema(version)}}


def request_body(model, system, inputs, *, response_schema_version=None):
    parameters = model_parameters(model)
    request = transport.request_body(model, system, inputs, max_tokens=MAX_COMPLETION_TOKENS)
    request.pop('max_tokens')
    request.update(parameters, response_format=response_format(response_schema_version))
    if parameters.get('reasoning_effort') == 'low':
        # The shared transport builder supplies temperature=0. Strip it here;
        # the single-POST transport serializes this body without adding defaults.
        for field in ('temperature', 'top_p', 'logprobs'):
            request.pop(field, None)
    return request


class UnsupportedStructuredSchema(transport.VerificationConfigurationError):
    category = 'unsupported_schema'


def complete_once(model, key_name, request, *, on_raw_output=None, on_artifact=None):
    """Classify refusal/incompletion after raw evidence is persisted by transport."""
    evidence = {}
    started = time.perf_counter()
    def capture(name, body):
        evidence[name] = body
        if on_artifact:
            on_artifact(name, body)
    error, raw = None, None
    try:
        raw = transport.complete_once(model, key_name, request,
                                     on_raw_output=on_raw_output, on_artifact=capture)
    except (transport.EvidencePersistenceError, KeyboardInterrupt):
        raise
    except Exception as caught:
        error = caught
    elapsed = time.perf_counter() - started
    try:
        payload = json.loads(evidence.get('response.raw.bin', b'{}'))
    except (ValueError, UnicodeDecodeError):
        payload = {}
    metadata = json.loads(evidence.get('response.json', b'{}'))
    choices = payload.get('choices', []) if isinstance(payload, dict) else []
    if not isinstance(choices, list):
        choices = []
    choice = choices[0] if len(choices) == 1 and isinstance(choices[0], dict) else {}
    message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
    refusal = message.get('refusal')
    status = 'UNKNOWN_COMPLETION' if not metadata or metadata.get('failure') else 'FAILED'
    if isinstance(error, transport.VerificationConfigurationError):
        api_error = (payload.get('error') or {}) if isinstance(payload, dict) else {}
        if isinstance(api_error, dict) and ('response_format' in str(api_error.get('param', ''))
                or api_error.get('code') in {'invalid_json_schema', 'unsupported_schema'}):
            status = 'UNSUPPORTED_SCHEMA'
            error = UnsupportedStructuredSchema('Provider rejected response_format schema; raw error retained; no fallback.')
        else:
            status = 'CONFIGURATION_REJECTED'
    elif metadata.get('failure'):
        status = 'INCOMPLETE_HTTP'
        error = ConsolidationValidationError('incomplete_response', 'HTTP body incomplete; completion unknown and no retry.', ('response',))
    elif refusal:
        status = 'REFUSED'
        error = ConsolidationValidationError('refusal', 'Provider refused the request; inspect saved refusal.', ('response', 'message', 'refusal'))
    elif choice and choice.get('finish_reason') != 'stop':
        status = 'INCOMPLETE_OUTPUT'
        error = ConsolidationValidationError('incomplete_output', f"Model finish_reason={choice.get('finish_reason')}; no repair or retry.", ('response', 'finish_reason'))
    elif error is None:
        status = 'COMPLETED'
    transport.persist(on_artifact, 'completion_status.json', json.dumps({
        'status': status, 'latency_seconds': elapsed, 'http_status': metadata.get('http_status'),
        'requested_model': request['model'], 'response_model': payload.get('model') if isinstance(payload, dict) else None,
        'finish_reason': choice.get('finish_reason'), 'usage': payload.get('usage') if isinstance(payload, dict) else None,
        'refusal': refusal, 'provider_completion_unknown': status in {'UNKNOWN_COMPLETION', 'INCOMPLETE_HTTP'},
    }, ensure_ascii=False).encode('utf-8'))
    if error:
        raise error
    return raw
