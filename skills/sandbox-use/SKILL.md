---
name: sandbox-use
description: Manage Docker sandbox containers for the OpenScientist agent stack — the isolated execution environments agents reach for when they need a tool that isn't on the host (Lean, pinned Python, custom toolchains). Covers the full runtime lifecycle — listing which sandboxes are available in `~/.openscientist/sandboxes/index.json`, checking/changing which one is *active* (the default target for exec calls), starting/stopping containers, live-probing health via `docker inspect`, and running shell commands inside the active sandbox. **HARD CONSTRAINT on where you can use it:** the sandbox bind-mounts ONLY `~/.openscientist` into the container (same-path bind, SPEC §6). `exec.sh` defaults the container's working directory to the caller's `$PWD` and refuses with exit 126 if that `$PWD` is outside `~/.openscientist` — silent fallback would make relative paths resolve against the wrong place. So: only call this skill from an agent whose working directory is a SPOT worktree or otherwise lives under `~/.openscientist/…`. If an agent runs out of `~/Documents` or any other host path, move the work under `~/.openscientist/` first or the skill won't execute. Use this skill whenever the user (or a higher-level skill) asks to run a command that requires a sandbox-resident tool, wants to switch between sandboxes, or needs to check which sandbox is currently wired in. File I/O should go through host-side Read/Write/Edit tools on the same absolute paths — only reach for `exec.sh` when you need to *execute* something. Adding / pulling / removing / uninstalling sandboxes is intentionally not in this skill yet (separate tools land later); `activate.sh` errors cleanly if the sandbox isn't already in the index.
metadata:
  skill-author: OpenScientist
category: execution
---

# Sandbox Use

Manage Docker sandbox containers agents run commands inside.

A **sandbox** is a long-lived Docker container that mounts `~/.openscientist` at the identical absolute path (`/home/<user>/.openscientist` → `/home/<user>/.openscientist`), so file paths match on both sides with no translation. Every agent tool call is a fresh `docker exec` — per-call cwd and env, stateless except for the filesystem. One sandbox per SPOT installation is *active* at a time; that's the default target for exec calls. Switching active stops the previous container and starts the new one.

The catalog — which sandboxes exist, their docker spec, their last-known status, which one is active — lives in `~/.openscientist/sandboxes/index.json`. Every script in this skill reads and/or writes that file.

## Where you can run the skill (read this first)

> **`exec.sh` only works when the caller's `$PWD` is under `~/.openscientist/…`.** If you run it from anywhere else (e.g. `~/Documents/foo`, `/tmp/bar`, a checkout under `~/src/…`), it will refuse with a big visible banner and exit 126. This is a hard constraint, not a bug.

### Why

The sandbox bind-mounts only `~/.openscientist` into the container (same-path bind, SPEC §6). Any host path outside that tree simply does not exist inside the container. `exec.sh` defaults the container's working directory to your `$PWD` so relative paths and shell redirections work the same way they do on the host — but that only holds if `$PWD` actually exists inside the container. Silent fallback to the container's default WORKDIR would make `cat foo.txt` resolve against a completely different directory than you thought; that kind of silent wrongness is worse than failing out.

### Who this is (and isn't) fine for

| Caller's cwd | Can use the skill? |
|---|---|
| `~/.openscientist/sessions/<sid>/worktrees/<wt>/…` (every SPOT deep-run worktree) | ✓ yes, with full pwd ergonomics |
| Any other path under `~/.openscientist/…` | ✓ yes |
| `~/Documents/...`, `~/src/...`, `/tmp/...`, `/etc/...`, etc. | ✗ refused with exit 126 |

### If you're in the ✗ row

- Move the working files under `~/.openscientist/<something>/` and `cd` there, **or**
- Pass an explicit `--workdir /some/path/under/.openscientist/` and use absolute paths in the command.

There is no third option today. A future "per-mount-root container instance" feature would relax this (§SPEC follow-ups); for now, the invariant stands.

## PWD transparency (when you're in the ✓ row)

Inside a SPOT worktree, calling `exec.sh` feels like running the command on the host shell from the same directory. Concretely:

