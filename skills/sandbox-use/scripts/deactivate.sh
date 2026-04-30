#!/usr/bin/env bash
# deactivate.sh — stop the currently active sandbox container and clear .active.
# No-op if nothing is active.
source "$(dirname "$0")/_common.sh"
ensure_index

active="$(active_sandbox)"
if [[ -z "$active" ]]; then
  log "no active sandbox"
  jq -n '{active:null, stopped:false}'
  exit 0
fi

name="$(container_name "$active")"
stopped=false
if container_running "$name"; then
  log "stopping $name"
  docker stop "$name" >/dev/null 2>&1 || log "  warn: docker stop failed"
  stopped=true
fi

write_index "$(jq_index --arg n "$active" '.active = null | .sandboxes[$n].status = "stopped"')"

log "deactivated $active"
jq -n --arg n "$active" --argjson s "$stopped" '{active:null, previous:$n, stopped:$s}'
