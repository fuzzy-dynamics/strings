#!/usr/bin/env bash
# activate.sh <id> [--mount /abs/path]... — ensure <id>'s container is running,
# bound to the canonical $SPOT_HOST_MOUNT plus any additional same-path mounts
# requested via --mount. No global "active sandbox" anymore — multiple
# sandboxes may run concurrently, each with its own bind set.
#
# Decision table (where "binds match" = requested set == container's actual
# bind sources via `docker inspect`):
#
#   running, binds match     → no-op
#   running, binds differ    → docker stop + rm + create fresh
#   exited,  binds match     → docker start
#   exited,  binds differ    → docker rm + create fresh
#   missing                  → create fresh
#
# When called with no --mount, an already-running container is reused
# regardless of its current bindings — the canonical mount is always present,
# which is everything a deep-run agent under ~/.openscientist/worktrees/...
# needs. So Trigger 3 (deep agent) calls `activate.sh <id>` and adopts
# whatever's running without disturbing a UI-driven binding.
#
# Emits a one-line JSON summary on stdout.
source "$(dirname "$0")/_common.sh"
ensure_index

id=""
mounts=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mount)
      [[ -z "${2:-}" || "$2" != /* ]] && die "--mount requires an absolute path"
      mounts+=("$2"); shift 2 ;;
    -h|--help)
      cat <<EOF >&2
usage: activate.sh <id> [--mount /abs/path]...
EOF
      exit 2 ;;
    *)
      [[ -z "$id" ]] && id="$1" || die "unexpected arg: $1"
      shift ;;
  esac
done

[[ -z "$id" ]] && die "usage: activate.sh <id> [--mount /abs/path]..."
sandbox_exists "$id" || die "no such sandbox: $id (add it first — add.sh deferred)"

name="$(container_name "$id")"
spec="$(sandbox_get "$id")"

# requested = canonical bind sources from spec ∪ --mount extras (deduped, sorted)
requested_binds() {
  {
    while IFS= read -r bind; do
      [[ -z "$bind" || "$bind" == "null" ]] && continue
      interp "$(jq -r '.source' <<<"$bind")"
    done < <(jq -c '.binds[]?' <<<"$spec")
    for m in "${mounts[@]:-}"; do
      [[ -n "$m" ]] && printf '%s\n' "$m"
    done
  } | sort -u
}

binds_match() {
  local req cur
  req="$(requested_binds)"
  cur="$(container_bindings "$name" | sort -u)"
  [[ "$req" == "$cur" ]]
}

create_fresh() {
  local args
  args=(run -d --name "$name")
  [[ "$(jq -r '.init // false' <<<"$spec")" == "true" ]] && args+=(--init)
  args+=(--user "$HOST_UID:$HOST_GID")
  args+=(--workdir "$HOST_MOUNT")
  args+=(--label "spot.sandbox-id=$id")
  args+=(--label "spot.schema-version=$(jq -r '.schema_version // 1' <<<"$spec")")

  # Spec binds first.
  local spec_sources=()
  while IFS= read -r bind; do
    [[ -z "$bind" || "$bind" == "null" ]] && continue
    src="$(interp "$(jq -r '.source' <<<"$bind")")"
    tgt="$(interp "$(jq -r '.target' <<<"$bind")")"
    mode="$(jq -r '.mode // "rw"' <<<"$bind")"
    args+=(-v "$src:$tgt:$mode")
    spec_sources+=("$src")
  done < <(jq -c '.binds[]?' <<<"$spec")

  # --mount extras, same-path, deduped against spec sources so the canonical
  # mount can be passed without spurious duplication.
  for m in "${mounts[@]:-}"; do
    [[ -z "$m" ]] && continue
    local dup=false
    for s in "${spec_sources[@]:-}"; do [[ "$s" == "$m" ]] && dup=true; done
    [[ "$dup" == true ]] && continue
    args+=(-v "$m:$m:rw")
  done

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
  # entrypoint (e.g. `lean` on lean4 images) would swallow `sleep infinity`.
  args+=(--entrypoint "")
  args+=("$(jq -r '.image // empty' <<<"$spec")")

  readarray -t cmd_arr < <(jq -r '(.command // ["sleep","infinity"])[]' <<<"$spec")
  args+=("${cmd_arr[@]}")

  err_file="$(mktemp)"
  if ! docker "${args[@]}" >/dev/null 2>"$err_file"; then
    err="$(tr '\n' ' ' <"$err_file")"
    rm -f "$err_file"
    write_index "$(jq_index --arg n "$id" '.sandboxes[$n].status = "error"')"
    die "docker run failed: $err"
  fi
  rm -f "$err_file"
}

transition=""
exists=false
running=false
container_exists "$name" && exists=true
container_running "$name" && running=true

if [[ "$running" == true && ${#mounts[@]} -eq 0 ]]; then
  # Permissive deep-run path: any running container is fine, we only need
  # the canonical mount which is always there.
  transition="already_running"
elif [[ "$running" == true ]] && binds_match; then
  transition="already_running"
elif [[ "$exists" == true ]] && binds_match; then
  log "starting existing container: $name"
  docker start "$name" >/dev/null
  transition="restarted"
elif [[ "$exists" == true ]]; then
  log "binds differ — recreating $name"
  if [[ "$running" == true ]]; then
    docker stop "$name" >/dev/null 2>&1 || true
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  create_fresh
  transition="recreated"
else
  log "creating container: $name"
  create_fresh
  transition="created"
fi

log "$id: $transition"
jq -n --arg id "$id" --arg c "$name" --arg t "$transition" \
  '{id:$id, container:$c, status:"running", transition:$t}'
