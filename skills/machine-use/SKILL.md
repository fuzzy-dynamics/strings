---
name: machine-use
description: Operate already-provisioned remote Linux machines that host the OpenScientist agent stack so deep runs can execute off-laptop. Covers day-to-day use — listing registered machines and inspecting their state, activating/deactivating which one is the current target (Electron opens or tears down the SSH tunnel based on this), live status probes (SSH ControlMaster, systemd services, healthz), reopening a dropped tunnel, triggering deep runs end-to-end (worktree prep + plane POST), and claiming a run's result by fetching the `osci/<sid>` branch back into the laptop's `.git`. Use this skill whenever the user wants to switch active machine, check why runs aren't showing up, repair a tunnel, spawn a deep run, or pull a finished run's result. Lifecycle (registering, provisioning, installing providers, retiring) lives in the sibling `machine-setup` skill — switch to it for those flows. Reaches the remote over SSH using keys the user already has on the laptop; all scripts are shell-native (ssh / scp / rsync / curl / jq) and drive the registry file directly.
metadata:
  skill-author: OpenScientist
category: infrastructure
---

# Machine Use

Use the machines that have already been set up to run deep runs.

This skill is the **runtime complement** to `machine-setup`. After `machine-setup/setup.sh` lands a machine at `status: "ready"`, every later interaction — listing, activating, status probes, reopening dropped tunnels, triggering deep runs, claiming results — happens through this skill. Lifecycle changes (register, install plane + kimi, install provider CLIs, uninstall, remove from registry) live in `machine-setup`.

A **machine** is a remote Linux box (or the laptop itself, reserved name `local`) that hosts the OpenScientist agent stack: the plane server (HTTP API on port 5495), the kimi-server (HTTP API on port 5494), and zero or more external provider CLIs (claudecode, codex). When a machine is **active**, the Electron app opens an SSH tunnel from the laptop so the UI can poll it as if it were local.

### Providers, explained once clearly

There are exactly three provider options for `--provider`:

- **`gecko`** — the built-in orchestrator that runs *inside* the kimi-server daemon on port 5494. `machine-setup`'s `install.sh` already provisions this on every machine; there is **no separate CLI, no npm package, no auth step**. If kimi-server is healthy (`status.sh` reports `services.kimi: ready`), then `gecko` is ready.
- **`claudecode`** — external Anthropic CLI. Install + auth via `machine-setup/scripts/setup-claude.sh`.
- **`codex`** — external OpenAI CLI. Install + auth via `machine-setup/scripts/setup-codex.sh`.

The wire-format string plane expects for the built-in option is `kimi` (historical — kept stable to avoid churning backend auth / session records). `trigger-deep-run.sh` accepts `gecko` (canonical), `openscientist-gecko`, and `kimi` (legacy) and canonicalizes them to `kimi` before POSTing. Prefer `gecko` in new invocations and docs — it removes the confusable collision with the kimi-server daemon name.

#### Zero configuration for gecko ↔ plane ↔ kimi-server

Every port and URL is hardcoded by the bundle at install time. There is **nothing for you to configure, nothing for the user to tell you**, and no config file to hunt for. Specifically:

- `kimi-server` always binds `127.0.0.1:5494` (systemd `Environment=KIMI_PORT=5494` in `kimi.service`).
- `plane` always binds `127.0.0.1:5495` and reaches kimi at `KIMI_SERVER_URL=http://127.0.0.1:5494` (both baked into `plane.service`).
- Both are on the same machine, on loopback, same user. No firewall, no DNS, no TLS involved.

**Client side — reaching plane from the laptop.** The above is *server-side* binding on a provisioned machine (remote or laptop-as-local). For *clients* on the laptop (scripts, gecko tools, UI-IPC callers), the authoritative URL is the environment variable `PLANE_SERVER_URL`. Electron main exports it into `process.env` at startup so every descendant process inherits it. The skill's scripts and all plane consumers in the frontend read that variable with **no fallback** — if it's missing, they error rather than silently defaulting to `127.0.0.1:5495`. Reason: the two addresses look identical in the happy path (laptop active, plane on 5495), but diverge the moment a dev run rebinds plane, a test harness mocks it, or anyone starts thinking of 5495 as a constant they can sprinkle through code.

