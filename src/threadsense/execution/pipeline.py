"""Full ThreadSense run: snapshot -> Agent 1 interpretation -> Agent 1 verification -> grouping -> Agent 2 -> Agent 3
-> finalize, each through its existing runner or public function, all under one Execution (ledger, store, guard).

Every stage writes stages/<stage>/stage_manifest.json: its output (an attempt directory), dependencies (the manifests it
consumed, by hash), output tree hash, versions and the requests it made by origin. A completed stage whose dependencies
are unchanged is kept on resume; anything else runs again in a new attempt directory, where requests this run already
answered are served from the store (no charge) and interrupted ones are never resent. Agent 3 resumes in place through
its own resumable workflow. Nothing earlier than this run is reused unless a parent run is named (replay or branch).
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

from threadsense.routing import ROOT

CUTOFF = '2026-10-02T12:00:00Z'
FIXTURE = ROOT/'data/fixtures/slack_generated_demo'
INDEX_DIR = ROOT/'.index/retrieval'
STAGES = ('snapshot', 'agent1_interpret', 'agent1_verify', 'grouping', 'agent2', 'agent3', 'finalize')
AGENTS = {'agent1_interpret': 'agent1', 'agent1_verify': 'agent1', 'agent2': 'agent2', 'agent3': 'agent3'}
# Each agent's validated model settings (Agent 1 v3, Agent 2 v7, Agent 3 Sol acceptance).
ENV = {'THREADSENSE_MODEL': 'openai/gpt-4o-mini-2024-07-18', 'THREADSENSE_VERIFIER_MODEL': 'openai/gpt-4.1',
       'THREADSENSE_AGENT2_REASONING_EFFORT': 'low', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
AGENT2_MODEL = 'openai/gpt-5.4-2026-03-05'
AGENT3_PER_TOPIC = 4


class StageFailed(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def tree_hash(root, skip=()):
    h = sha256()
    root = Path(root)
    for path in sorted(root.rglob('*')):
        if path.is_file() and not any(part in skip for part in path.relative_to(root).parts):
            h.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            import time
            time.sleep(0.5 * (attempt + 1))


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_script(name):
    spec = importlib.util.spec_from_file_location(f'threadsense_full_{name}', ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def environment(values):
    previous = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def checkout():
    """The checkout this run executed: HEAD plus hashes of every changed or untracked file (credentials excluded)."""
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    head = git('rev-parse', 'HEAD').strip()
    dirty = {}
    for line in git('status', '--porcelain', '--untracked-files=all').splitlines():
        path = line[3:].strip().strip('"')
        if path.startswith('data/experiments/threadsense_full') or path == '.env':
            continue
        p = ROOT/path
        if p.is_file():
            dirty[path] = file_hash(p)
    return {'head': head, 'branch': git('rev-parse', '--abbrev-ref', 'HEAD').strip(), 'dirty_files_sha256': dirty,
            'combined_sha256': sha256(json.dumps([head, dirty], sort_keys=True).encode()).hexdigest()}


def configuration():
    """Frozen semantic configuration: models, prompts and schemas, inputs and code versions."""
    from threadsense.agents import advisor_pilot as pilot
    runner = load_script('run_agent3_overnight')
    settings = runner.live_settings()
    return {
        'pipeline': 'threadsense-full-run-v1', 'cutoff': CUTOFF,
        'fixture': {'path': FIXTURE.relative_to(ROOT).as_posix(), 'tree_sha256': tree_hash(FIXTURE)},
        'knowledge_tree_sha256': tree_hash(ROOT/'data/knowledge'),
        'rubric_sha256': file_hash(ROOT/'data/knowledge/severity_rubric.py'),
        'retrieval_index': {'path': '.index/retrieval', 'manifest_sha256': file_hash(INDEX_DIR/'manifest.json'),
                            'build_fingerprint': read_json(INDEX_DIR/'manifest.json')['build_fingerprint']},
        'models': {'agent1_interpreter': ENV['THREADSENSE_MODEL'], 'agent1_verifier': ENV['THREADSENSE_VERIFIER_MODEL'],
                   'agent2': AGENT2_MODEL, 'agent2_reasoning_effort': ENV['THREADSENSE_AGENT2_REASONING_EFFORT'],
                   'agent3': {k: settings[k] for k in ('model', 'reasoning_effort', 'service_tier', 'input_token_limit',
                                                       'max_completion_tokens_per_call', 'timeout_seconds',
                                                       'provider_sdk_max_retries', 'model_fallback')}},
        'agent3_prompts': pilot.prompt_fingerprints(), 'agent3_pilot_version': pilot.PILOT_VERSION,
        'agent3_options': {'research_mode': 'batch (ReAct off)', 'flag_impact': False, 'revision_and_tot': 'conditional (existing)'},
        'transport': {'retries': 0, 'fallback_models': None, 'batch_api': 'not used (sequential proven transports)'},
    }


class Run:
    def __init__(self, run_dir, execution):
        self.dir, self.ex = Path(run_dir), execution

    def manifest_path(self, stage):
        return self.dir/'stages'/stage/'stage_manifest.json'

    def manifest(self, stage):
        p = self.manifest_path(stage)
        return read_json(p) if p.is_file() else None

    def output(self, stage):
        m = self.manifest(stage)
        if not m or m['status'] != 'COMPLETE':
            raise StageFailed(f'{stage} has no completed output.')
        return self.dir/m['output']

    def deps(self, stage):
        order = STAGES[:STAGES.index(stage)]
        return {s: file_hash(self.manifest_path(s)) for s in order if self.manifest_path(s).is_file()}

    def attempt_dir(self, stage, pattern):
        base = self.dir/'stages'/stage
        n = 1
        while any(path.name == pattern.format(n=n) or path.name.startswith(pattern.format(n=n) + '_')
                  for path in (base.iterdir() if base.is_dir() else [])):
            n += 1  # A number is used once, including by an earlier attempt's sibling directories.
        return base/pattern.format(n=n)

    def requests(self, stage):
        rows = [r for r in self.ex.ledger.rows() if r['stage'] == stage]
        out = {}
        for r in rows:
            k = f"{r['origin'].split(':')[0]}:{r['state']}"
            out[k] = out.get(k, 0) + 1
        return {'by_origin_state': out, 'charged_usd': round(sum(r['charged_usd'] for r in rows), 6),
                'uncertain_reserved_usd': round(sum(r['reserved_usd'] for r in rows if r['state'] == 'UNCERTAIN'), 6)}

    def finish(self, stage, output, status, extra=None, versions=None):
        m = {'stage': stage, 'status': status, 'output': Path(output).relative_to(self.dir).as_posix(), 'dependencies': self.deps(stage),
             'output_tree_sha256': tree_hash(output) if Path(output).exists() else None, 'versions': versions or {},
             'requests': self.requests(stage), 'finished_at': now(), **(extra or {})}
        write_json(self.manifest_path(stage), m)
        return m

    def current(self, stage):
        m = self.manifest(stage)
        return m is not None and m['status'] == 'COMPLETE' and m['dependencies'] == self.deps(stage)


# ---- Stages ------------------------------------------------------------------------------------------------------

def stage_snapshot(run):
    out = run.dir/'snapshot'
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(FIXTURE, out/'slack')
    shutil.copytree(INDEX_DIR, out/'retrieval_index_copy')  # Preserved for inspection; Agent 3 reads the checked original.
    info = {'fixture_tree_sha256': tree_hash(out/'slack'), 'source_fixture_tree_sha256': tree_hash(FIXTURE),
            'retrieval_manifest_sha256': file_hash(INDEX_DIR/'manifest.json'),
            'knowledge_tree_sha256': tree_hash(ROOT/'data/knowledge')}
    if info['fixture_tree_sha256'] != info['source_fixture_tree_sha256']:
        raise StageFailed('Snapshot copy differs from its source.')
    write_json(out/'snapshot_manifest.json', info)
    return run.finish('snapshot', out, 'COMPLETE', {'snapshot': info})


def stage_agent1_interpret(run):
    out = run.attempt_dir('agent1_interpret', 'agent1_interpretations_v{n}')
    module = load_script('run_agent1_batch')
    with environment(ENV), run.ex.stage('agent1_interpret', 'agent1'):
        code = module.main(['--limit', '0', '--cutoff', CUTOFF, '--output-dir', str(out), '--fixture-root', str(run.dir/'snapshot'/'slack'),
                            '--source-destination', str(out/'announcement_sources')])
    status = read_json(out/'batch_status.json')
    ok = status['state'] in ('complete', 'complete_with_review')
    return run.finish('agent1_interpret', out, 'COMPLETE' if ok else 'STOPPED',
                      {'runner_exit_code': code, 'batch_status': status}, {'runner': file_hash(ROOT/'scripts/run_agent1_batch.py')})


def discussion_view(snapshot, target, exclude=()):
    """The snapshot's threads with an accepted Agent 1 interpretation: non-announcement channels (announcements bypass
    Agent 1), minus threads Agent 1 rejected (`exclude`: (channel_id, thread_id); accounted for separately, never
    dropped silently). The historical verification runner requires its baseline to cover every source it is given and
    partitions announcements out itself, so it receives this view instead of a runner change."""
    target.mkdir(parents=True)
    (target/'channels').mkdir()
    shutil.copy2(snapshot/'users.json', target/'users.json')
    kept, excluded = [], set(exclude)
    for path in sorted((snapshot/'channels').glob('*.json')):
        data = read_json(path)
        if data['channel'].get('channel_type') == 'ANNOUNCEMENTS':
            continue
        channel = data['channel']['id']
        drop = {t for c, t in excluded if c == channel}
        if drop:
            data['history'] = [m for m in data['history'] if m['ts'] not in drop]
            data['replies'] = {k: v for k, v in data['replies'].items() if k not in drop}
            (target/'channels'/path.name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        else:
            shutil.copy2(path, target/'channels'/path.name)
        kept.append(path.name)
    return kept


def discussion_identities(fixture_root):
    from threadsense.adapters.mock_slack import MockSlackAdapter
    adapter = MockSlackAdapter(str(fixture_root/'channels'), str(fixture_root/'users.json'))
    return {(t.project_id, t.batch_id, t.channel_id, t.thread_id) for path in sorted((fixture_root/'channels').glob('C_*.json'))
            for t in adapter.get_threads(path.stem)}


def agent1_rejections(run):
    """Threads the Agent 1 interpreter rejected (no accepted interpretation; retries are disabled), with the saved request
    and raw response that carried them."""
    folder = run.output('agent1_interpret')
    rejected = read_json(folder/'review_required.json')
    rows = [r for r in run.ex.ledger.rows() if r['stage'] == 'agent1_interpret' and r['request_sha']]
    out = []
    for item in rejected:
        hits = [r for r in rows if item['thread_id'].encode() in run.ex.store.get(r['request_sha'])]
        out.append({**{k: item[k] for k in ('project_id', 'batch_id', 'channel_id', 'thread_id', 'rule', 'error', 'attempts')},
                    'failure_file': (folder/'failures'/f"{item['input_sha256']}.json").relative_to(run.dir).as_posix(),
                    'requests': [{'request_id': r['request_id'], 'request_sha': r['request_sha'], 'response_sha': r['response_sha'],
                                  'state': r['state']} for r in hits],
                    'downstream': 'Not verified, grouped, classified or advised: no accepted Agent 1 interpretation.'})
    return out


def stage_agent1_verify(run):
    baseline = run.output('agent1_interpret')/'interpretations.json'
    out = run.attempt_dir('agent1_verify', 'agent1_verified_v{n}')
    view = out.parent/f'{out.name}_sources'
    rejected = agent1_rejections(run)
    kept = discussion_view(run.dir/'snapshot'/'slack', view, exclude={(r['channel_id'], r['thread_id']) for r in rejected})
    interpreted = {(r['project_id'], r['batch_id'], r['channel_id'], r['thread_id']) for r in read_json(baseline)}
    if discussion_identities(view) != interpreted:
        raise StageFailed('The discussion view and the Agent 1 baseline cover different threads; nothing is verified.')
    module = load_script('run_agent1_verification')
    module.BASELINE, module.FIXTURES = baseline, view  # Module constants only; the runner bytes are unchanged.
    with environment(ENV), run.ex.stage('agent1_verify', 'agent1'):
        code = module.main(['--run', '--limit', '0', '--output-dir', str(out)])
    manifest = read_json(out/'manifest.json')
    ok = code == 0 and manifest.get('unprocessed') == 0
    return run.finish('agent1_verify', out, 'COMPLETE' if ok else 'STOPPED',
                      {'source_view': {'path': view.relative_to(run.dir).as_posix(), 'channels': kept, 'tree_sha256': tree_hash(view),
                                       'excluded_agent1_rejections': len(rejected)},
                       'agent1_rejected': rejected,
                       'runner_exit_code': code, 'verification': {k: manifest.get(k) for k in ('state', 'counts', 'retained', 'unprocessed',
                                                                                                 'model_calls_recorded')}},
                      {'runner': file_hash(ROOT/'scripts/run_agent1_verification.py')})


def stage_grouping(run):
    from threadsense.topic_grouping import refresh_grouping
    canonical = run.output('agent1_verify')/'interpretations.json'
    out = run.attempt_dir('grouping', 'grouping_v{n}')
    with environment(ENV):
        report = refresh_grouping(out, input_path=canonical)
    return run.finish('grouping', out, 'COMPLETE', {'grouping': {k: report[k] for k in ('thread_count', 'cluster_count',
                                                                                          'singleton_count', 'review_member_count')}})


def stage_agent2(run):
    from threadsense.topic_inputs import load_candidate_payloads
    from threadsense.agents.topic_pipeline import execute_batch
    canonical = run.output('agent1_verify')/'interpretations.json'
    payloads = load_candidate_payloads(grouping_path=run.output('grouping')/'clusters.json', canonical_path=canonical)
    out = run.attempt_dir('agent2', 'agent2_v{n}')
    with environment(ENV), run.ex.stage('agent2', 'agent2'):
        execute_batch(payloads, out, run=True, maximum_requests=len(payloads), model_override=AGENT2_MODEL)
    manifest = read_json(out/'manifest.json')
    ok = manifest.get('state') in ('complete', 'complete_with_review') and not manifest.get('unprocessed_groups')
    return run.finish('agent2', out, 'COMPLETE' if ok else 'STOPPED',
                      {'agent2': {k: manifest.get(k) for k in ('state', 'selected_groups', 'retained_input_identities', 'processing_counts',
                                                                'unprocessed_groups', 'inherited_review_obligations', 'review_group_count',
                                                                'new_request_attempts', 'unknown_completion_requests')},
                       'groups_sent': len(payloads)})


def agent3_reservation():
    from threadsense.execution import pricing
    settings = load_script('run_agent3_overnight').live_settings()
    return pricing.reservation(settings['model'], settings['input_token_limit'], settings['max_completion_tokens_per_call'])


def agent3_budget(run, out, per_request):
    """Agent 3's own run budget (a pre-check inside its workflow; the run-wide ledger stays the enforced ceiling)."""
    if (out/'run_manifest.json').is_file():  # Its workflow resumes in place: completed topics kept, interrupted ones not resent.
        return read_json(out/'run_manifest.json')['fingerprints']['cost_limit_usd']
    if run.ex.mode == 'REPLAY':  # Zero spend allowed; reproduce the parent's configuration so its saved responses match.
        for parent in run.ex.parent_dirs:
            saved = parent/'stages'/'agent3'/'overnight_run'/'run_manifest.json'
            if saved.is_file():
                return read_json(saved)['fingerprints']['cost_limit_usd']
    remaining = run.ex.ledger.limit_usd - run.ex.ledger.committed_usd()
    return round(remaining - per_request, 4)  # One reservation of headroom below the run-wide ceiling.


