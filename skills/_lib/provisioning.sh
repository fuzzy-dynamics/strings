#!/usr/bin/env bash
# provisioning.sh — shared helpers for machine-setup / machine-use scripts.
#
# Per machine-provisioning-spec.md §11, every script sources this file:
#     source "$(dirname "$0")/../../_lib/provisioning.sh"
#
# Provides:
#   emit_progress  <level> <stage> <msg> [<progress-json>]
#   mark_broken    <stage> <message> [<extra-json>]
#   index_lock     <name>
#   index_read     <name> [<jq-path>]
#   index_update   <name> <jq-merge-expr>
#   with_timeout   <seconds> <stage> -- <cmd...>
#   ssh_run        <name> -- <cmd...>
#   ssh_pipe       <name> [--env KEY=VAL ...] -- <local-script> [<args...>]
#   log_open       <script>
#   remote_log_tail <name> <script-log> [<lines>]
#
# Plus low-level helpers carried over from the old _common.sh:
#   ensure_index, write_index, jq_index, machine_exists, machine_get,
#   machine_field, ssh_sock, ssh_master_alive, ssh_base_opts, ssh_target,
#   now_iso, need.

set -euo pipefail

# ── paths and constants ──────────────────────────────────────────────────────

OPENSCIENTIST_HOME="${OPENSCIENTIST_HOME:-$HOME/.openscientist}"
INDEX_PATH="${OPENSCIENTIST_MACHINES_INDEX:-$OPENSCIENTIST_HOME/machines/index.json}"
INDEX_DIR="$(dirname "$INDEX_PATH")"
SSH_DIR="${OPENSCIENTIST_SSH_DIR:-$OPENSCIENTIST_HOME/ssh}"
AUTH_PATH="${OPENSCIENTIST_AUTH:-$OPENSCIENTIST_HOME/auth.json}"
LOG_DIR="${OPENSCIENTIST_LOG_DIR:-$OPENSCIENTIST_HOME/logs}"
LOCK_DIR="$INDEX_DIR"          # <name>.lock files live next to index.json
LASTERROR_DIR="$INDEX_DIR"     # <name>.lasterror forensic files

mkdir -p "$INDEX_DIR" "$SSH_DIR" "$LOG_DIR" "$LASTERROR_DIR" 2>/dev/null || true

# Skill name shown in log prefix. Set by the caller via:
#     SKILL_TAG="machine-setup" source ".../_lib/provisioning.sh"
SKILL_TAG="${SKILL_TAG:-provisioning}"
SCRIPT_NAME="$(basename "${BASH_SOURCE[1]:-${0}}" .sh)"

# Sentinel preventing ERR-trap recursion when mark_broken itself fails.
MARK_BROKEN_IN_PROGRESS="${MARK_BROKEN_IN_PROGRESS:-0}"

# ── primitives ───────────────────────────────────────────────────────────────

log() { printf "[%s] %s\n" "$SKILL_TAG" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "required command missing: $1"
}

need jq
need ssh
need flock
need sha256sum

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Print one NDJSON progress line on stderr. Schema:
#     {"ts":"...","name":"...","stage":"...","level":"info|warn|error","msg":"...","progress":{...}?}
emit_progress() {
  local level="${1:-info}" stage="${2:-?}" msg="${3:-}" prog="${4:-}"
  local name="${PROVISIONING_NAME:-?}"
  local line
  if [[ -n "$prog" ]]; then
    line=$(jq -nc \
      --arg ts "$(now_iso)" --arg name "$name" --arg stage "$stage" \
      --arg level "$level" --arg msg "$msg" --argjson prog "$prog" \
      '{ts:$ts,name:$name,stage:$stage,level:$level,msg:$msg,progress:$prog}')
  else
    line=$(jq -nc \
      --arg ts "$(now_iso)" --arg name "$name" --arg stage "$stage" \
      --arg level "$level" --arg msg "$msg" \
      '{ts:$ts,name:$name,stage:$stage,level:$level,msg:$msg}')
  fi
  printf '%s\n' "$line" >&2
}

# ── index helpers ────────────────────────────────────────────────────────────

ensure_index() {
  if [[ ! -f "$INDEX_PATH" ]]; then
    mkdir -p "$INDEX_DIR"
    umask 077
    printf '%s\n' '{"version":1,"machines":{}}' > "$INDEX_PATH"
  fi
}

# Atomic whole-file replacement.
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
  ensure_index
  jq_index -e --arg n "$name" '.machines | has($n)' >/dev/null
}

machine_get() {
  local name="$1"
  ensure_index
  jq_index --arg n "$name" '.machines[$n]'
}

machine_field() {
  local name="$1" path="$2"
  ensure_index
  jq_index -r --arg n "$name" ".machines[\$n].$path // empty"
}

