#!/usr/bin/env bash
# _common.sh — shared helpers for the machine-setup skill.
# A duplicated copy of the same helpers lives in ../machine-use/scripts/_common.sh;
# both originate from the same world-model file at sync time. Keep them in sync.
# Source this at the top of every script:
#     source "$(dirname "$0")/_common.sh"

set -euo pipefail

INDEX_PATH="${OPENSCIENTIST_MACHINES_INDEX:-$HOME/.openscientist/machines/index.json}"
SSH_DIR="${OPENSCIENTIST_SSH_DIR:-$HOME/.openscientist/ssh}"
AUTH_PATH="${OPENSCIENTIST_AUTH:-$HOME/.openscientist/auth.json}"

log() { printf "[machine-setup] %s\n" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "required command missing: $1"
}

need jq
need ssh
need curl

ensure_index() {
  if [[ ! -f "$INDEX_PATH" ]]; then
    mkdir -p "$(dirname "$INDEX_PATH")"
    umask 077
    printf '%s\n' '{"version":1,"machines":{}}' > "$INDEX_PATH"
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

machine_exists() {
  local name="$1"
  jq_index -e --arg n "$name" '.machines | has($n)' >/dev/null
}

machine_get() {
  local name="$1"
  jq_index --arg n "$name" '.machines[$n]'
}

machine_field() {
  local name="$1" path="$2"
  jq_index -r --arg n "$name" ".machines[\$n].$path // empty"
}

active_machine() {
  jq_index -r '.active // "local"'
}

ssh_sock() {
  mkdir -p "$SSH_DIR"
  printf '%s/%s.sock' "$SSH_DIR" "$1"
}

ssh_master_alive() {
  local name="$1"
  local sock; sock="$(ssh_sock "$name")"
  [[ -S "$sock" ]] || return 1
  ssh -O check -S "$sock" "check-$name" 2>/dev/null
}

# Build the ssh option array for a named machine. Use with:
#     mapfile -t opts < <(ssh_base_opts osci-math)
#     ssh "${opts[@]}" "$(ssh_target osci-math)" '<cmd>'
ssh_base_opts() {
  local name="$1"
  local host user key port sock
  host="$(machine_field "$name" "host")"
  user="$(machine_field "$name" "user")"
  key="$(machine_field "$name" "ssh.keyPath")"
  port="$(machine_field "$name" "port")"
  [[ -z "$port" ]] && port=22
  sock="$(ssh_sock "$name")"
  [[ -z "$host" ]] && die "$name: missing host"
  [[ -z "$user" ]] && die "$name: missing user"
  [[ -z "$key"  ]] && die "$name: missing ssh.keyPath"
  # One option per line so mapfile can split on newlines.
  printf -- '-i\n%s\n-p\n%s\n-o\nConnectTimeout=5\n-o\nBatchMode=yes\n-o\nControlPath=%s\n' \
    "$key" "$port" "$sock"
}

ssh_target() {
  local name="$1"
  printf '%s@%s' "$(machine_field "$name" "user")" "$(machine_field "$name" "host")"
}

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
