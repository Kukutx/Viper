# Viper agent 入口

Viper 是基于 RustDesk 的 Rust / Flutter 远程桌面项目，不是 Web 后端。未经明确要求，不改变 AGPL 许可、上游署名、协议身份、应用标识、系统权限或签名身份。

## 真源与路径

| 范围 | 先读 |
| --- | --- |
| 工具版本与升级目标 | `configs/toolchain.json` |
| 目录边界、迁移状态、验收条件 | `docs/engineering/foundation.md` |
| 本地命令、CI/CD、发布验证 | `tools/README.md` |
| Rust、异步、平台实现、本地化 | `docs/engineering/rust-guidelines.md` |
| 原生依赖 | `Cargo.toml`、`Cargo.lock`、`vcpkg.json`、`.gitmodules` |
| Flutter 依赖 | `flutter/pubspec.yaml`、`flutter/pubspec.lock` |

## 工作规则

- 唯一 agent 入口是小写单数 `agent.md`；不新增 CLAUDE.md、AGENTS.md 或重复入口。
- 保留与当前任务无关的工作区改动。使用任务分支；不强制推送、不擅自合并或执行生产发布。
- 工具版本固定到核验过的稳定版本。依赖迁移必须同步 manifest、lockfile、生成代码和相关测试。
- 不把维护过的平台 fork 直接替换成同名公共包；先核对具体补丁和回归影响。
- 不通过禁用测试、删除功能、忽略错误或增加依赖覆盖来伪造迁移通过。
- 不暴露密钥，不让 PR 构建获取签名凭据；生产部署单独授权。
- 本次用户明确要求的版本迁移允许必要的协同重构；原工程指南中的 Rust、Tokio、本地化和回归检查规则继续生效。
- 交付时分别报告配置检查、依赖解析、编译、测试、签名和部署的实际结果；未执行的项目不能标为通过。
- 当前任务的连接器访问仅限 GitHub，不使用其他连接器或远程开发网关。