If you catch yourself about to do any of the following, **stop and re-read this section** — you are hallucinating a config step that does not exist:

- Asking the user "what port is the kimi orchestrator on?" → Answer is always 5494. Don't ask.
- Looking for a plane config file to point at kimi-server → There isn't one; it's compiled into the systemd unit via `envsubst` at install time.
- Running `npm search` or `npm install` for anything named `kimi`, `kimi-cli`, `@x/kimi-*` → Unrelated third-party packages. Never install them.
- Setting `KIMI_SERVER_URL` in a shell, bashrc, or `set-environment` → It's already set correctly in the plane systemd unit; overriding it elsewhere will either be ignored or break routing.

If a `--provider gecko` run fails, the cause is **always** one of: (a) kimi-server unit unhealthy (`journalctl --user -u kimi -n 100`), (b) plane unit unhealthy (`journalctl --user -u plane -n 100`), (c) a genuine task-payload / auth / network problem *inside* the orchestrator — which you diagnose by reading the session's `meta.json` and `stdout.log` under `~/.kimi/plane/sessions/<sid>/`, not by reconfiguring ports.

All state lives in `~/.openscientist/machines/index.json`. Every script in this skill reads and/or writes that file.

## Where things live

| Path | Purpose |
|---|---|
| `~/.openscientist/machines/index.json` | machine registry (authoritative); home-scoped because it's machine state, not skill content |
| `~/.openscientist/ssh/<name>.sock` | SSH ControlMaster socket per machine |
| `${KIMI_WORK_DIR}/.openscientist/skills/<name>/...` | world-model skills, synced into the current work_dir on chat start (space root) and on each deep-run worktree creation. There is **no** home-level `~/.openscientist/skills/` — the sync target is always the work_dir. Mirrored to `${KIMI_WORK_DIR}/.claude/skills/`, `.codex/skills/`, `.agents/skills/`. |
| `~/.openscientist/worktrees/<sid>/` *(laptop for local runs; remote for remote runs)* | per-session worktree. Local worktrees share `.git` with the user's main repo and are **detached by design** — naming a branch per session at spawn time would flood the user's branch list. The `osci/<sid>` branch is created lazily by `fetch-session-branch.sh` only when the user claims a run's result. Remote worktrees live in `~/.openscientist/repos/<id>/bare.git`, a separate bare with isolated branch namespace, so they are born on branch `osci/<sid>` directly. |

For setup-side paths (cloud-run bundle, remote install dir, systemd units, `~/.openscientist/auth.json`), see `machine-setup/SKILL.md`.

## index.json schema

The canonical layout — written by both this skill and `machine-setup`, read by Electron's `MachineBridge` (see `frontend/electron/cloud-run/ssh-bridge.cjs`) — keeps SSH connection fields flat at the top level and nests only non-essential auxiliary metadata under `ssh`:

```jsonc
{
  "version": 1,
  "active": "osci-math",                    // reserved name "local" = laptop
  "machines": {
    "osci-math": {
      "name": "osci-math",
      "host": "34.57.180.63",               // required — top-level
      "user": "zeero",                      // required — top-level
      "port": 22,                           // required — top-level
      "ssh": {
        "keyPath":       "/home/zeero/.ssh/osci-math",  // required
        "keyPresent":    true,
        "keyMode":       "600",
        "controlSocket": "/home/zeero/.openscientist/ssh/osci-math.sock",
        "lastReachableAt": "2026-04-21T11:39:34Z"
      },
      "remote": {
        "home":   "/home/zeero",
        "arch":   "x86_64",
        "distro": "ubuntu-24.04",
        "nodeBin": "/usr/bin/node"
      },
      "status": "ready",                    // unprovisioned | provisioning | ready | degraded | error
      "services": {
        "plane":     { "status": "ready", "version": "2.0.0",  "port": 5495, "lastCheckedAt": "..." },
        "kimi":      { "status": "ready", "version": "1.25.0", "port": 5494, "lastCheckedAt": "..." },
        "providers": {
          "claudecode": { "installed": true, "authed": true, "version": "2.1.100"  },
          "codex":      { "installed": true, "authed": true, "version": "0.122.0"  },
          "gecko":      { "installed": true, "authed": true, "version": "1.25.0"   }
        }
      },
      "spaces":        {},
      "bundleVersion": "0.1.0+theater-01adbe20+frontend-ee4ba4e",
      "provisionedAt": "2026-04-21T07:56:00Z",
      "lastError":     null,
      "createdAt":     "2026-04-21T07:53:00Z"
    }
  }
}
```

