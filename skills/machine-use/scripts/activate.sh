#!/usr/bin/env bash
# activate.sh <name> — set the active machine. Electron's index watcher opens
# the SSH tunnel and forwards 5494/5495. Reserved: "local" clears the tunnel.
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: activate.sh <name|local>"

if [[ "$name" != "local" ]]; then
  machine_exists "$name" || die "no such machine: $name"
  status="$(machine_field "$name" "status")"
  if [[ "$status" != "ready" && "$status" != "degraded" ]]; then
    die "machine $name has status=$status; run install.sh first"
  fi
fi

write_index "$(jq_index --arg n "$name" '.active = $n')"
log "active machine: $name"
