---
name: machine-use
description: Spawn deep-run orchestrators on the host you're running on, claim a run's result back into the laptop's git, and (laptop-only) install provider CLIs on registered remotes. This skill is the **agent's** machine-touching surface; cross-machine routing — selecting which machine, opening tunnels, probing reachability, syncing space repos — is the renderer's job and is not exposed here. Use this skill when the user wants to trigger a deep run, claim a finished run's branch, or install Claude / Codex on a remote.
metadata:
  skill-author: OpenScientist
category: infrastructure
---

# Machine Use

The agent-callable surface for spawning + claiming deep runs.

## Partitioning rule

This is the most important constraint in this skill. **Each gecko operates in its own machine's frame.** Concretely:

- You do **not** select which machine the user is targeting. There is no `.active` field in `index.json`. The renderer holds the selection in memory; you don't read or set it.
- `trigger-deep-run.sh` is **local-only**. It spawns a run on the host that invoked it. There is no `--machine` flag. If the user wants a run on a different machine, they pick it in the renderer; Electron orchestrates the SSH-exec on the target and runs the same script there in *its* local frame.
- You do **not** enumerate machines or probe their reachability. Boot probe, periodic probe, dropdown gate — all renderer-only. Don't invoke `verify.sh`, `sync-space.sh`, or `reconnect-ssh.sh` (against arbitrary remotes) on your own initiative.
- Cross-machine work the agent *can* do (laptop only, explicit user request): `install-claude.sh`, `install-codex.sh`, `fetch-session-branch.sh`. These are scoped, named-machine operations the user explicitly asks for.

If the user reports a machine isn't reachable: tell them to use the in-app machine controls. Do not attempt cross-machine repair from this session.

## Where things live

| Path | Purpose |
|---|---|
| `~/.openscientist/machines/index.json` | persistent machine registry (ssh, remote paths, `services.providers`, `bundleVersion`, `provisionedAt`). No live state. |
| `~/.openscientist/worktrees/<sid>/` | per-session worktree on the host that ran `trigger-deep-run.sh`. Detached (no branch ref) — the `osci/<sid>` branch is created lazily by `fetch-session-branch.sh` only when the user claims a run's result. |
| `${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts/` | world-model-synced skill scripts. Always invoke via `bash <path>`; the executable bit is not preserved across sync. |

For setup-side paths (cloud-run bundle, remote install dir, systemd units, `~/.openscientist/auth.json`), see `machine-setup/SKILL.md`.

## Agent-callable scripts

| Script | When | Notes |
|---|---|---|
| `trigger-deep-run.sh --provider P --prompt X --path DIR [--agent A] [--title T] [--space-id S]` | The user wants to spawn an autonomous deep run on this host | **Local frame only.** No `--machine` flag. POSTs to `$PLANE_SERVER_URL` (default `http://127.0.0.1:5495`). Returns `{orchestratorId, sessionId, worktreePath, provider, branch, dirty}` on stdout. |
| `fetch-session-branch.sh --session-id SID --path LAPTOP_REPO --machine M` | The user wants to claim a finished deep run's result back into the laptop's git | Laptop-only. `--machine M` names which remote (or `local`) the run lived on. Creates `osci/<sid>` in the laptop `.git`. |
| `install-claude.sh <name> [--token-stdin \| --token-file PATH]` | The user asks to install Claude Code on a registered remote | Laptop-only. Auth-required; see "Provider installs" below. |
| `install-codex.sh <name>` | The user asks to install Codex on a registered remote | Laptop-only. Auth via separate rsync of `~/.codex/` (see below). |

## Electron-internal scripts (do not invoke from agent)

These scripts exist for the renderer's machine bridge and supervisor flows. Calling them from agent context violates partitioning — they're listed only so you recognize them in commit history and in `cloud-run/` Node code.

- `verify.sh` — plane-reachability probe. Run by Electron's boot probe + 20 s periodic timer.
- `sync-space.sh` — laptop → remote space repo mirror. Called from `desktop:ensure-space-on-machine` IPC.
- `reconnect-ssh.sh` — reopen the SSH ControlMaster. Called from Electron's machine bridge and from `machine-setup` scripts.

## Trigger a deep run

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/machine-use/scripts
bash $SCRIPTS/trigger-deep-run.sh \
  --provider gecko \
  --prompt   "summarize the repo and find areas needing tests" \
  --path     "$PWD" \
  --agent    osci-orchestrator \
  --spawned-by-session "$OSCI_SESSION_ID" \
  --spawned-by-role    osci-general
```

Output (single-line JSON):
```json
{ "orchestratorId": "orch_a021bb97-...",
  "sessionId":      "<root session id from plane>",
  "worktreePath":   "/home/.../openscientist/worktrees/<8-hex>",
  "provider":       "kimi",
  "branch":         "master",
  "dirty":          true }
