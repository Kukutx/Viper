"""Verify an iOS device bundle and statically linked bridge, without claiming execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SYMBOLS = {
    '_frb_pde_ffi_dispatcher_primary', '_frb_pde_ffi_dispatcher_sync',
    '_frb_get_rust_content_hash', '_frb_init_frb_dart_api_dl',
    '_frb_rust_vec_u8_new', '_frb_rust_vec_u8_resize', '_frb_rust_vec_u8_free',
    '_frb_free_wire_sync_rust2dart_sse', '_frb_dart_fn_deliver_output',
    '_rustdesk_core_main', '_session_get_rgba',
}


def inspect(command: list[str]) -> str:
    process = subprocess.run(command, capture_output=True, text=True, timeout=120,
                             encoding='utf-8', errors='strict')
    if process.returncode:
        raise ValueError(f'{command[0]} failed ({process.returncode}): {process.stderr[-2000:]}')
    return process.stdout


def rust_llvm_nm(expected_rust: str) -> tuple[Path, dict]:
    """Use the pinned compiler's reader; Apple's LLVM may lag Rust bitcode."""
    version = inspect(['rustc', '-vV'])
    fields = dict(line.split(': ', 1) for line in version.splitlines() if ': ' in line)
    if fields.get('release') != expected_rust:
        raise ValueError('Rust version drift while selecting the iOS symbol reader')
    host = fields.get('host', '')
    llvm = fields.get('LLVM version', '')
    if not re.fullmatch(r'[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)+', host):
        raise ValueError('Invalid Rust host triple')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', llvm):
        raise ValueError('Missing or invalid Rust LLVM version')
    sysroot = Path(inspect(['rustc', '--print', 'sysroot']).strip())
    if not sysroot.is_absolute():
        raise ValueError('Rust sysroot must be an absolute path')
    name = 'llvm-nm.exe' if sys.platform == 'win32' else 'llvm-nm'
    tool = sysroot / 'lib' / 'rustlib' / host / 'bin' / name
    if tool.is_symlink() or not tool.is_file():
        raise ValueError('Missing compiler-matched llvm-nm; run rustup component add llvm-tools-preview')
    tool_version = inspect([str(tool), '--version'])
    match = re.search(r'\bLLVM version ([0-9]+\.[0-9]+\.[0-9]+)(?=[-\s]|$)', tool_version)
    if not match or match.group(1) != llvm:
        raise ValueError('llvm-nm version does not match the pinned Rust compiler')
    return tool, {'rust': expected_rust, 'host': host, 'llvm': llvm,
                  'path': str(tool), 'sha256': digest(tool), 'version': tool_version.strip()}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(bundle: Path, archive: Path, expected: dict, *, symbol_tool: Path) -> dict:
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError('Expected a regular iOS application bundle')
    plist = bundle / 'Info.plist'
    if plist.is_symlink() or not plist.is_file() or plist.stat().st_size > 1_000_000:
        raise ValueError('Missing or invalid application Info.plist')
    info = plistlib.loads(plist.read_bytes())
    fields = {'CFBundleIdentifier': 'com.carriez.flutterHbb', 'CFBundleExecutable': 'Runner',
              'MinimumOSVersion': expected['minimum'], 'DTSDKName': 'iphoneos' + expected['sdk'],
              'CFBundleSupportedPlatforms': ['iPhoneOS']}
    for key, value in fields.items():
        if info.get(key) != value:
            raise ValueError(f'iOS application metadata drift: {key}')
    scene = info.get('UIApplicationSceneManifest', {}).get('UISceneConfigurations', {})
    scenes = scene.get('UIWindowSceneSessionRoleApplication', [])
    if len(scenes) != 1 or scenes[0].get('UISceneDelegateClassName') != 'FlutterSceneDelegate':
        raise ValueError('The iOS device bundle is missing its Flutter scene delegate')
    paths = [bundle / 'Runner', bundle / 'Frameworks/App.framework/App',
             bundle / 'Frameworks/Flutter.framework/Flutter', archive]
    for path in paths:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < 2_000_000_000:
            raise ValueError(f'Missing or invalid native file: {path}')
        if inspect(['xcrun', 'lipo', '-archs', str(path)]).strip() != 'arm64':
            raise ValueError(f'Expected only arm64 in {path.name}')
    assets = bundle / 'Frameworks/App.framework/flutter_assets'
    if not assets.is_dir() or not any(p.is_file() for p in assets.rglob('*')):
        raise ValueError('Missing Flutter assets')
    for path in (archive, bundle / 'Runner'):
        symbols = {line.split()[-1] for line in inspect([str(symbol_tool), '--extern-only', '--defined-only', str(path)]).splitlines() if line.split()}
        missing = BRIDGE_SYMBOLS - symbols
        if missing:
            raise ValueError(f'Unlinked Rust/FRB symbols in {path.name}: {sorted(missing)}')
    return {'platform': 'ios-device', 'architecture': 'arm64',
            'minimum_os': expected['minimum'], 'sdk': expected['sdk'],
            'runner_sha256': digest(bundle / 'Runner'), 'rust_archive_sha256': digest(archive),
            'bridge_symbols': sorted(BRIDGE_SYMBOLS),
            'device_execution': 'not-verified', 'signature': 'not-verified'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads((ROOT / 'configs/toolchain.json').read_text(encoding='utf-8'))
        tool, reader = rust_llvm_nm(config['rust'])
        report = verify(args.bundle, args.archive, config['ios'], symbol_tool=tool)
        report['symbol_reader'] = reader
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Verified iOS device bundle structure and static Rust/FRB linkage; device execution is unverified.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException, subprocess.SubprocessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
