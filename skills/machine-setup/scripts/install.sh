#!/usr/bin/env bash
# install.sh <name> [--bundle PATH]
#
# Single source of truth for the machine install. Drives stages from the
# laptop over the SSH ControlMaster. Per machine-provisioning-spec.md §4.2
# and §4.2.1: the bundle ships only artifacts; this script is the only
# orchestrator. Idempotent. Re-runs from setup-complete | ready | broken
# are allowed; services.providers is preserved across rerun.
#
# Bundle layout expected (no install.sh shipped per spec):
#   <bundle>/kimi-server         — PyInstaller binary
#   <bundle>/plane.tar.gz        — plane node bundle
#   <bundle>/systemd/{kimi,plane}.service
#   <bundle>/manifest.json       — has .bundleVersion (sha256 of plane.tar.gz)
#
# Bundle resolution order:
#   1. --bundle <path>
#   2. $OPENSCIENTIST_CLOUD_RUN_BUNDLE
#   3. ~/.openscientist/cloud-run/<arch>/  (canonical Electron-maintained symlink)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-setup" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

# ── parse args ───────────────────────────────────────────────────────────────

NAME=""
BUNDLE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    -h|--help)
      echo "usage: install.sh <name> [--bundle PATH]" >&2
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

[[ -z "$NAME" ]] && { printf '{"ok":false,"stage":"parse-args","message":"missing <name>"}\n'; exit 2; }
if [[ "$NAME" == "local" ]]; then
  printf '{"ok":false,"stage":"precheck","message":"local machine is implicit; no install needed"}\n'
  exit 1
fi

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME
ensure_index
machine_exists "$NAME" || { printf '{"ok":false,"stage":"precheck","message":"no such machine: %s — run add.sh first"}\n' "$NAME"; exit 1; }

index_lock "$NAME"
trap_unhandled_errors

