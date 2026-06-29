# Security Boundaries

- Users must set `authorized: true` before a URL run. This confirms ownership or authorization; it is not a legal substitute for permission.
- Only `GET` and `HEAD` methods are accepted.
- Embedded URL credentials are rejected.
- Loopback, private, link-local, reserved, multicast, local, internal, and common cloud metadata hosts are blocked.
- Configurations reject unknown fields and arbitrary command definitions.
- The tool creates a local outbox file after approval. It does not send real email.

Before any hosted deployment, add DNS rebinding protection, redirect validation, request budgets, per-project allowlists, audit logging, and managed secret storage.
