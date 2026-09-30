# Windows 原生验证

`windows-native.yml` 在 PR（包括 Draft）、main 和手动运行时执行 x64 / ARM64 原生构建。使用中央 Flutter/Rust/CMake pin、Visual Studio 2026 稳定主版本与固定 LLVM 23.1.2；LLVM 归档采用已核对的上游 SHA-256。`windows_native.py` 选择本机 C++ 工具环境，不安装全局 LLVM、不修改签名身份。

验证链：固定 vcpkg 提交及软件编解码依赖 → SDK/桥接/锁文件门禁 → Rust Release DLL → Flutter Release 桌面目录 → PE 架构、资源、包内 DLL 与 Cargo 输出一致 → 包内库真实 FFI → 跟踪文件无隐式变化。报告保留在 GitHub Actions，任何步骤失败都保留非零状态。

此流程没有发布、签名、驱动安装、服务安装或生产密钥，也不替代硬件编解码、MSI/便携封装、远控会话或真机验收。既有完整 Windows 发布任务及硬件能力仍保留；新流程的配置和工具单元测试不等于原生构建成功。精确提交和运行结果以 PR 中的实际记录为准。

本机使用需要原生 Windows x64/ARM64 Python、中央 Flutter/Rust 版本、Visual Studio 2026 C++ 工作负载和联网环境：

```powershell
python -m pip install -r tools/requirements-dev.txt
python tools/windows_native.py
```

工具使用新的项目 LLVM / 临时 vcpkg 目录；拒绝覆盖已有目录，避免丢弃本机修改。上游来源：LLVM `llvmorg-23.1.2` release、GitHub runner-images 的 Windows2025-VS2026 与 Windows11-VS2026-Arm64 软件清单。
