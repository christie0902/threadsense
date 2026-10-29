"""Project the reviewed Agent 2 v7 release onto the current routed handoff. Zero calls.

Not a fresh taxonomy run. Announcement members are routed out (kept, with their
obligations, in routing_manifest.json). Groups whose discussion membership is
unchanged are re-exported from their saved v7 responses with the current
schema-8 adapter. Groups that lost announcement members cannot reuse their saved
response without altering model output, so their members stay unassigned and
reviewable. Naming cautions carry over only when the group, its members and the
saved response bytes are identical; others stay listed as unresolved.
Read-only unless --write; the frozen release and review registry are never changed.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

from threadsense.handoff_inputs import ROOT, digest, file_hash, identity, read_json
from threadsense.topic_inputs import load_candidate_payloads, routing_manifest_for_payloads
from threadsense.agents.topic_consolidation import export_result, parse_response
from threadsense.agents.topic_effective import REGISTRY, load_effective_output
from threadsense.agents.topic_pipeline import write_json

RELEASE = ROOT/'data/processed/agent2_taxonomy_final_v7'
PROJECTION_VERSION = 'agent2-v7-release-to-handoff-v2-projection-v1'


def stored(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def verify_release(source, historical):
    """Every saved response must still reproduce its accepted v7 export exactly."""
    rows = {r['candidate_group_id']: r for r in read_json(source/'consolidations.json')}
    if set(rows) != set(historical):
        raise ValueError('Release groups differ from the historical candidate payloads.')
    release = read_json(source/'release_manifest.json')
    if file_hash(source/'consolidations.json') != release['canonical_sha256']:
        raise ValueError('Release canonical file changed.')
    for gid, payload in historical.items():
        d = source/'records'/gid
        if read_json(d/'input.json') != payload or read_json(d/'result.json') != rows[gid]:
            raise ValueError(f'{gid}: saved input/result differ from the release.')
        raw = (d/'analysis.raw.txt').read_text(encoding='utf-8')
        replay = export_result(payload, parse_response(payload, raw), state='CONSOLIDATED',
                               export_adapter_version=rows[gid]['export_adapter_version'])
        if replay != rows[gid]:
            raise ValueError(f'{gid}: saved response no longer reproduces the accepted export.')
    return rows, release


def registered_cautions(source, registry):
    found = []
    for entry in read_json(registry)['supplements']:
        if (ROOT/entry['run']).resolve() != source:
            continue
        if file_hash(ROOT/entry['path']) != entry['sha256']:
            raise ValueError('Registered review supplement changed.')
        for review in read_json(ROOT/entry['path'])['entries']:
            if review.get('assisted_content_review_required'):
                found.append((entry, review))
    return found


def project(source, output, *, registry=REGISTRY):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Use a new output directory outside the release.')
    historical = {p['candidate_group_id']: p for p in load_candidate_payloads(historical=True)}
    payloads = load_candidate_payloads()
    routing = routing_manifest_for_payloads(payloads)
    rows, release = verify_release(source, historical)
    source_view = load_effective_output(source, registry=registry)
    if source_view['unapplied_findings']:
        raise ValueError('Release has stale review bindings; inspect before projecting.')

    output.mkdir(parents=True)
    write_json(output/'routing_manifest.json', routing, exclusive=True)
    records, provenance = [], {}
    for payload in payloads:
        gid, parent = payload['candidate_group_id'], payload['routing_manifest']['parent_candidate_group_id']
        d = output/'records'/gid
        d.mkdir(parents=True)
        write_json(d/'input.json', payload, exclusive=True)
        origin = {'parent_candidate_group_id': parent, 'parent_input_sha256': file_hash(source/'records'/parent/'input.json'),
                  'parent_result_sha256': file_hash(source/'records'/parent/'result.json'),
                  'parent_members': len(historical[parent]['members']), 'projected_members': len(payload['members'])}
        if gid == parent:
            shutil.copyfile(source/'records'/parent/'analysis.raw.txt', d/'analysis.raw.txt')
            if file_hash(d/'analysis.raw.txt') != file_hash(source/'records'/parent/'analysis.raw.txt'):
                raise ValueError(f'{gid}: copied response bytes differ.')
            row = export_result(payload, parse_response(payload, (d/'analysis.raw.txt').read_text(encoding='utf-8')),
                                state='CONSOLIDATED')
            origin.update(method='REEXPORTED_SAVED_V7_RESPONSE', raw_response_sha256=file_hash(d/'analysis.raw.txt'))
        else:
            routed_out = len(historical[parent]['members']) - len(payload['members'])
            row = export_result(payload, state='NOT_RUN', error=(
                f'Projection gap: the saved v7 response for {parent} also assigned {routed_out} announcement '
                'member(s) now routed out; reusing it would alter model output. Members stay unassigned and reviewable.'))
            origin.update(method='NOT_REUSABLE_PARTIAL_GROUP', routed_out_members=routed_out)
        write_json(d/'result.json', row, exclusive=True)
        records.append(row)
        provenance[gid] = origin
    dropped = sorted(set(historical) - {o['parent_candidate_group_id'] for o in provenance.values()})

    write_json(output/'consolidations.json', records, exclusive=True)
    write_json(output/'review_queue.json', [r for r in records if r['review_required']], exclusive=True)
    write_json(output/'member_review_queue.json',
               [o for r in records for o in r['inherited_review_obligations']], exclusive=True)

    carried, unresolved = [], []
    for entry, review in registered_cautions(source, registry):
        gid = review['candidate_group_id']
        origin, d = provenance.get(gid), output/'records'/gid
        same = (origin is not None and origin['method'] == 'REEXPORTED_SAVED_V7_RESPONSE'
                and review['binding'].get('raw_draft_sha256') == origin['raw_response_sha256']
                and {m['member_id'] for m in historical[gid]['members']} == {m['member_id'] for m in read_json(d/'input.json')['members']})
        if not same:
            unresolved.append({'candidate_group_id': gid, 'reason': 'No identical group/members/response in the projection.',
                               'original_review': {'path': entry['path'], 'sha256': entry['sha256']}, 'finding': deepcopy(review)})
            continue
        moved = deepcopy(review)
        moved['binding'] = {'input_file_sha256': file_hash(d/'input.json'), 'raw_draft_sha256': file_hash(d/'analysis.raw.txt'),
                            'export_result_sha256': file_hash(d/'result.json')}
        moved['carried_from'] = {'run': entry['run'], 'review_path': entry['path'], 'review_sha256': entry['sha256'],
                                 'original_binding': deepcopy(review['binding']),
                                 'match_basis': 'same candidate group, same member IDs, byte-identical saved response'}
        carried.append(moved)
    supplement = {'origin': 'Naming cautions carried from the registered v7 taxonomy review by exact match; not a new review',
                  'run': stored(output), 'entries': carried, 'unresolved': unresolved,
                  'method': 'Bindings are recomputed for the projected files; original review provenance kept per entry.'}
    supplement_path = output/'carried_review_supplement.json'
    write_json(supplement_path, supplement, exclusive=True)
    view = load_effective_output(output, registry=registry, additional_supplements=(supplement_path,))
    if view['unapplied_findings'] or len(view['applied_content_obligations']) != sum(len(e.get('findings') or [None]) for e in carried):
        raise ValueError('Carried cautions did not bind to the projected output.')
    write_json(output/'effective_output.json', view, exclusive=True)

    announcements = routing['announcement_sources']
    members = [m for r in records for m in r['members']]
    totals = [identity(m) for m in members] + [identity(m) for m in announcements]
    if len(totals) != len(set(totals)) or len(totals) != routing['input_threads']:
        raise ValueError('Projection lost or duplicated member identities.')
    if sum(m['agent1_record']['review_required'] for m in [*members, *announcements]) != sum(
            m['agent1_record']['review_required'] for p in historical.values() for m in p['members']):
        raise ValueError('Projection lost inherited review obligations.')
    methods = Counter(o['method'] for o in provenance.values())
    manifest = {
        'projection_version': PROJECTION_VERSION, 'fresh_taxonomy_run': False, 'model_calls': 0,
        'source_release': stored(source), 'source_release_manifest_sha256': file_hash(source/'release_manifest.json'),
        'source_canonical_sha256': release['canonical_sha256'], 'source_handoff_contract': release['handoff_contract'],
        'registry': stored(registry), 'registry_sha256': file_hash(registry),
        'projection_script_sha256': file_hash(Path(__file__)),
        'export_schema_versions': sorted({r['schema_version'] for r in records}),
        'export_adapter_versions': sorted({r['export_adapter_version'] for r in records}),
        'handoff_contracts': sorted({r['taxonomy_handoff']['contract_version'] for r in view['records']}),
        'routing_version': routing['routing_version'], 'routing_sha256': digest(routing),
        'groups': len(records), 'group_methods': dict(methods), 'dropped_announcement_only_parent_groups': dropped,
        'topics': sum(len(r['topics']) for r in records),
        'discussion_members': len(members), 'announcement_members': len(announcements),
        'member_dispositions': dict(Counter(d['disposition'] for r in records for d in r['member_dispositions'])),
        'discussion_obligations': sum(len(r['inherited_review_obligations']) for r in records),
        'announcement_obligations': sum(m['agent1_record']['review_required'] for m in announcements),
        'carried_naming_cautions': len(carried), 'unresolved_naming_cautions': len(unresolved),
        'carried_review_supplement': stored(supplement_path), 'carried_review_supplement_sha256': file_hash(supplement_path),
        'review_groups': len(view['review_queue']), 'record_provenance': provenance,
        'effective_sha256': file_hash(output/'effective_output.json'), 'canonical_sha256': file_hash(output/'consolidations.json')}
    write_json(output/'projection_manifest.json', manifest, exclusive=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', type=Path, default=RELEASE)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data/processed/agent2_handoff_v2_projection')
    parser.add_argument('--write', action='store_true', help='Write the projection to a new directory.')
    args = parser.parse_args(argv)
    if not args.write:
        payloads = load_candidate_payloads()
        changed = sum(p['candidate_group_id'] != p['routing_manifest']['parent_candidate_group_id'] for p in payloads)
        print(f'Zero-call inspection: {len(payloads)} projected groups ({len(payloads) - changed} reusable, {changed} partial). '
              'Use --write to create the projection.')
        return 0
    try:
        manifest = project(args.source, args.output_dir)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps({k: v for k, v in manifest.items() if k != 'record_provenance'}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