```

Stderr is a human progress log. Tell the user the short orchestrator id; everything else (worktree path, plane state) is plane's bookkeeping.

### What it does internally

1. Resolve the git root from `--path`.
2. Generate a random 8-hex session id.
3. `git stash create` to capture index + working tree (no branch / stash-list pollution); fall through to HEAD if clean.
4. `git worktree add --detach $HOME/.openscientist/worktrees/<sid> <snapshot>`. Detached deliberately — naming a branch per session at spawn time would flood your branch list. The `osci/<sid>` branch is created lazily on pull-back by `fetch-session-branch.sh`.
5. POST `/orchestrator/start` to `$PLANE_SERVER_URL` (defaults to `http://127.0.0.1:5495` — every host's local plane).
6. Emit consolidated JSON.

### Provider selection

`--provider` picks which CLI runs the orchestrator (not which model). Three valid values:

- `gecko` — built-in kimi-server orchestrator. Always available after `machine-setup/install.sh`. The default for any run that doesn't ask for something else.
- `claudecode` — Anthropic's Claude Code CLI.
- `codex` — OpenAI's Codex CLI.

Legacy aliases `kimi` and `openscientist-gecko` canonicalize to `gecko`'s wire form (`kimi`).

If the user names `claudecode` or `codex` and it isn't installed on this host (`jq '.machines["<name>"]?.services.providers' ~/.openscientist/machines/index.json` — but only consult this on the laptop), tell them and offer to fall back to `gecko`. Don't put "claude code" or "codex" into the prompt as if it were a model name.

## Claim a deep run's result

```bash
SID="<session-id>"
MACHINE="<name | local>"     # ask the user which one — you do not query this
LAPTOP_REPO="$PWD"
bash $SCRIPTS/fetch-session-branch.sh --session-id "$SID" --path "$LAPTOP_REPO" --machine "$MACHINE"
git -C "$LAPTOP_REPO" checkout "osci/$SID"
```

`fetch-session-branch.sh` is the *only* point at which `osci/<sid>` enters the laptop's `.git`. Runs the user never claims leave no branch behind. If the user has uncommitted local changes, do `git stash push -u -m "osci-pre-pull-$SID"` first and tell them.

## Provider installs (laptop-only)

These live in `machine-use/` because they're per-machine (configure a registered remote) but they're agent-driveable from the laptop with explicit user consent. Both require the SSH ControlMaster to the target machine to be alive (`reconnect-ssh.sh` first if not).

### Claude Code (`install-claude.sh`)

Claude Code on a remote needs a `CLAUDE_CODE_OAUTH_TOKEN`. The laptop's interactive OAuth credentials don't transfer; the user runs `claude setup-token` on the laptop and gives the agent the token in one of two ways:

```bash
# 1. paste in chat
echo "<paste-the-token>" | bash $SCRIPTS/install-claude.sh osci-math --token-stdin

# 2. stored in a file
bash $SCRIPTS/install-claude.sh osci-math --token-file ~/.config/claude/token
```

Do **not** use `--token <value>` for chat-pasted secrets — argv is visible in `ps`.

The script: `npm install -g @anthropic-ai/claude-code` → smoke-test `claude --version` → scp the token to `~/.openscientist/providers/claudecode.env` (mode 600) → drop a systemd path drop-in so user units find `~/.local/bin/claude` → restart `kimi.service` + `plane.service` → `claude auth status --json`. On success, writes `services.providers.claude` into `index.json`. On failure, sets `services.providers.claude.installed=false` — the base machine stays usable for `gecko` runs.

Without any token flag the script installs but marks `authed: false`. The base machine still works; only `claudecode`-routed runs on that remote will fail.

### Codex (`install-codex.sh`)

Codex stores auth in a portable file at `~/.codex/auth.json`. Install + smoke-test via the script, then rsync the laptop's `~/.codex/` to the remote:

```bash
bash $SCRIPTS/install-codex.sh osci-math
ssh osci-math 'mkdir -p ~/.codex'
rsync -az ~/.codex/ osci-math:.codex/
ssh osci-math 'codex login status'   # confirm
```

## Conventions for new scripts

- **Args:** single positional, long-form flags, `--help` exits 0.
- **Stdout** is one structured JSON document; stderr is human log.
- **Exit 0** iff `ok=true`.
- **Atomic writes** to `index.json` via `_lib/provisioning.sh`'s `index_update`.
- **Timeouts on every blocking op:** `ssh -o ConnectTimeout=5 -o BatchMode=yes`, `curl -m N`. Never hang the agent.
