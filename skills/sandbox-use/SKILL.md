---
name: sandbox-use
description: Manage Docker sandbox containers for the OpenScientist agent stack — the isolated execution environments agents reach for when they need a tool that isn't on the host (Lean, pinned Python, custom toolchains). Multiple sandboxes can be running concurrently. There is no global "active" sandbox — `exec.sh --sandbox <id>` is required, and "active for path P" is a derived predicate (container running AND P falls under one of its current bind-mount targets). The frontend's brick-button dropdown drives activation/deactivation per-space; agents can also self-activate via `activate.sh <id>` (with optional `--mount <abs-path>` to add a same-path bind beyond the canonical `~/.openscientist`). Workdir transparency holds for any host path that's currently bound — `exec.sh` defaults `--workdir` to `$PWD` and refuses with exit 126 if `$PWD` isn't under any of the target container's bind targets. Use this skill whenever you need to run a command that requires a sandbox-resident tool, or to check which sandbox is bound to a given host path. Adding/pulling/removing sandboxes still lives in higher layers (the Electron app's `POST /sandbox/add`); `activate.sh` errors cleanly if the sandbox isn't already in the index.
metadata:
  skill-author: OpenScientist
category: execution
---

# Sandbox Use

Manage Docker sandbox containers agents run commands inside.

A **sandbox** is a long-lived Docker container started from a spec stored in `~/.openscientist/sandboxes/index.json`. Every sandbox bind-mounts `~/.openscientist` at the same absolute path (so file paths match host↔container with zero translation), plus any additional same-path host directories the activator passed via `--mount`. Every agent tool call is a fresh `docker exec` — per-call cwd and env, stateless except for the filesystem.

**Multiple sandboxes can be running concurrently.** The single global `.active` field that the previous version of this skill maintained is gone. "Active for space S" is now a *derived predicate*: a sandbox qualifies iff its container is running AND `S`'s repo root appears in its current bind set. There's no stored "the one true sandbox" — the question is always relative to a host path.

The catalog (`~/.openscientist/sandboxes/index.json`) is now strictly a record of *what's installed* — image, command, canonical binds, env, limits. Runtime state (status, current bindings, who's bound where) is derived live from `docker inspect` on every read, so it can never go stale.

## What `exec.sh` requires

> **`exec.sh --sandbox <id>` is mandatory.** There's no fallback to a "currently active" sandbox — silently picking one would be wrong when several are running with different bind sets. Pass it explicitly.

> **`exec.sh` only works when `$PWD` is under one of the target container's actual bind targets.** Read live via `docker inspect`. If `$PWD` is outside, it refuses with a banner and exit 126. Silent fallback to the container's default WORKDIR would make `cat foo.txt` resolve against a directory you didn't intend.

### Who this is fine for

| Caller's cwd | Can use the skill? |
|---|---|
| `~/.openscientist/...` (always bound; covers every SPOT worktree) | ✓ yes |
| Any path the user `--mount`-ed when activating the sandbox | ✓ yes |
| Anywhere else | ✗ refused, exit 126 |

### If you're in the ✗ row

You have two options:

- `cd` into a path under one of the container's existing binds (see `list.sh` or `status.sh <id>` to find them), **or**
- `activate.sh <id> --mount /your/path`, then retry. This recreates the container with the new bind added.

The banner shown on exit 126 enumerates the live binds and prints the exact `activate.sh` command to fix it.

## PWD transparency

Inside a bound directory, calling `exec.sh` feels like running the command on the host shell from the same directory. Concretely:

```bash
$ cd ~/.openscientist/sessions/abc/worktrees/w1     # under canonical mount
$ bash $SCRIPTS/exec.sh --sandbox math -- pwd
/home/zeero/.openscientist/sessions/abc/worktrees/w1   # matches host PWD

$ bash $SCRIPTS/exec.sh --sandbox math -- cat math.txt          # relative — works
$ bash $SCRIPTS/exec.sh --sandbox math --command 'ls > out.txt' # redirect — works via --command
$ cat out.txt                                                   # host sees the sandbox's write
```

