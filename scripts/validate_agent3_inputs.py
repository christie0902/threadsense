"""Validate Agent 3 milestone-2 inputs offline: knowledge corpus, rubric, Agent 2 handoff.

Zero model calls, no embeddings, no writes to source files. Prints a summary; with
--report, also saves the full JSON report to a fresh path. Exit 1 on errors,
2 on missing dependencies; warnings (open data questions, gaps) do not fail.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def dependencies():
    return {name: 'available' if importlib.util.find_spec(module) else 'MISSING'
            for name, module in (('pyyaml', 'yaml'), ('pydantic', 'pydantic'))}


def main(argv=None):
    from threadsense.routing import ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--knowledge-root', type=Path, default=ROOT/'data/knowledge')
    parser.add_argument('--fixtures', type=Path, default=ROOT/'data/fixtures/slack_generated_demo',
                        help='Active Slack snapshot (default: the 201-thread demo snapshot).')
    parser.add_argument('--original-fixtures', type=Path, default=ROOT/'data/fixtures/slack_generated',
                        help='Original 200-thread snapshot, counted for comparison and never modified.')
    parser.add_argument('--cutoff', default='2026-10-02T12:00:00Z', help='Fixture cutoff for snapshot counts.')
    parser.add_argument('--agent2-run', type=Path, default=ROOT/'data/processed/agent2_handoff_v2_projection',
                        help='Agent 2 export to account for (default: the schema-8 projection of the v7 release).')
    parser.add_argument('--report', type=Path, help='Fresh path for the full JSON report.')
    args = parser.parse_args(argv)
    if args.report is not None and args.report.exists():
        parser.error('--report must be a new path; reports are never overwritten.')
    deps = dependencies()
    if 'MISSING' in deps.values():
        print(json.dumps({'dependencies': deps, 'state': 'missing_dependencies'}, indent=2))
        return 2

    from threadsense.agents.advice_inputs import (
        DECISION_KINDS, coverage, decision_record_from_source, inspect_handoff, load_effective_view,
        review_items_from_announcement_route, review_items_from_view)
    from threadsense.handoff_inputs import read_json
    from threadsense.knowledge_corpus import validate_corpus
    from threadsense.source_ingestion import fixture_routes
    from threadsense.knowledge_markdown import markdown_source
    from threadsense.severity_rubric import compatibility_issues, load_rubric

    errors, warnings = [], []
    snapshots = {}
    for name, root in (('active', args.fixtures), ('original', args.original_fixtures)):
        if not (root/'channels').is_dir():
            errors.append(f'fixtures: {name} snapshot missing at {root}.')
            continue
        discussion, announcements, routes = fixture_routes(root, cutoff=args.cutoff)
        snapshots[name] = {'path': root.resolve().relative_to(ROOT).as_posix() if root.resolve().is_relative_to(ROOT) else str(root),
                           'cutoff': args.cutoff, 'threads': len(discussion) + len(announcements),
                           'messages': sum(len(t['messages']) for t in [*discussion, *announcements]),
                           'discussion_threads': len(discussion), 'announcement_threads': len(announcements)}
    corpus = validate_corpus(args.knowledge_root, fixture_root=args.fixtures)
    for key in ('normalization_failures', 'authoring_conflicts'):
        errors += [f'{key}: {json.dumps(item, ensure_ascii=False)}' for item in corpus[key]]
    # Overlaps are one source seen twice, never independent corroboration; report them.
    for key in ('duplicate_representations', 'overlapping_representations'):
        warnings += [f'{key}: {json.dumps(item, ensure_ascii=False)}' for item in corpus[key]]
    if corpus['shared_ingestion_error']:
        errors.append(f"shared ingestion: {corpus['shared_ingestion_error']}")
    if not corpus['stable_ids_on_repeat']:
        errors.append('Repeated normalization produced different IDs.')
    warnings += [f"reference: {json.dumps(item, ensure_ascii=False)}" for item in corpus['reference_issues']]

    decisions, decision_failures = [], []
    for path in sorted(args.knowledge_root.rglob('*.md')):
        if path.name == 'README.md' or not any(d['file'] == path.resolve().relative_to(args.knowledge_root.resolve()).as_posix()
                                               for d in corpus['documents']):
            continue
        record = markdown_source(path)
        if record.source_metadata['authoring'].get('record_kind') in DECISION_KINDS:
            try:
                decisions.append(decision_record_from_source(record))
            except ValueError as error:
                decision_failures.append(f'{path.name}: {error}')
    errors += [f'decision record: {item}' for item in decision_failures]

    try:
        rubric = load_rubric()
        rubric_summary = {k: rubric[k] for k in ('version', 'content_sha256', 'source_file', 'enum_values', 'rubric_scope')}
        rubric_summary['required_signals'] = {k: len(v['required_signals']) for k, v in rubric['levels'].items()}
        rubric_summary['project_scopes'] = {p: load_rubric(p)['rubric_scope'] for p in sorted(corpus['counts']['project_id'])}
        errors += [f'rubric: {issue}' for issue in compatibility_issues(rubric)]
    except Exception as error:  # A TL edit may break the file; report it rather than crash.
        rubric_summary = {'error': f'{type(error).__name__}: {error}'}
        errors.append(f"rubric: {rubric_summary['error']}")

    handoff = inspect_handoff(args.agent2_run)
    run = handoff.get('inspected_run', {})
    if handoff['active_export_status'] == 'UNAVAILABLE':
        warnings.append('agent2: no schema-8 / agent2-taxonomy-handoff-v2 export exists in the repository.')
    if run.get('error'):
        errors.append(f"agent2: {run['error']}")
    elif not run.get('matches_current_code_contract'):
        warnings.append(f"agent2: inspected {run.get('run')} uses {run.get('handoff_contracts')}, not the current contract.")
    if run.get('projection'):
        p = run['projection']
        warnings.append(f"agent2: {run['run']} is a projection of {p['source_release']}, not a fresh taxonomy run; "
                        f"{p['group_methods'].get('NOT_REUSABLE_PARTIAL_GROUP', 0)} partial groups have no reusable taxonomy.")
        if p['unresolved_naming_cautions']:
            warnings.append(f"agent2: {p['unresolved_naming_cautions']} naming caution(s) unresolved by the projection.")
    errors += [f'agent2 accounting: {issue}' for issue in run.get('accounting_issues', [])]
    for entry in run.get('registry', {}).get('entries_for_run', []):
        if not (entry['exists'] and entry['sha256_matches']):
            errors.append(f"agent2 registry: {entry['path']} missing or changed.")
    warnings += [f'agent2 registry: entry for absent run {r} (not applied to the inspected run).'
                 for r in run.get('registry', {}).get('entries_for_missing_runs', [])]
    review = {}
    if not run.get('error'):
        view = load_effective_view(args.agent2_run)
        items = review_items_from_view(view)
        missing = coverage(view, (), items)['missing_obligations']
        routed = args.agent2_run/'routing_manifest.json'
        announcement_items = review_items_from_announcement_route(
            read_json(routed)['announcement_sources']) if routed.is_file() else []
        errors += [f'review item missing obligation {key}' for key in missing]
        everything = [*items, *announcement_items]
        review = {'model_review_items': len(everything), 'from_agent2_groups': len(items),
                  'from_announcement_route': len(announcement_items),
                  'distinct_item_ids': len({i.item_id for i in everything}), 'obligations_without_item': len(missing)}

    report = {'dependencies': deps, 'model_calls': 0, 'fixture_snapshots': snapshots, 'rubric': rubric_summary,
              'corpus': corpus, 'decision_records': {'mapped': len(decisions), 'failures': decision_failures},
              'agent2_handoff': handoff, 'review_items': review,
              'errors': errors, 'warnings': warnings, 'state': 'failed' if errors else 'valid_with_warnings' if warnings else 'valid'}
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    summary = {'state': report['state'], 'model_calls': 0, 'dependencies': deps, 'fixture_snapshots': snapshots,
               'rubric': rubric_summary,
               'corpus': {k: corpus[k] for k in ('discovered', 'normalized_documents', 'unique_document_versions',
                                                 'shared_ingestion_documents', 'counts', 'stable_ids_on_repeat',
                                                 'supersession', 'overlap_scope')},
               'excluded_files': len(corpus['excluded']), 'decision_records': report['decision_records'],
               'agent2_handoff': {'code_contract': handoff['code_contract'],
                                  'active_export_status': handoff['active_export_status'],
                                  'inspected_run': {k: v for k, v in run.items() if k != 'registry'}},
               'review_items': review, 'errors': errors, 'warnings': warnings}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
