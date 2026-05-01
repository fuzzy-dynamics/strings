#!/usr/bin/env bash
# show.sh <id> — full record for one sandbox: static spec from the catalog,
# enriched with live runtime state via `docker inspect`. The persisted
# `status` / `last_started_at` / `image_digest` fields (legacy runtime hints
# that catalog.cjs strips on read anyway) are dropped here so the caller
# can never accidentally trust a stale value. Live fields:
#   status, running, started_at, image_ref, current_bindings.
source "$(dirname "$0")/_common.sh"
ensure_index

id="${1:-}"
[[ -z "$id" ]] && die "usage: show.sh <id>"
sandbox_exists "$id" || die "no such sandbox: $id"

name="$(container_name "$id")"
spec="$(sandbox_get "$id" | jq 'del(.status, .last_started_at, .image_digest)')"
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
  --argjson spec "$spec" \
  '$spec + {id:$id, container:$container, status:$status, running:$running, started_at:$started_at, image_ref:$image_ref, current_bindings:$binds}'
