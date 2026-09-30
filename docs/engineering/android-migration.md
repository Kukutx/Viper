# Android 工具链迁移候选

候选使用 AGP 9.4.0、Gradle 9.8.0、Temurin 27+35、NDK 30.0.16248370、API 37、Java 编译目标 17、Protobuf Gradle 插件 0.10.0 与 Java runtime/protoc 4.36.2。版本、Gradle 分发及 wrapper 校验值在 `configs/android-toolchain.json`。真实 Gradle wrapper 从校验过的分发生成，不手写二进制。应用身份及 release 签名来源不变；最低 Android 目标由 22 提升至 24，旧系统不再是这一候选的构建承诺。

`codex/viper-android-modernization` 是隔离候选，不等于主迁移 PR 已采用，候选 CI 的显式 QR/锁文件生成也不能作为常规验证流程保留。`qr_code_scanner_plus` 保留 ZXing/AVFoundation 实现和原扫码流程，不引入 ML Kit；新版 QRView 自动释放控制器，移除旧的无效 dispose 调用。必须审查精确 pub 锁文件变化并提交后，才能接入只读、禁止隐式依赖更新的正式验证。

## 已确认与剩余边界

候选 head `9c59c6426f46f966f58af554e9126b6ca9005095` 的运行 `36735624743` 已实际安装 NDK r30、验证 Gradle 9.8 分发/wrapper 校验和、运行 Temurin 27+35，并完成 103 项 Flutter 测试、分析 0 error / 0 warning / 926 info；随后 Android 构建失败于 Flutter Gradle 插件的 `AbstractAppExtension` 强制转换。不能把候选整个 job 记作成功。

Flutter 3.47 支持 `android.builtInKotlin=true`，但该 SDK 的 Gradle 插件尚未完全迁移新 AGP DSL。因此显式使用 `android.newDsl=false`；这是上游依赖的未完成迁移，不是版本降级，也不能声称旧兼容配置已清零。保留内置 Kotlin，不恢复旧 KGP 或强制 Kotlin 1.9.10。后续官方稳定 Flutter 完成新 DSL 迁移后，需要通过实际 Android 构建再移除这一项；禁止修改 SDK 源码或忽略编译错误。

来源：
- https://docs.flutter.dev/release/breaking-changes/migrate-to-built-in-kotlin
- https://github.com/flutter/flutter/issues/180137
- https://github.com/flutter/flutter/blob/3.47.5/packages/flutter_tools/gradle/src/main/kotlin/FlutterPlugin.kt

候选当前只检查 Gradle/Android 插件与协议类生成，不构成 Rust 原生库、完整 APK 启动、16 KB 页对齐、模拟器、真机或签名发布的验收。所有这些检查仍需补齐；不会以缺失 Rust 库的 APK 冒充可用客户端。正式发布和生产签名均未执行。
