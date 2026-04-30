---
name: machine-setup
description: Provision and retire remote Linux machines that host the OpenScientist agent stack (plane server + kimi-server + provider CLIs). Covers the lifecycle that *changes persistent state* — registering a new machine in `~/.openscientist/machines/index.json`, opening the SSH ControlMaster the first time, rsyncing the cloud-run bundle and running its installer, opt-in installs of `claudecode` / `codex` provider CLIs (with auth), uninstalling services on the remote, and removing the machine from the registry. Use this skill whenever the user wants to add / connect / provision / set up / install / bring up / retire a machine. Day-to-day operation of an already-provisioned machine — listing, switching active, status probes, reopening a dropped tunnel, triggering deep runs, claiming results — lives in the sibling `machine-use` skill; this skill is self-contained and hands off conceptually once `setup.sh` lands `status: "ready"`. All scripts are shell-native (ssh / scp / rsync / curl / jq) and drive the registry file directly.
metadata:
  skill-author: OpenScientist
category: infrastructure
---

# Machine Setup

Provision, install, and retire the machines that run deep runs.

This skill is the **lifecycle complement** to the sibling `machine-use` skill. Use **machine-setup** for everything that changes the persistent state of a machine: registering it in the index, rsyncing the cloud-run bundle, installing plane + kimi-server, adding provider CLIs (claudecode, codex), deprovisioning services, removing from the registry. After `setup.sh` lands `status: "ready"`, the user typically wants to switch to `machine-use` for activation, status probes, deep runs, and result claims — that's its surface, not this one's.

The two skills are intentionally self-contained: each carries its own copy of any helper script it needs. Both read and write the same registry file (`~/.openscientist/machines/index.json`); see `machine-use/SKILL.md` for the full schema.

A **machine** is a remote Linux box (or the laptop itself, reserved name `local`) that hosts the OpenScientist agent stack: the plane server (HTTP API on port 5495), the kimi-server (HTTP API on port 5494), and zero or more external provider CLIs (claudecode, codex).

## Where things live (setup-side paths)

| Path | Purpose |
|---|---|
| `~/.openscientist/machines/index.json` | machine registry (authoritative; written by every script in this skill) |
| `~/.openscientist/auth.json` | SPOT auth token, synced to remote during install. The synced copy's `base_url` is rewritten to `https://aloo-gobi.fydy.ai` (override via `OPENSCIENTIST_REMOTE_BASE_URL`) so the remote hits the prod backend even when the laptop's local `base_url` is `http://localhost:8000`. Laptop copy is untouched. |
| `~/.openscientist/cloud-run/<arch>/` | **cloud-run bundle** — symlink Electron main maintains at startup. Points at `<app-resources>/cloud-run/` in a packaged app, or at `frontend/electron/cloud-run/` in dev. `install.sh` reads from here and nowhere else in production. |
| `~/.openscientist/providers/<name>.env` *(on remote)* | per-provider env file the systemd units pick up via `EnvironmentFile=-…`. Created/updated by `setup-claude.sh --token` and `setup-codex.sh`. |
| `~/.local/share/openscientist/` *(on remote)* | installed binaries + plane dir, laid down by `install.sh` |
| `~/.config/systemd/user/{kimi,plane}.service` *(on remote)* | user-level systemd units rendered by the bundle installer |

`install.sh` resolves the bundle from `$OPENSCIENTIST_CLOUD_RUN_BUNDLE` (escape hatch for manual dev testing) or `~/.openscientist/cloud-run/<arch>/` (canonical). **It does not prompt, guess resource dirs, or search the filesystem.** If the symlink is missing, the error tells you to start Electron — do not treat "bundle not found" as a user-input prompt.

### Bundle layout (what the symlink points at)

**It's a directory, not a file.** Do not point `$OPENSCIENTIST_CLOUD_RUN_BUNDLE` at `plane.tar.gz` — that's *one entry inside* the bundle. The directory is shipped by `frontend/scripts/build-cloud-run-bundle.sh` and has this layout:

```
<bundle>/
├── install.sh         # runs on the remote after rsync
├── kimi-server        # PyInstaller binary, executable
├── plane.tar.gz       # plane node bundle (tarred, unpacked on remote)
├── manifest.json      # {version, kimiSha, planeSha, commits}
└── systemd/
    ├── kimi.service
    └── plane.service
```

