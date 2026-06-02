#!/usr/bin/env bash
# Shared helpers for the witsoc skill scripts.

set -euo pipefail

log() { printf "[witsoc] %s\n" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

usage_error() {
  printf "%s\n" "$*" >&2
  exit 2
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "required command missing: $1"
}

json_string() {
  jq -Rs . <<<"${1-}"
}

repo_root() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$script_dir/../../../.." && pwd
}

find_wit_cli() {
  if [[ -n "${WITSOC_WIT_BIN:-}" ]]; then
    [[ -x "$WITSOC_WIT_BIN" ]] || die "WITSOC_WIT_BIN is not executable: $WITSOC_WIT_BIN"
    printf "%s\n" "$WITSOC_WIT_BIN"
    return 0
  fi

  if command -v wit >/dev/null 2>&1; then
    command -v wit
    return 0
  fi

  local root
  root="$(repo_root)"
  if [[ -x "$root/witsoc/env/bin/wit" ]]; then
    printf "%s\n" "$root/witsoc/env/bin/wit"
    return 0
  fi

  die "wit CLI not found. Set WITSOC_WIT_BIN, install wit, or keep witsoc/env/bin/wit available."
}

require_wit_file() {
  local file="$1"
  [[ -n "$file" ]] || usage_error "missing .wit file"
  [[ -f "$file" ]] || die "file not found: $file"
  [[ "$file" == *.wit ]] || die "expected a .wit file: $file"
}

receipt_path_for() {
  local file="$1"
  printf "%s.receipt.json\n" "${file%.wit}.wit"
}

status_from_file() {
  local file="$1"
  sed -n 's/^-- Status:[[:space:]]*\([A-Z][A-Z_]*\).*$/\1/p' "$file" 2>/dev/null | head -1
}

run_capture() {
  local stdout_file="$1"
  local stderr_file="$2"
  shift 2
  set +e
  "$@" >"$stdout_file" 2>"$stderr_file"
  local code=$?
  set -e
  return "$code"
}
