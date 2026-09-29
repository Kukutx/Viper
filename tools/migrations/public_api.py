"""将客户端切换到 FRB 2 公开函数，修复新版 UI API 与分析诊断。"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def change(name, old, new, count=1):
    path = ROOT / name
    text = path.read_text()
    if text.count(old) != count:
        raise ValueError(f'{name}: expected {count} occurrences of {old!r}; got {text.count(old)}')
    path.write_text(text.replace(old, new))


def main():
    generated = (ROOT / 'flutter/lib/generated/frb_generated.dart').read_text()
    names = set(re.findall(r'\b(crateFlutterFfi\w+)\s*\(', generated))
    if len(names) < 300:
        raise ValueError('Generated API is incomplete')
    mapping = {name: name[15].lower() + name[16:] for name in names}
    receiver = re.compile(r'\b(?:bind|_ffiBind|rustdeskImpl)(\s*\.\s*)(' + '|'.join(sorted(mapping, key=len, reverse=True)) + r')\b')
    namespace = "import 'package:flutter_hbb/generated/flutter_ffi.dart'\n    if (dart.library.html) 'package:flutter_hbb/web/bridge.dart' as bind;\n"
    for file in (ROOT / 'flutter/lib').rglob('*.dart'):
        if 'generated' in file.parts:
            continue
        text = file.read_text()
        text, count = receiver.subn(lambda m: 'bind.' + mapping[m[2]], text)
        if count:
            if file.name == 'web_model.dart':
                text = text.replace("import 'package:flutter_hbb/web/bridge.dart';", "import 'package:flutter_hbb/web/bridge.dart' as bind;")
            else:
                text = namespace + text
            file.write_text(text)
    change('flutter/lib/models/platform_model.dart', "import 'package:flutter_hbb/generated/frb_generated.dart'\n    if (dart.library.html) 'package:flutter_hbb/web/bridge.dart';\n", '')
    change('flutter/lib/models/platform_model.dart', 'RustLibApi get bind => platformFFI.ffiBind;\n', '')
    change('flutter/lib/models/native_model.dart', '  late RustLibApi _ffiBind;\n', '')
    change('flutter/lib/models/native_model.dart', '  RustLibApi get ffiBind => _ffiBind;\n', '')
    change('flutter/lib/models/native_model.dart', '      _ffiBind = RustLib.instance.api;\n', '')
    change('flutter/lib/models/native_model.dart', '_startListenEvent(_ffiBind)', '_startListenEvent()')
    change('flutter/lib/models/native_model.dart', 'void _startListenEvent(RustLibApi rustdeskImpl)', 'void _startListenEvent()')
    change('flutter/lib/models/web_model.dart', '  final RustLibApi _ffiBind = RustLibApi();\n', '')
    change('flutter/lib/models/web_model.dart', '  RustLibApi get ffiBind => _ffiBind;\n', '')
    # Web 后端仍调用原来的 JS API；移除无状态的旧 API 容器，不改变事件和传输字段。
    path = ROOT / 'flutter/lib/web/bridge.dart'
    text = path.read_text()
    start = text.index('class RustLibApi {\n')
    head, body = text[:start], text[start + len('class RustLibApi {\n'):]
    if not body.rstrip().endswith('}'):
        raise ValueError('Web API container ending drift')
    body = body.rstrip()[:-1]
    body = '\n'.join(line[2:] if line.startswith('  ') else line for line in body.splitlines())
    for old, new in mapping.items():
        body = re.sub(r'\b' + old + r'\b', new, body)
    path.write_text(head + body.rstrip() + '\n')
    change('flutter/lib/desktop/pages/install_page.dart', 'FilePicker.platform\n', 'FilePicker\n')

    path = 'flutter/lib/common/widgets/address_book.dart'
    change(path, '  var menuPos = RelativeRect.fill;\n', '''  var menuPos = RelativeRect.fill;
  late final ValueNotifier<String?> _selectedAddressBook;
  late final Worker _addressBookNameWorker;
  final _addressBookSearch = TextEditingController();

  @override
  void initState() {
    super.initState();
    _selectedAddressBook = ValueNotifier(gFFI.abModel.currentName.value);
    _addressBookNameWorker = ever<String>(gFFI.abModel.currentName, (name) {
      _selectedAddressBook.value = name;
    });
  }

  @override
  void dispose() {
    _addressBookNameWorker.dispose();
    _selectedAddressBook.dispose();
    _addressBookSearch.dispose();
    super.dispose();
  }
''')
    change(path, 'valueListenable: gFFI.abModel.currentName,', 'valueListenable: _selectedAddressBook,')
    change(path, 'final TextEditingController textEditingController = TextEditingController();', 'final textEditingController = _addressBookSearch;')

    # Rust 继续拥有截图缓存及原子成功/失败语义；使用只选择路径的官方插件。
    change('flutter/pubspec.yaml', 'dependencies:\n', 'dependencies:\n  file_selector: 1.1.0\n', count=2)
    # 第二次匹配是 dev_dependencies 后缀；避免重复声明。
    change('flutter/pubspec.yaml', 'dev_dependencies:\n  file_selector: 1.1.0\n', 'dev_dependencies:\n')
    path = 'flutter/lib/models/model.dart'
    change(path, "import 'dart:convert';", "import 'dart:convert';\nimport 'package:file_selector/file_selector.dart' as file_selector;\nimport '../utils/screenshot_save.dart';")
    file = ROOT / path
    text = file.read_text()
    start = text.index('          String? outputFile = await FilePicker.saveFile(')
    end = text.index('\n        });', start)
    text = text[:start] + '''          try {
            final res = await saveScreenshotToSelectedPath(
              selectPath: () async => (await file_selector.getSaveLocation(
                suggestedName: 'screenshot_$ts.png',
                confirmButtonText: translate('Save as'),
                acceptedTypeGroups: const [
                  file_selector.XTypeGroup(
                    label: 'PNG', extensions: ['png'],
                    uniformTypeIdentifiers: ['public.png'],
                  ),
                ],
              ))?.path,
              handleAction: (action) => bind.sessionHandleScreenshot(
                sessionId: sessionId, action: action,
              ),
            );
            if (res.isNotEmpty) {
              msgBox(sessionId, 'custom-nook-nocancel-hasclose-error',
                  'Take screenshot', res, '', dialogManager);
            }
          } catch (error) {
            msgBox(sessionId, 'custom-nook-nocancel-hasclose-error',
                'Take screenshot', error.toString(), '', dialogManager);
          }''' + text[end:]
    if 'FilePicker.' not in text:
        text = re.sub(r"^import 'package:file_picker/file_picker.dart';\n", '', text, flags=re.M)
    file.write_text(text)

    # 新 SDK 的无效代码诊断：删除未被调用的私有成员，不隐藏警告。
    change('flutter/lib/common.dart', "import 'dart:math';\n", '')
    path = ROOT / 'flutter/lib/desktop/pages/desktop_setting_page.dart'
    text = path.read_text().replace('const _Printer({super.key});', 'const _Printer();')
    text, count = re.subn(r'\n_LabeledTextField\([\s\S]*?\n\}\n', '\n', text)
    if count != 1:
        raise ValueError('Unused labeled field anchor drift')
    path.write_text(text)
    path = ROOT / 'flutter/lib/desktop/pages/view_camera_page.dart'
    text = path.read_text()
    for name in ('_buildCustomCursor', '_buildDisabledCursor'):
        text, count = re.subn(r'\n  MouseCursor ' + name + r'\([^\n]*\) \{[\s\S]*?\n  \}\n', '\n', text)
        if count != 1:
            raise ValueError('Unused camera cursor anchor drift')
    path.write_text(text)
    path = ROOT / 'flutter/lib/desktop/widgets/material_mod_popup_menu.dart'
    text, count = re.subn(r'^const double _kDefaultIconSize[^\n]*\n', '', path.read_text(), flags=re.M)
    if count != 1:
        raise ValueError('Unused popup constant anchor drift')
    path.write_text(text)
    path = ROOT / 'flutter/lib/desktop/widgets/tabbar_widget.dart'
    text, count = re.subn(r'\n  static RxString tablabelGetter\([^\n]*\) \{[\s\S]*?\n  \}\n', '\n', path.read_text())
    if count != 1:
        raise ValueError('Unused tab label anchor drift')
    path.write_text(text)
    path = 'flutter/lib/mobile/pages/file_manager_page.dart'
    change(path, 'selectedItems!.items.single.isFile', 'selectedItems.items.single.isFile')
    change(path, '_exportFile(selectedItems!.items.single)', '_exportFile(selectedItems.items.single)')
    change(path, '_exportItems(selectedItems!)', '_exportItems(selectedItems)')
    path = 'flutter/lib/models/file_model.dart'
    for expression in ('registerReadEmptyDirsTask(isLocal, path)', 'pendingTask.completer.future', 'fetchDirectory(path, isLocal, showHidden)', 'task.completer.future', 'registerReadRecursiveTask(actID)'):
        change(path, 'return ' + expression + ';', 'return await ' + expression + ';')
    change('flutter/lib/utils/http_service.dart', "        default:\n          throw Exception('Unsupported HTTP method');\n", '')
    change('flutter/packages/dash_chat_2/lib/src/widgets/message_list/message_list.dart', '      default:\n        return false;\n', '')
    path = ROOT / 'flutter/packages/dash_chat_2/VIPER.md'
    path.write_text(path.read_text() + '\nDart 3.13: removed an unreachable default in the exhaustive separator-frequency switch.\n')
    # FRB 2 的发送返回 Result；接收方已关闭时记录诊断，不静默丢弃错误。
    path = ROOT / 'src/flutter.rs'
    text = path.read_text()
    pattern = re.compile(r'^(\s*)((?:stream|s)\.add\([^\n]+\));$', re.M)
    text, count = pattern.subn(lambda m: m[1] + 'if let Err(error) = ' + m[2] + ' {\n' + m[1] + '    log::debug!("Flutter event receiver closed: {error}");\n' + m[1] + '}', text)
    if count < 5:
        raise ValueError(f'Expected at least five Result-returning event sends, got {count}')
    path.write_text(text)
    print(f'Public FRB API migrated: {len(mapping)} functions. Event send Results handled: {count}.')


if __name__ == '__main__':
    main()
