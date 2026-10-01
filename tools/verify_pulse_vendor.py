"""Verify that the local PulseAudio fork preserves its reviewed upstream source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path = ROOT) -> int:
    vendor = root / 'libs/pulsectl'
    if vendor.is_symlink():
        raise ValueError('PulseAudio vendor directory must not be a symlink')
    meta = json.loads((vendor / 'upstream.json').read_text(encoding='utf-8'))
    if meta['revision'] != 'aa34dde499aa912a3abc5289cc0b547bd07dd6e2':
        raise ValueError('Unreviewed upstream PulseAudio revision')
    expected = meta['source_blobs']
    for name, sha in expected.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Unsafe upstream source path')
        path = vendor / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing regular imported source: {name}')
        source = path.read_text(encoding='utf-8')
        for old, new in reversed(meta['replacements'].get(name, [])):
            if source.count(new) != 1:
                raise ValueError(f'Unexpected migration diff: {name}')
            source = source.replace(new, old)
        data = source.encode('utf-8')
        original = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        if original != sha:
            raise ValueError(f'Upstream source or license changed outside the migration: {name}')
    actual = {p.relative_to(vendor).as_posix() for p in (vendor / 'src').rglob('*.rs')}
    if actual != {n for n in expected if n.startswith('src/')}:
        raise ValueError('Imported source module set changed')
    manifest = (root / 'Cargo.toml').read_text(encoding='utf-8')
    if 'rust-pulsectl = { path = "libs/pulsectl" }' not in manifest:
        raise ValueError('The Linux dependency must use the reviewed local fork')
    if (vendor / 'Cargo.lock').exists():
        raise ValueError('The workspace Cargo.lock is the only dependency lock')
    return len(expected)


def main() -> int:
    try:
        print(f'Verified {verify()} original PulseAudio fork files and reviewed API substitutions')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
