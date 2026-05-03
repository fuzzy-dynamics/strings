#!/usr/bin/env bash
# reconnect-ssh.sh <name>
#
# Reopens the SSH ControlMaster for a machine. Idempotent — if the master is
# already alive, exits 0 without change. Does NOT add LocalForwards;
# Electron's machine bridge owns those. After a successful reconnect, touch
# index.json so Electron's watcher re-runs activation and re-adds forwards.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-setup" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  printf '{"ok":false,"stage":"parse-args","message":"usage: reconnect-ssh.sh <name>"}\n'
  exit 2
fi
if [[ "$NAME" == "local" ]]; then
  printf '{"ok":false,"stage":"parse-args","message":"reserved name \"local\" has no SSH tunnel"}\n'
  exit 2
fi

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME
ensure_index
machine_exists "$NAME" || { printf '{"ok":false,"stage":"precheck","message":"no such machine: %s"}\n' "$NAME"; exit 1; }

if ssh_master_alive "$NAME"; then
  emit_progress info "ssh-master" "ControlMaster already alive"
  jq -nc --arg name "$NAME" '{ok:true,name:$name,stage:"already-alive"}'
  exit 0
fi

host="$(machine_field "$NAME" "ssh.host")"
user="$(machine_field "$NAME" "ssh.user")"
key="$(machine_field "$NAME" "ssh.keyPath")"
port="$(machine_field "$NAME" "ssh.port")"
# Backwards compat with old flat layout.
[[ -z "$host" ]] && host="$(machine_field "$NAME" "host")"
[[ -z "$user" ]] && user="$(machine_field "$NAME" "user")"
[[ -z "$port" ]] && port="$(machine_field "$NAME" "port")"
[[ -z "$port" ]] && port=22

[[ -z "$host" ]] && { printf '{"ok":false,"stage":"precheck","message":"missing ssh.host"}\n'; exit 1; }
[[ -z "$user" ]] && { printf '{"ok":false,"stage":"precheck","message":"missing ssh.user"}\n'; exit 1; }
[[ -z "$key"  ]] && { printf '{"ok":false,"stage":"precheck","message":"missing ssh.keyPath"}\n'; exit 1; }

sock="$(ssh_sock "$NAME")"
mkdir -p "$(dirname "$sock")"
[[ -e "$sock" ]] && rm -f "$sock"

emit_progress info "ssh-master-open" "opening ControlMaster ($user@$host:$port)"
if ! with_timeout 30 "ssh-master-open" -- \
  ssh -M -S "$sock" \
    -o ControlPersist=60m \
    -o ExitOnForwardFailure=yes \
    -o ConnectTimeout=10 \
    -o BatchMode=yes \
    -i "$key" -p "$port" \
    -fN "$user@$host"
then
  printf '{"ok":false,"stage":"ssh-master-open","message":"ssh -M failed to spawn"}\n'
  exit 1
fi

if ! ssh_master_alive "$NAME"; then
  printf '{"ok":false,"stage":"ssh-master-open","message":"ControlMaster failed to come up at %s"}\n' "$sock"
  exit 1
fi

# Probe to confirm.
if ! with_timeout 15 "ssh-probe" -- ssh_run "$NAME" -q -- "uname -a"; then
  printf '{"ok":false,"stage":"ssh-probe","message":"ControlMaster up but probe failed"}\n'
  exit 1
fi

# Mark setup-complete if currently unprovisioned.
current_status="$(machine_field "$NAME" "status")"
if [[ "$current_status" == "unprovisioned" ]]; then
  index_update "$NAME" '. + {status:"setup-complete"}'
  emit_progress info "status" "marked setup-complete"
fi

# Bump index.json mtime so Electron's fs.watch fires and re-adds forwards.
touch "$INDEX_PATH"

emit_progress info "done" "ControlMaster reopened: $sock"
jq -nc --arg name "$NAME" --arg sock "$sock" '{ok:true,name:$name,stage:"done",socket:$sock}'
