"""TL decisions -> knowledge sources for a later retrieval snapshot, through the existing ingestion path.

A saved decision is rendered as a mock-knowledge-markdown-v1 decision record (the format of
data/knowledge/decisions) and parsed back by knowledge_markdown -> SourceRecord -> normalize_document, the same
path as every authored decision. Before a decision is saved, decision_record_from_source must reproduce its
DecisionRecord from that text exactly (except `source`, which becomes the knowledge-source citation), so approval,
execution and outcome states survive indexing unchanged.

Lineage: one authoring document per (run, card); each later decision on the card is the next version, so in
version_mode='current' only the latest decision is CURRENT and earlier ones are SUPERSEDED_REVISION.
Records are decisions (history), never guidelines or FAQ: an approved draft is not promoted into current policy.

Exports are derived files (rebuilt from the store, byte-identical for the same decision). Indexing builds a NEW
snapshot directory at an explicit cutoff; decisions recorded after that cutoff are excluded and reported, never
backdated. The active run's index is never modified.
"""
from hashlib import sha256
from pathlib import Path

import yaml

from threadsense.agents.advice_contracts import ACTION_LABELS, DecisionRecord
from threadsense.agents.advice_inputs import decision_record_from_source
from threadsense.knowledge_markdown import markdown_text_source
from threadsense.knowledge_sources import normalize_document
from threadsense.retrieval.config import FIXTURE_ROOT, INDEX_DIR, KNOWLEDGE_ROOT
from threadsense.routing import ROOT, aware

EXPORT_DIR = ROOT/'.state/dashboard/decision_exports'
STATUS = {'APPROVED': 'tl_approved', 'APPROVED_WITH_EDITS': 'tl_approved', 'REJECTED': 'tl_rejected',
          'OVERRIDDEN': 'tl_overridden'}
RESPONSE = {'APPROVED': 'approved', 'APPROVED_WITH_EDITS': 'approved_with_edits', 'REJECTED': 'rejected',
            'OVERRIDDEN': 'overridden'}
KIND_WORDING = {'APPROVE_ACTION': 'approved the recommended action', 'CONFIRM_FAQ_UPDATE': 'confirmed an FAQ update',
                'CONFIRM_ANNOUNCEMENT': 'confirmed an announcement', 'OVERRIDE_SEVERITY': 'overrode the assessed severity',
                'DISMISS': 'dismissed the card', 'ROUTE_TO_EXPERT': 'routed the topic to an expert'}


class _Dumper(yaml.SafeDumper):
    pass


def authoring_id(entry):
    """One lineage per (run directory, card); the card ID alone can repeat across runs."""
    return 'tl-decision-' + sha256(f"{entry['run_key']}\n{entry['card_id']}".encode('utf-8')).hexdigest()[:20]


def decision_markdown(entry):
    """The decision as an authored decision record. Body sections keep model-grounded and TL text apart."""
    d, text = entry['decision'], entry['text']
    response = d['tl_response']
    front = {
        'authoring_schema': 'mock-knowledge-markdown-v1', 'document_id': authoring_id(entry), 'document_type': 'decision',
        'record_kind': 'expert_referral' if entry['kind'] == 'ROUTE_TO_EXPERT' else 'advice_review',
        'project_id': entry['project_id'], 'scope': 'project', 'batch_id': entry['batch_id'],
        'version': str(entry['sequence']), 'effective_at': entry['recorded_at'], 'last_updated': entry['recorded_at'],
        'status': STATUS[response['outcome']], 'decision_status': STATUS[response['outcome']],
        'execution_status': d['execution']['source_status'], 'outcome_status': d['outcome']['source_status'],
        'authority': {'actor_id': entry['actor_id'], 'role': entry['actor_role'], 'provenance': 'tl_decision_store'},
        'source': {'system': 'manual', 'manual_key': authoring_id(entry)},
        'decision_id': d['decision_id'], 'decision_kind': entry['kind'], 'run_key': entry['run_key'],
        'run_id': entry['run_id'], 'run_mode': entry['run_mode'], 'card_id': entry['card_id'],
        'text_origin': text['origin'], 'tags': ['tl-decision', entry['kind'].lower().replace('_', '-')], 'source_refs': [],
        'originating_advice': {k: v for k, v in d['original_advice'].items() if k != 'proposed_severity'},
        'tl_response': {'outcome': RESPONSE[response['outcome']], 'actor_id': response['actor_id'],
                        'reviewed_at': response['reviewed_at'], 'text': response['text']},
        'approved_actions': response['approved_actions'], 'severity_override': response['severity_override'],
        'applicability': d['applicability'],
    }
    if entry['supersedes_entry_id']:
        front['supersedes_decision_id'] = entry['supersedes_entry_id']
    advice = d['original_advice']
    lines = [f"# TL decision: {entry['topic_name']}", '', '## Original advice (model-grounded card text)']
    lines.append(f"Proposed action: {ACTION_LABELS[advice['proposed_action']]}." if advice['proposed_action']
                 else 'The card proposed no action.')
    if advice['proposed_text']:
        lines += ['', 'Draft on the card:', '', advice['proposed_text']]
    lines += ['', '## TL decision', f"The team lead {KIND_WORDING[entry['kind']]}"
              + (f" ({entry['expert'].replace('_', ' ').lower()})" if entry['expert'] else '') + '.']
    if response['severity_override']:
        o = response['severity_override']
        lines.append(f"Severity: assessed {o['proposed']}, TL selected {o['tl_selected']} for this card (not a rubric change).")
    if response['approved_actions']:
        lines.append('Approved: ' + ', '.join(ACTION_LABELS[a] for a in response['approved_actions']) + '.')
    if entry['note']:
        lines += ['', f"TL note: {entry['note']}"]
    if text['origin'] in ('TL_EDITED', 'TL_WRITTEN'):
        lines += ['', '## TL-edited text' if text['origin'] == 'TL_EDITED' else '## TL-written text',
                  '(Written by the team lead; not model-grounded.)', '', text['tl_text']]
    lines += ['', '## State at this record',
              'Recorded team-lead decision only: not executed (approval is not posting or implementation), outcome not '
              'observed, and not evidence that the issue is resolved. It is a decision record, not current guidance.']
    body = '\n'.join(lines) + '\n'
    return '---\n' + yaml.dump(front, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000) + '---\n\n' + body


