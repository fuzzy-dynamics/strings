#!/usr/bin/env bash
# deactivate.sh [<name>] — drop the SSH ControlMaster for a machine (or the
# only one currently up if no name is given). No longer writes `.active` —
# Electron drives bridge lifecycle.
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
if [[ -n "$name" && "$name" != "local" ]]; then
  machine_exists "$name" || die "no such machine: $name"
  sock="$(ssh_sock "$name")"
  if [[ -S "$sock" ]]; then
    ssh -O exit -S "$sock" "check-$name" 2>/dev/null || true
    log "closed ControlMaster: $name"
  else
    log "$name has no live ControlMaster — nothing to do"
  fi
else
  log "no machine name given; nothing to do (use deactivate.sh <name> to close a tunnel)"
fi
