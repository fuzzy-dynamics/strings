#!/usr/bin/env bash
# setup-claude.sh <machine> [--token TOKEN]
#
# Opt-in step after install.sh: puts the claude CLI on the remote and (if a
# token is provided) wires up headless OAuth. install.sh does NOT touch
# providers — each one is a separate script because the auth flow differs.
#
# Claude's interactive OAuth credentials (~/.claude/.credentials.json) hook
# into the OS keychain on the laptop and are not portable. The correct way to
# move a claude install to another machine is `claude setup-token`, which
# prints a long-lived CLAUDE_CODE_OAUTH_TOKEN for headless environments.
#
# Two-phase flow, because setup-token requires user action on the laptop:
#
#   1. `setup-claude.sh <machine>`
#        — installs the CLI on the remote and ensures systemd sees it on PATH
#        — records `installed: true, authed: false`
#        — prints instructions for step 2
#
#   2a. Headless path (agent-friendly):
#         On THIS laptop:  claude setup-token
#         Copy the token (format: sk-ant-oat01-...)
#         Back to the agent: setup-claude.sh <machine> --token <paste>
#
#   2b. Manual path: ssh into the remote, run `claude`, log in interactively.
#       The agent should offer both to the user and let them choose.
#
# With --token, the script scp's a small env file to
# ~/.openscientist/providers/claudecode.env, which the bundle's kimi.service
# and plane.service already pick up via `EnvironmentFile=-`. It also appends
# a ~/.bashrc loader so interactive SSH shells export the token too. Then
# kimi + plane are restarted so the new EnvironmentFile takes effect.
#
# Token is transferred via scp (encrypted), never via ssh argv — so it never
# appears in `ps` on either side.

source "$(dirname "$0")/_common.sh"
ensure_index

name=""
token=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --token) token="$2"; shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  [[ -z "$name" ]] && name="$1" || die "usage: setup-claude.sh <machine> [--token TOKEN]"; shift ;;
  esac
done
[[ -z "$name" ]] && die "usage: setup-claude.sh <machine> [--token TOKEN]"
[[ "$name" == "local" ]] && die 'setup-claude.sh is for remotes; "local" already has your claude install'
machine_exists "$name" || die "no such machine: $name — run add.sh first"

# Forgiving token input: user might paste "CLAUDE_CODE_OAUTH_TOKEN=sk-ant-..."
# or with surrounding quotes / trailing newline.
if [[ -n "$token" ]]; then
  token="${token#CLAUDE_CODE_OAUTH_TOKEN=}"
  token="${token%\"}"; token="${token#\"}"
  token="${token%\'}"; token="${token#\'}"
  token="${token%$'\r'}"; token="${token%$'\n'}"
fi

"$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"
sock="$(ssh_sock "$name")"
key="$(machine_field "$name" "ssh.keyPath")"
port="$(machine_field "$name" "port")"; [[ -z "$port" ]] && port=22

log "stage 1: ensure claude installed on remote"
ssh "${opts[@]}" "$target" bash -s <<'REMOTE'
set -e
export PATH="$HOME/.local/bin:$PATH"
if command -v claude >/dev/null 2>&1; then
  echo "[claude] already installed: $(command -v claude) ($(claude --version 2>/dev/null | head -1))"
  exit 0
fi
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found; Node.js/npm is a plane prerequisite — run install.sh first" >&2; exit 2; }
mkdir -p "$HOME/.local"
npm install -g --prefix "$HOME/.local" @anthropic-ai/claude-code
hash -r
ver="$("$HOME/.local/bin/claude" --version 2>/dev/null | head -1 || true)"
echo "[claude] installed: ${ver:-unknown}"
REMOTE

log "stage 2: ensure systemd units have ~/.local/bin on PATH"
ssh "${opts[@]}" "$target" bash -s <<'REMOTE'
set -e
for unit in kimi plane; do
  d="$HOME/.config/systemd/user/$unit.service.d"
  mkdir -p "$d"
  cat > "$d/path.conf" <<'CONF'
[Service]
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
CONF
done
systemctl --user daemon-reload
REMOTE

version="$(ssh "${opts[@]}" "$target" 'PATH="$HOME/.local/bin:$PATH" claude --version 2>/dev/null | head -1' || true)"
[[ -z "$version" ]] && die "claude installed but not callable on remote — check PATH"

probe_claude_auth() {
  # Runs `claude auth status --json` on the remote with the env file sourced,
  # returns "true" / "false" on stdout.
  ssh "${opts[@]}" "$target" '
    set -a
    [ -f "$HOME/.openscientist/providers/claudecode.env" ] && . "$HOME/.openscientist/providers/claudecode.env" 2>/dev/null
    set +a
    PATH="$HOME/.local/bin:$PATH" claude auth status --json 2>/dev/null
  ' | jq -r '.loggedIn // false' 2>/dev/null || printf 'false'
}

