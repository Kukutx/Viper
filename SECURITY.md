# Security

Viper assumes explicit remote-assistance consent.

Current guarantees:
- TLS 1.3 transport.
- Local pairing approval before access.
- Session lifetime capped at one hour.
- Session bound to the approving connections.
- Disconnect revokes the session.
- Read-only MVP capabilities only.

Before broad Internet deployment, add durable device identities, controller authentication, rate limiting, audit logs, per-capability approval, request quotas, and independent security review.

Never use `-insecure` on public networks.