def stage_agent3(run):
    from threadsense.agents import advisor_pilot as pilot
    from threadsense.agents import overnight
    runner = load_script('run_agent3_overnight')
    for k, v in pilot.QUIET_ENV.items():
        os.environ.setdefault(k, v)
    out = run.dir/'stages'/'agent3'/'overnight_run'
    per_request = agent3_reservation()
    resume = (out/'run_manifest.json').is_file()
    budget = agent3_budget(run, out, per_request)
    with run.ex.stage('agent3', 'agent3'):
        rt = runner.build_runtime(out, 'LIVE', cutoff=CUTOFF, only=None, max_requests=None,
                                  max_cost=budget, handoff=run.output('agent2'), fixture_root=run.dir/'snapshot'/'slack',
                                  per_request=per_request, index_dir=INDEX_DIR)
        state = overnight.run(rt)
    brief = read_json(out/'morning_brief.json')
    ok = brief['accounting']['status'] == 'COMPLETE' and not brief.get('incomplete_work')
    return run.finish('agent3', out, 'COMPLETE' if ok else 'STOPPED',
                      {'agent3': {'status': brief['status'], 'accounting': brief['accounting'], 'counts': brief['counts'],
                                  'usage': brief['usage']['totals'], 'incomplete_work': len(brief.get('incomplete_work') or []),
                                  'graph_state': {k: state.get(k) for k in ('status', 'cursor', 'total', 'stop_reason')},
                                  'resumed': resume, 'agent3_budget_usd': budget, 'per_request_reservation_usd': per_request}})