if [[ -z "$token" ]]; then
  ssh "${opts[@]}" "$target" 'systemctl --user restart kimi plane || true'

  # If the manager has an ephemeral CLAUDE_CODE_OAUTH_TOKEN but the env file is
  # missing, someone (an earlier agent run?) set it via `set-environment`.
  # That works for the current session but vanishes on reboot / daemon-reexec.
  # Surface it loudly so the agent can convert it to the durable file-based path.
  has_ephemeral=0
  has_file=0
  ssh "${opts[@]}" "$target" 'systemctl --user show-environment | grep -q "^CLAUDE_CODE_OAUTH_TOKEN="' 2>/dev/null && has_ephemeral=1
  ssh "${opts[@]}" "$target" 'test -s "$HOME/.openscientist/providers/claudecode.env"' 2>/dev/null && has_file=1
  if (( has_ephemeral && ! has_file )); then
    log ""
    log "WARNING: CLAUDE_CODE_OAUTH_TOKEN is set on the systemd user manager but"
    log "  ~/.openscientist/providers/claudecode.env is missing. That auth is"
    log "  EPHEMERAL — it will not survive reboot or \`systemctl --user daemon-reexec\`."
    log "  Rescue it by re-running this script with --token <the-value> so the env"
    log "  file is written. Retrieve the value via:"
    log "      ssh $name systemctl --user show-environment | grep CLAUDE_CODE_OAUTH_TOKEN"
    log ""
  fi

  # Probe anyway — user may have logged in manually on a previous run.
  authed="$(probe_claude_auth)"
  log "  claude auth status: loggedIn=$authed"
  [[ "$authed" == "true" ]] || authed=false

  write_index "$(jq_index --arg n "$name" --arg v "$version" --argjson a "$authed" \
    '.machines[$n].services.providers.claudecode = {installed: true, authed: $a, version: $v}')"

  if [[ "$authed" == "true" ]]; then
    log "claude ready on $name (version: $version, authed: yes — found existing login)"
    exit 0
  fi
  log ""
  log "claude installed on $name, but NOT yet authenticated."
  log ""
  log "Option A — headless (recommended for agent flows):"
  log "    1. On THIS laptop, run:  claude setup-token"
  log "    2. Copy the CLAUDE_CODE_OAUTH_TOKEN= value it prints."
  log "    3. Finish setup via:"
  log "         bash \$SCRIPTS/setup-claude.sh $name --token <paste-here>"
  log ""
  log "Option B — manual (user logs in themselves):"
  log "    ssh into $name and run \`claude\` to complete the interactive login,"
  log "    then re-run this script with no --token to re-probe and mark authed."
  log ""
  log "Either works. Pick whichever the user prefers."
  exit 0
fi

log "stage 3: ship OAuth token to remote (scp, never via ssh argv)"
tmp="$(mktemp)"; chmod 600 "$tmp"
trap 'rm -f "$tmp"' EXIT
printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$token" > "$tmp"

ssh "${opts[@]}" "$target" 'mkdir -p "$HOME/.openscientist/providers" && chmod 700 "$HOME/.openscientist/providers"'
scp -o ControlPath="$sock" -i "$key" -P "$port" -q "$tmp" "$target:.openscientist/providers/claudecode.env"
ssh "${opts[@]}" "$target" 'chmod 600 "$HOME/.openscientist/providers/claudecode.env"'

log "stage 4: append ~/.bashrc loader so interactive shells see the token"
ssh "${opts[@]}" "$target" bash -s <<'REMOTE'
set -e
rcfile="$HOME/.bashrc"
marker="# osci:claudecode-token"
if ! grep -qF "$marker" "$rcfile" 2>/dev/null; then
  {
    printf '\n%s\n' "$marker"
    printf 'if [ -f "$HOME/.openscientist/providers/claudecode.env" ]; then set -a; . "$HOME/.openscientist/providers/claudecode.env"; set +a; fi\n'
  } >> "$rcfile"
fi
REMOTE

log "stage 5: restart kimi + plane (pick up new EnvironmentFile)"
# Clear any ephemeral CLAUDE_CODE_OAUTH_TOKEN on the user manager first. If one
# was set via `systemctl --user set-environment` (e.g. a previous quick-fix),
# leaving it in place lets the services run on it in-memory and masks whether
# our durable env file is actually wired. Unsetting forces the restart below
# to depend solely on EnvironmentFile — so a successful auth probe in stage 6
# actually proves the file-based path works.
ssh "${opts[@]}" "$target" 'systemctl --user unset-environment CLAUDE_CODE_OAUTH_TOKEN 2>/dev/null || true; systemctl --user restart kimi plane || true'

log "stage 6: probe claude auth (verifies token actually works)"
authed="$(probe_claude_auth)"
[[ "$authed" == "true" ]] || authed=false
log "  claude auth status: loggedIn=$authed"

write_index "$(jq_index --arg n "$name" --arg v "$version" --argjson a "$authed" \
  '.machines[$n].services.providers.claudecode = {installed: true, authed: $a, version: $v}')"

if [[ "$authed" != "true" ]]; then
  log ""
  log "WARNING: token shipped, but claude auth status reports loggedIn=false."
  log "  The token may be stale or malformed. Re-run \`claude setup-token\` on the laptop,"
  log "  then re-invoke: setup-claude.sh $name --token <new-token>"
  exit 1
fi

log "claude ready on $name (version: $version, authed: yes)"
