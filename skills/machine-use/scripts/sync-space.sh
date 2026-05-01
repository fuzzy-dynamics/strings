#!/usr/bin/env bash
# sync-space.sh <machine> --space-id S --path P
#
# Mirrors a space's local repo state into a per-space worktree on a remote
# machine. Idempotent — safe to call every time the user switches machines or
# starts a chat. First call materializes the worktree; subsequent calls do
# stash → reset --hard <new ref> → stash pop so any uncommitted remote-side
# work survives the sync.
#
# Reuses sync-repo.sh's bare-repo-per-(repo_id) layout: one bare per laptop
# repo per machine, content-addressed by sha256 of the laptop's absolute path.
# Deep runs and chat sessions for the same space share the same bare.
#
# Direction is one-way local → remote. Pull-back stays explicit via
# fetch-session-branch.sh / the UI's Checkout button (same as deep runs).
#
# Stdout (single-line JSON):
#   { "machine":          "<name>",
#     "spaceId":          "<id>",
#     "workDir":          "<remote spaces_root>/<space_id>",
#     "branch":           "osci-space/<space_id>",
#     "synced":           "<commit SHA pushed>",
#     "mode":             "create" | "update",
#     "stashHadConflict": true | false }
#
# Stderr: human log of each step.
#
# Exit codes:
#   0   success
#   1   user/argument error
#   2   environment error (no git repo, ssh unreachable, push failed, …)

source "$(dirname "$0")/_common.sh"
ensure_index

name=""
space_id=""
path=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --space-id) space_id="$2"; shift 2 ;;
    --path)     path="$2";     shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  [[ -z "$name" ]] && name="$1" || die "usage: sync-space.sh <machine> --space-id S --path P"
        shift ;;
  esac
done

[[ -z "$name" || -z "$space_id" || -z "$path" ]] && \
  die "usage: sync-space.sh <machine> --space-id S --path P"
[[ "$name" == "local" ]] && \
  die "sync-space.sh is for remote machines only; local syncs go through plane's sync-before-gecko-chat"
[[ "$space_id" =~ ^[A-Za-z0-9._-]+$ ]] || \
  die "space-id must match [A-Za-z0-9._-]+ (got: $space_id)"

machine_exists "$name" || die "no such machine: $name"

# Resolve git root from the given path
[[ -d "$path" ]] || die "path not a directory: $path"
abs_path="$(cd "$path" && pwd)"
repo_root="$(cd "$abs_path" && git rev-parse --show-toplevel 2>/dev/null)" || \
  die "not inside a git repo: $abs_path"
cd "$repo_root"

repo_id="$(printf '%s' "$repo_root" | sha256sum | head -c16)"
base_commit="$(git rev-parse HEAD 2>/dev/null)" || die "repo has no HEAD"

# Capture local working state (uncommitted changes included) — same trick as
# sync-repo.sh. `git stash create` exits 0 with empty stdout when clean.
snapshot="$(git stash create 2>/dev/null || true)"
[[ -z "$snapshot" ]] && snapshot="$base_commit"

# Ensure SSH master + read connection params
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
[[ -z "$remote_home" || "$remote_home" == "null" ]] && \
  die "remote.home not set in index.json; run install.sh $name first"

spaces_root="$(machine_field "$name" "remote.spacesRoot")"
if [[ -z "$spaces_root" || "$spaces_root" == "null" ]]; then
  # Fallback for machines installed before remote.spacesRoot was recorded.
  spaces_root="$remote_home/.openscientist/spaces"
fi

bare="$remote_home/.openscientist/repos/$repo_id/bare.git"
wt_path="$spaces_root/$space_id"
sync_ref="refs/heads/_osci-space/$space_id"
wt_branch="osci-space/$space_id"

log "repo_id=$repo_id  space=$space_id  snapshot=${snapshot:0:12}"
log "remote bare:     $bare"
log "remote worktree: $wt_path"

