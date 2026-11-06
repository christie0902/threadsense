"""Replay one topic of a saved overnight run through the current Advisor, zero model calls.

The recorded draft, revision and ToT outputs are fed back unchanged; a recorded grounding verdict is reused only for
a statement whose kind, text, evidence and attributions and whose full evidence context are unchanged (see
advisor_pilot.ReplayClient). Anything the current code needs that was not judged in the recorded run stays PENDING.
Retrieval uses the run's recorded snapshot (its build fingerprint must match) and the run's own expansion setting.

  uv run --locked python scripts/replay_overnight_topic.py --run data/experiments/agent3_repair_eval_v1 \
      --work topic:cluster_6b59d13144282285/topic_2 [--write <new path>]

Consolidated work items (consolidated:<id>) replay against the consolidation and processing history the run fingerprinted.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def replay(run, work_id, *, view=None, retriever=None, client=None):
    """(result, summary) for one work item of a saved overnight run, zero model calls. A consolidated work item and the
    processing history are rebuilt from the records the run itself fingerprinted (threadsense-full-run-v2). client: a
    ReplayClient (subclass) for this run; default the plain recorded replay."""
    from threadsense.agents import advisor_pilot as pilot
    for name, value in pilot.QUIET_ENV.items():
        os.environ.setdefault(name, value)
    from threadsense.agents import overnight
    from threadsense.agents.advisor_evidence import Budget
    from threadsense.handoff_inputs import ROOT, read_json
    from threadsense.severity_rubric import load_rubric
    manifest = read_json(run/'run_manifest.json')
    fingerprints = manifest['fingerprints']
    close = retriever is None
    if retriever is None:
        index_dir = fingerprints['index'].get('index_dir') or '.index/retrieval'
        retriever = overnight.open_snapshot(ROOT/index_dir if not Path(index_dir).is_absolute() else Path(index_dir))
    if retriever.manifest['build_fingerprint'] != fingerprints['index']['build_fingerprint']:
        raise SystemExit('The recorded snapshot is no longer the one at that path; replay needs the original snapshot.')
    view = view or recorded_view(run)
    item = next(w for w in overnight.plan(view) if w['work_id'] == work_id)
    scenario = {'id': work_id, 'candidate_group_id': item['candidate_group_id'], 'focus': item['topic_name'] or 'projection gap',
                **({'topic_id': item['topic_id']} if item['topic_id'] else {}),
                **({'consolidated_topic_id': item['topic_id']} if item['kind'] == 'CONSOLIDATED_TOPIC' else {})}
    client = client or pilot.ReplayClient(run)
    result = pilot.advise(scenario, view=view, retriever=retriever, client=client, budget=Budget(overnight.PER_TOPIC),
                          rubric=load_rubric(None), run_id=manifest['run_id'], as_of=retriever.manifest['cutoff'])
    if close:
        retriever.client.close()
    recorded = next(r['result'] for r in (read_json(p) for p in (run/'topics').rglob('*.json'))
                    if r['work_item']['work_id'] == work_id)
    old = {s['statement_id']: s['verdict'] for s in recorded['grounding']['statements']}
    new = {s['statement_id']: s['verdict'] for s in result['grounding']['statements']}
    summary = {'work_id': work_id, 'model_calls_sent': sum((c.get('http_requests') or {}).get('sent', 0) for c in result['model_calls']),
               'same_evidence_context': set(result['evidence_ledger']) == set(recorded['evidence_ledger']),
               'grounding': {'recorded': recorded['grounding']['status'], 'replay': result['grounding']['status'],
                             'replay_basis': result['grounding']['basis']},
               'changed_verdicts': {k: [old.get(k), new.get(k)] for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)},
               'pending': result['grounding'].get('pending'),
               'card': {'recorded_action': (recorded['card']['recommended_action'] or {}).get('action_type'),
                        'replay_action': (result['card']['recommended_action'] or {}).get('action_type'),
                        'replay_line': result['card']['card_line'],
                        'replay_reasons': [r['code'] for r in result['card']['needs_review_reasons']]},
               'reuse': {'reused': sum(r['reused'] for r in client.reuse_log), 'not_reused': [
                   {k: r[k] for k in ('statement_id', 'reason')} for r in client.reuse_log if not r['reused']]}}
    return result, summary


def recorded_view(run):
    """The effective view the run advised: its handoff, less processing-history groups, with its consolidation."""
    from threadsense.agents.advice_inputs import apply_consolidation, load_effective_view
    from threadsense.handoff_inputs import ROOT, read_json
    fingerprints = read_json(run/'run_manifest.json')['fingerprints']
    view = load_effective_view(ROOT/fingerprints['handoff']['run'])
    if fingerprints.get('processing_history'):
        history = {h['member_id'] for h in read_json(ROOT/fingerprints['processing_history']['path'])}
        view = {**view, 'records': [r for r in view['records'] if not {m['member_id'] for m in r['members']} <= history]}
    if fingerprints.get('consolidation'):
        view = apply_consolidation(view, read_json(ROOT/fingerprints['consolidation']['path']))
    return view


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--work', required=True, help='Work ID in that run.')
    parser.add_argument('--write', type=Path, help='New path for the replayed result JSON.')
    args = parser.parse_args(argv)
    if args.write and args.write.exists():
        parser.error('--write must be a new path.')
    sys.stdout.reconfigure(encoding='utf-8')
    result, summary = replay(args.run, args.work)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(json.dumps({'summary': summary, 'result': result}, ensure_ascii=False, indent=1, default=str) + '\n',
                              encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
