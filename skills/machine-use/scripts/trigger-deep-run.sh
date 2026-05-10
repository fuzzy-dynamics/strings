#!/usr/bin/env bash
# trigger-deep-run.sh — spawn a deep-run orchestrator on the LOCAL plane.
#
# This script is local-frame only. It always creates a worktree on the host
# it's invoked on and POSTs to the local plane at $PLANE_SERVER_URL (default
# http://127.0.0.1:5495). There is no --machine flag.
#
# Cross-machine deep runs are orchestrated by Electron, which:
#   1. Calls ensureSpaceOnMachine (sync-space.sh) to materialize the space
#      repo on the remote.
#   2. SSH-execs this same script on the remote, against the remote
#      space worktree.
# In other words: each gecko sees only its own machine. The renderer is the
# one routing across hosts; the script never moves between them.
#
# Usage:
#   trigger-deep-run.sh --provider P --prompt X --path DIR \
#     [--agent A] [--title T] [--space-id S] \
#     [--spawned-by-session SID] [--spawned-by-role ROLE]
#
# Required:
#   --provider   gecko | claudecode | codex
#                (`gecko` is the built-in kimi-server orchestrator that
#                machine-setup/install.sh provisions on every machine. Legacy
#                aliases `kimi` and `openscientist-gecko` accepted; all
#                canonicalize to `kimi` in the wire payload because that's
#                the string plane validates on.)
#   --prompt     initial user prompt for the orchestrator
#   --path       absolute path to the host-local space root (must be inside
#                a git repo)
#
# Optional:
#   --agent              orchestrator agent name (default: "osci-orchestrator")
#   --title              run title shown in the runs sidebar
#   --space-id           backend space id used for skillsforspace sync
#   --spawned-by-session provenance: invoking session id
#   --spawned-by-role    provenance: invoking session role
#
# Output (stdout, single-line JSON):
#   { "orchestratorId": "...",
#     "sessionId":      "...",
#     "worktreePath":   "/abs/.openscientist/worktrees/<sid>",
#     "provider":       "...",
#     "branch":         "<branch or DETACHED>",
#     "dirty":          true|false }
#
# Stderr: human log of every step.
#
# Exit codes:
#   0   success
#   1   user/argument or environment error

set -euo pipefail

source "$(dirname "$0")/_common.sh"

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
    --agent)              agent="$2";    shift 2 ;;
    --title)              title="$2";    shift 2 ;;
    --space-id)           space_id="$2"; shift 2 ;;
    --spawned-by-session) spawned_by_session="$2"; shift 2 ;;
    --spawned-by-role)    spawned_by_role="$2";    shift 2 ;;
    --machine)
      die "--machine is not supported. Each gecko triggers deep runs only on its own host. For cross-machine deep runs, use the renderer (Electron orchestrates the SSH-exec)." ;;
    -*) die "unknown flag: $1" ;;
    *)  die "unexpected positional arg: $1" ;;
  esac
done

[[ -z "$provider" ]] && die "--provider is required"
[[ -z "$prompt"   ]] && die "--prompt is required"
[[ -z "$path"     ]] && die "--path is required"

# Canonicalize provider aliases. User-facing name is `gecko`; plane's wire
# format is `kimi`. claudecode/codex pass through verbatim.
case "$provider" in
  gecko|openscientist-gecko) provider="kimi" ;;
  kimi|claudecode|codex)     ;;
  *) die "--provider must be one of: gecko, claudecode, codex (got: $provider)" ;;
esac

session_id="$(rand_hex 4)"
log "provider=$provider session-id=$session_id agent=$agent path=$path"

# ---- 1) Resolve git root + create the per-session worktree -----------------

[[ -d "$path" ]] || die "path not a directory: $path"
abs_path="$(cd "$path" && pwd)"
repo_root="$(cd "$abs_path" && git rev-parse --show-toplevel 2>/dev/null)" || \
  die "not inside a git repo: $abs_path"
cd "$repo_root"

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo DETACHED)"
base_commit="$(git rev-parse HEAD 2>/dev/null)" || die "repo has no HEAD"

# Dirty-tree-safe snapshot. `git stash create` exits 0 with empty stdout when
# the tree is clean — fall through to HEAD in that case.
snapshot="$(git stash create 2>/dev/null || true)"
if [[ -n "$snapshot" ]]; then
  dirty="true"
else
  dirty="false"
  snapshot="$base_commit"
fi

wt_base="$HOME/.openscientist/worktrees"
mkdir -p "$wt_base"
worktree="$wt_base/$session_id"
[[ -e "$worktree" ]] && die "worktree path already exists: $worktree (pick a new session-id)"

log "worktree: $worktree @ ${snapshot:0:12} (dirty=$dirty) [detached]"
# --detach deliberately: the worktree shares this host's .git; naming a
# branch per session would pollute the host's branch list. The branch is
# created lazily on pull-back by fetch-session-branch.sh.
git worktree add --detach "$worktree" "$snapshot" >&2 || die "git worktree add failed"

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

# ---- 3) POST to the local plane --------------------------------------------

plane_url="${PLANE_SERVER_URL:-http://127.0.0.1:5495}"
log "posting to plane at $plane_url ..."
resp="$(curl -fsS -m 60 -X POST "$plane_url/orchestrator/start" \
  -H 'content-type: application/json' \
  --data-raw "$payload")" || die "plane POST failed (URL=$plane_url)"

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
  --arg provider  "$provider" \
  --arg branch    "$branch" \
  --argjson dirty "$dirty" \
  '{orchestratorId:$oid, sessionId:$sid, worktreePath:$wt,
    provider:$provider, branch:$branch, dirty:$dirty}'