def stage_finalize(run):
    out = run.dir/'final'
    out.mkdir(exist_ok=True)
    verify = run.manifest('agent1_verify') or {}
    summary = {'generated_at': now(), 'stages': {s: run.manifest(s) for s in STAGES[:-1]}, 'ledger': run.ex.ledger.summary(),
               'unfinished_work': {'agent1_rejected_threads': verify.get('agent1_rejected', [])}}
    write_json(out/'run_summary.json', summary)
    return run.finish('finalize', out, 'COMPLETE')


STAGE_FUNCS = {'snapshot': stage_snapshot, 'agent1_interpret': stage_agent1_interpret, 'agent1_verify': stage_agent1_verify,
               'grouping': stage_grouping, 'agent2': stage_agent2, 'agent3': stage_agent3, 'finalize': stage_finalize}


def execute(run, *, stop_after=None):
    """Run every stage that is not already complete with unchanged dependencies. Stops at the first stage that does not
    complete (its output and accounting are kept)."""
    done = []
    for stage in STAGES:
        if run.current(stage):
            done.append({'stage': stage, 'kept': True})
        else:
            try:
                m = STAGE_FUNCS[stage](run)
            except BaseException as error:  # Guard stops, runner refusals (SystemExit), interruptions: recorded, then raised.
                attempts = sorted((run.dir/'stages'/stage).glob('*')) if (run.dir/'stages'/stage).is_dir() else []
                output = next((a for a in reversed(attempts) if a.is_dir()), run.dir/'stages'/stage)
                run.finish(stage, output, 'STOPPED', {'error': f'{type(error).__name__}: {str(error)[:1500]}'})
                done.append({'stage': stage, 'status': 'STOPPED', 'error': type(error).__name__})
                if isinstance(error, (KeyboardInterrupt, SystemExit)) or not isinstance(error, Exception):
                    raise
                break
            done.append({'stage': stage, 'status': m['status']})
            if m['status'] != 'COMPLETE':
                break
        if stop_after == stage:
            break
    return done
