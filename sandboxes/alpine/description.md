# Alpine (POC)

A minimal Alpine Linux container. Ships with `sh`, `busybox`, and the standard coreutils — nothing else.

Use this sandbox to verify the sandboxing plumbing (same-path bind, host-uid writes, `docker exec` ergonomics) without waiting on a heavy image. It is the default target for smoke-testing the `sandbox-use` skill and the plane `/sandbox/*` endpoints.

**Size:** ~5 MB

**Contents:** Alpine 3.x base, no additional packages.

**Not suitable for:** Lean, Python, or other language toolchains — add a richer sandbox (coming soon) for those.
