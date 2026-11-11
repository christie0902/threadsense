"""FastAPI backend for the morning-brief dashboard. Local only: no model calls, no Slack posting, no endpoints that
execute an approved action. Run artifacts and the knowledge corpus are read; the only writes go to the decision store
(decisions, review actions and AI-quality feedback events, each in its own table).
"""
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from threadsense.agents.advice_contracts import ACTION_LABELS
from threadsense.dashboard import feedback as fb
from threadsense.dashboard import lessons as ls
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


def create_app(*, catalog=None, store=None, fixture_root=FIXTURE_ROOT, clock=now_iso, static_dir=WEB_DIST,
               decision_origin='TL_DASHBOARD', session_actor=None):
    """decision_origin: TL_DASHBOARD for a team lead's own decisions; demo scripts and tests pass DEMO_SCRIPT or TEST
    so their simulated decisions stay out of operational snapshots even on a live run's cards.

    session_actor: the team lead this server acts for (the runner always sets it). Only that team lead is offered to
    the UI and only that ID may record decisions or review actions; None leaves the API open to every recorded team
    lead (backend tests). Local identity only: there is still no authentication."""
    catalog = catalog or Catalog()
    store = store or DecisionStore()
    actors = {a['actor_id']: a for a in team_leads(fixture_root)}
    if session_actor is not None:
        if session_actor not in actors:
            raise ValueError(f'{session_actor} is not a recorded team lead.')
        actors = {session_actor: actors[session_actor]}
    app = FastAPI(title='ThreadSense morning brief', docs_url='/api/docs', openapi_url='/api/openapi.json')

    @app.exception_handler(RunNotFound)
    async def not_found(_, error):
        return JSONResponse({'code': 'NOT_FOUND', 'detail': str(error).strip("'")}, status_code=404)

    def run_of(run_key):
        return catalog.get(run_key)

    def card_state(run, card_id):
        history = store.history('card', run.ref, card_id)
        return {'decisions': history, 'head': history[-1] if history else None,
                'indexing': store.indexing({e['entry_id'] for e in history})}

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'store': str(store.path), 'runs': len(catalog.runs), 'decision_origin': decision_origin,
                'session_actor': session_actor}

    @app.get('/api/runs')
    def runs():
        return {'runs': catalog.summaries(), 'actors': list(actors.values()),
                'session': actors[session_actor] if session_actor else None}

    @app.get('/api/runs/{run_key}/brief')
    def brief(run_key: str):
        run = run_of(run_key)
        b = run.brief
        decided = {e['card_id'] for e in store.history('card', run.ref)}
        reports = [fb.fold(h) for h in fb.grouped(store.feedback(run.ref)).values()]
        per_card = {}
        for v in reports:
            per_card[v['report']['card_id']] = per_card.get(v['report']['card_id'], 0) + 1
        return {
            'run': run.summary(catalog.runs.values()), 'counts': b['counts'], 'validation_baseline': b['validation_baseline'],
            'scope': {k: v for k, v in (b.get('scope') or {}).items() if k != 'out_of_scope_work'},
            'incomplete_work': b.get('incomplete_work') or [], 'projection_gaps': b.get('projection_gaps') or [],
            'announcements_in_window': b.get('announcements_in_window') or [], 'usage_totals': (b.get('usage') or {}).get('totals'),
            'accounting': b.get('accounting'), 'briefing_markdown': _briefing(run.path),
            'topics': run.topic_summary(),
            'cards': [{'card': card, 'semantic_source': run.semantic_source(card_id),
                       'alternatives': run.alternatives(card_id), 'allowed_decisions': KINDS_BY_LINE[card['card_line']],
                       'cited_evidence': run.cited_evidence(card_id), 'review': run.review(card_id),
                       'presentation': run.presentation(card_id), 'activity': run.activity(card_id),
                       'display_title': run.display_title(card_id), 'resolved': card_id in decided,
                       'feedback_reports': per_card.get(card_id, 0),
                       'reviewer_context_sent': len((run.reviewer_feedback(card_id) or {}).get('sent') or [])}
                      for card_id, card in run.cards.items()],
            'action_labels': ACTION_LABELS, 'feedback_counts': fb.counts(reports, run.reviewer_feedback_used()),
        }

    @app.get('/api/runs/{run_key}/cards/{card_id}')
    def card(run_key: str, card_id: str):
        run = run_of(run_key)
        c = run.card(card_id)
        topic = run.topics.get(card_id) or {}
        result = topic.get('result') or {}
        return {'card': c, 'semantic_source': run.semantic_source(card_id), 'alternatives': run.alternatives(card_id),
                'allowed_decisions': KINDS_BY_LINE[c['card_line']], 'evidence': run.evidence(card_id), 'review': run.review(card_id),
                'presentation': run.presentation(card_id),
                'display_title': run.display_title(card_id),
                'decision_state': card_state(run, card_id),
                'details': {'work_item': topic.get('work_item'), 'workflow': topic.get('workflow'),
                            'checks': c['checks'], 'needs_review_reasons': c['needs_review_reasons'],
                            'lineage': c['lineage'], 'confidence': c['confidence'], 'confidence_band': c['confidence_band'],
                            'severity': c['severity'], 'inherited_flags': c['inherited_flags'],
                            'diagnostics': result.get('diagnostics'), 'coverage_issues': result.get('coverage_issues'),
                            'action_notes': result.get('action_notes'), 'tot_status': (result.get('tot') or {}).get('status'),
                            'action_candidate': run.action_candidate(card_id)}}

    @app.get('/api/runs/{run_key}/cards/{card_id}/flags')
    def card_flags(run_key: str, card_id: str):
        """Upstream provenance of each inherited flag and what it references on the card (derived, read-only)."""
        return {'flags': run_of(run_key).flags(card_id)}

    @app.get('/api/runs/{run_key}/evidence/{evidence_id:path}')
    def evidence(run_key: str, evidence_id: str):
        return run_of(run_key).evidence_entry(evidence_id)

    @app.get('/api/runs/{run_key}/threads/{channel_id}/{thread_id}')
    def thread(run_key: str, channel_id: str, thread_id: str):
        return thread_view(run_of(run_key), channel_id, thread_id, fixture_root)

    @app.get('/api/runs/{run_key}/decisions')
    def decisions(run_key: str):
        run = run_of(run_key)
        history = store.history('card', run.ref)
        return {'decisions': history, 'indexing': store.indexing({e['entry_id'] for e in history}),
                'run_instance': run.instance, 'rows_for_other_instances': store.other_instances(run.key, run.ref)}

    @app.get('/api/runs/{run_key}/review-queue')
    def review_queue(run_key: str):
        run = run_of(run_key)
        actions = store.history('review', run.ref)
        lesson_views = ls.views(store.lessons())
        items = []
        for item_id, item in run.queue.items():
            mine = [a for a in actions if a['item_id'] == item_id]
            current = review_item_with_actions(item, mine)
            items.append({'item': current.model_dump(mode='json'), 'review_state': current.review_state,
                          'entries': mine, 'head': mine[-1] if mine else None,
                          'lesson_agent': ls.ORIGIN_AGENT.get(item.origin),
                          'lessons': [v for v in lesson_views if v['lesson']['origin']['item_id'] == item_id
                                      and v['head']['run_key'] == run.ref]})
        return {'items': items}

    def _key(value):
        import re
        if not value or not re.fullmatch(KEY_PATTERN, value):
            raise HTTPException(428, {'code': 'IDEMPOTENCY_KEY_REQUIRED',
                                      'detail': 'Send an Idempotency-Key header (8-128 letters, digits, - _ : .).'})
        return value

    def _session_check(actor_id):
        if session_actor is not None and actor_id != session_actor:
            return JSONResponse({'code': 'NOT_SESSION_USER',
                                 'detail': f'This dashboard records decisions for {session_actor} only.'}, status_code=403)
        return None

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
        if refused := _session_check(parsed.actor_id):
            return refused

        def build(head, sequence, digest):
            return build_decision(run=run, card=card, request=parsed, actors=actors, sequence=sequence, head=head,
                                  recorded_at=clock(), key=key, request_sha=digest, alternatives=run.alternatives(card_id),
                                  decision_origin=decision_origin)

        def index_row(db, entry):
            document = ingest(entry)  # Refuses a decision that would not survive normalization.
            db.execute('INSERT INTO indexing VALUES (?,?,?,?,?,?,?,?,?)',
                       (entry['entry_id'], document['document_id'], document['version_id'],
                        f"{authoring_id(entry)}@1", 'PENDING', None, None, None, entry['recorded_at']))

        return _submit(kind='card', run_key=run.ref, target_id=card_id, key=key, body=parsed.model_dump(mode='json'),
                       build=build, on_insert=index_row)

    @app.post('/api/runs/{run_key}/review-items/{item_id}/actions')
    async def review_action(run_key: str, item_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        key = _key(idempotency_key)
        run = run_of(run_key)
        if item_id not in run.queue:
            raise RunNotFound(f'Review item {item_id} is not in run {run.key}.')
        try:
            parsed = ReviewRequest.model_validate(await _json(request))
            lesson = ls.LessonInput.model_validate(parsed.lesson) if parsed.lesson is not None else None
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_DECISION', 'detail': _message(error)}, status_code=422)
        if refused := _session_check(parsed.actor_id):
            return refused
        if lesson is not None and parsed.action != 'REJECT':
            return JSONResponse({'code': 'INVALID_DECISION', 'detail': 'A lesson is saved only with a rejection.'}, status_code=422)

        def build(head, sequence, digest):
            return build_review_action(run=run, item=run.queue[item_id], request=parsed, actors=actors, sequence=sequence,
                                       head=head, recorded_at=clock(), key=key, request_sha=digest,
                                       decision_origin=decision_origin)

        def save_lesson(db, entry):  # Same transaction as the rejection: both are saved or neither.
            event = ls.from_rejection(run=run, item=run.queue[item_id], review_entry=entry, lesson=lesson, actors=actors,
                                      key=key, request_sha=entry['request_sha256'])
            store.insert_lesson_event(db, event)
            return {'lesson': event}

        body = parsed.model_dump(mode='json', exclude={'lesson'} if lesson is None else None)
        return _submit(kind='review', run_key=run.ref, target_id=item_id, key=key, body=body, build=build,
                       on_insert=save_lesson if lesson is not None else None)

    @app.get('/api/lessons')
    def lessons():
        """Every lesson from human review (all runs), newest first, with its history and originating review item."""
        views = ls.views(store.lessons())
        return {'lessons': views, 'counts': {s: sum(v['state'] == s for v in views) for s in ('ACTIVE', 'INACTIVE', 'SUPERSEDED')},
                'categories': {a: list(c) for a, c in ls.CATEGORIES.items()}}

    def lesson_events(lesson_id):
        events = store.lessons(lesson_id)
        if not events:
            raise RunNotFound(f'No lesson {lesson_id}.')
        return events

    @app.post('/api/lessons/{lesson_id}/actions')
    async def lesson_action(lesson_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        key = _key(idempotency_key)
        events = lesson_events(lesson_id)
        try:
            parsed = ls.LessonActionRequest.model_validate(await _json(request))
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_LESSON', 'detail': _message(error)}, status_code=422)
        if refused := _session_check(parsed.actor_id):
            return refused

        def build(head, sequence, digest):
            return ls.action_event(head=head, request=parsed, actors=actors, sequence=sequence, recorded_at=clock(), key=key,
                                   request_sha=digest)

        return _submit(kind='lesson', run_key=events[0]['run_key'], target_id=lesson_id, key=key,
                       body=parsed.model_dump(mode='json'), build=build)

    @app.post('/api/lessons/{lesson_id}/supersede')
    async def lesson_supersede(lesson_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        """Save an edited version as a new lesson; the earlier one becomes SUPERSEDED (one transaction, history kept)."""
        key = _key(idempotency_key)
        earlier = lesson_events(lesson_id)
        try:
            parsed = ls.SupersedeRequest.model_validate(await _json(request))
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_LESSON', 'detail': _message(error)}, status_code=422)
        if refused := _session_check(parsed.actor_id):
            return refused
        new_id = ls.lesson_id_for(earlier[0]['run_key'], f'supersedes:{lesson_id}', key)
        pending = {}

        def build(head, sequence, digest):
            saved, old = ls.superseding(earlier=earlier, request=parsed, actors=actors, recorded_at=clock(), key=key,
                                        request_sha=digest, new_id=new_id)
            pending['old'] = old
            return ls.LessonEvent.model_validate(saved)

        def replace(db, entry):  # The earlier lesson must still be at the head the team lead edited.
            current = store.lessons_in_tx(db, lesson_id)[-1]
            if current['entry_id'] != parsed.expected_head:
                raise StaleHead(current)
            store.insert_lesson_event(db, pending['old'])
            return {'superseded': pending['old']}

        body = {**parsed.model_dump(mode='json', exclude={'expected_head'}), 'replaces': lesson_id,
                'replaces_head': parsed.expected_head}
        return _submit(kind='lesson', run_key=earlier[0]['run_key'], target_id=new_id, key=key, body=body, build=build,
                       on_insert=replace)

    def feedback_view(run, card_id=None):
        views = [fb.fold(h) for h in fb.grouped(store.feedback(run.ref)).values()]
        views = [v for v in views if card_id is None or v['report']['card_id'] == card_id]
        return sorted(views, key=lambda v: v['report']['submitted_at'], reverse=True)

    def reviewer_context(run, card_id):
        """The corrections this card's requests received (from its saved topic result), with their text from the store."""
        record = run.reviewer_feedback(card_id)
        if not record:
            return None
        def described(x):
            view = fb.fold(store.feedback(feedback_id=x['feedback_id']))
            r = view and view['report']
            return {**x, **({'what_is_wrong': r['what_is_wrong'], 'correction': r['suggested_correction'],
                             'state_now': view['state'], 'origin_topic': r['topic_name']} if r else {'state_now': None})}
        return {**record, 'sent': [described(x) for x in record['sent']]}

    @app.get('/api/runs/{run_key}/cards/{card_id}/feedback')
    def card_feedback(run_key: str, card_id: str):
        run = run_of(run_key)
        run.card(card_id)
        return {'targets': fb.targets(run, card_id), 'categories': fb.CATEGORY_LABELS,
                'problems': {k: list(v) for k, v in fb.PROBLEMS.items()}, 'history': feedback_view(run, card_id),
                'reviewer_context': reviewer_context(run, card_id),
                'limits': {'min_correction': fb.MIN_CORRECTION, 'max_scope_threads': fb.MAX_SCOPE_THREADS,
                           'max_text': fb.MAX_TEXT}}

    @app.get('/api/runs/{run_key}/feedback')
    def run_feedback(run_key: str):
        run = run_of(run_key)
        views = feedback_view(run)
        return {'items': views, 'counts': fb.counts(views, run.reviewer_feedback_used())}

    @app.post('/api/runs/{run_key}/cards/{card_id}/feedback')
    async def submit_feedback(run_key: str, card_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        """Report an AI issue on this card. Records feedback only: no decision, no review action, no card change."""
        key = _key(idempotency_key)
        run = run_of(run_key)
        card = run.card(card_id)
        try:
            parsed = fb.FeedbackRequest.model_validate(await _json(request))
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_FEEDBACK', 'detail': _message(error)}, status_code=422)
        if refused := _session_check(parsed.actor_id):
            return refused
        feedback_id = fb.feedback_id_for(run, card_id, key)

        def build(head, sequence, digest):
            report = fb.build_report(run=run, card=card, request=parsed, actors=actors, feedback_id=feedback_id,
                                     recorded_at=clock(), history=lambda fid: store.feedback(feedback_id=fid),
                                     origin=decision_origin)
            return fb.submission(run=run, report=report, key=key, request_sha=digest)

        return _submit(kind='feedback', run_key=run.ref, target_id=feedback_id, key=key,
                       body={**parsed.model_dump(mode='json'), 'card_id': card_id}, build=build)

    @app.post('/api/runs/{run_key}/feedback/{feedback_id}/actions')
    async def feedback_action(run_key: str, feedback_id: str, request: Request, idempotency_key: str | None = Header(default=None)):
        """CONFIRM (an authorized team lead; makes an opted-in correction eligible for later snapshots) or WITHDRAW."""
        key = _key(idempotency_key)
        run = run_of(run_key)
        if not store.feedback(run.ref, feedback_id):
            raise RunNotFound(f'Feedback {feedback_id} is not recorded on run {run.key}.')
        try:
            parsed = fb.FeedbackActionRequest.model_validate(await _json(request))
        except ValidationError as error:
            return JSONResponse({'code': 'INVALID_FEEDBACK', 'detail': _message(error)}, status_code=422)
        if refused := _session_check(parsed.actor_id):
            return refused

        def build(head, sequence, digest):
            return fb.action_event(head=head, request=parsed, actors=actors, sequence=sequence, recorded_at=clock(), key=key,
                                   request_sha=digest)

        return _submit(kind='feedback', run_key=run.ref, target_id=feedback_id, key=key, body=parsed.model_dump(mode='json'),
                       build=build, on_insert=lambda db, entry: fb.supersede_on_confirm(store, db, entry, store.feedback_in_tx))

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
