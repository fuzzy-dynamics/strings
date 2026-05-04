---
name: machine-setup
description: Provision and retire remote Linux machines that host the OpenScientist agent stack (plane server + kimi-server). Covers the lifecycle that *changes persistent state* — registering a new machine in `~/.openscientist/machines/index.json`, opening the SSH ControlMaster the first time, rsyncing the cloud-run bundle and bringing up systemd services, uninstalling on the remote, and removing from the registry. Use this skill whenever the user says "add / connect / provision / set up / install / bring up / retire" a machine. Day-to-day operation of an already-provisioned machine — listing, switching active, status probes, deep runs, claiming results, and **provider CLI installs (claude, codex)** — lives in the sibling `machine-use` skill.
metadata:
  skill-author: OpenScientist
category: infrastructure
---

# Machine Setup

Provision, install, and retire the machines that run deep runs.

This skill is the lifecycle complement to `machine-use`. After `setup.sh` lands `status: "ready"`, switch to `machine-use` for activation, verify, sync-space, deep runs, **and provider CLI installs**.

A **machine** is a remote Linux box (or the laptop itself, reserved name `local`) that hosts the OpenScientist agent stack: the plane server (HTTP API on port 5495), the kimi-server (HTTP API on port 5494), and zero or more provider CLIs (claude, codex) installed separately via `machine-use/install-claude.sh` / `install-codex.sh`.

This skill follows the contracts in `frontend/docs/machine-provisioning-spec.md`. Read that doc for the design rationale; this README is the agent-facing reference for *how to drive* the scripts.

## State machine (spec §5)

```
unprovisioned --add.sh--> unprovisioned (entry exists, ssh not validated yet)
unprovisioned --reconnect-ssh.sh--> setup-complete
                                 \--> broken
setup-complete --install.sh--> provisioning --[verify]--> ready
                                          \--> broken
ready --install.sh--> provisioning  (rerun preserves services.providers.*)
                  \--> broken
```

The renderer's machine selector enables only `ready` machines. `provisioning` and `verifying` show a spinner; `broken` shows red with the `lastError.message` tooltip; `setup-complete` and `unprovisioned` show gray with a "run install.sh" hint.

## Where things live

