"""Exercise compiler-matched symbol reader selection without executing an SDK."""
from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_ios_bundle as verifier


class IosSymbolReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = 'aarch64-apple-darwin'
        self.tool = self.root / 'lib/rustlib' / self.host / 'bin/llvm-nm'
        self.tool.parent.mkdir(parents=True)
        self.tool.write_bytes(b'fixture, not an executable')
        self.version = 'rustc 1.98.1\nrelease: 1.98.1\nhost: aarch64-apple-darwin\nLLVM version: 22.1.8\n'
        self.tool_version = 'llvm-nm, compatible with GNU nm\nLLVM version 22.1.8-rust-1.98.1-stable\n'
        self.sysroot = str(self.root)
        self.calls = []
        self.mock = patch.object(verifier, 'inspect', side_effect=self.inspect).start()
        self.addCleanup(patch.stopall)

    def inspect(self, args):
        self.calls.append(args)
        if args == ['rustc', '-vV']:
            return self.version
        if args == ['rustc', '--print', 'sysroot']:
            return self.sysroot + '\n'
        if args == [str(self.tool), '--version']:
            return self.tool_version
        self.fail(f'Unexpected external command: {args}')

    def test_matching_component_records_compiler_and_reader_identity(self):
        tool, info = verifier.rust_llvm_nm('1.98.1')
        self.assertEqual(tool, self.tool)
        self.assertEqual(info['llvm'], '22.1.8')
        self.assertEqual(info['sha256'], hashlib.sha256(self.tool.read_bytes()).hexdigest())
        self.assertEqual(len(self.calls), 3)

    def test_compiler_drift_is_rejected_before_resolving_sysroot(self):
        with self.assertRaisesRegex(ValueError, 'Rust version drift'):
            verifier.rust_llvm_nm('1.98.0')
        self.assertEqual(self.calls, [['rustc', '-vV']])

    def test_missing_fields_and_unsafe_host_are_rejected(self):
        for line in ('host: aarch64-apple-darwin\n', 'LLVM version: 22.1.8\n'):
            with self.subTest(line=line), patch.object(verifier, 'inspect', return_value=self.version.replace(line, '')):
                with self.assertRaises(ValueError):
                    verifier.rust_llvm_nm('1.98.1')
        self.version = self.version.replace('aarch64-apple-darwin', '../../external-tool')
        with self.assertRaisesRegex(ValueError, 'host triple'):
            verifier.rust_llvm_nm('1.98.1')

    def test_nonabsolute_sysroot_is_rejected(self):
        self.sysroot = 'relative-toolchain'
        with self.assertRaisesRegex(ValueError, 'absolute path'):
            verifier.rust_llvm_nm('1.98.1')

    def test_missing_component_has_no_system_fallback(self):
        self.tool.unlink()
        with self.assertRaisesRegex(ValueError, 'llvm-tools-preview'):
            verifier.rust_llvm_nm('1.98.1')
        self.assertEqual(len(self.calls), 2)

    def test_symlinked_tool_is_rejected(self):
        real = self.root / 'other-nm'
        self.tool.rename(real)
        self.tool.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'llvm-tools-preview'):
            verifier.rust_llvm_nm('1.98.1')

    def test_different_or_unparseable_reader_is_rejected(self):
        for text in ('LLVM version 21.0.0', 'LLVM version 22.1.80', 'unversioned nm'):
            self.tool_version = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'does not match'):
                verifier.rust_llvm_nm('1.98.1')

    def test_reader_version_command_failure_propagates(self):
        def inspect(args):
            if args == [str(self.tool), '--version']:
                raise ValueError('llvm-nm failed')
            return self.inspect(args)
        self.mock.side_effect = inspect
        with self.assertRaisesRegex(ValueError, 'llvm-nm failed'):
            verifier.rust_llvm_nm('1.98.1')

    def test_subprocess_failure_or_timeout_is_not_ignored(self):
        patch.stopall()
        failed = subprocess.CompletedProcess(['llvm-nm'], 1, '', 'Unknown attribute kind')
        with patch.object(verifier.subprocess, 'run', return_value=failed):
            with self.assertRaisesRegex(ValueError, 'Unknown attribute kind'):
                verifier.inspect(['llvm-nm', 'archive.a'])
        with patch.object(verifier.subprocess, 'run', side_effect=subprocess.TimeoutExpired('llvm-nm', 120)):
            with self.assertRaises(subprocess.TimeoutExpired):
                verifier.inspect(['llvm-nm', 'archive.a'])


if __name__ == '__main__':
    unittest.main()
