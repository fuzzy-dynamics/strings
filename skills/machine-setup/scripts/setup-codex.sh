#!/usr/bin/env bash
# setup-codex.sh <machine>
#
# Opt-in step after install.sh: puts the codex CLI on the remote and ships the
# laptop's ~/.codex/ over so it's authed as the same user. install.sh does NOT
# touch providers — each one is a separate script because the auth flow differs.
#
# How it works:
#   1. On the remote: `npm install -g --prefix ~/.local @openai/codex` if
#      codex isn't already on PATH. User-prefix install → no sudo.
#   2. Drop a systemd drop-in so kimi/plane units see ~/.local/bin on PATH.
#      (Without this, kimi-server can find the binary when spawning codex but
#      exec fails because systemd-user PATH is minimal by default.)
#   3. rsync -az --delete ~/.codex/ → remote ~/.codex/ (auth.json + config.toml
#      + whatever else codex writes). Codex reads auth from this dir on every
#      invocation, so no restart is needed for the auth itself.
#   4. Restart kimi + plane so the new PATH drop-in takes effect.
#   5. Record providers.codex in index.json.
#
# Idempotent — re-run to refresh auth after a codex `login` on the laptop.

source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: setup-codex.sh <machine>"
[[ "$name" == "local" ]] && die 'setup-codex.sh is for remotes; "local" already has your ~/.codex/'
machine_exists "$name" || die "no such machine: $name — run add.sh first"
[[ -d "$HOME/.codex" ]] || die "no ~/.codex on this laptop — log in to codex here first"

"$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"
sock="$(ssh_sock "$name")"
key="$(machine_field "$name" "ssh.keyPath")"
port="$(machine_field "$name" "port")"; [[ -z "$port" ]] && port=22

log "stage 1: ensure codex installed on remote"
ssh "${opts[@]}" "$target" bash -s <<'REMOTE'
set -e
export PATH="$HOME/.local/bin:$PATH"
if command -v codex >/dev/null 2>&1; then
  echo "[codex] already installed: $(command -v codex) ($(codex --version 2>/dev/null | head -1))"
  exit 0
fi
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found; Node.js/npm is a plane prerequisite — run install.sh first" >&2; exit 2; }
mkdir -p "$HOME/.local"
npm install -g --prefix "$HOME/.local" @openai/codex
hash -r
ver="$("$HOME/.local/bin/codex" --version 2>/dev/null | head -1 || true)"
echo "[codex] installed: ${ver:-unknown}"
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

log "stage 3: rsync ~/.codex/ -> remote"
rsync -az --delete \
  -e "ssh -o ControlPath=$sock -i $key -p $port -o BatchMode=yes" \
  "$HOME/.codex/" "$target:.codex/"

log "stage 4: restart kimi + plane"
ssh "${opts[@]}" "$target" 'systemctl --user restart kimi plane || true'

log "stage 5: verify binary + auth"
version="$(ssh "${opts[@]}" "$target" 'PATH="$HOME/.local/bin:$PATH" codex --version 2>/dev/null | head -1' || true)"
[[ -z "$version" ]] && die "codex installed but not callable on remote — check PATH and ~/.codex/"

# codex login status prints "Logged in using ChatGPT" (or "Logged in using API key")
# when authed. Parse the output rather than trust exit codes.
auth_out="$(ssh "${opts[@]}" "$target" 'PATH="$HOME/.local/bin:$PATH" codex login status 2>&1' || true)"
authed=false
if printf '%s' "$auth_out" | grep -qi '^Logged in'; then authed=true; fi
log "  codex: $(printf '%s' "$auth_out" | head -1)"

write_index "$(jq_index --arg n "$name" --arg v "$version" --argjson a "$authed" \
  '.machines[$n].services.providers.codex = {installed: true, authed: $a, version: $v}')"

if [[ "$authed" != "true" ]]; then
  log ""
  log "WARNING: codex installed but not authenticated on $name."
  log "  If the laptop's codex is logged in (\`codex login status\`), re-run this script."
  log "  Otherwise log in on the laptop first: \`codex login\` — then re-run."
  exit 0
fi

log "codex ready on $name (version: $version, authed: yes)"
