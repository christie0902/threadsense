"""Offline comparison: production batch follow-ups versus the opt-in adaptive (react) controller. Zero model calls.

Same work items, initial research, first follow-up query, snapshot (the active .index/retrieval) and filters in both
arms. What is real: local retrieval (hybrid ranking, version and scope filters, the bounded recorded-link expansion),
the evidence ledger, the controller's sequencing, stop rules and request accounting. What is scripted: the prepared
drafts (tests/fixtures/agent3_pilot_scripted_judgments.json, or a gap written for this experiment where labelled) and
every controller decision (advisor_research.scripted_decision, a deterministic stand-in reading recorded fields).
No revision is generated, so whether recovered evidence would be USED in a revised answer is not measured here.

  uv run --locked python scripts/run_agent3_react_comparison.py                 # plan only
  uv run --locked python scripts/run_agent3_react_comparison.py --write data/experiments/agent3_react_comparison_v1
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

FROZEN_QUERY = ('Audio multimodal batch 05 one-reload playback trial ending August 28 2026: observed results and decisions '
                'extending, ending or replacing the trial; applicability to batch 06 player never loads or waveform '
                'visible with no playback')
CASES = [
    {'id': 'audio_trial_outcome', 'scenario': 'audio_playback',
     'question': 'Did the earlier batch-05 one-reload playback trial have a recorded outcome?',
     'gap': {'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'query': FROZEN_QUERY,
             'source_types': ['decision', 'announcement', 'guideline'], 'version_mode': 'history'},
     'gap_source': 'The frozen live follow-up query (agent3_open_evaluation_cases.json, audio_trial_outcome_followup_miss).',
     'expected': ['audio-playback-trial-outcome@1.0'],
     # agent3_final_eval_v1 (live, prompts v6.2): this topic's comparison ran on the OPEN_CONFIRMATION trigger.
     'live_tot_triggers': ['OPEN_CONFIRMATION']},
    {'id': 'control_initial_evidence_answers', 'scenario': 'submit_failure',
     'question': 'What is the current handling for the Submit reports? (current instructions answer it)',
     'gap': None, 'gap_source': 'The prepared Submit draft names no follow-up: the initial evidence covers it.', 'expected': []},
    {'id': 'gap_corpus_cannot_answer', 'scenario': 'repeated_ending',
     'question': 'Was the repeated final line confirmed in a downloaded recording or on a second player?',
     'gap': {'gap_id': 'g1', 'need': 'PRIOR_DECISION_OUTCOME', 'source_types': ['decision'], 'version_mode': 'history',
             'query': 'repeated final line in exported audio: result of the downloaded-recording or second-player comparison'},
     'gap_source': 'Written for this experiment (the prepared draft names this gap without a query); the corpus records '
                   'only the deferred review that requested this evidence.', 'expected': []},
]


def setup(case, retriever, view, expansion):
    from threadsense.agents import advisor_pilot as pilot
    from threadsense.agents.advisor_evidence import Budget, ResearchTools, member_messages
    scenario = next(s for s in json.loads(pilot.SCENARIOS.read_text(encoding='utf-8'))['scenarios'] if s['id'] == case['scenario'])
    packet = pilot.topic_packet(view, scenario)
    budget = Budget(pilot.BUDGET)
    budget.start_topic()
    tools = ResearchTools(retriever, project=packet['project_id'], batch=packet['batch_id'], as_of=retriever.manifest['cutoff'],
                          budget=budget, top_k=pilot.TOP_K, expansion=expansion,
                          ledger={i['evidence_id']: i for i in member_messages(packet['members'])})
    query = pilot.initial_query(packet)
    tools.search(query, purpose='initial_current_guidance')
    if tools.withheld:
        tools.search(query, purpose='supersession_check', version_mode='history')
    return scenario, packet, tools


def tot_triggered(case, tools):
    """Whether the prepared draft would trigger the option comparison (needed for the request estimate)."""
    from threadsense.agents import advisor_tot
    from threadsense.agents.advisor_checks import temporal_check
    from threadsense.agents.advisor_contracts import AdvisorDraft
    from threadsense.agents.advisor_pilot import ScriptedClient
    raw = ScriptedClient(ROOT/'tests/fixtures/agent3_pilot_scripted_judgments.json').responses[case['scenario']]['draft']
    draft = AdvisorDraft.model_validate(raw if isinstance(raw, dict) else json.loads(raw))
    return advisor_tot.triggers(draft, temporal_check(draft, tools.ledger), tools.ledger)


def found(ids, expected):
    return sorted({e for e in expected for i in ids if e in i})


def batch_arm(case, retriever, view, expansion):
    _, packet, tools = setup(case, retriever, view, expansion)
    triggers = tot_triggered(case, tools)
    initial = set(tools.ledger)
    steps = []
    if case['gap']:
        g = case['gap']
        tools.search(g['query'], purpose=f"gap:{g['need']}", source_types=g['source_types'], version_mode=g['version_mode'],
                     gap_id=g['gap_id'])
        t = tools.trace[-1]
        steps.append({'step': 1, 'gap_id': g['gap_id'], 'query': g['query'], 'status': t['status'],
                      'returned_ids': t.get('result_ids', []), 'added_by_expansion': [a['evidence_id'] for a in t.get('added', [])],
                      'new_evidence_ids': [i for i in tools.ledger if i not in initial]})
    recovered = [i for s in steps for i in s['new_evidence_ids']]
    requests = 1 + (1 if steps else 0) + (1 if triggers else 0) + 1
    return {'arm': f"batch (production){'' if expansion else ', expansion off'}", 'expansion': expansion, 'steps': steps,
            'stop_reason': 'NO_GAP' if not steps else 'ALL_REQUESTED_QUERIES_RUN', 'tot_triggers': triggers,
            'recovered_evidence_ids': recovered, 'expected_found': found(recovered, case['expected']),
            'local_searches': len(tools.trace), 'follow_up_searches': len(steps),
            'model_requests_estimate': {'draft': 1, 'revision': 1 if steps else 0, 'tot': 1 if triggers else 0, 'grounding': 1,
                                        'total': requests}}


def react_arm(case, retriever, view, expansion, ceiling=4, triggers_override=None):
    from threadsense.agents import advisor_research as research
    _, packet, tools = setup(case, retriever, view, expansion)
    triggers = triggers_override or tot_triggered(case, tools)
    initial = set(tools.ledger)
    decisions = []
    left = {'requests': ceiling - 1}  # After the draft.

    def room_for_another():
        need = 3 + (1 if triggers else 0)
        return left['requests'] >= need, (f"A second search needs {need} more requests (revision, second revision, "
                                          f"{'comparison, ' if triggers else ''}grounding); {left['requests']} remain under "
                                          f'the {ceiling}-request ceiling.')

    def revise(may_search, steps):
        left['requests'] -= 1
        observed = [tools.ledger[i] for i in steps[-1]['returned_ids'] + steps[-1]['added_by_expansion'] if i in tools.ledger]
        d = research.scripted_decision(case['gap'], observed, tools.ledger)
        decisions.append({'after_step': len(steps), 'may_search': may_search, 'filled': d['filled'],
                          'request': d['request']['query'] if d['request'] and may_search else None, 'basis': d['basis'],
                          'decided_by': 'SCRIPTED_STAND_IN'})
        return {'draft': None, 'request': d['request'] if may_search else None, 'filled': d['filled']}
    out = research.adaptive_research(tools, case['gap'], revise, room_for_another=room_for_another,
                                     topic_text=packet['topic_label'])
    recovered = [i for i in tools.ledger if i not in initial]
    useful = found(recovered, case['expected'])
    filled_at = next((s['step'] for s in out['steps'] if found(s.get('new_evidence_ids', []), case['expected'])), None)
    unnecessary = sum(1 for s in out['steps'] if s['status'] == 'DONE' and (filled_at is None or s['step'] > filled_at))
    requests = 1 + out['revisions'] + (1 if triggers else 0) + 1
    label = (f"react (opt-in){'' if expansion else ', expansion off'}{'' if ceiling == 4 else f', ceiling {ceiling}'}"
             + (', comparison triggered as in the live v6.2 run' if triggers_override else ''))
    return {'arm': label, 'expansion': expansion, 'ceiling': ceiling, 'steps': out['steps'], 'decisions': decisions,
            'stop_reason': out['stop_reason'], 'note': out['note'], 'fifth_request_needed': out['fifth_request_needed'],
            'tot_triggers': triggers, 'recovered_evidence_ids': recovered, 'expected_found': useful,
            'unnecessary_follow_up_searches': unnecessary, 'local_searches': len(tools.trace),
            'follow_up_searches': sum(s['status'] == 'DONE' for s in out['steps']),
            'model_requests_estimate': {'draft': 1, 'revision': out['revisions'], 'tot': 1 if triggers else 0, 'grounding': 1,
                                        'total': requests}}


def run():
    from threadsense.agents.advice_inputs import load_effective_view
    from threadsense.agents.advisor_evidence import open_retriever
    from threadsense.agents.advisor_pilot import HANDOFF
    retriever, view = open_retriever(), load_effective_view(HANDOFF)
    try:
        cases = []
        for case in CASES:
            arms = [batch_arm(case, retriever, view, True), react_arm(case, retriever, view, True)]
            if case['gap']:
                arms += [batch_arm(case, retriever, view, False), react_arm(case, retriever, view, False),
                         react_arm(case, retriever, view, False, ceiling=5)]
                if case.get('live_tot_triggers'):
                    arms += [react_arm(case, retriever, view, False, triggers_override=case['live_tot_triggers'])]
            for arm in arms:  # Unnecessary searches for batch: follow-ups that recovered nothing expected.
                if arm['arm'].startswith('batch'):
                    arm['unnecessary_follow_up_searches'] = sum(1 for s in arm['steps'] if s['status'] == 'DONE'
                                                                and not found(s['new_evidence_ids'], case['expected']))
            cases.append({k: case[k] for k in ('id', 'scenario', 'question', 'gap', 'gap_source', 'expected')} | {'arms': arms})
        return {'version': 'agent3-react-comparison-v1', 'model_calls': 0,
                'snapshot': {k: retriever.manifest[k] for k in ('build_fingerprint', 'cutoff', 'chunking_version')},
                'scripted': {'drafts': 'prepared (tests/fixtures/agent3_pilot_scripted_judgments.json); gaps as labelled per case',
                             'controller_decisions': 'advisor_research.scripted_decision (deterministic stand-in)',
                             'revisions': 'not generated; "used" is not measured offline'},
                'real': ['local hybrid retrieval on the active snapshot', 'version, scope and date filters',
                         'recorded-link expansion (when on)', 'evidence ledger', 'controller sequencing and stop rules'],
                'cases': cases}
    finally:
        if getattr(retriever, 'client', None) is not None:
            retriever.client.close()


def table(report):
    rows = ['| Case | Arm | Follow-up searches | Expected evidence recovered | Used in a revision | Unnecessary searches | '
            'Stop reason | Model requests (est.) |', '|---|---|---|---|---|---|---|---|']
    for case in report['cases']:
        for a in case['arms']:
            got = ', '.join(a['expected_found']) or ('n/a' if not case['expected'] else 'no')
            req = a['model_requests_estimate']['total']
            rows.append(f"| {case['id']} | {a['arm']} | {a['follow_up_searches']} | {got} | not measured offline | "
                        f"{a['unnecessary_follow_up_searches']} | {a['stop_reason']} | {req}{' (over the ceiling)' if req > 4 else ''} |")
    return '\n'.join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--write', type=Path, help='New output directory (must not exist).')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error(f'{args.write} exists; choose a new output directory.')
    report = run()
    print(table(report))
    if args.write:
        args.write.mkdir(parents=True)
        (args.write/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (args.write/'report.md').write_text(f"# Batch versus adaptive follow-up research (offline)\n\nZero model calls. "
                                            f"Snapshot {report['snapshot']['build_fingerprint'][:12]} (cutoff "
                                            f"{report['snapshot']['cutoff']}). Controller decisions: scripted stand-in. "
                                            f"Drafts: prepared.\n\n{table(report)}\n", encoding='utf-8')
        print(f'Wrote {args.write}')


if __name__ == '__main__':
    main()