The `active` field is read by Electron's machine watcher. Writing it from a script is how this skill switches machines — Electron sees the change and opens / tears down the SSH tunnel + LocalForward rules.

## Scripts

All scripts live in `scripts/`. They take named or positional args, emit structured output on stdout (usually JSON), log progress to stderr, and exit non-zero on failure. Every script sources `_common.sh`.

| Script | Purpose |
|---|---|
| `list.sh` | Print all machines (name, status, active flag). |
| `show.sh <name>` | Dump one machine's full record. |
| `active.sh` | Print the currently active machine name (or `local`). |
| `activate.sh <name>` | Set active machine. Electron opens tunnel. Refuses unknown names. |
| `deactivate.sh` | Clear active (falls back to `local`). |
| `status.sh <name>` | Live probe: SSH master, systemd services, /healthz, bundle version. Writes result back into the index. |
| `reconnect-ssh.sh <name>` | Reopen the ControlMaster if it has dropped. A copy of the same script also lives in `machine-setup`, which uses it for its own internal flows. |
| `trigger-deep-run.sh --provider P --prompt X --path DIR [--machine M] [--agent A] [--title T] [--spawned-by-session SID] [--spawned-by-role ROLE]` | **The only correct way to spawn a deep run.** Owns worktree prep end-to-end: calls `sync-repo.sh` internally, then POSTs to plane. Both the gecko agent and Electron main (for UI-initiated runs) call this. Emits JSON with `orchestratorId`, `sessionId`, `worktreePath`. `--spawned-by-session` / `--spawned-by-role` are optional provenance — pass them so `/orchestrators` can later be filtered by caller (e.g. "runs this gecko session spawned"). |
| `sync-repo.sh <name> --path P --session-id SID` | Primitive invoked by `trigger-deep-run.sh`. Snapshots current tree (dirty included), pushes to shared bare repo on remote over the ControlMaster, materializes per-session worktree. Local machines skip the push. Rarely called directly — prefer `trigger-deep-run.sh`. |
| `fetch-session-branch.sh --session-id SID --path LAPTOP_REPO [--machine M] [--branch NAME]` | **Claim** a deep run's result — make it addressable via `osci/<sid>` in the laptop's `.git` so the caller can `git checkout osci/<sid>`. For **remote** runs: fetches the branch from the remote bare over the existing ControlMaster (real network transfer). For **local** runs: queries plane for the worktree HEAD sha and runs `git branch -f osci/<sid> <sha>` — no data moves (objects are already in the shared `.git`), just the named ref is created on demand. This is the *only* place the `osci/<sid>` branch gets created for local runs, so unclaimed runs leave no branch behind. Emits JSON with `bareUrl`, `fetched`, `localRef`, `sha`. |

### Common helpers (`_common.sh`)

Every script sources `_common.sh`, which provides:

- `INDEX_PATH`, `SSH_DIR` — canonical paths (overridable via env).
- `ensure_index` — create empty `index.json` if missing.
- `write_index <json>` — atomic temp+rename, preserves 0600.
- `machine_exists <name>`, `machine_get <name>` — registry reads.
- `ssh_sock <name>`, `ssh_master_alive <name>` — tunnel state probes.
- `ssh_base_opts <name>` — builds `-i key -p port -o ControlPath=sock ...` array.

