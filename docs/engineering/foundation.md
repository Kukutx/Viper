# Viper 底座与迁移状态

核对日期：2026-09-29。导入基线：`d6c0376fd3cc14a64987c1a02f84c576cdcc83bf`。

## 当前边界

| 路径 | 职责 |
| --- | --- |
| `src/` | Rust 客户端、远程控制、会话和服务生命周期 |
| `src/server/`、`src/platform/` | 音视频、输入、网络和系统适配 |
| `flutter/` | 当前桌面端和移动端 UI |
| `src/ui/` | 尚未完成迁移的 Sciter UI |
| `libs/hbb_common/` | 与服务端共享的协议、连接、配置；固定 Git 子模块 |
| `libs/base/` | 客户端协议、文件传输、配置键；不要放入共享子模块 |
| `libs/scrap/`、`libs/enigo/`、`libs/clipboard/` | 采集、输入、剪贴板 |
| `configs/`、`tools/` | 工具版本真源、可测试的自动化入口 |
| `.github/workflows/` | 验证、构建与发布编排 |

参考 AppPlatform 的最小 agent 入口、配置真源、工具入口和验证/发布分离方式；不引入其业务后端、支付、云数据库或凭据。Viper 是桌面/移动客户端，构建镜像不是可直接部署的远程桌面服务。

## 已确认的问题

- 导入提交存在 `.gitmodules` 声明，但没有 `libs/hbb_common` Gitlink，不能仅靠 recursive checkout 恢复工作区。
- CI 的 push 分支仍指向 `master`，而本仓库使用 `main`。
- Flutter 构建混用 3.22、3.24 和 3.44；Rust 混用 1.75、1.81、旧 nightly 和 stable。
- FRB 固定 1.80.1，Rust 使用 `SyncReturn`、`StreamSink`，Dart 使用旧生成绑定；升级 2.x 必须成套迁移。
- 原 Dockerfile 使用旧 vcpkg、下载 Sciter、关闭部分 TLS 校验，且 entrypoint 重新拆分参数。
- Android 仍保留旧插件 namespace/JVM 兼容配置；不能在插件替换前直接删除。

## 本次底座变更

`agent.md` 为唯一入口；原工程规则保留在本文同目录，不丢失。恢复 hbb_common 到固定 revision；新增集中版本配置及 Rust、Flutter、Python 选择器。工具和工作流的实际验收结果见 PR，不把历史机器上的测试结果冒充当前提交的 CI。

## 迁移验收清单

| 项目 | 必须满足的条件 |
| --- | --- |
| Rust / 原生依赖 | 所有 workspace 和目标平台编译，锁文件可复现；逐个审查 fork 补丁和 major API |
| FRB 2.x | Rust API、Dart API、两端运行时、codegen 版本一致；重新生成绑定；会话、视频帧、输入、剪贴板、文件传输回归 |
| Flutter | 所有平台采用一个 SDK；移除构建时源码补丁；分析、单测和平台构建通过 |
| Android | 插件 API、Gradle、AGP、Kotlin、JDK、NDK 一起验证；真机权限、后台服务和签名安装测试 |
| Sciter / 旧系统 | 先迁移能力和启动/服务路径，再删除旧代码与依赖；不能以取消功能伪装迁移 |
| CI/CD | PR 无生产凭据；构建与发布分离；固定 revision、产物清单、SHA-256、签名与回滚说明 |
| 最终升级完成 | manifest、lockfile、生成代码、运行时和发布矩阵全部一致；`configs/toolchain.json` 不再存在 pending 项 |

**现在仍不是“所有依赖和兼容代码已迁移完成”。** `.fvmrc` 指定迁移 SDK，不代表旧发布工作流已统一。FRB、原生 major、Android 和 Sciter 的剩余工作必须通过上述验收，不做纯版本号替换。

## 回归范围

本次仅调整 agent 路由、工具版本选择、缺失的共享子模块和工程自动化；不改远程控制协议、加密语义、业务标识、签名身份或本地化。每次后续迁移必须在 PR 列出实际改变的运行时路径和验证结果。
