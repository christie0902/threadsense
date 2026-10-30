"""Extract recorded acceptance-run items used as regression cases into tests/fixtures/agent3_acceptance_v1_cases.json.

Source: data/experiments/agent3_acceptance_v1 and agent3_readability_v1 (gpt-6.1-sol, LIVE_MODEL, read only). Each case keeps the exact recorded
model output and the SHA-256 of the raw response it came from; retrieved evidence items are copied from the run's
evidence ledger (member messages are rebuilt from the handoff by the tests).
  uv run --locked python tests/fixtures/make_agent3_acceptance_cases.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'data/experiments/agent3_acceptance_v1'


def result(scenario):
    return json.loads((RUN/'results'/f'{scenario}.json').read_text(encoding='utf-8'))


def source(r, stage):
    call = next(c for c in r['model_calls'] if c['stage'] == stage)
    return {'file': f"results/{r['scenario']['id']}.json", 'stage': stage, 'raw_sha256': call['raw_sha256']}


def claim(r, claim_id):
    return next(c for c in r['drafts']['final']['claims'] if c['claim_id'] == claim_id)


def retrieved(r):
    return {k: v for k, v in r['evidence_ledger'].items() if v['origin'] == 'retrieved_source'}


audio, prose, korean, submit, pii = (result(s) for s in ('audio_playback', 'json_vs_prose', 'korean_register',
                                                           'submit_failure', 'fictional_pii'))
judgment = json.loads(next(c for c in submit['model_calls'] if c['stage'] == 'grounding')['raw'])
cases = {
    'false_name_rejections': {
        'failure': 'NAME_NOT_IN_CITED_EVIDENCE for correct names: the owner of the cited message\'s thread, not its author.',
        'claims': [{'scenario': 'json_vs_prose', 'source': source(prose, 'draft'), 'claim': claim(prose, 'C6')},
                   {'scenario': 'korean_register', 'source': source(korean, 'draft'), 'claim': claim(korean, 'c5')},
                   {'scenario': 'audio_playback', 'source': source(audio, 'draft'), 'claim': claim(audio, 'c2')}]},
    'submit_dependency': {
        'scenario': 'submit_failure', 'source': {'draft': source(submit, 'draft'), 'grounding': source(submit, 'grounding')},
        'failure': 'The judge named C13 essential (shown as SENT) while judging the announcement C13 rests on UNSUPPORTED.',
        'draft': submit['drafts']['final'], 'judgment': judgment, 'retrieved_evidence': retrieved(submit)},
    'pii_superseded_section': {
        'scenario': 'fictional_pii', 'source': source(pii, 'draft'),
        'failure': 'A superseded help-page section against two current sources was reported as an unexplained conflict.',
        'source_conflicts': pii['drafts']['final']['source_conflicts'],
        'established_handling': pii['established_handling'],
        'retrieved_evidence': {e: pii['evidence_ledger'][e] for c in pii['drafts']['final']['source_conflicts']
                               for e in c['evidence_ids']}},
}
# Readability run (data/experiments/agent3_readability_v1, pilot v6): deterministic false rejections found there.
READ = ROOT/'data/experiments/agent3_readability_v1'
if READ.exists():
    def read_result(scenario):
        return json.loads((READ/'results'/f'{scenario}.json').read_text(encoding='utf-8'))
    r_audio, r_submit = read_result('audio_playback'), read_result('submit_failure')
    signal = next(x for x in r_audio['drafts']['final']['severity']['signals'] if (x['level'], x['signal_index']) == ('HIGH', 0))
    record = 'k:rp-submit-engineering-handoff@1.0:d84c905d'
    cases['readability_false_rejections'] = {
        'source_run': 'data/experiments/agent3_readability_v1',
        'failure': 'PLURAL_NOT_SUPPORTED_BY_DISTINCT_AUTHORS for "two tutors\' threads" (thread starters, not authors) and '
                   'ATTRIBUTION_INVALID for a record whose authority actor is the attributed team lead.',
        'possessive_plural': {'scenario': 'audio_playback', 'source': source(r_audio, 'revision'),
                              'claim': next(c for c in r_audio['drafts']['final']['claims'] if c['claim_id'] == 'c8'),
                              'signal': signal},
        'record_author': {'scenario': 'submit_failure', 'source': source(r_submit, 'draft'),
                          'claim': next(c for c in r_submit['drafts']['final']['claims'] if c['claim_id'] == 'c6'),
                          'retrieved_evidence': {record: r_submit['evidence_ledger'][record]}},
        'review_note': {'scenario': 'audio_playback', 'source': source(r_audio, 'revision'),
                        'text': r_audio['drafts']['final']['review_note']}}
out = ROOT/'tests/fixtures/agent3_acceptance_v1_cases.json'
out.write_text(json.dumps({'source_run': 'data/experiments/agent3_acceptance_v1', 'cases': cases}, ensure_ascii=False,
                          indent=1, sort_keys=True) + '\n', encoding='utf-8')
print(f'wrote {out}')
