#!/usr/bin/env bash
# activate.sh <id> — make <id> the active sandbox.
# Stops the currently active container (if different), ensures <id>'s container
# is running (adopting existing, starting an exited one, or creating fresh),
# sets .active = <id>, and writes the new status back to index.json.
# Emits a one-line JSON summary on stdout.
source "$(dirname "$0")/_common.sh"
ensure_index

id="${1:-}"
[[ -z "$id" ]] && die "usage: activate.sh <id>"
sandbox_exists "$id" || die "no such sandbox: $id (add it first — add.sh deferred)"

# Stop the previously active container if different.
prev="$(active_sandbox)"
if [[ -n "$prev" && "$prev" != "$id" ]]; then
  prev_name="$(container_name "$prev")"
  if container_running "$prev_name"; then
    log "stopping previous active: $prev"
    docker stop "$prev_name" >/dev/null 2>&1 || log "  warn: docker stop $prev_name failed"
  fi
  write_index "$(jq_index --arg n "$prev" '.sandboxes[$n].status = "stopped"')"
fi

# Three start paths: already running | exited container present | create fresh.
name="$(container_name "$id")"
transition=""

if container_running "$name"; then
  transition="already_running"
elif container_exists "$name"; then
  log "restarting existing container: $name"
  docker start "$name" >/dev/null
  transition="restarted"
else
  log "creating container: $name"
  spec="$(sandbox_get "$id")"

  image="$(jq -r '.image // empty' <<<"$spec")"
  [[ -z "$image" ]] && die "$id: missing .image in index.json"

  args=(run -d --name "$name")
  [[ "$(jq -r '.init // false' <<<"$spec")" == "true" ]] && args+=(--init)
  args+=(--user "$HOST_UID:$HOST_GID")
  args+=(--workdir "$HOST_MOUNT")
  args+=(--label "spot.sandbox-id=$id")
  args+=(--label "spot.schema-version=$(jq -r '.schema_version // 1' <<<"$spec")")

  # Bind mounts (interpolate ${SPOT_HOST_MOUNT} etc.).
  while IFS= read -r bind; do
    [[ -z "$bind" || "$bind" == "null" ]] && continue
    src="$(interp "$(jq -r '.source' <<<"$bind")")"
    tgt="$(interp "$(jq -r '.target' <<<"$bind")")"
    mode="$(jq -r '.mode // "rw"' <<<"$bind")"
    args+=(-v "$src:$tgt:$mode")
  done < <(jq -c '.binds[]?' <<<"$spec")

  # Named volumes.
  while IFS= read -r vol; do
    [[ -z "$vol" || "$vol" == "null" ]] && continue
    vsrc="$(jq -r '.source' <<<"$vol")"
    vtgt="$(jq -r '.target' <<<"$vol")"
    docker volume create "$vsrc" >/dev/null 2>&1 || true
    args+=(-v "$vsrc:$vtgt")
  done < <(jq -c '.named_volumes[]?' <<<"$spec")

  # Env vars.
  while IFS= read -r pair; do
    [[ -z "$pair" ]] && continue
    args+=(-e "$pair")
  done < <(jq -r '(.env // {}) | to_entries[] | "\(.key)=\(.value)"' <<<"$spec")

  # Resource limits.
  cpus="$(jq -r '.limits.cpus // empty' <<<"$spec")"
  mem="$(jq -r '.limits.memory // empty' <<<"$spec")"
  [[ -n "$cpus" ]] && args+=(--cpus "$cpus")
  [[ -n "$mem" ]] && args+=(--memory "$mem")

  # Always clear the image's ENTRYPOINT — sandboxes are passive holding
  # containers where the agent interacts via `docker exec`. The baked
  # entrypoint (e.g. `lean` on lean4 images) would swallow `sleep infinity`
  # as an argument instead of letting it become PID 1.
  args+=(--entrypoint "")
  args+=("$image")

  # Command.
  readarray -t cmd_arr < <(jq -r '(.command // ["sleep","infinity"])[]' <<<"$spec")
  args+=("${cmd_arr[@]}")

  err_file="$(mktemp)"
  if ! docker "${args[@]}" >/dev/null 2>"$err_file"; then
    err="$(tr '\n' ' ' <"$err_file")"
    rm -f "$err_file"
    write_index "$(jq_index --arg n "$id" --arg e "$err" '.sandboxes[$n].status = "error" | .sandboxes[$n].error_message = $e')"
    die "docker run failed: $err"
  fi
  rm -f "$err_file"
  transition="created"
fi

now="$(now_iso)"
write_index "$(jq_index --arg n "$id" --arg t "$now" '
  .active = $n
  | .sandboxes[$n].status = "running"
  | .sandboxes[$n].last_started_at = $t
  | .sandboxes[$n].error_message = null
')"

log "active sandbox: $id ($transition)"
jq -n --arg id "$id" --arg c "$name" --arg t "$transition" \
  '{id:$id, container:$c, active:true, status:"running", transition:$t}'
