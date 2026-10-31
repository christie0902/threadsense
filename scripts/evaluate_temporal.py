"""Temporal golden-set evaluation (data/evaluation/temporal_golden.json), offline, zero model calls.

Per case, the controlled source bundle is written to a throwaway knowledge root (and, for Slack announcements, a
throwaway fixture root) outside the repository, ingested and indexed by production code (knowledge_markdown /
knowledge_sources, retrieval.index with versions.py eligibility), and retrieved complete (top_k above the bundle
size, so ranking cannot hide a source). The draft the Advisor would write is assembled from PREPARED semantic
judgments only (which sources it cites, which pairs state different rules, announcement relevance, current-source
agreement, open question); the expected outcome is never an input. Production then decides: temporal_check and
temporal_decision (advisor_checks). This script compares and reports; it contains no precedence logic of its own.

Metrics: joint accuracy (decision, baseline, status, review and update target all correct), decisive-baseline
accuracy, correct abstention, false overrides (a must_not_win source chosen), update-target accuracy, plus the same
metrics for an always-abstain policy (which must fail every decisive case), timezone/effective-date/section checks
and input-order independence (each bundle also run in reverse order).

  uv run --locked python scripts/evaluate_temporal.py [--tmp D:/tsb/temporal] [--write <new path>]
"""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT/'data/evaluation/temporal_golden.json'
FOLDERS = {'instructions': 'instructions', 'faq': 'faq', 'decision': 'decisions', 'announcement': 'decisions'}


class WordHashEncoder:
    """Deterministic bag-of-words vectors: only so the snapshot can be built offline; ranking is irrelevant here."""
    allow_download, dimension, max_tokens = False, 64, 400

    def count(self, text):
        return len(text.split()) + 2

    def encode(self, texts):
        out = []
        for text in texts:
            v = [0.0] * self.dimension
            for word in re.findall(r'\w+', text.lower()):
                v[int(sha256(word.encode()).hexdigest(), 16) % self.dimension] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out

    def identity(self):
        from threadsense.retrieval.config import EMBEDDING
        return {**EMBEDDING, 'dimension': self.dimension, 'max_tokens': self.max_tokens}


def markdown(src, defaults):
    front = {'authoring_schema': 'mock-knowledge-markdown-v1', 'document_id': src['document_id'],
             'document_type': src['type'], 'project_id': src.get('project', defaults['project']), 'scope': 'project',
             'batch_id': src.get('batch', defaults['batch']) if src['type'] in ('decision', 'announcement') else None,
             'version': src['version'], 'effective_at': src['effective_at'], 'status': src['status'],
             'authority': {'actor_id': 'U_GOLD_TL', 'role': 'TEAM_LEAD', 'provenance': 'temporal_golden'},
             'source': {'system': 'manual', 'manual_key': src['document_id']}, 'synthetic': True}
    for key in ('record_kind', 'decision_status', 'execution_status', 'outcome_status', 'valid_until', 'published_at'):
        if src.get(key):
            front[key] = src[key]
    if src['type'] == 'announcement':
        front['record_kind'] = 'channel_announcement'
    if src.get('supersedes'):
        front['supersedes'] = src['supersedes']
    body = '\n\n'.join(f'## {name}\n{text}' for name, text in src['sections'].items())
    return '---\n' + yaml.safe_dump(front, sort_keys=False, allow_unicode=True) + f"---\n\n# {src['document_id']}\n\n{body}\n"


def json_source(src, defaults):
    from threadsense.knowledge_sources import SourceIdentity, SourceRecord
    record = SourceRecord(source=SourceIdentity(system='manual', project_id=src.get('project', defaults['project']),
                                                manual_key=src['manual_key']),
                          scope='project', document_type='guideline', record_kind='guideline', original_text=src['text'],
                          authority={'recorded_role': 'TEAM_LEAD', 'actor_id': 'U_GOLD_TL', 'provenance': 'temporal_golden',
                                     'approval_status': 'EXPLICIT_SOURCE_MARKER'},
                          source_metadata={'authoring': {'document_id': src['document_id'], 'version': src['version'],
                                                         'status': src['status']}})
    return record.model_dump()


