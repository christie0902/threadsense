"""Agent 1 relevance (agent1-relevance-v1): does a discussion thread belong in project analysis?

Relevance is judged in the same interpretation request as the summary (one call, extended schema), checked by a
deterministic verification step, and recorded beside the interpretation. It is kept apart from resolution, severity and
the need to intervene: it never changes those fields.

- PROJECT threads (model behavior, tool incidents, QA disagreements, useful observations, answered threads that can
  evidence a recurring issue) and MIXED threads are clustered. A MIXED thread is clustered on Agent 1's interpretation
  of its substantive messages; the full thread stays as evidence.
- SOCIAL_ONLY and ROUTINE_ADMIN threads go to processing history; a TIME_BOUND_NOTICE goes there only once its latest
  possible end is at or before the briefing cutoff. Processing history keeps every identity and review obligation.
- A missing, invalid or unverified judgment (legacy records included) is UNCERTAIN and stays eligible.
- agent1-relevance-v2 (stage): a model exclusion also needs Agent 1's semantic verifier. The exclusion becomes one
  candidate prose unit judged under the verifier's own contract (prose_comparison.PROSE_RULES, ProseComparison schema,
  verifier model, verbatim-evidence validation), one request per proposed exclusion, zero retries. Only SUPPORTED
  excludes; an unavailable, failed or other verdict keeps the thread eligible. An audited label is an explicit
  exclusion and records that it needed no model assessment.

The fingerprinted Agent 1 modules are reused unchanged: this module extends their prompt and schema and calls their
parser for the interpretation part. Cached runs can supply audited, input-bound labels (load_labels) instead of model
judgments; their provenance is recorded per thread.
"""
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

RELEVANCE_VERSION = 'agent1-relevance-v1'  # The judgment contract (interpretation request and schema).
STAGE_VERSION = 'agent1-relevance-v2'  # v2: model exclusions need the semantic verifier (v1: structural checks only).
SEMANTIC_VERSION = 'agent1-relevance-verification-v1'
UNIT_ID = 'relevance:1'
LABELS_CONTRACT = 'agent1-thread-relevance-labels-v1'
Relevance = Literal['PROJECT', 'MIXED', 'SOCIAL_ONLY', 'ROUTINE_ADMIN', 'TIME_BOUND_NOTICE', 'UNCERTAIN']
HISTORY = ('SOCIAL_ONLY', 'ROUTINE_ADMIN')
# No timezone is recorded for users or channels: a notice's end is bounded over every real UTC offset.
OFFSETS_MINUTES = range(-12*60, 14*60 + 1, 15)

RELEVANCE_RULES = """
Relevance:
Decide whether this thread belongs in project analysis. Relevance is separate
from resolution, severity and whether anyone should act; it must not change the
summary, resolution or authority fields.

- PROJECT: model behavior, tool or platform incidents, QA disagreements,
  guidance questions, or useful project observations. Statements without a
  question count, and so do threads already answered: an answered thread can
  still be evidence of a recurring issue.
- MIXED: social wording together with substantive project content. List the
  substantive messages in substantive_message_ids.
- SOCIAL_ONLY: greetings, thanks, well-wishes or small talk with no project
  content.
- ROUTINE_ADMIN: a clearly routine administrative or logistics exchange with no
  bearing on annotation work, model behavior, tools or working conditions.
- TIME_BOUND_NOTICE: a schedule or operational notice tied to a time, such as a
  queue closure or shift coverage. Fill notice with the message_id, the day it
  refers to relative to that message (day_offset, 0 for the same day) or an
  explicit local_date (YYYY-MM-DD), and local_end_time (HH:MM) when stated.
- UNCERTAIN: the thread does not show which applies.

In evidence_message_ids cite every message your judgment relies on; for
SOCIAL_ONLY or ROUTINE_ADMIN cite every message in the thread. Use null for
notice unless the relevance is TIME_BOUND_NOTICE. Keep reason under 300
characters. Put the relevance object in the same JSON output.
"""


