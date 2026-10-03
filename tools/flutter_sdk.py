#!/usr/bin/env python3
"""Verify the repository-pinned Flutter/Dart SDK on every supported host."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path = ROOT) -> str:
    expected = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))
    executable = shutil.which('flutter')
    if executable is None:
        raise ValueError('Flutter executable not found; install the pinned SDK')
    reports = root / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    # First launch can bootstrap the Flutter tool, especially on Windows.
    # Keep that output separate rather than accepting non-JSON version reports.
    for name, arguments in (
        ('flutter-bootstrap.log', ['--version']),
        ('flutter-version.json', ['--version', '--machine']),
    ):
        result = subprocess.run(
            [executable, *arguments], cwd=root, capture_output=True,
            text=True, encoding='utf-8', errors='replace',
        )
        (reports / name).write_text(result.stdout, encoding='utf-8')
        (reports / (name + '.stderr.log')).write_text(result.stderr, encoding='utf-8')
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    sdk = json.loads(result.stdout)
    if not isinstance(sdk, dict):
        raise ValueError('Flutter version report must be a JSON object')
    dart = sdk.get('dartSdkVersion')
    if not isinstance(dart, str) or not dart.split():
        raise ValueError('Flutter version report has no Dart SDK version')
    if sdk.get('frameworkVersion') != expected['flutter'] or dart.split()[0] != expected['dart']:
        raise ValueError(f"Expected Flutter {expected['flutter']} / Dart {expected['dart']}; got {sdk}")
    if 'flutter_revision' in expected and sdk.get('frameworkRevision') != expected['flutter_revision']:
        raise ValueError('Flutter framework revision differs from the reviewed commit')
    if sdk.get('channel') != 'stable':
        raise ValueError('The pinned Flutter SDK must use the stable channel')
    print(f"Verified Flutter {expected['flutter']} / Dart {expected['dart']}: {executable}")
    return executable


def main() -> int:
    try:
        verify()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
