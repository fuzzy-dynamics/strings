#!/usr/bin/env bash
# status.sh <name>
# Probes a machine's live state and emits a JSON snapshot on stdout. Updates
# the machine record in index.json with the same snapshot so the UI sees it.
#
# What it checks:
#   - SSH ControlMaster (socket exists + ssh -O check succeeds)
#   - systemd user units (kimi, plane) via `systemctl --user is-active`
#   - plane /healthz and kimi /healthz via the remote's loopback (over ssh)
#   - bundle version (reads remote manifest.json)
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: status.sh <name>"

if [[ "$name" == "local" ]]; then
  jq -n '{name:"local", sshMaster:"n/a", services:{kimi:"unknown", plane:"unknown"}, healthz:{kimi:null, plane:null}, bundleVersion:null}'
  exit 0
fi

machine_exists "$name" || die "no such machine: $name"

ssh_master="down"
svc_kimi="unreachable"
svc_plane="unreachable"
hz_kimi="null"
hz_plane="null"
bundle="null"
last_err=""

if ssh_master_alive "$name"; then
  ssh_master="up"
fi

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"

# Build one remote probe. Timeout with `-o ConnectTimeout=5` already set.
probe_output="$(ssh "${opts[@]}" "$target" bash -s <<'REMOTE' 2>/dev/null || true
set -e
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
printf 'svc_kimi=%s\n'  "$(systemctl --user is-active kimi.service  2>/dev/null || echo unknown)"
printf 'svc_plane=%s\n' "$(systemctl --user is-active plane.service 2>/dev/null || echo unknown)"
printf 'hz_kimi=%s\n'   "$(curl -fsS -m 3 http://127.0.0.1:5494/healthz >/dev/null 2>&1 && echo ok || echo fail)"
printf 'hz_plane=%s\n'  "$(curl -fsS -m 3 http://127.0.0.1:5495/healthz >/dev/null 2>&1 && echo ok || echo fail)"
if [ -f "$HOME/.openscientist/cloud-run/manifest.json" ]; then
  printf 'bundle=%s\n' "$(jq -r '.version // .bundleVersion // "unknown"' "$HOME/.openscientist/cloud-run/manifest.json" 2>/dev/null || echo unknown)"
else
  printf 'bundle=none\n'
fi
REMOTE
)"

if [[ -n "$probe_output" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      svc_kimi)  svc_kimi="$value" ;;
      svc_plane) svc_plane="$value" ;;
      hz_kimi)   hz_kimi="\"$value\"" ;;
      hz_plane)  hz_plane="\"$value\"" ;;
      bundle)    [[ "$value" == "none" ]] && bundle="null" || bundle="\"$value\"" ;;
    esac
  done <<<"$probe_output"
else
  last_err="remote probe failed (ssh unreachable or timed out)"
fi

snapshot="$(jq -n \
  --arg name    "$name" \
  --arg ssh     "$ssh_master" \
  --arg kimi    "$svc_kimi" \
  --arg plane   "$svc_plane" \
  --argjson hk  "$hz_kimi" \
  --argjson hp  "$hz_plane" \
  --argjson bv  "$bundle" \
  --arg err     "$last_err" \
  --arg checked "$(now_iso)" \
  '{
     name:          $name,
     sshMaster:     $ssh,
     services:      {kimi: $kimi, plane: $plane},
     healthz:       {kimi: $hk,   plane: $hp},
     bundleVersion: $bv,
     lastCheckedAt: $checked,
     lastError:     (if $err == "" then null else $err end)
   }')"

# Pure stdout probe — no writeback. The renderer (or Electron's boot probe in
# cloud-run/index.cjs) derives liveness from the bridge state and from
# repeated calls to this script. Persisting derived fields used to drift fast
# (services flap, healthz blips) and Electron now strips them on read anyway.
printf '%s\n' "$snapshot"
