"""Active taxonomy contract; historical parsing/export requires explicit version dispatch."""
from threadsense.agents.topic_taxonomy import (
    RULES, PROMPT_VERSION, RESPONSE_SCHEMA_VERSION, EXPORT_ADAPTER_VERSION, RUBRIC_VERSION,
    validate_input, validate_output,
)
from threadsense.agents import topic_taxonomy


def _contract(version):
    if version == 7:
        return topic_taxonomy
    if version in {5, 6}:
        from threadsense.agents import topic_consolidation_v6
        return topic_consolidation_v6
    if version in {2, 3, 4}:
        from importlib import import_module
        return import_module(f'threadsense.agents.topic_consolidation_v{version}')
    raise ValueError('Unknown Agent 2 response schema version.')


def build_request(payload, glossary, model, *, response_schema_version=7, export_adapter_version=None):
    if response_schema_version == 5:
        raise ValueError('Use the saved v5 request for historical replay; do not reconstruct it as v6.')
    if response_schema_version==7 and export_adapter_version=='taxonomy-to-canonical-v1':
        from threadsense.legacy import topic_taxonomy_v7
        return topic_taxonomy_v7.build_request(payload, glossary, model)
    return _contract(response_schema_version).build_request(payload, glossary, model)


def parse_response(payload, raw, *, response_schema_version=7):
    module = _contract(response_schema_version)
    if response_schema_version in {5, 6}:
        return module.parse_response(payload, raw, response_schema_version=response_schema_version)
    return module.parse_response(payload, raw)


def export_result(payload, analysis=None, *, response_schema_version=7, export_adapter_version=None, **kwargs):
    if response_schema_version==7 and export_adapter_version=='taxonomy-to-canonical-v1':
        from threadsense.legacy import topic_taxonomy_v7
        return topic_taxonomy_v7.export_result(payload, analysis, **kwargs)
    return _contract(response_schema_version).export_result(payload, analysis, **kwargs)
