#!/usr/bin/env bash
# exec.sh --sandbox <id> --command "<cmd>" [--workdir PATH] [--timeout N]
#     or: exec.sh --sandbox <id> [--workdir /path] -- <cmd and args...>
#
# Runs a shell command inside the named sandbox via `docker exec`.
#
# `--sandbox <id>` is REQUIRED. There's no global "active sandbox" anymore —
# multiple sandboxes can be running concurrently with different bind sets, and
# silently picking one would be wrong. Pass it explicitly.
#
# PWD transparency
#   By default, --workdir defaults to the caller's $PWD. So if you `cd` into a
#   path that's bind-mounted into the sandbox and run `exec.sh --sandbox X --
#   cat foo.txt`, the sandbox runs the command with cwd == your cwd. Relative
#   paths and shell redirects behave identically to native shell execution.
#
# Workdir gate
#   $PWD (or explicit --workdir) MUST fall under one of the target container's
#   actual bind-mount targets — read live via `docker inspect`. If it's not,
#   exec.sh refuses with exit 126. Silent fallback to the container's default
#   WORKDIR would make relative paths silently resolve somewhere you didn't
#   intend.
#
# Invocation forms
#   --command '<string>'   for anything that needs shell redirection/quoting (>, |, &&).
#   -- <argv...>           for simple argv (no redirection; quoting flattens).
#
# Exit codes
#   the command's exit code, EXCEPT:
#     124  timeout
#     125  sandbox container not running (run activate.sh)
#     126  bad args (non-absolute workdir, or workdir outside the container's bind set)
#     127  docker CLI unavailable
source "$(dirname "$0")/_common.sh"
ensure_index

cmd=""
workdir="$PWD"
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
usage: exec.sh --sandbox <id> --command "<cmd>" [--workdir /path] [--timeout N]
       exec.sh --sandbox <id> [--workdir /path] -- <cmd...>
EOF
      exit 2
      ;;
    *) die "unknown flag: $1 (use --command '<cmd>' or -- <cmd...>)" ;;
  esac
done

[[ -z "$target_id" ]] && die "--sandbox <id> is required (no global active sandbox; pass it explicitly)"
[[ -z "$cmd" ]] && die "usage: exec.sh --sandbox <id> --command '<cmd>' [...]"
sandbox_exists "$target_id" || die "no such sandbox: $target_id"

name="$(container_name "$target_id")"
container_running "$name" || { log "ERROR: container $name is not running (run: activate.sh $target_id)"; exit 125; }

# Reject non-absolute workdir (SPEC §9.3 — exit 126 for bad args).
if [[ -n "$workdir" ]]; then
  if [[ "$workdir" == "~"* || "$workdir" != /* ]]; then
    log "ERROR: workdir must be an absolute host path (got: $workdir)"
    exit 126
  fi
fi

# Workdir gate: must fall under one of the container's actual bind targets,
# read live (not the catalog — `binds[]` in index.json no longer reflects
# per-activation extras like a space root added via `activate.sh --mount`).
binds_for_target=()
while IFS= read -r b; do
  [[ -z "$b" ]] && continue
  binds_for_target+=("$b")
done < <(container_bindings "$name")

inside_any=false
for b in "${binds_for_target[@]:-}"; do
  if [[ "$workdir" == "$b" || "$workdir" == "$b"/* ]]; then
    inside_any=true
    break
  fi
done

if [[ "$inside_any" != true ]]; then
  {
    printf '\n'
    printf '╔══════════════════════════════════════════════════════════════════════╗\n'
    printf '║  SANDBOX REFUSED — WORKING DIRECTORY IS OUTSIDE THE CONTAINER MOUNTS ║\n'
    printf '╚══════════════════════════════════════════════════════════════════════╝\n'
    printf '  Sandbox:         %s\n' "$target_id"
    printf '  Your cwd:        %s\n' "$workdir"
    printf '  Container binds:\n'
    if [[ ${#binds_for_target[@]} -eq 0 ]]; then
      printf '    (none — container missing or no bind mounts)\n'
    else
      for b in "${binds_for_target[@]}"; do printf '    • %s\n' "$b"; done
    fi
    printf '\n'
    printf '  Any path outside those binds does not exist inside the container,\n'
    printf '  so relative paths would silently resolve against the wrong place.\n'
    printf '\n'
    printf '  To use the sandbox from this agent:\n'
    printf '    • cd into a path under one of the binds above, OR\n'
    printf '    • activate.sh %s --mount %s   (then retry)\n' "$target_id" "$workdir"
    printf '\n'
    printf '  This is a hard constraint of the sandbox design, not a bug.\n'
    printf '  See: sandbox-use/SKILL.md §"Workdir gate".\n'
    printf '\n'
  } >&2
  exit 126
fi

args=(exec)
[[ -n "$workdir" ]] && args+=(--workdir "$workdir")
args+=("$name" sh -c "$cmd")

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