class NoticeTime(BaseModel):
    model_config = {'extra': 'forbid'}
    message_id: str
    day_offset: int | None = Field(default=None, ge=0, le=14)
    local_date: str | None = None
    local_end_time: str | None = None

    @field_validator('local_end_time')
    @classmethod
    def clock(cls, value):
        if value is not None:
            time.fromisoformat(value)
        return value

    @field_validator('local_date')
    @classmethod
    def day(cls, value):
        if value is not None:
            datetime.strptime(value, '%Y-%m-%d')
        return value


class ThreadRelevance(BaseModel):
    model_config = {'extra': 'forbid'}
    relevance: Relevance
    reason: str = Field(min_length=1, max_length=300)
    evidence_message_ids: list[str] = Field(min_length=1)
    substantive_message_ids: list[str] = Field(default_factory=list)
    notice: NoticeTime | None = None


# ---- The extended interpretation request ------------------------------------------------------------------------

def output_schema():
    from threadsense.agents.thread_interpreter import get_interpretation_output_schema
    schema = get_interpretation_output_schema()
    relevance = ThreadRelevance.model_json_schema()
    schema.setdefault('$defs', {}).update(relevance.pop('$defs', {}))
    schema['properties']['relevance'] = relevance
    schema['required'] = [*schema.get('required', []), 'relevance']
    return schema


def prompt():
    from threadsense.agents.thread_interpreter import INTERPRETATION_RULES
    head, marker, tail = INTERPRETATION_RULES.partition('\nOutput:\n')
    if not marker:
        raise ValueError('Interpretation rules changed shape; refusing to place the relevance rules.')
    return f'{head}\n{RELEVANCE_RULES}{marker}{tail}'


def fingerprint():
    """What a cached relevance judgment depends on: these rules, the contract and this module."""
    from pathlib import Path
    return sha256(json.dumps({'rules': RELEVANCE_RULES, 'schema': ThreadRelevance.model_json_schema(),
                              'module': Path(__file__).read_text(encoding='utf-8')}, sort_keys=True).encode()).hexdigest()


def parse_relevance(thread, raw):
    """The relevance entry of one response. An invalid relevance object never invalidates the interpretation: it is
    recorded as INVALID and treated as uncertain (eligible)."""
    raw = raw.strip()
    if raw.startswith(('```json\n', '```\n')) and raw.endswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    try:
        judgment = ThreadRelevance.model_validate(json.loads(raw).get('relevance'))
    except (ValueError, ValidationError, AttributeError) as error:
        return {'version': RELEVANCE_VERSION, 'source': 'AGENT1_MODEL', 'status': 'INVALID',
                'error': f'{type(error).__name__}: {str(error)[:300]}'}
    return {'version': RELEVANCE_VERSION, 'source': 'AGENT1_MODEL', 'status': 'JUDGED',
            'judgment': judgment.model_dump(mode='json')}


def interpret_thread(thread):
    """(ThreadInterpretation, relevance entry) from ONE interpretation request with the extended prompt and schema."""
    from crewai import Agent, Crew, Process, Task
    from threadsense.agents import thread_interpreter as ti
    from threadsense.routing import require_discussion
    require_discussion(thread)
    if not thread.messages:
        raise ValueError('Cannot interpret a thread with no messages.')
    agent = Agent(role='ThreadSense Thread Interpreter',
                  goal='Accurately summarize one Slack thread, assess its resolution and authority evidence, and judge '
                       'whether it belongs in project analysis.',
                  backstory='You analyze human-data labeling discussions carefully, distinguishing questions, answers, '
                            'endorsements, and open issues.',
                  llm=ti.create_llm(), tools=[], allow_delegation=False, verbose=False, max_iter=3, max_retry_limit=0)
    task = Task(description=prompt(), agent=agent,
                expected_output='One JSON object with a factual summary, central question, resolution state, authority '
                                'evidence message IDs, brief resolution rationale, confidence, and a relevance object.')
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, memory=False, planning=False, verbose=False)
    output = crew.kickoff(inputs={
        'thread_json': thread.model_dump_json(), 'output_schema': json.dumps(output_schema(), ensure_ascii=False),
        'authority_eligible_message_ids': json.dumps(sorted(ti.get_authority_eligible_message_ids(thread)))})
    return ti.parse_interpretation_response(thread, output.raw), parse_relevance(thread, output.raw)


