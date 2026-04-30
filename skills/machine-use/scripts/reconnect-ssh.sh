#!/usr/bin/env bash
# reconnect-ssh.sh <name>
# Reopens the SSH ControlMaster for a machine. Idempotent — if the master is
# already alive, it exits 0 without change. Does NOT add LocalForwards;
# Electron's machine bridge owns those. After a successful reconnect, touch
# index.json so Electron's watcher re-runs its activation logic and re-adds
# the forwards.
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: reconnect-ssh.sh <name>"
[[ "$name" == "local" ]] && die 'reserved name "local" has no SSH tunnel'
machine_exists "$name" || die "no such machine: $name"

if ssh_master_alive "$name"; then
  log "ControlMaster already alive for $name"
  exit 0
fi

host="$(machine_field "$name" "host")"
user="$(machine_field "$name" "user")"
key="$(machine_field "$name" "ssh.keyPath")"
port="$(machine_field "$name" "port")"
[[ -z "$port" ]] && port=22

sock="$(ssh_sock "$name")"
mkdir -p "$(dirname "$sock")"
[[ -e "$sock" ]] && rm -f "$sock"

log "opening ControlMaster for $name ($user@$host:$port) ..."
ssh -M -S "$sock" \
  -o ControlPersist=60m \
  -o ExitOnForwardFailure=yes \
  -o ConnectTimeout=10 \
  -o BatchMode=yes \
  -i "$key" -p "$port" \
  -fN "$user@$host"

if ! ssh_master_alive "$name"; then
  die "ControlMaster failed to come up at $sock"
fi

# Bump index.json mtime so Electron's fs.watch fires and re-adds forwards.
touch "$INDEX_PATH"

log "ControlMaster reopened: $sock"
