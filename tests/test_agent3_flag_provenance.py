"""Flag provenance and card dependencies on saved runs (read-only; zero calls)."""
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from threadsense.agents.advice_contracts import GROUPING_LABEL, FlagProvenance
from threadsense.agents.flag_provenance import FlagSource, dependencies
from threadsense.dashboard.runs import Run

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT/'data/experiments'
LINEAGE = ROOT/'data/processed/agent1_verified_v3'
pytestmark = pytest.mark.skipif(not (EXP/'agent3_final_eval_v1').is_dir() or not LINEAGE.is_dir(),
                                reason='saved runs and the Agent 1 lineage base are needed')


def flags_for(run_name, topic_id):
    run = Run(EXP/run_name)
    card_id = next(cid for cid, c in run.cards.items() if c['lineage'].get('topic_id') == topic_id)
    card, result = run.cards[card_id], run.topics[card_id]['result']
    return run, card, [(p, dependencies(card, result, p, run.flag_source)) for p in run.flag_source.provenance(card)]


def links(deps, relation=None, displayed=None):
    return {l.element_id for l in deps.links if (relation is None or l.relation == relation)
            and (displayed is None or l.displayed == displayed)}


def test_json_versus_prose_keeps_the_substantive_finding_apart_from_the_failed_revision():
    _, card, [(prov, deps)] = flags_for('agent3_summary_eval_v1', 'cluster_fb1dce1eeeedc4cb/topic_1')
    assert prov.recovery == 'RECOVERED' and prov.effective_attempt == 'original'
    [finding] = prov.findings
    assert finding.category == 'RESOLUTION' and finding.nature == 'SUBSTANTIVE'
    assert finding.message_ids == ['m:C_RP_QA:1790913880.000113', 'm:C_RP_QA:1790913921.000226']
    assert finding.source.path.endswith('/result.json') and finding.source.pointer == '/result/passes/0/findings'
    # The card's saved flag text is the failed revision, not the dispute; it is kept and labelled as such.
    assert card['inherited_flags'][0]['detail'].startswith('The single targeted revision failed')
    assert prov.card_detail_is == 'ATTEMPT_ERROR' and [e.stage for e in prov.attempt_errors] == ['REVISION_FAILED']
    # Code establishes references and the exact topic aggregation; it never records independence.
    assert 'action:need' in links(deps, 'DIRECT', True)
    assert 'resolution:member_225803f43142caa5d3c165cf' in links(deps, 'DIRECT')
    assert links(deps, 'INVARIANT') == {'topic_resolution'}
    assert {l.relation for l in deps.links} <= {'DIRECT', 'DERIVED', 'SAME_THREAD', 'INVARIANT', 'NOT_ESTABLISHED'}
    assert 'claim:c4' not in links(deps)  # The FAQ claim cites no flagged message: absence is simply not listed.


def test_repeated_ending_links_the_title_caution_and_the_counted_report():
    _, card, found = flags_for('agent3_policy_eval_v1', 'cluster_b7e5234380f9ea67/topic_1')
    (agent1, a_deps), (caution, c_deps) = found
    assert caution.category == 'CONTENT_CAUTION' and caution.findings[0].category == 'TAXONOMY_NAMING_CAUTION'
    assert caution.findings[0].disputed_fields == ['topics[0].topic_name'] and caution.queue_item_id
    title = next(l for l in c_deps.links if l.element == 'TITLE')
    assert title.relation == 'DIRECT' and card['topic_name'] in title.note
    assert next(l for l in c_deps.links if l.element == 'SUMMARY').relation == 'NOT_ESTABLISHED'
    assert agent1.findings[0].category == 'RESOLUTION'
    assert {'claim:c1', 'reporter:U011', 'summary'} <= links(a_deps, 'DIRECT', True)
    assert 'This run records no sentence-to-claim links' in a_deps.record_gaps[0]


def test_audit_unavailable_record_cannot_be_narrowed():
    _, _, [(prov, deps)] = flags_for('agent3_final_eval_v1', 'cluster_9378eb54bc546fcd/topic_1')
    assert prov.recovery == 'NOT_NARROWED'
    assert prov.findings and all(f.nature == 'PROCESS_FAILURE' and not f.message_ids for f in prov.findings)
    assert not links(deps, 'DIRECT') and not links(deps, 'DERIVED') and not links(deps, 'SAME_THREAD')
    assert {'claim:c2', 'action', 'summary'} <= links(deps, 'NOT_ESTABLISHED', True)