def ingest(entry):
    """Normalize through the existing path and check the round trip. Returns the normalized document."""
    record = markdown_text_source(decision_markdown(entry))
    stored = DecisionRecord.model_validate(entry['decision'])
    parsed = decision_record_from_source(record)
    if parsed.model_dump(exclude={'source'}) != stored.model_dump(exclude={'source'}):
        raise ValueError('The decision does not survive normalization unchanged.')
    return normalize_document(record)


def export(entries, directory=EXPORT_DIR):
    """Write each decision's Markdown once (content-addressed by lineage and version). Existing identical files stay."""
    written, unchanged = [], []
    for entry in entries:
        body = decision_markdown(entry).encode('utf-8')
        path = Path(directory)/entry['project_id']/f"{authoring_id(entry)}@{entry['sequence']}.md"
        if path.is_file():
            if path.read_bytes() != body:
                raise ValueError(f'{path} differs from the stored decision; exports are derived, not edited.')
            unchanged.append(str(path))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        written.append(str(path))
    return {'written': len(written), 'unchanged': len(unchanged)}


def build_snapshot(store, index_dir, *, cutoff, encoder, export_dir=EXPORT_DIR, knowledge_root=KNOWLEDGE_ROOT,
                   fixture_root=FIXTURE_ROOT, rebuild=False):
    """A NEW retrieval snapshot with the knowledge store plus the TL decisions recorded at or before cutoff."""
    from threadsense.retrieval.index import build_index
    index_dir = Path(index_dir).resolve()
    if index_dir == Path(INDEX_DIR).resolve():
        raise ValueError('Refusing to modify the active retrieval index; give a new snapshot directory.')
    entries = store.all_card_decisions()
    included = [e for e in entries if aware(e['recorded_at']) <= aware(cutoff)]
    later = [e['entry_id'] for e in entries if e not in included]
    exported = export(entries, export_dir)
    ids = [e['entry_id'] for e in included]
    try:
        manifest = build_index(index_dir, encoder=encoder, rebuild=rebuild, knowledge_root=knowledge_root,
                               fixture_root=fixture_root, cutoff=cutoff, decision_root=export_dir)
    except Exception as error:
        store.mark_indexing(ids, 'FAILED', snapshot=str(index_dir), error=f'{type(error).__name__}: {error}'[:500])
        raise
    indexed = {tuple(k.split('@')) for k in _documents(index_dir)}
    expected = {e['entry_id']: (doc['document_id'], doc['version_id']) for e in included for doc in [ingest(e)]}
    present = [i for i, key in expected.items() if key in indexed]
    missing = [i for i in ids if i not in present]
    store.mark_indexing(present, 'INDEXED', snapshot=str(index_dir), fingerprint=manifest['build_fingerprint'])
    if missing:
        store.mark_indexing(missing, 'FAILED', snapshot=str(index_dir), error='Not found in the built snapshot.')
    return {'status': manifest['status'], 'index_dir': str(index_dir), 'cutoff': cutoff,
            'build_fingerprint': manifest['build_fingerprint'], 'exports': exported, 'decisions_indexed': len(present),
            'decisions_missing': missing, 'decisions_after_cutoff': later,
            'tl_decision_receipt': manifest['corpus'].get('tl_decisions')}


def _documents(index_dir):
    import json
    return json.loads((Path(index_dir)/'documents.json').read_text(encoding='utf-8'))
