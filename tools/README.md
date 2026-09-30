# Viper 工具入口

工具版本真源为 `configs/toolchain.json`；Actions SHA 真源为 `configs/actions-lock.json`。CI 使用 `.python-version` 的精确版本。先执行 `git submodule update --init --recursive`。

```sh
python -m pip install -r tools/requirements-dev.txt
python tools/viper.py check
python -m unittest discover -s tools/tests -v
python tools/viper.py env
python tools/viper.py inventory
python tools/viper.py inventory --latest
```

`inventory --latest` 只查询 crates.io / pub.dev，不修改依赖。清单区分 registry、Git fork、path、workspace 和 overrides；它不是兼容性证明。网络查询失败返回非零，不能当成已最新。

## 版本与绑定

```sh
# 先核验上游版本，再编辑中央配置。
python tools/viper.py versions --write
python tools/viper.py versions
python tools/viper.py actions --write
python tools/bridge.py check
python tools/flutter_sdk.py
```

`tools/bridge.py` 检查 Rust、Dart 与生成器的 FRB 版本一致，生成器二进制校验固定 SHA-256。更新 FRB 必须更新中央版本、下载校验和、Cargo/pub manifest、锁文件、两端生成代码和原生 FFI 回归；不手改生成文件。

`flutter_sdk.py` 在 Windows/macOS/Linux 上解析实际可执行路径，将首次启动日志与机器 JSON 分开保存，严格校验中央 Flutter/Dart 版本和 stable channel。`cargo_tools.py` 为生成器安装配置中固定的 `cargo-expand`，使用 `--locked` 和项目内 `.tools/cargo`，不替换用户全局 Cargo 工具。

Linux x86_64 的完整开发验证（使用配置中的 Flutter/Dart SDK）：

```sh
bash tools/native/setup-linux.sh
source tools/.reports/native.env
python tools/bridge.py generate
python tools/check_bridge_outputs.py
python tools/analyze_flutter.py
(cd flutter && flutter test --no-pub test)
cargo check --locked --lib --features flutter,linux-pkg-config
cargo build --locked --lib --features flutter,linux-pkg-config
(cd flutter && VIPER_NATIVE_LIBRARY="$PWD/../target/debug/liblibrustdesk.so" \
  flutter test --no-pub test_native/bridge_ffi_test.dart)
bash tools/native/build-linux-bundle.sh
```

`check_bridge_outputs.py` 检查全部必要 Rust/Dart 输出非空、非符号链接、已被 Git 跟踪，并且相对 HEAD 没有变化，包括已暂存改动和被 ignore 的新增生成文件。开发中有意重新生成的差异应先审查和提交，再执行此可复现性门禁；不能用手写绑定绕过。

`build-linux-bundle.sh` 在原生库和锁文件依赖已准备好后编译 Linux Debug 桌面包，检查可执行文件、资源、包内 Rust 库与 Cargo 输出的一致性及动态链接依赖，再从包内库执行真实 FFI 测试。任何一步失败都返回非零；日志写入 `tools/.reports/bundle-*.log`。它不启动桌面会话、不验证远程连接，也不生成生产安装包。

Linux 原生 setup 会安装开发系统包，因此需要 sudo；它只支持 Linux x86_64。生成器下载支持已登记的 Linux、macOS、Windows 主机，但这不表示相应应用构建已验证。

macOS Apple Silicon 的原生环境入口为 `bash tools/native/setup-macos.sh`，随后加载 `tools/.reports/macos-native.env`；当前原生基线为 macOS 12.3。Apple 显式 C ABI、动态/静态链接、Swift Package Manager 与原生验证边界见 [Apple 迁移说明](../docs/engineering/apple-native-migration.md)。不再使用占位的 FRB 1 C header 或 dummy bundling 函数。

`generate` 验证 Flutter/Dart 版本和锁文件，禁止生成器静默升级依赖。绑定位于 `src/bridge_generated.rs`、`flutter/lib/generated/`。`analyze_flutter.py` 解析平台上的 Dart 可执行路径并保留 UTF-8 完整诊断；错误与警告使检查失败，信息级弃用提示仍在报告内。

## CI 层次

- `foundation.yml`：配置、工具测试、工作流检查及 Rust `base` / `hbb_common` 核心测试。
- `flutter-validate.yml`：Draft PR 也执行，检查可复现绑定（包括未跟踪的新增生成文件）、Flutter 分析和测试、Linux Rust 库、真实 FFI 和 Debug 桌面包；没有仓库写入或发布权限。
- `bridge.yml`：复用上述唯一验证链，成功后从同一提交导出已跟踪的 FRB 2 绑定。不再安装 FRB 1、降级依赖或补丁修改源码。为保持现有下载接口，两个历史 artifact 标签暂时保留，但内容完全相同，均不代表旧 SDK 兼容性；不导出旧 C header。
- `flutter-platform-tests.yml`：Windows x64 和 macOS runner 使用相同中央 SDK、同一 pub 锁文件和全部 `flutter/test` 测试；没有 Rust 原生库构建或签名步骤，不能当作平台安装包验证。
- `apple-native.yml`：只读、无签名凭据，单独验证 macOS arm64 Rust Release 库、Flutter Debug 桌面包、包内真实 FFI 和项目无隐式改写。原生项目和依赖解析证据保存在报告中；iOS 只检查链接配置与 C ABI，不冒充完整 iOS 构建。
- `ci.yml` / `flutter-ci.yml` / `flutter-build.yml`：历史完整平台矩阵的 SDK、Apple 旧 C header 消费和兼容补丁仍需继续迁移。共用桥接流程更新不等于整个发布矩阵已可用；Draft 阶段跳过的任务不能算作通过。
- `dependency-review.yml`：需要启用 GitHub Dependency graph。设置缺失时保留失败，不降低审查级别。

核心库可单独验证：

```sh
cargo metadata --locked --format-version 1
cargo test --locked -p base -p hbb_common --lib
```

Linux Debug 包和 FFI smoke test 不验证 GUI 启动、硬件编码、跨设备连接、Windows/macOS/Android/iOS 原生构建或真机。新增配置中的步骤必须有对应提交的实际 CI 结果，才能标为通过。具体剩余范围见 `docs/engineering/foundation.md`。

## 构建镜像与发布

Dockerfile 提供原生开发环境，不是面向公网的服务。镜像本身不包含 Flutter SDK、源代码或应用安装包；挂载仓库后使用已提交绑定还需要安装平台原生依赖。

```sh
docker build --build-arg BUILDER_UID="$(id -u)" \
  --build-arg BUILDER_GID="$(id -g)" -t viper-builder .
docker run --rm -v "$PWD:/workspace" viper-builder test --locked -p base -p hbb_common --lib
```

`build-environment.yml` 在 PR 中只验证镜像。仅 main 手动启动并显式选择 publish 才发布 GHCR 构建镜像，附 SHA 标签、SBOM 与 provenance。管理员仍需配置 `build-images` 环境审批；仅声明环境名称不等于审批已生效。

```sh
python tools/viper.py manifest dist --revision "$(git rev-parse HEAD)"
python tools/viper.py verify dist
```

产物清单拒绝空目录、符号链接、路径穿越、重复、缺失或额外文件；SHA-256 校验不等于签名验证。应用发布必须另外完成平台签名、来源证明、安装回归与回退演练。

`tools/.reports/` 是可丢弃证据目录，不存放凭据或唯一配置。此次迁移没有执行应用签名、商店发布或生产部署。
