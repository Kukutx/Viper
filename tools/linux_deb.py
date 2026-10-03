"""Package the validated native Linux Release as a rootless, inspected Debian archive."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib

import linux_release as release
import viper

ROOT = Path(__file__).resolve().parents[1]
DEB_ARCH = {'x64': 'amd64', 'arm64': 'arm64'}
SCRIPTS = ('preinst', 'postinst', 'prerm', 'postrm')
RESOURCES = {
    'res/rustdesk.service': 'usr/share/rustdesk/files/systemd/rustdesk.service',
    'res/rustdesk.desktop': 'usr/share/applications/rustdesk.desktop',
    'res/rustdesk-link.desktop': 'usr/share/applications/rustdesk-link.desktop',
    'res/128x128@2x.png': 'usr/share/icons/hicolor/256x256/apps/rustdesk.png',
    'res/scalable.svg': 'usr/share/icons/hicolor/scalable/apps/rustdesk.svg',
    'LICENCE': 'usr/share/doc/rustdesk/copyright',
}


def regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or not path.stat().st_size:
        raise ValueError(f'Expected a nonempty regular file: {path}')


def tree_manifest(root: Path) -> dict:
    paths = release.check_tree(root)
    mode = stat.S_IMODE(root.stat().st_mode)
    if mode & 0o7002:
        raise ValueError('Unsafe package root permissions')
    entries = {'': ('dir', mode, None)}
    for path in paths:
        name = path.relative_to(root).as_posix()
        if any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise ValueError(f'Unsafe package path: {name!r}')
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            entry = ('link', mode, os.readlink(path))
        else:
            if mode & 0o7002:
                raise ValueError(f'Unsafe package permissions: {name}')
            entry = ('dir', mode, None) if path.is_dir() else ('file', mode, release.digest(path))
        entries[name] = entry
    return entries


def verify_tar(archive: Path, expected: dict, *, prefix: str = '', root_owned: bool = True) -> None:
    """Check paths, types, ownership, permissions and every payload byte before extraction."""
    observed = {}
    with tarfile.open(archive, 'r:*') as tar:
        for member in tar:
            name = member.name
            if name.startswith('./'):
                name = name[2:]
            name = name.rstrip('/') if member.isdir() else name
            if name in ('', '.') and member.isdir():
                name = ''
            elif not name or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/')):
                raise ValueError(f'Unsafe archive path: {member.name}')
            if prefix:
                if name == prefix:
                    name = ''
                elif name.startswith(prefix + '/'):
                    name = name[len(prefix) + 1:]
                else:
                    raise ValueError('Unexpected archive root')
            if name in observed:
                raise ValueError(f'Duplicate archive entry: {name}')
            if root_owned and (member.uid != 0 or member.gid != 0):
                raise ValueError(f'Non-root archive ownership: {name}')
            if member.isdir():
                entry = ('dir', member.mode, None)
            elif member.issym():
                if PurePosixPath(member.linkname).is_absolute():
                    raise ValueError('Absolute archive link')
                entry = ('link', member.mode, member.linkname)
            elif member.isreg():
                with tar.extractfile(member) as stream:
                    entry = ('file', member.mode, hashlib.file_digest(stream, 'sha256').hexdigest())
            else:
                raise ValueError(f'Unsupported archive entry: {name}')
            observed[name] = entry
    if observed != expected:
        changed = sorted(key for key in observed.keys() | expected.keys()
                         if observed.get(key) != expected.get(key))
        raise ValueError(f'Archive differs from staging: {changed[:10]}')


def control_text(version: str, arch: str, dependencies: str, size: int, revision: str) -> str:
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or arch not in DEB_ARCH:
        raise ValueError('Expected stable application version and a supported architecture')
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or type(size) is not int or size <= 0:
        raise ValueError('Expected full source revision and positive installed size')
    if not dependencies or not re.fullmatch(r'[a-zA-Z0-9+.:, ()<>=|~\-]+', dependencies):
        raise ValueError('Invalid generated Debian dependencies')
    text = (ROOT / 'configs/linux-deb-control.in').read_text(encoding='utf-8') % (version, DEB_ARCH[arch], '')
    lines = text.strip().splitlines()
    if sum(line.startswith('Depends: ') for line in lines) != 1 or lines[0] != 'Package: rustdesk':
        raise ValueError('Debian package identity or dependency template drift')
    lines = [line + ', ' + dependencies if line.startswith('Depends: ') else line for line in lines]
    return '\n'.join(lines) + f'\nInstalled-Size: {size}\nX-Viper-Source-Revision: {revision}\n'


def stage(bundle: Path, directory: Path) -> Path:
    tree_manifest(bundle)
    if directory.exists() or directory.is_symlink():
        raise ValueError('Refusing to reuse Debian staging directory')
    installed = directory / 'usr/share/rustdesk'
    shutil.copytree(bundle, installed, symlinks=True)
    for source, relative in RESOURCES.items():
        path = ROOT / source
        regular(path)
        destination = directory / relative
        if destination.exists() or destination.is_symlink():
            raise ValueError(f'Package resource would overwrite a bundled file: {relative}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        destination.chmod(0o644)
    helper = installed / 'files/polkit'
    if helper.exists() or helper.is_symlink():
        raise ValueError('Package helper would overwrite a bundled file')
    helper.write_text('#!/bin/sh\n', encoding='utf-8')
    helper.chmod(0o755)
    (directory / 'usr/bin').mkdir(parents=True)
    (directory / 'DEBIAN').mkdir()
    for script in SCRIPTS:
        source = ROOT / 'res/DEBIAN' / script
        regular(source)
        shutil.copyfile(source, directory / 'DEBIAN' / script)
        (directory / 'DEBIAN' / script).chmod(0o755)
    for path in [directory, *directory.rglob('*')]:
        if path.is_dir() and not path.is_symlink():
            path.chmod(0o755)
    return installed


def capture_tar(package: Path, argument: str, target: Path) -> None:
    with target.open('xb') as stream:
        subprocess.run(['dpkg-deb', argument, str(package)], stdout=stream, check=True, timeout=300)


def package() -> None:
    arch = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
    if platform.system() != 'Linux' or arch is None:
        raise ValueError('Use a native Linux x64 or arm64 host')
    revision = release.command(['git', 'rev-parse', 'HEAD'], 'linux-deb-revision.txt').strip()
    epoch = release.command(['git', 'show', '-s', '--format=%ct', 'HEAD'], 'linux-deb-epoch.txt').strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or not re.fullmatch(r'[1-9][0-9]{8,11}', epoch):
        raise ValueError('Invalid source identity')
    if release.command(['dpkg', '--print-architecture'], 'linux-deb-host.log').strip() != DEB_ARCH[arch]:
        raise ValueError('Debian host and native build architectures disagree')
    previous = ROOT / f'dist/linux-{arch}-unsigned'
    viper.verify_manifest(previous)
    regular(previous / 'validation.json')
    report = json.loads((previous / 'validation.json').read_text())
    required = {'revision': revision, 'architecture': arch, 'build_mode': 'release', 'ffi': 'passed',
                'features': ['flutter', 'linux-pkg-config']}
    if not isinstance(report, dict) or any(report.get(k) != value for k, value in required.items()):
        raise ValueError('Missing or stale native Release evidence')
    source = ROOT / 'target/release/liblibrustdesk.so'
    bundle = ROOT / f'flutter/build/linux/{arch}/release/bundle'
    release.check_bundle(bundle, source, arch)
    if release.digest(source) != report.get('rust_library_sha256'):
        raise ValueError('Native Release evidence has the wrong Rust library')
    # This entry never labels a DRM/consent-bypass artifact as the stock application.
    if any('libdrmtap' in p.name for p in bundle.rglob('*')):
        raise ValueError('DRM artifacts require the existing explicit DRM package route')
    for binary in (source, bundle / 'rustdesk'):
        if b'/usr/lib/rustdesk/libdrmtap.so.0' in binary.read_bytes():
            raise ValueError('DRM binaries require the existing explicit DRM package route')
    archive = previous / f'RustDesk-linux-{arch}-unsigned.tar.gz'
    regular(archive)
    if release.digest(archive) != report.get('archive_sha256'):
        raise ValueError('Native Release archive digest mismatch')
    verify_tar(archive, tree_manifest(bundle), prefix='RustDesk', root_owned=False)
    output = ROOT / f'dist/linux-{arch}-deb-unsigned'
    if output.exists() or output.is_symlink() or output.parent.is_symlink():
        raise ValueError('Refusing to overwrite or follow a package output directory')
    version = tomllib.loads((ROOT / 'Cargo.toml').read_text())['package']['version']
    with tempfile.TemporaryDirectory(prefix='viper-deb-') as temporary:
        work = Path(temporary)
        staged = work / 'debian/rustdesk'
        installed = stage(bundle, staged)
        binaries = release.check_bundle(installed, source, arch)
        (work / 'debian/control').write_text(
            'Source: rustdesk\nMaintainer: rustdesk <info@rustdesk.com>\n\n'
            'Package: rustdesk\nArchitecture: any\nDescription: A remote control software.\n', encoding='utf-8')
        dependencies_output = release.command(
            ['dpkg-shlibdeps', '-O', '-xrustdesk', '-l' + str(installed / 'lib'),
             *['-e' + str(path) for path in binaries]], 'linux-deb-shlibdeps.log', work)
        matches = re.findall(r'^shlibs:Depends=(.+)$', dependencies_output, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous system library dependencies')
        payload = tree_manifest(staged)
        for key in list(payload):
            if key == 'DEBIAN' or key.startswith('DEBIAN/'):
                del payload[key]
        size = sum((staged / name).stat().st_size for name, entry in payload.items() if entry[0] == 'file')
        control = control_text(version, arch, matches[0], (size + 1023) // 1024, revision)
        (staged / 'DEBIAN/control').write_text(control, encoding='utf-8')
        md5s = []
        for name, entry in payload.items():
            if entry[0] == 'file':
                with (staged / name).open('rb') as stream:
                    value = hashlib.file_digest(stream, 'md5').hexdigest()
                md5s.append(f'{value}  {name}\n')
        (staged / 'DEBIAN/md5sums').write_text(''.join(md5s), encoding='utf-8')
        for name in ('control', 'md5sums'):
            (staged / 'DEBIAN' / name).chmod(0o644)
        for path in [staged, *staged.rglob('*')]:
            os.utime(path, (int(epoch), int(epoch)), follow_symlinks=False)
        env = {**os.environ, 'SOURCE_DATE_EPOCH': epoch, 'LC_ALL': 'C', 'TZ': 'UTC'}
        packages = [work / f'{name}.deb' for name in ('first', 'second')]
        for index, deb in enumerate(packages):
            release.command(['dpkg-deb', '--root-owner-group', '-Zxz', '-z6', '--threads-max=2',
                             '--build', str(staged), str(deb)], f'linux-deb-build-{index}.log', work, env)
        if release.digest(packages[0]) != release.digest(packages[1]):
            raise ValueError('Repeated package serialization is not reproducible')
        for argument, expected in (('--fsys-tarfile', payload),
                                   ('--ctrl-tarfile', tree_manifest(staged / 'DEBIAN'))):
            tar = work / (argument[2:] + '.tar')
            capture_tar(packages[0], argument, tar)
            verify_tar(tar, expected)
        extracted = work / 'extracted'
        release.command(['dpkg-deb', '--raw-extract', str(packages[0]), str(extracted)], 'linux-deb-extract.log')
        if tree_manifest(extracted) != tree_manifest(staged):
            raise ValueError('Extracted Debian files differ from staging')
        release.check_bundle(extracted / 'usr/share/rustdesk', source, arch)
        release.command(['flutter', 'test', '--no-pub', 'test_native/bridge_ffi_test.dart'], 'linux-deb-ffi.log',
                        ROOT / 'flutter', {**os.environ, 'VIPER_NATIVE_LIBRARY': str(extracted / 'usr/share/rustdesk/lib/librustdesk.so')})
        release.command(['git', 'diff', '--exit-code', 'HEAD', '--', 'Cargo.toml', 'Cargo.lock',
                         'flutter/pubspec.yaml', 'flutter/pubspec.lock', 'flutter/linux', 'res/DEBIAN',
                         'configs/linux-deb-control.in', 'res/rustdesk.service', 'res/rustdesk.desktop',
                         'res/rustdesk-link.desktop', 'res/128x128@2x.png', 'res/scalable.svg',
                         'LICENCE', 'tools/linux_deb.py'], 'linux-deb-source.log')
        output.mkdir(parents=True)
        deb = output / f'rustdesk-{version}-{DEB_ARCH[arch]}.deb'
        shutil.copyfile(packages[0], deb)
        result = {'revision': revision, 'architecture': arch, 'package_architecture': DEB_ARCH[arch],
                  'package_version': version, 'deb_sha256': release.digest(deb),
                  'rust_library_sha256': release.digest(source), 'features': required['features'],
                  'elf_files_checked': len(binaries), 'payload_entries_checked': len(payload),
                  'root_ownership': 'verified', 'repeated_serialization': 'identical',
                  'extracted_library_ffi': 'passed', 'installed_service_and_gui': 'not-verified',
                  'hardware_codecs': 'not-verified', 'signature': 'not-verified',
                  'depends': matches[0], 'source_date_epoch': int(epoch)}
        (output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        (output / 'SOURCE_REVISION').write_text(revision + '\n', encoding='utf-8')
        (ROOT / 'tools/.reports/linux-deb.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        (output / 'release-manifest.json').write_text(
            json.dumps(viper.make_manifest(output, revision), indent=2) + '\n', encoding='utf-8')
        viper.verify_manifest(output)
    print('Debian package verified; installation, service execution and signing were not performed')


if __name__ == '__main__':
    try:
        package()
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.SubprocessError) as error:
        print(f'Debian packaging failed: {error}', file=sys.stderr)
        raise SystemExit(1)
