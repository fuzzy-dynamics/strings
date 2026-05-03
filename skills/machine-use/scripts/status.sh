#!/usr/bin/env bash
# status.sh <name>
#
# DEPRECATED — retired in favor of verify.sh per machine-provisioning-spec.md
# §4.7. This is a thin shim kept for back-compat with skill prompts that
# reference status.sh by name. Will be removed after one release cycle.
#
# Forwards all arguments to verify.sh, which is read-only and produces a
# structured JSON outcome with the same shape (kimi.ok, plane.ssh.ok, etc.).
exec "$(dirname "$0")/verify.sh" "$@"