def build(case, defaults, root, order):
    knowledge, fixtures = root/'knowledge', root/'fixtures'
    for folder in ('instructions', 'faq', 'decisions'):
        (knowledge/folder).mkdir(parents=True, exist_ok=True)
    (fixtures/'channels').mkdir(parents=True, exist_ok=True)
    users, channels = [{'id': 'U_GOLD_TL', 'name': 'Lead', 'role': 'TEAM_LEAD'}], {}
    for i, src in enumerate(order(case['sources'])):
        if src['type'] == 'json_guideline':
            (knowledge/'instructions'/'manual').mkdir(exist_ok=True)
            (knowledge/'instructions'/'manual'/f"{i:02d}_{src['sid']}.json").write_text(
                json.dumps(json_source(src, defaults)), encoding='utf-8')
        elif src['type'] == 'slack_announcement':
            ch = channels.setdefault(src['channel_id'], {'channel': {'id': src['channel_id'], 'name': src['channel_id'].lower(),
                                                                      'project_id': defaults['project'], 'batch_id': defaults['batch'],
                                                                      'channel_type': 'ANNOUNCEMENTS'}, 'history': [], 'replies': {}})
            ch['history'].append({'ts': src['ts'], 'user': src['user'], 'text': src['text'], 'source': 'USER',
                                  'reactions': [], 'reply_count': 0})
        else:
            folder = knowledge/FOLDERS[src['type']]/(defaults['project'] if FOLDERS[src['type']] == 'decisions' else '')
            folder.mkdir(parents=True, exist_ok=True)
            (folder/f"{i:02d}_{src['sid']}.md").write_text(markdown(src, defaults), encoding='utf-8')
    for cid, data in channels.items():
        (fixtures/'channels'/f'{cid}.json').write_text(json.dumps(data), encoding='utf-8')
    (fixtures/'users.json').write_text(json.dumps({'users': users}), encoding='utf-8')
    return knowledge, fixtures


def sid_of(item, case, defaults):
    citation = item.get('citation') or {}
    authoring, source = citation.get('authoring'), citation.get('source') or {}
    for src in case['sources']:
        if src['type'] == 'slack_announcement':
            if source.get('channel_id') == src['channel_id'] and source.get('thread_id') == src['ts']:
                return src['sid']
        elif authoring == f"{src['document_id']}@{src['version']}" and source.get('project_id') == src.get('project', defaults['project']):
            return src['sid']
    return None


