"""保留完整分析输出，按错误/警告分类，不隐藏迁移中的诊断。"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
result = subprocess.run(['dart', 'analyze', '--format', 'machine'], cwd=root / 'flutter', capture_output=True, text=True)
output = result.stdout + result.stderr
(root / 'tools/.reports/analyze.log').write_text(output)
errors = [line for line in output.splitlines() if line.startswith('ERROR|')]
warnings = [line for line in output.splitlines() if line.startswith('WARNING|')]
print(f'Analyzer: {len(errors)} errors, {len(warnings)} warnings; exit={result.returncode}')
print('\n'.join(errors[:140]))
if result.returncode and not errors:
    print('\n'.join(output.splitlines()[-100:]))
# 这里是诊断步骤，保留原始退出码；警告仍然使候选门禁失败。
sys.exit(result.returncode)
