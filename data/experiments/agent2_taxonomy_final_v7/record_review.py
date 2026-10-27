"""One-off, zero-call publication of the completed Codex-assisted taxonomy review.

Observations below were made by inspecting all 90 saved outputs against their
canonical Agent 1 summaries/questions. This does not re-evaluate original Slack.
No generated response, automated outcome, or inherited obligation is changed.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from threadsense.handoff_inputs import ROOT, read_json, file_hash, digest
from threadsense.agents.topic_pipeline import write_json
from threadsense.agents.topic_effective import REGISTRY, load_effective_output

HERE = Path(__file__).resolve().parent
RUN = ROOT/'data/processed/agent2_taxonomy_final_v7'
REVIEW = HERE/'taxonomy_review.json'

NOTES = {
    'cluster_6042d88a3d171626': 'Appropriate split: transcript/recording correspondence (members 1-3) versus silent/zero-audio file handling (4).',
    'cluster_6b59d13144282285': 'Accepted pilot split retained: silent/empty audio (1,4) versus player playback failure (2,3,5,6). Both inherited disputes remain.',
    'cluster_e6a79dfad226e738': 'Appropriate split: silent file-content check (1) versus buffering player (2).',
    'cluster_6d503e25f7b2c30c': 'Appropriate split: regional Vietnamese vocabulary acceptability (1) versus English language switching (2). Both inherited disputes remain.',
    'cluster_839fecb69ec3fa12': 'Coherent split: unfindable/nonexistent references (1,2) versus DOI pointing to an unrelated publication (3). No new source verification.',
    'cluster_f944891544b06f79': 'Coherent split: cosmetic-difference tie judgments (1,2) versus inconsistent QA tie decisions/calibration (3-5). Rationale is grouping metadata, not scoring authority.',
    'cluster_01c1906236921239': 'Appropriate split: QA coverage schedule (1) versus batch/guidance-scope announcement (2).',
    'cluster_ab4fa9e9a46e0a07': 'Fixed sample: five playback/blank-player/spinner reports share a coherent tool-failure topic; canonical differences and inherited disputed history remain in members.',
    'cluster_0df9e215dec4e314': 'Fixed sample: Korean/English and Spanish/English cases share language-adherence subject matter; no language-specific scoring judgment is established by membership.',
    'cluster_3b950ad40b12ab58': 'Fixed sample: Korean honorific/register transitions remain together, including prior-discussion lookup and unresolved QA handling questions.',
    'cluster_14c5fc257d90b58f': 'Fixed sample: five disabled/unresponsive submission reports cohere; three inherited obligations retained.',
    'cluster_7a710abcd893e0a6': 'Fixed sample: warning/support quotations share contextual-classification subject matter; grouping does not decide safety labels.',
    'cluster_1f272d7fa384df0c': 'Fixed sample: override/jailbreak language versus actual output classification cohere; no new category decision.',
    'cluster_bc1ccc03c19a64cf': 'Accepted pilot: overlapping speech and unintelligible-span labeling share a coherent topic.',
    'cluster_b3bfce178039d7d4': 'Accepted pilot: calibration and queue-assignment announcements fit a broad workflow-announcement topic; retain separate canonical members and the inherited dispute.',
    'cluster_be4e3bac742eccb3': 'Accepted pilot: social language-day greeting remains a singleton; no work question invented by the taxonomy producer.',
    'cluster_2349d858e077f77b': 'Queue reopening and reference-resource announcements share an intentionally broad team-information topic; distinct canonical records remain available.',
    'cluster_098a12c005ecf00b': 'Onboarding-resource and queue-closing announcements share a broad announcements topic; no claim that they are one incident.',
    'cluster_797c816fbcc6ccc1': 'Timestamp-review name emphasizes coordination within the canonical defect-label disagreement; no consequential mismatch or new operational severity.',
    'cluster_1ba596334ad5cde7': 'Version-conflict topic preserves canonical supersession questions without itself selecting an authoritative document.',
    'cluster_d9ad05f5bda622e1': 'Fictional/placeholder contact handling is coherent despite inherited canonical QN wording errors. No re-interpretation or flag clearance performed.',
}

CAUTIONS = {
    'cluster_7249f5e5bbe9af0b': {
        'summary': 'The Spanish-specific title is narrower than the full language-switching membership.',
        'detail': 'The name "Requested English audio generated in Spanish" fits several members, but member 4 concerns a mid-clip switch to another language without naming Spanish. Shared requested-language adherence is coherent; the title must not assert that every member reports Spanish.',
        'member_numbers': [1, 4],
    },
    'cluster_b7e5234380f9ea67': {
        'summary': 'The exported-audio title over-specifies the location of repetition for members still comparing file and player.',
        'detail': '"Repeated final line in exported audio" fits confirmed-file members, but members 1 and 4 still need to distinguish file repetition from LT playback. Repeated-ending membership is coherent. Neither the title nor recurrence establishes the location or cause for every member.',
        'member_numbers': [1, 4],
    },
    'cluster_a6dfe8374217a497': {
        'summary': 'The answer-shaped topic name must not be consumed as a general Quarantine rule.',
        'detail': '"Minor mention alone does not require QN" generalizes a decision-shaped title across a coherent group whose member 2 explicitly has no general answer and member 3 retains a handling question/diagnostic context. This review concerns the title, not the underlying policy. Use it only as grouping metadata; canonical questions remain available for later research.',
        'member_numbers': [1, 2, 3],
    },
}


def main():
    if REVIEW.exists():
        raise FileExistsError('Preserve the published review; do not overwrite it.')
    rows = read_json(RUN/'consolidations.json')
    selection = read_json(HERE/'review_selection.json')
    assert len(rows) == 90
    entries = []
    for row in rows:
        gid = row['candidate_group_id']; d = RUN/'records'/gid
        mids = [m['member_id'] for m in row['members']]
        actual = [x for t in row['topics'] for x in t['member_ids']] + row['rejected_member_ids'] + row['unassigned_member_ids']
        assert sorted(actual) == sorted(mids) and len(actual) == len(set(actual))
        entry = {
            'candidate_group_id': gid, 'project_id': row['project_id'],
            'binding': {'input_file_sha256': file_hash(d/'input.json'),
                        'raw_draft_sha256': file_hash(d/'analysis.raw.txt'),
                        'export_result_sha256': file_hash(d/'result.json')},
            'processing_state': row['processing_state'], 'member_count': len(mids),
            'inherited_obligations_retained': len(row['inherited_review_obligations']),
            'fixed_sample': gid in selection['fixed_group_ids'],
            'accepted_pilot': gid in selection['pilot_groups'],
            'split': len(row['topics']) > 1,
            'topic_names_and_members': [{k:t[k] for k in ('topic_id','topic_name','member_ids')} for t in row['topics']],
            'canonical_review_basis': [{'member_id':m['member_id'],
                'full_identity':{k:m[k] for k in ('project_id','batch_id','channel_id','thread_id')},
                'candidate_sha256':m['agent1_record']['candidate_sha256'],
                'source_sha256':m['agent1_record']['input_sha256'],
                'summary':m['agent1_record']['interpretation']['summary'],
                'central_question':m['agent1_record']['interpretation']['central_question']}
                for m in row['members']],
            'summary': NOTES.get(gid, 'Reviewed saved names and every assigned member against canonical summaries/questions; coherent subject matter and no consequential membership defect observed.'),
            'partition_check': 'PASS',
            'assisted_content_review_required': gid in CAUTIONS,
            'findings': [],
        }
        if gid in CAUTIONS:
            caution = CAUTIONS[gid]
            entry['findings'] = [{
                'kind': 'TAXONOMY_NAMING_CAUTION', 'affected_fields': ['topics[0].topic_name'],
                'summary': caution['summary'], 'detail': caution['detail'],
                'scope': 'Nonblocking naming caution; no membership correction or policy/answer validation.',
                'canonical_member_evidence': [deepcopy(entry['canonical_review_basis'][n-1]) for n in caution['member_numbers']],
                'nonblocking': True, 'requires_new_model_call': False,
                'membership_defect_observed': False,
            }]
        entries.append(entry)
    review = {
        'origin': 'Codex-assisted taxonomy review against canonical Agent 1 interpretations; not human approval, raw-Slack verification, or independent ground truth',
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'run': RUN.relative_to(ROOT).as_posix(),
        'selection_file': (HERE/'review_selection.json').relative_to(ROOT).as_posix(),
        'selection_sha256': file_hash(HERE/'review_selection.json'),
        'reviewed_scope': 'All 90 groups / 200 canonical members; all seven splits plus the eight fixed pre-output samples and four accepted pilot groups. No rejected, all-rejected or failed groups occurred.',
        'limitations': [
            'Grouping review does not validate canonical interpretations, answers, authority, source quotations, or policy.',
            'Rationales and names are grouping metadata, never authoritative guidance or operational severity.',
            'Granularity and broad announcement categories are subjective; repeated names do not merge candidate groups.',
            'No live rejection/failure/UNKNOWN-completion behavior occurred; retained offline tests cover those paths.',
            'Existing loader conservatively marks a cautioned topic assignment PROVISIONAL; the finding itself is about naming, not a demonstrated wrong member.'
        ],
        'decision': 'Taxonomy milestone complete with three nonblocking naming cautions and all inherited obligations retained; no obvious consequential membership defect observed.',
        'entries': entries,
    }
    write_json(REVIEW, review, exclusive=True)
    before = read_json(REGISTRY)
    updated = deepcopy(before)
    updated['supplements'].append({'run': RUN.relative_to(ROOT).as_posix(),
        'path': REVIEW.relative_to(ROOT).as_posix(), 'sha256': file_hash(REVIEW)})
    # Exercise the exact evidence binding before publishing the registry entry.
    trial = load_effective_output(RUN, additional_supplements=(REVIEW,))
    assert not trial['unapplied_findings'] and len(trial['applied_content_obligations']) == 3
    assert len(trial['member_review_queue']) == 49
    write_json(REGISTRY, updated)
    final = load_effective_output(RUN)
    assert final['records'] == trial['records'] and not final['unapplied_findings']
    assert updated['supplements'][:-1] == before['supplements']
    print({'reviewed_groups':len(entries), 'naming_cautions':3,
           'inherited_obligations':len(final['member_review_queue']),
           'effective_review_groups':len(final['review_queue']), 'model_calls':0})


if __name__ == '__main__':
    main()
