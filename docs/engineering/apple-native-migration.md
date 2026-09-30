# Apple 原生构建迁移

这是迁移中的原生构建说明，不是生产发布批准。macOS Rust 库、桌面壳、包内 FFI、GUI/权限、签名和部署是不同验收项；各项结果以精确提交的 Actions 为准。

## 原生接口与链接

FRB 2 使用 `full_dep: false` 时生成的 C 文件只是占位注释，不能继续承担 FRB 1 的 `dummy_method_to_enforce_bundling` 职责。因此不再配置 C header 输出，也不手写 FRB wire 定义。`flutter/native/rustdesk.h` 仅声明 `src/flutter.rs` 已存在的三个 runner C ABI：原生启动、重新打开窗口及 RGBA 读取；Rust/Dart 生成文件继续由固定版本生成器维护。

macOS 三种 Xcode 配置共用已跟踪的 `Runner-Bridging-Header.h`，动态库采用正常链接而非 weak link。iOS 三种配置为原有 Rust archive 加上 `-force_load`，保留原有 `DEAD_CODE_STRIPPING=NO`，去掉旧 dummy 调用。iOS 仍需完整构建、静态符号检查、设备和签名验证，不能由这些源码检查推断已通过。

多窗口 Swift 注册改用 `app_links` 和 `sqflite_darwin`。`path_provider_foundation 2.6.0` 已使用 `dartPluginClass`，不再导入或注册不存在的 Swift 模块；Dart 路径访问依赖和窗口回调没有删除。原 AppDelegate 按 Flutter 的迁移提示声明安全状态恢复支持。

## macOS 基线与工具

现代化 macOS runner 的最低版本明确设为 **12.3**，Podfile、Xcode 六个设置和原生验证环境保持一致。此前的 10.14 不是新 Flutter 构建的有效支持承诺：Flutter 3.47.5 自身会自动把旧项目升级到至少 12.0。这里同时对齐现有 native 验证的 12.3 基线。历史完整发布矩阵尚未统一，不能据此宣称所有发行渠道均已切换。

`tools/native/setup-macos.sh` 面向 Apple Silicon 主机，安装开发工具，并按中央 vcpkg revision 和仓库 overlay 编译软件编解码依赖。它不等同于硬件编码、所有架构或生产打包环境。`apple-native.yml` 使用只读权限、无签名凭据，验证 Rust Release 库和 Flutter Debug 桌面包；检查包内库与 Cargo 输出的字节一致性、arm64 架构及真实 FFI。

Swift Package Manager 保持启用；仍需 CocoaPods 的六个维护 fork 没有被删除或以公共同名包替换。Xcode/Podfile/scheme 的自动改写必须形成可审查提交，不能在构建中静默接受。报告保留原生锁文件、项目差异和生成注册器用于核对。

## 资源恢复

`res/mac-tray-dark-x2.png` 恢复自 rustdesk/rustdesk 同路径的原版 60×60 PNG，Git blob 为 `8b838cb5ea16f38e4d788589a33fe72570f4c394`。没有重新设计图标或删除托盘功能；原有项目许可与署名不变。

## 已执行的诊断

- 运行 `36652468249` 首次暴露缺失托盘 PNG；其 C header 生成步骤虽成功，产物仅为占位注释，不算 Apple 链接验证通过。
- 运行 `36655225881`、源提交 `22cf1e6a957727a5a5c1760f58cc38d937112c75`：真实 macOS Rust Release 库构建成功；根 crate 有 **105 条 warning**，不是无警告或 Clippy 通过。随后桌面壳因旧 `path_provider_foundation` Swift import 失败，包内 FFI 未执行。
- 上述运行诊断 artifact `11073075698` 的 SHA-256 为 `d13006264bdb67736327759014a71c0fc5fd05a14968b2c39edb9874ed440ddd`。不要把该运行的 Rust 成功误记为整个 job 成功。

本文件之后的修复和原生项目收敛需查看对应提交的 CI 结果。GUI 启动、远控、多窗口链接、服务、权限、硬件编码、签名、公证、安装和回退不在最小 FFI 测试覆盖范围内。

## 上游依据

- FRB 2.13.0 的 C generator：`fzyzcjy/flutter_rust_bridge`，`frb_codegen/src/library/codegen/generator/wire/c/`。
- Flutter 3.47.5 最低平台迁移：`flutter/flutter`，`packages/flutter_tools/lib/src/macos/migrations/macos_deployment_target_migration.dart`。
- Dart-only 路径插件：`flutter/packages`，tag `path_provider_foundation-v2.6.0`，`packages/path_provider/path_provider_foundation/pubspec.yaml`。
