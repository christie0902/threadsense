"""Eligibility of TL decisions as current handling, and withdrawal, end to end through production ingestion, indexing and
version eligibility (scripts/evaluate_temporal.run_case builds each controlled bundle into a throwaway snapshot in
pytest's temp directory; semantic inputs are PREPARED). Variants of golden case T02 change one recorded fact at a
time; the golden file itself is unchanged."""
from copy import deepcopy
import importlib.util
import json

import pytest

from threadsense.routing import ROOT

spec = importlib.util.spec_from_file_location('evaluate_temporal', ROOT/'scripts/evaluate_temporal.py')
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)
GOLDEN = json.loads((ROOT/'data/evaluation/temporal_golden.json').read_text(encoding='utf-8'))
T02 = next(c for c in GOLDEN['cases'] if c['id'] == 'T02_authorized_tl_directive')
TARGET = {'sid': 'G', 'section': 'Contact details'}


def variant(decision=None, extra=(), prepared=None, drop=()):
    case = deepcopy(T02)
    d = next(s for s in case['sources'] if s['sid'] == 'D')
    for key, value in (decision or {}).items():
        if value is None:
            d.pop(key, None)
        else:
            d[key] = value
    case['sources'] = [s for s in case['sources'] if s['sid'] not in drop] + list(extra)
    case['prepared_judgments'] = {**case['prepared_judgments'], **(prepared or {})}
    return case


def post(**changes):
    """A posted TL announcement that links the decision through its source_refs (the preferred governing source)."""
    return {'sid': 'A', 'type': 'announcement', 'document_id': 'gt02-pii-post', 'version': '1.0', 'status': 'tl_approved',
            'execution_status': 'posted', 'effective_at': '2026-09-10T14:00:00Z',
            'source_refs': [{'document_id': 'gt02-tl-directive', 'version': '1.0'}],
            'sections': {'Posted message': 'A phone number clearly invented inside a fictional story no longer needs '
                                           'quarantine on its own.'}, **changes}


ANNOUNCED = {'cited': ['G', 'D', 'A'], 'announcements': {'A': {'relevant': True, 'directive': True,
                                                               'quote': 'no longer needs quarantine on its own'}}}


def run(case, tmp_path):
    return evaluate.run_case(case, GOLDEN['defaults'], tmp_path, lambda xs: list(xs))


def test_t02_as_recorded_lacks_enactment_evidence_and_stays_reviewable(tmp_path):
    """T02's decision is approved, effective and declares supersession, but its only execution record is a generic
    'posted' on an advice review, with no linked announcement or guideline: enactment is not established. The guide's
    section is not silently replaced; it stays current with the supersession flagged as unverified, for review."""
    out = run(T02, tmp_path)
    assert out['uses'] == {'G': ['CURRENT_GUIDANCE'], 'D': ['PRIOR_DECISION']}
    assert out['enactment_gaps'] == {'D': ['NO_ENACTMENT_EVIDENCE']}
    assert ('UNVERIFIED_SUPERSESSION_CITED', 'DETECTED') in out['temporal_findings']
    assert out['decision'] == 'ABSTAIN' and out['baseline'] == [] and out['temporal_review_required']
    assert out['reason'].startswith('supersession not verified') and 'SUPERSEDING_DECISION_NOT_ENACTED' in out['reason']


def test_linked_posted_announcement_enacts_the_decision_and_governs(tmp_path):
    """With a later posted TL announcement linking the decision, the decision is current handling (its type and
    recorded states unchanged), its supersession applies, the announcement is named as the governing source and the
    guide's old section is the documentation update target."""
    out = run(variant(extra=[post()], prepared=ANNOUNCED), tmp_path)
    assert out['uses']['D'] == ['ENACTED_DECISION'] and out['uses']['G'] == ['HISTORY_ONLY']
    assert (out['decision'], out['baseline'], out['temporal_status']) == ('DECIDED', ['A', 'D'], 'RESOLVED_BY_RECORD')
    assert out['governing_sources'] == ['A'] and out['documentation_update_target'] == TARGET


