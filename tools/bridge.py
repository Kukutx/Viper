#!/usr/bin/env python3
"""校验、安装并运行固定版本的 Flutter/Rust 桥接生成器。"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def configuration(root: Path = ROOT) -> dict:
    spec = json.loads((root / 'configs/toolchain.json').read_text())['flutter_rust_bridge']
    if not re.fullmatch(r'\d+\.\d+\.\d+', spec['version']):
        raise ValueError('Bridge version must be an exact stable release')
    return spec


def binary_from_archive(data: bytes, name: str, windows: bool) -> bytes:
    if windows:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            matches = [item for item in archive.infolist() if Path(item.filename).name == name]
            if len(matches) != 1 or matches[0].is_dir() or matches[0].file_size > 100_000_000:
                raise ValueError('Expected one bounded generator executable')
            return archive.read(matches[0])
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        matches = [item for item in archive.getmembers() if Path(item.name).name == name]
        if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 100_000_000:
            raise ValueError('Expected one bounded regular generator executable')
        stream = archive.extractfile(matches[0])
        if stream is None:
            raise ValueError('Executable cannot be read')
        return stream.read()


def install(root: Path = ROOT) -> Path:
    config = configuration(root)
    machine = platform.machine().lower()
    machine = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(machine, machine)
    host = f'{platform.system().lower()}-{machine}'
    asset = config['assets'].get(host)
    if asset is None:
        raise ValueError(f'No reviewed generator binary for {host}; use the canonical Linux generation job')
    digest = asset['sha256']
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Invalid generator SHA-256')
    windows = host.startswith('windows-')
    suffix = '.zip' if windows else '.tgz'
    name = 'flutter_rust_bridge_codegen' + ('.exe' if windows else '')
    version = config['version']
    filename = f"flutter_rust_bridge_codegen-{asset['target']}-v{version}{suffix}"
    request = urllib.request.Request(
        f'https://github.com/fzyzcjy/flutter_rust_bridge/releases/download/v{version}/{filename}',
        headers={'User-Agent': 'Viper-bridge-tool/1.0'},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(64_000_001)
    if len(data) > 64_000_000 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Generator archive checksum mismatch')
    binary = binary_from_archive(data, name, windows)
    directory = root / '.tools/bin'
    if (root / '.tools').is_symlink() or directory.is_symlink():
        raise ValueError('Tool directory cannot be a symlink')
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.is_symlink():
        raise ValueError('Tool target cannot be a symlink')
    with tempfile.NamedTemporaryFile(dir=directory, suffix='.exe' if windows else '', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(binary)
    try:
        temporary.chmod(0o755)
        actual = subprocess.check_output([str(temporary), '--version'], text=True).strip()
        if not actual or actual.split()[-1] != version:
            raise ValueError(f'Generator version mismatch: {actual}')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Installed verified generator {version}: {target}')
    return target


def check(root: Path = ROOT) -> None:
    import yaml
    version = configuration(root)['version']
    cargo = tomllib.loads((root / 'Cargo.toml').read_text())
    pub = yaml.safe_load((root / 'flutter/pubspec.yaml').read_text())
    if cargo['dependencies']['flutter_rust_bridge']['version'] != '=' + version:
        raise ValueError('Rust bridge version differs from central configuration')
    if pub['dependencies']['flutter_rust_bridge'] != version:
        raise ValueError('Dart bridge version differs from central configuration')
    generation = yaml.safe_load((root / 'flutter_rust_bridge.yaml').read_text())
    if generation.get('auto_upgrade_dependency') is not False or generation.get('stop_on_error') is not True:
        raise ValueError('Generation must neither change dependency versions nor ignore errors')
    print(f'Rust, Dart and generator versions agree: {version}')


def generate(root: Path = ROOT) -> None:
    check(root)
    toolchain = json.loads((root / 'configs/toolchain.json').read_text())
    sdk = json.loads(subprocess.check_output(['flutter', '--version', '--machine'], cwd=root, text=True))
    if sdk['frameworkVersion'] != toolchain['flutter'] or sdk['dartSdkVersion'].split()[0] != toolchain['dart']:
        raise ValueError('Use the pinned Flutter/Dart SDK')
    executable = install(root)
    subprocess.run(['cargo', 'metadata', '--locked', '--no-deps', '--format-version', '1'], cwd=root, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(['flutter', 'pub', 'get', '--enforce-lockfile'], cwd=root / 'flutter', check=True)
    locks = {name: (root / name).read_bytes() for name in ('Cargo.lock', 'flutter/pubspec.lock')}
    subprocess.run([str(executable), 'generate', '--config-file', 'flutter_rust_bridge.yaml'], cwd=root, check=True)
    if any((root / name).read_bytes() != data for name, data in locks.items()):
        raise ValueError('Code generation changed a lockfile; review the dependency change separately')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'install', 'generate'))
    args = parser.parse_args()
    try:
        {'check': check, 'install': install, 'generate': generate}[args.command]()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
