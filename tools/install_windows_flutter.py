"""Bootstrap an unmodified, exact Flutter Git checkout with the native Dart SDK."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from windows_native import MACHINES, ROOT, command, host, pe_machine

SOURCE = 'https://github.com/flutter/flutter.git'


def prepare_checkout(destination: Path, version: str, revision: str) -> None:
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('An exact Flutter version and revision are required')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Use a new SDK directory; existing worktrees must not be overwritten')
    command(['git', '-c', 'core.autocrlf=false', 'clone', '--depth', '1', '--branch', version,
             SOURCE, str(destination)], 'windows-sdk-clone.log')
    actual = command(['git', '-C', str(destination), 'rev-parse', 'HEAD'], 'windows-sdk-revision.log').strip()
    if actual != revision:
        raise ValueError('The SDK tag does not match the reviewed Flutter revision')
    command(['git', '-C', str(destination), 'switch', '-c', 'stable'], 'windows-sdk-channel.log')


def install(destination: Path | None = None, github_env: bool = False) -> None:
    arch = host()
    config = json.loads((ROOT / 'configs/toolchain.json').read_text(encoding='utf-8'))
    version, revision = config['flutter'], config['flutter_revision']
    if os.environ.get('FLUTTER_PREBUILT_ENGINE_VERSION') or os.environ.get('FLUTTER_STORAGE_BASE_URL'):
        raise ValueError('This validation requires the official SDK engine and artifact source')
    if destination is None:
        destination = Path(os.environ.get('RUNNER_TEMP', ROOT / '.tools')) / f'viper-flutter-{version}-{arch}'
    destination = destination.absolute()
    prepare_checkout(destination, version, revision)
    os.environ['FLUTTER_ROOT'] = str(destination)
    os.environ['PATH'] = str(destination / 'bin') + os.pathsep + os.environ['PATH']
    from flutter_sdk import verify
    verify(ROOT)
    dart = destination / 'bin/cache/dart-sdk/bin/dart.exe'
    if pe_machine(dart) != MACHINES[arch]:
        raise ValueError('Flutter selected a non-native Dart SDK; emulation is not accepted')
    command(['git', '-C', str(destination), 'diff', '--exit-code', 'HEAD'], 'windows-sdk-source-drift.log')
    report = {'source': SOURCE, 'version': version, 'revision': revision, 'arch': arch,
              'path': str(destination), 'dart_executable': str(dart)}
    (ROOT / 'tools/.reports/windows-sdk.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if github_env:
        with Path(os.environ['GITHUB_PATH']).open('a', encoding='utf-8') as stream:
            stream.write(str(destination / 'bin') + '\n')
        with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8') as stream:
            stream.write('FLUTTER_ROOT=' + str(destination) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--github-env', action='store_true')
    args = parser.parse_args()
    try:
        install(args.destination, args.github_env)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
