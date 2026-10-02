"""Build and verify native Windows bundles without signing or deployment."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
MACHINES = {'x64': 0x8664, 'arm64': 0xAA64}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pe_machine(path: Path) -> int:
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            raise ValueError(f'Not a PE binary: {path}')
        offset = struct.unpack_from('<I', header, 60)[0]
        if offset < 64 or offset > path.stat().st_size - 6:
            raise ValueError(f'Invalid PE header offset: {path}')
        stream.seek(offset)
        header = stream.read(6)
        if header[:4] != b'PE\0\0':
            raise ValueError(f'Invalid PE signature: {path}')
        return struct.unpack_from('<H', header, 4)[0]


def check_bundle(bundle: Path, source: Path, arch: str) -> None:
    expected = MACHINES[arch]
    for name in ('rustdesk.exe', 'librustdesk.dll', 'flutter_windows.dll'):
        path = bundle / name
        if path.is_symlink() or pe_machine(path) != expected:
            raise ValueError(f'Wrong architecture or symlink: {path}')
    if digest(source) != digest(bundle / 'librustdesk.dll'):
        raise ValueError('Bundled Rust library differs from this build')
    for path in (bundle / 'data/icudtl.dat', bundle / 'data/app.so'):
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise ValueError(f'Missing nonempty bundle asset: {path}')
    assets = bundle / 'data/flutter_assets'
    if not assets.is_dir() or not any(p.is_file() for p in assets.rglob('*')):
        raise ValueError('Flutter assets are missing')


def command(args: list[str], log: str, cwd: Path = ROOT) -> str:
    reports = ROOT / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    output = reports / log
    with output.open('w', encoding='utf-8') as stream:
        result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
    text = output.read_text(encoding='utf-8', errors='replace')
    if result.returncode:
        print('\n'.join(text.splitlines()[-100:]), file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, args)
    return text


def host() -> str:
    if platform.system() != 'Windows':
        raise ValueError('Native Windows validation requires a Windows host')
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
    if arch is None:
        raise ValueError(f'Unsupported Windows architecture: {platform.machine()}')
    return arch


def install_llvm(config: dict, arch: str) -> Path:
    version = config['llvm']
    asset = config['assets'][arch]
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or not re.fullmatch(r'[a-f0-9]{64}', asset['sha256']):
        raise ValueError('LLVM version and SHA-256 must be fixed')
    name = asset['name']
    if '/' in name or '\\' in name or not name.endswith('.tar.xz'):
        raise ValueError('Unexpected LLVM archive name')
    tools = ROOT / '.tools'
    if tools.is_symlink():
        raise ValueError('The tool directory cannot be a symlink')
    tools.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='llvm-', dir=tools) as temporary:
        directory = Path(temporary)
        archive = directory / 'llvm.tar.xz'
        url = f'https://github.com/llvm/llvm-project/releases/download/llvmorg-{version}/{urllib.parse.quote(name)}'
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as output:
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 1_100_000_000:
                    raise ValueError('LLVM archive exceeds size limit')
                output.write(chunk)
        if digest(archive) != asset['sha256']:
            raise ValueError('LLVM archive checksum mismatch')
        unpacked = directory / 'unpacked'
        with tarfile.open(archive, 'r:xz') as package:
            package.extractall(unpacked, filter='data')
        matches = list(unpacked.glob('*/bin/clang.exe'))
        if len(matches) != 1:
            raise ValueError('Expected one LLVM distribution')
        source = matches[0].parent.parent
        target = tools / f'llvm-{version}-{arch}'
        if target.exists() or target.is_symlink():
            raise ValueError(f'Use a clean LLVM installation directory: {target}')
        source.rename(target)
    compiler = target / 'bin/clang.exe'
    library = target / 'bin/libclang.dll'
    if pe_machine(compiler) != MACHINES[arch] or pe_machine(library) != MACHINES[arch]:
        raise ValueError('LLVM binaries do not match the native host')
    actual = command([str(compiler), '--version'], 'windows-clang.log')
    if not re.search(r'\bclang version ' + re.escape(version) + r'\b', actual):
        raise ValueError(f'LLVM version mismatch: {actual}')
    return target / 'bin'


def visual_studio(arch: str, major: int) -> dict[str, str]:
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    result = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-version',
                                      f'[{major}.0,{major+1}.0)', '-format', 'json'], encoding='utf-8')
    installations = json.loads(result)
    if len(installations) != 1 or installations[0].get('isPrerelease'):
        raise ValueError('A stable native Visual Studio installation is required')
    installation = installations[0]
    script = Path(installation['installationPath']) / 'VC/Auxiliary/Build/vcvarsall.bat'
    if not script.is_file():
        raise ValueError('Visual Studio C++ tools are missing')
    output = subprocess.check_output(f'cmd /d /s /c ""{script}" {arch} >nul && set"', text=True)
    for line in output.splitlines():
        key, sep, value = line.partition('=')
        if sep and key and not key.startswith('='):
            os.environ[key] = value
    return {'installationVersion': installation['installationVersion'], 'installationPath': installation['installationPath']}


def build() -> None:
    arch = host()
    config = json.loads((ROOT / 'configs/toolchain.json').read_text(encoding='utf-8'))
    windows = config['windows']
    studio = visual_studio(arch, windows['visual_studio_major'])
    llvm = install_llvm(windows, arch)
    os.environ['LIBCLANG_PATH'] = str(llvm)
    os.environ['PATH'] = str(llvm) + os.pathsep + os.environ['PATH']
    command([sys.executable, '-m', 'pip', 'install', f"cmake=={config['cmake']}"], 'windows-cmake-setup.log')
    cmake = shutil.which('cmake')
    if cmake is None or f"cmake version {config['cmake']}" not in command([cmake, '--version'], 'windows-cmake.log'):
        raise ValueError('Pinned CMake is not active')
    rust = command(['rustc', '-vV'], 'windows-rust.log')
    target = 'aarch64-pc-windows-msvc' if arch == 'arm64' else 'x86_64-pc-windows-msvc'
    if f'host: {target}' not in rust or f"release: {config['rust']}" not in rust:
        raise ValueError('Rust version or native host does not match the toolchain')
    vcpkg = Path(os.environ.get('RUNNER_TEMP', ROOT / '.tools')) / f'viper-vcpkg-{arch}'
    if vcpkg.exists():
        raise ValueError(f'Refusing to replace an existing vcpkg checkout: {vcpkg}')
    command(['git', 'clone', '--no-checkout', '--filter=blob:none', 'https://github.com/microsoft/vcpkg.git', str(vcpkg)], 'windows-vcpkg-clone.log')
    revision = config['vcpkg']['revision']
    command(['git', '-C', str(vcpkg), 'checkout', '--detach', revision], 'windows-vcpkg-checkout.log')
    if subprocess.check_output(['git', '-C', str(vcpkg), 'rev-parse', 'HEAD'], text=True).strip() != revision:
        raise ValueError('vcpkg revision mismatch')
    command([str(vcpkg / 'bootstrap-vcpkg.bat'), '-disableMetrics'], 'windows-vcpkg-bootstrap.log')
    triplet = f'{arch}-windows-static'
    os.environ['VCPKG_ROOT'] = str(vcpkg)
    packages = ['libyuv', 'libvpx', 'opus', 'aom', 'libjpeg-turbo']
    if arch == 'arm64':
        packages.append('libsodium')
        os.environ['SODIUM_LIB_DIR'] = str(vcpkg / f'installed/{triplet}/lib')
    command([str(vcpkg / 'vcpkg.exe'), 'install', '--classic', f'--triplet={triplet}',
             f'--overlay-ports={ROOT / "res/vcpkg"}', *packages], 'windows-vcpkg.log')
    command([sys.executable, str(ROOT / 'tools/prepare_flutter.py')], 'windows-preflight.log')
    command(['cargo', 'build', '--locked', '--release', '--lib', '--features', 'flutter'], 'windows-cargo.log')
    command(['cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter', 'audio', '--', '--test-threads=1'], 'windows-audio-tests.log')
    command(['cargo', 'test', '--locked', '--release', '--lib', '--features', 'flutter', 'windows_dependency', '--', '--test-threads=1'], 'windows-dependency-tests.log')
    flutter = shutil.which('flutter')
    if flutter is None:
        raise ValueError('Flutter is missing')
    command([flutter, 'build', 'windows', '--release', '--no-pub'], 'windows-flutter.log', ROOT / 'flutter')
    bundle = ROOT / f'flutter/build/windows/{arch}/runner/Release'
    check_bundle(bundle, ROOT / 'target/release/librustdesk.dll', arch)
    command(['dumpbin', '/dependents', str(bundle / 'rustdesk.exe')], 'windows-linked-libraries.log')
    os.environ['VIPER_NATIVE_LIBRARY'] = str(bundle / 'librustdesk.dll')
    command([flutter, 'test', '--no-pub', 'test_native/bridge_ffi_test.dart'], 'windows-ffi.log', ROOT / 'flutter')
    command(['git', 'diff', '--exit-code', 'HEAD', '--', 'Cargo.lock', 'flutter/pubspec.yaml', 'flutter/pubspec.lock', 'flutter/windows'], 'windows-source-drift.log')
    report = {'arch': arch, 'rust_target': target, 'llvm': windows['llvm'], 'visual_studio': studio,
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'rust_library_sha256': digest(bundle / 'librustdesk.dll'), 'profile': 'software-codec',
              'signing': 'not-performed'}
    (ROOT / 'tools/.reports/windows-native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Windows {arch} Release bundle and real FFI validated')


def main() -> int:
    try:
        build()
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