A duplicated copy of `_common.sh` (and `reconnect-ssh.sh`) also lives in `machine-setup/scripts/` so each skill is self-contained — both skills carry their own copies, kept in sync at the world-model level.

Always `source "$(dirname "$0")/_common.sh"` at the top of your script — do not duplicate these helpers inline.

## Workflows

Scripts resolve their own location via `$(dirname "$0")`, so invoke them directly by path. After world-model sync they land under `${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts/` — the sync target is the current work_dir (space root for chat, worktree path for deep runs), never home.

**Always prefix invocations with `bash`** — `bash $SCRIPTS/trigger-deep-run.sh …`, not `$SCRIPTS/trigger-deep-run.sh …`. World-model sync does not preserve the executable bit, so direct invocation fails with "Permission denied" on every fresh sync. You can also `chmod +x $SCRIPTS/*.sh` once as a setup step, but the `bash` prefix is idempotent and works without that.

### List, show, switch active

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts
bash $SCRIPTS/list.sh                     # all registered machines
bash $SCRIPTS/show.sh osci-math           # one machine's full record
bash $SCRIPTS/active.sh                   # the currently active machine
bash $SCRIPTS/activate.sh osci-math       # Electron opens the tunnel
bash $SCRIPTS/deactivate.sh               # falls back to "local"
```

`activate.sh` refuses unknown names — register/provision the machine first via `machine-setup/setup.sh`. Multiple machines share the laptop's port space but only one is active at a time; Electron allocates dynamic LocalForward ports per machine.

### Runs aren't updating in the sidebar

```bash
bash $SCRIPTS/status.sh osci-math           # look for sshMaster: "down" or services: "unreachable"
bash $SCRIPTS/reconnect-ssh.sh osci-math    # if master dropped
bash $SCRIPTS/status.sh osci-math           # verify recovery
```

If services are down (SSH master up, but kimi/plane unit inactive), ssh into the machine and `systemctl --user status kimi plane` — likely a crash loop. Check `journalctl --user -u kimi -n 100` for the reason, then `systemctl --user restart`.

### Trigger a deep run (local or remote)

**Every deep run goes through `trigger-deep-run.sh`.** The agent never creates a worktree itself; neither does the UI. This script owns that concern uniformly for both the reserved `local` machine and any remote, and both call sites (gecko's `Shell` tool, Electron main's `child_process`) invoke it the same way.

```bash
bash $SCRIPTS/trigger-deep-run.sh \
  --provider gecko \
  --prompt   "hi, summarize the repo" \
  --path     "$PWD"
  # --provider gecko | claudecode | codex
  #   gecko is the in-process kimi-server orchestrator — always available after machine-setup/install.sh.
  #   legacy aliases accepted for compat: kimi, openscientist-gecko
  # --machine <name>   (defaults to active)
  # --agent   <name>   (defaults to "osci-orchestrator")
  # --title   "..."    (optional, shown in the sidebar)
  # --space-id <id>    (optional, for skills-for-space)
```

Output on stdout (single-line JSON the caller consumes):

```json
{
  "orchestratorId": "orch_a021bb97-...",
  "sessionId":      "<root session id returned by plane>",
  "worktreePath":   "/home/zeero/.openscientist/worktrees/<8-hex>",
  "machine":        "osci-math",
  "provider":       "kimi",
  "branch":         "master",
  "dirty":          true
}
```

Stderr carries step-by-step progress (`machine=…`, `local worktree: …`, `git push …`, `posting to plane …`, `spawned: orchestrator=…`) — useful for debugging and for wiring progress toasts into the UI later.

#### What `trigger-deep-run.sh` does under the hood

1. Resolves target machine (explicit `--machine`, or `active.sh`).
2. Generates a random 8-hex session id.
3. Calls `sync-repo.sh <machine> --path $PATH --session-id <sid>`:
   - Local: `git worktree add --detach` from a `git stash create` snapshot. Deliberately detached — see the "Local worktrees are detached by design" note under "Where things live".
   - Remote: `git init --bare` on remote if absent → `git push` the stash-snapshot to `refs/heads/_osci-session/<sid>` over the existing SSH ControlMaster (via `GIT_SSH_COMMAND` with `-o ControlPath=$sock`) → `git worktree add -B "osci/<sid>"` on remote. Remote commits land on that branch and are fetched back to the laptop by `fetch-session-branch.sh`.
4. POSTs `/orchestrator/start` to plane:
   - Local: direct `curl "$PLANE_SERVER_URL/..."` (env var is required; the script dies with a clear error if unset — no 5495 fallback).
   - Remote: `ssh <master> curl http://127.0.0.1:5495/...` — the SSH ControlMaster is the transport, so the script works even when Electron's LocalForward isn't up (e.g., triggered from a background agent while the UI is closed). `5495` here is the remote's baked systemd port, not the laptop's env var.
