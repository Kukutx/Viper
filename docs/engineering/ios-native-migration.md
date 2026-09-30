# iOS 原生迁移与验收

本次协同迁移采用中央配置的 Xcode 27 / iPhoneOS SDK 27 和最低 iOS 15.0。最低系统是构建目标，不代表已完成真机验收。

## 源码与依赖

- `AppDelegate.swift` 将插件注册移到 `FlutterImplicitEngineDelegate`，`Info.plist` 显式使用 `FlutterSceneDelegate`。保持单场景、应用 ID、entitlements、原有系统权限和由 `app_links` 处理深链接的行为。
- iOS 插件改由 `FlutterGeneratedPluginSwiftPackage` 链接，移除 Podfile、Podfile.lock、Pods build phases 和失效的手工插件 framework flags；保留系统 framework、Rust archive 的三配置 force-load，以及公开 C ABI。macOS 的定制 CocoaPods 插件不受此 iOS 迁移影响。
- 恢复上游 AppIcon / LaunchImage 原始 PNG，18 个 blob 身份记录在 `configs/ios-resources.json`。上游资源树为 `cbde719c65daefdaeb2b95ade76130828b9ae772` 和 `fc352403270a2b22d030aaa76fabdce37c30c49a`（rustdesk/rustdesk）；保持原许可和署名。
- `libs/scrap/build.rs` 在 iOS 打包 libyuv 所需 JPEG 静态库；新的 arm64-ios triplet 将设备最低系统限定在目标构建中，防止污染 macOS host tools。
- `default-net 0.14.1` 迁为固定 `netdev 0.46.3` 并同步 Cargo.lock。关闭未使用的默认扩展（网关、Apple 额外系统配置、Android Java 额外元数据），不移除接口枚举。`src/lan.rs` 只适配 IP 地址访问 API，保留 WOL、MAC 匹配、广播套接字策略、iOS OS-selected 路由和协议消息。

## 验证入口

```sh
python -m pip install -r tools/requirements-dev.txt
bash tools/native/setup-ios.sh
source tools/.reports/ios-native.env
bash tools/native/build-ios.sh
```

该入口要求 Apple Silicon macOS 和精确的 Xcode / SDK，不安装或执行 CocoaPods。使用完整 vcpkg manifest、`cargo build --locked --features flutter,hwcodec` 和 `flutter build ios --release --no-codesign --no-pub`。构建后检查静态 Rust / FRB 导出符号、arm64 架构、应用 ID、最低系统、SDK、Flutter 资源、已提交工程无改写和无新增未提交原生配置。

`ios-native.yml` 在 Draft PR 执行只读验证，无签名凭据；仅成功后归档未签名 Runner.app，并记录提交与 SHA-256 清单。`test_ios_native.py` 使用假二进制/检查器来测试拒绝路径，不能当作真实 iOS 编译或设备执行。Linux 的 `tests/network_interfaces.rs` 验证 host 地址、MAC 文本和实际本机接口枚举，不发送 WOL 或广播包。

每次构建的完成状态以该提交的 Actions 结果为准。未签名设备包、静态符号检查不能证明 iPhone 真机启动、后台/前台切换、扫码、深链接、网络发现、硬件解码、跨设备远控或安装回退。没有签名、公证、商店发布或生产部署。

参考：Flutter 官方 UIScene adoption 与 Swift Package Manager for app developers；netdev `v0.46.3` 的 Cargo features 和公开 API。历史准备分支产物不是最新任务提交的构建成功证据。
