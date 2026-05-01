#!/usr/bin/env bash
# activate.sh <name|local> — assert the machine is provisioned and SSH-reachable.
#
# No longer writes `.active` into index.json — the renderer drives "currently
# viewed machine" via Electron's bridge IPC; this script is now used by Gecko
# only as a precondition check ("can I drive this machine?"). Reserved name
# "local" is a no-op success.
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: activate.sh <name|local>"

if [[ "$name" == "local" ]]; then
  log "local — nothing to do"
  exit 0
fi

machine_exists "$name" || die "no such machine: $name"

status="$(machine_field "$name" "status")"
case "$status" in
  ""|""|"") ;;                          # absent ≡ ready (install.sh deletes the key on success)
  unprovisioned)  die "machine $name is unprovisioned; run install.sh first" ;;
  provisioning)   die "machine $name install in flight; wait for it to finish" ;;
  error)          die "machine $name is in error state; re-run install.sh" ;;
  *)              ;; # any other value (legacy "ready"/"degraded") — Electron strips on read
esac

if ! ssh_master_alive "$name"; then
  log "ControlMaster down; opening ..."
  "$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null
fi

# Touch the index so Electron's watcher re-emits machines-changed. Cheap signal
# that the renderer should re-snapshot bridge state.
touch "$INDEX_PATH"
log "ready: $name"
