"""The static web demo bundle (web/demo/briefing.json) is the saved API output of its run and nothing else."""
import importlib.util
import json

from threadsense.routing import ROOT

BUNDLE = ROOT/'web/demo/briefing.json'


def load_script():
    spec = importlib.util.spec_from_file_location('build_web_demo_data', ROOT/'scripts/build_web_demo_data.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_matches_a_fresh_snapshot_of_its_run():
    script = load_script()
    bundle = json.loads(BUNDLE.read_text(encoding='utf-8'))
    run, responses, _ = script.snapshot(bundle['run_key'], [ROOT/'data/experiments'])
    assert bundle['run_instance'] == run.instance  # the run files are the ones the bundle was made from
    assert bundle['responses'] == script.relative_paths(responses, [0])
    text = BUNDLE.read_text(encoding='utf-8')
    assert not [p.pattern for p in script.FORBIDDEN if p.search(text)]
    paths = set(bundle['responses'])
    assert paths <= {'/api/runs', '/api/lessons'} | {p for p in paths if p.startswith(f"/api/runs/{bundle['run_key']}/")}
    assert json.loads(json.dumps(bundle['responses']['/api/runs']['body']))['runs'][0]['run_key'] == bundle['run_key']
    assert len(bundle['responses']['/api/runs']['body']['runs']) == 1
