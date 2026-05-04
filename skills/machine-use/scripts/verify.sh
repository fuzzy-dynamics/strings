#!/usr/bin/env bash
# verify.sh — laptop-side health probe for a machine.
#
# Per machine-provisioning-spec.md §4.5:
#   - Read-only. Never mutates the index.
#   - Used as the last gate of install.sh / install-claude.sh / install-codex.sh,
#     by the renderer's machine selector boot probe, and for manual checks.
#   - Three calling patterns:
#       1. --kimi-port P --plane-port P given → probe forwarded ports, via=bridge.
#       2. No flags, ports.json fresh    → read snapshot, via=bridge.
#       3. Otherwise / fallback          → ssh exec to remote loopback, via=remote-loopback.
#
# Usage:
#   verify.sh <name> [--kimi-port P] [--plane-port P]
#
# Output (stdout, single JSON):
#   {"ok":bool,"name":"...","via":"bridge|remote-loopback",
#    "ssh":{"ok":bool},"kimi":{"ok":bool,"latencyMs":N},"plane":{...},
#    "providers":{"claude":{...}|null,"codex":{...}|null},
#    "verifiedAt":"..."}
#
# Exit codes:
#   0  ok=true  AND  ssh+kimi+plane all reachable
#   1  ok=false (any of ssh/kimi/plane failed)
#   2  arg error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-use" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

# ── parse args ───────────────────────────────────────────────────────────────

NAME=""
KIMI_PORT=""
PLANE_PORT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --kimi-port)  KIMI_PORT="$2"; shift 2 ;;
    --plane-port) PLANE_PORT="$2"; shift 2 ;;
    -h|--help)
      echo "usage: verify.sh <name> [--kimi-port P] [--plane-port P]" >&2
      exit 0 ;;
    --*)
      printf '{"ok":false,"stage":"parse-args","message":"unknown flag: %s"}\n' "$1"
      exit 2 ;;
    *)
      if [[ -z "$NAME" ]]; then NAME="$1"; else
        printf '{"ok":false,"stage":"parse-args","message":"unexpected positional: %s"}\n' "$1"
        exit 2
      fi
      shift ;;
  esac
done

if [[ -z "$NAME" ]]; then
  printf '{"ok":false,"stage":"parse-args","message":"missing <name>"}\n'
  exit 2
fi

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME

# ── port resolution: flags > snapshot > remote-loopback ──────────────────────

VIA="remote-loopback"
PORTS_SNAPSHOT="$SSH_DIR/$NAME.ports.json"
SNAPSHOT_FRESH_SECS=300

if [[ -n "$KIMI_PORT" && -n "$PLANE_PORT" ]]; then
  VIA="bridge"
elif [[ -f "$PORTS_SNAPSHOT" ]]; then
  # Fresh enough?
  local_now="$(date +%s)"
  snap_mtime="$(stat -c %Y "$PORTS_SNAPSHOT" 2>/dev/null || echo 0)"
  if (( local_now - snap_mtime <= SNAPSHOT_FRESH_SECS )); then
    KIMI_PORT="$(jq -r '.kimi // empty' "$PORTS_SNAPSHOT" 2>/dev/null || true)"
    PLANE_PORT="$(jq -r '.plane // empty' "$PORTS_SNAPSHOT" 2>/dev/null || true)"
    if [[ -n "$KIMI_PORT" && -n "$PLANE_PORT" ]]; then
      VIA="bridge"
    fi
  else
    emit_progress warn "ports-snapshot" "ports.json is stale (>${SNAPSHOT_FRESH_SECS}s); falling back to remote-loopback"
  fi
fi

# ── helpers ──────────────────────────────────────────────────────────────────

probe_localhost_healthz() {
  local port="$1"
  local started ended status
  started="$(date +%s%3N)"
  if status=$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$port/healthz" 2>/dev/null); then
    ended="$(date +%s%3N)"
    if [[ "$status" == "200" ]]; then
      printf '{"ok":true,"latencyMs":%d}' "$((ended - started))"
      return 0
    fi
  fi
  printf '{"ok":false,"latencyMs":null}'
  return 1
}

probe_remote_healthz() {
  local port="$1"
  local started ended out
  started="$(date +%s%3N)"
  if out=$(ssh_run "$NAME" -q -- "curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:$port/healthz" 2>/dev/null); then
    ended="$(date +%s%3N)"
    if [[ "$out" == "200" ]]; then
      printf '{"ok":true,"latencyMs":%d}' "$((ended - started))"
      return 0
    fi
  fi
  printf '{"ok":false,"latencyMs":null}'
  return 1
}