Whether you're in dev or running a packaged build, `install.sh` always reads the bundle through `~/.openscientist/cloud-run/<arch>/`. That symlink is created/refreshed by Electron main on every app start, so the only requirement is that Electron has started at least once since the last update. You never set `$OPENSCIENTIST_CLOUD_RUN_BUNDLE` in normal operation; the env var exists solely for manual dev testing when you want to point at a custom-built bundle.

Never run the bundle's own `install.sh` directly. Always go through `machine-setup/scripts/install.sh`, which rsyncs the bundle to `~/.openscientist/cloud-run/` on the remote and invokes the bundle installer with the right `STAGE_DIR` environment variable pointed at that path. Manually creating `~/.openscientist/stage/` on the remote is a band-aid — it won't contain the files the installer expects.

## Scripts

All scripts live in `scripts/`. They take named or positional args, emit structured output on stdout (usually JSON), log progress to stderr, and exit non-zero on failure. Every script sources `_common.sh`. Helpers and the SSH-tunnel primitive (`reconnect-ssh.sh`) are duplicated from `machine-use` — this skill is self-contained and never reaches across to its sibling.

| Script | Purpose |
|---|---|
| `setup.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key K [--port P]]` | **Preferred entry point when the user says "add / connect / provision / set up a machine".** One-shot wrapper that runs `add` → `reconnect-ssh` → `install` in order, without pausing between steps. Skips the add step if the machine is already registered. Emits a single `{name, status, bundleVersion, lastError}` JSON line on stdout; step-by-step progress on stderr. |
| `add.sh <name> --host H --user U --key K [--port P]` | Add a new machine as `status: "unprovisioned"`. Use directly only if the user explicitly wants to register without installing; otherwise prefer `setup.sh`. |
| `install.sh <name> [--bundle PATH]` | rsync the bundle to the remote and run the remote installer. Installs **plane + kimi only** — provider CLIs are opt-in via the two scripts below. Updates `status` and `bundleVersion`. Calls `reconnect-ssh.sh` internally to ensure the ControlMaster is up before scp/rsync. |
| `reconnect-ssh.sh <name>` | Open or repair the SSH ControlMaster. Idempotent. A copy of the same script also lives in `machine-use`. |
| `setup-codex.sh <name>` | Opt-in: installs `@openai/codex` on the remote (user-prefix npm, no sudo) and rsyncs `~/.codex/` across. Verifies with `codex login status`. Updates `services.providers.codex`. |
| `setup-claude.sh <name> [--token TOKEN]` | Opt-in: installs `@anthropic-ai/claude-code` on the remote. With `--token` (from `claude setup-token` on the laptop), writes `CLAUDE_CODE_OAUTH_TOKEN` to the provider env file the systemd units already pick up. Without `--token`, installs only and records `authed: false` until the user logs in manually or re-runs with a token. Verifies with `claude auth status --json`. |
| `uninstall.sh <name>` | Stop and disable services on the remote; clear remote install dir. Keeps the machine in the registry (use `remove.sh` after). |
| `remove.sh <name>` | Delete from registry. Refuses if machine is active or has `status: "ready"` (force with `--force`). |

## Workflows

Scripts resolve their own location via `$(dirname "$0")`, so invoke them directly by path. After world-model sync they land under `${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts/` — the sync target is the current work_dir (space root for chat, worktree path for deep runs), never home.

**Always prefix invocations with `bash`** — `bash $SCRIPTS/setup.sh …`, not `$SCRIPTS/setup.sh …`. World-model sync does not preserve the executable bit, so direct invocation fails with "Permission denied" on every fresh sync. You can also `chmod +x $SCRIPTS/*.sh` once as a setup step, but the `bash` prefix is idempotent and works without that.

### Set up a new machine

**All of these phrasings mean the same thing — run `setup.sh`, don't ask which one:**

> "add a machine" · "connect a machine" · "provision a machine" · "set up a machine" · "install a machine" · "bring up a machine"

