"""Select and verify the exact Apple toolchain without changing global xcode-select."""
from pathlib import Path
import argparse
import json
import os
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path = ROOT, *, ios: bool = False) -> dict[str, str]:
    expected = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['apple']
    if platform.system() != 'Darwin':
        raise RuntimeError('Apple SDK verification requires macOS')
    developer = Path(expected['developer_dir'])
    if not developer.is_absolute() or not developer.is_dir():
        raise RuntimeError(f'Required Xcode is missing: {developer}')
    env = {**os.environ, 'DEVELOPER_DIR': str(developer)}
    reports = root / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    commands = {
        'xcode': ['xcodebuild', '-version'],
        'macos_sdk': ['xcrun', '--sdk', 'macosx', '--show-sdk-version'],
    }
    if ios:
        commands['ios_sdk'] = ['xcrun', '--sdk', 'iphoneos', '--show-sdk-version']
        expected['ios_sdk'] = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))['ios']['sdk']
    else:
        commands['cocoapods'] = ['pod', '--version']
    actual = {}
    for name, command in commands.items():
        process = subprocess.run(command, env=env, capture_output=True, text=True,
                                 encoding='utf-8', errors='replace', timeout=120)
        (reports / f'apple-{name}.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        if process.returncode:
            raise RuntimeError(f'{name} inspection failed with exit {process.returncode}')
        actual[name] = process.stdout.strip()
    match = re.fullmatch(r'Xcode ([0-9.]+)\nBuild version ([A-Za-z0-9]+)', actual['xcode'])
    if match is None or match.groups() != (expected['xcode'], expected['build']):
        raise RuntimeError(f"Wrong Xcode version/build: {actual['xcode']!r}")
    for name in ('macos_sdk', 'ios_sdk' if ios else 'cocoapods'):
        if actual[name] != expected[name]:
            raise RuntimeError(f"Wrong {name}: {actual[name]!r}; expected {expected[name]!r}")
    result = {**actual, 'developer_dir': str(developer)}
    (reports / 'apple-toolchain.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--github-env', action='store_true')
    parser.add_argument('--ios', action='store_true', help='Verify iPhoneOS SDK; CocoaPods is not used')
    args = parser.parse_args()
    try:
        result = verify(ios=args.ios)
        if args.github_env:
            destination = os.environ.get('GITHUB_ENV')
            if not destination:
                raise RuntimeError('GITHUB_ENV is missing')
            developer = result['developer_dir']
            if any(c in developer for c in '\r\n'):
                raise RuntimeError('Invalid developer directory')
            with open(destination, 'a', encoding='utf-8') as stream:
                stream.write(f'DEVELOPER_DIR={developer}\n')
        print(f"Verified {result['xcode'].replace(chr(10), ' / ')}; macOS SDK {result['macos_sdk']}")
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
