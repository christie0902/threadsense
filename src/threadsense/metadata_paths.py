"""Explicit hash-checked aliases for JSON metadata relocated after repository cleanup.

Saved evidence continues to name its original path. Only the enumerated, byte-exact
archive can satisfy a missing historical reference; arbitrary paths never fall back.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'data/metadata/historical'


def resolve_metadata(path):
    path=Path(path)
    if path.exists():return path
    absolute=path.resolve()
    if not absolute.is_relative_to(ROOT):return path
    relative=absolute.relative_to(ROOT).as_posix()
    manifest=ARCHIVE/'recovery_manifest.json'
    if not manifest.exists():return path
    for entry in json.loads(manifest.read_text(encoding='utf-8'))['files']:
        if entry['historical_path']!=relative:continue
        archived=ROOT/entry['archive_path']
        if hashlib.sha256(archived.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Archived historical metadata fingerprint mismatch.')
        return archived
    return path
