#!/usr/bin/env bash
# deactivate.sh <id> — stop the named sandbox container. No-op if it isn't
# running. There's no global "active sandbox" anymore, so the id is required.
source "$(dirname "$0")/_common.sh"
ensure_index

id="${1:-}"
[[ -z "$id" ]] && die "usage: deactivate.sh <id>"
sandbox_exists "$id" || die "no such sandbox: $id"

name="$(container_name "$id")"
stopped=false
if container_running "$name"; then
  log "stopping $name"
  docker stop "$name" >/dev/null 2>&1 || log "  warn: docker stop failed"
  stopped=true
fi

write_index "$(jq_index --arg n "$id" '.sandboxes[$n].status = "stopped"')"

log "deactivated $id"
jq -n --arg n "$id" --argjson s "$stopped" '{id:$n, stopped:$s}'