def run_case(case, defaults, tmp, order):
    from threadsense.agents.advisor_checks import temporal_check, temporal_decision
    from threadsense.agents.advisor_contracts import AdvisorDraft
    from threadsense.agents.advisor_evidence import Budget, ResearchTools
    from threadsense.retrieval.index import build_index
    from threadsense.retrieval.search import Retriever
    root = Path(tempfile.mkdtemp(prefix=case['id'][:3] + '_', dir=tmp))
    knowledge, fixtures = build(case, defaults, root, order)
    as_of, encoder = case.get('as_of', defaults['as_of']), WordHashEncoder()
    build_index(root/'index', encoder=encoder, knowledge_root=knowledge, fixture_root=fixtures, cutoff=as_of, canonical_members=[])
    retriever = Retriever(root/'index', encoder=encoder)
    try:
        tools = ResearchTools(retriever, project=defaults['project'], batch=defaults['batch'], as_of=as_of, budget=Budget({}),
                              top_k=50, expansion=False)
        tools.search(case['question'], purpose='initial_current_guidance')
        if tools.withheld:  # As the Advisor does (advisor_pilot.advise): superseded material exists, so check it.
            tools.search(case['question'], purpose='supersession_check', version_mode='history')
        ledger = tools.ledger
        by_sid = {}
        for eid, item in ledger.items():
            sid = sid_of(item, case, defaults)
            section = (case.get('question_section') or {}).get(sid)
            if sid and (section is None or section in (item['citation'].get('sections') or [])):
                by_sid.setdefault(sid, []).append(eid)
        prepared = case['prepared_judgments']
        cited = [s for s in order(prepared['cited']) if s in by_sid]  # The draft can only cite what it was shown.
        claims = [{'claim_id': f'c{i}', 'kind': 'HISTORY' if ledger[by_sid[s][0]]['use'] in ('PRIOR_DECISION', 'HISTORY_ONLY') else 'GUIDANCE',
                   'text': f'Source {i} on the question.', 'evidence_ids': by_sid[s]} for i, s in enumerate(cited, 1)]
        conflicts = [{'evidence_ids': [e for s in pair for e in by_sid[s][:1]], 'description': 'Prepared: these sources state different rules.'}
                     for pair in order(prepared.get('conflicts', [])) if sum(s in by_sid for s in pair) >= 2
                     for pair in [[s for s in pair if s in by_sid]]]
        assessments = [{'evidence_id': by_sid[s][0], 'relevant': a['relevant'], 'directive': a['directive'],
                        'directive_quote': a.get('quote'), 'rationale': 'Prepared judgment.'}
                       for s, a in (prepared.get('announcements') or {}).items() if s in by_sid]
        open_question = prepared.get('open_question') == 'SUPPORTED'
        draft = AdvisorDraft.model_validate({
            'summary': 'Prepared.', 'reasoning': 'Prepared.', 'claims': claims, 'evidence_sufficiency': 'SUFFICIENT',
            'severity': {'level': 'LOW', 'rationale': 'Not assessed here.'}, 'confidence': 0.9,
            'open_confirmation': 'OPEN' if open_question else 'NONE',
            **({'open_question': case['question'], 'open_question_evidence_ids': [e for s in cited for e in by_sid[s][:1]]} if open_question else {}),
            'source_conflicts': conflicts, 'announcement_assessments': assessments})
        verdicts = {f'announcement:{a["evidence_id"]}': 'SUPPORTED' for a in assessments if a['relevant'] and a['directive']}
        verdicts.update({f'temporal:conflict[{i}]': prepared['agreement'] for i in range(len(conflicts)) if prepared.get('agreement')})
        from threadsense.agents.advisor_checks import established
        handling = {e for e in established(draft, ledger) if verdicts.get(f'announcement:{e}') == 'SUPPORTED'}
        temporal = temporal_check(draft, ledger, handling, verdicts)
        decision = temporal_decision(draft, ledger, temporal, handling=handling, open_question_supported=open_question,
                                     withheld=tools.notes()['withheld_by_version'])
        to_sid = {e: s for s, ids in by_sid.items() for e in ids}
        targets = []
        for t in decision['update_targets']:
            sid = next((src['sid'] for src in case['sources'] if t['authoring'] == f"{src.get('document_id')}@{src.get('version')}"), None)
            targets.append({'sid': sid, 'section': t['section']})
        return {'decision': decision['decision'], 'baseline': sorted({to_sid[e] for e in decision['baseline']}),
                'temporal_status': decision['temporal_status'], 'temporal_review_required': decision['review_required'],
                'documentation_update_target': targets[0] if targets else None, 'reason': decision['reason'],
                'temporal_findings': [(f['code'], f['status']) for f in temporal['findings']],
                'uses': {s: sorted({ledger[e]['use'] for e in ids}) for s, ids in by_sid.items()},
                'withheld': [(w['authoring'], w['state']) for w in tools.notes()['withheld_by_version']],
                'not_retrieved': sorted({src['sid'] for src in case['sources']} - set(by_sid))}
    finally:
        retriever.client.close()


