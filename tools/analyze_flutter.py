"""Run Dart analysis without hiding errors or warnings; retain complete diagnostics."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    result = subprocess.run(
        ['dart', 'analyze', '--format', 'machine'],
        cwd=ROOT / 'flutter', capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    reports = ROOT / 'tools/.reports'
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'analyze.log').write_text(output)
    counts = {level: sum(line.startswith(level + '|') for line in output.splitlines())
              for level in ('ERROR', 'WARNING', 'INFO')}
    print(f'Analyzer diagnostics: {counts}; exit={result.returncode}')
    important = [line for line in output.splitlines()
                 if line.startswith(('ERROR|', 'WARNING|'))]
    print('\n'.join(important[:150]))
    if result.returncode and not important:
        print('\n'.join(output.splitlines()[-80:]))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