# ---- Verification and eligibility -------------------------------------------------------------------------------

def verify(entry, messages, interpretation):
    """Deterministic verification of a relevance entry against the thread and its verified interpretation. messages:
    [{'message_id', 'timestamp'}]. Returns the entry with a verification block; anything not VERIFIED is uncertain."""
    if not entry or entry.get('status') != 'JUDGED':
        reason = 'no relevance judgment recorded (legacy record)' if not entry else f"judgment {entry.get('status')}"
        return {**(entry or {'version': RELEVANCE_VERSION, 'source': 'MISSING', 'status': 'MISSING'}),
                'verification': {'status': 'NOT_JUDGED', 'findings': [reason]}}
    j, ids = entry['judgment'], [m['message_id'] for m in messages]
    findings = [f'unknown message {mid}' for mid in j['evidence_message_ids'] + j['substantive_message_ids'] if mid not in ids]
    if j['relevance'] in HISTORY and set(j['evidence_message_ids']) != set(ids):
        findings.append(f"{j['relevance']} must cite every message; {len(set(ids) - set(j['evidence_message_ids']))} not cited")
    if j['relevance'] == 'SOCIAL_ONLY' and (interpretation or {}).get('central_question'):
        findings.append('SOCIAL_ONLY but the verified interpretation records a central question')
    if j['relevance'] == 'MIXED' and not j['substantive_message_ids']:
        findings.append('MIXED without substantive messages')
    if j['relevance'] == 'TIME_BOUND_NOTICE':
        notice = j.get('notice')
        if not notice or notice['message_id'] not in ids:
            findings.append('TIME_BOUND_NOTICE without a notice message in the thread')
        elif notice['day_offset'] is None and notice['local_date'] is None:
            findings.append('TIME_BOUND_NOTICE without a day')
    elif j.get('notice'):
        findings.append('notice given for a relevance that is not TIME_BOUND_NOTICE')
    return {**entry, 'verification': {'status': 'UNVERIFIED' if findings else 'VERIFIED', 'findings': findings}}


# The statement an exclusion makes about the thread, judged as one candidate prose unit by the verifier.
CLAIMS = {
    'SOCIAL_ONLY': 'This thread contains only social conversation, such as greetings, thanks or well-wishes, and no project '
                   'question, report, observation, finding or decision.',
    'ROUTINE_ADMIN': 'This thread is a routine administrative or logistics exchange with no bearing on annotation work, model '
                     'behavior, tools or working conditions.',
    'TIME_BOUND_NOTICE': 'This thread is a schedule or operational notice with no project question, report, observation or '
                         'finding beyond the notice itself.'}


def exclusion_unit(judgment):
    """The candidate prose unit for a proposed exclusion: the claim it makes plus Agent 1's own reason."""
    return {'unit_id': UNIT_ID, 'candidate_field': 'relevance',
            'candidate_text': f"{CLAIMS[judgment['relevance']]} {judgment['reason'].strip()}"}


def semantic_request(thread, unit, model):
    """The verifier's prose-comparison request, with the exclusion as its only candidate unit."""
    from threadsense.agents.contracts import ProseComparison
    from threadsense.agents.prose_comparison import PROSE_RULES
    from threadsense.agents.verification_requests import request_body
    from threadsense.terminology import get_terms
    return request_body(model, PROSE_RULES + json.dumps(ProseComparison.model_json_schema()), {
        'original_conversation': thread.model_dump(mode='json'), 'approved_glossary': dict(get_terms()),
        'candidate_prose_units': [unit]}, max_tokens=4096)


