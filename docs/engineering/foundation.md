# Viper 底座与迁移状态

版本核对日期：2026-09-29。导入基线：`d6c0376fd3cc14a64987c1a02f84c576cdcc83bf`。

## 代码边界

| 路径 | 职责 |
| --- | --- |
| `src/` | Rust 客户端、远程控制、会话与服务生命周期 |
| `src/server/`、`src/platform/` | 音视频、输入、网络和系统适配 |
| `flutter/` | 桌面端和移动端 UI |
| `src/ui/` | 尚未迁移完成的 Sciter UI |
| `libs/hbb_common/` | 与服务端共享的协议、连接、配置；固定 Git 子模块 |
| `libs/base/` | 客户端协议、文件传输和配置键 |
| `libs/scrap/`、`libs/enigo/`、`libs/clipboard/` | 采集、输入和剪贴板 |
| `configs/`、`tools/` | 版本真源、可测试的开发与构建入口 |
| `.github/workflows/` | 验证、构建和发布编排 |

参考 AppPlatform 的最小 agent 入口、配置真源、工具入口和验证/发布分离方式；不复制其业务服务或凭据。Viper 是桌面/移动客户端，构建镜像不是面向公网的远程桌面服务。

## 已落地的底座

唯一规则入口为 `agent.md`；原 Rust、Tokio、平台和本地化规范保留在 `rust-guidelines.md`。恢复导入提交中缺失的 hbb_common Gitlink，保留协议和上游许可。

Rust 1.98.1、Flutter 3.47.5 / Dart 3.13.4、Python 3.14.7、CMake 4.4.3 等版本由 `configs/toolchain.json` 管理。GitHub Actions 使用审查过的完整 SHA。基础工具、核心库与构建镜像分别验证；PR 无签名或生产发布凭据。

## Flutter / FRB 2 源码迁移

- Rust runtime、Dart runtime 和生成器统一为 FRB 2.13.0，绑定和两种锁文件一并提交。
- 100 个原同步接口保留同步调用语义；`SyncReturn` 转为 `frb(sync)`，暴露的结果类型使用生成器可识别的 `anyhow::Result`。事件发送失败可观察，不再忽略新的 `Result`。
- Dart 调用生成的公开顶层函数；原生端通过 `RustLib.init` 与 `ExternalLibrary` 初始化，不保留 FRB 1 适配层或手写内部 `api` 访问。Web 的原 JS 后端使用对应函数名，JS 消息和协议字段不改写。
- 直接 hosted Flutter 包升级到核验版本，更新传递依赖锁；删除原 `intl` 和 Android lifecycle 覆盖。仍受 SDK/上游约束的传递依赖不能被称为“全部最新”。
- `uni_links` / `uni_links_desktop` 改为 `app_links`，包含冷启动、运行中链接和 Windows 转发。iOS/Android 关闭重复的 Flutter 内建链接处理，让插件承担原能力；不取消链接功能。
- Dash Chat 使用带原许可的最新已发布源码，保留旧 fork 的输入栏 bottom SafeArea 定制；补丁及来源记在 `flutter/packages/dash_chat_2/VIPER.md`。
- 适配新版主题、下拉框、文件选择器和 Windows 类型。截图选择保存位置后仍交给 Rust 写入：取消才丢弃缓存，写入/选择器失败不提前消费缓存。
- Linux 光标方形补边采用无损像素复制，避免 alpha 混合导致单字节漂移；保留原逐字节回归断言。

`tools/bridge.py` 校验三方版本、生成器 SHA-256 和 Flutter/Dart 版本，禁止生成过程静默更新依赖或忽略接口错误。生成代码标为 generated；常规 CI 校验再生成无差异，不在构建时补丁修改业务源码。

## 验证边界

`flutter-validate.yml` 是只读验证流程，Draft PR 也执行：锁文件解析、绑定一致性、Dart 分析、Flutter 测试、Linux Rust 库编译，以及真实动态库的同步/异步 FFI 测试。每次执行的结论以对应提交的 GitHub Actions 日志为准；配置了步骤不等于该步骤已通过。

Dart 分析要求错误和警告为零，信息级弃用诊断仍记录在完整报告中。原生库的 Linux 编译和最小 FFI 测试不等于完整桌面壳、GPU 编码、系统服务或其他平台已通过。核心测试不代替会话、视频、输入、剪贴板和文件传输端到端测试。

## 未完成与发布阻塞

| 项目 | 剩余验收 |
| --- | --- |
| 旧发布矩阵 | Flutter SDK/FRB 入口已统一到中央配置，Linux Flutter 打包迁到原生 runner；完整矩阵仍需实跑，Sciter、Android 和平台工具/签名链尚未完成迁移 |
| Apple 平台 | 更新静态链接/旧 C header 引用，验证 macOS/iOS 编译、权限、签名、安装与运行 |
| Android | 联动迁移 AGP、Gradle、Kotlin、JDK、NDK 和旧插件；验证权限、后台服务、相机、真机与签名 |
| Web | Dart 条件导入分析不代表 Web bundle 可构建；历史 Web 构建未启用且所需资源未完整纳入版本管理 |
| 原生依赖 major | 逐个审查平台 fork、安全补丁和破坏性 API，完成 workspace 与目标平台矩阵 |
| Sciter / 旧系统 | 迁移实际能力、启动与服务路径后再删除旧代码，不能通过关闭功能换取通过 |
| 安全设置 | 启用仓库 Dependency graph 后重新执行 Dependency review；当前设置阻塞不能按安全扫描通过处理 |
| 部署 | 完整构建、签名、来源证明、安装回归、版本回退与环境审批通过后才能发布 |

**PR 仍应保持 Draft；不得宣称全量版本迁移完成，也不得据此合并或执行生产发布。** 构建镜像、库文件和应用安装包是不同产物。

## 本次运行时回归面

Rust 变动限于 FFI 返回类型、同步属性、事件流发送/关闭方式及生成绑定；Dart 变动包含桥接初始化和调用点、链接处理、截图保存、地址簿选择状态、文件任务异常传播及无损光标补边。上述路径是 SDK/接口迁移的直接回归面，需保留对应测试并继续做平台端到端验证。远程协议、加密语义、应用/签名身份、许可与本地化不在本次改变范围。

最新构建入口、Xcode 工具链与验证边界见 `build-entry-convergence.md`；历史验证记录的运行编号不代表新提交的结果。
