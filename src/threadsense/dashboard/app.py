"""FastAPI backend for the morning-brief dashboard. Local only: no model calls, no Slack posting, no endpoints that
execute an approved action. Run artifacts and the knowledge corpus are read; the only writes go to the decision store.
"""
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from threadsense.agents.advice_contracts import ACTION_LABELS
from threadsense.dashboard.decision_sources import authoring_id, ingest
from threadsense.dashboard.decisions import (
    KINDS_BY_LINE, DecisionError, DecisionRequest, DecisionStore, KeyReused, ReviewRequest, StaleHead,
    build_decision, build_review_action, now_iso, review_item_with_actions,
)
from threadsense.dashboard.runs import Catalog, RunNotFound, team_leads, thread_view
from threadsense.retrieval.config import FIXTURE_ROOT
from threadsense.routing import ROOT

WEB_DIST = ROOT/'web/dist'
KEY_PATTERN = r'^[A-Za-z0-9_\-:.]{8,128}$'


def create_app(*, catalog=None, store=None, fixture_root=FIXTURE_ROOT, clock=now_iso, static_dir=WEB_DIST):
    catalog = catalog or Catalog()
    store = store or DecisionStore()
    actors = {a['actor_id']: a for a in team_leads(fixture_root)}
    app = FastAPI(title='ThreadSense morning brief', docs_url='/api/docs', openapi_url='/api/openapi.json')

    @app.exception_handler(RunNotFound)
    async def not_found(_, error):
        return JSONResponse({'code': 'NOT_FOUND', 'detail': str(error).strip("'")}, status_code=404)

    def run_of(run_key):
        return catalog.get(run_key)

    def card_state(run, card_id):
        history = store.history('card', run.key, card_id)
        return {'decisions': history, 'head': history[-1] if history else None,
                'indexing': store.indexing({e['entry_id'] for e in history})}

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'store': str(store.path), 'runs': len(catalog.runs)}

    @app.get('/api/runs')
    def runs():
        return {'runs': catalog.summaries(), 'actors': list(actors.values())}

    @app.get('/api/runs/{run_key}/brief')
    def brief(run_key: str):
        run = run_of(run_key)
        b = run.brief
        decided = {e['card_id'] for e in store.history('card', run.key)}
        return {
            'run': run.summary(catalog.runs.values()), 'counts': b['counts'], 'validation_baseline': b['validation_baseline'],
            'scope': {k: v for k, v in (b.get('scope') or {}).items() if k != 'out_of_scope_work'},
            'incomplete_work': b.get('incomplete_work') or [], 'projection_gaps': b.get('projection_gaps') or [],
            'announcements_in_window': b.get('announcements_in_window') or [], 'usage_totals': (b.get('usage') or {}).get('totals'),
            'accounting': b.get('accounting'), 'briefing_markdown': _briefing(run.path),
            'topics': run.topic_summary(),
            'cards': [{'card': card, 'semantic_source': run.semantic_source(card_id),
                       'alternatives': run.alternatives(card_id), 'allowed_decisions': KINDS_BY_LINE[card['card_line']],
                       'cited_evidence': run.cited_evidence(card_id), 'resolved': card_id in decided}
                      for card_id, card in run.cards.items()],
            'action_labels': ACTION_LABELS,
        }

    @app.get('/api/runs/{run_key}/cards/{card_id}')
    def card(run_key: str, card_id: str):
        run = run_of(run_key)
        c = run.card(card_id)
        topic = run.topics.get(card_id) or {}
        result = topic.get('result') or {}
        return {'card': c, 'semantic_source': run.semantic_source(card_id), 'alternatives': run.alternatives(card_id),
                'allowed_decisions': KINDS_BY_LINE[c['card_line']], 'evidence': run.evidence(card_id),
                'decision_state': card_state(run, card_id),
                'details': {'work_item': topic.get('work_item'), 'workflow': topic.get('workflow'),
                            'checks': c['checks'], 'needs_review_reasons': c['needs_review_reasons'],
                            'lineage': c['lineage'], 'confidence': c['confidence'], 'confidence_band': c['confidence_band'],
                            'severity': c['severity'], 'inherited_flags': c['inherited_flags'],
                            'diagnostics': result.get('diagnostics'), 'coverage_issues': result.get('coverage_issues'),
                            'action_notes': result.get('action_notes'), 'tot_status': (result.get('tot') or {}).get('status')}}

    @app.get('/api/runs/{run_key}/evidence/{evidence_id:path}')
    def evidence(run_key: str, evidence_id: str):
        return run_of(run_key).evidence_entry(evidence_id)

    @app.get('/api/runs/{run_key}/threads/{channel_id}/{thread_id}')
    def thread(run_key: str, channel_id: str, thread_id: str):
        return thread_view(run_of(run_key), channel_id, thread_id, fixture_root)

    @app.get('/api/runs/{run_key}/decisions')
    def decisions(run_key: str):
        run = run_of(run_key)
        history = store.history('card', run.key)
        return {'decisions': history, 'indexing': store.indexing({e['entry_id'] for e in history})}

    @app.get('/api/runs/{run_key}/review-queue')
    def review_queue(run_key: str):
        run = run_of(run_key)
        actions = store.history('review', run.key)
        items = []
        for item_id, item in run.queue.items():
            mine = [a for a in actions if a['item_id'] == item_id]
            current = review_item_with_actions(item, mine)
            items.append({'item': current.model_dump(mode='json'), 'review_state': current.review_state,
                          'entries': mine, 'head': mine[-1] if mine else None})
        return {'items': items}

    def _key(value):
        import re
        if not value or not re.fullmatch(KEY_PATTERN, value):
            raise HTTPException(428, {'code': 'IDEMPOTENCY_KEY_REQUIRED',
                                      'detail': 'Send an Idempotency-Key header (8-128 letters, digits, - _ : .).'})
        return value

    def _submit(**kwargs):
        try:
            response, replayed = store.submit(**kwargs)
        except StaleHead as error:
            return JSONResponse({'code': 'STALE', 'detail': str(error), 'current_head': error.current}, status_code=409)
        except KeyReused as error:
            return JSONResponse({'code': 'IDEMPOTENCY_KEY_REUSED', 'detail': str(error),
                                 'original_entry_id': error.original['entry']['entry_id']}, status_code=422)
        except (DecisionError, ValidationError, ValueError) as error:
            return JSONResponse({'code': 'INVALID_DECISION', 'detail': _message(error)}, status_code=422)
        return JSONResponse({**response, 'replayed': replayed, 'persisted': True}, status_code=200 if replayed else 201)

    @app.post('/api/runs/{run_key}/cards/{card_id}/decisions')
    async def decide(run_key: str, card_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        key = _key(idempotency_key)
        run = run_of(run_key)
        card = run.card(card_id)
        body = await _json(request)
        try:
            parsed = DecisionRequest.model_validate(body)
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_DECISION', 'detail': _message(error)}, status_code=422)

        def build(head, sequence, digest):
            return build_decision(run=run, card=card, request=parsed, actors=actors, sequence=sequence, head=head,
                                  recorded_at=clock(), key=key, request_sha=digest, alternatives=run.alternatives(card_id))

        def index_row(db, entry):
            document = ingest(entry)  # Refuses a decision that would not survive normalization.
            db.execute('INSERT INTO indexing VALUES (?,?,?,?,?,?,?,?,?)',
                       (entry['entry_id'], document['document_id'], document['version_id'],
                        f"{authoring_id(entry)}@{entry['sequence']}", 'PENDING', None, None, None, entry['recorded_at']))

        return _submit(kind='card', run_key=run.key, target_id=card_id, key=key, body=parsed.model_dump(mode='json'),
                       build=build, on_insert=index_row)

    @app.post('/api/runs/{run_key}/review-items/{item_id}/actions')
    async def review_action(run_key: str, item_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        key = _key(idempotency_key)
        run = run_of(run_key)
        if item_id not in run.queue:
            raise RunNotFound(f'Review item {item_id} is not in run {run.key}.')
        try:
            parsed = ReviewRequest.model_validate(await _json(request))
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_DECISION', 'detail': _message(error)}, status_code=422)

        def build(head, sequence, digest):
            return build_review_action(run=run, item=run.queue[item_id], request=parsed, actors=actors, sequence=sequence,
                                       head=head, recorded_at=clock(), key=key, request_sha=digest)

        return _submit(kind='review', run_key=run.key, target_id=item_id, key=key, body=parsed.model_dump(mode='json'),
                       build=build)

    @app.get('/api/runs/{run_key}/negative-examples')
    def negative_examples(run_key: str):
        """Model-review items whose latest TL action is REJECT, with the upstream obligation verbatim."""
        items = review_queue(run_key)['items']
        return {'items': [{'item': i['item'], 'rejected_by': i['head']['action']} for i in items if i['review_state'] == 'REJECTED']}

    static = Path(static_dir)
    if (static/'index.html').is_file():
        @app.get('/{path:path}', include_in_schema=False)
        def frontend(path: str):
            target = (static/path).resolve()
            if path and target.is_file() and target.is_relative_to(static.resolve()):
                return FileResponse(target)
            if path.startswith('api/'):
                raise HTTPException(404)
            return FileResponse(static/'index.html')

    return app


async def _json(request):
    try:
        return await request.json()
    except json.JSONDecodeError:
        raise HTTPException(400, {'code': 'INVALID_JSON', 'detail': 'The request body is not JSON.'})


def _message(error):
    if isinstance(error, ValidationError):
        return '; '.join(f"{'.'.join(map(str, e['loc'])) or 'request'}: {e['msg']}" for e in error.errors())
    return str(error)


def _briefing(path):
    """The saved readable brief up to its first card section (status, window, counts, scope, incomplete work)."""
    md = (Path(path)/'morning_brief.md')
    if not md.is_file():
        return None
    head = []
    for line in md.read_text(encoding='utf-8').splitlines():
        if line.startswith('## ') and line != '## Incomplete work':
            break
        head.append(line)
    return '\n'.join(head).strip()