5. Emits consolidated JSON.

#### How copies are avoided

On a remote there is **one bare repo per `(machine × repo)`** at `~/.openscientist/repos/<repo_id>/bare.git` where `repo_id = sha256(abs_laptop_path)[:16]`. Every session's worktree is a thin `git worktree add` against that shared bare — object store is shared, not duplicated; a worktree's `.git` is a file (pointing at the bare), not a directory. Git's pack protocol means the first push transfers the full history and every later push sends only delta objects. Ten runs against the same repo cost "full history once + deltas × 9," not ten full copies.

#### What if the tree is dirty

`sync-repo.sh` uses `git stash create` under the hood: a floating commit capturing the index + working tree without touching your branches or stash list. That SHA is pushed to the per-session ref; the remote worktree checks out exactly what the laptop looked like at trigger time, uncommitted hunks included. If the tree is clean, the script falls through to HEAD transparently.

#### Calling from Electron main (UI path)

The same script is invoked from Electron main via `child_process.execFile("bash", [synced_path, "--provider", ...])`. The `synced_path` resolves to `<work_dir>/.openscientist/skills/machine-use/scripts/trigger-deep-run.sh`, which is autosynced from the backend world-model on chat start (space root as work_dir) and every deep-run worktree creation. UI callers parse the JSON on stdout and stream stderr to a progress display (deferred to a later iteration).

### Claim a deep run's result

When the user wants to inspect or keep a finished run:

```bash
SID="<session-id>"
MACHINE="<name>"
LAPTOP_REPO="$PWD"
bash $SCRIPTS/fetch-session-branch.sh --session-id "$SID" --path "$LAPTOP_REPO" --machine "$MACHINE"
git -C "$LAPTOP_REPO" checkout "osci/$SID"
```

`fetch-session-branch.sh` is the *only* point at which `osci/<sid>` enters the laptop's `.git`. Runs the user never claims leave no branch behind.

## Writing conventions

- **Exit codes**: 0 success, 1 user error (bad args, unknown machine), 2 environment error (missing index, SSH unreachable).
- **Stdout is structured**, **stderr is human log**. Agents should parse stdout as JSON where the script emits it.
- **Atomic writes only** for `index.json` — `_common.sh`'s `write_index` does temp+rename, never append.
- **Never hardcode** machine names or paths in new scripts — always go through `_common.sh` helpers.
- **Timeouts everywhere**: `ssh -o ConnectTimeout=5 -o BatchMode=yes`, curl `-m 5`. Never hang the agent.

## Troubleshooting

