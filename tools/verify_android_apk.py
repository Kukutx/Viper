"""Check APK structure, bundled Rust identity, CPU ABI and 16 KiB ELF alignment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
import zipfile

from android_toolchain import ABIS

LIMIT = 512 * 1024 * 1024


def verify_elf(data: bytes, abi: str) -> None:
    if abi not in ABIS:
        raise ValueError(f'Unsupported ABI: {abi}')
    elf_class, machine = ABIS[abi][3:5]
    minimum = 64 if elf_class == 2 else 52
    if len(data) < minimum or data[:7] != b'\x7fELF' + bytes((elf_class, 1, 1)):
        raise ValueError('Invalid ELF header, class or endianness')
    kind, actual_machine, version = struct.unpack_from('<HHI', data, 16)
    if (kind, actual_machine, version) != (3, machine, 1):
        raise ValueError('ELF is not a shared library for the required ABI')
    if elf_class == 2:
        offset = struct.unpack_from('<Q', data, 32)[0]
        entry_size, count = struct.unpack_from('<HH', data, 54)
        fmt, size = '<IIQQQQQQ', 56
    else:
        offset = struct.unpack_from('<I', data, 28)[0]
        entry_size, count = struct.unpack_from('<HH', data, 42)
        fmt, size = '<IIIIIIII', 32
    if not 0 < count < 65535 or entry_size != size or offset < minimum or offset + size * count > len(data):
        raise ValueError('Invalid ELF program header table')
    loads = 0
    for i in range(count):
        fields = struct.unpack_from(fmt, data, offset + i * size)
        if fields[0] != 1:
            continue
        loads += 1
        if elf_class == 2:
            file_offset, virtual, file_size, memory_size, alignment = fields[2], fields[3], fields[5], fields[6], fields[7]
        else:
            file_offset, virtual, file_size, memory_size, alignment = fields[1], fields[2], fields[4], fields[5], fields[7]
        if file_size > memory_size or file_offset + file_size > len(data):
            raise ValueError('ELF load segment lies outside the file')
        if alignment < 1 or alignment & (alignment - 1) or file_offset % alignment != virtual % alignment:
            raise ValueError('Invalid ELF load segment alignment')
        if elf_class == 2 and alignment < 16384:
            raise ValueError('64-bit native library does not support 16 KiB pages')
    if loads == 0:
        raise ValueError('ELF has no loadable segments')


def verify(apk: Path, rust_library: Path, abi: str, release: bool = True) -> dict:
    if abi not in ABIS:
        raise ValueError(f'Unsupported ABI: {abi}')
    for path in (apk, rust_library):
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= LIMIT:
            raise ValueError(f'Expected a bounded nonempty regular file: {path}')
    native = {}
    with zipfile.ZipFile(apk) as archive:
        files = archive.infolist()
        names = [f.filename for f in files]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate APK entries')
        if sum(f.file_size for f in files) > 2 * 1024 * 1024 * 1024:
            raise ValueError('APK exceeds uncompressed size limit')
        for f in files:
            path = PurePosixPath(f.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in f.filename or ':' in f.filename:
                raise ValueError('Unsafe APK path')
            if stat.S_ISLNK(f.external_attr >> 16) or f.flag_bits & 1 or f.file_size > LIMIT:
                raise ValueError('Unsupported APK entry type or size')
            if f.filename.startswith('lib/') and not f.is_dir():
                if len(path.parts) != 3 or path.parts[1] != abi or not f.filename.endswith('.so'):
                    raise ValueError('Unexpected APK native architecture or file')
                data = archive.read(f)
                verify_elf(data, abi)
                native[path.name] = hashlib.sha256(data).hexdigest()
        required = {f'lib/{abi}/librustdesk.so', f'lib/{abi}/libflutter.so',
                    f'lib/{abi}/libc++_shared.so', 'AndroidManifest.xml', 'classes.dex'}
        required.add(f'lib/{abi}/libapp.so' if release else 'assets/flutter_assets/kernel_blob.bin')
        if not required.issubset(names):
            raise ValueError(f'Incomplete APK: {sorted(required.difference(names))}')
        for name in required:
            if archive.getinfo(name).file_size == 0:
                raise ValueError(f'Empty required APK entry: {name}')
        if not any(name.startswith('assets/flutter_assets/') for name in names):
            raise ValueError('Missing Flutter assets')
    if native['librustdesk.so'] != hashlib.sha256(rust_library.read_bytes()).hexdigest():
        raise ValueError('Bundled Rust library differs from the validated Cargo output')
    return {'abi': abi, 'mode': 'release' if release else 'debug', 'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
            'native_sha256': native, 'device_execution': 'not-verified', 'signature': 'not-verified'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('rust_library', type=Path)
    parser.add_argument('--abi', choices=tuple(ABIS), required=True)
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify(args.apk, args.rust_library, args.abi, not args.debug)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'Verified APK content and native libraries: {args.abi}')
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, struct.error) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