def test_recorded_policy_enactment_makes_the_decision_its_own_governing_source(tmp_path):
    out = run(variant({'execution_status': 'policy_enacted'}), tmp_path)
    assert (out['decision'], out['baseline'], out['governing_sources']) == ('DECIDED', ['D'], ['D'])
    assert out['documentation_update_target'] == TARGET and not out['temporal_review_required']


@pytest.mark.parametrize('decision, extra, missing', [
    ({'execution_status': 'not_executed'}, [], ['NO_ENACTMENT_EVIDENCE']),                    # approved, not carried out
    ({'execution_status': 'executed'}, [], ['NO_ENACTMENT_EVIDENCE']),                        # generic "executed"
    ({'decision_status': 'reported', 'status': 'reported', 'execution_status': 'policy_enacted'}, [], ['NO_TL_APPROVAL']),
    ({'execution_status': 'policy_enacted', 'valid_until': '2026-09-30T00:00:00Z'}, [], None),  # expired: history only
    ({'execution_status': 'policy_enacted', 'batch': 'gold_batch_9'}, [], ['OUT_OF_SCOPE']),
    ({}, [post(effective_at='2026-09-09T12:00:00Z')], ['NO_ENACTMENT_EVIDENCE']),              # posted before the decision
    ({}, [post(authority_role='QA_TUTOR')], ['NO_ENACTMENT_EVIDENCE']),                        # not posted by a team lead
    ({}, [post(source_refs=[])], ['NO_ENACTMENT_EVIDENCE']),                                    # no recorded link
])
def test_decisions_without_established_enactment_never_become_current(tmp_path, decision, extra, missing):
    """Approval alone, a generic execution status, an expired, out-of-scope or unapproved record, or an announcement
    that is earlier, not from a team lead or not linked: the decision does not support current handling and its
    declared supersession is not applied (the guide stays, flagged)."""
    out = run(variant(decision, extra, prepared=ANNOUNCED if extra else None), tmp_path)
    assert 'D' not in out['baseline'] and out['uses']['G'] == ['CURRENT_GUIDANCE']
    if missing is not None:
        assert out['enactment_gaps'] == {'D': missing}
    assert out['decision'] == 'ABSTAIN' and out['temporal_review_required']


def test_completed_operational_action_is_not_a_policy_enactment(tmp_path):
    """An escalation receipt marked completed records that an action happened, not that a rule changed: with no declared
    supersession it is not current handling, and its disagreement with the guide stays reviewable."""
    out = run(variant({'record_kind': 'escalation_receipt', 'execution_status': 'completed', 'supersedes': None}), tmp_path)
    assert out['uses']['D'] == ['PRIOR_DECISION'] and out['enactment_gaps'] == {'D': ['NOT_A_POLICY_CHANGE', 'NO_ENACTMENT_EVIDENCE']}
    assert ('UNEXPLAINED_SOURCE_CONFLICT', 'DETECTED') in out['temporal_findings'] and out['decision'] == 'ABSTAIN'


def test_approved_but_unexecuted_decision_without_supersession_leaves_the_guide_decisive(tmp_path):
    out = run(variant({'execution_status': 'not_executed', 'supersedes': None}), tmp_path)
    assert (out['decision'], out['baseline'], out['temporal_status']) == ('DECIDED', ['G'], 'NO_CONFLICT')


WITHDRAWN_GUIDE = {'sid': 'W', 'type': 'instructions', 'document_id': 'gt02-safety-guide', 'version': '1.1', 'status': 'withdrawn',
                   'effective_at': '2026-09-20T09:00:00Z', 'sections': {'Status': 'This guide is withdrawn. No replacement '
                                                                                  'has been published.'}}


def test_withdrawn_guide_is_not_current_and_no_earlier_revision_returns(tmp_path):
    """Explicit withdrawal with no replacement differs from unverified supersession: no revision of the guide is current
    (the earlier approved one does not come back), and the baseline abstains for that reason."""
    case = variant(extra=[WITHDRAWN_GUIDE], drop=('D',), prepared={'cited': ['G'], 'conflicts': []})
    out = run(case, tmp_path)
    assert out['uses']['G'] == out['uses']['W'] == ['HISTORY_ONLY']
    assert ('gt02-safety-guide@1.0', 'WITHDRAWN') in out['withheld']
    assert (out['decision'], out['reason']) == ('ABSTAIN', 'guidance withdrawn without replacement')