The only exception is if the user *explicitly* says they want to register without installing (e.g., "just add it, don't install anything") — in that case, use `add.sh` directly. Otherwise, they want a working machine end-to-end.

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts
bash $SCRIPTS/setup.sh osci-math
```

`setup.sh` runs `add` → `reconnect-ssh` → `install` in order without pausing between steps. It defaults to `--from-ssh-config <name>` for connection details, so any machine defined in `~/.ssh/config` works with no further input. Pass `--host H --user U --key K [--port P]` to override / supply missing fields.

Only after `setup.sh` exits 0 with `"status":"ready"`, stop and ask what's next. Good prompts then:

- "Want me to activate this machine now (open the Electron tunnel)?" → that's a `machine-use` action.
- "Need Claude Code or Codex on this machine? Each is an opt-in step." → still `machine-setup`.

Do **not** silently run `setup-codex.sh`, `setup-claude.sh`, or `machine-use`'s `activate.sh` as part of setup — those are separate decisions the user should make explicitly.

#### `install.sh` timeouts are not install failures

`install.sh` (wrapped by `setup.sh`) can run for several minutes on a cold machine — bundle rsync + remote Node bootstrap + systemd unit restart + first healthz. Many agent tool harnesses cap bash commands at 1–2 minutes. **When your tool reports a timeout, do not conclude the install failed** — it almost certainly succeeded or is still in flight. The authoritative signal is `~/.openscientist/machines/index.json`:

```bash
NAME=osci-math
until jq -re --arg n "$NAME" '.machines[$n].status | test("ready|error")' ~/.openscientist/machines/index.json >/dev/null; do
  sleep 5
done
jq --arg n "$NAME" '.machines[$n] | {status, bundleVersion, lastError}' ~/.openscientist/machines/index.json
```

Run this loop after a timed-out `setup.sh`/`install.sh` invocation. The `status` field transitions `unprovisioned → provisioning → ready` (or `error`, with `lastError` set). Never re-run `setup.sh` while `status` is still `provisioning` — you'll just rsync the bundle twice. And never ask the user "did the install fail?" — the file answers that; you read it.

#### Before asking the user for host/user/key — check `~/.ssh/config` first

`setup.sh` does this automatically (it defaults to `--from-ssh-config <name>`), so in the common case you never need to probe the config manually. The note below is for when that default isn't enough — e.g., the alias exists but `setup.sh` reports a missing field, or the user named the machine something different from the ssh alias.

```bash
# Does the user's requested name resolve via ssh_config?
ssh -G <name> 2>/dev/null | awk '
  $1=="hostname"     {host=$2}
  $1=="user"         {user=$2}
  $1=="port"         {port=$2}
  $1=="identityfile" {key=$2}
  END {
    if (host && user && key) {
      gsub(/^~/, ENVIRON["HOME"], key)
      printf("host=%s\nuser=%s\nport=%s\nkey=%s\n", host, user, (port ? port : "22"), key)
    }
  }
'
```

If the output has all four fields, you have enough to call `setup.sh` without bothering the user. If something's missing (e.g., no IdentityFile — the user's auth-sock flow), ask only for the gap. Only fall back to asking for everything when `ssh -G` returns defaults for an unknown host.

#### Under the hood

`setup.sh` is just a thin wrapper; if you need to drive the steps manually (e.g., to debug one step in isolation) they are:

1. `add.sh` — registers the machine as `status: "unprovisioned"`. `setup.sh` skips this if the machine is already registered.
2. `reconnect-ssh.sh` — opens the SSH ControlMaster. Idempotent; `install.sh` calls it internally as well. Running it before `install.sh` surfaces SSH-key/host-key problems before you spend time rsyncing a bundle.
3. `install.sh` — rsyncs the bundle, runs the remote installer, and syncs `~/.openscientist/auth.json` (with `base_url` rewritten to the remote-reachable backend — see "Where things live").

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts
bash $SCRIPTS/add.sh osci-math --from-ssh-config osci-math
bash $SCRIPTS/reconnect-ssh.sh osci-math
bash $SCRIPTS/install.sh osci-math
```

### Provider auth (claude code, codex)

`install.sh` intentionally does **not** install the provider CLIs. Each provider is its own opt-in step because the auth mechanics differ, and a given machine might only need one. Both scripts are idempotent — re-run to refresh.

