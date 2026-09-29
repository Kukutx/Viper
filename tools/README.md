# Viper 工具入口

版本真源：`configs/toolchain.json`。工具最低需要 Python 3.11；CI 使用 `.python-version` 的精确版本。先执行 `git submodule update --init --recursive`。

```sh
python -m pip install -r tools/requirements-dev.txt
python tools/viper.py check
python -m unittest discover -s tools/tests -v
python tools/viper.py env
python tools/viper.py inventory
python tools/viper.py inventory --latest
```

`inventory --latest` 只查询 crates.io / pub.dev，不修改依赖。清单区分 registry、Git fork、path、workspace 和 overrides；它是声明清单，不是兼容性证明。网络查询失败返回非零，不能把失败当成已最新。

## 同步版本

核对上游版本并编辑 `configs/toolchain.json` 后：

```sh
python tools/viper.py versions --write
python tools/viper.py versions
```

同时更新 Dockerfile 中对应的基础镜像与默认 ARG，并运行构建镜像验证。Actions 真源是 `configs/actions-lock.json`：核对 release 与 SHA 后修改锁，再执行 `python tools/viper.py actions --write`；不接受未登记的第三方 action 或已弃用的 actions-rs。Dependabot 不自动合并，关联配置必须在同一 PR 更新。

Flutter SDK 选择器不等于应用依赖迁移完成。FRB 两端、生成代码、Flutter 包和各平台构建仍必须成套验证，状态见 `docs/engineering/foundation.md`。

## 原生验证

```sh
cargo metadata --locked --format-version 1
cargo test --locked -p base -p hbb_common --lib
```

完整 Linux 构建还需要 GTK、PulseAudio、X11、GStreamer、Clang 及 `vcpkg.json` 中的原生依赖。`.github/workflows/ci.yml` 保留完整构建与 workspace 测试。Draft PR 运行基础门禁；Ready PR 才运行完整原生/Flutter 矩阵。基础测试通过不代表 Windows/macOS/Android/iOS 已通过。

## 构建镜像

Dockerfile 是原生开发/构建环境，不是面向公网的服务；不包含 Flutter SDK 或预生成 FFI 绑定。

```sh
# Linux/macOS 非 root 用户：匹配挂载目录的写入权限。
docker build --build-arg BUILDER_UID="$(id -u)" --build-arg BUILDER_GID="$(id -g)" -t viper-builder .
docker run --rm -v "$PWD:/workspace" viper-builder test --locked -p base -p hbb_common --lib
```

不传 UID/GID 时默认 10001。默认命令为 `cargo build --locked --features flutter --lib`，先生成项目 FFI 绑定和安装 vcpkg 依赖才能完成应用构建。传入参数是 cargo 子命令，按原样传递，不经 shell 重新拆分。

`build-environment.yml` 在 PR 中只验证镜像，不登录、不推送。仅手工从 main 启动并显式选择 publish 才发布 GHCR 构建镜像；使用 SHA 标签、SBOM 和 provenance。`build-images` 环境的审批与保护规则需由仓库管理员配置；仅写 environment 名称不等于已配置审批。没有执行任何生产应用部署。

## 发布产物校验

```sh
python tools/viper.py manifest dist --revision "$(git rev-parse HEAD)"
python tools/viper.py verify dist
```

清单记录精确源提交、相对路径、字节数和 SHA-256；拒绝空目录、符号链接、目录穿越、重复、缺失或额外产物。哈希校验不是签名验证；还必须执行平台签名、来源证明和安装回归。

`tools/.reports/` 是可丢弃报告目录，不存放凭据或唯一配置。代码签名、商店发布和生产部署必须使用受保护环境与真实配置；不得提交秘密或复制参考仓库的凭据。
