#!/usr/bin/env bash
# deactivate.sh — clear active machine (falls back to "local").
source "$(dirname "$0")/_common.sh"
ensure_index
write_index "$(jq_index '.active = "local"')"
log "active machine: local"
