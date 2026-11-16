"""Fresh-15 model comparison: the standard full run (scripts/run_threadsense_full.py) on experiment inputs and models.

Nothing in the repository's runners, prompts, contracts or frozen files changes. This wrapper sets, for this process only:
  inputs     fixture inputs/slack, cutoff 2026-10-17T00:00:00Z (window [cutoff-24h, cutoff)), index .index/fresh_15_v1
  models     every enabled role on the pipeline's `openrouter/...` route label, delivered directly to the provider
             (delivery.py): Sonnet 5.5 to api.anthropic.com (native Messages API, `ant auth login` profile), Grok 4.7 to
             api.x.ai (XAI_API_KEY). No request reaches openrouter.ai or api.openai.com.
  guard      every delivered request goes through the existing transport guard (stored body, reservation against the
             hard ceiling, one send, stored raw response, settlement); a route allowlist refuses any other host or model
             before anything is reserved or sent
  pricing    list rates for the two models; xAI settlement from its reported cost when present
Every override is recorded in the run manifest (configuration.experiment). The answer key is never read.

  preflight [--arm sonnet|grok] [--count-tokens]                        zero model calls (--count-tokens: free
                                                                         Anthropic token counting of one translated request)
  live   [--arm sonnet|gpt] --write DIR --run --max-cost USD             Run A Sonnet / Run C original OpenAI plan (PAID)
  branch --source RUN_A --write DIR --run --max-cost USD                 Run B, Grok for Agent 3; Agent 1/2 served from
                                                                         Run A's saved responses, never resent (PAID)
  agent3 --arm A --source RUN_A --write DIR --run --max-cost USD          Agent 3 alone on RUN_A's persisted handoff (PAID)
  resume DIR [--reason TEXT]                                             continue an interrupted run (same arm and checks)
  ledger DIR                                                             which models and providers actually answered

    uv run --locked --with anthropic==2.4.0 python experiments/fresh_15_v1/run_experiment.py preflight
"""
import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(HERE))
import delivery as D  # noqa: E402
from delivery import RouteRefused  # noqa: E402,F401

FIXTURE = HERE/'inputs/slack'
KNOWLEDGE = HERE/'inputs/knowledge'
INDEX = ROOT/'.index/fresh_15_v1'
RUNS = HERE/'runs'
CUTOFF = '2026-10-17T00:00:00Z'
SONNET = 'openrouter/anthropic/claude-sonnet-5.5'   # pipeline route label; delivered as claude-sonnet-5-5
GROK = 'openrouter/x-ai/grok-4.7'                   # pipeline route label; delivered as grok-4.7
# List rates (USD/token): Sonnet 5.5 $2/$10 (Claude models table; cache reads $0.10), checked 2026-11-16; Grok 4.7 $2/$6
# (api.x.ai/v1/language-models/grok-4.7 on 2026-11-16; doubled above a 200k-token prompt, which the 24k input cap
# rules out). No prompt caching is requested, so no cache-write charge applies.
RATES = {'claude-sonnet-5-5': {'input': 2.0e-6, 'cached_input': 0.1e-6, 'cache_write': None, 'output': 10.0e-6},
         'grok-4.7': {'input': 2.0e-6, 'cached_input': 0.5e-6, 'cache_write': None, 'output': 6.0e-6}}
MAX_OUTPUT = {'claude-sonnet-5-5': 128000, 'grok-4.7': 450000}
INPUT_MARGIN = 1.6  # Token estimates use o200k; Claude counts measured up to 1.48x that (free count_tokens, 2026-11-16).
AGENT3 = {'temperature': 0, 'max_completion_tokens': 16384, 'reasoning_effort': None, 'service_tier': None}
# Run C ('gpt'): the repository's validated OpenAI plan, unchanged (pipeline.ENV / AGENT2_MODEL and the Agent 3 runner's
# Sol settings), on the standard transports to api.openai.com; only the experiment inputs and the user directory change.
GPT = {'agent1': 'openai/gpt-4o-mini-2024-07-18', 'agent1_verifier': 'openai/gpt-4.1', 'agent2': 'openai/gpt-5.4-2026-03-05',
       'agent3': 'openai/gpt-6.1-sol'}
ARMS = {'sonnet': {'agent1': SONNET, 'agent2': SONNET, 'agent3': SONNET},
        'grok': {'agent1': SONNET, 'agent2': SONNET, 'agent3': GROK},  # Run B: Agent 1/2 only via Run A's responses.
        'gpt': GPT}
ALLOWED_TO_SEND = {'sonnet': {'claude-sonnet-5-5'}, 'grok': {'grok-4.7'},
                   'gpt': {'gpt-4o-mini-2024-07-18', 'gpt-4.1', 'gpt-5.4-2026-03-05', 'gpt-6.1-sol'}}
