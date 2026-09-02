# Viper

Viper is a small cross-platform remote-assistance foundation designed for explicit, user-approved sessions and future AI tool control.

The current MVP has three Go programs:

- `viper-server` — public TLS relay/control server.
- `viper-agent` — runs on the computer receiving assistance.
- `kuku` — controller CLI.

The agent does **not** open an inbound port. It connects outbound to the relay server, which makes it usable behind normal home NAT/CGNAT without router configuration.

## Current capabilities

The first public MVP intentionally starts read-only:

- `device.info`
- `file.list`
- `file.read` (1 MiB maximum per request, restricted to the configured shared root)

Remote command execution is not enabled in this first version. The next execution layer should require explicit per-command approval on the agent side before a command is started.

## Safety model

- The agent prints a pairing code locally.
- A remote controller must know that code.
- The remote user must explicitly approve the session in the agent terminal.
- Approved sessions expire after at most one hour.
- Closing either side invalidates the session.
- File operations are sandboxed under the agent's configured `-root` directory; absolute paths, `..` traversal, and symlink escapes are rejected.
- Protocol messages have a bounded wire size and require the current protocol version.
- The relay binds pairing decisions and request results to the expected peer and expires pending state.
- Pairing attempts are throttled per controller connection.
- The MVP installs no persistence and does not hide itself.

## Requirements

Go 1.23+ is required only to build. End users can run the compiled single binary.

## Build

```bash
go build -o bin/viper-server ./cmd/server
go build -o bin/viper-agent ./cmd/agent
go build -o bin/kuku ./cmd/kuku
```

Cross-compile examples:

```bash
GOOS=linux GOARCH=amd64 go build -o dist/viper-agent-linux-amd64 ./cmd/agent
GOOS=darwin GOARCH=arm64 go build -o dist/viper-agent-darwin-arm64 ./cmd/agent
GOOS=windows GOARCH=amd64 go build -o dist/viper-agent-windows-amd64.exe ./cmd/agent
```

## Quick local test

Start the server. With no certificate arguments it creates an in-memory self-signed development certificate:

```bash
go run ./cmd/server
```

Start an agent and explicitly choose the directory that may be inspected during the approved session:

```bash
go run ./cmd/agent -server localhost:8443 -insecure -root .
```

The agent prints an 8-digit pairing code.

In another terminal:

```bash
go run ./cmd/kuku -server localhost:8443 -insecure connect 12345678
```

Use the actual code shown by the agent. The remote side must type `y` before the session becomes active.

Then try:

```text
info
ls .
read README.md
quit
```

Attempts to read outside the configured root are rejected.

## Public deployment

Run `viper-server` on a public host and use a trusted TLS certificate:

```bash
viper-server -listen :443 -cert fullchain.pem -key privkey.pem
```

Then agents connect outbound and expose only an explicitly chosen directory:

```bash
viper-agent -server remote.example.com:443 -root /srv/viper-share
```

Controllers use:

```bash
kuku -server remote.example.com:443 connect <pair-code>
```

Do not use `-insecure` on public networks.

## Protocol

Messages are newline-delimited JSON over TLS 1.3. The server routes approved requests between a controller and an agent. The transport and capability model are deliberately separated so P2P/QUIC can be added later without changing the higher-level remote-assistance API.

## Roadmap

1. Durable Ed25519 device identity and encrypted local state.
2. Fine-grained capability approval and structured audit log.
3. Server-wide/IP-aware abuse controls in addition to per-connection pairing throttling.
4. Per-command local approval for any future execution capability.
5. PTY interactive terminal and streaming file transfer only after the approval model is hardened and independently reviewed.
6. UDP endpoint discovery, authenticated hole punching, P2P transport, relay fallback.
7. AI tool adapter using the capability protocol.
8. Screen streaming/input control as separate opt-in capabilities.
9. Android APK using the same protocol with Android-specific capabilities.
