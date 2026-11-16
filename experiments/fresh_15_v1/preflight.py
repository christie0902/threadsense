"""Zero-paid-call preflight for the fresh-15 comparison (called by run_experiment.py preflight).

Checks, in order: frozen inputs and answer key unchanged; the answer key reaches no input, index or run directory;
15 roots = 14 discussions + 1 announcement through the normal ingestion path; the isolated index and its version
states; every enabled model role's effective configuration; then every role's real entry point builds its request,
which is captured at the transport (after the provider pin, under the route allowlist) and never sent. Ends with a
REPLAY smoke run in a temporary directory (network disabled) and the spend estimate.
"""
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import contextlib
import tempfile

import run_experiment as X
import delivery as D

ANSWER_KEY = X.HERE/'answer_key/threadsense_fresh_15_answer_key.md'
# Content and the file name of the answer key (a mention that it is never read is not a leak).
KEY_PHRASES = ('Expected resolution', 'What would fail', 'Seek freezes', 'threadsense_fresh_15_answer_key')


class Captured(BaseException):
    pass


def check_freeze():
    freeze = json.loads((X.HERE/'freeze.json').read_text(encoding='utf-8'))
    changed = {k: 'missing' if not (X.ROOT/k).is_file() else 'changed' for k, v in freeze['files'].items()
               if not (X.ROOT/k).is_file() or X.sha(X.ROOT/k) != v['sha256']}
    unlisted = sorted(p.relative_to(X.ROOT).as_posix() for d in ('inputs', 'source', 'answer_key') for p in (X.HERE/d).rglob('*')
                      if p.is_file() and p.relative_to(X.ROOT).as_posix() not in freeze['files'])
    return {'files': len(freeze['files']), 'changed': changed, 'unlisted_input_files': unlisted, 'ok': not changed and not unlisted}


def check_answer_key_isolation():
    hits = []
    places = [X.HERE/'inputs', X.INDEX, X.HERE/'id_map.json', X.HERE/'convert_fixture.py']
    for place in places:
        for p in ([place] if place.is_file() else place.rglob('*') if place.exists() else []):
            if p.is_file() and p.stat().st_size < 50_000_000:
                text = p.read_bytes().decode('utf-8', 'ignore')
                hits += [(p.relative_to(X.ROOT).as_posix(), k) for k in KEY_PHRASES if k in text]
    manifest = (X.INDEX/'manifest.json').read_text(encoding='utf-8')
    return {'answer_key': ANSWER_KEY.relative_to(X.ROOT).as_posix(), 'outside_inputs_and_index': 'answer_key' not in manifest,
            'phrase_hits_in_inputs_index_converter': hits, 'ok': not hits and 'answer_key' not in manifest}


def check_ingestion():
    from threadsense.source_ingestion import interpretation_threads
    idm = json.loads((X.HERE/'id_map.json').read_text(encoding='utf-8'))
    rev = {v['thread_id']: k for k, v in idm['threads'].items()}
    threads, announcements, routing = interpretation_threads(X.FIXTURE, cutoff=X.CUTOFF, channels=None)
    tid = lambda a: a.get('thread_id') if isinstance(a, dict) else a.thread_id
    out = {'roots': routing['input_threads'], 'discussion': routing['eligible_threads'], 'announcement': routing['announcement_threads'],
           'discussion_ids': sorted(rev[t.thread_id] for t in threads), 'announcement_ids': sorted(rev[tid(a)] for a in announcements)}
    out['ok'] = (out['roots'], out['discussion'], out['announcement'], out['announcement_ids']) == (15, 14, 1, ['T15'])
    return out