```bash
$ cd ~/.openscientist/sessions/abc/worktrees/w1    # some SPOT worktree
$ bash $SCRIPTS/exec.sh -- pwd
/home/zeero/.openscientist/sessions/abc/worktrees/w1   # matches host PWD
$ bash $SCRIPTS/exec.sh -- cat math.txt                # relative path — works
$ bash $SCRIPTS/exec.sh --command 'ls -la > listing.txt'  # redirects — works via --command
$ cat listing.txt                                      # host sees the sandbox's write
```

No path translation. No workdir juggling. Same-path bind + auto `--workdir $PWD` = native shell ergonomics.

### `--` vs `--command` — when to use which

Both forms are supported, and it matters which one you reach for:

- **`exec.sh -- <argv...>`** — pass a plain argv. Use this for `cat foo`, `ls -la`, `lake build`, anything without shell metacharacters. Quoting flattens (every arg is joined with spaces before being passed to `sh -c`), so `>`, `|`, `&&`, nested quotes do NOT survive.
- **`exec.sh --command '<string>'`** — pass one shell string. Use this for anything with `>`, `|`, `&&`, `$(…)`, nested quoting, multi-line shell. The whole string is handed verbatim to `sh -c` in the sandbox.

Rule of thumb: if the command contains `>`, `|`, `&&`, or needs to preserve quotes, use `--command`.

## Where things live

| Path | Purpose |
|---|---|
| `~/.openscientist/sandboxes/index.json` | sandbox catalog (authoritative) |
| `~/.openscientist/sandboxes/defs/*.yaml` | Docker-Compose-shaped authoring files (consumed by the deferred `add.sh` tool) |
| `~/.openscientist` | the host mount root — bind-mounted into every sandbox at the same absolute path |
| `spot-sandbox-<id>` | container name convention; always computed from the sandbox id |

The host mount path resolves from `$SPOT_HOST_MOUNT` if set, else `$HOME/.openscientist`. Host uid/gid default to `id -u` / `id -g`, overridable with `$SPOT_HOST_UID` / `$SPOT_HOST_GID`. Every `docker run` uses `--user $HOST_UID:$HOST_GID` so files written inside the container land on the host with the right perms.

## index.json schema

Records are flat — everything the scripts need to `docker run` the container sits on the record, no YAML parsing in shell. Variables `$SPOT_HOST_MOUNT`, `$SPOT_HOST_UID`, `$SPOT_HOST_GID` are interpolated at start time inside `binds[].source` / `binds[].target`.

```jsonc
{
  "version": 1,
  "active": "alpine",                       // null when no sandbox is active
  "sandboxes": {
    "alpine": {
      "label":          "Alpine (POC)",
      "image":          "alpine:latest",
      "command":        ["sleep", "infinity"],
      "init":           true,               // --init, tini as PID 1 (SPEC §5.3)
      "env":            {},
      "binds": [
        { "source": "$SPOT_HOST_MOUNT", "target": "$SPOT_HOST_MOUNT", "mode": "rw" }
      ],
      "named_volumes":  [],                 // [{source:"spot-mathlib-cache", target:"/var/cache/mathlib"}, …]
      "limits":         {},                 // {cpus:"4", memory:"8g"}
      "schema_version": 1,
      "status":         "running",          // last-known; reconciled by status.sh
      "image_digest":   null,
      "added_at":       "2026-04-22T...",
      "last_started_at":"2026-04-22T...",
      "last_used_at":   "2026-04-22T...",
      "error_message":  null
    }
  }
}
```

The `active` field is the default sandbox for `exec.sh`. Setting it is how `activate.sh` switches.

## Scripts

All scripts live in `scripts/`. Stdout is structured JSON; stderr is a human log prefixed `[sandbox-use]`. Exit codes: `0` success, `1` user error (bad args, unknown sandbox), `2` environment error (no docker, missing index).

| Script | Purpose |
|---|---|
| `list.sh` | JSON array of every sandbox: `id`, `label`, `status`, `image`, `active`. |
| `show.sh <id>` | Dump one sandbox's full record. |
| `active.sh` | Print the currently active sandbox id (empty if none). |
| `activate.sh <id>` | Stop the previous active (if any), start `<id>` (adopt / restart / create), set `.active = <id>`. Refuses unknown ids. |
| `deactivate.sh` | Stop the active container and clear `.active`. No-op if nothing is active. |
| `status.sh <id>` | Live `docker inspect`, reconcile the index's `status`, emit probed state as JSON. |
| `exec.sh --command "<cmd>" [--workdir PATH] [--timeout N] [--sandbox ID]` / `exec.sh -- <cmd…>` | Run a shell command in the active (or `--sandbox`-overridden) sandbox via `docker exec`. Rejects non-absolute workdirs (exit 126). |

