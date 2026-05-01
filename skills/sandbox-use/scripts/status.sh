#!/usr/bin/env bash
# status.sh <id> — live-probe a sandbox via `docker inspect`, emit the probed
# state as JSON. Read-only: does NOT write back to the catalog (Docker is the
# source of truth for runtime state; the persisted `status` field exists only
# as a stale hint and is overridden on read by enrichment).
source "$(dirname "$0")/_common.sh"
ensure_index

id="${1:-}"
[[ -z "$id" ]] && die "usage: status.sh <id>"
sandbox_exists "$id" || die "no such sandbox: $id"

name="$(container_name "$id")"
raw="$(docker inspect "$name" 2>/dev/null || true)"

if [[ -z "$raw" || "$raw" == "[]" ]]; then
  status="not_running"
  running=false
  started_at=null
  image_ref=null
  binds_json="[]"
else
  running="$(jq -r '.[0].State.Running' <<<"$raw")"
  raw_status="$(jq -r '.[0].State.Status' <<<"$raw")"
  if [[ "$running" == "true" ]]; then
    status="running"
  elif [[ "$raw_status" == "exited" || "$raw_status" == "created" ]]; then
    status="stopped"
  else
    status="$raw_status"
  fi
  started_at="$(jq '.[0].State.StartedAt' <<<"$raw")"
  image_ref="$(jq '.[0].Config.Image' <<<"$raw")"
  binds_json="$(jq '[.[0].Mounts // [] | .[] | select(.Type == "bind") | .Source] | unique' <<<"$raw")"
fi

jq -n \
  --arg id "$id" \
  --arg container "$name" \
  --arg status "$status" \
  --argjson running "$running" \
  --argjson started_at "$started_at" \
  --argjson image_ref "$image_ref" \
  --argjson binds "$binds_json" \
  '{id:$id, container:$container, status:$status, running:$running, started_at:$started_at, image_ref:$image_ref, current_bindings:$binds}'