def check_index():
    from threadsense.retrieval.search import Retriever
    m = json.loads((X.INDEX/'manifest.json').read_text(encoding='utf-8'))
    r = Retriever(X.INDEX)
    q = 'Do I still add a reviewer note on two-line alignment checks for an archived export?'
    cur = r.search(q, project='multilingual_eval', as_of=X.CUTOFF, version_mode='current')
    hist = r.search(q, project='multilingual_eval', as_of=X.CUTOFF, version_mode='history')
    cite = lambda x: x['citation'].get('authoring') or x['citation']['source'].get('channel_id')
    ann = m['corpus']['current_day_announcements']
    out = {'build_fingerprint': m['build_fingerprint'], 'documents': m['documents'],
           'knowledge_documents': m['corpus']['knowledge_documents'],
           'announcements': {k: ann[k] for k in ('announcement_threads', 'discussion_threads', 'extracted', 'extraction_failures')},
           'sources': {k: m.get(k) for k in ('knowledge_root', 'fixture_root', 'cutoff')
                                                                       if k in m},
           'current': [cite(x) for x in cur['results']],
           'withheld_in_current': [(w['citation']['authoring'], w.get('state')) for w in cur.get('withheld_by_version') or []],
           'history': [cite(x) for x in hist['results']]}
    out['ok'] = ('pilot-multilingual-alignment-review-guide@1.4' not in out['current']
                 and 'pilot-multilingual-alignment-review-guide@1.4' in out['history']
                 and ann['extracted'] == 1 and m['documents'] == 7 and m['corpus']['knowledge_documents'] == 6)
    return out


def role_table(arm):
    from threadsense.execution import pipeline as p
    s = p.load_script('run_agent3_overnight').live_settings()
    a1, a3 = p.ENV['THREADSENSE_MODEL'], s['model']
    return [
        {'role': 'Agent 1 interpreter (CrewAI LLM, one request per thread; relevance judged in the same request)', 'model': a1},
        {'role': 'Agent 1 revision (single-POST transport)', 'model': a1},
        {'role': 'Agent 1 decision-evidence auditor (CrewAI LLM)', 'model': p.ENV['THREADSENSE_VERIFIER_MODEL']},
        {'role': 'Agent 1 source analysis + prose comparison (single-POST transport)', 'model': p.ENV['THREADSENSE_VERIFIER_MODEL']},
        {'role': 'Agent 1 relevance exclusion verifier (single-POST transport)', 'model': p.ENV['THREADSENSE_VERIFIER_MODEL']},
        {'role': 'Agent 2 taxonomy (strict json_schema)', 'model': p.AGENT2_MODEL if arm == 'gpt' else p.ENV['THREADSENSE_MODEL'],
         'note': 'stage override (standard)' if arm == 'gpt' else 'via THREADSENSE_MODEL (see overrides)'},
        {'role': 'Agent 2 consolidation judge (strict json_schema)', 'model': p.AGENT2_MODEL},
        {'role': 'Agent 3 draft / revision / ToT / grounding (CrewAI, json_object)', 'model': a3,
         'settings': {k: s[k] for k in ('temperature', 'reasoning_effort', 'max_completion_tokens_per_call', 'input_token_limit',
                                        'provider_sdk_max_retries', 'model_fallback', 'api_key_variable')}},
        {'role': 'Optional paths', 'model': None, 'note': 'ReAct research off, flag impact off, reviewer feedback off, lessons off; '
                                                         'retries 0 on every transport; no fallback model anywhere'},
    ]


def capture_class():
    base = X.routed_execution_class()
    from threadsense.execution import pricing

    class CaptureExecution(base):
        captured = []

        def execute(self, *, method, url, body, send):
            X.check_route(url, body, self.allowed)
            model, tokens, cap = pricing.body_fields(bytes(body))
            data = json.loads(body)
            self.captured.append({'url': str(url), 'model': model, 'agent': self.agent,
                                  'params': {k: data[k] for k in ('max_tokens', 'temperature', 'thinking', 'reasoning_effort',
                                                                   'stop_sequences', 'stream') if k in data},
                                  'output_config': {k: (v if k != 'format' else {'type': v.get('type'), 'schema': 'present'})
                                                    for k, v in (data.get('output_config') or {}).items()},
                                  'response_format': (data.get('response_format') or {}).get('type'),
                                  'system_chars': len(data.get('system') or ''), 'messages': len(data.get('messages') or []),
                                  'input_tokens_estimate': tokens, 'output_cap': cap,
                                  'reservation_usd': round(pricing.reservation(model, tokens, cap), 5), '_body': data})
            raise Captured()
    return CaptureExecution


@contextmanager
def capturing(arm):
    from threadsense.execution.guard import Guard
    cls = capture_class()
    cls.allowed = frozenset(X.ALLOWED_TO_SEND[arm] | {'claude-sonnet-5-5'})  # Upstream roles are inspected too.
    cls.captured = []
    with tempfile.TemporaryDirectory(dir='D:/tsb' if Path('D:/tsb').is_dir() else None, ignore_cleanup_errors=True) as tmp:
        ex = cls(Path(tmp)/'capture', mode='LIVE', limit_usd=0.0)
        try:
            with Guard(ex) as guard, X.routes(guard, ex):
                yield cls.captured, ex
        finally:
            ex.close()


