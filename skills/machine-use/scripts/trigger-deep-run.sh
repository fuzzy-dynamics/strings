#!/usr/bin/env bash
# trigger-deep-run.sh — unified deep-run spawn for local and remote machines.
#
# THIS IS THE ONLY CORRECT WAY TO SPAWN A DEEP RUN. Both the gecko agent
# (via Shell) and Electron main (via child_process, for UI-initiated runs)
# invoke this script. It owns worktree preparation end-to-end — callers must
# never materialize worktrees themselves.
#
# Usage:
#   trigger-deep-run.sh --provider P --prompt X --path DIR \
#     [--machine M] [--agent A] [--title T] [--space-id S]
#
# Required:
#   --provider   gecko | claudecode | codex
#                (`gecko` is the built-in kimi-server orchestrator that
#                install.sh already provisions on every machine — no separate
#                CLI to install. Legacy aliases accepted: `kimi`,
#                `openscientist-gecko`; all canonicalize to `kimi` in the wire
#                payload because that's the string plane validates on.)
#   --prompt     initial user prompt for the orchestrator (pass via file or
#                quoted string — remember shell escaping if from a CLI caller)
#   --path       laptop-absolute path to the space root (must be inside a git repo)
#
# Optional:
#   --machine    machine id from index.json; defaults to currently active.
#                Reserved name "local" spawns on the laptop.
#   --agent      orchestrator agent name (default: "osci-orchestrator")
#   --title      human-readable title displayed in the runs sidebar
#   --space-id   backend space id used for skillsforspace sync
#
# Output (stdout, single-line JSON):
#   {
#     "orchestratorId": "...",
#     "sessionId":      "...",
#     "worktreePath":   "/home/.../worktrees/<sid>",
#     "machine":        "<name>",
#     "provider":       "...",
#     "branch":         "<branch or DETACHED>",
#     "dirty":          true|false
#   }
#
# Stderr: human log of every step (sync, push, spawn). Safe to stream to UI.
#
# Exit codes:
#   0   success
#   1   user/argument error
#   2   environment error (no git repo, ssh unreachable, plane unhealthy)

source "$(dirname "$0")/_common.sh"
ensure_index

rand_hex() {
  local bytes="${1:-4}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  elif [[ -r /dev/urandom ]]; then
    od -An -N"$bytes" -tx1 /dev/urandom | tr -d ' \n'
  else
    die "no source of randomness available (no openssl, no /dev/urandom)"
  fi
}

provider=""
prompt=""
path=""
machine=""
agent="osci-orchestrator"
title=""
space_id=""
spawned_by_session=""
spawned_by_role=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)           provider="$2"; shift 2 ;;
    --prompt)             prompt="$2";   shift 2 ;;
    --path)               path="$2";     shift 2 ;;
    --machine)            machine="$2";  shift 2 ;;
    --agent)              agent="$2";    shift 2 ;;
    --title)              title="$2";    shift 2 ;;
    --space-id)           space_id="$2"; shift 2 ;;
    # Provenance — who invoked this run. Used for filtering "my runs" later.
    # Agents should pass their own session id; UI launchers can pass "ui".
    --spawned-by-session) spawned_by_session="$2"; shift 2 ;;
    --spawned-by-role)    spawned_by_role="$2";    shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  die "unexpected positional arg: $1" ;;
  esac
done

[[ -z "$provider" ]] && die "--provider is required"
[[ -z "$prompt"   ]] && die "--prompt is required"
[[ -z "$path"     ]] && die "--path is required"

# Canonicalize provider aliases. User-facing name is `gecko`; plane's wire
# format is still `kimi` (deep backend — deliberately untouched). If either an
# agent or the UI passes `gecko` / `openscientist-gecko`, rewrite it before
# the POST so plane sees what it expects.
case "$provider" in
  gecko|openscientist-gecko) provider="kimi" ;;
esac

[[ "$provider" =~ ^(claudecode|codex|kimi)$ ]] || \
  die "--provider must be one of: gecko, claudecode, codex (got: $provider)"

[[ -z "$machine" ]] && machine="$(active_machine)"

if [[ "$machine" != "local" ]] && ! machine_exists "$machine"; then
  die "no such machine: $machine"
fi

session_id="$(rand_hex 4)"

log "machine=$machine provider=$provider session-id=$session_id agent=$agent"

