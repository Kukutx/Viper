# 剩余迁移与验收清单

核对日期：2026-10-02。依据任务基线 `8a0c7be69e6af9147f9206e7d72157d8d2cdd7dd` 的源码、锁文件和已完成 CI，以及本轮 Windows 测试修复 `1b6f1ef760c6de787aeff5b6e76356d9e94407a6`。这是待办和退出条件，不是“全部最新”证明；后续提交的运行状态以 PR #1 和对应 Actions 为准。架构与命令仍以 [foundation.md](foundation.md)、[tools/README.md](../../tools/README.md) 为入口，不另建 agent 规则。

## 后续复核：f91bf7e

2026-10-02 对源码与完整 CI/产物重新复核。设计发现、本次 Windows 校验增强与待实施方案见 [架构与交付复核](architecture-review-2026-10-02.md)；下表更新到该次复核，未来提交仍须重新验收。

## 先处理的真实阻塞

| 优先级 | 项目 | 当前事实 | 退出条件 |
| --- | --- | --- | --- |
| P0 | Windows 原生门禁 | 私有 API 编译错误已修复。`37054791846` 的 x64 成功；arm64 编译、48 项音频、9 项依赖测试和打包均完成，但 Rust 缓存收尾耗尽 job 预算后被取消。本次调整预算并增强测试数量与全部 PE 的校验 | 本次修复提交的两架构完整 job 成功，不能把旧构建重检或仅完成业务步骤当成整条检查通过 |
| 已解除设置阻塞 | Dependency review | `37054791735` 第二次 attempt、job `111045700344` 已成功；未降低 high 门槛。14 条依赖声明仍未识别许可证 | 后续每个提交继续执行原检查，并核实未知许可证；不把依赖差异检查当作全树安全证明 |
| P0 | 发布门禁 | 现代平台验证与历史完整发行矩阵是不同范围；Draft 跳过的工作流不能算成功 | 计划交付的平台/格式均有同一提交的完整证据，且安全检查通过；否则保持 Draft |

Dependency graph 的旧设置阻塞不再列为待管理员处理项。原安全检查继续保留，不扩大普通 PR 的 token 权限。生产签名和部署仍需要独立凭据与环境审批。

## 尚未迁移完的源码与依赖

| 优先级 | 范围与位置 | 剩余工作 | 退出条件 |
| --- | --- | --- | --- |
| P1 | HTTP 安全策略：`src/hbbs_http/http_client.rs` | 继承的代理构造失败回退默认客户端，以及非严格证书探测回退，需要独立协同迁移 | 明确返回错误、禁止指定代理失败后直连，支持显式自建服务信任；同步/异步与账户/上传调用方负向回归通过 |
| P1 | Rust 与原生平台：根目录及 `libs/*/Cargo.toml`、`vcpkg.json` | 继续审查其他 major/API；当前声明仍包括 zstd 0.13、cidr-utils 0.5、qrcode-generator 4.1、image 0.24，及 Windows/Apple/Linux/Android 平台依赖。它们是 manifest 约束示例，不是本日全部最新版本审计，也不是精确解析版本 | 逐项核验上游稳定发布、补丁与调用方；由包管理器生成锁文件；功能回归和目标平台完整编译通过 |
| P1 | 受维护 fork 与传递依赖：`Cargo.lock`、各 Git 依赖 | machine-uid/wallpaper 的传递 winreg 0.11 和 portable-pty 的 winreg 0.10 仍保留；cpal、输入、剪贴板、PTY、WebRTC/TLS 等 fork 的行为补丁不能丢失 | 先迁移调用方补丁，再刷新锁文件；保留来源、许可和功能测试，不用强制依赖覆盖替代迁移 |
| P1 | macOS 插件：`flutter/pubspec.lock`、`flutter/macos/Podfile.lock` | 六个定制 CocoaPods fallback：desktop_multi_window、flutter_custom_cursor、screen_retriever、texture_rgba_renderer、window_manager、window_size | 补齐各 fork 的 SwiftPM 支持并保持多窗口、光标、显示器、纹理和窗口能力；移除 Pods 后实际 Debug/Release 构建、包内 FFI 与工程无改写检查通过 |
| P1 | Flutter/Android：`flutter/pubspec.yaml`、`flutter/android/gradle.properties` | Flutter D-Bus 约束冲突，以及 Flutter Gradle 插件仍需的 DSL/Kotlin 兼容开关 | 协同迁移 Flutter/插件接口并消除冲突；不新增依赖覆盖；三 ABI APK、插件行为和锁文件验证通过 |
| P1 | Sciter/旧 ABI：`src/ui/`、`src/ui.rs` 与条件编译调用方 | 旧实现仍有引用；不能只删除依赖或目录 | 列出功能及启动/服务调用方，完成替代和回归后再删除旧路径；Flutter 与服务模式都必须继续工作 |
| P1 | Web：`flutter/web` 及历史 Web 构建入口 | 尚无完整 Web bundle 验收，历史资源和条件导入还需整理 | 完整资源受版本管理，真实 Web 编译与浏览器端连接/输入/文件能力验证；Dart 分析不替代这些结果 |

## 尚未闭环的发行与运行验收

| 优先级 | 范围 | 剩余工作与退出条件 |
| --- | --- | --- |
| P1 | F-Droid | 四 ABI 与定制 x86 engine 的完整源码构建；不拿普通 Android 三 ABI APK 替代，不删除第四 ABI |
| P1 | Linux 发行矩阵 | RPM、AppImage、Flatpak、DRM/DRM-wake 与对应依赖、功能门禁。当前 DEB 使用 Ubuntu 24.04 库、libc6 >= 2.39，不能标为旧 Linux 通用包；还需安装、升级、卸载、服务和回退验证 |
| P1 | Windows 发行矩阵 | 完整硬件编码/驱动、安装器和 MSI 安装卸载、服务注册启停、显示设置恢复；当前 software-codec Release 和临时 HKCU 测试不覆盖这些行为 |
| P1 | Apple 发行矩阵 | macOS 安装/回退、签名与公证；iOS 设备侧静态桥接、签名 IPA、安装及商店交付。未签名 XCArchive 不等于可分发的 IPA |
| P2 | 跨平台端到端 | GUI、最低系统版本、权限拒绝/恢复、声卡/音质、硬件编码、后台服务、相机、网络发现、远控会话、输入、剪贴板、文件传输、重连和版本回退 |
| P2 | 诊断清理 | 保留已有 Rust warning 与 Dart INFO，并逐类处理；不得压低诊断等级或屏蔽检查来声称零诊断 |
| P2 | 正式发布 | 确认产物/源码提交一致，完成签名、来源证明、SBOM、安全门禁、安装回归、回退和环境审批后，才执行发布；不得把构建镜像当作远程桌面服务部署 |

## f91bf7e 已修正的旧声明（历史记录）

根 `Cargo.toml` 的 `package.metadata.bundle.osx_minimum_system_version` 原为 10.14，与已经采用的 macOS 12.3 基线不一致。本轮改为 12.3；Foundation 的 Apple 配置测试改读中央 `apple.deployment_target`，同时核对 Cargo 元数据、Podfile、六处 Xcode 配置和 CI 环境值。没有再次提高实际部署下限，也没有修改应用身份、权限、业务代码、依赖选择或锁文件。

Windows 私有 API 的源码回归检查和 Apple 元数据校验是早期配置门禁，不能代替真实 Windows/macOS 构建。本轮本地工具测试为 393 项通过；实际 CI 结果在 PR 中另行记录。未完成项不因文档更新自动完成。