#### Codex

Codex stores auth in a file (`~/.codex/auth.json`) that's portable for the same user. `setup-codex.sh` installs the CLI and rsyncs the whole `~/.codex/` directory:

```bash
bash $SCRIPTS/setup-codex.sh osci-math
```

Under the hood: `npm install -g --prefix ~/.local @openai/codex` on the remote (no sudo), rsync `~/.codex/ → remote:.codex/`, restart kimi+plane so the PATH drop-in takes effect, then `codex login status` confirms. Requires the laptop to be logged in already (`codex login` on the laptop first if it isn't).

#### Claude

Claude's interactive OAuth credentials sit in the laptop's OS keychain and aren't portable. The correct path is the headless token flow: `claude setup-token` generates a long-lived `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…` on the laptop; we write that into a file the remote's systemd units already read via `EnvironmentFile=-${PROV_DIR}/claudecode.env`.

Two-phase because setup-token needs user action on the laptop:

```bash
# Phase 1 — install only.
bash $SCRIPTS/setup-claude.sh osci-math
```

At that point the agent has two options to offer the user:

- **Option A — headless (agent-friendly):**
  1. Ask the user to run `claude setup-token` on *this* laptop.
  2. Ask them to paste the `CLAUDE_CODE_OAUTH_TOKEN=…` line.
  3. Finish via `bash $SCRIPTS/setup-claude.sh osci-math --token sk-ant-oat01-…`.

  The token is scp'd to the remote (never passed via ssh argv, so it doesn't appear in `ps`) and written to `~/.openscientist/providers/claudecode.env` with mode 600. `claude auth status --json` verifies it actually works; `authed: true/false` in `index.json` reflects that probe, not just the install state.

- **Option B — manual:** the user ssh's into the remote and runs `claude` interactively to log in. After they've done that, re-run `setup-claude.sh osci-math` (no token) to re-probe and flip `authed: true`.

Ask the user which they prefer; both are fully supported.

> **Do not substitute either option with `systemctl --user set-environment CLAUDE_CODE_OAUTH_TOKEN=…`.** That's the canonical shortcut agents reach for when they see services don't read `~/.bashrc` — it "works" in the current session because user units inherit the manager env, but it is **ephemeral**: a reboot, logout, or `systemctl --user daemon-reexec` wipes it and the machine silently goes back to unauthed. The bundle's unit files already have `EnvironmentFile=-${PROV_DIR}/claudecode.env` wired in — dropping a file at that path via `setup-claude.sh --token` is the only durable mechanism. If you find yourself on a box where the manager env has a token but the file doesn't (e.g. someone ran `set-environment` previously), run `setup-claude.sh <name>` with no args first: it will detect that state and tell you to rescue the token into the file.

#### Why a sanity probe matters

Both setup scripts end with a real auth probe, not just a `--version` check:

- `codex login status` — exits 0 and prints `Logged in using ChatGPT` (or `… using API key`) when authed.
- `claude auth status --json` — returns `{"loggedIn": true, "authMethod": "...", "email": "..."}`.

The result is written back into `index.json` as `services.providers.<name>.authed`. If either reports unauthed, the script warns loudly and records `authed: false` — so the next `machine-use` status probe reflects reality.

#### PATH for systemd services

`npm install -g --prefix ~/.local` puts the binary at `~/.local/bin/{claude,codex}`. systemd user services have a minimal default `PATH` that may not include that directory, so both setup scripts drop in `~/.config/systemd/user/{kimi,plane}.service.d/path.conf` to prepend `%h/.local/bin`. One-time per machine, idempotent on re-run.

### Watching a long install (don't rely on background-task notifications)

`install.sh` takes anywhere from ~20 seconds (warm rsync, same bundle, same machine) to several minutes (cold install on a freshly-provisioned box). If you start it with `run_in_background=true`, your platform may or may not reliably notify you on completion. Prefer one of these:

