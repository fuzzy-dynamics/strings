#!/usr/bin/env bash
# exec.sh --command "<cmd>" [--workdir PATH] [--timeout N] [--sandbox ID]
#     or: exec.sh [--workdir /path] -- <cmd and args...>
#
# Runs a shell command inside the active sandbox via `docker exec`.
#
# PWD transparency
#   By default, --workdir defaults to the caller's $PWD. So if you `cd` into a
#   worktree under ~/.openscientist and run `exec.sh -- cat foo.txt`, the sandbox
#   runs the command with its cwd == your cwd. Relative paths and shell redirects
#   behave identically to native shell execution.
#
#   REQUIREMENT: your $PWD (or explicit --workdir) MUST be under the sandbox mount
#   (defaults to ~/.openscientist). If it's not, exec.sh refuses with exit 126.
#   This is deliberate — silent fallback to the container's default WORKDIR would
#   make relative paths silently resolve somewhere you didn't intend.
#
# Invocation forms
#   --command '<string>'   for anything that needs shell redirection/quoting (>, |, &&).
#   -- <argv...>           for simple argv (no redirection; quoting flattens).
#
# Exit codes
#   the command's exit code, EXCEPT:
#     124  timeout
#     125  sandbox container not running (run activate.sh)
#     126  bad args (non-absolute workdir, or workdir outside the sandbox mount)
#     127  docker CLI unavailable
source "$(dirname "$0")/_common.sh"
ensure_index

cmd=""
workdir="$PWD"                                  # default: run as-though-from caller's cwd
timeout_s=120
target_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --command)  cmd="$2"; shift 2 ;;
    --workdir)  workdir="$2"; shift 2 ;;
    --timeout)  timeout_s="$2"; shift 2 ;;
    --sandbox)  target_id="$2"; shift 2 ;;
    --)         shift; cmd="$*"; break ;;
    -h|--help)
      cat <<EOF >&2
usage: exec.sh --command "<cmd>" [--workdir /path] [--timeout N] [--sandbox ID]
       exec.sh [--workdir /path] -- <cmd...>
EOF
      exit 2
      ;;
    *) die "unknown flag: $1 (use --command '<cmd>' or -- <cmd...>)" ;;
  esac
done

[[ -z "$cmd" ]] && die "usage: exec.sh --command '<cmd>' [--workdir PATH] [--timeout N]"

# Reject non-absolute workdir (SPEC §9.3 — exit 126 for bad args).
if [[ -n "$workdir" ]]; then
  if [[ "$workdir" == "~"* || "$workdir" != /* ]]; then
    log "ERROR: workdir must be an absolute host path (got: $workdir)"
    exit 126
  fi
fi

# Reject workdirs outside the sandbox mount — silent fallback to the container's
# default WORKDIR would hide "your files aren't where you think" from the caller.
# HOST_MOUNT is exported by _common.sh (defaults to ${SPOT_HOST_MOUNT:-$HOME/.openscientist}).
if [[ -n "$workdir" && "$workdir" != "$HOST_MOUNT" && "$workdir" != "$HOST_MOUNT"/* ]]; then
  {
    printf '\n'
    printf '╔══════════════════════════════════════════════════════════════════════╗\n'
    printf '║  SANDBOX REFUSED — WORKING DIRECTORY IS OUTSIDE THE SANDBOX MOUNT    ║\n'
    printf '╚══════════════════════════════════════════════════════════════════════╝\n'
    printf '  Your cwd:        %s\n' "$workdir"
    printf '  Sandbox mount:   %s\n' "$HOST_MOUNT"
    printf '\n'
    printf '  The sandbox only bind-mounts %s. Any path outside\n' "$HOST_MOUNT"
    printf '  that tree does not exist inside the container, so relative paths\n'
    printf '  would silently resolve against the wrong place.\n'
    printf '\n'
    printf '  To use the sandbox from this agent:\n'
    printf '    • Move the working files under %s/ and cd there, OR\n' "$HOST_MOUNT"
    printf '    • Pass --workdir with a path under %s/.\n' "$HOST_MOUNT"
    printf '\n'
    printf '  This is a hard constraint of the sandbox design, not a bug.\n'
    printf '  See: sandbox-use/SKILL.md §"Where you can run the skill".\n'
    printf '\n'
  } >&2
  exit 126
fi

if [[ -z "$target_id" ]]; then
  target_id="$(active_sandbox)"
  [[ -z "$target_id" ]] && { log "ERROR: no active sandbox — run activate.sh <id> first"; exit 1; }
fi
sandbox_exists "$target_id" || die "no such sandbox: $target_id"

name="$(container_name "$target_id")"
container_running "$name" || { log "ERROR: container $name is not running"; exit 125; }

args=(exec)
[[ -n "$workdir" ]] && args+=(--workdir "$workdir")
args+=("$name" sh -c "$cmd")

write_index "$(jq_index --arg n "$target_id" --arg t "$(now_iso)" '.sandboxes[$n].last_used_at = $t')"

if command -v timeout >/dev/null 2>&1 && [[ "$timeout_s" -gt 0 ]]; then
  set +e
  timeout --signal=KILL "$timeout_s" docker "${args[@]}"
  rc=$?
  set -e
  [[ $rc -eq 137 ]] && rc=124
  exit $rc
else
  exec docker "${args[@]}"
fi