def capture_roles(arm):
    """Each role's real request builder and transport, translated by delivery.py and stopped at the guard (never sent).
    Returns one captured provider body per role."""
    from threadsense.execution import pipeline as p
    from threadsense.adapters.mock_slack import MockSlackAdapter
    results = []

    def attempt(role, agent, fn):
        before = len(captured)
        error = None
        try:
            with p.environment(p.ENV), ex.stage(role, agent), contextlib.redirect_stdout(io.StringIO()):
                fn()
        except Captured:
            pass
        except X.RouteRefused as e:
            error = f'RouteRefused: {e}'
        except BaseException as e:  # noqa: BLE001 - recorded: a role that fails before building its request
            error = f'{type(e).__name__}: {str(e)[:300]}'
        got = captured[before:]
        results.append({'role': role, 'captured': got[0] if got else None, 'requests_attempted': len(got), 'error': error,
                        'ok': bool(got) and error is None})

    adapter = MockSlackAdapter(str(X.FIXTURE/'channels'), str(X.FIXTURE/'users.json'))
    thread = adapter.get_threads('C_91AUDIO01')[0]
    with capturing(arm) as (captured, ex):
        if arm in ('sonnet', 'gpt'):  # Run C: the same roles on the standard OpenAI plan.
            from threadsense.agents import thread_interpreter, decision_evidence_audit as dea, verification_requests as vr
            from threadsense.agents import topic_requests, topic_merge
            from threadsense import config
            attempt('agent1_interpreter', 'agent1', lambda: thread_interpreter.interpret_thread(thread))
            attempt('agent1_auditor', 'agent1', lambda: dea.create_verifier_llm().call([{'role': 'user', 'content': 'preflight'}]))

            def auditor_transport():  # Resolved inside the run environment, as the verification stage does.
                m, k = dea.get_auditor_model_settings()
                vr.complete_once(m, k, vr.request_body(m, 'preflight', {'preflight': True}, max_tokens=16384))

            def revision_transport():
                m, k = config.get_model_settings()
                vr.complete_once(m, k, vr.request_body(m, 'preflight', {'preflight': True}, max_tokens=4096))

            def taxonomy():
                m, k = (p.AGENT2_MODEL, 'OPENAI_API_KEY') if arm == 'gpt' else config.get_model_settings()  # Run C: the stage's override
                topic_requests.complete_once(m, k, topic_requests.request_body(m, 'preflight', {'p': 1}))
            attempt('agent1_auditor_transport (source analysis, prose comparison, relevance verifier)', 'agent1', auditor_transport)
            attempt('agent1_revision_transport', 'agent1', revision_transport)
            attempt('agent2_taxonomy', 'agent2', taxonomy)
            judge = topic_merge.LiveJudge(p.AGENT2_MODEL)
            attempt('agent2_consolidation_judge', 'agent2', lambda: topic_requests.complete_once(judge.model, judge.key_name,
                                                                                               judge.request({'preflight': True})))
        from threadsense.agents import advisor_pilot as pilot, advisor_contracts
        settings = p.load_script('run_agent3_overnight').live_settings()
        attempt('agent3 (one client serves draft, revision, ToT and grounding)', 'agent3',
                lambda: pilot.CrewAIClient(settings).complete('draft', {'scenario_id': 'preflight', 'rules': 'Preflight only.', 'preflight': True},
                                                              advisor_contracts.AdvisorDraft))
    return results


def count_tokens_check(results):
    """Free Anthropic token counting (no generation) of every translated Sonnet body: checks the request shape (model,
    system, messages, thinking, structured-output schema) against the live API before any paid call, and measures real
    token counts against the o200k estimate."""
    import anthropic
    client = D.anthropic_client()
    out = []
    for r in results:
        body = (r.get('captured') or {}).get('_body')
        if not body or not str(body.get('model', '')).startswith('claude-'):
            continue
        params = {k: v for k, v in body.items() if k not in ('max_tokens', 'stop_sequences')}
        try:
            n = client.messages.count_tokens(**params)
            out.append({'role': r['role'], 'ok': True, 'input_tokens': n.input_tokens,
                        'o200k_estimate_with_margin': r['captured']['input_tokens_estimate']})
        except anthropic.APIStatusError as e:
            out.append({'role': r['role'], 'ok': False, 'http_status': e.status_code, 'error': str(e.message)[:300]})
        except TypeError as e:
            out.append({'role': r['role'], 'ok': False, 'error': f'SDK parameter: {e}'})
    return out