### Common helpers (`_common.sh`)

Every script sources `_common.sh`, which provides:

- `INDEX_PATH`, `DEFS_DIR`, `HOST_MOUNT`, `HOST_UID`, `HOST_GID` — canonical paths and ids (all env-overridable).
- `ensure_index` — create empty `index.json` if missing.
- `write_index <json>` — atomic temp+rename, preserves 0600.
- `jq_index <expr…>` — shorthand for `jq <expr…> "$INDEX_PATH"`.
- `sandbox_exists <id>`, `sandbox_get <id>`, `sandbox_field <id> <path>` — registry reads.
- `active_sandbox` — prints `.active` (empty string if null).
- `container_name <id>` — always `spot-sandbox-<id>`.
- `container_exists <name>`, `container_running <name>` — docker inspect probes.
- `interp <string>` — substitute `$SPOT_HOST_MOUNT` / `$SPOT_HOST_UID` / `$SPOT_HOST_GID`.

Always `source "$(dirname "$0")/_common.sh"` at the top — do not duplicate these.

## Workflows

Scripts resolve their own location via `$(dirname "$0")`, so invoke them directly by path. After world-model sync they land under `${KIMI_WORK_DIR}/.openscientist/skills/sandbox-use/scripts/` — the sync target is the current work_dir (space root for chat, worktree path for deep runs), never home.