probe_provider() {
  local cmd="$1"
  # Provider CLIs are installed under ~/.local/bin (per install-{claude,codex}.sh
  # using --prefix=~/.local). Non-interactive ssh sessions don't get that on
  # PATH by default, so probe by absolute path. Falls back to PATH lookup if
  # the binary is somehow elsewhere.
  local probe='V=$($HOME/.local/bin/'"$cmd"' --version 2>/dev/null) || V=$('"$cmd"' --version 2>/dev/null) || true; printf "%s" "$V"'
  local version
  if version=$(ssh_run "$NAME" -q -- "$probe" 2>/dev/null); then
    version=$(printf '%s' "$version" | head -1 | tr -d '\r\n')
    if [[ -n "$version" ]]; then
      jq -nc --arg v "$version" '{ok:true,version:$v}'
      return
    fi
  fi
  jq -nc '{ok:false,version:null}'
}

# ── stages ───────────────────────────────────────────────────────────────────

# 1. ssh-master
ssh_ok=false
if ssh_master_alive "$NAME"; then ssh_ok=true; fi

# 2/3. kimi/plane healthz
kimi_json='{"ok":false,"latencyMs":null}'
plane_json='{"ok":false,"latencyMs":null}'

if [[ "$ssh_ok" == "true" ]]; then
  if [[ "$VIA" == "bridge" ]]; then
    # Try bridge-mode first; if it fails, fall through to remote-loopback.
    if k=$(probe_localhost_healthz "$KIMI_PORT") 2>/dev/null; then kimi_json="$k"; fi
    if p=$(probe_localhost_healthz "$PLANE_PORT") 2>/dev/null; then plane_json="$p"; fi
    # Auto-fallback if the bridge probes both failed.
    if [[ "$(jq -r '.ok' <<<"$kimi_json")" == "false" && "$(jq -r '.ok' <<<"$plane_json")" == "false" ]]; then
      emit_progress warn "via-fallback" "bridge probes failed; retrying via remote-loopback"
      VIA="remote-loopback"
      if k=$(probe_remote_healthz "5494") 2>/dev/null; then kimi_json="$k"; fi
      if p=$(probe_remote_healthz "5495") 2>/dev/null; then plane_json="$p"; fi
    fi
  else
    if k=$(probe_remote_healthz "5494") 2>/dev/null; then kimi_json="$k"; fi
    if p=$(probe_remote_healthz "5495") 2>/dev/null; then plane_json="$p"; fi
  fi
fi

# 4/5. providers (only if installed)
claude_json="null"
codex_json="null"
if [[ "$ssh_ok" == "true" ]]; then
  ensure_index
  claude_installed="$(machine_field "$NAME" 'services.providers.claude.installed' 2>/dev/null || true)"
  codex_installed="$(machine_field "$NAME" 'services.providers.codex.installed' 2>/dev/null || true)"
  if [[ "$claude_installed" == "true" ]]; then
    claude_json="$(probe_provider claude)"
  fi
  if [[ "$codex_installed" == "true" ]]; then
    codex_json="$(probe_provider codex)"
  fi
fi

# ── compose output ───────────────────────────────────────────────────────────

verified_at="$(now_iso)"

ok="true"
[[ "$ssh_ok"   != "true" ]] && ok="false"
[[ "$(jq -r '.ok' <<<"$kimi_json")"  != "true" ]] && ok="false"
[[ "$(jq -r '.ok' <<<"$plane_json")" != "true" ]] && ok="false"

result=$(jq -n \
  --argjson ok "$ok" \
  --arg name "$NAME" \
  --arg via "$VIA" \
  --argjson ssh "{\"ok\":$ssh_ok}" \
  --argjson kimi "$kimi_json" \
  --argjson plane "$plane_json" \
  --argjson claude "$claude_json" \
  --argjson codex "$codex_json" \
  --arg verifiedAt "$verified_at" \
  '{ok:$ok,name:$name,via:$via,ssh:$ssh,kimi:$kimi,plane:$plane,
    providers:{claude:$claude,codex:$codex},
    verifiedAt:$verifiedAt}')

printf '%s\n' "$result"

[[ "$ok" == "true" ]] || exit 1