def replay_smoke(arm):
    """A REPLAY run in a temporary directory: the snapshot stage copies the experiment inputs into the run, and the first
    model request is refused (no saved response). Shows the entry wiring and run-directory isolation; spends nothing."""
    from threadsense.execution.guard import Guard, NetworkDisabled
    from threadsense.execution import pipeline as p
    with tempfile.TemporaryDirectory(dir='D:/tsb' if Path('D:/tsb').is_dir() else None, ignore_cleanup_errors=True) as tmp:
        path = Path(tmp)/'runs'/'smoke'
        old = X.RUNS
        X.RUNS = Path(tmp)/'runs'
        run = None
        try:
            full, run = X.start(path, 'REPLAY', 0.0, arm)
            with Guard(run.ex) as guard, X.routes(guard, run.ex), contextlib.redirect_stdout(io.StringIO()):
                try:
                    stages = p.execute(run)
                except (SystemExit, NetworkDisabled) as error:  # Recorded in the stage manifest, then re-raised.
                    stages = [{'stage': 'snapshot', 'status': (run.manifest('snapshot') or {}).get('status')},
                              {'stage': 'agent1_interpret', 'status': 'STOPPED', 'error': type(error).__name__}]
            manifest = json.loads((path/'run_manifest.json').read_text(encoding='utf-8'))
            snap = json.loads((path/'snapshot'/'snapshot_manifest.json').read_text(encoding='utf-8'))
            last = run.manifest(stages[-1]['stage']) or {}
            rows = len(run.ex.ledger.rows())
            return {'stages': stages, 'stopped_with': (last.get('error') or '')[:200], 'ledger_rows': rows,
                    'snapshot_matches_fixture': snap['source_fixture_tree_sha256'] == X.tree(X.FIXTURE),
                    'manifest_experiment_inputs': manifest['configuration']['experiment']['inputs'],
                    'manifest_delivery': manifest['configuration']['experiment']['delivery'],
                    'pipeline': manifest['configuration']['pipeline'],
                    'ok': stages[0] == {'stage': 'snapshot', 'status': 'COMPLETE'} and 'NetworkDisabled' in (last.get('error') or '')
                          and rows == 0}
        finally:
            if run is not None:
                run.ex.close()
            X.RUNS = old


def estimate():
    """Measured per-request usage of threadsense_full_v1 (same stages, other models), scaled for this fixture."""
    tok, verbose, think = 1.25, 1.5, 2.0  # input tokenizer allowance; output verbosity; Agent 3 reasoning output
    s_in, s_out, g_in, g_out = 2.0e-6, 10.0e-6, 2.0e-6, 6.0e-6
    work = {'threads': 14, 'agent1_verify_requests': round(14 * 2.86), 'groups': 8, 'consolidation_sets': 6, 'exclusions': 3,
            'agent3_items': 14, 'agent3_requests': round(14 * 2.3)}
    a = {'agent1_interpret': 14 * (1632 * tok * s_in + 174 * verbose * s_out),
         'agent1_verify': work['agent1_verify_requests'] * (2000 * tok * s_in + 600 * verbose * s_out),
         'agent1_relevance_verifier': 3 * (3000 * tok * s_in + 500 * verbose * s_out),
         'agent2_taxonomy': 8 * (787 * tok * s_in + 138 * verbose * s_out * 2),
         'agent2_consolidation': 6 * (1500 * tok * s_in + 300 * verbose * s_out),
         'agent3': work['agent3_requests'] * (12289 * tok * s_in + 2962 * think * s_out)}
    b = {'agent3': work['agent3_requests'] * (12289 * tok * g_in + 2962 * think * g_out)}
    exposure_a = (14 * (1785 * 1.35 * s_in + 4096 * s_out) + 14 * (43008 * s_out + 4 * 3300 * 1.35 * s_in)
                  + 14 * (4096 * s_out) + 8 * 8192 * s_out + 6 * 8192 * s_out + 56 * (24000 * 1.6 * s_in + 16384 * s_out))
    exposure_b = 56 * (24000 * 1.6 * g_in + 16384 * g_out)
    return {'assumed_work': work, 'basis': 'threadsense_full_v1 ledger means (Agent 1 1.6k/0.2k, verification ~2.0k/0.6k, '
                                           'Agent 2 0.8k/0.14k, Agent 3 12.3k/3.0k tokens per request); input x1.25, output '
                                           'x1.5 (Agents 1-2, thinking off) or x2 (Agent 3, medium reasoning)',
            'run_a_expected_usd': round(sum(a.values()), 2), 'run_a_by_stage_usd': {k: round(v, 3) for k, v in a.items()},
            'run_a_all_limits_hit_usd': round(exposure_a, 2),
            'run_b_expected_usd': round(sum(b.values()), 2), 'run_b_all_limits_hit_usd': round(exposure_b, 2),
            'balances_reported_usd': {'anthropic': 5.0, 'xai': 5.0},
            'proposed_caps_usd': {'run_a': 4.5, 'run_b': 4.5}}


