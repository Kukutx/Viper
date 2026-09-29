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

Actions 真源是 `configs/actions-lock.json`。核对实际 release 与 SHA 后修改锁，再执行 `python tools/viper.py actions --write`；不接受未登记的第三方 action 或已弃用的 actions-rs。

Flutter SDK 选择器不等于应用依赖迁移完成。FRB 两端、生成代码、Flutter 包和各平台构建仍必须成套验证，状态见 `docs/engineering/foundation.md`。

## 原生验证

```sh
cargo metadata --locked --format-version 1
cargo test --locked -p base -p hbb_common --lib
```

完整 Linux 构建还需要 GTK、PulseAudio、X11、GStreamer、Clang 及 `vcpkg.json` 中的原生依赖。`.github/workflows/ci.yml` 保留完整构建与 workspace 测试；基础测试通过不代表 Windows/macOS/Android/iOS 已通过。

## 构建镜像

Dockerfile 是原生开发/构建环境，不是面向公网的服务。由 `build-environment.yml` 构建；PR 只验证，不登录仓库、不推送。手工从 main 启动并显式选择 publish 才发布到 GHCR，使用 SHA 标签、SBOM 和 provenance，生产应用部署不在此处执行。

## 发布产物校验

```sh
python tools/viper.py manifest dist --revision "$(git rev-parse HEAD)"
python tools/viper.py verify dist
```

清单记录精确源提交、相对路径、字节数和 SHA-256；拒绝空目录、符号链接、目录穿越、重复、缺失或额外产物。哈希校验不是签名验证；还必须执行平台签名、来源证明和安装回归。

`tools/.reports/` 是可丢弃报告目录，不存放凭据或唯一配置。任何代码签名、商店发布或生产部署必须使用受保护的环境与真实配置；不得提交秘密或复制参考仓库的凭据。
