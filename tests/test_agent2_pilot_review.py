"""Real rejected-pilot replay plus bounded reporting/contract regressions; no calls."""
from copy import deepcopy
import json
import runpy

import pytest

# Historical semantic-contract regressions; active taxonomy has separate coverage.
pytestmark = pytest.mark.usefixtures("legacy_agent2_v6")

from threadsense.handoff_inputs import ROOT, digest, read_json, identity
from threadsense.agents import topic_pipeline as pipeline
from threadsense.agents import verification_requests as transport
from threadsense.legacy.agent2.topic_consolidation_v3 import build_request, parse_response
from threadsense.legacy.agent2.topic_consolidation_v3 import PROMPT_VERSION
from threadsense.legacy.agent2.topic_contracts_v3 import ProvisionalSeverity
from threadsense.agents.topic_diagnostics import describe_exception
from threadsense.terminology import get_terms

PILOT = ROOT / 'data/processed/agent2_hardening_pilot_v3'
CASES = read_json(ROOT / 'docs/agent2-hardening-pilot-v3.json')['cases']


@pytest.mark.parametrize('case', CASES, ids=[c['candidate_group_id'] for c in CASES])
def test_saved_pilot_failures_remain_failures_without_repair(case):
    directory = PILOT / 'records' / case['candidate_group_id']
    payload = read_json(directory / 'input.json')
    raw = (directory / 'analysis.raw.txt').read_text(encoding='utf-8')
    with pytest.raises(ValueError) as caught:
        parse_response(payload, raw)
    assert describe_exception(payload, caught.value) == read_json(directory / 'diagnostics.json')


def test_cli_replays_all_six_failures_without_calling_provider_and_reports_counts(monkeypatch, tmp_path, capsys):
    # Explicit historical replay under v3, never a v4 migration or live success.
    from threadsense.legacy.agent2 import topic_consolidation_v3 as historical
    for name in ('build_request', 'parse_response', 'export_result'):
        monkeypatch.setattr(pipeline, name, getattr(historical, name))
    selected = [read_json(PILOT / 'records' / c['candidate_group_id'] / 'input.json') for c in CASES]
    model = 'openai/gpt-4o-mini'
    selection = deepcopy(read_json(ROOT / 'docs/agent2-hardening-pilot-v3.json'))
    # Bind only this synthetic test run to current code; the historical selection is immutable.
    selection['configuration_sha256'] = digest(pipeline.configuration(selected, model))
    path = tmp_path / 'synthetic-replay-selection.json'
    pipeline.write_json(path, selection)
    monkeypatch.setenv('THREADSENSE_MODEL', model)
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-mocked-test-key')
    calls = []

    def send(endpoint, body, key):
        request = json.loads(body)
        gid = json.loads(request['messages'][1]['content'])['candidate_group_id']
        calls.append(gid)
        return 200, (PILOT / 'records' / gid / 'response.raw.bin').read_bytes(), None

    monkeypatch.setattr(transport, 'send_once', send)
    main = runpy.run_path(str(ROOT / 'scripts/run_agent2_batch.py'))['main']
    monkeypatch.setitem(main.__globals__, 'load_candidate_payloads', lambda: selected)
    monkeypatch.setitem(main.__globals__, 'build_request', historical.build_request)
    out = tmp_path / 'replayed'
    code = main(['--run', '--pilot', str(path), '--max-requests', '6', '--output-dir', str(out)])
    assert code == 0  # Completed nonblocking processing, not semantic acceptance.
    printed = capsys.readouterr().out
    assert 'CONSOLIDATED=0, FAILED=6, INTERRUPTED=0, NOT_RUN=0' in printed
    assert 'Saved responses: 6; unknown completions: 0' in printed
    assert calls == [c['candidate_group_id'] for c in CASES]
    rows = read_json(out / 'consolidations.json')
    members = [m for r in rows for m in r['members']]
    flags = [f for r in rows for f in r['inherited_review_obligations']]
    assert len(members) == len({identity(m) for m in members}) == 18
    assert len(flags) == 5 and read_json(out / 'member_review_queue.json') == flags
    assert flags == read_json(PILOT / 'member_review_queue.json')
    assert read_json(out / 'review_queue.json') == rows
    assert all(r['processing_state'] == 'FAILED' and r['unassessed_severity']['level'] == 'UNKNOWN' for r in rows)
    assert all(not r['topics'] and not r['morning_review_obligations'] for r in rows)


