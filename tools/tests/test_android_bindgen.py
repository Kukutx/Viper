"""Verify API-qualified cross-compilation without mutating host bindgen flags."""
from pathlib import Path
import shlex
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from android_cargo import TARGETS, environment


class AndroidBindgenTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='NDK with spaces ')
        self.addCleanup(temporary.cleanup)
        self.ndk = Path(temporary.name)
        for _, headers in TARGETS.values():
            (self.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include' / headers).mkdir(parents=True, exist_ok=True)

    def test_all_abis_get_exact_target_api_and_quoted_sysroot(self):
        for target, (clang, headers) in TARGETS.items():
            with self.subTest(target=target):
                inherited = {'BINDGEN_EXTRA_CLANG_ARGS': '-DHOST_FLAG', 'RUSTFLAGS': '-C debuginfo=1'}
                result = environment(target, self.ndk, 24, inherited)
                args = shlex.split(result[f'BINDGEN_EXTRA_CLANG_ARGS_{target}'])
                self.assertEqual(args[0], f'--target={clang}24')
                self.assertEqual(len(args), 3)
                self.assertEqual(Path(args[1].removeprefix('--sysroot=')), self.ndk/'toolchains/llvm/prebuilt/linux-x86_64/sysroot')
                self.assertTrue(args[2].endswith('/usr/include/' + headers))
                self.assertEqual(result['BINDGEN_EXTRA_CLANG_ARGS'], '-DHOST_FLAG')
                self.assertEqual(result['RUSTFLAGS'], '-C debuginfo=1')
                self.assertEqual(len(inherited), 2)

    def test_conflicting_target_override_is_not_silently_lost(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            environment('aarch64-linux-android', self.ndk, 24,
                        {'BINDGEN_EXTRA_CLANG_ARGS_aarch64-linux-android': '--target=wrong'})

    def test_missing_target_headers_are_fatal(self):
        with self.assertRaisesRegex(ValueError, 'Missing target headers'):
            environment('aarch64-linux-android', self.ndk/'absent', 24, {})

    def test_invalid_target_or_api_is_fatal(self):
        for target, api in [('x86_64-unknown-linux-gnu', 24), ('aarch64-linux-android', 0), ('aarch64-linux-android', True)]:
            with self.subTest(target=target, api=api), self.assertRaises(ValueError):
                environment(target, self.ndk, api, {})

    def test_native_entry_uses_the_versioned_cross_compiler(self):
        root = Path(__file__).resolve().parents[2]
        script = (root/'tools/native/build-android.sh').read_text()
        self.assertIn('python tools/android_cargo.py "$target" build --locked --release --lib --features flutter,hwcodec', script)
        self.assertNotIn('-D__ANDROID_API__', script)


if __name__ == '__main__':
    unittest.main()