# ---- 1) Sync + create worktree (uniform for local and remote) --------------

SCRIPTS_DIR="$(dirname "$0")"
sync_out="$("$SCRIPTS_DIR/sync-repo.sh" "$machine" --path "$path" --session-id "$session_id")" || \
  die "sync-repo.sh failed (see stderr above)"

worktree="$(jq -r '.worktreePath // empty' <<<"$sync_out")"
branch="$(jq -r '.branch // "DETACHED"' <<<"$sync_out")"
dirty="$(jq -r '.dirty // false' <<<"$sync_out")"
[[ -z "$worktree" ]] && die "sync-repo.sh produced no worktreePath"
log "worktree: $worktree (branch=$branch dirty=$dirty)"

# ---- 2) Build plane payload -------------------------------------------------

payload="$(jq -n \
  --arg provider     "$provider" \
  --arg prompt       "$prompt" \
  --arg folder       "$worktree" \
  --arg spaceFolder  "$path" \
  --arg agent        "$agent" \
  --arg title        "$title" \
  --arg spaceId      "$space_id" \
  --arg spawnedBySession "$spawned_by_session" \
  --arg spawnedByRole    "$spawned_by_role" \
  '{
    provider:$provider, prompt:$prompt, folder:$folder, worktree:$folder,
    spaceFolder:$spaceFolder,
    agent:$agent, title:$title, spaceId:$spaceId,
    spawnedBy: (
      if $spawnedBySession != "" or $spawnedByRole != "" then
        { sessionId: ($spawnedBySession | if . == "" then null else . end),
          role:      ($spawnedByRole    | if . == "" then null else . end) }
      else null end
    )
  } | with_entries(select(.value != null and .value != ""))')"

# ---- 3) POST to plane -------------------------------------------------------
# Local: direct curl to laptop's plane.
# Remote: SSH-exec curl from inside the remote — uses the existing
# ControlMaster as the transport. No dependency on Electron's dynamically
# allocated LocalForward ports; the script works even if renderer isn't up.

if [[ "$machine" == "local" ]]; then
  [[ -n "${PLANE_SERVER_URL:-}" ]] || die "PLANE_SERVER_URL is unset (Electron main and kimi-server both export it; if you're running this by hand, set it explicitly — no fallback to 127.0.0.1:5495)"
  log "posting to local plane at $PLANE_SERVER_URL ..."
  resp="$(curl -fsS -m 60 -X POST "$PLANE_SERVER_URL/orchestrator/start" \
    -H 'content-type: application/json' \
    --data-raw "$payload")" || die "local plane POST failed"
else
  log "posting to plane on $machine via SSH ControlMaster ..."
  if ! ssh_master_alive "$machine"; then
    log "ControlMaster down; reopening ..."
    "$SCRIPTS_DIR/reconnect-ssh.sh" "$machine" >/dev/null
  fi
  mapfile -t opts < <(ssh_base_opts "$machine")
  target="$(ssh_target "$machine")"
  resp="$(ssh "${opts[@]}" "$target" \
    "curl -fsS -m 60 -X POST http://127.0.0.1:5495/orchestrator/start \
     -H 'content-type: application/json' --data @-" <<<"$payload")" || \
    die "remote plane POST failed"
fi

# Validate plane's response is JSON and has an orchestrator id.
if ! jq -e '.' <<<"$resp" >/dev/null 2>&1; then
  die "plane returned non-JSON response: $resp"
fi

orch_id="$(jq -r '.orchestratorId // .orchestrator_id // .id // empty' <<<"$resp")"
root_sid="$(jq -r '.sessionId // .session_id // empty' <<<"$resp")"
[[ -z "$orch_id" ]] && die "plane response missing orchestratorId: $resp"

log "spawned: orchestrator=$orch_id session=${root_sid:-<unknown>}"

# ---- 4) Emit consolidated JSON ----------------------------------------------

jq -n \
  --arg oid       "$orch_id" \
  --arg sid       "${root_sid:-$session_id}" \
  --arg wt        "$worktree" \
  --arg machine   "$machine" \
  --arg provider  "$provider" \
  --arg branch    "$branch" \
  --argjson dirty "$dirty" \
  '{orchestratorId:$oid, sessionId:$sid, worktreePath:$wt,
    machine:$machine, provider:$provider, branch:$branch, dirty:$dirty}'
