#!/usr/bin/env bash
# remote-stage.sh — runs ON THE REMOTE, piped over `ssh bash -s` from the
# laptop-side install.sh. Has no executable presence on the remote outside
# this single invocation. Per machine-provisioning-spec.md §4.2.1 / §4.2.2.
#
# Inputs (env, propagated from the laptop via ssh_pipe --env):
#   KIMI_PORT              required
#   PLANE_PORT             required
#   NODE_BIN               required (absolute path to node on remote)
#   STAGE_DIR              required (where the laptop scp'd the bundle artifacts)
#
# Optional env:
#   NO_LINGER              skip `loginctl enable-linger`
#   SKIP_SYSTEMD           stop after unit render (dry run)
#
# Args (positional):
#   $1   stage to run: "all" | "layout" | "install-binary" | "extract-plane"
#                      | "render-units" | "enable-services"
#        Default "all".
#
# Per-stage atomicity:
#   - kimi-server binary: write to kimi-server.new, then atomic rename.
#   - plane bundle: tar -xf --overwrite into a fresh staging dir, then
#     atomic dir-swap into PLANE_DIR.
#   - systemd unit: envsubst > unit.new && mv unit.new unit.

set -euo pipefail

# ── strict env validation (spec §4.2.2) ──────────────────────────────────────
: "${KIMI_PORT:?KIMI_PORT not propagated; check ssh_pipe --env wiring}"
: "${PLANE_PORT:?PLANE_PORT not propagated}"
: "${NODE_BIN:?NODE_BIN not propagated}"
: "${STAGE_DIR:?STAGE_DIR not propagated}"

PREFIX="$HOME/.local/share/openscientist"
BIN_DIR="$PREFIX/bin"
PLANE_DIR="$PREFIX/plane"
USER_UNIT_DIR="$HOME/.config/systemd/user"
PROV_DIR="$HOME/.openscientist/providers"
LOG_FILE="${REMOTE_LOG_FILE:-$HOME/.openscientist/logs/remote-stage-$(date -u +%Y%m%dT%H%M%SZ).log}"

mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { printf "[remote-stage] %s\n" "$*" >&2; }
die()  { log "ERROR: $*"; exit 1; }

[ -d "$STAGE_DIR" ] || die "STAGE_DIR not found: $STAGE_DIR"
[ -x "$STAGE_DIR/kimi-server" ] || die "$STAGE_DIR/kimi-server not executable"
[ -f "$STAGE_DIR/plane.tar.gz" ] || die "$STAGE_DIR/plane.tar.gz missing"
[ -f "$STAGE_DIR/systemd/kimi.service" ] || die "systemd/kimi.service missing"
[ -f "$STAGE_DIR/systemd/plane.service" ] || die "systemd/plane.service missing"
[ -n "$NODE_BIN" ] || die "NODE_BIN empty"
[ -x "$NODE_BIN" ] || die "NODE_BIN=$NODE_BIN is not executable"

stage="${1:-all}"

# ── stages ───────────────────────────────────────────────────────────────────

stage_layout() {
  log "[layout] mkdir prefix dirs"
  mkdir -p "$BIN_DIR" "$PLANE_DIR" "$USER_UNIT_DIR" "$PROV_DIR" "$HOME/.openscientist"
  chmod 700 "$PROV_DIR" "$HOME/.openscientist"
}

stage_install_binary() {
  log "[install-binary] atomic write kimi-server"
  install -m 0755 "$STAGE_DIR/kimi-server" "$BIN_DIR/kimi-server.new"
  # POSIX rename is atomic on the same filesystem.
  mv -f "$BIN_DIR/kimi-server.new" "$BIN_DIR/kimi-server"
}

stage_extract_plane() {
  log "[extract-plane] idempotent re-extract via staging dir"
  local staging="$PLANE_DIR.next"
  rm -rf "$staging"
  mkdir -p "$staging"
  # --overwrite handles any leftover entries inside the staging dir
  # (cannot happen here since we just created it, but cheap insurance).
  tar -xzf "$STAGE_DIR/plane.tar.gz" -C "$staging" --overwrite
  [ -f "$staging/kimi-server.cjs" ] || die "plane bundle missing kimi-server.cjs after extract"
  # Atomic dir swap. mv on existing PLANE_DIR fails on non-empty dest;
  # so we move existing aside, then move new into place, then delete old.
  if [ -d "$PLANE_DIR" ] && [ "$(ls -A "$PLANE_DIR" 2>/dev/null || true)" ]; then
    rm -rf "$PLANE_DIR.old" 2>/dev/null || true
    mv "$PLANE_DIR" "$PLANE_DIR.old"
  fi
  mv "$staging" "$PLANE_DIR"
  rm -rf "$PLANE_DIR.old" 2>/dev/null || true
}

stage_render_units() {
  log "[render-units] envsubst systemd templates"
  export HOME PREFIX BIN_DIR PLANE_DIR NODE_BIN KIMI_PORT PLANE_PORT PROV_DIR
  local VARS='${HOME} ${PREFIX} ${BIN_DIR} ${PLANE_DIR} ${NODE_BIN} ${KIMI_PORT} ${PLANE_PORT} ${PROV_DIR}'
  envsubst "$VARS" < "$STAGE_DIR/systemd/kimi.service"  > "$USER_UNIT_DIR/kimi.service.new"
  envsubst "$VARS" < "$STAGE_DIR/systemd/plane.service" > "$USER_UNIT_DIR/plane.service.new"
  chmod 0644 "$USER_UNIT_DIR/kimi.service.new" "$USER_UNIT_DIR/plane.service.new"
  mv -f "$USER_UNIT_DIR/kimi.service.new"  "$USER_UNIT_DIR/kimi.service"
  mv -f "$USER_UNIT_DIR/plane.service.new" "$USER_UNIT_DIR/plane.service"
}

stage_enable_services() {
  log "[enable-services] linger + daemon-reload + restart"
  if [ -n "${NO_LINGER:-}" ]; then
    log "  NO_LINGER set; skipping linger"
  elif loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    log "  already lingered"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo loginctl enable-linger "$USER" && log "  enabled linger"
  else
    log "  WARNING: passwordless sudo unavailable; units will die on SSH logout."
    log "  run once manually:  sudo loginctl enable-linger $USER"
  fi

  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  systemctl --user daemon-reload
  systemctl --user enable kimi.service plane.service >/dev/null
  systemctl --user restart kimi.service plane.service
}

# ── dispatch ─────────────────────────────────────────────────────────────────

case "$stage" in
  all)
    stage_layout
    stage_install_binary
    stage_extract_plane
    stage_render_units
    if [ -n "${SKIP_SYSTEMD:-}" ]; then
      log "SKIP_SYSTEMD set — stopping after unit render"
    else
      stage_enable_services
    fi
    ;;
  layout)          stage_layout ;;
  install-binary)  stage_install_binary ;;
  extract-plane)   stage_extract_plane ;;
  render-units)    stage_render_units ;;
  enable-services) stage_enable_services ;;
  *) die "unknown stage: $stage" ;;
esac

log "done: stage=$stage"
log "log: $LOG_FILE"
printf '%s\n' "$LOG_FILE"
