"""Retrieval evaluation over labelled cases: BM25-only, dense-only, RRF, RRF + MMR.

Measures whether needed sources are retrieved, not whether a question is answered.
"""
import json
from pathlib import Path

from threadsense.routing import ROOT

CASES = ROOT/'data/evaluation/agent3_retrieval_cases.json'
HOLDOUT = ROOT/'data/evaluation/agent3_retrieval_holdout.json'
VARIANTS = {'bm25': {'mode': 'bm25', 'use_mmr': False}, 'dense': {'mode': 'dense', 'use_mmr': False},
            'hybrid_rrf': {'mode': 'hybrid', 'use_mmr': False}, 'hybrid_rrf_mmr': {'mode': 'hybrid', 'use_mmr': True}}


def label(result):
    m = result['metadata']
    base = m['authoring_document_id'] or f"slack:{m['channel_id']}/{m['thread_id']}"
    return base + (f"#{result['sections'][0]}" if result['sections'] else '')


def matches(ref, result):
    m = result['metadata']
    if 'slack' in ref:
        return [m['channel_id'], m['thread_id']] == list(ref['slack']) and m['source_system'] == 'slack'
    return m['authoring_document_id'] == ref['authoring'] and ('section' not in ref or ref['section'] in result['sections'])


def check_labels(cases, retriever):
    """Every label must name an indexed source; a typo would silently lower recall."""
    unknown = []
    for case in cases:
        for kind in ('relevant', 'context', 'distractors', 'must_exclude'):
            for ref in case.get(kind, []):
                if not any(matches(ref, {'metadata': c['metadata'], 'sections': c['sections']}) for c in retriever.chunks.values()):
                    unknown.append({'case': case['id'], 'kind': kind, 'ref': ref})
    return unknown


def evaluate(retriever, cases=None, *, top_k=5, mmr_lambda=None):
    cases = cases or json.loads(Path(CASES).read_text(encoding='utf-8'))['cases']
    unknown = check_labels(cases, retriever)
    if unknown:
        raise ValueError(f'Evaluation labels name sources that are not indexed: {unknown}')
    report = {'top_k': top_k, 'mmr_lambda': mmr_lambda or retriever.manifest['retrieval_defaults']['mmr_lambda'],
              'cases': [], 'summary': {}}
    for case in cases:
        row = {'id': case['id'], 'query': case['query'], 'answerable': case['answerable'], 'variants': {}}
        for name, options in VARIANTS.items():
            extra = {'mmr_lambda': mmr_lambda} if mmr_lambda is not None and options['use_mmr'] else {}
            results = retriever.search(case['query'], case['project'], top_k=top_k, **options, **extra, **case['filters'])['results']
            def kind(result):
                for category, key in (('R', 'relevant'), ('X', 'must_exclude'), ('D', 'distractors'), ('C', 'context')):
                    if any(matches(ref, result) for ref in case.get(key, [])):
                        return category
                return '-'
            found = [ref for ref in case['relevant'] if any(matches(ref, r) for r in results)]
            ranks = [r['rank'] for r in results if kind(r) == 'R']
            row['variants'][name] = {
                'recall': len(found) / len(case['relevant']) if case['relevant'] else None,
                'first_relevant_rank': min(ranks) if ranks else None,
                'missed': [ref for ref in case['relevant'] if ref not in found],
                'distractors': [label(r) for r in results if kind(r) == 'D'],
                'must_exclude_violations': [label(r) for r in results if kind(r) == 'X'],
                'top': [f"{kind(r)} {label(r)}" for r in results]}
        report['cases'].append(row)
    for name in VARIANTS:
        scored = [c['variants'][name] for c in report['cases'] if c['answerable']]
        report['summary'][name] = {
            'mean_recall': round(sum(v['recall'] for v in scored) / len(scored), 3),
            'cases_with_hit': sum(v['first_relevant_rank'] is not None for v in scored),
            'cases_with_full_recall': sum(v['recall'] == 1 for v in scored),
            'distractor_results': sum(len(v['distractors']) for v in scored),
            'must_exclude_violations': sum(len(c['variants'][name]['must_exclude_violations']) for c in report['cases']),
            'answerable_cases': len(scored)}
    return report
