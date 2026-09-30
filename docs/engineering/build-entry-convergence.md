# 构建入口收敛（2026-09-30）

本轮以 `693c0c36ada9270054bfe2a8d6c7e16bc4c2f085` 为底座。任务分支保持 Draft；没有签名发布、合并或生产部署。

## 变更

- 固定 Xcode 27.0 / build 27A266a、macOS SDK 27.0、CocoaPods 1.17.0；选择每进程 DEVELOPER_DIR，不修改全局 xcode-select。GitHub 的 `xcode-27` 是预览 runner，SDK 本身须通过精确版本检查。Debug 和 Release 分别检查真实包内库；Release 的归档与 SHA-256 清单仅供 CI 验证。
- Release 链接参数继承 Pods/SwiftPM 设置，同时保留原有 pre-login section。首次新工具链构建的 Debug 包成功，但锁文件差异门禁失败。审查运行 36660492263 导出的 Podfile.lock，仅六个定制插件 spec checksum 改变，版本、依赖和来源未变；提交这些变化后仍须重跑严格无差异检查，不删除门禁。
- `tools/viper.py versions` 管理完整 Flutter 构建工作流中的版本镜像值。Flutter 版本统一，Rust 构建不再借用 Sciter Rust pin；平台 fork、身份、协议及权限不改。
- `build.py` 的 Debian、Arch、macOS、Windows Flutter 入口先校验 SDK/桥接/锁文件，包含跳过 Cargo 的调用；Flutter build 使用 --no-pub。Linux 架构目录在源码中按主机选择，不在 CI 临时 sed 改写。
- 保留全部 15 个工作流任务，以及 Linux x64/arm64、DRM、Windows/iOS/Android、Sciter、AppImage/Flatpak 的原有职责。两个 Flutter Linux 打包任务改为 Ubuntu 24.04 原生 runner；不再借用旧 node16/QEMU 构建 action、旧 Flutter-eLinux 或旧引擎。
- 保留 DRM 测试及测试数非零断言、产物内 libdrmtap 和 consent/provenance 检查。Linux 构建系统基线改变，不再承诺 Ubuntu 18.04 的二进制兼容性；这不等于任何远控/权限功能被移除。
- F-Droid 的 SDK/FRB 参数读取中央配置，生成器从固定源码和锁文件构建。保留四种 ABI 与 F-Droid 补丁，移除旧生成器命令、依赖降级及保存/重置整个工作区的桥接旁路。

## 验证与限制

工具测试包含 SDK/镜像值漂移、打包前置步骤失败、源码生成器安装失败、平台矩阵与 DRM 回归约束。工具层模拟测试和配置检查不能替代完整平台编译。

常规 Linux 与 Apple 原生验证实际调用新的打包前置入口。精确结果以 PR #1 对应提交的 Actions 运行和报告为准；配置包含步骤不代表执行成功。未运行的完整矩阵不计通过。

Android AGP/Gradle/Kotlin/JDK/NDK/cargo-ndk、Sciter ABI/旧系统路径、Windows 原生包、iOS 完整编译、GPU/DRM 设备会话、Web、商店发布与回退仍有剩余工作。保留的 Sciter 老工具链不能称为已迁移；本轮没有通过关闭这些能力冒充全量升级。Dependency review 的仓库 Dependency graph 设置阻塞仍保留。

## 版本来源

- Xcode 稳定版：Apple App Store Xcode 发布记录。
- runner/SDK/build：actions/runner-images 的 xcode-27-arm64-Readme.md；来源保存在 configs/toolchain.json。
- Flutter 3.47.5：官方 tag 对应提交 6a19cca56475dbfba1478ee68d7bd0c2ef891da1；通用 SDK 校验也检查该提交。
