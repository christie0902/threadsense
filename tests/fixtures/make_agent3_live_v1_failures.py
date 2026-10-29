"""Extract the recorded live-v1 failures used as regression cases into tests/fixtures/agent3_live_v1_failures.json.

Source: data/experiments/agent3_pilot_live_v1 (gpt-4o-mini, LIVE_MODEL, read only). Each case keeps the exact recorded
model output (claim, severity proposal or member resolution) and the SHA-256 of the raw response it came from.
  uv run --locked python tests/fixtures/make_agent3_live_v1_failures.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/'data/experiments/agent3_pilot_live_v1'


def recorded(scenario):
    result = json.loads((RUN/'results'/f'{scenario}.json').read_text(encoding='utf-8'))
    call = next(c for c in result['model_calls'] if c['stage'] == 'draft')
    return result['drafts']['final'], {'file': f'results/{scenario}.json', 'stage': 'draft', 'raw_sha256': call['raw_sha256']}


def claim(draft, claim_id):
    return next(c for c in draft['claims'] if c['claim_id'] == claim_id)


pii, pii_src = recorded('fictional_pii')
rep, rep_src = recorded('repeated_ending')
audio, audio_src = recorded('audio_playback')
prose, prose_src = recorded('json_vs_prose')
cases = {
    'quotation': {'source': pii_src, 'scenario': 'fictional_pii', 'failure': 'Paraphrase presented as a verbatim quote; '
                  'in v1 it voided the whole draft.', 'claim': claim(pii, 'guidance_1'),
                  'other_claims': [claim(pii, 'incident_fact_1'), claim(pii, 'incident_fact_2')]},
    'guidance_from_slack': {'source': pii_src, 'scenario': 'fictional_pii',
                            'failure': 'A team lead Slack message cited as current guidance.', 'claim': claim(pii, 'guidance_2')},
    'attribution': {'source': rep_src, 'scenario': 'repeated_ending', 'failure': 'Affected reporter U017 cited with a '
                    "message by U013; in v1 it voided the severity assessment.", 'severity': rep['severity']},
    'reported_symptom': {'source': rep_src, 'scenario': 'repeated_ending', 'failure': 'Members\' claim that the repeat is in the '
                         'exported audio, which the team lead asked to verify.', 'claim': claim(rep, 'incident_fact_2')},
    'partial_thread_resolution': {'source': audio_src, 'scenario': 'audio_playback', 'failure': 'Resolution citing part of '
                                  'the thread; the uncited team lead reply gives interim handling.',
                                  'resolution': next(r for r in audio['resolution'] if r['member_id'].endswith('894091'))},
    'named_people': {'source': prose_src, 'scenario': 'json_vs_prose', 'failure': 'Claims name people; v1 evidence carried '
                     'author IDs only, so names could not be checked.', 'claims': [claim(prose, 'incident_fact_1'),
                                                                                    claim(prose, 'incident_fact_2')]},
}
out = ROOT/'tests/fixtures/agent3_live_v1_failures.json'
out.write_text(json.dumps({'version': 'agent3-live-v1-failures-v1', 'run': 'data/experiments/agent3_pilot_live_v1',
                           'run_id': json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))['run_id'],
                           'cases': cases}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
print('wrote', out)