# Mark provisioning at the start. Preserve services.providers across this update.
index_update "$NAME" '
  . + { status: "provisioning", lastError: null }
  | .services = ((.services // {}) | (.providers //= {}) | .)
'

# ── stage: bundle-resolve ────────────────────────────────────────────────────

emit_progress info "bundle-resolve" "resolving cloud-run bundle for arch"

resolve_bundle() {
  local arch
  arch="$(uname -m)"
  [[ "$arch" == "x86_64" ]] && arch="linux-x86_64" || die "unsupported arch: $arch"

  local candidates=(
    "${OPENSCIENTIST_CLOUD_RUN_BUNDLE:-}"
    "$HOME/.openscientist/cloud-run/$arch"
  )
  for c in "${candidates[@]}"; do
    [[ -z "$c" ]] && continue
    [[ -x "$c/kimi-server" && -f "$c/plane.tar.gz" && -f "$c/manifest.json" ]] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

if [[ -z "$BUNDLE" ]]; then
  BUNDLE="$(resolve_bundle)" || mark_broken "bundle-resolve" \
    "bundle not found at \$HOME/.openscientist/cloud-run/<arch>/ (Electron maintains this symlink at startup; if missing, restart the app or run scripts/build-cloud-run-bundle.sh)" '{}'
fi
[[ -d "$BUNDLE" ]]                || mark_broken "bundle-resolve" "bundle path not a directory: $BUNDLE" '{}'
[[ -f "$BUNDLE/manifest.json" ]]  || mark_broken "bundle-resolve" "bundle missing manifest.json: $BUNDLE" '{}'
[[ -x "$BUNDLE/kimi-server" ]]    || mark_broken "bundle-resolve" "bundle missing executable kimi-server: $BUNDLE" '{}'
[[ -f "$BUNDLE/plane.tar.gz" ]]   || mark_broken "bundle-resolve" "bundle missing plane.tar.gz: $BUNDLE" '{}'

bundle_version="$(jq -r '.bundleVersion // .components.plane.sha256 // empty' "$BUNDLE/manifest.json")"
[[ -n "$bundle_version" ]] || mark_broken "bundle-resolve" "manifest.json has no bundleVersion or components.plane.sha256" '{}'
emit_progress info "bundle-resolve" "bundle=$BUNDLE version=${bundle_version:0:16}"

# ── stage: precheck (ssh) ────────────────────────────────────────────────────

emit_progress info "precheck" "ensuring SSH ControlMaster"
"$SCRIPT_DIR/reconnect-ssh.sh" "$NAME" >/dev/null || mark_broken "precheck" "reconnect-ssh.sh failed" '{}'

mapfile -t SSH_OPTS < <(ssh_base_opts "$NAME")
SSH_TARGET="$(ssh_target "$NAME")"
SSH_SOCK="$(ssh_sock "$NAME")"
SSH_KEY="$(machine_field "$NAME" "ssh.keyPath")"
SSH_PORT="$(machine_field "$NAME" "ssh.port")"; [[ -z "$SSH_PORT" ]] && SSH_PORT=22

remote_home="$(ssh "${SSH_OPTS[@]}" "$SSH_TARGET" 'printf %s "$HOME"' 2>/dev/null || true)"
[[ -n "$remote_home" ]] || mark_broken "precheck" "could not resolve remote \$HOME" '{}'
remote_stage="$remote_home/.openscientist/cloud-run"
emit_progress info "precheck" "remote.home=$remote_home"

# ── stage: bundle-copy ───────────────────────────────────────────────────────

emit_progress info "bundle-copy" "rsync bundle artifacts to remote"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p '$remote_stage'" \
  || mark_broken "bundle-copy" "could not create remote staging dir" '{}'

if ! with_timeout 90 "bundle-copy" -- \
  rsync -az --delete \
    -e "ssh -o ControlPath=$SSH_SOCK -i $SSH_KEY -p $SSH_PORT -o BatchMode=yes" \
    "$BUNDLE/" "$SSH_TARGET:$remote_stage/"
then
  mark_broken "bundle-copy" "rsync failed; check disk space or remote permissions" '{}'
fi

# ── stage: auth.json copy (best-effort) ──────────────────────────────────────

if [[ -f "$AUTH_PATH" ]]; then
  remote_base_url="${OPENSCIENTIST_REMOTE_BASE_URL:-https://aloo-gobi.fydy.ai}"
  tmp_auth="$(mktemp)"
  jq --arg url "$remote_base_url" '.base_url = $url' "$AUTH_PATH" > "$tmp_auth"
  emit_progress info "auth-copy" "syncing auth.json with base_url=$remote_base_url"
  if ! scp -o ControlPath="$SSH_SOCK" -i "$SSH_KEY" -P "$SSH_PORT" -q "$tmp_auth" "$SSH_TARGET:$remote_home/.openscientist/auth.json" 2>/dev/null; then
    emit_progress warn "auth-copy" "auth.json copy failed; provider routing may not work"
  else
    ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "chmod 600 '$remote_home/.openscientist/auth.json'" 2>/dev/null || true
  fi
  rm -f "$tmp_auth"
else
  emit_progress warn "auth-copy" "no $AUTH_PATH on laptop; provider-routing endpoints will fail"
fi

# ── stage: remote-stage (piped) ──────────────────────────────────────────────

emit_progress info "remote-stage" "piping remote-stage.sh"
remote_node="$(ssh "${SSH_OPTS[@]}" "$SSH_TARGET" 'command -v node || true' 2>/dev/null)"
[[ -n "$remote_node" ]] || mark_broken "remote-stage" "node not found on remote PATH" '{}'

# ssh_pipe runs the script with explicit env injection, no SendEnv config.
# Stage "all" runs layout, install-binary, extract-plane, render-units, enable-services.
remote_log_path=""
if ! remote_log_path=$(with_timeout 90 "remote-stage" -- \
  ssh_pipe "$NAME" \
    --env "KIMI_PORT=5494" \
    --env "PLANE_PORT=5495" \
    --env "NODE_BIN=$remote_node" \
    --env "STAGE_DIR=$remote_stage" \
    --env "HEALTHCHECK_TIMEOUT_S=30" \
    -- "$SCRIPT_DIR/remote-stage.sh" "all" \
  | tail -1)
then
  tail_log="$(remote_log_tail "$NAME" "\$HOME/.openscientist/logs/remote-stage-*.log" 200)"
  mark_broken "remote-stage" "remote-stage.sh failed" \
    "$(jq -nc --arg t "$tail_log" '{remoteLogTail:$t}')"
fi

# ── stage: pre-create remote dirs ────────────────────────────────────────────

remote_spaces_root="$remote_home/.openscientist/spaces"
remote_worktrees_root="$remote_home/.openscientist/worktrees"
remote_prefix="$remote_home/.local/share/openscientist"

emit_progress info "remote-dirs" "ensuring spaces/worktrees roots"
ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "mkdir -p '$remote_spaces_root' '$remote_worktrees_root'" \
  || emit_progress warn "remote-dirs" "could not create spaces/worktrees roots (continuing)"

# ── stage: verify-from-laptop ────────────────────────────────────────────────

emit_progress info "verify-from-laptop" "running verify.sh"
verify_out=""
verify_rc=0
verify_out=$(with_timeout 30 "verify-from-laptop" -- \
  bash "$SCRIPT_DIR/../../machine-use/scripts/verify.sh" "$NAME") || verify_rc=$?
# verify.sh exits 0 even when its JSON reports ok:false, so check both.
verify_ok=$(printf '%s' "$verify_out" | tail -1 | jq -r '.ok // false' 2>/dev/null)
if [[ "$verify_rc" -ne 0 ]] || [[ "$verify_ok" != "true" ]]; then
  mark_broken "verify-from-laptop" "verify.sh failed; kimi or plane not reachable" \
    "$(jq -nc --arg v "$verify_out" '{verifyOutput:$v}')"
fi
emit_progress info "verify-from-laptop" "ok"

# ── stage: index-write-success ───────────────────────────────────────────────

emit_progress info "index-write-success" "merging success record"

# Atomic merge that PRESERVES services.providers across a reinstall (spec §4.2).
index_update "$NAME" "$(cat <<JQ
  (.services // {}) as \$svc
  | (\$svc.providers // {}) as \$prov
  | . + {
      status: "ready",
      bundleVersion: "$bundle_version",
      provisionedAt: "$(now_iso)",
      lastVerifiedAt: "$(now_iso)",
      remote: ((.remote // {}) + {
        home: "$remote_home",
        prefix: "$remote_prefix",
        spacesRoot: "$remote_spaces_root",
        worktreesRoot: "$remote_worktrees_root"
      }),
      services: (\$svc + { providers: \$prov }),
      lastError: null
    }
JQ
)"

# Final outcome on stdout, single JSON doc per contract.
jq -nc \
  --arg name "$NAME" \
  --arg version "$bundle_version" \
  --arg home "$remote_home" \
  --argjson verify "$verify_out" \
  '{ok:true,name:$name,stage:"done",bundleVersion:$version,remoteHome:$home,verify:$verify}'

emit_progress info "done" "install complete: $NAME @ ${bundle_version:0:16}"