# Read a field (or whole record if no path) from the index.
#     index_read osci-math
#     index_read osci-math .ssh.host
index_read() {
  local name="$1" path="${2:-}"
  ensure_index
  if [[ -n "$path" ]]; then
    jq_index --arg n "$name" ".machines[\$n] | $path"
  else
    machine_get "$name"
  fi
}

# Atomic merge into a machine record. <expr> is a jq expression that
# returns the updated record given the old record as `.`.
# Example:
#     index_update osci-math '. + {status:"ready", remote:{home:"/home/u"}}'
index_update() {
  local name="$1" expr="$2"
  ensure_index
  local new
  new=$(jq --arg n "$name" \
    ".machines[\$n] |= ($expr) | .machines[\$n].name = \$n" \
    "$INDEX_PATH")
  write_index "$new"
}

# Acquire a per-machine lock for the lifetime of the calling shell.
# Sets a trap to release the lock on EXIT.
#     index_lock osci-math
index_lock() {
  local name="$1"
  local lock_file="$LOCK_DIR/$name.lock"
  mkdir -p "$LOCK_DIR"
  exec {LOCK_FD}>"$lock_file"
  if ! flock -n "$LOCK_FD"; then
    emit_progress error "lock" "another op in progress on $name"
    printf '%s\n' "{\"ok\":false,\"name\":\"$name\",\"stage\":\"lock\",\"message\":\"another op in progress\"}"
    exit 1
  fi
  trap '_release_lock' EXIT
}

_release_lock() {
  if [[ -n "${LOCK_FD:-}" ]]; then
    flock -u "$LOCK_FD" 2>/dev/null || true
    eval "exec ${LOCK_FD}>&-" 2>/dev/null || true
  fi
}

# ── failure handling ─────────────────────────────────────────────────────────

# Append a forensic JSON line to <name>.lasterror, then mark the machine
# broken in the index. This is the ONLY error-exit path — every die() in
# scripts that have set up provisioning state should go through here.
#
#     mark_broken "<stage>" "<message>" '<extra-json-or-empty>'
#
# Extra is a JSON object (or "{}") merged into lastError. Use for
# remoteLogTail, serviceLogs, etc.
mark_broken() {
  local stage="${1:-?}" message="${2:-?}" extra="${3:-{\}}"
  local name="${PROVISIONING_NAME:-?}"
  local ts; ts="$(now_iso)"

  # Recursion guard: if we get called from our own ERR trap, fall through.
  if [[ "$MARK_BROKEN_IN_PROGRESS" == "1" ]]; then
    printf '{"stage":"mark_broken","level":"fatal","msg":"mark_broken itself failed","origStage":"%s"}\n' "$stage" >&2
    exit 70
  fi
  export MARK_BROKEN_IN_PROGRESS=1

  # 1) Forensic floor — single-syscall append, immune to jq failures.
  mkdir -p "$LASTERROR_DIR" 2>/dev/null || true
  local forensic
  forensic=$(jq -nc \
    --arg ts "$ts" --arg name "$name" --arg stage "$stage" \
    --arg message "$message" --argjson extra "$extra" \
    '{ts:$ts,name:$name,stage:$stage,message:$message} + $extra' \
    2>/dev/null \
    || printf '{"ts":"%s","name":"%s","stage":"%s","message":"%s"}' \
       "$ts" "$name" "$stage" "${message//\"/\\\"}")
  printf '%s\n' "$forensic" >> "$LASTERROR_DIR/$name.lasterror" 2>/dev/null || true

  # 2) Atomic index update.
  if machine_exists "$name" 2>/dev/null; then
    index_update "$name" \
      ". + {status:\"broken\", lastError: ($forensic)}" \
      2>/dev/null || true
  fi

  # 3) Stdout outcome (single JSON doc, contract per spec §3).
  printf '%s\n' "$forensic"

  # 4) Stderr progress line.
  emit_progress error "$stage" "$message"

  exit 1
}

# Install ERR trap that funnels unexpected failures through mark_broken.
# Call this once from a script after `set -euo pipefail` and after
# PROVISIONING_NAME is set.
trap_unhandled_errors() {
  trap 'mark_broken "trap" "unexpected: $BASH_COMMAND"' ERR
}

# ── timeouts ─────────────────────────────────────────────────────────────────

# Run a command with a timeout. On expiry, emits a structured timeout
# error and calls mark_broken. Use as:
#     with_timeout 60 health-kimi -- ssh "$target" curl -fsS http://127.0.0.1:5494/healthz
with_timeout() {
  local secs="$1" stage="$2"
  shift 2
  if [[ "${1:-}" == "--" ]]; then shift; fi
  local rc=0
  # timeout(1) can only exec binaries, not shell functions. Callers like
  # ssh_run / ssh_pipe rely on ssh's own ConnectTimeout for liveness, so
  # for function targets we invoke directly and trust that bound.
  if [[ "$(type -t "$1" 2>/dev/null)" == "function" ]]; then
    "$@" || rc=$?
  else
    timeout --foreground "$secs" "$@" || rc=$?
  fi
  if [[ "$rc" == "124" || "$rc" == "137" ]]; then
    mark_broken "$stage" "timeout after ${secs}s" "{}"
  fi
  return "$rc"
}

