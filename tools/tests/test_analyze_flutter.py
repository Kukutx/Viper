import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_flutter


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def analyze(self, output='', code=0, executable='/tools/dart'):
        completed = subprocess.CompletedProcess([], code, output, '')
        with patch.object(analyze_flutter, 'ROOT', self.root), \
             patch.object(analyze_flutter.shutil, 'which', return_value=executable), \
             patch.object(analyze_flutter.subprocess, 'run', return_value=completed) as run, \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            result = analyze_flutter.main()
        return result, run

    def test_info_is_retained_without_becoming_an_error(self):
        output = 'INFO|HINT|DEPRECATED|test.dart|1|1|1|Use the newer API.\n'
        result, _ = self.analyze(output)
        self.assertEqual(result, 0)
        self.assertEqual((self.root / 'tools/.reports/analyze.log').read_text(), output)

    def test_error_is_fatal_even_with_zero_exit(self):
        self.assertNotEqual(self.analyze('ERROR|COMPILE_TIME_ERROR|UNDEFINED|x')[0], 0)

    def test_warning_is_fatal_even_with_zero_exit(self):
        self.assertNotEqual(self.analyze('WARNING|STATIC_WARNING|UNUSED|x')[0], 0)

    def test_tool_failure_is_preserved_without_diagnostics(self):
        self.assertEqual(self.analyze('Analyzer failed to start', 7)[0], 7)

    def test_missing_executable_does_not_launch_a_process(self):
        result, run = self.analyze(executable=None)
        self.assertNotEqual(result, 0)
        run.assert_not_called()

    def test_resolved_windows_batch_path_is_used(self):
        executable = 'C:/Program Files/Flutter/bin/dart.bat'
        result, run = self.analyze(executable=executable)
        self.assertEqual(result, 0)
        self.assertEqual(run.call_args.args[0], [executable, 'analyze', '--format', 'machine'])
        self.assertEqual(run.call_args.kwargs['encoding'], 'utf-8')

    def test_unicode_report_is_utf8(self):
        output = 'INFO|HINT|EXAMPLE|路径.dart|1|1|1|说明\n'
        self.analyze(output)
        self.assertEqual((self.root / 'tools/.reports/analyze.log').read_bytes(), output.encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
