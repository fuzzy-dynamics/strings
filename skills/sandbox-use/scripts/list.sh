#!/usr/bin/env bash
# list.sh — JSON array of every installed sandbox, enriched with live state.
#
# Per-entry shape:
#   { id, label, image, status, current_bindings }
#
# `status` and `current_bindings` are derived live via `docker inspect`
# (status="not_running" when the container doesn't exist; current_bindings
# is null in that case). The catalog (~/.openscientist/sandboxes/index.json)
# remains the source of truth for static fields only.
source "$(dirname "$0")/_common.sh"
ensure_index

ids=()
while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  ids+=("$id")
done < <(jq_index -r '.sandboxes | keys[]')

entries=()
for id in "${ids[@]:-}"; do
  name="$(container_name "$id")"
  spec="$(sandbox_get "$id")"

  raw="$(docker inspect "$name" 2>/dev/null || true)"
  if [[ -z "$raw" || "$raw" == "[]" ]]; then
    status="not_running"
    binds_json="null"
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
    binds_json="$(jq '[.[0].Mounts // [] | .[] | select(.Type == "bind") | .Source] | unique' <<<"$raw")"
  fi

  entry="$(jq -c \
    --arg id "$id" \
    --arg status "$status" \
    --argjson binds "$binds_json" \
    '{
      id: $id,
      label: (.label // $id),
      image: (.image // null),
      status: $status,
      current_bindings: $binds
    }' <<<"$spec")"
  entries+=("$entry")
done

if [[ ${#entries[@]} -eq 0 ]]; then
  printf '[]\n'
else
  printf '%s\n' "${entries[@]}" | jq -s .
fi