def test_disputed_member_resolution_feeds_the_topic_state():
    _, card, [(prov, deps)] = flags_for('agent3_final_eval_v1', 'cluster_3b950ad40b12ab58/topic_1')
    topic = next(l for l in deps.links if l.element == 'TOPIC_RESOLUTION')
    assert card['resolution_status'] == deps.topic_resolution == 'UNRESOLVED'
    assert topic.relation == 'DERIVED' and topic.via == ['resolution:member_74e92dc600ce9bbc7f5bfc91']
    flagged = next(i for i in deps.resolution_inputs if i.flagged)
    assert 'PARTIALLY_RESOLVED' in flagged.states_changing_topic


def test_discarded_revision_check_is_not_the_finding():
    _, _, found = flags_for('agent3_policy_eval_v1', 'cluster_6b59d13144282285/topic_2')
    prov = found[1][0]
    assert prov.card_detail_is == 'ATTEMPT_ERROR' and prov.card_detail.startswith('Still unverified after one targeted revision')
    assert [f.category for f in prov.findings] == ['SUMMARY', 'CENTRAL_QUESTION', 'RESOLUTION']
    assert [e.stage for e in prov.attempt_errors] == ['NON_EFFECTIVE_ATTEMPT']


def test_projection_gap_is_a_card_only_grouping_condition():
    run, card, found = flags_for('agent3_writing_eval_v17_v1', None)
    gap, deps = found[-1]
    assert gap.category == 'TOPIC_GROUPING' and gap.label == GROUPING_LABEL and gap.queue_item_id is None
    assert gap.recovery == 'NOT_APPLICABLE' and not gap.findings
    assert {l.element for l in deps.links} == {'TOPIC_MEMBERSHIP', 'TITLE'}
    assert len(run.queue) == 52 and not any(i.kind == 'projection_gap' for i in run.queue.values())
    assert all(p.queue_item_id in run.queue for p, _ in found[:-1])
    with pytest.raises(ValueError):
        FlagProvenance(**{**gap.model_dump(), 'queue_item_id': 'review_x'})
    item = next(i for i in run.review(card['card_id'])['items'] if i['code'] == 'INHERITED_FLAG')
    assert item['title'] == '2 earlier review flags are still open; topic grouping needs review'
    entry = next(f for f in item['flags'] if f['grouping'])
    assert entry['label'] == GROUPING_LABEL and 'not an Agent 1/2 review obligation' in entry['check']
    submit = next(f for f in item['flags'] if not f['grouping'] and f['finding']['card_detail_is'] == 'ATTEMPT_ERROR')
    assert [x['category'] for x in submit['finding']['findings']] == ['CENTRAL_QUESTION', 'AUTHORITY']


def test_changed_or_missing_handoff_binding_is_recorded_not_guessed(tmp_path):
    source = EXP/'agent3_summary_eval_v1'
    card = json.loads((source/'cards.json').read_text(encoding='utf-8'))[1]
    for name, edit in (('changed', lambda m: m['fingerprints']['handoff'].update(canonical_sha256='0' * 64)),
                       ('missing', lambda m: m['fingerprints'].pop('handoff'))):
        run = tmp_path/name
        run.mkdir()
        shutil.copy(source/'review_queue.json', run)
        manifest = json.loads((source/'run_manifest.json').read_text(encoding='utf-8'))
        edit(manifest)
        (run/'run_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        [prov] = FlagSource(run, f'{name}#x').provenance(card)
        assert prov.recovery == 'UNAVAILABLE' and not prov.findings and prov.recovery_note


def test_report_matches_the_manual_audit_and_mutates_nothing():
    spec = importlib.util.spec_from_file_location('report_flag_dependence', ROOT/'scripts/report_flag_dependence.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    main, run_hashes = report.main, report.run_hashes
    runs = ['agent3_policy_eval_v1', 'agent3_summary_eval_v1', 'agent3_final_eval_v1', 'agent3_writing_eval_v17_v1',
            'agent3_repair_eval_v1']
    before = run_hashes(runs)
    assert main([]) == 0
    assert run_hashes(runs) == before
    labels = json.loads((ROOT/'data/evaluation/agent3_flag_dependence_labels_v1.json').read_text(encoding='utf-8'))
    assert labels['label_type'] == 'HUMAN_ASSESSMENT'
