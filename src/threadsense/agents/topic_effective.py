"""Maintained downstream view: canonical output plus mandatory registered reviews.

Historical records are never rewritten. Bindings include exact input, raw response
and exported-result bytes, plus aggregate/per-record equality. Stale findings are
visible separately and are never transferred to a different candidate.
"""
from copy import deepcopy
from pathlib import Path

from threadsense.handoff_inputs import ROOT, read_json, file_hash, digest

REGISTRY = ROOT / 'docs/agent2-review-supplements.json'


def _mark_provisional(value):
    if isinstance(value, list):
        for item in value:
            _mark_provisional(item)
    elif isinstance(value, dict):
        if 'evidence_ids' in value:
            value['reliability'] = 'PROVISIONAL'
        for item in value.values():
            _mark_provisional(item)


def research_handoff(row):
    """Agent 3 INPUT only: complete questions, original evidence and effective disputes.

    No new semantic verdicts or historical confidence are manufactured. Group-wide
    dispute routing is conservative; it does not claim every question is incorrect.
    Failed groups retain all sources and obligations even without a valid inventory.
    """
    questions = []
    for topic in row['topics']:
        inventory = topic.get('inventory', [])
        by_id = {i['item_id']: i for i in inventory}
        for item in inventory:
            if item.get('kind') != 'QUESTION':
                continue
            judgment = deepcopy(item['question'])
            # Unknown is explicit for old responses; never inferred from review flags.
            judgment.setdefault('resolution_confidence', None)
            judgment.setdefault('uncertainty_note', None)
            mids = {e['member_id'] for e in item.get('evidence', [])}
            reasons = []
            if judgment['status'] != 'ANSWERED':
                reasons.append('Model retained an unresolved or partial question.')
            if judgment['uncertainty_note']:
                reasons.append('Model supplied a question-specific uncertainty note.')
            if row['review_obligations'] or topic.get('review_required'):
                reasons.append('Effective review obligations remain; inspect their actual scope.')
            questions.append({
                'topic_id': topic['topic_id'], 'item_id': item['item_id'],
                'original_question': deepcopy(item), 'model_resolution': judgment,
                'confidence_interpretation': 'uncalibrated_model_self_assessment_not_probability',
                'confidence_origin': 'model' if judgment['resolution_confidence'] is not None else 'unknown',
                'linked_answer_items': [deepcopy(by_id[a]) for a in judgment['answer_item_ids'] if a in by_id],
                'relevant_guidance': [deepcopy(g) for g in topic.get('guidance', [])
                    + topic.get('supported_answers', []) + topic.get('provisional_answers', [])
                    if any(e['member_id'] in mids for e in g.get('evidence', []))],
                'effective_content_review_status': row['effective_content_review_status'],
                'answer_reliability': topic.get('answer_reliability'),
                'research_required': bool(reasons), 'research_reasons': reasons,
                'review_obligations': deepcopy(row['review_obligations']),
            })
    return {
        'contract_version': 'agent3-research-input-v1',
        'candidate_group_id': row['candidate_group_id'],
        'processing_state': row['processing_state'], 'nonblocking': True,
        'question_inventory_complete_for_exported_topics': True,
        'semantic_question_coverage_guaranteed': False,
        'questions': questions, 'members': deepcopy(row['members']),
        'review_obligations': deepcopy(row['review_obligations']),
        'topics': deepcopy(row['topics']),
        'interpretation_reliability_is_not_slack_resolution': True,
    }


def taxonomy_handoff(row):
    """Passive v7 assignments and canonical inputs; no regenerated question inventory."""
    return {'contract_version':'agent2-taxonomy-handoff-v1',
        'candidate_group_id':row['candidate_group_id'], 'processing_state':row['processing_state'],
        'nonblocking':True, 'topics':deepcopy(row['topics']), 'members':deepcopy(row['members']),
        'member_dispositions':deepcopy(row['member_dispositions']),
        'rejected_member_ids':list(row['rejected_member_ids']), 'unassigned_member_ids':list(row['unassigned_member_ids']),
        'review_obligations':deepcopy(row['review_obligations']),
        'review_evidence':deepcopy(row['review_evidence']),
        'grouping_file':row['grouping_file'],'grouping_sha256':row['grouping_sha256']}


