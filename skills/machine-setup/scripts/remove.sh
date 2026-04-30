#!/usr/bin/env bash
# remove.sh <name> [--force]
# Deletes a machine from index.json. Refuses if it's active or ready unless
# --force is passed. Does NOT touch the remote — use uninstall.sh first if you
# want to clean up there.
source "$(dirname "$0")/_common.sh"
ensure_index

name=""
force=0
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -*)      die "unknown flag: $arg" ;;
    *)       [[ -z "$name" ]] && name="$arg" || die "usage: remove.sh <name> [--force]" ;;
  esac
done

[[ -z "$name" ]] && die "usage: remove.sh <name> [--force]"
[[ "$name" == "local" ]] && die 'cannot remove reserved machine "local"'
machine_exists "$name" || die "no such machine: $name"

if [[ "$force" -ne 1 ]]; then
  active="$(active_machine)"
  [[ "$active" == "$name" ]] && die "$name is the active machine; deactivate first or use --force"
  status="$(machine_field "$name" "status")"
  [[ "$status" == "ready" || "$status" == "degraded" ]] && \
    die "$name has status=$status (uninstall first or use --force)"
fi

# If removing the active machine with --force, also clear active.
updated="$(jq_index --arg n "$name" '
  if .active == $n then .active = "local" else . end
  | del(.machines[$n])
')"
write_index "$updated"

# Clean the dangling ssh socket if any.
sock="$(ssh_sock "$name")"
if [[ -S "$sock" ]]; then
  ssh -O exit -S "$sock" "check-$name" 2>/dev/null || true
  rm -f "$sock"
fi

log "removed machine: $name"
