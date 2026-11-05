"""Stage boundaries of the full-run pipeline: resume, selective recomputation, replay and stop accounting. Offline:
stand-in stage functions make requests through the real guard to a fake provider."""
import json

import httpx
import pytest

from threadsense.execution import pipeline as p
from threadsense.execution.guard import Execution, Guard
from threadsense.execution.ledger import BudgetExceeded

from tests.test_execution_layer import FakeProvider, body, post

PROMPTS = {'agent1_interpret': 'interpret v1', 'agent2': 'taxonomy v1', 'agent3': 'advise v1'}


def stand_ins(monkeypatch, prompts):
    def make(stage):
        def run_stage(run):
            out = run.dir/'stages'/stage/'out'
            out.mkdir(parents=True, exist_ok=True)
            if stage in prompts:
                with run.ex.stage(stage, p.AGENTS.get(stage, stage)):
                    text = post(body(prompts[stage])).json()['choices'][0]['message']['content']
                (out/'result.json').write_text(json.dumps({'prompt': prompts[stage], 'answer': text}), encoding='utf-8')
            else:
                (out/'result.json').write_text(json.dumps({'stage': stage}), encoding='utf-8')
            return run.finish(stage, out, 'COMPLETE')
        return run_stage
    monkeypatch.setattr(p, 'STAGE_FUNCS', {s: make(s) for s in p.STAGES})


def run_in(path, mode, parents=(), limit=5.0):
    return p.Run(path, Execution(path, mode=mode, limit_usd=limit, parents=parents))


def execute(run):
    with Guard(run.ex):
        return p.execute(run)


def origins(run):
    return [(r['stage'], r['origin'].split(':')[0]) for r in run.ex.ledger.rows()]


def test_resume_keeps_completed_stages_and_makes_no_calls(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    stand_ins(monkeypatch, PROMPTS)
    run = run_in(tmp_path/'run', 'LIVE')
    assert all(r['status'] == 'COMPLETE' for r in execute(run))
    assert len(provider.calls) == 3
    run.ex.close()
    resumed = run_in(tmp_path/'run', 'LIVE')
    assert all(r.get('kept') for r in execute(resumed)) and len(provider.calls) == 3


def test_changed_agent3_prompt_recomputes_only_agent3(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    stand_ins(monkeypatch, PROMPTS)
    parent = run_in(tmp_path/'run', 'LIVE')
    execute(parent)
    parent.ex.close()
    stand_ins(monkeypatch, {**PROMPTS, 'agent3': 'advise v2'})
    branch = run_in(tmp_path/'branch', 'LIVE', parents=[tmp_path/'run'])
    execute(branch)
    assert origins(branch) == [('agent1_interpret', 'REUSED_PARENT'), ('agent2', 'REUSED_PARENT'), ('agent3', 'FRESH_LIVE')]
    assert len(provider.calls) == 4


def test_changed_upstream_interpretation_recomputes_its_descendants(tmp_path, monkeypatch):
    FakeProvider(monkeypatch)
    stand_ins(monkeypatch, PROMPTS)
    parent = run_in(tmp_path/'run', 'LIVE')
    execute(parent)
    parent.ex.close()

    def downstream_of_interpretation(run):  # Agent 2 and Agent 3 inputs are built from the interpretation output.
        upstream = json.loads((run.dir/'stages'/'agent1_interpret'/'out'/'result.json').read_text(encoding='utf-8'))['prompt']
        return {**PROMPTS, 'agent1_interpret': upstream}
    stand_ins(monkeypatch, {**PROMPTS, 'agent1_interpret': 'interpret v2', 'agent2': 'taxonomy v1 on interpret v2',
                            'agent3': 'advise v1 on interpret v2'})
    branch = run_in(tmp_path/'branch', 'LIVE', parents=[tmp_path/'run'])
    execute(branch)
    assert [o for _, o in origins(branch)] == ['FRESH_LIVE', 'FRESH_LIVE', 'FRESH_LIVE']


def test_exact_replay_reproduces_outputs_with_zero_calls(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    stand_ins(monkeypatch, PROMPTS)
    parent = run_in(tmp_path/'run', 'LIVE')
    execute(parent)
    parent.ex.close()
    replay = run_in(tmp_path/'replay', 'REPLAY', parents=[tmp_path/'run'], limit=0.0)
    execute(replay)
    assert len(provider.calls) == 3 and replay.ex.ledger.committed_usd() == 0
    for stage in PROMPTS:
        assert (tmp_path/'replay'/'stages'/stage/'out'/'result.json').read_bytes() == \
            (tmp_path/'run'/'stages'/stage/'out'/'result.json').read_bytes()


def test_a_budget_stop_is_recorded_and_later_stages_do_not_run(tmp_path, monkeypatch):
    provider = FakeProvider(monkeypatch)
    stand_ins(monkeypatch, {**PROMPTS, 'agent2': 'x' * 20000})
    run = run_in(tmp_path/'run', 'LIVE', limit=0.0003)
    with pytest.raises(BudgetExceeded):
        execute(run)
    manifest = run.manifest('agent2')
    assert manifest['status'] == 'STOPPED' and manifest['error'].startswith('BudgetExceeded')
    assert run.manifest('agent3') is None and len(provider.calls) == 1
    assert run.ex.ledger.committed_usd() <= 0.0003


def test_discussion_view_drops_announcements_and_only_the_named_rejected_threads(tmp_path):
    view = tmp_path/'view'
    p.discussion_view(p.FIXTURE, view)
    everything = p.discussion_identities(view)
    rejected = sorted(everything)[0]
    reduced = tmp_path/'reduced'
    p.discussion_view(p.FIXTURE, reduced, exclude={(rejected[2], rejected[3])})
    assert len(everything) == 178 and p.discussion_identities(reduced) == everything - {rejected}


def test_a_replay_uses_the_parents_agent3_budget_not_its_zero_ceiling(tmp_path):
    saved = tmp_path/'run'/'stages'/'agent3'/'overnight_run'
    saved.mkdir(parents=True)
    (saved/'run_manifest.json').write_text(json.dumps({'fingerprints': {'cost_limit_usd': 34.7432}}), encoding='utf-8')
    Execution(tmp_path/'run', mode='LIVE', limit_usd=39.0).close()
    replay = run_in(tmp_path/'replay', 'REPLAY', parents=[tmp_path/'run'], limit=0.0)
    assert p.agent3_budget(replay, tmp_path/'replay'/'stages'/'agent3'/'overnight_run', 0.22384) == 34.7432
    live = run_in(tmp_path/'live', 'LIVE', limit=10.0)
    assert p.agent3_budget(live, tmp_path/'live'/'stages'/'agent3'/'overnight_run', 0.25) == 9.75
