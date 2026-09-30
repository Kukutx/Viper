"""Archive only a verified Windows Release bundle; never sign or publish it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from windows_native import ROOT, check_bundle, digest, host


def archive_bundle(bundle: Path, destination: Path) -> None:
    entries = sorted(bundle.rglob('*'))
    if not any(entry.is_file() for entry in entries):
        raise ValueError('Cannot archive an empty bundle')
    for entry in entries:
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise ValueError(f'Unsupported bundle entry: {entry}')
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for entry in entries:
            if entry.is_file():
                archive.write(entry, Path('RustDesk') / entry.relative_to(bundle))


def package(root: Path = ROOT) -> Path:
    arch = host()
    bundle = root / f'flutter/build/windows/{arch}/runner/Release'
    check_bundle(bundle, root / 'target/release/librustdesk.dll', arch)
    evidence = json.loads((root / 'tools/.reports/windows-native.json').read_text(encoding='utf-8'))
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if evidence['revision'] != revision or evidence['arch'] != arch:
        raise ValueError('Native validation evidence does not match this checkout')
    if evidence['rust_library_sha256'] != digest(bundle / 'librustdesk.dll'):
        raise ValueError('The Rust library changed after native validation')
    if (root / 'dist').is_symlink():
        raise ValueError('The artifact directory cannot be a symlink')
    output = root / f'dist/windows-{arch}-unsigned'
    if output.exists() or output.is_symlink():
        raise ValueError('Use an empty output location; old artifacts must not be mixed in')
    output.mkdir(parents=True)
    archive_bundle(bundle, output / f'RustDesk-windows-{arch}-unsigned.zip')
    (output / 'build-profile.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    for args in [('manifest', str(output), '--revision', revision), ('verify', str(output))]:
        subprocess.run([sys.executable, str(root / 'tools/viper.py'), *args], cwd=root, check=True)
    return output


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(package())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
