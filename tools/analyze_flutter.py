"""Run Dart analysis without hiding errors or warnings; retain complete diagnostics."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    dart = shutil.which('dart')
    if dart is None:
        print('ERROR: Dart executable not found; install the pinned Flutter SDK.', file=sys.stderr)
        return 1
    result = subprocess.run(
        [dart, 'analyze', '--format', 'machine'],
        cwd=ROOT / 'flutter', capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )
    output = result.stdout + result.stderr
    reports = ROOT / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'analyze.log').write_text(output, encoding='utf-8')
    counts = {level: sum(line.startswith(level + '|') for line in output.splitlines())
              for level in ('ERROR', 'WARNING', 'INFO')}
    print(f'Analyzer diagnostics: {counts}; exit={result.returncode}')
    important = [line for line in output.splitlines()
                 if line.startswith(('ERROR|', 'WARNING|'))]
    print('\n'.join(important[:150]))
    if result.returncode and not important:
        print('\n'.join(output.splitlines()[-80:]))
    return result.returncode or (1 if important else 0)


if __name__ == '__main__':
    raise SystemExit(main())