| Symptom | First check | Fix |
|---|---|---|
| Deep run reports `status: completed` but `fetch-session-branch.sh` + `git checkout` shows an empty run | Get the worktree path: `curl -fsS -X POST $PLANE_SERVER_URL/sessions/<sid>/branch` (local) or `ssh <machine> curl -fsS -X POST http://127.0.0.1:5495/sessions/<sid>/branch` (remote). Then check it: `git -C <worktree> status --porcelain && git -C <worktree> log --oneline -5` (prefix with `ssh <machine>` for remote). If porcelain is non-empty and log shows only the pre-run base commit, the agent never committed its work. | This is an orchestrator-agent bug, not a transport issue. Recover in the worktree: `git -C <worktree> add -A && git -C <worktree> commit -m "Recover uncommitted work from session <sid>"` (prefix with `ssh <machine>` for remote). Then re-run `fetch-session-branch.sh --session-id <sid> --path "$LAPTOP_REPO" --machine <name>` — it will advance `osci/<sid>` to the new HEAD (local: `git branch -f` overwrites; remote: `git fetch --force` pulls the updated branch). Then `git -C "$LAPTOP_REPO" checkout osci/<sid>`. File the bug — the agent prompt for that role should enforce final-commit discipline. |
| `status.sh` shows `sshMaster: down` | `ls -la $SSH_DIR/<name>.sock` | `reconnect-ssh.sh <name>` |
| `/healthz` 200 locally but not through tunnel | `ssh -O check -S <sock> <name>` | Master is alive but LocalForward dropped — touch `index.json` to re-trigger Electron's forward setup, or `reconnect-ssh.sh`. |
| Multiple machines share a port on the laptop | Expected — Electron allocates dynamic local ports per machine; only one is active at a time. | Use `active.sh` to see which. |
| `--provider gecko` run fails and you're tempted to `npm install kimi-cli` or similar | `ssh <name> systemctl --user status kimi` — is kimi-server healthy? | **Do not install anything.** `gecko` is the kimi-server daemon at :5494 that `machine-setup/install.sh` already provisioned. There is no external kimi CLI. If kimi-server is unhealthy, check `journalctl --user -u kimi -n 100` and fix the daemon, or re-run `machine-setup/install.sh <name>`. If it's healthy and runs still fail, the cause is elsewhere (auth, network, task payload) — don't chase phantom packages. |
| You're about to ask the user "what port is kimi/plane on?" or look for a plane config file to point at kimi-server | Re-read the "Zero configuration for gecko ↔ plane ↔ kimi-server" section above. | Ports are hardcoded: kimi=5494, plane=5495, `KIMI_SERVER_URL=http://127.0.0.1:5494` — all baked into the systemd units by `machine-setup/install.sh`. There is no runtime configuration to do and no value for the user to supply. If a gecko run fails, diagnose service health and session logs — never reconfigure ports. |

## What this skill does not do

- It does not provision or install. To register a machine, install plane + kimi, or add provider CLIs, switch to `machine-setup`. Lifecycle entry points all live there; this skill is purely about operating an already-provisioned machine.
- It does not manage LocalForward rules. Electron owns tunnel port allocation; scripts only manage the ControlMaster.
- `trigger-deep-run.sh` is the end of this skill's "spawn" surface. For *observing* a running orchestrator (sessions, messages, mail), curl plane directly:
  - **Local (laptop is the target)**: use `$PLANE_SERVER_URL` — Electron main exports it into `process.env` at startup, so every child (kimi-server, gecko Shell subprocesses, the IPC `trigger-deep-run` invocation) inherits it. **No fallback**: if it's unset, fail loudly rather than guessing a port. Hardcoding `127.0.0.1:5495` is wrong because dev/test setups may bind elsewhere, and even in prod the env var is the canonical source of truth.
  - **Remote**: `ssh <machine> curl http://127.0.0.1:5495/...` over the existing ControlMaster. `5495` here is the *remote's* baked systemd port (from `machine-setup/install.sh`) — it is **not** the laptop's `$PLANE_SERVER_URL`. The laptop env var and the remote's loopback port live in two different address spaces; do not conflate them.
- It does not pull run artifacts back from remote beyond the `osci/<sid>` branch (via `fetch-session-branch.sh`). Other artifacts living inside a remote worktree are still readable through the tunneled plane and kimi endpoints.
- It does not prune old bare repos or worktrees. They accumulate. Future `prune-repo.sh` will GC repos untouched for N days; for now, manual cleanup is: `ssh <machine> "git --git-dir=<bare> worktree remove --force <wt>"` or `rm -rf` the bare dir to force a full re-sync next run.