def parse_assessment(thread, raw, unit):
    """The verifier's assessment of the exclusion unit, validated as the verifier validates prose (exact unit and text,
    known messages, verbatim quotes); INVALID otherwise."""
    from threadsense.agents.contracts import ProseComparison
    try:
        comparison = ProseComparison.model_validate_json(raw)
        items = comparison.prose_assessments
        if [i.unit_id for i in items] != [unit['unit_id']] or items[0].candidate_text != unit['candidate_text']:
            raise ValueError('the assessment does not cover exactly the exclusion unit')
        item, texts = items[0], {m.message_id: m.text for m in thread.messages}
        if not item.evidence_message_ids or len(item.evidence_message_ids) != len(item.evidence_quotes):
            raise ValueError('matching evidence IDs and quotations are required')
        if any(mid not in texts or not q.strip() or q not in texts[mid] for mid, q in zip(item.evidence_message_ids, item.evidence_quotes)):
            raise ValueError('a quotation is not verbatim source evidence')
    except (ValueError, ValidationError) as error:
        return {'version': SEMANTIC_VERSION, 'status': 'INVALID', 'unit': unit, 'error': f'{type(error).__name__}: {str(error)[:300]}'}
    return {'version': SEMANTIC_VERSION, 'status': 'ASSESSED', 'unit': unit, 'verdict': item.verdict,
            'explanation': item.explanation, 'evidence_message_ids': list(item.evidence_message_ids)}


def assess_exclusion(thread, unit):
    """One live verifier request (zero retries); a failure is recorded and leaves the thread eligible."""
    from threadsense.agents.decision_evidence_audit import get_auditor_model_settings
    from threadsense.agents.verification_requests import complete_once
    model, key_name = get_auditor_model_settings()
    try:
        raw = complete_once(model, key_name, semantic_request(thread, unit, model))
    except Exception as error:  # noqa: BLE001 - recorded, never retried
        return {'version': SEMANTIC_VERSION, 'status': 'FAILED', 'unit': unit, 'model': model,
                'error': f'{type(error).__name__}: {str(error)[:300]}'}
    return {**parse_assessment(thread, raw, unit), 'model': model}


def semantic_fingerprint():
    """What a semantic exclusion assessment depends on: the verifier's prose rules and schema, the claims, the version."""
    from threadsense.agents.contracts import ProseComparison
    from threadsense.agents.prose_comparison import PROSE_RULES
    return sha256(json.dumps({'version': SEMANTIC_VERSION, 'rules': PROSE_RULES, 'schema': ProseComparison.model_json_schema(),
                              'claims': CLAIMS}, sort_keys=True).encode()).hexdigest()


def latest_end(posted, notice):
    """Latest UTC instant at which a notice can still be current, over every UTC offset (no timezone is recorded).
    posted: the notice message's timestamp (aware)."""
    end_time = time.fromisoformat(notice['local_end_time']) if notice.get('local_end_time') else None
    latest = None
    for minutes in OFFSETS_MINUTES:
        offset = timedelta(minutes=minutes)
        if notice.get('local_date'):
            day = datetime.strptime(notice['local_date'], '%Y-%m-%d').date()
        else:
            day = (posted.astimezone(timezone.utc) + offset).date() + timedelta(days=notice['day_offset'])
        end = datetime.combine(day + timedelta(days=1), time()) if end_time is None else datetime.combine(day, end_time)
        end = end.replace(tzinfo=timezone.utc) - offset
        latest = end if latest is None or end > latest else latest
    return latest


