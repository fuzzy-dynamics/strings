#!/usr/bin/env bash
# sync-repo.sh <machine> --path P --session-id SID
#
# Prepares a fresh worktree for a deep run, on the local machine or a remote.
# Must be called immediately before POST /orchestrator/start so plane sees an
# already-materialized worktree path.
#
# For machine == "local":
#   Creates ~/.openscientist/worktrees/<SID> from a dirty-tree-safe snapshot of
#   the current working tree (uncommitted changes included). No network I/O.
#
# For a remote machine:
#   1. Ensures a shared bare repo exists at
#      $REMOTE_HOME/.openscientist/repos/<repo_id>/bare.git
#      where repo_id = sha256(absolute_laptop_path)[:16]. One bare per repo per
#      machine; subsequent runs reuse it.
#   2. Captures current index+working tree with `git stash create` (floating
#      commit, does not touch branches). Falls back to HEAD if the tree is clean.
#   3. Git-pushes that SHA to refs/heads/_osci-session/<SID> on the bare. Uses
#      GIT_SSH_COMMAND with the existing ControlMaster socket — no new SSH
#      handshake, only an exec channel on the already-authenticated connection.
#   4. `git worktree add -B osci/<SID>` on the remote to materialize
#      $REMOTE_HOME/.openscientist/worktrees/<SID> on a named branch. Commits
#      made inside the worktree move the branch; pulling back is then a simple
#      `git fetch bare osci/<SID>:osci/<SID>` on the laptop.
#
# Local vs remote branching is ASYMMETRIC on purpose:
#   - Remote worktrees live inside `~/.openscientist/repos/<id>/bare.git`, a
#     bare repo that has its own branch namespace isolated from the laptop. A
#     named branch per session there costs nothing — no laptop pollution.
#   - Local worktrees share `.git` with the user's main working tree. Naming
#     a branch per session would accumulate hundreds of `osci/<SID>` refs in
#     the user's branch list over time. So local worktrees are detached by
#     default; the `osci/<SID>` branch is created LAZILY on pull-back
#     (`fetch-session-branch.sh`) — only for runs the user explicitly claims.
#
# Stdout (single-line JSON):
#   { "repoId":       "abc1234...",
#     "worktreePath": "/home/.../openscientist/worktrees/<SID>",
#     "sessionId":    "<SID>",
#     "baseCommit":   "<HEAD SHA>",
#     "branch":       "<laptop branch or 'DETACHED'>",
#     "dirty":        true|false,
#     "machine":      "<name>" }
#
# Stderr: human log of each step.
#
# Idempotent in the happy case: a re-run with the same SID against an existing
# worktree path will fail fast with a clear message (pick a new SID).

source "$(dirname "$0")/_common.sh"
ensure_index

name=""
path=""
session_id=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)       path="$2";       shift 2 ;;
    --session-id) session_id="$2"; shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  [[ -z "$name" ]] && name="$1" || die "usage: sync-repo.sh <machine> --path P --session-id SID"
        shift ;;
  esac
done

[[ -z "$name" || -z "$path" || -z "$session_id" ]] && \
  die "usage: sync-repo.sh <machine> --path P --session-id SID"

[[ "$session_id" =~ ^[A-Za-z0-9._-]+$ ]] || \
  die "session-id must match [A-Za-z0-9._-]+ (got: $session_id)"

# Resolve git root from the given path
[[ -d "$path" ]] || die "path not a directory: $path"
abs_path="$(cd "$path" && pwd)"
repo_root="$(cd "$abs_path" && git rev-parse --show-toplevel 2>/dev/null)" || \
  die "not inside a git repo: $abs_path"
cd "$repo_root"

repo_id="$(printf '%s' "$repo_root" | sha256sum | head -c16)"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo DETACHED)"
base_commit="$(git rev-parse HEAD 2>/dev/null)" || die "repo has no HEAD"

# Dirty-tree-safe snapshot. `git stash create` exits 0 with empty stdout when
# the tree is clean — fall through to HEAD in that case.
snapshot="$(git stash create 2>/dev/null || true)"
dirty="false"
if [[ -n "$snapshot" ]]; then
  dirty="true"
