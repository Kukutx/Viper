"""一次性完成新版接口的明确 API 差异，随后由原生工具重新生成绑定。"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def change(path, old, new, count=1):
    file = ROOT / path
    text = file.read_text()
    if text.count(old) != count:
        raise ValueError(f'{path}: anchor drift: {old!r} ({text.count(old)} != {count})')
    file.write_text(text.replace(old, new))


def main():
    path = ROOT / 'src/flutter_ffi.rs'
    text = path.read_text()
    if 'ResultType<' not in text:
        raise ValueError('FFI ResultType migration anchor missing')
    text = text.replace('ResultType<', 'anyhow::Result<').replace('    ResultType,', '    anyhow,')
    # SyncReturn 的单参数尾逗号不能保留为 Rust 单元素 tuple。
    for call in ('crate::privacy_mode::get_supported_privacy_mode_impl()', 'crate::keyboard::input_source::get_supported_input_source()'):
        pattern = r'\(\s*serde_json::to_string\(&' + re.escape(call) + r'\)\s*\.unwrap_or_default\(\),\s*\)'
        text, count = re.subn(pattern, 'serde_json::to_string(&' + call + ').unwrap_or_default()', text)
        if count != 1:
            raise ValueError('Privacy/input-source return expression drift: ' + call)
    path.write_text(text)
    cargo = ROOT / 'Cargo.toml'
    cargo.write_text(cargo.read_text() + '\n[lints.rust]\nunexpected_cfgs = { level = "warn", check-cfg = ["cfg(frb_expand)"] }\n')
    change('flutter/lib/common.dart', 'await getInitialLink()', '(await AppLinks().getInitialLink())?.toString()')
    change('flutter/lib/models/model.dart', "if (dart.library.html) 'package:flutter_hbb/web/bridge.dart';", "if (dart.library.html) 'package:flutter_hbb/web/bridge.dart'\n    show EventToUI, EventToUI_Event, EventToUI_Rgba, EventToUI_Texture;")
    for file in (ROOT / 'flutter/lib').rglob('*.dart'):
        if 'generated' in file.parts:
            continue
        text = file.read_text()
        updated = text.replace('FilePicker.platform.', 'FilePicker.')
        if updated != text:
            file.write_text(updated)
    change('flutter/lib/native/win32.dart', '    ..wProductType = 0\n    ..wReserved = 0;', '    ..wProductType = 0;')
    file = ROOT / 'flutter/lib/common/widgets/toolbar.dart'
    text, count = re.subn(r'\bon:', 'on_:', file.read_text())
    if count != 7:
        raise ValueError(f'Expected seven migrated toggle parameters, got {count}')
    file.write_text(text)
    path = 'flutter/lib/common/widgets/address_book.dart'
    change(path, '.map((e) => DropdownMenuItem(value: e, child: buildItem(e)))', '.map((e) => DropdownItem<String>(value: e, height: 36, child: buildItem(e)))')
    change(path, '''    var menuItemStyleData = MenuItemStyleData(height: 36);
    if (contains && items.length > 1) {
      items.insert(1, DropdownMenuItem(enabled: false, child: Divider()));
      List<double> customHeights = List.filled(items.length, 36);
      customHeights[1] = 4;
      menuItemStyleData = MenuItemStyleData(customHeights: customHeights);
    }''', '''    if (contains && items.length > 1) {
      items.insert(1, DropdownItem<String>(enabled: false, height: 4, child: Divider()));
    }''')
    change(path, 'value: gFFI.abModel.currentName.value,', 'valueListenable: gFFI.abModel.currentName,')
    change(path, '      menuItemStyleData: menuItemStyleData,\n', '')
    change(path, 'searchInnerWidgetHeight:', 'searchBarWidgetHeight:')
    change(path, 'searchInnerWidget:', 'searchBarWidget:')
    # 内部的 Web 方法调用也要随接口改名；保留所有 JS API 字符串与参数字段。
    generated = (ROOT / 'flutter/lib/generated/frb_generated.dart').read_text()
    names = set(re.findall(r'\b(crateFlutterFfi\w+)\s*\(', generated))
    mapping = {name[15].lower() + name[16:]: name for name in names}
    file = ROOT / 'flutter/lib/web/bridge.dart'
    text = file.read_text()
    for old, new in mapping.items():
        text = re.sub(r'\b' + re.escape(old) + r'(?=\s*\()', new, text)
    text = text.replace('final String field0', 'String field0').replace('final int field0', 'int field0').replace('final bool field1', 'bool field1')
    # 删除从旧生成文件复制而未被实际事件类使用的私有 mixin。
    text = re.sub(r'final _privateConstructorUsedError = UnsupportedError\([\s\S]*?mixin _\$EventToUI \{[\s\S]*?\}\n\n', '', text, count=1)
    file.write_text(text)
    report = ROOT / 'tools/.reports'
    report.mkdir(parents=True, exist_ok=True)
    print('Applied explicit Result, dropdown, link, file-picker and Dart API migrations.')


if __name__ == '__main__':
    main()