def credentials():
    import anthropic
    out = {'anthropic_sdk': anthropic.__version__, 'anthropic_sdk_expected': D.SDK_VERSION}
    try:
        D.anthropic_client()
        out['anthropic'] = 'ant profile resolved by the SDK (no request made)'
    except BaseException as e:  # noqa: BLE001
        out['anthropic'] = f'UNAVAILABLE: {type(e).__name__}: {str(e)[:200]}'
    out['xai'] = 'XAI_API_KEY present (not printed)' if X.XAI_KEY[0].startswith('xai-') else 'MISSING'
    out['openrouter'] = 'not used (placeholder only; every request is delivered directly)'
    out['ok'] = out['anthropic'].startswith('ant profile') and out['xai'].startswith('XAI') and anthropic.__version__ == D.SDK_VERSION
    return out


def strip(results):
    for r in results:
        if r.get('captured'):
            r['captured'].pop('_body', None)
    return results


def preflight(arms, count_tokens=False):
    report = {'freeze': check_freeze(), 'answer_key_isolation': check_answer_key_isolation(), 'ingestion': check_ingestion()}
    with contextlib.redirect_stderr(io.StringIO()):
        report['index'] = check_index()
    for arm in arms:
        X.configure(arm)
        report[f'{arm}_roles'] = role_table(arm)
        from threadsense.agents import advisor_checks, advisor_evidence
        authors = {m['user'] for p in (X.FIXTURE/'channels').glob('*.json') for t in json.loads(p.read_text(encoding='utf-8'))['history']
                   for m in [t]} | {m['user'] for p in (X.FIXTURE/'channels').glob('*.json')
                                    for ms in json.loads(p.read_text(encoding='utf-8'))['replies'].values() for m in ms}
        missing = sorted(authors - set(advisor_checks.user_directory()) | (authors - set(advisor_evidence.user_directory())))
        report[f'{arm}_agent3_user_directory'] = {'fixture_authors': len(authors), 'missing': missing, 'ok': not missing}
        from threadsense.execution import pipeline as pl
        try:  # The stage's own per-request reservation (stage_agent3 calls this before any request).
            report[f'{arm}_agent3_reservation'] = {'usd': round(pl.agent3_reservation(), 5), 'ok': True}
        except BaseException as e:  # noqa: BLE001
            report[f'{arm}_agent3_reservation'] = {'error': f'{type(e).__name__}: {e}', 'ok': False}
        with contextlib.redirect_stderr(io.StringIO()):
            captured = capture_roles(arm)
        if count_tokens and arm == 'sonnet':
            report['sonnet_count_tokens'] = count_tokens_check(captured)
        report[f'{arm}_captured'] = strip(captured)
        if arm == 'sonnet':
            with contextlib.redirect_stderr(io.StringIO()):
                report['replay_smoke'] = replay_smoke(arm)
    report['credentials'] = credentials()
    report['estimate'] = estimate()
    ok = all(v.get('ok', True) for v in report.values() if isinstance(v, dict)) and all(
        r['ok'] for a in arms for r in report[f'{a}_captured']) and all(r['ok'] for r in report.get('sonnet_count_tokens', []))
    report['preflight_ok'] = ok
    print(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return 0 if ok else 1