# 1) Ensure bare repo + spaces_root exist on remote (idempotent)
ssh "${opts[@]}" "$target" "
  set -e
  if [ ! -d '$bare' ]; then
    mkdir -p '$(dirname "$bare")'
    git init --bare --quiet '$bare'
  fi
  mkdir -p '$spaces_root'
" || die "failed to prepare remote bare/spaces dirs"

# 2) Push snapshot to a side ref on the bare. We deliberately push to
#    refs/heads/_osci-space/<space_id> rather than the worktree's own branch
#    (osci-space/<space_id>) so git never refuses to update a checked-out
#    branch. The remote step below moves the worktree onto the new commit.
if [[ "$port" == "22" ]]; then
  push_url="ssh://$user@$host$bare"
else
  push_url="ssh://$user@$host:$port$bare"
fi

log "git push -> $sync_ref"
GIT_SSH_COMMAND="ssh -o ControlPath=$sock -o ControlMaster=no -o BatchMode=yes" \
  git push --force --quiet "$push_url" "$snapshot:$sync_ref" || \
    die "git push failed"

# 3) Materialize / refresh the worktree on remote.
#    First call: `git worktree add -B …` creates everything.
#    Subsequent: stash any dirty remote state, point the worktree's branch at
#    the new commit, reset --hard, then pop the stash. If the pop conflicts,
#    leave it in `git stash list` for the user to inspect manually.
remote_script=$(cat <<'REMOTE'
set -e
bare="$1"
wt="$2"
sync_ref="$3"
wt_branch="$4"

if [ ! -d "$wt" ]; then
  mkdir -p "$(dirname "$wt")"
  git --git-dir="$bare" worktree add -B "$wt_branch" --quiet "$wt" "$sync_ref"
  printf 'mode=create\nstash=none\n'
  exit 0
fi

cd "$wt"

# `git stash create` works in detached / mid-rebase heads where `git stash
# push` doesn't, so we use the create+store pair.
stash_sha=""
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
  stash_sha="$(git stash create -u 2>/dev/null || true)"
  if [ -n "$stash_sha" ]; then
    git stash store -m "osci-sync $(date -u +%Y%m%dT%H%M%SZ)" "$stash_sha" >/dev/null 2>&1 || true
  fi
fi

# Move the worktree's branch onto the just-pushed ref, then reset --hard.
git update-ref "refs/heads/$wt_branch" "$sync_ref"
git checkout --quiet -B "$wt_branch" 2>/dev/null || true
git reset --hard --quiet "refs/heads/$wt_branch"
git clean -fd --quiet >/dev/null 2>&1 || true

stash_status="none"
if [ -n "$stash_sha" ]; then
  if git stash pop --quiet 2>/dev/null; then
    stash_status="popped"
  else
    stash_status="conflict"
    # Leave the stash in `git stash list` — user can inspect / resolve.
  fi
fi

printf 'mode=update\nstash=%s\n' "$stash_status"
REMOTE
)

probe_output="$(ssh "${opts[@]}" "$target" \
  bash -s -- "$bare" "$wt_path" "$sync_ref" "$wt_branch" \
  <<<"$remote_script")" || die "remote sync step failed"

mode=""
stash_status=""
while IFS='=' read -r key value; do
  case "$key" in
    mode)  mode="$value" ;;
    stash) stash_status="$value" ;;
  esac
done <<<"$probe_output"

stash_conflict="false"
[[ "$stash_status" == "conflict" ]] && stash_conflict="true"

log "remote $mode (stash=$stash_status)"

jq -n \
  --arg machine "$name" \
  --arg sid     "$space_id" \
  --arg wd      "$wt_path" \
  --arg br      "$wt_branch" \
  --arg sync    "$snapshot" \
  --arg mode    "$mode" \
  --argjson conflict "$stash_conflict" \
  '{machine:$machine, spaceId:$sid, workDir:$wd, branch:$br,
    synced:$sync, mode:$mode, stashHadConflict:$conflict}'
