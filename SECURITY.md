# Security

Viper assumes explicit remote-assistance consent.

Current guarantees:
- TLS 1.3 transport.
- Local pairing approval before access.
- Session lifetime capped at one hour.
- Session bound to the approving connections.
- Disconnect revokes the session.
- Read-only MVP capabilities only.
- Agent file access is restricted to an explicit shared root and rejects absolute paths, parent traversal, and symlink escapes.
- Protocol messages have a bounded wire size and require the current protocol version.
- Pending pairing and request state expires, and responses are accepted only from the expected agent.
- Pairing attempts are throttled per controller connection.
- Pairing codes are not written to normal server logs.

Before broad Internet deployment, add durable device identities, controller authentication, server-wide/IP-aware rate limiting, structured audit logs, per-capability approval, request quotas, encrypted durable local state, and independent security review.

Per-connection throttling is not a substitute for a distributed abuse-control layer. Do not expose the development relay directly to untrusted networks without additional controls.

Never use `-insecure` on public networks.