No path translation. No workdir juggling. Same-path bind + auto `--workdir $PWD` = native shell ergonomics.

### `--` vs `--command` — when to use which

- **`exec.sh --sandbox <id> -- <argv...>`** — pass a plain argv. Use this for `cat foo`, `ls -la`, `lake build`, anything without shell metacharacters. Quoting flattens (every arg is joined with spaces before being passed to `sh -c`), so `>`, `|`, `&&`, nested quotes do NOT survive.
- **`exec.sh --sandbox <id> --command '<string>'`** — pass one shell string. Use for anything with `>`, `|`, `&&`, `$(…)`, nested quoting, multi-line shell. Handed verbatim to `sh -c` in the sandbox.

## Where things live

| Path | Purpose |
|---|---|
| `~/.openscientist/sandboxes/index.json` | catalog (installed sandbox specs only — no runtime state) |
| `~/.openscientist/sandboxes/defs/*.yaml` | Compose-shaped authoring files (consumed by the install flow on the Electron side) |
| `~/.openscientist` | the canonical host mount root — bind-mounted into every sandbox at the same absolute path |
| `spot-sandbox-<id>` | container name convention; always computed from the sandbox id |

The host mount path resolves from `$SPOT_HOST_MOUNT` if set, else `$HOME/.openscientist`. Host uid/gid default to `id -u` / `id -g`, overridable with `$SPOT_HOST_UID` / `$SPOT_HOST_GID`. Every `docker run` uses `--user $HOST_UID:$HOST_GID` so files written inside the container land on the host with the right perms.

## index.json schema

Catalog records carry only what's needed to launch a sandbox; runtime fields are no longer persisted. Variables `$SPOT_HOST_MOUNT`, `$SPOT_HOST_UID`, `$SPOT_HOST_GID` are interpolated at start time inside `binds[].source` / `binds[].target`.

```jsonc
{
  "version": 1,
  "active": null,                          // legacy, no longer used by this skill
  "sandboxes": {
    "math": {
      "label":          "Math (Lean 4)",
      "image":          "leanprovercommunity/lean4:latest",
      "image_digest":   "sha256:8d…",      // pinned at install
      "command":        ["sleep", "infinity"],
      "init":           true,              // --init / tini as PID 1
      "env":            {},
      "binds": [                           // canonical only — per-activation extras
        { "source": "$SPOT_HOST_MOUNT",    // are passed at runtime via --mount and
          "target": "$SPOT_HOST_MOUNT",    // never persisted here
          "mode": "rw" }
      ],
      "named_volumes":  [],
      "limits":         {},
      "schema_version": 1,
      "added_at":       "2026-04-22T..."
    }
  }
}
```

The `last_used_at` and `error_message` fields older versions persisted have been removed entirely. `status` and `last_started_at` may still appear in legacy files; they're treated as stale hints and overridden by live `docker inspect` on every read.

## Scripts

All scripts live in `scripts/`. Stdout is structured JSON; stderr is a human log prefixed `[sandbox-use]`. Exit codes: `0` success, `1` user error (bad args, unknown sandbox), `2` environment error (no docker, missing index).

| Script | Purpose |
|---|---|
| `list.sh` | JSON array, every installed sandbox enriched with live `status` and `current_bindings`. |
| `show.sh <id>` | Dump one sandbox's full catalog record (static fields only). |
| `active.sh [<host-path>]` | JSON array of running sandbox ids; with a path, filtered to sandboxes whose live binds include it (the "active for this path" predicate). |
| `activate.sh <id> [--mount /abs/path]…` | Ensure `<id>`'s container is running with the canonical mount + any `--mount` extras. Compares requested binds against the container's live bind set; recreates when they differ, `docker start`s when they match, no-ops when already correctly running. Does **not** touch any other sandbox. |
| `deactivate.sh <id>` | `docker stop` the container. Explicit id required. |
| `status.sh <id>` | Live `docker inspect`, emit JSON. Read-only — never writes the catalog. |
| `exec.sh --sandbox <id> --command "<cmd>"  [--workdir PATH] [--timeout N]` / `exec.sh --sandbox <id> -- <cmd…>` | Run a shell command in the named sandbox via `docker exec`. `--sandbox` is required. Workdir gate is "any of this container's live bind targets". |

