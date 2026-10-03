#!/usr/bin/env python3
"""Require complete, tracked, reproducible Rust/Dart bridge outputs."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DART_DIRECTORY = 'flutter/lib/generated'
REQUIRED = (
    'src/bridge_generated.rs',
    *(f'{DART_DIRECTORY}/{name}' for name in (
        'flutter_ffi.dart', 'flutter_ffi.freezed.dart', 'frb_generated.dart',
        'frb_generated.io.dart', 'frb_generated.web.dart',
    )),
)


def check(root: Path = ROOT) -> None:
    paths = set(REQUIRED)
    directory = root / DART_DIRECTORY
    if directory.is_symlink():
        raise ValueError('Generated output directory must not be a symlink')
    paths.update(str(path.relative_to(root).as_posix()) for path in directory.rglob('*')
                 if path.is_file() or path.is_symlink())
    for name in sorted(paths):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Missing, empty or symlinked bridge output: {name}')
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', *sorted(paths)], cwd=root,
    ).decode('utf-8').split('\0')
    missing = paths - set(tracked)
    if missing:
        raise ValueError(f'Untracked bridge outputs (including ignored files): {sorted(missing)}')
    # HEAD catches staged changes as well as unstaged regeneration drift.
    subprocess.run(
        ['git', 'diff', '--exit-code', 'HEAD', '--', *sorted(paths),
         'Cargo.lock', 'flutter/pubspec.yaml', 'flutter/pubspec.lock'],
        cwd=root, check=True,
    )
    print(f'All {len(paths)} Rust/Dart bridge outputs are tracked and unchanged')


def main() -> int:
    try:
        check()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
