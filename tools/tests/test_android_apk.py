"""Exercise APK rejection paths using synthetic ELF files, not device substitutes."""
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import android_toolchain
import verify_android_apk as apkcheck


def elf(abi='arm64-v8a', alignment=16384):
    kind, machine = android_toolchain.ABIS[abi][3:5]
    data = bytearray(256)
    data[:7] = b'\x7fELF' + bytes((kind, 1, 1))
    struct.pack_into('<HHI', data, 16, 3, machine, 1)
    if kind == 2:
        struct.pack_into('<Q', data, 32, 64)
        struct.pack_into('<HH', data, 54, 56, 1)
        struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, 0, 0, len(data), len(data), alignment)
    else:
        struct.pack_into('<I', data, 28, 52)
        struct.pack_into('<HH', data, 42, 32, 1)
        struct.pack_into('<IIIIIIII', data, 52, 1, 0, 0, 0, len(data), len(data), 5, alignment)
    return bytes(data)


class ApkTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.apk = self.root / 'app.apk'
        self.rust = self.root / 'rust.so'
        self.rust.write_bytes(elf())
        self.entries = {'AndroidManifest.xml': b'manifest', 'classes.dex': b'dex',
                        'assets/flutter_assets/AssetManifest.bin': b'assets'}
        for name in ('librustdesk.so', 'libflutter.so', 'libc++_shared.so', 'libapp.so'):
            self.entries['lib/arm64-v8a/' + name] = elf()

    def write(self):
        with zipfile.ZipFile(self.apk, 'w') as archive:
            for name, data in self.entries.items():
                archive.writestr(name, data)

    def verify(self):
        return apkcheck.verify(self.apk, self.rust, 'arm64-v8a')

    def test_complete_apk_records_limits_without_claiming_device_test(self):
        self.write()
        result = self.verify()
        self.assertEqual(result['device_execution'], 'not-verified')
        self.assertEqual(result['signature'], 'not-verified')
        self.assertEqual(len(result['native_sha256']), 4)

    def test_missing_required_entry(self):
        for name in ('AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/librustdesk.so', 'lib/arm64-v8a/libapp.so'):
            with self.subTest(name=name):
                original = self.entries.pop(name)
                self.write()
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    self.verify()
                self.entries[name] = original

    def test_wrong_architecture(self):
        self.entries['lib/arm64-v8a/libflutter.so'] = elf('x86_64')
        self.write()
        with self.assertRaisesRegex(ValueError, 'ABI'):
            self.verify()

    def test_extra_architecture(self):
        self.entries['lib/x86_64/libflutter.so'] = elf('x86_64')
        self.write()
        with self.assertRaisesRegex(ValueError, 'architecture'):
            self.verify()

    def test_all_libraries_require_page_compatibility(self):
        self.entries['lib/arm64-v8a/libflutter.so'] = elf(alignment=4096)
        self.write()
        with self.assertRaisesRegex(ValueError, '16 KiB'):
            self.verify()

    def test_wrong_rust_identity(self):
        self.rust.write_bytes(elf() + b'different')
        self.write()
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.verify()

    def test_traversal(self):
        for name in ('../escape', '/escape', r'lib\escape', 'C:/escape'):
            with self.subTest(name=name):
                self.entries[name] = b'bad'
                self.write()
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.verify()
                self.entries.pop(name)

    def test_duplicates(self):
        self.write()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.apk, 'a') as z:
                z.writestr('classes.dex', b'other')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.verify()

    def test_symlink_entry(self):
        self.write()
        with zipfile.ZipFile(self.apk, 'a') as z:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, 'target')
        with self.assertRaisesRegex(ValueError, 'entry type'):
            self.verify()

    def test_empty_manifest(self):
        self.entries['AndroidManifest.xml'] = b''
        self.write()
        with self.assertRaisesRegex(ValueError, 'Empty'):
            self.verify()

    def test_input_symlink(self):
        self.write()
        alternate = self.root / 'link.apk'
        alternate.symlink_to(self.apk)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            apkcheck.verify(alternate, self.rust, 'arm64-v8a')


class ElfTests(unittest.TestCase):
    def test_each_supported_abi(self):
        for abi in android_toolchain.ABIS:
            with self.subTest(abi=abi):
                apkcheck.verify_elf(elf(abi), abi)

    def test_truncated_table(self):
        with self.assertRaisesRegex(ValueError, 'table'):
            apkcheck.verify_elf(elf()[:90], 'arm64-v8a')

    def test_out_of_bounds_segment(self):
        data = bytearray(elf())
        struct.pack_into('<Q', data, 64 + 32, 100000)
        with self.assertRaisesRegex(ValueError, 'outside'):
            apkcheck.verify_elf(data, 'arm64-v8a')

    def test_missing_load_segment(self):
        data = bytearray(elf())
        struct.pack_into('<I', data, 64, 2)
        with self.assertRaisesRegex(ValueError, 'no loadable'):
            apkcheck.verify_elf(data, 'arm64-v8a')

    def test_wrong_endianness(self):
        data = bytearray(elf())
        data[5] = 2
        with self.assertRaisesRegex(ValueError, 'endianness'):
            apkcheck.verify_elf(data, 'arm64-v8a')

    def test_invalid_alignment(self):
        for alignment in (0, 32767):
            with self.subTest(alignment=alignment), self.assertRaisesRegex(ValueError, 'alignment'):
                apkcheck.verify_elf(elf(alignment=alignment), 'arm64-v8a')


if __name__ == '__main__':
    unittest.main()