### Common helpers (`_common.sh`)

Every script sources `_common.sh`, which provides:

- `INDEX_PATH`, `DEFS_DIR`, `HOST_MOUNT`, `HOST_UID`, `HOST_GID` — canonical paths and ids (env-overridable).
- `ensure_index` — create empty `index.json` if missing.
- `write_index <json>` — atomic temp+rename, preserves 0600.
- `jq_index <expr…>` — shorthand for `jq <expr…> "$INDEX_PATH"`.
- `sandbox_exists <id>`, `sandbox_get <id>`, `sandbox_field <id> <path>` — registry reads.
- `container_name <id>` — always `spot-sandbox-<id>`.
- `container_exists <name>`, `container_running <name>` — docker inspect probes.
- `container_bindings <name>` — sorted/deduped host-side bind sources for a container; empty when the container doesn't exist.
- `interp <string>` — substitute `$SPOT_HOST_MOUNT` / `$SPOT_HOST_UID` / `$SPOT_HOST_GID`.
- `active_sandbox` — DEPRECATED; reads the legacy `.active` field. Callers should use `container_bindings` plus `container_running` instead.

## Workflows

After world-model sync, scripts land under `${KIMI_WORK_DIR}/.openscientist/skills/sandbox-use/scripts/`.

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/sandbox-use/scripts
```

Always prefix invocations with `bash` — sync does not preserve the executable bit.

### Run a command in a sandbox bound to your CWD

The common path. The frontend has typically already activated the sandbox for the user's space; agents just exec into it.

```bash
bash $SCRIPTS/list.sh                                    # see what's installed + live state
bash $SCRIPTS/active.sh "$KIMI_WORK_DIR"                 # which sandboxes are bound to my CWD?
bash $SCRIPTS/exec.sh --sandbox math -- lake build       # run inside math
```

### Self-activate from an agent (Trigger 2)

When the frontend hasn't picked a sandbox and the agent realizes it needs one (e.g. it sees a `.lean` file and wants the math toolchain), it can activate the sandbox itself with its own work_dir as the bind:

```bash
bash $SCRIPTS/activate.sh math --mount "$KIMI_WORK_DIR"
bash $SCRIPTS/exec.sh --sandbox math -- lake build
```

If the user later picks a different sandbox via the UI, that one gets recreated for the new selection independently — Trigger 2's container keeps running for its current work_dir.

### Deep-run agents (Trigger 3)

A deep-run agent's CWD is under `~/.openscientist/worktrees/...`, which is always covered by the canonical mount. So:

```bash
bash $SCRIPTS/activate.sh math       # no --mount needed
bash $SCRIPTS/exec.sh --sandbox math -- lake build
```

`activate.sh` with no `--mount` is permissive: if `math` is already running with a UI-driven binding for some other space, it's reused as-is (the canonical mount is always there, so the deep run gets what it needs without disturbing the user's session). If `math` was stopped, it's started with canonical-only binds.

### Deactivate a sandbox

```bash
bash $SCRIPTS/deactivate.sh math    # docker stop
```

Other running sandboxes are untouched. There's no "the active one" to clear.

### Reconcile when something looks wrong

Live state is derived on every read, so there's no `index.json` ↔ Docker drift to reconcile. If `list.sh` says "stopped" but you remember starting it, the container actually died — check `docker logs spot-sandbox-<id>`.

## Path contract

- **`$PWD` (or explicit `--workdir`) must fall under one of the target sandbox's current bind targets.** `exec.sh`'s gate reads them live via `docker inspect`. Subdirectories of any bind work transparently.
- **Relative paths work** — they resolve against `$PWD` exactly like native shell. `exec.sh --sandbox X -- cat foo.txt` reads `$PWD/foo.txt` both on the host and in the sandbox (same file via same-path bind).
- **Absolute paths work** — as long as they point inside one of the binds.
- **Never `~`.** The container's `$HOME` is not the host's home (different `/etc/passwd`); `~` inside a sandbox exec does not resolve to anything bound. Use absolute paths or relative-to-PWD.
- **Don't use sandbox tools for file I/O** — host-side `Read` / `Write` / `Edit` work on the same files at the same paths. Reach for `exec.sh` only when you need to *run* something the host doesn't have.
- **Shell is `sh -c`, not `bash -lc`.** Don't rely on bashisms in commands you pass to `exec.sh`.

## Exit codes (for agents parsing `exec.sh` results)

| Code | Meaning |
|---|---|
| `0` | command succeeded |
| `>0` (any other positive) | real process exit code from the command |
| `124` | exec exceeded `--timeout` seconds |
| `125` | container not running (run `activate.sh <id>`) |
| `126` | bad args — non-absolute workdir, `~` in workdir, **or workdir outside the target container's bind set** (see "Workdir gate"). The last case prints a banner enumerating the live binds and a fix-up `activate.sh` command. |
| `127` | (reserved) docker CLI not available |

## Writing conventions

- **Exit codes**: 0 success, 1 user error, 2 environment error.
- **Stdout is structured**, **stderr is human log**.
- **Atomic writes only** for `index.json` — `_common.sh`'s `write_index` does temp+rename, never append.
- **Never hardcode** sandbox ids or container names — always go through `container_name <id>` and the helpers.

## Troubleshooting

| Symptom | First check | Fix |
|---|---|---|
| `exec.sh` exits 1 with "--sandbox required" | You forgot the flag | All exec calls now require `--sandbox <id>` explicitly. |
| `exec.sh` exits 125 | `bash $SCRIPTS/status.sh <id>` | The container isn't running — `activate.sh <id>` (add `--mount $PWD` if your CWD is outside the canonical mount). |
| `exec.sh` exits 126 | The banner enumerates the container's live binds | `cd` to a path under one of those binds, or run the suggested `activate.sh <id> --mount …`. |
| `activate.sh` errors "no such sandbox" | `bash $SCRIPTS/list.sh` | Sandbox isn't installed. Use the Electron app's `POST /sandbox/add` flow. |
| `activate.sh` fails with "docker run failed" | `bash $SCRIPTS/show.sh <id>` for the spec; the failure prints stderr verbatim | Usually a missing image (pull manually with `docker pull <image>`) or a bad bind source (e.g. host path doesn't exist). |
| Container writes land as root on the host | `docker inspect spot-sandbox-<id> --format '{{.Config.User}}'` | Image hardcodes a uid in its default user. `activate.sh` passes `--user $HOST_UID:$HOST_GID` — if this is being overridden, the image is broken. |
| `$HOME` inside exec isn't the host home | Expected. | The container's `$HOME` comes from its own `/etc/passwd`. Never expand `~` in commands you pass to `exec.sh`. |

## What this skill does not do

- **It does not install sandboxes.** Installing is the Electron app's job (`POST /sandbox/add` on plane). `activate.sh` errors out if the sandbox isn't already in the catalog.
- **It does not pull images on demand.** That happens at install time; `activate.sh` assumes the image is local.
- **It does not remove sandboxes.** No `uninstall.sh` yet.
- **It does not mediate per-file I/O.** Use host-side `Read` / `Write` / `Edit` on the same absolute paths — same-path bind makes them equivalent.
- **It does not manage concurrency between multiple SPOT processes.** Two processes calling `activate.sh <same-id> --mount <different-path>` can race, causing one to recreate the container out from under the other. The §7.8 flock has not landed; for now, treat per-(sandbox, host-path) activations as serially scheduled by the user.