| Path | Purpose |
|---|---|
| `~/.openscientist/machines/index.json` | machine registry (authoritative; written via atomic tmp+rename through `_lib/provisioning.sh`'s `index_update`). |
| `~/.openscientist/machines/<name>.lock` | per-machine `flock` for the duration of any setup/install/uninstall script. |
| `~/.openscientist/machines/<name>.lasterror` | forensic floor (spec §3). Append-only NDJSON; mark_broken writes here before any jq invocation. |
| `~/.openscientist/auth.json` | SPOT auth token, synced to remote during install. The synced copy's `base_url` is rewritten to `https://aloo-gobi.fydy.ai` (override via `OPENSCIENTIST_REMOTE_BASE_URL`). Laptop copy is untouched. |
| `~/.openscientist/cloud-run/<arch>/` | **cloud-run bundle** — symlink Electron main maintains at startup. Points at `<app-resources>/cloud-run/` in a packaged app, or `frontend/electron/cloud-run/` in dev. |
| `~/.openscientist/ssh/<name>.sock` | SSH ControlMaster socket. |
| `~/.openscientist/ssh/<name>.ports.json` | renderer-written snapshot of forwarded local ports (used by `verify.sh` pattern 2). |
| `~/.local/share/openscientist/` *(on remote)* | installed binaries + plane dir, laid down by `remote-stage.sh`. |
| `~/.config/systemd/user/{kimi,plane}.service` *(on remote)* | user-level systemd units rendered atomically by `remote-stage.sh` from the bundle's templates. |
| `~/.openscientist/logs/<script>-<ts>.log` *(on remote)* | per-invocation verbose logs. Path appears in every structured outcome. |

## Bundle layout (no `install.sh` inside the bundle)

Per spec §4.2.1, the bundle ships **only artifacts** — no executable orchestration. The laptop-side `install.sh` (this skill) is the single source of truth and pipes `remote-stage.sh` over `ssh bash -s` for the remote work.

```
<bundle>/
├── kimi-server        # PyInstaller binary, executable
├── plane.tar.gz       # plane node bundle (deps autoscanned at build time)
├── manifest.json      # {schemaVersion: 2, bundleVersion: sha256(plane.tar.gz), ...}
└── systemd/
    ├── kimi.service   # template with ${...} placeholders
    └── plane.service  # template with ${...} placeholders
```

`bundleVersion = sha256(plane.tar.gz)` is the canonical version field. `install.sh` reads it from `manifest.json` and writes it into `index.json` so the renderer can show version skew across machines.

## Universal script contract (spec §3)

Every script in this skill obeys:

- **Args:** single positional `<name>`, long-form flags only.
- **Stdout:** ends with one JSON document. Success: `{ok:true, name, stage:"done", ...}`. Failure: `{ok:false, name, stage, message, ...}`.
- **Stderr:** NDJSON progress lines, one per stage transition.
- **Exit 0** iff and only if `ok=true`.
- **Failure path:** `mark_broken` writes `<name>.lasterror`, sets `status="broken"`, sets `lastError`, prints the JSON, exits 1.
- **Locking:** `flock` on `<name>.lock` for the duration. A second concurrent invocation fails immediately with `{stage:"lock"}` rather than blocking.

## Scripts

| Script | Purpose | Wrapper budget |
|---|---|---|
| `setup.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key K [--port P]] [--force]` | **Preferred entry point.** Wraps `add` → `reconnect-ssh` → `install` in order. Skips `add` if the machine is already registered. | 425s |
| `add.sh <name> [--force]` | Register entry as `unprovisioned`. Does NOT reach the machine. | 15s |
| `reconnect-ssh.sh <name>` | Open or repair the SSH ControlMaster. Marks `setup-complete` on first success. | 90s |
| `install.sh <name> [--bundle PATH]` | rsync bundle, pipe remote-stage.sh, run verify-from-laptop, write `ready`. | 360s |
| `remote-stage.sh` | **Not invoked directly.** Piped over stdin by install.sh; runs on the remote. | (caller-bounded) |
| `uninstall.sh <name>` | Stop services on remote, clear install dir. Keeps the machine in the registry. | 90s |
| `remove.sh <name> [--force]` | Delete from registry. Refuses an active or ready machine without `--force`. | 5s |

## Workflows

Scripts resolve their own location via `$(dirname "$0")`. After world-model sync they land at `${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts/`.

**Always prefix with `bash`** — `bash $SCRIPTS/setup.sh …`. World-model sync does not preserve the executable bit.

### Set up a new machine

All of these phrasings mean the same thing — run `setup.sh`:

> "add a machine" · "connect a machine" · "provision a machine" · "set up a machine" · "install a machine" · "bring up a machine"

The only exception is if the user *explicitly* says "just register, don't install" — then call `add.sh` directly.

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts
bash $SCRIPTS/setup.sh osci-math
```

`setup.sh` defaults to `--from-ssh-config <name>`, so any machine in `~/.ssh/config` works with no further input. Pass `--host H --user U --key K [--port P]` to override or supply missing fields.

After `setup.sh` exits 0 with `"status":"ready"`, ask what's next:

- "Want me to install Claude Code or Codex on this machine? Each is opt-in." → `machine-use` provider scripts.
- "Want me to activate this machine in the renderer?" → `machine-use/activate.sh` (which the renderer triggers automatically on selection anyway).

Do **not** silently chain provider installs.

### Reading structured outcomes

Every script's stdout ends with one JSON document. Parse it directly:

```bash
out=$(bash $SCRIPTS/setup.sh osci-math)
ok=$(printf '%s' "$out" | tail -1 | jq -r .ok)
if [[ "$ok" == "true" ]]; then
  bv=$(printf '%s' "$out" | tail -1 | jq -r .bundleVersion)
  echo "ready @ ${bv:0:16}"
else
  printf '%s' "$out" | tail -1 | jq -r '"\(.stage): \(.message)"'
fi
```

For long-running scripts where your tool harness times out before completion: do **not** assume failure. Read `index.json` instead. The `status` field is authoritative.

```bash
NAME=osci-math
until jq -re --arg n "$NAME" '.machines[$n].status | test("ready|broken")' ~/.openscientist/machines/index.json >/dev/null; do
  sleep 3
done
jq --arg n "$NAME" '.machines[$n] | {status, lastError, bundleVersion}' ~/.openscientist/machines/index.json
```

Never re-run `setup.sh` / `install.sh` while `status == "provisioning"` — you'll trip the per-machine `flock` and waste a round.

### Reading `<name>.lasterror` (forensic floor)

If `mark_broken` ran, `~/.openscientist/machines/<name>.lasterror` has every failure record appended (one JSON line each). The most recent line is at the bottom:

```bash
tail -1 ~/.openscientist/machines/osci-math.lasterror | jq .
```

This file is **immune to jq failures and disk-write contention** — it's written via `printf >>` before any structured index update is attempted. So even if the index update itself failed, the forensic line is still there.

### `index.json` half-write recovery

If a previous Electron crash or SIGKILL left a machine in `provisioning` or `verifying` with no live process, the renderer's startup reaper (`cloudRun.init()` in the Electron app) downgrades it to `broken` with `lastError={stage:"reaper", message:"abandoned ... from prior session"}` after a 10-minute cutoff. From that point the machine is selectable for re-install.

If you see a `status: "provisioning"` that's clearly stale (no `flock` held, no recent log activity), and the renderer's reaper hasn't fired yet, force a manual reset by re-running `install.sh` — it acquires the lock and overwrites the state.

### Retire a machine

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts
bash $SCRIPTS/uninstall.sh osci-math       # stop + clear services on remote
bash $SCRIPTS/remove.sh osci-math          # delete from index
```

`remove.sh` refuses an active or `ready` machine without `--force`.

## Troubleshooting

| Symptom | Diagnostic | Fix |
|---|---|---|
| `setup.sh` reports `{ok:false, stage:"bundle-resolve"}` | `ls -l ~/.openscientist/cloud-run` | Restart Electron — main maintains the symlink at startup. Do NOT prompt the user for `--bundle` unless they explicitly opted into a custom build. |
| `setup.sh` reports `{stage:"remote-stage", remoteLogTail:"..."}` | `cat ~/.openscientist/machines/<name>.lasterror \| tail -1 \| jq .` | Read the embedded `remoteLogTail` and `serviceLogs.{kimi,plane}`. Common: `Cannot find module 'js-yaml'` means a stale bundle — rebuild via `frontend/scripts/build-cloud-run-bundle.sh` (the new build's smoke test catches missing deps). |
| `setup.sh` reports `{stage:"verify-from-laptop", verifyOutput:"..."}` | `bash ${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts/verify.sh <name>` | Run verify.sh standalone for a fresh probe. The remote services may have started but be returning non-200; check `journalctl --user -u kimi -u plane -n 50` over SSH. |
| Tool harness "timed out" before script returned | `jq --arg n "<name>" '.machines[$n] \| {status, lastError}' ~/.openscientist/machines/index.json` | If `status` is `ready` or `broken`, the script finished — read the structured outcome. The harness exit code is not authoritative. |
| `{stage:"lock", message:"another op in progress"}` | `ls -l ~/.openscientist/machines/<name>.lock`; `lsof ~/.openscientist/machines/<name>.lock` | Real concurrent invocation: wait. Stale lock from a SIGKILL: the renderer's startup reaper handles it after 10 min, OR delete the lockfile manually if no process holds it. |
| Service won't survive reboot | `ssh <name> 'loginctl show-user $USER \| grep Linger'` | `ssh <name> 'sudo loginctl enable-linger $USER'`. `remote-stage.sh` attempts this with passwordless sudo but logs a warning if unavailable. |

## What this skill does NOT do

- **Does not install provider CLIs.** Use `machine-use/install-claude.sh` and `machine-use/install-codex.sh` (spec §4.3, §4.4). Provider installs require `status="ready"` and live in the sibling skill because they're a runtime concern, not a provisioning one.
- **Does not run health probes.** Use `machine-use/verify.sh` (spec §4.5).
- **Does not build the bundle.** That's `frontend/scripts/build-cloud-run-bundle.sh`. This skill consumes a prebuilt bundle from `~/.openscientist/cloud-run/<arch>/`.
- **Does not manage LocalForward rules.** Electron's bridge owns tunnel port allocation; the renderer writes `<name>.ports.json` so verify.sh can find the forwarded ports.
- **Does not rotate auth tokens during normal operation.** Re-run `install.sh` — the auth-copy stage re-syncs `~/.openscientist/auth.json`.
