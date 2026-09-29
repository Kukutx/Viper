"""限定修复新事件流诊断的模块路径，不改既有日志行为。"""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
path = root / 'src/flutter.rs'
text = path.read_text()
old = 'log::debug!("Flutter event receiver closed: {error}");'
if text.count(old) != 6:
    raise ValueError('Expected six newly added event-stream diagnostics')
path.write_text(text.replace(old, 'hbb_common::' + old))
