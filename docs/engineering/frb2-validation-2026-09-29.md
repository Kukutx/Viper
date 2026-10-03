# Flutter / FRB 2 验证记录

本记录描述实际执行过的 Linux 验证，不代表所有平台或所有依赖迁移完成。

## 精确证据

- [GitHub Actions 运行 36630942301](https://github.com/Kukutx/Viper/actions/runs/36630942301)，job `109619694008`，结果 success。
- 运行源提交：`c1ba1d86c7d4bc9037441dfb29db9d1b60ff9162`。
- 隔离工作树中只修正了六处新增事件流诊断的 `hbb_common::log` 路径，然后生成绑定、编译及测试。
- 导出的已测试候选提交：`4314d8fc5c6a45a4a202325cdf474d8a897bfa4d`；树 `962f375ea0da9ec0676dd19f4f457858d2e7d0a7`。该源码树由 GitHub 连接器用于最终提交，不依赖本地机器的未提交状态。
- Artifact `11063040392` 的 SHA-256：`6de4693ec9d727f3f27889e16f1355ba6bd0d10dc848c8bc35a114c2160506a5`。证据包包含完整分析/编译/测试日志、源码快照和对应 Git 对象清单；artifact 有保留期限，不能作为配置真源。

## 已通过

| 检查 | 实际结果 |
| --- | --- |
| Python 工具测试 | 35 项通过，包含 11 项桥接版本和下载归档校验测试 |
| Flutter 锁文件 | `flutter pub get --enforce-lockfile` 通过 |
| 绑定生成 | FRB 2.13.0 校验版本与 SHA-256 后生成成功，锁文件未被静默修改 |
| Dart 分析 | 0 error、0 warning；仍有 926 条 info，完整保留，没有关闭规则 |
| Flutter 回归 | `flutter test --no-pub test`：103 项全部通过，包括原光标逐字节断言和 5 项截图保存测试 |
| Rust 编译检查 | `cargo check --locked --lib --features flutter,linux-pkg-config` 通过 |
| 真实动态库 | `cargo build --locked --lib --features flutter,linux-pkg-config` 通过，产出 Linux `liblibrustdesk.so` |
| 真实 FFI | Dart 加载上述动态库：2 项测试通过，同步/异步应用标识一致、异步版本读取有效 |

本次 native build 仍有 45 条 root crate warning；不能据此宣称 Clippy 或无警告构建通过。构建为 dev profile，不是已签名的生产安装包。

## 收敛与剩余限制

最终改动保留上述源码，移除一次性迁移脚本和具有 contents:write 的候选导出工作流；新增 `flutter-validate.yml` 常规只读 CI，加入再生成无差异检查。最终 PR 的新检查需查看对应提交的 Actions 结果，不把此前运行编号冒充新运行。

旧发布矩阵、Android 构建栈、Apple 静态链接、Sciter 兼容路径及原生依赖 major 仍待迁移。没有验证跨设备远控、GPU 编码、完整平台安装包或生产部署。Dependency review 的仓库 Dependency graph 设置阻塞仍需解决。
