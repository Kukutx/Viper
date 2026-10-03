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
# 私有虚拟声卡回归需要额外的测试服务，不使用真实音频设备。
sudo apt-get install -y pulseaudio pulseaudio-utils
bash tools/native/test-pulsectl.sh
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

Linux 原生 setup 会安装开发系统包，因此需要 sudo；支持 Linux x86_64 与 aarch64，并分别使用对应的 libyuv triplet。上面的 Debug / 生成器完整验证入口仍为 x86_64。生成器下载支持已登记的 Linux、macOS、Windows 主机，但这不表示相应应用构建已验证。

macOS Apple Silicon 的原生环境入口为 `bash tools/native/setup-macos.sh`，随后加载 `tools/.reports/macos-native.env`；当前原生基线为 macOS 12.3。Apple 显式 C ABI、动态/静态链接、Swift Package Manager 与原生验证边界见 [Apple 迁移说明](../docs/engineering/apple-native-migration.md)。不再使用占位的 FRB 1 C header 或 dummy bundling 函数。

`generate` 验证 Flutter/Dart 版本和锁文件，禁止生成器静默升级依赖。绑定位于 `src/bridge_generated.rs`、`flutter/lib/generated/`。`analyze_flutter.py` 解析平台上的 Dart 可执行路径并保留 UTF-8 完整诊断；错误与警告使检查失败，信息级弃用提示仍在报告内。

## CI 层次

- `foundation.yml`：配置、工具测试、工作流检查及 Rust `base` / `hbb_common` 核心测试。
- `flutter-validate.yml`：Draft PR 也执行，检查可复现绑定（包括未跟踪的新增生成文件）、Flutter 分析和测试、Linux Rust 库、真实 FFI 和 Debug 桌面包；没有仓库写入或发布权限。
- `linux-release.yml`：Linux x64/arm64 原生 Release 应用、全部包内 ELF 架构与动态库检查、真实 FFI 和未签名归档；不替代 Debug、DRM 或发行格式验收。
- `bridge.yml`：复用唯一验证链，成功后导出同一提交的 FRB 2 绑定；所有消费者使用唯一 `bridge-artifact`，没有旧 SDK 专用产物、FRB 1 生成器或源码补丁。
- `flutter-platform-tests.yml`：Windows x64 和 macOS runner 使用相同中央 SDK、同一 pub 锁文件和全部 `flutter/test` 测试；没有 Rust 原生库构建或签名步骤，不能当作平台安装包验证。
- `apple-native.yml`：macOS arm64 Rust Release 库、Flutter Debug/Release 应用、包内真实 FFI、Pods 严格锁定和工程无差异；不签名、公证或发布。
- `windows-native.yml`：Windows x64/arm64 原生 Release 应用、包内 FFI、库/架构一致性及未签名归档；当前仅 software-codec profile。
- `android-native.yml`：三 ABI 的真实原生库和未签名 APK，保留 hwcodec；检查应用元数据和 16 KiB 对齐，不冒充真机执行。
- `ios-native.yml`：SwiftPM 的 Release 应用、XCArchive 与静态库导出验证，使用 Rust 匹配的 LLVM 工具；无签名 IPA 或设备执行。
- `ci.yml` / `flutter-ci.yml` / `flutter-build.yml`：完整历史平台与发行配置。SDK/FRB 和 Android/iOS 入口已收敛，Sciter、特殊架构及发行格式仍需验收；Draft 跳过不计通过。
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

## 打包入口与版本收敛

`python tools/prepare_flutter.py` 在打包前检查真实 SDK 版本/提交、FRB 版本、已提交生成文件和严格锁文件。`build.py` 的四个 Flutter 打包入口（含 `--skip-cargo`）均调用它，随后使用 `--no-pub`；不再 sed 修改旧生成文件。

`python tools/viper.py versions --write` 同步 `.github/workflows/flutter-build.yml` 的 Rust、Flutter、CMake 与 vcpkg 镜像值；`check` 会拒绝漂移。`tools/native/install-flutter.sh` 只在不存在的绝对路径安装官方固定提交，原生支持 Linux x64/arm64；不覆盖已有 SDK。

F-Droid 使用同一 SDK 和固定 NDK/cargo-ndk，`python tools/bridge.py generate --from-source` 从源码编译固定生成器；失败不会回退到预编译文件。Android Gradle/NDK 已迁入新版本，但 F-Droid 四 ABI 与定制 x86 engine 的完整产物仍未验收。