- **Foreground it.** Unless you have concurrent work to do, just run it synchronously. It's not that long.
- **Poll `index.json.status`.** `install.sh` transitions the machine's status through `unprovisioned → provisioning → ready` (or `error` with `lastError` set). A short loop works:
  ```bash
  bash $SCRIPTS/install.sh $NAME &   # or run_in_background
  until jq -re --arg n "$NAME" '.machines[$n].status | test("ready|error")' ~/.openscientist/machines/index.json >/dev/null; do
    sleep 3
  done
  jq --arg n "$NAME" '.machines[$n] | {status, lastError}' ~/.openscientist/machines/index.json
  ```
- **Tail the remote systemd journal** while the install is mid-flight to watch service startup:
  ```bash
  ssh <machine> 'journalctl --user -u kimi -u plane -f -n 50'
  ```

If `machine-use`'s `status.sh` reports `sshMaster: down` during the install, that's normal — the master cycles during install.sh's reconnect + bundle transfer. Don't interpret it as failure.

### Retire a machine

```bash
# Deactivate first (if currently active) — that's a machine-use action:
bash ${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts/deactivate.sh
# Then this skill takes over:
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-setup/scripts
bash $SCRIPTS/uninstall.sh osci-math       # stop + remove services on remote
bash $SCRIPTS/remove.sh osci-math          # delete from index.json
```

`remove.sh` refuses to delete an active or ready machine without `--force`, to prevent accidental loss of provisioned state.

## Writing conventions

- **Exit codes**: 0 success, 1 user error (bad args, unknown machine), 2 environment error (missing index, SSH unreachable).
- **Stdout is structured**, **stderr is human log**. Agents should parse stdout as JSON where the script emits it.
- **Atomic writes only** for `index.json` — `_common.sh`'s `write_index` does temp+rename, never append.
- **Never hardcode** machine names or paths in new scripts — always go through `_common.sh` helpers.
- **Timeouts everywhere**: `ssh -o ConnectTimeout=5 -o BatchMode=yes`, curl `-m 5`. Never hang the agent.

## Troubleshooting

| Symptom | First check | Fix |
|---|---|---|
| `setup.sh` or `install.sh` "timed out" in your tool harness | `jq --arg n "<name>" '.machines[$n] \| {status, lastError}' ~/.openscientist/machines/index.json` — if `status` is `ready`, it finished successfully; if `error`, `lastError` tells you why; if still `provisioning`, it's mid-install. | Do **not** re-run `setup.sh`/`install.sh` while `status == "provisioning"` (you'll rsync the bundle twice). Poll the file every few seconds until `status` is `ready` or `error`. `status` is the authoritative outcome — the shell exit code of a wrapped/timed-out invocation is not. |
| `install.sh` fails in stage 2 (Node) | SSH into machine, `node --version` | See `remote/install.sh` comments — apt/dnf/tarball fallbacks. |
| After reboot, services don't start | `loginctl show-user $USER` on remote | Run `sudo loginctl enable-linger $USER` on remote once. |
| Claude auth works now but breaks after reboot / daemon-reexec | `ssh <name> systemctl --user show-environment \| grep CLAUDE_CODE_OAUTH_TOKEN` — if the var is there but `~/.openscientist/providers/claudecode.env` is empty, a previous agent set it via `set-environment` (ephemeral). | Grab the token from `systemctl --user show-environment`, then `setup-claude.sh <name> --token <value>`. The script writes the env file and proactively `unset-environment`s the manager-level var so the file becomes the sole source. |

## What this skill does not do

- It does not handle day-to-day operation of a provisioned machine. Once `setup.sh` lands `status: "ready"`, switch to `machine-use` for `activate.sh`, `status.sh`, `trigger-deep-run.sh`, `fetch-session-branch.sh`, `reconnect-ssh.sh`.
- It does not build the bundle. That's the frontend repo's `build:cloud-run-bundle` script. This skill consumes a prebuilt bundle.
- It does not manage LocalForward rules. Electron owns tunnel port allocation.
- It does not rotate auth tokens during normal operation. To refresh, re-run `install.sh` — the auth-sync stage re-copies `~/.openscientist/auth.json` (rewriting `base_url` to `https://aloo-gobi.fydy.ai` — override via `OPENSCIENTIST_REMOTE_BASE_URL` — so the remote reaches the prod backend regardless of the laptop's local `base_url`).
