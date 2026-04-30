#!/usr/bin/env bash
# install.sh <name> [--bundle PATH]
# Stages the plane+kimi bundle onto the remote and runs its installer.
# On success, flips the machine's status to "ready" and records bundleVersion.
#
# Bundle layout expected:
#   <bundle>/install.sh          — runs on the remote
#   <bundle>/kimi-server         — PyInstaller binary
#   <bundle>/plane.tar.gz        — plane node bundle
#   <bundle>/systemd/{kimi,plane}.service
#   <bundle>/manifest.json       — has .version
#
# Bundle resolution order:
#   1. --bundle <path>
#   2. $OPENSCIENTIST_CLOUD_RUN_BUNDLE
#   3. ~/.openscientist/cloud-run/<arch>/ — canonical symlink Electron main
#      maintains at startup. Points at process.resourcesPath/cloud-run in a
#      packaged app, or at frontend/electron/cloud-run/ in dev. This is the
#      only production path — if it's missing, Electron hasn't started yet or
#      the app is installed incorrectly. Do NOT paper over that by prompting.
source "$(dirname "$0")/_common.sh"
ensure_index

name=""
bundle=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) bundle="$2"; shift 2 ;;
    -*) die "unknown flag: $1" ;;
    *)  [[ -z "$name" ]] && name="$1" || die "usage: install.sh <name> [--bundle PATH]"; shift ;;
  esac
done

[[ -z "$name" ]] && die "usage: install.sh <name> [--bundle PATH]"
[[ "$name" == "local" ]] && die 'cannot install on reserved machine "local"'
machine_exists "$name" || die "no such machine: $name — run add.sh first"

resolve_bundle() {
  local arch
  arch="$(uname -m)"
  [[ "$arch" == "x86_64" ]] && arch="linux-x86_64" || die "unsupported arch: $arch"

  # Single canonical location. Electron main ensures ~/.openscientist/cloud-run
  # is a symlink pointing at the right source (packaged resources dir in prod,
  # frontend/electron/cloud-run/ in dev). $OPENSCIENTIST_CLOUD_RUN_BUNDLE and
  # --bundle remain as escape hatches for manual dev testing but should never
  # be needed in normal operation.
  local candidates=(
    "${OPENSCIENTIST_CLOUD_RUN_BUNDLE:-}"
    "$HOME/.openscientist/cloud-run/$arch"
  )
  for c in "${candidates[@]}"; do
    [[ -z "$c" ]] && continue
    [[ -f "$c/install.sh" && -x "$c/kimi-server" && -f "$c/plane.tar.gz" ]] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

if [[ -z "$bundle" ]]; then
  bundle="$(resolve_bundle)" || die "bundle not found at \$HOME/.openscientist/cloud-run/<arch>/ — this symlink is maintained by Electron main at app startup. If you're seeing this, either the app hasn't started yet, or the install is broken. Do not prompt the user for a path — open the app to restore the symlink. (Manual override: --bundle PATH or \$OPENSCIENTIST_CLOUD_RUN_BUNDLE, for dev testing only.)"
fi
[[ -d "$bundle" ]] || die "bundle path not a directory: $bundle"
[[ -f "$bundle/install.sh" ]] || die "bundle missing install.sh: $bundle"

log "bundle: $bundle"

# Ensure ControlMaster before scp/rsync.
"$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"
sock="$(ssh_sock "$name")"
key="$(machine_field "$name" "ssh.keyPath")"
port="$(machine_field "$name" "port")"; [[ -z "$port" ]] && port=22

# Record "provisioning" so the UI sees progress.
write_index "$(jq_index --arg n "$name" '.machines[$n].status = "provisioning" | .machines[$n].lastError = null')"

remote_home="$(ssh "${opts[@]}" "$target" 'printf %s "$HOME"')"
[[ -z "$remote_home" ]] && die "could not resolve remote \$HOME"
remote_stage="$remote_home/.openscientist/cloud-run"

log "staging bundle on remote: $remote_stage"
ssh "${opts[@]}" "$target" "mkdir -p '$remote_stage'"

log "rsync bundle -> remote (this may take a minute on first push)"
rsync -az --delete \
  -e "ssh -o ControlPath=$sock -i $key -p $port -o BatchMode=yes" \
  "$bundle/" "$target:$remote_stage/"

log "copying auth token (if present)"
if [[ -f "$AUTH_PATH" ]]; then
  # Rewrite base_url to the remote-reachable backend so the machine hits the
  # production endpoint instead of the laptop's localhost. The local
  # auth.json is left untouched; only the synced copy is rewritten.
  # Override via OPENSCIENTIST_REMOTE_BASE_URL if you need to point a machine
  # at staging or a custom backend.
  remote_base_url="${OPENSCIENTIST_REMOTE_BASE_URL:-https://aloo-gobi.fydy.ai}"
  tmp_auth="$(mktemp)"
  jq --arg url "$remote_base_url" '.base_url = $url' "$AUTH_PATH" > "$tmp_auth"
  log "syncing auth.json with base_url=$remote_base_url"
  scp -o ControlPath="$sock" -i "$key" -P "$port" -q "$tmp_auth" "$target:$remote_home/.openscientist/auth.json" || \
    log "WARNING: auth.json copy failed; skill-sync and provider routing will not work until fixed"
  ssh "${opts[@]}" "$target" "chmod 600 '$remote_home/.openscientist/auth.json'" || true
  rm -f "$tmp_auth"
else
  log "no $AUTH_PATH on laptop — skipping; provider-routing endpoints will fail"
fi

log "running remote installer ..."
if ! ssh "${opts[@]}" "$target" "STAGE_DIR='$remote_stage' bash '$remote_stage/install.sh'"; then
  err="remote install.sh exited non-zero (see ssh output above)"
  write_index "$(jq_index --arg n "$name" --arg e "$err" '.machines[$n].status = "error" | .machines[$n].lastError = $e')"
  die "$err"
fi

version="$(ssh "${opts[@]}" "$target" "jq -r '.version // .bundleVersion // \"unknown\"' '$remote_stage/manifest.json'" 2>/dev/null || echo "unknown")"
remote_prefix="$remote_home/.local/share/openscientist"

updated="$(jq_index \
  --arg n "$name" \
  --arg ver "$version" \
  --arg home "$remote_home" \
  --arg prefix "$remote_prefix" \
  --arg at "$(now_iso)" \
  '.machines[$n].status = "ready"
   | .machines[$n].bundleVersion = $ver
   | .machines[$n].remote.home   = $home
   | .machines[$n].remote.prefix = $prefix
   | .machines[$n].provisionedAt = $at
   | .machines[$n].lastError     = null')"
write_index "$updated"

log "install complete: $name @ bundle $version"
log "next: run status.sh $name to verify healthz, then activate.sh $name"