def non_operational_assessment():
    """Synthetic severity-only correction, never a repair of the saved failed draft."""
    draft = read_json(PILOT / 'records/cluster_024655fb52cc3352/analysis.raw.txt')
    value = deepcopy(draft['topics'][0]['preliminary_severity'])
    value.update(matched_criteria=['non_operational'], evidence_basis='NON_OPERATIONAL')
    return value


def test_non_operational_basis_does_not_require_inventing_a_risk_or_outcome():
    assessment = ProvisionalSeverity.model_validate(non_operational_assessment())
    assert assessment.level == 'N/A' and assessment.evidence_basis == 'NON_OPERATIONAL'
    assert assessment.work_blockage is None and assessment.quality_or_safety_consequences is None
    assert assessment.rationale.evidence_ids == ['E001']


@pytest.mark.parametrize('level,criterion', [
    ('LOW', 'limited_demonstrated_consequence'), ('MEDIUM', 'bounded_operational_issue'),
    ('HIGH', 'substantial_blockage'), ('UNKNOWN', 'insufficient_impact_evidence'),
])
def test_non_operational_basis_cannot_explain_operational_or_unknown_severity(level, criterion):
    value = non_operational_assessment()
    value.update(level=level, matched_criteria=[criterion])
    with pytest.raises(ValueError):
        ProvisionalSeverity.model_validate(value)


def test_generated_request_exposes_severity_combinations_and_source_disposition_meaning():
    payload = read_json(PILOT / 'records/cluster_024655fb52cc3352/input.json')
    request = build_request(payload, get_terms(), 'openai/gpt-4o-mini')
    system = request['messages'][0]['content']
    schema = json.loads(system[system.index('{"$defs"'):])
    severity = schema['$defs']['ProvisionalSeverity']['properties']
    assert 'NON_OPERATIONAL' in severity['evidence_basis']['enum']
    assert 'UNKNOWN uses INSUFFICIENT_EVIDENCE' in severity['evidence_basis']['description']
    assert 'N/A requires non_operational' in severity['matched_criteria']['description']
    assert 'including for UNKNOWN/N/A' in severity['rationale']['description']
    assert 'question asked IN this message' in schema['$defs']['SourceAssessment']['properties']['question_status']['description']
    inputs = json.loads(request['messages'][1]['content'])
    assert not any(k in inputs for k in ('expected_verdicts', 'selection_purpose_not_model_input', 'source_review_findings'))


def test_revalidation_wire_requests_include_conditional_rules_without_pilot_review_labels():
    """Inspect serialized model inputs, not merely validator attributes or docs."""
    for case in CASES:
        gid = case['candidate_group_id']
        p = read_json(PILOT / 'records' / gid / 'input.json')
        request = build_request(p, get_terms(), 'openai/gpt-4o-mini')
        previous = read_json(ROOT / 'data/processed/agent2_targeted_pilot_v3_1_prepared/records' / gid / 'request.json')
        assert request['messages'][1] == previous['messages'][1]
        assert {k:v for k,v in request.items() if k!='messages'} == {k:v for k,v in previous.items() if k!='messages'}
        system = request['messages'][0]['content']
        assert system.startswith(f'Prompt version: {PROMPT_VERSION}\n')
        for requirement in (
            'representative_question alone does not satisfy this requirement',
            'statements/instructions without a question',
            'guidance_status is independent',
            'with an actual qualifying TL reaction is TL_ENDORSED',
            'Keep explicit conditions in limitations and context in scope',
            'UNKNOWN uses insufficient_impact_evidence and INSUFFICIENT_EVIDENCE',
            'non_operational and NON_OPERATIONAL',
            'HIGH requires a non-null, source-cited work_blockage or',
            'scope, or consequences use null, not an object with empty evidence_ids',
            'Every non-null cited field needs at least one actual supporting evidence ID',
            'must be cited in factual prose outside preliminary_severity',
        ):
            assert requirement in system
        assert gid not in system
        assert all(m['thread_id'] not in system for m in p['members'])
        assert case['selection_purpose_not_model_input'] not in system
        assert 'source_review_findings' not in request['messages'][1]['content']