DELIVERY_HOSTS = {'api.anthropic.com', 'api.x.ai'}
ARM_HOSTS = {'sonnet': DELIVERY_HOSTS, 'grok': DELIVERY_HOSTS, 'gpt': {'api.openai.com'}}
CURRENT = {'arm': None}
REFUSED_HOSTS = ('api.openai.com', 'openrouter.ai', 'api.anthropic.com', 'api.x.ai')  # direct use outside delivery
ROUTE_PLACEHOLDER = 'not-sent-direct-delivery'  # the pipeline requires a non-empty OPENROUTER_API_KEY; it is never sent
XAI_KEY = ['']


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    from threadsense.execution.pipeline import tree_hash
    return tree_hash(path)


# ---- Runtime configuration ----------------------------------------------------------------------------------------

def configure(arm):
    """Point the standard pipeline at the experiment inputs and models (this process only)."""
    from threadsense.agents import advisor_pilot as pilot, topic_pipeline, topic_requests
    from threadsense.execution import pipeline as p, pricing
    models = ARMS[arm]
    CURRENT['arm'] = arm
    for k, v in pilot.QUIET_ENV.items():
        os.environ.setdefault(k, v)
    os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OPENROUTER_API_KEY': ROUTE_PLACEHOLDER})
    from dotenv import dotenv_values  # Only XAI_API_KEY is read here; it is kept in memory, never printed or stored.
    from threadsense.config import ENV_FILE
    XAI_KEY[0] = (dotenv_values(ENV_FILE, encoding='utf-8-sig').get('XAI_API_KEY') or '').strip()
    p.FIXTURE, p.CUTOFF, p.INDEX_DIR = FIXTURE, CUTOFF, INDEX
    # Agent 3's attribution checks and evidence names read a user directory that defaults to the demo fixture
    # (advisor_evidence.user_directory, path retrieval.config.FIXTURE_ROOT/users.json), not the run's fixture: on fresh
    # data every fixture user would be "not in the user directory". Point it at this experiment's users.
    from functools import cache
    from threadsense.agents import advisor_checks, advisor_evidence
    base_directory = getattr(advisor_evidence.user_directory, '__wrapped__', advisor_evidence.user_directory)

    @cache
    def user_directory(path=FIXTURE/'users.json'):
        return base_directory(path)
    advisor_evidence.user_directory = advisor_checks.user_directory = user_directory
    if arm == 'gpt':  # The standard OpenAI plan: no model, parameter, key, pricing or transport override.
        assert p.ENV['THREADSENSE_MODEL'] == GPT['agent1'] and p.ENV['THREADSENSE_VERIFIER_MODEL'] == GPT['agent1_verifier']
        assert p.AGENT2_MODEL == GPT['agent2']
        return _record_configuration(arm, p)
    p.ENV = {'THREADSENSE_MODEL': models['agent1'], 'THREADSENSE_VERIFIER_MODEL': models['agent1'],
             'THREADSENSE_AGENT2_REASONING_EFFORT': 'none', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    p.AGENT2_MODEL = models['agent2']
    original_parameters = topic_requests.model_parameters

    def model_parameters(model):  # Agent 2's reviewed list has OpenAI models only; the experiment adds its own, explicitly.
        if model in (SONNET, GROK):
            return {'temperature': 0, 'max_completion_tokens': topic_requests.MAX_COMPLETION_TOKENS}
        return original_parameters(model)
    topic_requests.model_parameters = topic_pipeline.model_parameters = model_parameters
    original_load = p.load_script

    def load_script(name):
        module = original_load(name)
        if name == 'run_agent3_overnight':
            module.live_settings = lambda: pilot.live_settings(models['agent3'], **AGENT3, input_token_limit=pilot.INPUT_TOKEN_LIMIT)
        return module
    p.load_script = load_script
    # Agent 2 hard-codes OPENAI_API_KEY for a model override (topic_pipeline.execute_batch) and as LiveJudge's default
    # key. Both files are fingerprinted, so the experiment routes around it: Agent 2 takes its model from
    # THREADSENSE_MODEL (the same model in both arms), which selects the route's key; the judge gets that key too.
    assert models['agent1'] == models['agent2']
    original_agent2 = p.STAGE_FUNCS['agent2']

    def stage_agent2(run):
        saved = p.AGENT2_MODEL
        p.AGENT2_MODEL = None
        try:
            return original_agent2(run)
        finally:
            p.AGENT2_MODEL = saved
    p.STAGE_FUNCS['agent2'] = stage_agent2
    from threadsense.agents import topic_merge

    class Judge(topic_merge.LiveJudge):
        def __init__(self, model, key_name='OPENAI_API_KEY', on_artifact=None):
            super().__init__(model, 'OPENROUTER_API_KEY' if model.startswith('openrouter/') else key_name, on_artifact)
    topic_merge.LiveJudge = Judge
    pricing.PRICES.update(RATES)
    # Agent 3's per-request reservation prices its route label (pricing.rates strips one segment, leaving
    # 'anthropic/claude-sonnet-5.5' / 'x-ai/grok-4.7'); same rates as the delivered models.
    pricing.PRICES.update({'anthropic/claude-sonnet-5.5': RATES['claude-sonnet-5-5'], 'x-ai/grok-4.7': RATES['grok-4.7']})
    pricing.MAX_OUTPUT.update(MAX_OUTPUT)
    pricing.INPUT_MARGIN = INPUT_MARGIN
    original_settled = pricing.settled_cost

    def settled_cost(model, usage):
        """xAI reports the charge in usd ticks (1e-10 USD) when present. Otherwise its reasoning tokens are added to the
        completion tokens (conservative if the provider already counts them there). Anthropic usage settles from tokens."""
        if model == 'grok-4.7' and isinstance(usage, dict):
            if isinstance(usage.get('cost_in_usd_ticks'), int):
                return usage['cost_in_usd_ticks'] / 1e10
            reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
            if isinstance(usage.get('prompt_tokens'), int):
                usage = {**usage, 'completion_tokens': (usage.get('completion_tokens') or 0) + reasoning}
        return original_settled(model, usage)
    pricing.settled_cost = settled_cost
    return _record_configuration(arm, p)


def _record_configuration(arm, p):
    original_configuration, original_checkout = p.configuration, p.checkout

    def configuration(pipeline=p.PIPELINE_V2):
        c = original_configuration(pipeline)
        c['experiment'] = experiment_record(arm)
        return c

    def checkout():
        c = original_checkout()
        c['dirty_files_sha256'] = {k: v for k, v in c['dirty_files_sha256'].items()
                                   if not k.startswith('experiments/fresh_15_v1/runs/')}
        return c
    p.configuration, p.checkout = configuration, checkout
    return ARMS[arm]


def _common_record():
    freeze = json.loads((HERE/'freeze.json').read_text(encoding='utf-8'))
    manifest = json.loads((INDEX/'manifest.json').read_text(encoding='utf-8'))
    return {
            'inputs': {'fixture': FIXTURE.relative_to(ROOT).as_posix(), 'fixture_tree_sha256': tree(FIXTURE),
                       'knowledge': KNOWLEDGE.relative_to(ROOT).as_posix(), 'knowledge_tree_sha256': tree(KNOWLEDGE),
                       'index': '.index/fresh_15_v1', 'index_build_fingerprint': manifest['build_fingerprint'],
                       'index_corpus_fingerprint': manifest['corpus_fingerprint'], 'cutoff': CUTOFF},
            'freeze_sha256': sha(HERE/'freeze.json'), 'frozen': {k: v['sha256'] for k, v in freeze['files'].items()},
            'disabled': {'reviewer_feedback_snapshot': 'not passed (Agent 3 feedback_snapshot=None)',
                         'review_lessons': 'not passed (Agent 1/2 --lessons absent)',
                         'parent_caches': 'none for Run A; Run B reads Run A only', 'react_research': 'off', 'flag_impact': 'off'}}


def experiment_record(arm):
    if arm == 'gpt':
        from threadsense.agents import advisor_pilot as pilot
        from threadsense.execution import pipeline as p
        return {'fixture_id': 'threadsense_fresh_15_v1', 'arm': arm, 'models': ARMS[arm],
                'transport': 'standard repository transports to api.openai.com (no interception)',
                'allowed_to_send': sorted(ALLOWED_TO_SEND[arm]), 'allowed_hosts': sorted(ARM_HOSTS[arm]),
                'agent2_reasoning_effort': p.ENV['THREADSENSE_AGENT2_REASONING_EFFORT'],
                'agent3_settings': 'scripts/run_agent3_overnight.live_settings (gpt-6.1-sol, reasoning medium, '
                                   f'{pilot.REQUEST_TIMEOUT_SECONDS} s timeout)',
                'pricing': 'repository pricing.py (verified prices), default input margin',
                **_common_record(),
                'runtime_overrides': ['pipeline FIXTURE/CUTOFF/INDEX_DIR', 'Agent 3 user directory = the experiment fixture users',
                                      'route allowlist: api.openai.com and the four plan models only',
                                      'checkout() ignores experiments/fresh_15_v1/runs/']}
    return {'fixture_id': 'threadsense_fresh_15_v1', 'arm': arm, 'route_labels': ARMS[arm],
            'delivery': {label: {'provider': prov, 'model': model, 'endpoint': D.ANTHROPIC_URL if prov == 'anthropic' else D.XAI_URL}
                         for label, (prov, model) in D.DELIVERY.items()},
            'allowed_to_send': sorted(ALLOWED_TO_SEND[arm]), 'anthropic_sdk': D.SDK_VERSION,
            'role_settings': D.ROLE_SETTINGS, 'rates_usd_per_token': RATES, 'input_margin': INPUT_MARGIN,
            'agent3_settings': AGENT3, 'agent2_parameters': {'temperature': 0, 'max_completion_tokens': 8192, 'reasoning': 'not sent'},
            **_common_record(),
            'runtime_overrides': ['pipeline FIXTURE/CUTOFF/INDEX_DIR/ENV/AGENT2_MODEL', 'Agent 3 live_settings',
                                  'Agent 2 model_parameters for the experiment models',
                                  'Agent 2 model taken from THREADSENSE_MODEL instead of the override, which hard-codes '
                                  'OPENAI_API_KEY', 'consolidation LiveJudge uses the route key',
                                  'direct delivery (delivery.py) with a route allowlist', 'pricing rates and input margin',
                                  'xAI settlement from cost_in_usd_ticks or tokens incl. reasoning',
                                  'checkout() ignores experiments/fresh_15_v1/runs/',
                                  'Agent 3 user directory = the experiment fixture users (default is the demo fixture)',
                                  f'delivery read timeout {D.TIMEOUT_SECONDS} s for both providers']}


# ---- Route allowlist and delivery on top of the existing guard -----------------------------------------------------

def routed_execution_class():
    from threadsense.execution.guard import Execution, cache_key

    class RoutedExecution(Execution):
        allowed = frozenset()

        def execute(self, *, method, url, body, send):
            # Agent 3 never reuses another run's responses (Run B's parent is Run A): every Agent 3 request is sent.
            parents = self.parents
            if self.stage_name == 'agent3':
                self.parents = []
            try:
                key = cache_key(method, url, bytes(body or b''))
                served = self._successful(self.ledger.rows(key)) or any(self._successful(l.rows(key)) for _, l, _ in self.parents)
                if not served:
                    check_route(url, body, self.allowed)
                return super().execute(method=method, url=url, body=body, send=send)
            finally:
                self.parents = parents
    return RoutedExecution


def check_route(url, body, allowed):
    from urllib.parse import urlsplit
    host = urlsplit(str(url)).hostname
    if host not in ARM_HOSTS[CURRENT['arm']]:
        raise RouteRefused(f'Provider host {host} is not allowed in this experiment.')
    model = json.loads(body).get('model')
    if model not in allowed:
        raise RouteRefused(f'Model {model!r} is not allowed to send in this run (allowed: {sorted(allowed)}).')
    if (host == 'api.anthropic.com') != model.startswith('claude-'):
        raise RouteRefused(f'Model {model!r} does not belong to {host}.')


@contextmanager
def routes(guard, execution):
    """Installed after Guard: every request on the pipeline's OpenAI-format route is delivered directly (delivery.py);
    direct calls to provider hosts from anywhere else are refused, on both transports."""
    import httpx
    from threadsense.agents import verification_requests as vr
    guarded_handle, guarded_send_once = httpx.HTTPTransport.handle_request, vr.send_once
    if CURRENT['arm'] == 'gpt':  # Standard transports; only api.openai.com may be reached through the guard.
        def handle_gpt(transport, request):
            if request.url.host in ('openrouter.ai', 'api.anthropic.com', 'api.x.ai'):
                raise RouteRefused(f'Provider host {request.url.host} is refused in Run C.')
            return guarded_handle(transport, request)

        def send_once_gpt(endpoint, body, api_key):
            from urllib.parse import urlsplit
            if urlsplit(endpoint).hostname != 'api.openai.com':
                raise RouteRefused(f'Endpoint {endpoint} is refused in Run C.')
            return guarded_send_once(endpoint, body, api_key)
        httpx.HTTPTransport.handle_request, vr.send_once = handle_gpt, send_once_gpt
        try:
            yield
        finally:
            httpx.HTTPTransport.handle_request, vr.send_once = guarded_handle, guarded_send_once
        return
    deliver = D.Delivery(execution, guard._send_once, XAI_KEY[0])

    def handle(transport, request):
        host = request.url.host
        if host == 'openrouter.ai' and request.content:
            status, raw, _ = deliver(request.content)
            return httpx.Response(status, headers={'content-type': 'application/json'}, content=raw, request=request)
        if host in REFUSED_HOSTS:
            raise RouteRefused(f'Provider host {host} is refused in this experiment.')
        return guarded_handle(transport, request)

    def send_once(endpoint, body, api_key):
        from urllib.parse import urlsplit
        if urlsplit(endpoint).hostname != 'openrouter.ai':
            raise RouteRefused(f'Endpoint {endpoint} is refused in this experiment.')
        status, raw, headers = deliver(body)
        return status, raw, headers.get('x-transport-failure')
    httpx.HTTPTransport.handle_request, vr.send_once = handle, send_once
    try:
        yield
    finally:
        httpx.HTTPTransport.handle_request, vr.send_once = guarded_handle, guarded_send_once


# ---- Commands -------------------------------------------------------------------------------------------------------

def runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location('run_threadsense_full', ROOT/'scripts/run_threadsense_full.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def open_routed(path, mode, *, limit, parents, arm):
    from threadsense.execution.pipeline import Run
    cls = routed_execution_class()
    cls.allowed = frozenset(ALLOWED_TO_SEND[arm])
    return Run(path, cls(path, mode=mode, limit_usd=limit, parents=parents))


def start(path, mode, limit, arm, parents=(), label='FRESH_LIVE'):
    import time
    started = time.perf_counter()
    full = runner()
    full.open_run = lambda p_, m_, *, limit=None, parents=(): open_routed(p_, m_, limit=limit, parents=parents, arm=arm)
    run = full.start(Path(path), mode, limit, parents=parents, label=label)
    SETUP['seconds'] = round(time.perf_counter() - started, 3)  # run creation: configuration hashing and manifest
    return full, run


def usable_briefing(run_dir, fixture_root=None):
    """The generated briefing loaded through the real dashboard API (FastAPI test client, network disabled, throwaway
    decision store): the brief, every card, every cited source, every related Slack thread and the review queue must
    load. Read-only; nothing in the run directory changes."""
    import tempfile
    from fastapi.testclient import TestClient
    from threadsense.dashboard.app import create_app
    from threadsense.dashboard.decisions import DecisionStore
    from threadsense.dashboard.runs import Catalog
    from threadsense.execution.guard import Execution, Guard
    from urllib.parse import quote
    run_dir = Path(run_dir)
    if not (run_dir/'stages'/'agent3'/'overnight_run'/'morning_brief.json').is_file():
        return {'usable': False, 'reason': 'no Agent 3 briefing was written'}
    with tempfile.TemporaryDirectory(dir='D:/tsb' if Path('D:/tsb').is_dir() else None, ignore_cleanup_errors=True) as tmp:
        ex = Execution(Path(tmp)/'render', mode='REPLAY', limit_usd=0.0)
        try:
            with Guard(ex):
                client = TestClient(create_app(catalog=Catalog([run_dir/'stages'/'agent3']), store=DecisionStore(Path(tmp)/'d.sqlite3'),
                                               decision_origin='TEST', static_dir=Path(tmp)/'none',
                                               fixture_root=fixture_root or run_dir/'snapshot'/'slack'))
                base = '/api/runs/overnight_run'
                brief = client.get(f'{base}/brief')
                items = brief.json().get('cards', []) if brief.status_code == 200 else []
                cards, sources, threads, missing = {}, {}, {}, []
                for item in items:
                    cid = item['card']['card_id']
                    cards[cid] = client.get(f'{base}/cards/{cid}').status_code
                    for e in item.get('cited_evidence') or []:
                        if e.get('missing_from_ledger'):
                            missing.append((cid, e['evidence_id']))
                        sources[e['evidence_id']] = client.get(f"{base}/evidence/{quote(e['evidence_id'], safe='')}").status_code
                    for t in item['card'].get('related_threads') or []:
                        key = f"{t['channel_id']}/{t['thread_id']}"
                        threads[key] = client.get(f'{base}/threads/{key}').status_code
                queue = client.get(f'{base}/review-queue')
        finally:
            ex.close()
    report = {'brief_status': brief.status_code, 'cards': len(cards), 'card_lines': {},
              'card_endpoints_ok': sum(s == 200 for s in cards.values()), 'cited_sources': len(sources),
              'cited_sources_resolved': sum(s == 200 for s in sources.values()), 'cited_missing_from_ledger': missing,
              'related_threads': len(threads), 'related_threads_resolved': sum(s == 200 for s in threads.values()),
              'review_queue_status': queue.status_code,
              'review_queue_items': len(queue.json().get('items', [])) if queue.status_code == 200 else None}
    for item in items:
        line = item['card']['card_line']
        report['card_lines'][line] = report['card_lines'].get(line, 0) + 1
    report['usable'] = (brief.status_code == 200 and report['cards'] > 0 and report['card_endpoints_ok'] == report['cards']
                        and report['cited_sources_resolved'] == report['cited_sources'] and not missing
                        and report['related_threads_resolved'] == report['related_threads'] and queue.status_code == 200)
    return report


def go(run):
    """Execute the pipeline, then load the briefing through the dashboard. Timing uses time.perf_counter (monotonic):
    each stage function from entry to return; `pipeline` from just before the first stage (snapshot = ingestion) to the
    last stage's return; `usable_briefing_check` is the dashboard load; `ingestion_to_usable_briefing` spans both. Run
    creation (manifest, configuration hashing) happens before and is timed separately as `setup`."""
    import time
    from threadsense.execution.guard import Guard
    from threadsense.execution import pipeline as p
    stale = run.ex.ledger.recover()
    if stale:
        print(f'{len(stale)} request(s) from an interrupted process are UNCERTAIN (charged in full, never resent).')
    timing = {'clock': 'time.perf_counter (monotonic), seconds', 'setup_seconds': SETUP.get('seconds'), 'stages': []}
    originals = dict(p.STAGE_FUNCS)

    def timed(name, fn):
        def inner(run_):
            started, status = time.perf_counter(), 'RAISED'
            try:
                m = fn(run_)
                status = m['status']
                return m
            finally:
                timing['stages'].append({'stage': name, 'seconds': round(time.perf_counter() - started, 3), 'status': status})
        return inner
    p.STAGE_FUNCS.update({k: timed(k, v) for k, v in originals.items()})
    t0 = time.perf_counter()
    result = None
    try:
        with Guard(run.ex) as guard, routes(guard, run.ex):
            result = p.execute(run)
    finally:
        p.STAGE_FUNCS.update(originals)
        timing['pipeline_seconds'] = round(time.perf_counter() - t0, 3)
        p.write_json(run.dir/'ledger_summary.json', run.ex.ledger.summary())
        t1 = time.perf_counter()
        check = usable_briefing(run.dir)
        timing['usable_briefing_check_seconds'] = round(time.perf_counter() - t1, 3)
        timing['ingestion_to_usable_briefing_seconds'] = round(time.perf_counter() - t0, 3) if check.get('usable') else None
        timing['completed_stages'] = result
        attempts = p.read_json(run.dir/'timing.json')['attempts'] if (run.dir/'timing.json').is_file() else []
        p.write_json(run.dir/'timing.json', {'attempts': attempts + [timing]})
        p.write_json(run.dir/'usable_briefing.json', check)
    print(json.dumps({'stages': result, 'ledger': run.ex.ledger.summary(), 'timing': timing, 'usable_briefing': check},
                     indent=1, ensure_ascii=False))
    return 0 if all(r.get('status', 'COMPLETE') == 'COMPLETE' for r in result) and len(result) == len(run.stages) else 1


SETUP = {}


def inside_runs(path):
    path = Path(path).resolve()
    if RUNS.resolve() not in path.parents:
        raise SystemExit(f'Runs of this experiment are written under {RUNS.relative_to(ROOT)}/ only.')
    return path


def require_credentials(arm):
    """Run A sends Sonnet (the ant profile through the SDK); Run B sends Grok only (XAI_API_KEY)."""
    if arm == 'sonnet':
        try:
            D.anthropic_client()
        except BaseException as error:  # noqa: BLE001 - reported, nothing sent
            raise SystemExit(f'Anthropic client unavailable ({type(error).__name__}: {error}); run `ant auth login`. Nothing was sent.')
    elif arm == 'gpt':
        from dotenv import dotenv_values
        from threadsense.config import ENV_FILE
        if not (os.environ.get('OPENAI_API_KEY') or dotenv_values(ENV_FILE, encoding='utf-8-sig').get('OPENAI_API_KEY') or '').strip():
            raise SystemExit('OPENAI_API_KEY is missing; nothing was sent.')
    elif not XAI_KEY[0].startswith('xai-'):
        raise SystemExit('XAI_API_KEY in .env is missing; nothing was sent.')


def live(args):
    if not args.run:
        raise SystemExit('Add --run for a paid run (nothing was sent).')
    configure(args.arm)
    require_credentials(args.arm)
    full, run = start(inside_runs(args.write), 'LIVE', args.max_cost, args.arm)
    return go(run)


def branch(args):
    if not args.run:
        raise SystemExit('Add --run for a paid run (nothing was sent).')
    configure('grok')
    require_credentials('grok')
    source = inside_runs(args.source)
    full, run = start(inside_runs(args.write), 'LIVE', args.max_cost, 'grok', parents=(source,), label='BRANCH')
    code = go(run)
    print(json.dumps(handoff_identity(source, run.dir), indent=1))
    return code


def agent3_only(args):
    """Agent 3 alone on a source run's persisted handoff (its exact agent2 output, consolidation and processing
    history, snapshot fixture), with the same stage code as the full run (pipeline.stage_agent3): one ledger with its
    own hard ceiling, the existing guard, the route allowlist, no parent runs (no response reuse at all), monotonic
    timing and the dashboard briefing check."""
    import hashlib
    import time
    from threadsense.agents import advisor_pilot as pilot, overnight
    from threadsense.execution import pipeline as p
    from threadsense.execution.guard import Guard
    if not args.run:
        raise SystemExit('Add --run for a paid run (nothing was sent).')
    configure(args.arm)
    require_credentials(args.arm)
    stream = stream_grok(args)
    source, path = inside_runs(args.source), inside_runs(args.write)
    if path.exists():
        raise SystemExit(f'{path} exists; every run writes a new directory.')
    src = p.Run(source, None)
    inputs = {'handoff': src.output('agent2'), 'consolidation': src.output('agent2_consolidate')/'consolidation.json',
              'processing_history': src.output('agent1_relevance')/'processing_history.json', 'fixture_root': source/'snapshot'/'slack'}
    started = time.perf_counter()
    configuration = p.configuration(p.PIPELINE_V2)
    configuration['agent3_only'] = {'source_run': source.relative_to(ROOT).as_posix(),
                                    'inputs': {k: {'path': v.relative_to(ROOT).as_posix(),
                                                   'sha256': p.tree_hash(v) if v.is_dir() else hashlib.sha256(v.read_bytes()).hexdigest()}
                                               for k, v in inputs.items()},
                                    'delivery_timeout_seconds': pilot.REQUEST_TIMEOUT_SECONDS if args.arm == 'gpt' else D.TIMEOUT_SECONDS, 'response_reuse': 'none (no parent runs)'}
    if stream:
        configuration['agent3_only']['xai_transport'] = stream
    path.mkdir(parents=True)
    p.write_json(path/'run_manifest.json', {'kind': 'AGENT3_ONLY', 'mode': 'LIVE', 'parents': [], 'created_at': p.now(),
                                            'hard_ceiling_usd': args.max_cost, 'configuration': configuration, 'checkout': p.checkout()})
    run = open_routed(path, 'LIVE', limit=args.max_cost, parents=(), arm=args.arm)
    setup = round(time.perf_counter() - started, 3)
    for k, v in pilot.QUIET_ENV.items():
        os.environ.setdefault(k, v)
    out = path/'stages'/'agent3'/'overnight_run'
    timing = {'clock': 'time.perf_counter (monotonic), seconds', 'setup_seconds': setup}
    t0, status, error = time.perf_counter(), 'RAISED', None
    try:
        runner = p.load_script('run_agent3_overnight')
        per_request = p.agent3_reservation()
        budget = round(run.ex.ledger.limit_usd - run.ex.ledger.committed_usd() - per_request, 4)
        with Guard(run.ex) as guard, routes(guard, run.ex), run.ex.stage('agent3', 'agent3'):
            rt = runner.build_runtime(out, 'LIVE', cutoff=CUTOFF, only=None, max_requests=None, max_cost=budget,
                                      handoff=inputs['handoff'], fixture_root=inputs['fixture_root'], per_request=per_request,
                                      index_dir=INDEX, consolidation=inputs['consolidation'],
                                      processing_history=inputs['processing_history'])
            state = overnight.run(rt)
        brief = p.read_json(out/'morning_brief.json')
        status = 'COMPLETE' if brief['accounting']['status'] == 'COMPLETE' and not brief.get('incomplete_work') else 'STOPPED'
        timing['graph_state'] = {k: state.get(k) for k in ('status', 'cursor', 'total', 'stop_reason')}
        timing['agent3_budget_usd'], timing['per_request_reservation_usd'] = budget, per_request
    except BaseException as e:  # noqa: BLE001 - recorded, then re-raised
        error = f'{type(e).__name__}: {str(e)[:500]}'
        raise
    finally:
        timing['stages'] = [{'stage': 'agent3', 'seconds': round(time.perf_counter() - t0, 3), 'status': status, 'error': error}]
        p.write_json(path/'ledger_summary.json', run.ex.ledger.summary())
        t1 = time.perf_counter()
        check = usable_briefing(path, fixture_root=inputs['fixture_root'])
        timing['usable_briefing_check_seconds'] = round(time.perf_counter() - t1, 3)
        p.write_json(path/'timing.json', {'attempts': [timing]})
        p.write_json(path/'usable_briefing.json', check)
        run.ex.close()
    print(json.dumps({'status': status, 'ledger': p.read_json(path/'ledger_summary.json'), 'timing': timing, 'usable_briefing': check},
                     indent=1, ensure_ascii=False))
    return 0 if status == 'COMPLETE' else 1


GROK_RESERVATION_OUTPUT_MULTIPLIER = 2  # xAI does not count reasoning within max_tokens (probe: 18,578 output on a 16,384 cap)


def stream_grok(args):
    """--xai-stream (Grok only): streamed delivery and a reservation that covers reasoning beyond max_tokens."""
    if not getattr(args, 'xai_stream', False):
        return None
    if args.arm != 'grok':
        raise SystemExit('--xai-stream applies to the grok arm only.')
    from threadsense.execution import pricing
    D.XAI_STREAM[0] = True
    base = pricing.reservation

    def reservation(model, input_tokens, output_cap):
        if (model or '').split('/', 1)[-1] in ('grok-4.7', 'x-ai/grok-4.7') or model == 'grok-4.7':
            output_cap *= GROK_RESERVATION_OUTPUT_MULTIPLIER
        return base(model, input_tokens, output_cap)
    pricing.reservation = reservation
    return {'stream': True, 'stream_options': {'include_usage': True}, 'response_stored': 'assembled chat.completion JSON',
            'reservation_output_multiplier': GROK_RESERVATION_OUTPUT_MULTIPLIER,
            'reason': 'diagnostics/grok_probe_v1: completed responses were lost on idle non-streamed connections'}


def resume(args):
    """Continue an interrupted experiment run under its own arm, configuration check and route allowlist (the standard
    runner's resume refuses these runs: their configuration differs from the default models and inputs)."""
    from threadsense.execution import pipeline as p
    path = inside_runs(args.run_dir)
    saved = p.read_json(path/'run_manifest.json')
    arm = saved['configuration']['experiment']['arm']
    configure(arm)
    require_credentials(arm)
    if saved['configuration'] != p.configuration(saved['configuration']['pipeline']):
        raise SystemExit('Configuration changed since this run started (inputs, models, prompts or freeze); start a new run.')
    current = p.checkout()
    if saved['checkout']['combined_sha256'] != current['combined_sha256'] or saved.get('resumes'):
        saved.setdefault('resumes', []).append({'at': p.now(), 'checkout': current, 'reason': args.reason or 'not given'})
        p.write_json(path/'run_manifest.json', saved)
    return go(open_routed(path, saved['mode'], limit=saved['hard_ceiling_usd'], parents=[Path(x) for x in saved['parents']], arm=arm))


def handoff_identity(a, b):
    """Run B must advise Run A's exact Agent 2 handoff: compare the stage outputs that Agent 3 reads."""
    from threadsense.execution.pipeline import read_json
    out = {}
    for stage in ('agent2', 'agent2_consolidate', 'agent1_relevance'):
        ma, mb = (read_json(x/'stages'/stage/'stage_manifest.json') for x in (a, b))
        out[stage] = {'run_a': ma['output_tree_sha256'], 'run_b': mb['output_tree_sha256'],
                      'identical': ma['output_tree_sha256'] == mb['output_tree_sha256']}
    return {'handoff_identity': out}


def ledger(args):
    """Models and providers that answered, from the ledger and the saved raw responses."""
    import sqlite3
    from collections import Counter
    path = Path(args.run_dir)
    con = sqlite3.connect(f"file:{(path/'ledger.sqlite3').as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute('select * from requests').fetchall()
    con.close()
    seen = Counter((r['stage'], r['origin'].split(':')[0], r['state'], r['endpoint'].split('/')[2], r['model'], r['returned_model'],
                    r['http_status']) for r in rows)
    report = [dict(zip(('stage', 'origin', 'state', 'host', 'requested_model', 'returned_model', 'http_status', 'rows'), (*k, n)))
              for k, n in sorted(seen.items(), key=str)]
    hosts = Counter(r['endpoint'].split('/')[2] for r in rows)
    tokens = {}
    for r in rows:  # Provider-reported usage of requests this run sent (reused rows are counted in their own run).
        if r['origin'] != 'FRESH_LIVE' or not r['usage'] or not json.loads(r['usage']):
            continue
        u = json.loads(r['usage'])
        t = tokens.setdefault(r['stage'], Counter())
        t['requests'] += 1
        t['input'] += u.get('input_tokens', u.get('prompt_tokens')) or 0
        t['output'] += u.get('output_tokens', u.get('completion_tokens')) or 0
        t['cache_read'] += (u.get('cache_read_input_tokens') or (u.get('prompt_tokens_details') or {}).get('cached_tokens') or 0)
        t['cache_write'] += u.get('cache_creation_input_tokens') or 0
        t['reasoning'] += (u.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
    states = Counter(r['state'] for r in rows)
    print(json.dumps({'rows': report, 'endpoint_hosts': dict(hosts), 'states': dict(states),
                      'failed_or_uncertain': [{k: r[k] for k in ('stage', 'state', 'http_status', 'error')} for r in rows
                                              if r['state'] not in ('SETTLED', 'REUSED') or (r['http_status'] or 200) >= 300],
                      'rows_outside_delivery_hosts': sum(r['endpoint'].split('/')[2] not in DELIVERY_HOSTS for r in rows),
                      'openai_rows': sum('openai' in (r['endpoint'] or '') or 'gpt-' in (r['model'] or '') for r in rows),
                      'tokens_by_stage': {k: dict(v) for k, v in tokens.items()},
                      'charged_usd': round(sum(r['charged_usd'] or 0 for r in rows), 6),
                      'by_stage_usd': {s: round(sum(r['charged_usd'] or 0 for r in rows if r['stage'] == s), 6)
                                       for s in sorted({r['stage'] for r in rows})},
                      'by_host_usd': {h: round(sum(r['charged_usd'] or 0 for r in rows if r['endpoint'].split('/')[2] == h), 6)
                                      for h in hosts},
                      'hard_ceiling_usd': json.loads((path/'run_manifest.json').read_text(encoding='utf-8')).get('hard_ceiling_usd')},
                     indent=1))
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    pf = sub.add_parser('preflight')
    pf.add_argument('--arm', choices=sorted(ARMS), action='append')
    pf.add_argument('--count-tokens', action='store_true', help='Free Anthropic token count of one translated request.')
    lv = sub.add_parser('live')
    lv.add_argument('--arm', choices=('sonnet', 'gpt'), default='sonnet')
    lv.add_argument('--write', type=Path, required=True)
    lv.add_argument('--run', action='store_true')
    lv.add_argument('--max-cost', type=float, required=True)
    br = sub.add_parser('branch')
    br.add_argument('--source', type=Path, required=True)
    br.add_argument('--write', type=Path, required=True)
    br.add_argument('--run', action='store_true')
    br.add_argument('--max-cost', type=float, required=True)
    rs = sub.add_parser('resume')
    rs.add_argument('run_dir', type=Path)
    rs.add_argument('--reason')
    a3 = sub.add_parser('agent3')
    a3.add_argument('--arm', choices=sorted(ARMS), required=True)
    a3.add_argument('--source', type=Path, required=True)
    a3.add_argument('--write', type=Path, required=True)
    a3.add_argument('--run', action='store_true')
    a3.add_argument('--max-cost', type=float, required=True)
    a3.add_argument('--xai-stream', action='store_true', help='Grok only: streamed delivery (see delivery.XAI_STREAM).')
    lg = sub.add_parser('ledger')
    lg.add_argument('run_dir', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'preflight':
        from preflight import preflight
        return preflight(args.arm or sorted(ARMS), count_tokens=args.count_tokens)
    return {'live': live, 'branch': branch, 'resume': resume, 'agent3': agent3_only, 'ledger': ledger}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