def _aware(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def disposition(entry, messages, cutoff):
    """CLUSTER or PROCESSING_HISTORY for one verified entry. Never resolves anything: only where the thread is analysed.
    A model exclusion stands only with the semantic verifier's SUPPORTED verdict (entry['semantic']); an audited label
    is an explicit exclusion."""
    decided = _disposition(entry, messages, cutoff)
    if decided['disposition'] != 'PROCESSING_HISTORY' or entry.get('source') == 'AUDITED_LABEL':
        return decided
    semantic = entry.get('semantic') or {'status': 'NOT_ASSESSED'}
    if semantic.get('verdict') == 'SUPPORTED':
        return {**decided, 'semantic_verdict': 'SUPPORTED'}
    found = semantic.get('verdict') or semantic['status']
    return {'disposition': 'CLUSTER', 'relevance': 'UNCERTAIN', 'proposed': decided['relevance'],
            'basis': f"Exclusion as {decided['relevance']} not confirmed by the semantic verifier ({found}); "
                     'uncertain relevance stays eligible.'}


def needs_assessment(entry, messages, cutoff):
    """Whether a verified model judgment proposes an exclusion that the semantic verifier must confirm."""
    return entry.get('source') == 'AGENT1_MODEL' and _disposition(entry, messages, cutoff)['disposition'] == 'PROCESSING_HISTORY'


def _disposition(entry, messages, cutoff):
    status = (entry.get('verification') or {}).get('status')
    if status != 'VERIFIED':
        return {'disposition': 'CLUSTER', 'relevance': 'UNCERTAIN',
                'basis': 'Relevance not verified (' + '; '.join((entry.get('verification') or {}).get('findings') or ['missing'])
                         + '); uncertain relevance stays eligible.'}
    j = entry['judgment']
    if j['relevance'] in HISTORY:
        return {'disposition': 'PROCESSING_HISTORY', 'relevance': j['relevance'], 'basis': j['reason']}
    if j['relevance'] == 'TIME_BOUND_NOTICE':
        posted = next(_aware(m['timestamp']) for m in messages if m['message_id'] == j['notice']['message_id'])
        end = latest_end(posted, j['notice'])
        expired = cutoff is not None and end <= _aware(cutoff)
        return {'disposition': 'PROCESSING_HISTORY' if expired else 'CLUSTER', 'relevance': j['relevance'],
                'notice_latest_end_utc': end.strftime('%Y-%m-%dT%H:%M:%SZ'), 'cutoff': cutoff,
                'basis': (f"Notice ended by {end:%Y-%m-%dT%H:%MZ} at the latest, before the cutoff; expiry is not completion."
                          if expired else f"Notice may still be current at the cutoff (latest end {end:%Y-%m-%dT%H:%MZ}).")}
    out = {'disposition': 'CLUSTER', 'relevance': j['relevance'], 'basis': j['reason']}
    if j['relevance'] == 'MIXED':
        out['substantive_message_ids'] = list(j['substantive_message_ids'])
    return out


# ---- Audited labels for cached runs -----------------------------------------------------------------------------

def load_labels(raw):
    """Audited thread labels keyed by (channel_id, thread_id), each bound to the thread's input_sha256."""
    if raw.get('contract_version') != LABELS_CONTRACT:
        raise ValueError(f"Unsupported thread relevance labels {raw.get('contract_version')!r}.")
    out = {}
    for label in raw['labels']:
        key = (label['channel_id'], label['thread_id'])
        if key in out:
            raise ValueError(f'Two relevance labels for thread {key}.')
        ThreadRelevance.model_validate(label['judgment'])
        out[key] = {**label, 'label_source': raw['label_source']}
    return out


def labelled_entry(label, input_sha256):
    """A relevance entry from an audited label, or None when the label is bound to different input."""
    if label is None or label['input_sha256'] != input_sha256:
        return None
    return {'version': RELEVANCE_VERSION, 'source': 'AUDITED_LABEL', 'status': 'JUDGED', 'label_id': label['label_id'],
            'label_source': label['label_source'], 'judgment': label['judgment']}


# ---- The relevance stage (zero calls): eligible clustering input plus processing history -------------------------

def _read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def build_stage(canonical_dir, out_dir, *, cutoff, interpretations=None, labels=None, assessor=None):
    """Verify each thread's relevance and split the verified Agent 1 export into a clustering input (eligible threads,
    with their sources and records, loadable as a canonical handoff) and processing history (every other thread, with
    its full record and review obligation). interpretations: the Agent 1 interpretation export carrying model
    relevance; labels: audited labels (load_labels) for cached runs. A label applies only to the exact input it was
    written for; a thread with neither stays eligible as UNCERTAIN. assessor(thread, unit): the semantic verifier for a
    proposed model exclusion (assess_exclusion live; prepared responses offline); None leaves every model exclusion
    unassessed, hence eligible."""
    from pathlib import Path
    import shutil
    canonical_dir, out_dir = Path(canonical_dir), Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f'{out_dir} exists; every relevance stage writes a new directory.')
    records = _read(canonical_dir/'interpretations.json')
    manifest, queue = _read(canonical_dir/'manifest.json'), _read(canonical_dir/'review_queue.json')
    model = {r['input_sha256']: r.get('relevance') for r in (interpretations or [])}
    rows, kept, history = [], [], []
    for record in records:
        source = _read(canonical_dir/record['lineage']['source_file'])
        messages = [{'message_id': m['message_id'], 'timestamp': m['timestamp']} for m in source['messages']]
        key = (record['channel_id'], record['thread_id'])
        entry = labelled_entry((labels or {}).get(key), record['input_sha256']) or model.get(record['input_sha256'])
        checked = verify(entry, messages, record['interpretation'])
        if needs_assessment(checked, messages, cutoff):
            from threadsense.models import Thread
            unit = exclusion_unit(checked['judgment'])
            checked['semantic'] = (assessor(Thread.model_validate(source), unit) if assessor else
                                   {'version': SEMANTIC_VERSION, 'status': 'NOT_ASSESSED', 'unit': unit})
        elif checked.get('source') == 'AUDITED_LABEL':
            checked['semantic'] = {'version': SEMANTIC_VERSION, 'status': 'NOT_REQUIRED',
                                   'basis': 'audited label: an explicit exclusion, attributed to its label source'}
        decided = disposition(checked, messages, cutoff)
        row = {'project_id': record['project_id'], 'batch_id': record['batch_id'], 'channel_id': record['channel_id'],
               'thread_id': record['thread_id'], 'input_sha256': record['input_sha256'], 'relevance_entry': checked,
               **decided, 'review_required': record['review_required']}
        rows.append(row)
        if decided['disposition'] == 'CLUSTER':
            kept.append(record)
        else:
            history.append({**row, 'agent1_record': record, 'original_thread': source,
                            'obligation': {'origin': 'agent1', 'kind': 'inherited_agent1_review_processing_history',
                                           'review_reasons': record['review_reasons']} if record['review_required'] else None})
    target = out_dir/'clustering_input'
    for record in kept:
        for rel in (record['lineage']['source_file'], record['lineage']['verification_file']):
            src, dst = canonical_dir/rel, target/rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    counts = {k: v for k, v in sorted({s: sum(r['verification_status'] == s for r in kept) for s in
                                       ('VERIFIED', 'CORRECTED', 'NEEDS_REVIEW')}.items())}
    subset = {**manifest, 'retained': len(kept), 'selected': len(kept), 'counts': counts,
              'config': {**manifest['config'], 'source_count': len(kept)},
              'clustering_subset': {'version': STAGE_VERSION, 'parent_export': str(canonical_dir),
                                    'parent_threads': len(records), 'eligible_threads': len(kept),
                                    'processing_history_threads': len(history),
                                    'note': 'coverage refers to the eligible threads; the rest are in processing_history.json'}}
    _write(target/'interpretations.json', kept)
    _write(target/'manifest.json', subset)
    _write(target/'review_queue.json', [r for r in kept if r['review_required']])
    if (canonical_dir/'routing_manifest.json').is_file():
        shutil.copy2(canonical_dir/'routing_manifest.json', target/'routing_manifest.json')
    _write(out_dir/'processing_history.json', history)
    summary = {'version': STAGE_VERSION, 'judgment_contract': RELEVANCE_VERSION, 'semantic_verification': SEMANTIC_VERSION,
               'cutoff': cutoff, 'threads': len(records), 'clustered': len(kept),
               'processing_history': len(history),
               'processing_history_obligations': sum(1 for h in history if h['obligation']),
               'by_source': dict(sorted(_count(r['relevance_entry'].get('source', 'MISSING') for r in rows).items())),
               'by_relevance': dict(sorted(_count(r['relevance'] for r in rows).items())),
               'by_verification': dict(sorted(_count(r['relevance_entry']['verification']['status'] for r in rows).items())),
               'semantic_assessments': dict(sorted(_count((r['relevance_entry'].get('semantic') or {}).get('verdict')
                                                          or (r['relevance_entry'].get('semantic') or {}).get('status')
                                                          for r in rows if r['relevance_entry'].get('semantic')).items()))}
    _write(out_dir/'relevance.json', {'summary': summary, 'threads': rows})
    if len(kept) + len(history) != len(records) or sum(r['review_required'] for r in records) != (
            sum(r['review_required'] for r in kept) + summary['processing_history_obligations']) or len(queue) != sum(
            r['review_required'] for r in records):
        raise ValueError('Relevance stage lost a thread or a review obligation.')
    return summary


def _count(values):
    out = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out
