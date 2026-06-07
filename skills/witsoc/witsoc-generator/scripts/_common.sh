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

  local plugin_dir="${WITSOC_PLUGIN_DIR:-$HOME/.openscientist/plugins/witsoc}"
  if [[ -x "$plugin_dir/bin/ensure-deps" ]]; then
    "$plugin_dir/bin/ensure-deps" >/dev/null 2>&1 || "$plugin_dir/bin/ensure-deps"
    if [[ -x "$plugin_dir/data/venv/bin/wit" ]]; then
      printf "%s\n" "$plugin_dir/data/venv/bin/wit"
      return 0
    fi
  fi

  if [[ -x "$HOME/.openscientist/plugins/witsoc/data/venv/bin/wit" ]]; then
    printf "%s\n" "$HOME/.openscientist/plugins/witsoc/data/venv/bin/wit"
    return 0
  fi

  die "wit CLI not found. Set WITSOC_WIT_BIN, install wit, keep witsoc/env/bin/wit available, or install/activate the Witsoc plugin."
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

sanitize_slug() {
  local raw="${1:-proof}"
  raw="$(printf "%s" "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9_+-]+/-/g; s/^-+//; s/-+$//')"
  [[ -n "$raw" ]] || raw="proof"
  printf "%s\n" "$raw"
}

session_id_for_artifacts() {
  printf "%s\n" "${OSCI_SESSION_ID:-${PLANE_SESSION_ID:-${SESSION_ID:-manual}}}"
}

default_worktrees_root() {
  if [[ -n "${WITSOC_WORKTREES_DIR:-}" ]]; then
    printf "%s\n" "$WITSOC_WORKTREES_DIR"
    return 0
  fi
  if [[ -n "${PLANE_SESSION_DIR:-}" ]]; then
    printf "%s\n" "$PLANE_SESSION_DIR/worktrees"
    return 0
  fi
  if [[ -n "${KIMI_WORK_DIR:-}" ]]; then
    printf "%s\n" "$KIMI_WORK_DIR/worktrees"
    return 0
  fi
  printf "%s\n" "$PWD/worktrees"
}

default_proof_worktree() {
  local proof_id
  proof_id="$(sanitize_slug "${1:-proof}")"
  if [[ -n "${WITSOC_PROOF_WORKTREE:-}" ]]; then
    printf "%s\n" "$WITSOC_PROOF_WORKTREE"
    return 0
  fi
  printf "%s/witsoc-proof-%s-%s\n" "$(default_worktrees_root)" "$(session_id_for_artifacts)" "$proof_id"
}

default_artifact_path() {
  local name="$1"
  local ext="${2:-wit}"
  local proof_id
  proof_id="$(sanitize_slug "$name")"
  printf "%s/%s.%s\n" "$(default_proof_worktree "$proof_id")" "$name" "$ext"
}

register_witsoc_artifact() {
  local file="$1"
  local type="${2:-}"
  local owner_phase="${3:-${WITSOC_OWNER_PHASE:-witsoc-generator}}"
  local status="${4:-created}"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local registry_py="$script_dir/../../scripts/artifacts.py"
  [[ -f "$registry_py" ]] || return 0
  local args=( "$registry_py" register "$file" --owner-phase "$owner_phase" --status "$status" )
  [[ -z "$type" ]] || args+=( --type "$type" )
  if [[ -n "${WITSOC_PROOF_WORKTREE:-}" ]]; then
    args+=( --proof-worktree "$WITSOC_PROOF_WORKTREE" )
  fi
  python3 "${args[@]}" >/dev/null 2>&1 || true
}