def score(cases, actual):
    rows, totals = [], {'joint': 0, 'decisive': 0, 'decisive_correct': 0, 'abstain': 0, 'abstain_correct': 0,
                        'false_overrides': 0, 'target_correct': 0, 'cases': len(cases)}
    for case in cases:
        e, a = case['expected'], actual[case['id']]
        fields = ('decision', 'baseline', 'temporal_status', 'temporal_review_required', 'documentation_update_target')
        mismatch = {f: {'expected': sorted(e[f]) if f == 'baseline' else e[f], 'actual': a[f]} for f in fields
                    if (sorted(e[f]) if f == 'baseline' else e[f]) != a[f]}
        false_override = sorted(set(a['baseline']) & set(e['must_not_win']))
        totals['joint'] += not mismatch
        totals['false_overrides'] += bool(false_override)
        totals['target_correct'] += e['documentation_update_target'] == a['documentation_update_target']
        if e['decision'] == 'DECIDED':
            totals['decisive'] += 1
            totals['decisive_correct'] += a['decision'] == 'DECIDED' and a['baseline'] == sorted(e['baseline'])
        else:
            totals['abstain'] += 1
            totals['abstain_correct'] += a['decision'] == 'ABSTAIN'
        rows.append({'id': case['id'], 'ok': not mismatch, 'mismatch': mismatch, 'false_override': false_override})
    return totals, rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tmp', type=Path, default=None, help='Scratch directory outside the repository (default: system temp).')
    parser.add_argument('--write', type=Path, help='New path for the JSON report.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    tmp = Path(tempfile.mkdtemp(prefix='temporal_', dir=args.tmp)) if args.tmp else Path(tempfile.mkdtemp(prefix='temporal_'))
    if tmp.resolve().is_relative_to(ROOT):
        parser.error('Use a scratch directory outside the repository.')
    sys.stdout.reconfigure(encoding='utf-8')
    golden = json.loads(GOLDEN.read_text(encoding='utf-8'))
    cases, defaults = golden['cases'], golden['defaults']
    forward, reverse = (lambda xs: list(xs)), (lambda xs: list(reversed(list(xs))))
    actual, order_issues = {}, []
    for case in cases:
        actual[case['id']] = run_case(case, defaults, tmp, forward)
        again = run_case(case, defaults, tmp, reverse)
        keys = ('decision', 'baseline', 'temporal_status', 'temporal_review_required', 'documentation_update_target')
        if {k: actual[case['id']][k] for k in keys} != {k: again[k] for k in keys}:
            order_issues.append(case['id'])
    totals, rows = score(cases, actual)
    abstain_only = {c['id']: {'decision': 'ABSTAIN', 'baseline': [], 'temporal_status': 'UNRESOLVED',
                              'temporal_review_required': True, 'documentation_update_target': None} for c in cases}
    abstain_totals, _ = score(cases, abstain_only)
    report = {'golden': golden['version'], 'metrics': {
        'joint_accuracy': f"{totals['joint']}/{totals['cases']}",
        'decisive_baseline_accuracy': f"{totals['decisive_correct']}/{totals['decisive']}",
        'correct_abstention': f"{totals['abstain_correct']}/{totals['abstain']}",
        'false_overrides': f"{totals['false_overrides']}/{totals['cases']}",
        'update_target_accuracy': f"{totals['target_correct']}/{totals['cases']}",
        'input_order_dependent_cases': order_issues},
        'always_abstain_policy': {'joint_accuracy': f"{abstain_totals['joint']}/{abstain_totals['cases']}",
                                  'decisive_baseline_accuracy': f"{abstain_totals['decisive_correct']}/{abstain_totals['decisive']}"},
        'cases': [{**r, 'actual': actual[r['id']]} for r in rows]}
    print(json.dumps(report['metrics'], indent=1))
    print(json.dumps(report['always_abstain_policy']))
    for r in report['cases']:
        if not r['ok']:
            print(f"MISMATCH {r['id']}: {r['mismatch']} | findings {r['actual']['temporal_findings']} | uses {r['actual']['uses']} "
                  f"| withheld {r['actual']['withheld']} | not retrieved {r['actual']['not_retrieved']}")
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + '\n', encoding='utf-8')
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
