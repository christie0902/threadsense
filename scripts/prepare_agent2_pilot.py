"""Prepare a new offline pilot after reviewing code changes; preserve old artifacts."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from threadsense.config import get_model_settings
from threadsense.handoff_inputs import (
    CANONICAL, GROUPING, digest, file_hash, identity, read_json,
)
from threadsense.topic_inputs import load_candidate_payloads
from threadsense.agents.topic_consolidation import build_request
from threadsense.agents.topic_pipeline import configuration, execute_batch, write_json
from threadsense.terminology import get_terms


def prepare_pilot(source_pilot, source_preparation, output_pilot, output_dir, review_note,
                  allow_contract_upgrade=False):
    """Retain the reviewed selection; bind a new copy to the inspected current code.

    Source/model/selection changes require a separate review, not this code refresh.
    No credentials, completion function, or live execution path is used here.
    """
    source_pilot, source_preparation = Path(source_pilot), Path(source_preparation)
    output_pilot, output_dir = Path(output_pilot), Path(output_dir)
    if output_pilot.exists() or output_dir.exists():
        raise FileExistsError('Use new pilot and output paths; existing artifacts are preserved.')
    if not review_note.strip():
        raise ValueError('Describe the inspected code changes in --review-note.')
    pilot = read_json(source_pilot)
    previous = read_json(source_preparation / 'manifest.json')
    old_config = previous['config']
    if (digest(old_config) != pilot['configuration_sha256']
            or previous['config_sha256'] != pilot['configuration_sha256']):
        raise ValueError('Source preparation does not match the original pilot fingerprint.')
    if (pilot['schema_version'] != 2
            or pilot['canonical_sha256'] != file_hash(CANONICAL)
            or pilot['grouping_sha256'] != file_hash(GROUPING)):
        raise ValueError('Pilot inputs changed; review a new selection separately.')
    model, _ = get_model_settings()
    if model != pilot['model'] or model != old_config['model']:
        raise ValueError('Configured model differs from the source pilot.')
    bounds = {'requests_per_group': 1, 'automatic_retries': 0,
              'repairs': 0, 'additional_verifier_calls': 0}
    if any(pilot.get(k) != value for k, value in bounds.items()):
        raise ValueError('Preserve one attempt per group, zero retries/repairs/verifier calls.')
    ids = [case['candidate_group_id'] for case in pilot['cases']]
    payloads = {p['candidate_group_id']: p for p in load_candidate_payloads()}
    if (not ids or len(ids) != len(set(ids)) or not set(ids) <= payloads.keys()
            or len(ids) != pilot['maximum_request_attempts']):
        raise ValueError('Pilot selection is invalid or exceeds its original request bound.')
    selected = [payloads[gid] for gid in ids]
    for case, payload in zip(pilot['cases'], selected):
        members = payload['members']
        if ([identity(m) for m in members] != [identity(m) for m in case['member_identities']]
                or case['inherited_review_count'] != sum(m['agent1_record']['review_required'] for m in members)
                or case['anchor_thread_id'] not in {m['thread_id'] for m in members}):
            raise ValueError('Pilot member identities, anchor, or review obligations changed.')
        if read_json(source_preparation / 'records' / payload['candidate_group_id'] / 'input.json') != payload:
            raise ValueError('Source preparation contains different candidate inputs.')
    current = configuration(selected, model)
    # This operation accepts inspected code changes only, never silent data/model changes.
    permitted = {'code_sha256'}
    if allow_contract_upgrade:
        transition = (old_config.get('response_schema_version'), current['response_schema_version'])
        if transition not in {(3, 6), (4, 6), (5, 6), (6, 7)}:
            raise ValueError('Only an explicitly reviewed v3/v4/v5 to v6, or v6 to taxonomy v7, upgrade is supported.')
        permitted |= {'schema_version', 'response_schema_version', 'prompt_version',
                      'rubric_version', 'export_adapter_version',
                      'request_parameters', 'response_format_sha256'}
    if ({k: v for k, v in current.items() if k not in permitted}
            != {k: v for k, v in old_config.items() if k not in permitted}):
        raise ValueError('Non-code configuration changed; review the inputs/settings separately.')
    changed = {path: {'previous': old_config['code_sha256'].get(path),
                      'current': current['code_sha256'].get(path)}
               for path in sorted(old_config['code_sha256'].keys() | current['code_sha256'].keys())
               if old_config['code_sha256'].get(path) != current['code_sha256'].get(path)}
    requests_changed = []
    for payload in selected:
        gid = payload['candidate_group_id']
        old_request = read_json(source_preparation / 'records' / gid / 'request.json')
        if old_request != build_request(payload, get_terms(), model,
                                        response_schema_version=current['response_schema_version']):
            requests_changed.append(gid)
    revised = deepcopy(pilot)
    revised.update(
        response_schema_version=current['response_schema_version'],
        prompt_version=current['prompt_version'],
        origin='offline_prepared_pilot_after_code_review_not_executed',
        prepared_at=datetime.now(timezone.utc).isoformat(),
        configuration_sha256=digest(current),
        preparation_review={
            'source_pilot': source_pilot.as_posix(),
            'source_pilot_sha256': file_hash(source_pilot),
            'source_preparation': source_preparation.as_posix(),
            'previous_configuration_sha256': pilot['configuration_sha256'],
            'review_note': review_note.strip(),
            'contract_upgrade_reviewed': allow_contract_upgrade,
            'version_changes': {key: {'previous': old_config.get(key), 'current': current.get(key)}
                                for key in ('prompt_version', 'response_schema_version', 'rubric_version', 'export_adapter_version')
                                if old_config.get(key) != current.get(key)},
            'code_changes': changed,
            'model_requests_changed': requests_changed,
            'preparer_script_sha256': file_hash(Path(__file__)),
        },
    )
    manifest = execute_batch(selected, output_dir, run=False, maximum_requests=len(selected))
    if manifest['config_sha256'] != revised['configuration_sha256']:
        raise RuntimeError('Configuration changed during preparation; no pilot was published.')
    write_json(output_pilot, revised, exclusive=True)
    return revised, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pilot', type=Path, required=True)
    parser.add_argument('--source-preparation', type=Path, required=True,
                        help='Existing directory with the original manifest and exact inputs/requests.')
    parser.add_argument('--output-pilot', type=Path, required=True, help='New selection JSON; never overwritten.')
    parser.add_argument('--output-dir', type=Path, required=True, help='New offline preparation directory.')
    parser.add_argument('--review-note', required=True, help='Describe changes you have inspected.')
    parser.add_argument('--allow-contract-upgrade', action='store_true',
                        help='Reviewed legacy-to-v6 or v6-to-taxonomy-v7 contract change; sources/model/bounds stay identical.')
    args = parser.parse_args(argv)
    try:
        pilot, manifest = prepare_pilot(**vars(args))
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"Prepared {manifest['selected_groups']} groups, {manifest['retained_input_identities']} members, "
          f"{manifest['inherited_review_obligations']} inherited review obligations; zero model calls.")
    print(f"Changed model requests: {len(pilot['preparation_review']['model_requests_changed'])}")
    print(f"New pilot: {args.output_pilot}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
