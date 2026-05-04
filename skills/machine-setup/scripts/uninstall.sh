#!/usr/bin/env bash
# uninstall.sh <name>
# Stops + disables systemd user units on the remote and removes install dirs.
# Keeps the machine in index.json (use remove.sh to delete the registry entry).
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: uninstall.sh <name>"
[[ "$name" == "local" ]] && die 'cannot uninstall reserved machine "local"'
machine_exists "$name" || die "no such machine: $name"

if ! ssh_master_alive "$name"; then
  log "ControlMaster down; attempting reconnect ..."
  "$(dirname "$0")/reconnect-ssh.sh" "$name" >/dev/null
fi

mapfile -t opts < <(ssh_base_opts "$name")
target="$(ssh_target "$name")"

log "stopping services on $name ..."
ssh "${opts[@]}" "$target" bash -s <<'REMOTE' || true
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user stop    kimi.service plane.service 2>/dev/null || true
systemctl --user disable kimi.service plane.service 2>/dev/null || true
rm -f ~/.config/systemd/user/kimi.service ~/.config/systemd/user/plane.service
systemctl --user daemon-reload 2>/dev/null || true
rm -rf ~/.openscientist/cloud-run
rm -rf ~/.local/share/openscientist
REMOTE

# Close the control master too — no more reason to hold it open.
sock="$(ssh_sock "$name")"
[[ -S "$sock" ]] && ssh -O exit -S "$sock" "check-$name" 2>/dev/null || true

# Preserve services.providers across uninstall: provider auth files on the
# remote (e.g. ~/.openscientist/providers/claudecode.env) survive uninstall
# (we only remove the install dir + service unit files), so the renderer
# should still see the provider state. Plane/kimi keys are reset.
updated="$(jq_index --arg n "$name" --arg at "$(now_iso)" '
  .machines[$n] |= (del(.lastError))
  | .machines[$n].status        = "unprovisioned"
  | .machines[$n].bundleVersion = null
  | .machines[$n].provisionedAt = null
  | .machines[$n].services      = {
      plane: null,
      kimi:  null,
      providers: ((.machines[$n].services.providers // {}))
    }
  | .machines[$n].remote        = {home:null, prefix:null}
')"
write_index "$updated"

log "uninstalled $name; registry entry preserved (use remove.sh to delete it)"