# ── ssh helpers ──────────────────────────────────────────────────────────────

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

ssh_base_opts() {
  local name="$1"
  local host user key port sock
  host="$(machine_field "$name" "ssh.host")"
  user="$(machine_field "$name" "ssh.user")"
  key="$(machine_field "$name" "ssh.keyPath")"
  port="$(machine_field "$name" "ssh.port")"
  # Backwards-compat: older indexes used flat fields.
  [[ -z "$host" ]] && host="$(machine_field "$name" "host")"
  [[ -z "$user" ]] && user="$(machine_field "$name" "user")"
  [[ -z "$port" ]] && port="$(machine_field "$name" "port")"
  [[ -z "$port" ]] && port=22
  sock="$(ssh_sock "$name")"
  [[ -z "$host" ]] && die "$name: missing ssh.host"
  [[ -z "$user" ]] && die "$name: missing ssh.user"
  [[ -z "$key"  ]] && die "$name: missing ssh.keyPath"
  printf -- '-i\n%s\n-p\n%s\n-o\nConnectTimeout=5\n-o\nBatchMode=yes\n-o\nControlPath=%s\n' \
    "$key" "$port" "$sock"
}

ssh_target() {
  local name="$1"
  local user host
  user="$(machine_field "$name" "ssh.user")"
  host="$(machine_field "$name" "ssh.host")"
  [[ -z "$user" ]] && user="$(machine_field "$name" "user")"
  [[ -z "$host" ]] && host="$(machine_field "$name" "host")"
  printf '%s@%s' "$user" "$host"
}

# Run a command on the remote over the existing ControlMaster.
#     ssh_run osci-math -- uname -a
#     ssh_run osci-math -q -- systemctl --user is-active kimi.service
ssh_run() {
  local name="$1"; shift
  local quiet=0
  if [[ "${1:-}" == "-q" ]]; then quiet=1; shift; fi
  if [[ "${1:-}" == "--" ]]; then shift; fi
  local opts; mapfile -t opts < <(ssh_base_opts "$name")
  local target; target="$(ssh_target "$name")"
  if (( quiet )); then
    ssh "${opts[@]}" "$target" "$@" 2>/dev/null
  else
    ssh "${opts[@]}" "$target" "$@"
  fi
}

# Pipe a local script over ssh bash -s with explicit env propagation.
# Usage:
#     ssh_pipe osci-math --env KIMI_PORT=5494 --env PLANE_PORT=5495 \
#       -- "$SCRIPT_DIR/remote-stage.sh" arg1 arg2
ssh_pipe() {
  local name="$1"; shift
  local env_pairs=()
  while [[ "${1:-}" == "--env" ]]; do
    env_pairs+=("$2")
    shift 2
  done
  if [[ "${1:-}" == "--" ]]; then shift; fi
  local script="$1"; shift
  [[ -f "$script" ]] || die "ssh_pipe: script not found: $script"

  local opts; mapfile -t opts < <(ssh_base_opts "$name")
  local target; target="$(ssh_target "$name")"

  # Build inline env prefix for the remote shell. printf %q quotes safely.
  local env_prefix=""
  local kv
  for kv in "${env_pairs[@]}"; do
    local key="${kv%%=*}" val="${kv#*=}"
    env_prefix+=" $(printf '%s=%q' "$key" "$val")"
  done

  # Build positional args quoted for remote shell.
  local args_quoted=""
  local a
  for a in "$@"; do
    args_quoted+=" $(printf '%q' "$a")"
  done

  ssh "${opts[@]}" "$target" "${env_prefix# } bash -s --${args_quoted}" < "$script"
}

# Fetch tail of a remote log via a fresh SSH (works even if the original
# session was killed). Returns empty on failure.
remote_log_tail() {
  local name="$1" log_path="$2" lines="${3:-200}"
  ssh_run "$name" -q -- "tail -n $lines $log_path" 2>/dev/null || true
}

# Open a fresh remote log for this script invocation. Returns the remote
# path on stdout. The remote dir is created. Header line written.
log_open() {
  local name="$1" script="${2:-$SCRIPT_NAME}"
  local ts; ts="$(now_iso | tr ':' '-')"
  local remote_path="\$HOME/.openscientist/logs/${script}-${ts}.log"
  ssh_run "$name" -q -- "mkdir -p \$HOME/.openscientist/logs && \
    printf '== %s %s start\\n' '$script' '$ts' > $remote_path && \
    printf '%s\\n' '$remote_path'"
}
