"""Keep build-entry SDK mirrors synchronized with the reviewed central toolchain."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MIRRORS = {
    'RUST_VERSION': ('rust',),
    'FLUTTER_VERSION': ('flutter',),
    'VCPKG_CMAKE_VERSION': ('cmake',),
    'VCPKG_COMMIT_ID': ('vcpkg', 'revision'),
    'CARGO_NDK_VERSION': ('android', 'cargo_ndk'),
    'NDK_VERSION': ('android', 'ndk_release'),
}


def value(data: dict, key: str) -> str:
    current = data
    for part in key.split('.'):
        current = current[part]
    if not isinstance(current, str) or not re.fullmatch(r'[A-Za-z0-9._-]+', current):
        raise ValueError(f'Not a safe scalar toolchain value: {key}')
    return current


def sync(root: Path = ROOT, write: bool = False) -> None:
    data = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))
    path = root / '.github/workflows/flutter-build.yml'
    text = path.read_text(encoding='utf-8')
    for env, keys in MIRRORS.items():
        expected = value(data, '.'.join(keys))
        pattern = re.compile(r'^(  ' + env + r': )"[^"\n]+"[^\n]*$', re.M)
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError(f'Expected one build mirror for {env}')
        replacement = f'  {env}: "{expected}" # managed by tools/viper.py versions'
        if matches[0].group() != replacement:
            if not write:
                raise ValueError(f'Build SDK drift: {env}; run tools/viper.py versions --write')
            text = pattern.sub(lambda _: replacement, text)
    if write:
        path.write_text(text, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--value')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    try:
        if args.value:
            print(value(json.loads((ROOT / 'configs/toolchain.json').read_text(encoding='utf-8')), args.value))
        else:
            sync(write=args.write)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
