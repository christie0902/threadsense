"""Read-only loader for the TL-editable severity rubric; no severity classification.

The rubric file in data/knowledge stays the policy source. This module only loads
it, fingerprints its content and checks that Agent 3 contracts can reference it.
"""
from hashlib import sha256
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
RUBRIC_FILE = ROOT/'data/knowledge/severity_rubric.py'
# Levels the Agent 3 contracts accept; checked against the loaded rubric enum.
CONTRACT_LEVELS = ('LOW', 'MEDIUM', 'HIGH', 'N/A', 'UNKNOWN')
SIGNAL_LEVELS = ('MEDIUM', 'HIGH')


def _module(path):
    # Execute without importing, so no bytecode cache is written into data/knowledge.
    module = ModuleType('threadsense_tl_severity_rubric')
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), module.__dict__)
    return module


def load_rubric(project_id=None, *, path=RUBRIC_FILE):
    """Call the rubric's own interface and return a JSON-safe snapshot.

    content_sha256 hashes the parsed definitions, not file bytes, so it does not
    change with checkout line endings or comment-only edits.
    """
    module = _module(Path(path))
    loaded = module.get_rubric_for_project(project_id)
    levels = {getattr(level, 'value', level): {
        'definition': entry['definition'], 'examples': entry['examples'],
        'required_signals': list(entry['required_signals'])}
        for level, entry in loaded['rubric'].items()}
    content = json.dumps(levels, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    # get_rubric_for_project labels the response with the requested project, but
    # returns the shared default unless the file itself is a project copy (PROJECT_ID).
    project_specific = module.PROJECT_ID is not None and module.PROJECT_ID == project_id
    return {'version': loaded['version'], 'requested_project_id': project_id,
            'rubric_project_id': loaded['project_id'], 'project_specific': project_specific,
            'rubric_scope': 'PROJECT_SPECIFIC' if project_specific else 'SHARED_DEFAULT',
            'content_sha256': sha256(content.encode('utf-8')).hexdigest(),
            'enum_values': [level.value for level in module.SeverityLevel],
            'levels': levels, 'source_file': Path(path).resolve().relative_to(ROOT).as_posix()
                if Path(path).resolve().is_relative_to(ROOT) else str(path)}


def compatibility_issues(rubric):
    """Structural compatibility with the contracts; never edits or reinterprets policy."""
    issues = []
    if set(rubric['enum_values']) != set(CONTRACT_LEVELS):
        issues.append(f"Rubric levels {rubric['enum_values']} differ from contract levels {list(CONTRACT_LEVELS)}.")
    if set(rubric['levels']) != set(rubric['enum_values']):
        issues.append('Rubric entries do not cover exactly the rubric enum.')
    for level in SIGNAL_LEVELS:
        if not rubric['levels'].get(level, {}).get('required_signals'):
            issues.append(f'{level} has no required signals; MEDIUM/HIGH assessments could not cite one.')
    for level, entry in rubric['levels'].items():
        signals = entry['required_signals']
        if len(signals) != len(set(signals)) or any(not s.strip() for s in signals):
            issues.append(f'{level} signals must be unique and nonblank to be referenced by index.')
    return issues


def signal_reference_issues(severity, rubric):
    """Check an assessment's recorded rubric binding and cited signal text by index."""
    data = severity.model_dump(mode='json') if hasattr(severity, 'model_dump') else severity
    if data['assessment_status'] != 'ASSESSED':
        return []
    issues = []
    if data['rubric_version'] != rubric['version']:
        issues.append(f"Assessment cites rubric {data['rubric_version']}; loaded {rubric['version']}.")
    if data['rubric_content_sha256'] != rubric['content_sha256']:
        issues.append('Assessment rubric content hash differs from the loaded rubric.')
    if data['rubric_scope'] != rubric['rubric_scope']:
        issues.append(f"Assessment records rubric scope {data['rubric_scope']}; loaded {rubric['rubric_scope']}.")
    for match in data['matched_signals']:
        signals = rubric['levels'].get(match['level'], {}).get('required_signals', [])
        if match['signal_index'] >= len(signals) or signals[match['signal_index']] != match['signal_text']:
            issues.append(f"Signal {match['level']}[{match['signal_index']}] does not match the rubric text.")
    return issues
