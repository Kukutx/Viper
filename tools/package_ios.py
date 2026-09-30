"""Validate and archive unsigned iOS application and XCArchive outputs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tarfile

from verify_ios_bundle import ROOT, rust_llvm_nm, verify


def archive_application(directory: Path) -> tuple[Path, Path]:
    """Accept exactly one regular device archive and its canonical application."""
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Missing regular XCArchive output directory')
    candidates = list(directory.glob('*.xcarchive'))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one XCArchive; stale outputs must not be mixed')
    archive = candidates[0]
    if archive.is_symlink() or not archive.is_dir():
        raise ValueError('Expected a regular XCArchive')
    plist = archive / 'Info.plist'
    if plist.is_symlink() or not plist.is_file() or not 0 < plist.stat().st_size < 1_000_000:
        raise ValueError('Missing or invalid XCArchive Info.plist')
    info = plistlib.loads(plist.read_bytes())
    if not isinstance(info, dict):
        raise ValueError('Invalid XCArchive metadata')
    properties = info.get('ApplicationProperties')
    if not isinstance(properties, dict):
        raise ValueError('Missing XCArchive application metadata')
    if properties.get('ApplicationPath') != 'Applications/Runner.app':
        raise ValueError('XCArchive application path drift')
    if properties.get('CFBundleIdentifier') != 'com.carriez.flutterHbb':
        raise ValueError('XCArchive application identifier drift')
    application = archive / 'Products/Applications/Runner.app'
    if application.is_symlink() or not application.is_dir():
        raise ValueError('Missing archived Runner.app')
    return archive, application


def archive_tree(source: Path, destination: Path) -> None:
    """Preserve framework links, but never archive links outside the output."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Archive source must be a regular directory')
    source_root = source.resolve(strict=True)
    entries = sorted(source.rglob('*'))
    if not any(p.is_file() and not p.is_symlink() for p in entries):
        raise ValueError('Cannot archive an empty output')
    for entry in entries:
        if entry.is_symlink():
            if Path(os.readlink(entry)).is_absolute() or not entry.resolve(strict=True).is_relative_to(source_root):
                raise ValueError(f'Unsafe archive link: {entry}')
        elif not (entry.is_file() or entry.is_dir()):
            raise ValueError(f'Unsupported archive entry: {entry}')
    with tarfile.open(destination, 'x:gz', dereference=False) as package:
        package.add(source, arcname=source.name)


def package(root: Path = ROOT) -> Path:
    config = json.loads((root / 'configs/toolchain.json').read_text(encoding='utf-8'))
    output = root / 'dist/ios-arm64-unsigned'
    if (root / 'dist').is_symlink() or output.exists() or output.is_symlink():
        raise ValueError('Use a fresh regular artifact directory; old artifacts must not be mixed')
    archive, archived_app = archive_application(root / 'flutter/build/ios/archive')
    application = root / 'flutter/build/ios/iphoneos/Runner.app'
    library = root / 'target/aarch64-apple-ios/release/liblibrustdesk.a'
    tool, reader = rust_llvm_nm(config['rust'])
    app_report = verify(application, library, config['ios'], symbol_tool=tool)
    archive_report = verify(archived_app, library, config['ios'], symbol_tool=tool)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a complete source revision')
    report = {'revision': revision, 'symbol_reader': reader,
              'application': app_report, 'xcarchive': archive_report,
              'ipa_export': 'not-performed', 'signing': 'not-performed',
              'device_execution': 'not-verified'}
    reports = root / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'ios-archive.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    output.mkdir(parents=True)
    archive_tree(application, output / 'Runner-ios-arm64-unsigned.tar.gz')
    archive_tree(archive, output / 'Runner-ios-arm64-unsigned.xcarchive.tar.gz')
    (output / 'build-profile.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for args in [('manifest', str(output), '--revision', revision), ('verify', str(output))]:
        subprocess.run([sys.executable, str(root / 'tools/viper.py'), *args], cwd=root, check=True)
    return output


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(package())
        return 0
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException,
            subprocess.SubprocessError, tarfile.TarError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
