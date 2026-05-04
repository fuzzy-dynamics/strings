#!/usr/bin/env bash
# fetch-session-branch.sh --session-id SID --path LAPTOP_REPO [--machine NAME] [--branch NAME]
#
# "Claim" a deep run's result by making its commits addressable via a named
# branch on the laptop. This is the single primitive the pull-back flow calls;
# it handles both local and remote runs uniformly from the caller's side.
#
# Local runs (machine == "local"):
#   Local worktrees are detached by design — we don't create `osci/<sid>`
#   at spawn time because that would flood the user's branch list. This
#   script is the opt-in promotion: it asks plane for the session's current
#   worktree HEAD (via POST /sessions/<sid>/branch), then runs
#   `git branch -f osci/<sid> <sha>` in the laptop repo. The laptop already
#   has the commit objects (the worktree shares .git), so no data moves —
#   only the ref is created. Runs the user never claims stay detached and
#   eventually GC away when their worktrees are removed.
#
# Remote runs:
#   Fetches the `osci/<sid>` branch from the remote bare into the laptop's
#   .git, using the existing ControlMaster socket (same transport as
#   sync-repo.sh). The remote worktree is already on that branch by design —
#   no promotion step on the remote side is needed.
#
# After this script succeeds, the caller runs:
#   git -C "$LAPTOP_REPO" checkout osci/<sid>
# to put the run's result into the user's working tree.
#
# Stdout (single-line JSON):
#   { "machine":    "<name>",
#     "sessionId":  "<sid>",
#     "branch":     "osci/<sid>",
#     "bareUrl":    "<ssh url>" | null,          // null for local
#     "fetched":    true|false,
#     "localRef":   "refs/heads/osci/<sid>",
#     "sha":        "<head sha>" }
#
# Stderr: human log.

source "$(dirname "$0")/_common.sh"
ensure_index

session_id=""
path=""
machine=""
branch=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session-id) session_id="$2"; shift 2 ;;
    --path)       path="$2";       shift 2 ;;
    --machine)    machine="$2";    shift 2 ;;
    --branch)     branch="$2";     shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  die "unexpected positional arg: $1" ;;
  esac
done

[[ -z "$session_id" ]] && die "--session-id is required"
[[ -z "$path"       ]] && die "--path is required (the laptop repo root)"
[[ -d "$path/.git" || -f "$path/.git" ]] || die "$path is not a git repo"
[[ -z "$machine" ]] && machine="$(active_machine)"
[[ -z "$branch"  ]] && branch="osci/$session_id"

abs_path="$(cd "$path" && pwd)"
repo_id="$(printf '%s' "$abs_path" | sha256sum | head -c16)"

emit() {
  local bare="${1:-}" fetched="${2:-false}" sha="${3:-}"
  jq -n \
    --arg machine  "$machine" \
    --arg sid      "$session_id" \
    --arg branch   "$branch" \
    --arg bareUrl  "$bare" \
    --argjson fetched "$fetched" \
    --arg localRef "refs/heads/$branch" \
    --arg sha      "$sha" \
    '{machine:$machine, sessionId:$sid, branch:$branch,
      bareUrl: ($bareUrl | if . == "" then null else . end),
      fetched:$fetched, localRef:$localRef,
      sha: ($sha | if . == "" then null else . end)}'
}

# ---- local: promote detached HEAD into the `osci/<sid>` branch ------------
# The laptop's .git already has the worktree's commit objects (shared store);
# we just need to create a named ref pointing at them so the caller can
# `git checkout osci/<sid>` afterwards. We ask plane for the current HEAD
# sha rather than poking ~/.openscientist/worktrees/<sid>/.git directly
# because plane is the canonical source-of-truth for session state.
if [[ "$machine" == "local" ]]; then
  [[ -n "${PLANE_SERVER_URL:-}" ]] || die "PLANE_SERVER_URL is unset — Electron main and kimi-server both export it; if you're running this by hand, set it explicitly (no fallback to 127.0.0.1:5495, since dev setups may bind elsewhere)"

  log "querying plane for session worktree HEAD: $PLANE_SERVER_URL/sessions/$session_id/branch"
  branch_resp="$(curl -fsS -m 10 -X POST "$PLANE_SERVER_URL/sessions/$session_id/branch" 2>/dev/null)" || \
    die "plane /sessions/$session_id/branch failed (is plane running? is the session id correct?)"

  sha="$(printf '%s' "$branch_resp" | jq -r '.sha // empty')"
  [[ -n "$sha" ]] || die "plane response had no .sha: $branch_resp"

  log "promoting: git branch -f $branch $sha (in $abs_path)"
  git -C "$abs_path" branch -f "$branch" "$sha" >&2 || \
    die "git branch -f failed — the commit $sha may not be reachable from the laptop's .git (unexpected for a local run; check worktree integrity)"

  emit "" true "$sha"
  exit 0
fi

# ---- remote: fetch from the machine's bare via ControlMaster --------------
machine_exists "$machine" || die "no such machine: $machine"

if ! ssh_master_alive "$machine"; then
  log "ControlMaster down; reopening ..."
  "$(dirname "$0")/reconnect-ssh.sh" "$machine" >/dev/null
fi

sock="$(ssh_sock "$machine")"
host="$(machine_field "$machine" "ssh.host")"; [[ -z "$host" ]] && host="$(machine_field "$machine" "host")"
user="$(machine_field "$machine" "ssh.user")"; [[ -z "$user" ]] && user="$(machine_field "$machine" "user")"
port="$(machine_field "$machine" "ssh.port")"; [[ -z "$port" ]] && port="$(machine_field "$machine" "port")"; [[ -z "$port" ]] && port=22
remote_home="$(machine_field "$machine" "remote.home")"
[[ -z "$remote_home" ]] && die "no remote.home cached for $machine — run sync-repo.sh once first"

bare="$remote_home/.openscientist/repos/$repo_id/bare.git"
if [[ "$port" == "22" ]]; then
  bare_url="ssh://$user@$host$bare"
else
  bare_url="ssh://$user@$host:$port$bare"
fi

log "fetching $branch from $bare_url (via ControlMaster $sock)"
GIT_SSH_COMMAND="ssh -o ControlPath=$sock -o ControlMaster=no -o BatchMode=yes" \
  git -C "$abs_path" fetch --force "$bare_url" "$branch:$branch" >&2 || \
    die "git fetch failed"

sha="$(git -C "$abs_path" rev-parse "$branch" 2>/dev/null || true)"
emit "$bare_url" true "$sha"
