"""Build and verify native Linux Release bundles; never sign or publish."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MACHINES = {'x64': 62, 'arm64': 183}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def elf_machine(path: Path) -> int:
    with path.open('rb') as stream:
        header = stream.read(64)
    if len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01':
        raise ValueError(f'Expected a little-endian 64-bit ELF: {path}')
    kind, machine = struct.unpack_from('<HH', header, 16)
    if kind not in (2, 3):
        raise ValueError(f'Not an executable or shared ELF object: {path}')
    return machine


def check_tree(bundle: Path) -> list[Path]:
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError('A regular bundle directory is required')
    root = bundle.resolve()
    paths = sorted(bundle.rglob('*'))
    for path in paths:
        relative = path.relative_to(bundle).as_posix()
        if any(c in relative for c in '\r\n\\'):
            raise ValueError(f'Unsafe bundle path: {path}')
        if path.is_symlink():
            if Path(os.readlink(path)).is_absolute():
                raise ValueError(f'Absolute bundle symlink: {path}')
            try:
                target = path.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError(f'Dangling or cyclic bundle symlink: {path}') from error
            if not target.is_relative_to(root):
                raise ValueError(f'Escaping bundle symlink: {path}')
        elif not (path.is_file() or path.is_dir()):
            raise ValueError(f'Special bundle file: {path}')
    return paths


def check_bundle(bundle: Path, source: Path, arch: str) -> list[Path]:
    if arch not in MACHINES:
        raise ValueError(f'Unsupported Linux architecture: {arch}')
    paths = check_tree(bundle)
    required = ['rustdesk', 'lib/librustdesk.so', 'lib/libflutter_linux_gtk.so',
                'lib/libapp.so', 'data/icudtl.dat']
    for name in required:
        path = bundle / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Missing nonempty regular bundle file: {name}')
    if not os.access(bundle / 'rustdesk', os.X_OK):
        raise ValueError('The Linux runner lost its executable permission')
    assets = bundle / 'data/flutter_assets'
    if assets.is_symlink() or not assets.is_dir() or not any(p.is_file() for p in assets.rglob('*')):
        raise ValueError('Flutter assets are missing or empty')
    if source.is_symlink() or not source.is_file() or digest(source) != digest(bundle / 'lib/librustdesk.so'):
        raise ValueError('Bundled Rust library differs from this Cargo build')
    binaries = [bundle / 'rustdesk']
    for path in paths:
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as stream:
                is_elf = stream.read(4) == b'\x7fELF'
            if is_elf and path not in binaries:
                binaries.append(path)
            if path.parent == bundle / 'lib' and '.so' in path.name and not is_elf:
                raise ValueError(f'Non-ELF shared library: {path}')
    for path in binaries:
        if elf_machine(path) != MACHINES[arch]:
            raise ValueError(f'Wrong ELF architecture: {path}')
    return binaries


def command(args: list[str], log: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    reports = ROOT / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    output = reports / log
    with output.open('w', encoding='utf-8') as stream:
        result = subprocess.run(args, cwd=cwd, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=1800, check=False)
    text = output.read_text(encoding='utf-8', errors='replace')
    if result.returncode:
        print('\n'.join(text.splitlines()[-100:]), file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, args)
    return text


def check_linkage(binaries: list[Path]) -> None:
    for index, binary in enumerate(binaries):
        dynamic = command(['readelf', '--dynamic', str(binary)], f'linux-release-dynamic-{index}.log')
        if '(NEEDED)' in dynamic:
            linkage = command(['ldd', str(binary)], f'linux-release-linkage-{index}.log')
            if re.search(r'\bnot found\b', linkage):
                raise ValueError(f'Unresolved shared library dependency: {binary}')


def archive_bundle(bundle: Path, output: Path, arch: str, revision: str) -> Path:
    if arch not in MACHINES or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Archive architecture and full source revision are required')
    paths = check_tree(bundle)
    if not any(path.is_file() for path in paths):
        raise ValueError('Cannot archive an empty bundle')
    if output.exists() or output.is_symlink():
        raise ValueError('Refusing to overwrite an existing release directory')
    output.mkdir(parents=True)
    archive = output / f'RustDesk-linux-{arch}-unsigned.tar.gz'
    with tarfile.open(archive, 'w:gz', dereference=False) as tar:
        tar.add(bundle, arcname='RustDesk', recursive=False)
        for path in paths:
            tar.add(path, arcname='RustDesk/' + path.relative_to(bundle).as_posix(), recursive=False)
    (output / 'SOURCE_REVISION').write_text(revision + '\n', encoding='utf-8')
    return archive


def build() -> None:
    if platform.system() != 'Linux':
        raise ValueError('Native Linux validation requires Linux')
    arch = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
    if arch is None:
        raise ValueError('Only native Linux x64 and arm64 are supported')
    command([sys.executable, str(ROOT / 'tools/prepare_flutter.py')], 'linux-release-preflight.log')
    command(['cargo', 'build', '--locked', '--release', '--lib', '--features', 'flutter,linux-pkg-config'],
            'linux-release-cargo.log')
    command(['flutter', 'build', 'linux', '--release', '--no-pub'], 'linux-release-flutter.log', ROOT / 'flutter')
    bundle = ROOT / f'flutter/build/linux/{arch}/release/bundle'
    source = ROOT / 'target/release/liblibrustdesk.so'
    binaries = check_bundle(bundle, source, arch)
    check_linkage(binaries)
    command(['flutter', 'test', '--no-pub', 'test_native/bridge_ffi_test.dart'], 'linux-release-ffi.log',
            ROOT / 'flutter', {**os.environ, 'VIPER_NATIVE_LIBRARY': str(bundle / 'lib/librustdesk.so')})
    command(['git', 'diff', '--exit-code', '--', 'Cargo.lock', 'flutter/pubspec.lock', 'flutter/linux'],
            'linux-release-source.log')
    revision = command(['git', 'rev-parse', 'HEAD'], 'linux-release-revision.txt').strip()
    output = ROOT / f'dist/linux-{arch}-unsigned'
    archive = archive_bundle(bundle, output, arch, revision)
    report = {'revision': revision, 'architecture': arch, 'build_mode': 'release',
              'features': ['flutter', 'linux-pkg-config'], 'hardware_codecs': 'not-verified',
              'ffi': 'passed', 'gui_and_device_execution': 'not-verified', 'signature': 'not-verified',
              'rust_library_sha256': digest(source), 'archive_sha256': digest(archive),
              'elf_files_checked': len(binaries)}
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'tools/.reports/linux-release.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    command([sys.executable, str(ROOT / 'tools/viper.py'), 'manifest', str(output), '--revision', revision],
            'linux-release-manifest.log')
    command([sys.executable, str(ROOT / 'tools/viper.py'), 'verify', str(output)], 'linux-release-verify.log')
    print(f'Validated native Linux {arch} Release bundle and real FFI; no publication performed')


if __name__ == '__main__':
    try:
        build()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Linux Release validation failed: {error}', file=sys.stderr)
        raise SystemExit(1)