**Always prefix invocations with `bash`** — `bash $SCRIPTS/activate.sh …`, not `$SCRIPTS/activate.sh …`. World-model sync does not preserve the executable bit.

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/sandbox-use/scripts
```

### Switch sandbox and run a command

The common flow. `activate.sh` handles start-if-not-running + stop-previous; `exec.sh` uses the active one by default.

```bash
bash $SCRIPTS/list.sh                       # see what's available
bash $SCRIPTS/active.sh                     # which is current?
bash $SCRIPTS/activate.sh alpine            # start alpine, stop anything else
bash $SCRIPTS/exec.sh --command "uname -a"  # run in alpine
bash $SCRIPTS/exec.sh -- echo "hello"       # alternate form
```

### Keep using the already-active sandbox

Skip `activate.sh` entirely — it's only needed when switching. A bare `exec.sh` targets whatever `.active` points at:

```bash
bash $SCRIPTS/exec.sh -- lake build
```

### Run in a specific sandbox without changing active

Useful when an agent wants a one-off execution without touching the default:

```bash
bash $SCRIPTS/exec.sh --sandbox math -- lean --version
```

Note: the target sandbox must already be running (otherwise exit 125). `--sandbox` does not auto-start.

### Free resources

```bash
bash $SCRIPTS/deactivate.sh                 # stops the active container, clears .active
```

### Reconcile when something looks wrong

If `index.json` says `running` but `docker ps` disagrees (user ran `docker rm` manually, laptop rebooted, etc.), `status.sh` re-probes and writes the true state back:

```bash
bash $SCRIPTS/status.sh alpine
```

## Path contract (important for every agent)

- **Caller's `$PWD` must be under `~/.openscientist/…`.** `exec.sh` defaults `--workdir` to your `$PWD`. If that path isn't inside the mount, the skill refuses (exit 126, big visible banner). See "Where you can run the skill" above.
- **Relative paths work** — they resolve against the caller's `$PWD` exactly like native shell execution. `exec.sh -- cat foo.txt` reads `$PWD/foo.txt` both on the host and in the sandbox (they're the same file via same-path bind).
- **Absolute paths work** — as long as they point inside the mount. `/home/zeero/.openscientist/foo.txt` resolves identically on both sides.
- **Never `~`.** The container's `$HOME` is not the host's home (different `/etc/passwd`); `~` inside a sandbox exec does not resolve to `$HOME_MOUNT`. Use absolute paths (or relative-to-PWD).
- **Don't use sandbox tools for file I/O** — host-side `Read` / `Write` / `Edit` tools work on the same files at the same paths. Only reach for `exec.sh` when you need to *run* something (a compiler, an interpreter) the host doesn't have.
- **Shell is `sh -c`, not `bash -lc`.** Don't rely on bashisms in commands you pass to `exec.sh` (pending: richer images with bash will relax this).

## Exit codes (for agents parsing `exec.sh` results)

| Code | Meaning |
|---|---|
| `0` | command succeeded |
| `>0` (any other positive) | real process exit code from the command |
| `124` | exec exceeded `--timeout` seconds |
| `125` | container not running (run `activate.sh`) |
| `126` | bad args — non-absolute workdir, `~` in workdir, **or workdir outside the sandbox mount** (see "Where you can run the skill"). The last case prints a big banner to stderr; do not retry until you fix the cwd. |
| `127` | (reserved) docker CLI not available |

## Writing conventions

- **Exit codes**: 0 success, 1 user error (bad args, unknown sandbox), 2 environment error (missing docker, missing index).
- **Stdout is structured**, **stderr is human log**. Agents should parse stdout as JSON where the script emits it.
- **Atomic writes only** for `index.json` — `_common.sh`'s `write_index` does temp+rename, never append.
- **Never hardcode** sandbox ids or container names — always go through `container_name <id>` and the `_common.sh` helpers.
- **Variable interpolation in specs** — `_common.sh` provides `interp` for `$SPOT_HOST_MOUNT` / `$SPOT_HOST_UID` / `$SPOT_HOST_GID` in `binds[].source` / `binds[].target`. Apply it at start time, not at add time.

## Troubleshooting

| Symptom | First check | Fix |
|---|---|---|
| `exec.sh` exits 125 | `bash $SCRIPTS/status.sh <id>` | Run `activate.sh <id>` — the container isn't running. |
| `exec.sh` exits 126, banner says "OUTSIDE THE SANDBOX MOUNT" | Check the caller's `$PWD` | The caller is running outside `~/.openscientist/`. Move files under the mount and `cd` there, or pass `--workdir` pointing inside the mount. See "Where you can run the skill" in this file. |
| `exec.sh` exits 126, no banner | Check the `--workdir` argument | Workdir must be an absolute host path. Never `~`, never relative. |
| `activate.sh` errors "no such sandbox" | `bash $SCRIPTS/list.sh` | Sandbox isn't in `index.json`. Adding sandboxes is a separate (deferred) tool. |
| `index.json` says running but `docker ps` disagrees | `bash $SCRIPTS/status.sh <id>` | The script re-probes via `docker inspect` and writes the true state. |
| `activate.sh` fails with "docker run failed" | `bash $SCRIPTS/show.sh <id>` to see the spec; check `error_message` | Usually a missing image (no separate pull tool yet — pull manually with `docker pull <image>` as a one-off) or a bad bind source. |
| Container writes land as root on the host | `docker inspect spot-sandbox-<id> --format '{{.Config.User}}'` | The image hardcodes a uid in its default user. `activate.sh` passes `--user $HOST_UID:$HOST_GID` — if this is getting overridden, the image is broken. |
| `$HOME` inside exec isn't the host home | Expected. | The container's `$HOME` comes from its own `/etc/passwd`. Never expand `~` in commands you pass to `exec.sh`. |

## What this skill does not do

- **It does not add sandboxes.** There is no `add.sh` yet. Sandboxes currently in `index.json` were seeded manually; a future `add.sh` will accept a YAML def and compile it into the catalog.
- **It does not pull images.** `activate.sh` errors out if the image isn't present locally. Pull manually with `docker pull <image>` for now.
- **It does not remove sandboxes or uninstall images.** No `remove.sh` / `uninstall.sh` yet.
- **It does not manage per-file I/O.** Use host-side `Read` / `Write` / `Edit` on the same absolute paths — the bind is same-path (SPEC §6).
- **It does not write agent MCP configs.** That's what Electron / plane will own when MCP lands; this skill is the pre-MCP command surface agents use directly.
- **It does not manage concurrency between multiple SPOT processes.** Dev hot-reload with two plane processes can race on the same container; `.lock` support arrives when the SPEC's §7.8 flock lands.