def test_section_withdrawn_by_an_approved_source_has_no_replacement(tmp_path):
    notice = {'sid': 'N', 'type': 'announcement', 'document_id': 'gt02-withdrawal-notice', 'version': '1.0', 'status': 'approved',
              'effective_at': '2026-09-15T09:00:00Z',
              'supersedes': [{'document_id': 'gt02-safety-guide', 'version': '1.0', 'section': 'Contact details', 'withdrawn': True}],
              'sections': {'Notice': 'The contact-details rule is withdrawn pending review; no replacement yet.'}}
    out = run(variant(extra=[notice], drop=('D',), prepared={'cited': ['G'], 'conflicts': []}), tmp_path)
    assert ('gt02-safety-guide@1.0', 'SECTION_WITHDRAWN') in out['withheld'] and out['uses']['G'] == ['HISTORY_ONLY']
    assert (out['decision'], out['reason']) == ('ABSTAIN', 'guidance withdrawn without replacement')


def test_enacted_decision_keeps_its_document_type_and_states_in_the_ledger(tmp_path):
    """Presentation: the evidence item stays a decision record with its recorded states; its status line names the
    governing source. Read directly from the ledger the evaluator builds."""
    from threadsense.agents.advisor_evidence import Budget, ResearchTools
    from threadsense.retrieval.index import build_index
    from threadsense.retrieval.search import Retriever
    case = variant(extra=[post()])
    root = tmp_path/'snap'
    knowledge, fixtures = evaluate.build(case, GOLDEN['defaults'], root, lambda xs: list(xs))
    encoder = evaluate.WordHashEncoder()
    build_index(root/'index', encoder=encoder, knowledge_root=knowledge, fixture_root=fixtures, cutoff=GOLDEN['defaults']['as_of'],
                canonical_members=[])
    retriever = Retriever(root/'index', encoder=encoder)
    try:
        tools = ResearchTools(retriever, project='golden_temporal', batch='gold_batch_1', as_of=GOLDEN['defaults']['as_of'],
                              budget=Budget({}), top_k=50, expansion=False)
        tools.search(case['question'], purpose='initial_current_guidance')
        [item] = [i for i in tools.ledger.values() if i['citation']['authoring'] == 'gt02-tl-directive@1.0']
    finally:
        retriever.client.close()
    assert item['use'] == 'ENACTED_DECISION' and item['source_type'] == 'decision' and item['record_kind'] == 'advice_review'
    assert item['recorded_states']['execution_status'] == 'posted'
    assert item['applicability']['enactment']['governing_sources'] == ['gt02-pii-post@1.0']
    assert item['excerpt'].startswith('[ENACTED TL DECISION') and 'governing source: gt02-pii-post@1.0' in item['excerpt']


def test_operational_approvals_linked_by_posted_announcements_are_not_enacted_policy(tmp_path):
    """Real corpus (the knowledge store as indexed by the shared test fixture): three TL approvals are linked by later
    posted announcements, but they approve operational work (documentation sync, a calibration exercise, an audit
    manifest) and declare no rule they change, so a backward link does not make them current handling. No real decision
    record is enacted policy."""
    from tests.retrieval_doubles import HashEncoder
    from threadsense.retrieval.index import build_index
    from threadsense.retrieval.search import Retriever
    build_index(tmp_path/'index', encoder=HashEncoder())
    retriever = Retriever(tmp_path/'index', encoder=HashEncoder())
    try:
        found = {}
        for project in ('response_preference', 'safety_classification', 'audio_multimodal', 'multilingual_eval'):
            for key, v in retriever.select(project, as_of='2026-10-02T12:00:00Z', version_mode='history')['eligible'].items():
                if v['version']['enactment']:
                    found[retriever.chunks[key]['citation']['authoring']] = v['version']['enactment']
    finally:
        retriever.client.close()
    assert found and all(e['status'] == 'NOT_ENACTED' for e in found.values())
    for authoring in ('safety-doc-sync-approval@1.0', 'rp-tie-calibration-approval@1.0', 'rp-audit-manifest-approval@1.0'):
        assert found[authoring]['missing'] == ['NOT_A_POLICY_CHANGE'], authoring
