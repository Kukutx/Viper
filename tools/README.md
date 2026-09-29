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
```

`tools/bridge.py` 检查 Rust、Dart 与生成器的 FRB 版本一致，生成器二进制校验固定 SHA-256。更新 FRB 必须更新中央版本、下载校验和、Cargo/pub manifest、锁文件、两端生成代码和原生 FFI 回归；不手改生成文件。

Linux x86_64 的完整开发验证（使用配置中的 Flutter/Dart SDK）：

```sh
bash tools/native/setup-linux.sh
source tools/.reports/native.env
python tools/bridge.py generate
python tools/analyze_flutter.py
(cd flutter && flutter test --no-pub test)
cargo check --locked --lib --features flutter,linux-pkg-config
cargo build --locked --lib --features flutter,linux-pkg-config
(cd flutter && VIPER_NATIVE_LIBRARY="$PWD/../target/debug/liblibrustdesk.so" \
  flutter test --no-pub test_native/bridge_ffi_test.dart)
```

原生 setup 会安装开发系统包，因此需要 sudo；它只支持 Linux x86_64。生成器下载支持已登记的 Linux、macOS、Windows 主机，但这不表示相应应用构建已验证。其他目标的系统依赖、静态链接和打包继续使用其平台工程并完成迁移。

`generate` 验证 Flutter/Dart 版本和锁文件，禁止生成器静默升级依赖。绑定位于 `src/bridge_generated.rs`、`flutter/lib/generated/`。`analyze_flutter.py` 保留全部诊断；错误与警告使检查失败，信息级弃用提示仍在报告内。

## CI 层次

- `foundation.yml`：配置、工具测试、工作流检查及 Rust `base` / `hbb_common` 核心测试。
- `flutter-validate.yml`：Draft PR 也执行，检查可复现绑定、Flutter 分析和测试、Linux Rust 库编译及真实动态库 FFI 调用；没有仓库写入或发布权限。
- `ci.yml` / `flutter-ci.yml` / `flutter-build.yml`：历史完整平台矩阵仍需继续统一 SDK 和移除旧兼容补丁。Draft 阶段跳过的任务不能算作验证通过，当前 PR 不应转为可发布基线。
- `dependency-review.yml`：需要启用 GitHub Dependency graph。设置缺失时保留失败，不降低审查级别。

核心库可单独验证：

```sh
cargo metadata --locked --format-version 1
cargo test --locked -p base -p hbb_common --lib
```

Linux 库和 FFI smoke test 不是完整客户端、硬件编码、Windows/macOS/Android/iOS 构建或真机测试。具体剩余范围见 `docs/engineering/foundation.md`。

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