def load_effective_output(run_dir, *, additional_supplements=(), registry=REGISTRY):
    run = Path(run_dir).resolve()
    records = read_json(run / 'consolidations.json')
    ids = [r['candidate_group_id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate canonical group identities.')
    rows = {r['candidate_group_id']: deepcopy(r) for r in records}
    supplements = {}
    for entry in read_json(registry)['supplements']:
        if (ROOT / entry['run']).resolve() == run:
            path = ROOT / entry['path']
            if file_hash(path) != entry['sha256']:
                raise ValueError('Registered review supplement changed; review and update its registry binding.')
            supplements[path.resolve()] = path
    # Additional inputs extend, never replace, the mandatory registry.
    for path in additional_supplements:
        supplements[Path(path).resolve()] = Path(path)
    for row in rows.values():
        row['automated_review_required'] = row['review_required']
        row['content_review_obligations'] = []
        row['review_obligations'] = deepcopy(row.get('inherited_review_obligations', [])
            + row.get('agent2_review_obligations', []) + row.get('morning_review_obligations', []))
    stale, applied = [], {}
    for path in supplements.values():
        supplement = read_json(path)
        provenance = {'file': path.as_posix(), 'sha256': file_hash(path), 'origin': supplement['origin']}
        for entry in supplement['entries']:
            gid = entry['candidate_group_id']
            directory = run / 'records' / gid
            binding = entry.get('binding', {})
            reasons = []
            if (ROOT / supplement['run']).resolve() != run:
                reasons.append('run_mismatch')
            if gid not in rows:
                reasons.append('missing_group')
            for field, name in [('input_file_sha256', 'input.json'), ('raw_draft_sha256', 'analysis.raw.txt'),
                                ('export_result_sha256', 'result.json')]:
                target = directory / name
                if not target.is_file() or binding.get(field) != file_hash(target):
                    reasons.append(field + '_mismatch')
            if gid in rows and (directory / 'result.json').is_file():
                canonical = next(r for r in records if r['candidate_group_id'] == gid)
                if read_json(directory / 'result.json') != canonical:
                    reasons.append('aggregate_record_mismatch')
            if reasons:
                stale.append({'candidate_group_id': gid, 'reasons': reasons, 'provenance': provenance,
                              'finding': deepcopy(entry), 'applied': False})
                continue
            if not entry.get('assisted_content_review_required'):
                continue
            for finding in entry.get('findings', []):
                key = digest({'group': gid, 'binding': binding, 'finding': finding})
                if key in applied:
                    if provenance not in applied[key]['provenance']:
                        applied[key]['provenance'].append(provenance)
                    continue
                obligation = {'origin': 'assisted_content_review', 'obligation_id': key,
                              'candidate_group_id': gid, 'binding': deepcopy(binding),
                              'finding': deepcopy(finding), 'provenance': [provenance]}
                applied[key] = obligation
                rows[gid]['content_review_obligations'].append(obligation)
                rows[gid]['review_obligations'].append(obligation)
            # A review entry without individual findings still retains its obligation.
            if not entry.get('findings'):
                key = digest({'group': gid, 'binding': binding, 'summary': entry.get('summary')})
                if key not in applied:
                    obligation = {'origin': 'assisted_content_review', 'obligation_id': key,
                                  'candidate_group_id': gid, 'binding': deepcopy(binding),
                                  'finding': {'summary': entry.get('summary')}, 'provenance': [provenance]}
                    applied[key] = obligation
                    rows[gid]['content_review_obligations'].append(obligation)
                    rows[gid]['review_obligations'].append(obligation)
    for row in rows.values():
        if row['content_review_obligations']:
            row['review_required'] = True
            row['review_reasons'].append('Applicable assisted content-review findings remain open.')
            for topic in row['topics']:
                topic['review_required'] = True
                if row.get('schema_version') == 7:
                    topic['assignment_reliability'] = 'PROVISIONAL'
                    topic['assignment_review_obligation_ids'] = [o['obligation_id'] for o in row['content_review_obligations']]
                    continue
                topic['claim_reliability'] = topic['answer_reliability'] = 'PROVISIONAL'
                topic.setdefault('provisional_answers', []).extend(topic.get('supported_answers', []))
                topic['supported_answers'] = []
                topic['content_review_obligation_ids'] = [o['obligation_id'] for o in row['content_review_obligations']]
                topic['effective_factual_review_status'] = 'DISPUTED'
                for key in ('shared_issue', 'representative_question', 'relevant_differences', 'inventory',
                            'open_questions', 'guidance', 'provisional_answers', 'uncertainties'):
                    _mark_provisional(topic.get(key))
        row['effective_review_required'] = row['review_required']
        row['effective_content_review_status'] = 'DISPUTED' if row['content_review_obligations'] else 'NO_APPLICABLE_CONTENT_FINDING'
        if row.get('schema_version') == 7:
            row['taxonomy_handoff'] = taxonomy_handoff(row)
        else:
            row['research_handoff'] = research_handoff(row)
    effective = list(rows.values())
    return {'view_version': 2, 'canonical_file': (run / 'consolidations.json').as_posix(),
            'canonical_sha256': file_hash(run / 'consolidations.json'),
            'review_registry': str(registry), 'review_registry_sha256': file_hash(registry),
            'records': effective, 'review_queue': [r for r in effective if r['review_required']],
            'member_review_queue': [o for r in effective for o in r['inherited_review_obligations']],
            'applied_content_obligations': list(applied.values()), 'unapplied_findings': stale,
            'review_binding_status': 'STALE_FINDINGS_PRESENT' if stale else 'VALID'}
