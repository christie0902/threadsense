"""Explicit historical-contract binding for tests of the shared runner/transport.

These tests retain v6 assertions; new taxonomy tests use the production defaults.
No historical response is augmented or validated under the taxonomy contract.
"""
def bind_v6(monkeypatch):
    from threadsense.agents import topic_pipeline, topic_requests, topic_continuation
    from threadsense.legacy.agent2 import topic_comparison
    from threadsense.legacy.agent2 import topic_consolidation_v6 as legacy
    from threadsense.topic_inputs import load_candidate_payloads
    monkeypatch.setattr(topic_comparison, 'load_candidate_payloads', lambda: load_candidate_payloads(historical=True))

    for name in ('build_request', 'parse_response', 'export_result', 'PROMPT_VERSION',
                 'EXPORT_ADAPTER_VERSION', 'RUBRIC_VERSION'):
        monkeypatch.setattr(topic_pipeline, name, getattr(legacy, name))
    monkeypatch.setattr(topic_pipeline, 'RESPONSE_SCHEMA_VERSION', 6)
    monkeypatch.setattr(topic_requests, 'RESPONSE_SCHEMA_VERSION', 6)
    for name in ('build_request', 'export_result'):
        monkeypatch.setattr(topic_continuation, name, getattr(legacy, name))


def bind_v7(monkeypatch):
    """Frozen v7 export semantics, including its historical deterministic metadata."""
    from threadsense.agents import topic_pipeline
    from threadsense.legacy import topic_taxonomy_v7 as legacy
    for name in ('build_request', 'parse_response', 'export_result', 'PROMPT_VERSION',
                 'EXPORT_ADAPTER_VERSION', 'RUBRIC_VERSION', 'RESPONSE_SCHEMA_VERSION'):
        monkeypatch.setattr(topic_pipeline, name, getattr(legacy, name))
