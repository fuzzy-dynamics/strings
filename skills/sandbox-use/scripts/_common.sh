#!/usr/bin/env bash
# _common.sh — shared helpers for the sandbox-use skill.
# Source this at the top of every script:
#     source "$(dirname "$0")/_common.sh"

set -euo pipefail

INDEX_PATH="${OPENSCIENTIST_SANDBOXES_INDEX:-$HOME/.openscientist/sandboxes/index.json}"
DEFS_DIR="${OPENSCIENTIST_SANDBOXES_DEFS:-$HOME/.openscientist/sandboxes/defs}"
HOST_MOUNT="${SPOT_HOST_MOUNT:-$HOME/.openscientist}"
HOST_UID="${SPOT_HOST_UID:-$(id -u)}"
HOST_GID="${SPOT_HOST_GID:-$(id -g)}"

log() { printf "[sandbox-use] %s\n" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "required command missing: $1"
}

need jq
need docker

ensure_index() {
  if [[ ! -f "$INDEX_PATH" ]]; then
    mkdir -p "$(dirname "$INDEX_PATH")"
    umask 077
    printf '%s\n' '{"version":1,"sandboxes":{}}' > "$INDEX_PATH"
  fi
}

write_index() {
  local content="$1"
  local tmp
  tmp="$(mktemp "${INDEX_PATH}.XXXXXX")"
  printf '%s\n' "$content" > "$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$INDEX_PATH"
}

jq_index() { jq "$@" "$INDEX_PATH"; }

container_name() {
  printf 'spot-sandbox-%s' "$1"
}

sandbox_exists() {
  local id="$1"
  jq_index -e --arg n "$id" '.sandboxes | has($n)' >/dev/null
}

sandbox_get() {
  local id="$1"
  jq_index --arg n "$id" '.sandboxes[$n]'
}

sandbox_field() {
  local id="$1" path="$2"
  jq_index -r --arg n "$id" ".sandboxes[\$n].$path // empty"
}

# Return the running/exited container's bind-mount sources, sorted/deduped,
# one per line. Empty output when the container doesn't exist. Mirrors the
# Node-side `lifecycle.containerBindings` so both control planes agree.
container_bindings() {
  local name="$1"
  local raw
  raw="$(docker inspect "$name" 2>/dev/null || true)"
  [[ -z "$raw" || "$raw" == "[]" ]] && return 0
  jq -r '.[0].Mounts // [] | map(select(.Type == "bind") | .Source) | unique | .[]' <<<"$raw"
}

# Interpolate $SPOT_HOST_MOUNT / $SPOT_HOST_UID / $SPOT_HOST_GID in a string.
interp() {
  local s="$1"
  s="${s//\$SPOT_HOST_MOUNT/$HOST_MOUNT}"
  s="${s//\$SPOT_HOST_UID/$HOST_UID}"
  s="${s//\$SPOT_HOST_GID/$HOST_GID}"
  printf '%s' "$s"
}

container_exists() {
  local name="$1"
  docker inspect "$name" >/dev/null 2>&1
}

container_running() {
  local name="$1"
  local state
  state="$(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null || true)"
  [[ "$state" == "true" ]]
}

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
