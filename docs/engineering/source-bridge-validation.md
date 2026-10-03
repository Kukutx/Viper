# 源码桥接与 F-Droid SDK 入口

本说明补充 `build-entry-convergence.md`。配置真源为 `configs/toolchain.json`；步骤配置不等于实际运行通过。

## 固定源码生成器

Linux 开发环境执行：

```sh
python -m pip install -r tools/requirements-dev.txt
bash tools/native/setup-linux.sh
source tools/.reports/native.env
python tools/bridge.py generate --from-source
python tools/check_bridge_outputs.py
git diff --exit-code HEAD -- Cargo.lock flutter/pubspec.yaml flutter/pubspec.lock
```

`--from-source` 通过 `cargo install --locked` 构建配置中的精确 FRB 版本，并核对实际生成器版本；失败不回退到预编译生成器。普通生成保留校验 SHA-256 的预编译工具。两条路径都必须保持已提交的绑定、manifest 和锁文件无差异。

`.github/workflows/bridge-source.yml` 在相关 PR 改动时实际运行源码编译、绑定生成与一致性校验。该任务只有 contents:read，无发布凭据，失败不能被忽略。它不构建 Android APK，也不替代各平台原生库或真机测试。

## F-Droid SDK 准备

`flutter/build_fdroid.sh` 使用 `tools/native/prepare-fdroid-flutter.sh`。新 SDK 目录由固定官方 tag/commit 安装；现有目录必须已经处于固定提交且没有已跟踪文件改动。此时选择或创建指向相同提交的本地 stable 分支，让渠道检查与固定版本一致。

不同版本、符号链接、已有 stable 分支指向其他提交、未提交修改或安装失败均使步骤失败。脚本不 reset 现有 SDK、不丢弃用户修改、不覆盖其他 stable 分支。需要更换 SDK 时使用新的空目录。

对应测试使用真实临时 Git 仓库验证上述行为，Flutter 可执行文件为测试替身。源码生成器是否真实编译成功，以 bridge-source 对应提交的 Actions 日志为准，不能把工具测试视作实际 SDK 构建。

## 剩余验收

F-Droid 仍需 Android Gradle/NDK、四种 ABI、定制 x86 engine、包体与设备回归验收。历史全平台构建矩阵已统一 Flutter 版本声明，但 Sciter、平台原生依赖与发布工具仍有迁移工作；当前不得据此合并为完整发布基线。
