# Viper 底座与迁移状态

结构与入口整理日期：2026-10-01。导入基线：`d6c0376fd3cc14a64987c1a02f84c576cdcc83bf`。版本及其核对日期仍以 `configs/toolchain.json` 为准；本文不表示所有依赖已经升到最新 major。

## 代码边界

| 路径 | 职责 |
| --- | --- |
| `src/` | Rust 客户端、远程控制、会话与服务生命周期 |
| `src/server/`、`src/platform/` | 音视频、输入、网络和系统适配 |
| `flutter/` | 桌面端和移动端 UI |
| `src/ui/` | 尚未迁移完成的 Sciter UI |
| `libs/hbb_common/` | 与服务端共享的协议、连接、配置；固定 Git 子模块 |
| `libs/base/` | 客户端协议、文件传输和配置键 |
| `libs/pulsectl/` | 保留并维护的原 PulseAudio fork；来源、许可和限定修改可校验 |
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

## 当前验证与产物分层

下表描述已经实现的验证入口，不是对任意新提交自动盖章。每次改动仍须核对同一提交的 CI；运行中、跳过和历史候选成功不能替代当前结果。

| 入口 | 实际覆盖 | 不覆盖的边界 |
| --- | --- | --- |
| `foundation.yml` | 配置、版本/Actions/wrapper、Python 工具、工作流语法、Rust 核心库 | 全客户端、设备权限与 GUI |
| `flutter-validate.yml` | Linux x64 可复现绑定、Flutter 分析/测试、原生库、Debug 桌面包及包内 FFI；私有 PulseAudio 虚拟设备回归 | Linux Release 安装包、ARM、硬件编码和远程音频会话 |
| `bridge-source.yml` | 固定版本生成器从源码编译，绑定/锁文件无差异 | Android/F-Droid 整包 |
| `flutter-platform-tests.yml` | Windows/macOS 的完整 Flutter 单元测试和分析 | 原生安装包 |
| `windows-native.yml` | Windows x64/arm64 Rust + Flutter Release、包内 FFI、PE 架构、未签名归档 | 当前为 software-codec profile；不等于 GPU、驱动或安装程序验收 |
| `apple-native.yml` | macOS arm64 Rust Release 库、Debug/Release 应用、包内 FFI、Pods 锁文件和工程无差异 | 真机最低系统、硬件编码、公证；六个定制 Pods 仍保留 |
| `android-native.yml` | 三架构完整原生库与未签名 Release APK，保留 hwcodec，验证库一致性、ELF/ZIP 16 KiB 对齐和应用元数据 | 相机、后台服务、MediaProjection、输入、设备执行和正式签名 |
| `ios-native.yml` | SwiftPM、Rust 静态库、Release 应用及 XCArchive，使用编译器匹配的 LLVM 检查 11 个原生导出 | iPhone 上实际 FFI、安装、签名 IPA、商店交付 |
| `build-environment.yml` | 非 root 构建环境；显式受控的镜像发布入口 | 客户端部署和远程桌面服务器 |

普通 PR 验证只读，不使用签名凭据。完整历史发行矩阵只在相应条件下执行；Draft 跳过不能记作通过。Android/iOS 已有独立真实应用构建，不再只以链接配置检查代表这两个平台。

Dart 分析要求错误和警告为零，信息级诊断保留。原生编译警告也不屏蔽；编译通过不等于 Clippy 无诊断。所有平台仍需会话、音视频、输入、剪贴板、文件传输、服务生命周期及权限的端到端验收。

## Rust registry 与平台 fork

兼容范围内的 registry 刷新和 major/API 迁移是两类工作。前者更新 workspace `Cargo.lock`，不擅自移动定制 Git fork；后者必须审查每个调用者及平台能力。Cargo/pub 锁文件、生成代码和原生工程禁止在常规构建中静默改写。

`libs/pulsectl` 来自原锁定的 RustDesk fork，不是切换到同名公共包。限定改动为失效 libpulse 别名迁移、依赖下限和默认输入设备查找修复；源码、许可及精确替换由 `upstream.json` 和 `tools/verify_pulse_vendor.py` 校验。私有虚拟声卡测试显式启用 `private-server-tests`，普通 workspace 单元测试不会意外访问用户音频服务。详见该目录的 `VIPER.md` 与[registry 验证记录](registry-refresh-2026-10-01.md)。

## 未完成与发布阻塞

| 项目 | 剩余验收 |
| --- | --- |
| 旧发布矩阵 | Flutter SDK/FRB、Android 和 iOS 入口已收敛；完整矩阵、Linux 发行格式、Windows 完整硬件/安装配置仍需验收 |
| Apple 平台 | 当前 macOS/iOS 编译与未签名产物有独立验证；剩余六个 macOS Pods、权限、GUI、设备运行、签名、公证、安装与回退 |
| Android | 新构建栈已纳入真实三 ABI APK 验证；仍需去除 Flutter/插件上游 DSL/Kotlin 兼容开关，完成 F-Droid 四 ABI/定制 x86 engine、权限、后台服务、相机和真机签名验收 |
| Web | Dart 条件导入分析不代表 Web bundle 可构建；历史 Web 构建未启用且所需资源未完整纳入版本管理 |
| 原生依赖 major | 逐个审查平台 fork、安全补丁和破坏性 API，完成 workspace 与目标平台矩阵 |
| Sciter / 旧系统 | 迁移实际能力、启动与服务路径后再删除旧代码，不能通过关闭功能换取通过 |
| 安全设置 | 启用仓库 Dependency graph 后重新执行 Dependency review；当前设置阻塞不能按安全扫描通过处理 |
| 部署 | 完整构建、签名、来源证明、安装回归、版本回退与环境审批通过后才能发布 |

**PR 仍应保持 Draft；不得宣称全量版本迁移完成，也不得据此合并或执行生产发布。** 构建镜像、库文件和应用安装包是不同产物。

## 本次运行时回归面

运行时回归面包括 FFI 返回类型/同步语义/事件流、桥接初始化、链接处理、截图保存、文件任务异常传播、无损光标补边、Android 编码能力空值处理与扫码插件、iOS UIScene，以及 Linux 默认输入设备查找。上述路径是 SDK/接口迁移的直接回归面，需保留对应测试并继续做平台端到端验证。远程协议、加密语义、应用/签名身份、许可与本地化不在本次改变范围。

工具用法见 `tools/README.md`。各次 FRB、Apple、Android、iOS、Windows 和 registry 验证文档保留精确提交上下文；最新提交是否通过以 PR #1 的运行表和对应 Actions 结果为准。