macOS 验证显式选择中央配置的 Xcode 版本、build ID、SDK 和 CocoaPods，分别验证 Debug 与 Release 包内 FFI；Release 归档及清单是未签名 CI 产物，不是可直接发布的安装包。GitHub `xcode-27` runner 目前标为预览，独立记录，不能把 runner 标签当成 SDK 版本验证。范围见 `docs/engineering/build-entry-convergence.md`。

## 平台原生入口

Linux x64 / arm64 主机准备固定 Flutter/Dart/Rust 后，可执行 `bash tools/native/setup-linux.sh`、`source tools/.reports/native.env`、`python tools/linux_release.py`。检查通过后生成 `dist/linux-<arch>-unsigned/`，保留可执行位和安全的相对链接；已有产物目录不会被覆盖。该入口使用 software-codec profile，不表示硬件编解码、GUI、安装包格式或生产部署已验收。详见 [Linux Release 验证](../docs/engineering/linux-release-validation.md)。

Android 与 Linux Release CI 先运行 `python tools/ci_rust.py`：在 runner 临时目录安装并核验中央 Rust pin、rustfmt 和 Clippy，通过后才导出环境。它不改用户全局 Rustup/Cargo 目录，不降级、不移除组件；本地开发不调用这个 CI 专用入口。详见 [Rust 安装隔离](../docs/engineering/ci-rust-isolation.md)。

Android 的版本、wrapper 校验值和最低 API 24 位于 `configs/toolchain.json.android`。Linux x64 上先准备固定 JDK/Flutter、`ANDROID_HOME` 和工作流列出的系统开发包，再执行：

```sh
python tools/android_toolchain.py --java-only
bash tools/native/install-android-sdk.sh
bash tools/native/build-android.sh arm64-v8a
```

其他官方 ABI 为 `armeabi-v7a`、`x86_64`。每个 ABI 使用独立、干净的构建工作区；脚本拒绝签名 key.properties 和旧产物混入。相机、后台服务、权限与 F-Droid 边界见 `docs/engineering/android-native-migration.md`。

iOS 在 Apple Silicon macOS 上使用已固定的 Xcode/Flutter/Rust：

```sh
bash tools/native/setup-ios.sh
source tools/.reports/ios-native.env
bash tools/native/build-ios.sh
```

该入口同时验证 Release 应用和 XCArchive，保留 11 个所需原生导出与 framework 相对链接；不会导出签名 IPA。它拒绝已有 archive/产物目录，重复构建应使用新的干净工作区。iOS 不依赖 CocoaPods；macOS 六个定制插件仍使用已锁定 Pods，不能混为一谈。

Windows 原生主机准备好固定 SDK 后，执行 `python tools/windows_native.py`、`python tools/package_windows.py`；环境、Visual Studio、LLVM、架构、锁文件和包内 FFI 会逐项验证。CI 的 SDK 安装入口是 `tools/install_windows_flutter.py`；不会覆盖已有目录。完整环境参数以 `windows-native.yml` 为准。

## 保留的 PulseAudio fork

`python tools/verify_pulse_vendor.py` 对照原 Git blob 校验源码、许可和限定替换。`bash tools/native/test-pulsectl.sh` 显式启用私有服务测试，在临时 Unix socket 和 cookie 下运行虚拟 null sink，测试完成或失败都只清理自身进程。普通 `cargo test --workspace` 不会因为这项新增集成测试要求用户正在运行音频服务；CI 会显式运行全部三个测试，不使用忽略或放宽断言。

## Linux Debian package

After the same-commit native Release build, `python tools/linux_deb.py` creates and verifies an unsigned `.deb` on Ubuntu 24.04 x64/arm64 (`dpkg-dev` required). It preserves the existing service, maintainer scripts, identities and runtime requirements, adds ELF-derived dependencies, verifies both archive trees and repeat serialization, and runs FFI against the extracted Rust library. CI never installs the package or starts its service. Output: `dist/linux-<arch>-deb-unsigned/`. See [Debian validation](../docs/engineering/linux-debian-validation.md) for the explicit DRM, hardware, installation and signing boundaries.

## 音频依赖回归

Windows/macOS 原生构建在打包前执行 `cargo test --locked --release --lib --features flutter audio -- --test-threads=1`，覆盖当前构建配置的缓冲、欠载恢复、争用和分配回归。Linux 在默认桌面包及 FFI 检查之后执行 `cargo test --locked --test rubato_dependency_contract --features flutter,linux-pkg-config,use_rubato`；默认 `use_dasp` 不变。版本来源、API 变化和设备验收边界见 [音频迁移说明](../docs/engineering/audio-dependency-migration.md)。
