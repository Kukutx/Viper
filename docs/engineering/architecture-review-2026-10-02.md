# Viper 架构与交付复核

复核基线：`f91bf7ef0c26339ff045f251beef35d3bf54d4bc`，日期：2026-10-02。
本文是针对构建、交付边界、依赖和代表性运行路径的工程审查，不是所有源码、漏洞、许可证或设备功能均已验收的证明。版本真源仍为 `configs/toolchain.json`，唯一规则入口仍为 `agent.md`。下面明确区分本次修复与待实施设计。

## 结论

保留 Rust / Flutter 和现有模块边界，不引入微服务、Kubernetes、第二套构建框架或大规模目录重命名。当前首先需要解决的是双轨交付、隐式网络回退和验证证据不一致；继续机械升级版本或增加脚本不能代替这些工作。建议先收敛交付链和失败契约，再逐个替换旧平台能力，最后做内部模块拆分。

## 已复核的事实

- 基线的 Foundation、Flutter 平台、桥接及源码生成器、Linux Debug/Release/DEB、macOS、Android、iOS、构建镜像检查均已成功；历史完整发行矩阵仍因 Draft 跳过，不能计为成功。
- Windows 运行 [37054791846](https://github.com/Kukutx/Viper/actions/runs/37054791846)：x64 job `110996717923` 成功；arm64 job `110996718287` 的编译、测试、包内 FFI、封装和产物上传成功，但整个 job 在 Rust 缓存收尾阶段被取消。因此整条运行仍不是成功。
- arm64 的完整日志显示：19:38:46Z 开始，20:30:37Z 已完成产物上传，20:35:50Z 报告 Rust 缓存约 2,556,094,341 字节，20:39:01Z 取消。时间线与原 60 分钟 job 预算耗尽一致；不能将缓存收尾问题报告为应用编译失败。
- 重新执行 [Dependency review 37054791735](https://github.com/Kukutx/Viper/actions/runs/37054791735)，第二次 attempt 的 job `111045700344` 成功。此前 Dependency graph 设置阻塞已解除，没有修改检查或降低 `high` 门槛。
- 该成功仅说明本次依赖差异未检出 high 或更严重的已知漏洞，不是整个依赖树的完整安全证明。日志仍有 14 条未识别许可证的依赖声明，不代表这些包没有许可证。

## 本次修复：Windows 验证与产物边界

`.github/workflows/windows-native.yml` 按实测区分 x64 / arm64 预算：job 为 75 / 90 分钟，原生构建步骤为 55 / 65 分钟，为 SDK 准备、上传和缓存收尾留出空间。不增加无限重试，不把取消改成成功，不忽略构建失败。缓存键增加实际定义 vcpkg 包集合的 `tools/windows_native.py`，避免安装配置改动后仍误用相同键。这是有界稳定性调整，不是所有网络卡顿均已解决的承诺。

`tools/windows_native.py` 原来只检查三个主 EXE/DLL。现在递归检查全部 EXE/DLL 的 PE 架构和 SHA-256，拒绝符号链接、目录 junction 和特殊文件；将原生二进制清单保存到既有验证报告。`tools/package_windows.py` 封装前重新核对清单，阻止插件被替换、增加、遗漏，或缺少新验证证据时仍打包。

音频和 Windows 依赖测试仍使用原命令，但不再仅接受 Cargo 的退出码：必须有完整的 libtest 开始/结束记录，分别至少 48 / 9 项通过，失败、忽略和未完成执行均拒绝，允许以后增加测试。数量下限只用于发现空跑和明显缺失，不代替用例的语义审查；Rust 输出格式变化应显式迁移解析器，不能默认通过。

本次没有修改 Rust/Dart/Swift 业务、Cargo/pub 锁文件、依赖版本、协议、许可、权限、签名身份或发布授权。未改变 Windows 的 software-codec profile。检查所有 PE 架构不等于解析所有 DLL 导入、验证 Flutter AOT ELF、执行插件 GUI、硬件编码或驱动安装；文件摘要也不是签名或完整对抗性安全边界。

新增 20 项工具回归覆盖实际校验器的成功及失败路径，包括错误插件架构、链接目录、插件篡改、空跑/少跑/忽略测试、报告缺失、原封装成功路径和工作流预算。它们不冒充 Windows 原生执行。

### 独立复核的基线产物

| 证据 | Artifact ID | ZIP SHA-256 |
| --- | --- | --- |
| arm64 完整诊断 | 11251050584 | `c5929f7c0ec092a153a49d30ffa868305c23d601afd93027c02970a1420d4273` |
| arm64 未签名应用包 | 11250950765 | `df57653747e32f73d144a9e9c353652918810770ca56e182f02990952ceb1f46` |

两份 ZIP 均下载并校验。诊断的 checkout 为 `5762c5143091bb20b3cd8e10aad9010ecd2b7255`，包含 48 项音频与 9 项注册表/服务依赖测试，均为 0 failed、0 ignored。使用本次新校验器静态复核实际包内全部 15 个 EXE/DLL，均为 arm64；Rust 库与原报告中的摘要一致。这是旧构建产物的重新检查，不是本次提交的重新编译或真机测试。新提交的完整 CI 结论应在 PR 中单独记录。

## P1：发布必须只有一个放行点（待实施）

基线 `.github/workflows/flutter-build.yml` 有 15 处 Release 上传步骤，分布在 12 个 job；`generate-sbom` 没有等待平台构建的 `needs`，也可以直接上传 Release。现有逐步骤凭据保护值得保留，但它不能保证整个发行集完成后才对外可见。风险是某个平台后来失败时已存在部分发布，不是本次已发生生产事故。

现代只读验证与旧发行入口还不是同一条构建链：例如新 Windows 验证采用 VS18/LLVM23，而旧发行文件仍有 LLVM15、Sciter Rust1.75 和旧 CMake 配置。通过新 software-codec profile 并不能证明旧硬件/安装器/Sciter 发行配置可用。

目标链：

`发布计划 → 固定源码与 profile → 构建一次 → 原生/功能/包校验 → Release Gate → 受保护签名 → 签后复核 → 单点发布`

- 发布计划明确平台、架构、格式、功能 profile 和所需验证；不能从“当前碰巧生成的文件”反推发布完整性。未迁完的原平台任务保留并显式标为阻塞，不靠删除任务满足门禁。
- 新旧消费者调用同一原生构建入口。验证和签名消费同一组不可变、带摘要的产物；分发阶段不偷偷重新解析依赖或编译另一个版本。
- Release Gate 汇总所选目标、安全检查和证据；失败、取消、缺失、意外跳过都不能通过。它不同于现有只汇总 repository/core 的 Foundation Gate。
- 普通 PR 继续只读、无签名凭据。签名在全新隔离 job 中读取受保护环境的最小凭据，不执行 PR 提供的任意脚本；签后重新记录摘要并验证身份。
- 所有必需资产、SBOM、来源证明和清单先进入不可公开的不完整状态，例如 draft release；全部成功后再单点转为正式发布。稳定标签不可复用，nightly 单独管理，回退只使用已验收的旧产物。

GitHub 的[环境保护规则](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)可隔离审批和环境凭据；本次没有声称已创建或验证仓库的生产环境保护配置。不要把 workflow 中写入一个环境名称当成已配置审批。

## P1：HTTP 失败应保留用户安全策略（待独立实施）

`src/hbbs_http/http_client.rs` 的代理解析、代理设置或 proxied builder 构造失败时会退回默认客户端。默认客户端不等于用户明确指定的代理策略，因此后续调用可能绕开指定代理；本次没有制造或观测实际数据泄露。该路径在导入基线 `d6c0376` 中已经存在，不是本次升级新增的缺陷。

同一模块的非严格工厂还保留根据探测失败重试允许无效证书的兼容行为；严格 HTTPS 工厂与非严格工厂必须分别审查，不能笼统声称所有 TLS 都不校验。

建议把这些隐式行为改为显式、可测试的策略：工厂返回 `Result`；指定代理失败不得降级为默认直连；自建服务的证书通过明确 CA/信任配置处理，不根据网络错误自动放宽校验。缓存不能提升信任或改变代理身份。账户发现、上传和同步/异步调用方必须一起处理错误并向用户呈现，不能仅修改宏后假设调用方正确。

退出条件是私有 loopback 负向测试证明错误配置不发出直连请求、拒绝不可信证书且不污染缓存，同时验证自建服务的显式信任路径。先保留现有 17 项 HTTP/TLS 回归，再逐项修改兼容契约。本次没有在缺少这些行为验收时直接改动生产网络策略。

## P1：依赖和兼容路径按功能迁移（待实施）

当前锁文件有 1130 个包身份、59 个 Git 包身份，来自 34 条不同 Git source/revision；159 个包名存在多版本。多版本本身不是漏洞结论，59 个 Git 包也不是 59 个独立仓库。不能为了“全部最新”覆盖维护中的 WebRTC、TLS、输入、PTY 或声卡补丁。

在现有清单中给每个 fork 记录上游/本地 revision、补丁用途、许可证、对应回归和移除条件。按同一能力的一组调用方迁移，而非一次 `update` 全树。macOS 六个 Pods、Android 两个兼容开关、旧 winreg 传递使用者等都有具体调用方，需要协同替代。

优先核对依赖审查中未识别许可证的 14 条声明：dash_chat_2 清单内的 flutter_markdown、flutter_parsed_text、intl、url_launcher，以及 pull_down_button、url_launcher_windows、contextmenu、debounce_throttle、flutter_breadcrumb、password_strength、fake_async、freezed_annotation、matcher、provider。应读取对应已锁定来源中的许可证文件，记录路径与摘要后完善 SBOM；不能把未知值直接写成 MIT 或当作许可批准。该依赖差异检查的[严重程度语义](https://github.com/actions/dependency-review-action/blob/main/README.md)也不替代完整依赖树的持续审查。

Sciter 删除应以启动、服务和 UI 功能替代为前提。F-Droid 四 ABI/x86 engine、Web 完整资源与浏览器行为，以及 RPM/AppImage/Flatpak/DRM、Windows MSI/驱动、Apple 签名分发仍需要各自验收，不能借用相近 profile 的绿色结果。

## P2：证据和代码边界统一，不再扩散入口（待实施）

开发者仍只需要 `tools/viper.py` 这一层公共入口，平台专用实现保留在其模块中。优先让入口调用已有实现、共享契约，不新增平行 CLI 或每次迁移专用脚本。YAML 只负责编排，复杂打包逻辑留在能做行为测试的工具内。

区分三类数据：固定版本/目标配置、实际运行证据、发布准入策略。未来所有平台报告采用同一最小 schema：源码 head、实际测试 merge/tree、锁文件摘要、profile、实际工具链、测试结果、产物摘要和签名状态。报告由执行生成，PR 表格从报告汇总；`toolchain.json` 中的迁移文字和手写 PR 状态不能同时作为动态真源。本次仅增强既有 Windows 报告，没有宣称全平台 schema 已统一。

运行时保留模块化单体：Flutter 表达 UI，FRB 只做边界转换；Rust 内按会话/传输与认证、媒体、输入/剪贴板/文件、平台适配逐步整理。`hbb_common` 保持服务端共享协议边界，客户端专用代码留在 `libs/base` 或对应功能模块。

`src/client.rs`、`src/common.rs`、`src/server/connection.rs`、`src/platform/windows.rs` 是后续重点，但不因文件大就抽出通用 trait 或统一所有生命周期。先给目标状态机建立契约测试，再做保持行为的小步模块提取；不把 Tokio runtime、锁与异步边界重新藏进公共工具，不把平台差异移成到处传递的占位参数。不要把大版本升级、网络安全语义改变和模块重排塞进同一增量提交。

## 执行顺序与最终退出条件

1. 验收本次 Windows 证据和预算修复；收敛单点发布 gate，保留所有原验证与平台范围。
2. 单独修复 HTTP 失败策略，核实未知许可证，建立 fork 补丁及依赖审查台账。
3. 按能力依次关闭 Apple/Android 兼容项、Sciter/Web/F-Droid 和特殊发行目标；每次要求相同源码/profile 的编译与功能证据。
4. 完成 GUI、权限拒绝/恢复、物理声卡、硬件编码、跨设备会话、输入/剪贴板/文件、安装升级卸载及回退验收，再放行签名、公证和正式交付。

在上述条件完成前保留 Draft。此次审查没有修改 main、强推、合并、安装生产服务、正式签名、公证或发布；架构建议和文档的完成不等于实现与设备验收已完成。