else
  snapshot="$base_commit"
fi

emit_json() {
  local wt="$1"
  jq -n \
    --arg repoId    "$repo_id" \
    --arg wt        "$wt" \
    --arg sid       "$session_id" \
    --arg base      "$base_commit" \
    --arg br        "$branch" \
    --argjson dirty "$dirty" \
    --arg machine   "$name" \
    '{repoId:$repoId, worktreePath:$wt, sessionId:$sid,
      baseCommit:$base, branch:$br, dirty:$dirty, machine:$machine}'
}

# ---- local path ------------------------------------------------------------

if [[ "$name" == "local" ]]; then
  wt_base="$HOME/.openscientist/worktrees"
  mkdir -p "$wt_base"
  wt_path="$wt_base/$session_id"
  [[ -e "$wt_path" ]] && die "worktree path already exists: $wt_path (pick a new session-id)"

  log "local worktree: $wt_path @ ${snapshot:0:12} (dirty=$dirty) [detached]"
  # --detach deliberately. Local worktrees share the laptop's .git; naming a
  # branch per session would pollute the user's branch list. The branch is
  # created lazily on pull-back by fetch-session-branch.sh, only for runs the
  # user explicitly claims. See the file-header comment for rationale.
  git worktree add --detach "$wt_path" "$snapshot" >&2 || \
    die "git worktree add failed"

  emit_json "$wt_path"
  exit 0
fi

# ---- remote path -----------------------------------------------------------

machine_exists "$name" || die "no such machine: $name"

if ! ssh_master_alive "$name"; then
  log "ControlMaster down; reopening ..."
  "$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null
fi

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"
sock="$(ssh_sock "$name")"
host="$(machine_field "$name" "host")"
user="$(machine_field "$name" "user")"
port="$(machine_field "$name" "port")"; [[ -z "$port" ]] && port=22

remote_home="$(machine_field "$name" "remote.home")"
if [[ -z "$remote_home" || "$remote_home" == "null" ]]; then
  remote_home="$(ssh "${opts[@]}" "$target" 'printf %s "$HOME"')"
  [[ -z "$remote_home" ]] && die "could not resolve remote \$HOME"
  # Cache it for next time
  write_index "$(jq_index --arg n "$name" --arg h "$remote_home" \
    '.machines[$n].remote.home = $h')"
fi

bare="$remote_home/.openscientist/repos/$repo_id/bare.git"
wt_path="$remote_home/.openscientist/worktrees/$session_id"
ref="refs/heads/_osci-session/$session_id"

log "repo_id=$repo_id  branch=$branch  dirty=$dirty"
log "remote bare: $bare"
log "remote worktree: $wt_path"

# 1) Ensure bare repo exists (idempotent)
ssh "${opts[@]}" "$target" "
  set -e
  if [ ! -d '$bare' ]; then
    mkdir -p '$(dirname "$bare")'
    git init --bare --quiet '$bare'
  fi
" || die "failed to prepare bare repo on remote"

# 2) Push the snapshot to the per-session ref, over the multiplexed master.
#    -o ControlMaster=no → we're joining an existing master, not creating one.
#    Port goes into the URL so we don't need -p in GIT_SSH_COMMAND.
if [[ "$port" == "22" ]]; then
  push_url="ssh://$user@$host$bare"
else
  push_url="ssh://$user@$host:$port$bare"
fi

log "git push $push_url  $ref"
GIT_SSH_COMMAND="ssh -o ControlPath=$sock -o ControlMaster=no -o BatchMode=yes" \
  git push --force --quiet "$push_url" "$snapshot:$ref" || \
    die "git push failed"

# 3) Materialize the worktree on remote from that ref
ssh "${opts[@]}" "$target" "
  set -e
  if [ -e '$wt_path' ]; then
    echo 'worktree path already exists on remote; pick a new session-id' >&2
    exit 1
  fi
  mkdir -p '$(dirname "$wt_path")'
  git --git-dir='$bare' worktree add -B 'osci/$session_id' --quiet '$wt_path' '$ref'
" || die "remote worktree add failed at $wt_path"

emit_json "$wt_path"
