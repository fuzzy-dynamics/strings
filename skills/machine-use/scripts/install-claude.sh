#!/usr/bin/env bash
# install-claude.sh <name> [--token-stdin | --token-file PATH | --token TOKEN]
#
# Installs Claude Code CLI on a remote machine and (optionally) wires its
# OAuth token so the systemd-managed kimi+plane services can shell out to
# `claude` at runtime. Three token-source modes:
#
#   --token-stdin       read CLAUDE_CODE_OAUTH_TOKEN from stdin
#                       (preferred for chat-pasted tokens — argv stays clean
#                        so the value is not visible in `ps`).
#   --token-file PATH   read the token from a file (the file may contain a
#                       bare token or a `CLAUDE_CODE_OAUTH_TOKEN=...` line).
#   --token TOKEN       pass on argv. Convenient but visible in `ps` while
#                       the script runs — avoid for sensitive tokens.
#   (no flag)           install only; provider record marked authed=false.
#                       Stderr explains how to wire auth in a follow-up run.
#
# Requirements:
#   - Machine status="ready" (run setup.sh first).
#   - SSH ControlMaster alive.
#   - npm available on the remote (the bundle installer ensures this).
#
# Failure semantics: a failed provider install does NOT demote the machine
# to broken. Sets services.providers.claude.installed=false and records
# lastProviderError.claude. Base machine stays selectable.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-use" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

NAME=""
TOKEN_ARG=""
TOKEN_FILE=""
TOKEN_FROM_STDIN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --token)        TOKEN_ARG="$2"; shift 2 ;;
    --token-file)   TOKEN_FILE="$2"; shift 2 ;;
    --token-stdin)  TOKEN_FROM_STDIN=1; shift ;;
    -h|--help)
      sed -n '2,30p' "$0" >&2; exit 0 ;;
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
  printf '{"ok":false,"stage":"parse-args","message":"usage: install-claude.sh <name> [--token-stdin | --token-file PATH | --token TOKEN]"}\n'
  exit 2
fi
if [[ "$NAME" == "local" ]]; then
  printf '{"ok":false,"stage":"precheck","message":"local machine is implicit; install claude via your usual package manager"}\n'
  exit 1
fi

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME
ensure_index
machine_exists "$NAME" || { printf '{"ok":false,"stage":"precheck","message":"no such machine: %s"}\n' "$NAME"; exit 1; }

status="$(machine_field "$NAME" "status")"
if [[ "$status" != "ready" ]]; then
  printf '{"ok":false,"stage":"precheck","message":"machine status is %s, expected ready (run setup.sh first)"}\n' "$status"
  exit 1
fi
if ! ssh_master_alive "$NAME"; then
  printf '{"ok":false,"stage":"precheck","message":"SSH ControlMaster not alive; run reconnect-ssh.sh first"}\n'
  exit 1
fi

# ── token resolution ─────────────────────────────────────────────────────────
TOKEN=""
TOKEN_SRC=""

if [[ "$TOKEN_FROM_STDIN" -eq 1 ]]; then
  TOKEN_SRC="stdin"
  TOKEN="$(cat)"
elif [[ -n "$TOKEN_FILE" ]]; then
  TOKEN_SRC="file:$TOKEN_FILE"
  [[ -f "$TOKEN_FILE" ]] || { printf '{"ok":false,"stage":"parse-args","message":"token file not found: %s"}\n' "$TOKEN_FILE"; exit 1; }
  TOKEN="$(cat "$TOKEN_FILE")"
elif [[ -n "$TOKEN_ARG" ]]; then
  TOKEN_SRC="argv"
  TOKEN="$TOKEN_ARG"
fi

# Strip whitespace and an optional `CLAUDE_CODE_OAUTH_TOKEN=` prefix so users
# can paste either the bare value or the full `KEY=VALUE` line setup-token
# prints.
if [[ -n "$TOKEN" ]]; then
  TOKEN="$(printf '%s' "$TOKEN" | tr -d '\r\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  TOKEN="${TOKEN#CLAUDE_CODE_OAUTH_TOKEN=}"
  TOKEN="${TOKEN#export CLAUDE_CODE_OAUTH_TOKEN=}"
  TOKEN="${TOKEN%\"}"; TOKEN="${TOKEN#\"}"
  TOKEN="${TOKEN%\'}"; TOKEN="${TOKEN#\'}"
  if [[ -z "$TOKEN" ]]; then
    printf '{"ok":false,"stage":"parse-args","message":"token resolved to empty after stripping"}\n'
    exit 1
  fi
fi

# Resolve ssh args once (timeout can only exec binaries, not bash functions).
mapfile -t SSH_OPTS < <(ssh_base_opts "$NAME")
SSH_TGT="$(ssh_target "$NAME")"
SSH_SOCK="$(ssh_sock "$NAME")"
SSH_KEY="$(machine_field "$NAME" "ssh.keyPath")"
SSH_PORT="$(machine_field "$NAME" "ssh.port")"; [[ -z "$SSH_PORT" ]] && SSH_PORT=22

record_provider_failure() {
  local stage="$1" message="$2"
  local ts; ts="$(now_iso)"
  index_update "$NAME" "$(cat <<JQ
    . + {
      lastProviderError: ((.lastProviderError // {}) + {
        claude: { stage: "$stage", message: $(jq -Rsc <<<"$message"), ts: "$ts" }
      }),
      services: ((.services // {}) + {
        providers: ((.services.providers // {}) + {
          claude: ((.services.providers.claude // {}) + { installed: false })
        })
      })
    }
JQ
  )"
  jq -nc --arg name "$NAME" --arg stage "$stage" --arg msg "$message" \
    '{ok:false,name:$name,stage:$stage,message:$msg,provider:"claude"}'
  exit 1
}

# ── stage: install ───────────────────────────────────────────────────────────
# Pin --prefix ~/.local so the binary lands at a known path (~/.local/bin/claude).
# Without --prefix, npm uses whatever the user's npm config has (often /usr or
# nvm's per-version dir) which may not be on the non-interactive SSH PATH or
# the systemd user units' PATH. ~/.local is the de facto user-prefix and the
# systemd PATH drop-in below already includes it.

emit_progress info "install" "running npm install -g --prefix=~/.local @anthropic-ai/claude-code on remote"
install_log=""
if ! install_log=$(with_timeout 180 "install" -- \
  ssh "${SSH_OPTS[@]}" "$SSH_TGT" "mkdir -p \$HOME/.local && npm install -g --prefix=\$HOME/.local @anthropic-ai/claude-code 2>&1"); then
  record_provider_failure "install" "npm install failed: $(printf %s "$install_log" | tail -3 | tr '\n' ' ')"
fi

# ── stage: smoke ─────────────────────────────────────────────────────────────
# Call by absolute path so we don't depend on the remote's interactive PATH.

CLAUDE_BIN='$HOME/.local/bin/claude'
emit_progress info "smoke" "$CLAUDE_BIN --version"
version=""
if ! version=$(with_timeout 15 "smoke" -- \
  ssh "${SSH_OPTS[@]}" "$SSH_TGT" "$CLAUDE_BIN --version 2>&1"); then
  record_provider_failure "smoke" "claude --version failed; check ~/.local/bin/claude exists on the remote"
fi
version=$(printf '%s' "$version" | head -1 | tr -d '\r\n')
if [[ -z "$version" ]] || printf '%s' "$version" | grep -qiE 'command not found|no such file|cannot execute'; then
  record_provider_failure "smoke" "claude --version produced no version string: ${version:-(empty)}"
fi

emit_progress info "smoke" "$version"

# ── stage: token-write (only if a token was provided) ────────────────────────

authed="false"
auth_method="null"

if [[ -n "$TOKEN" ]]; then
  emit_progress info "token-write" "writing token to ~/.openscientist/providers/claudecode.env (source: $TOKEN_SRC)"

  with_timeout 15 "token-write" -- ssh "${SSH_OPTS[@]}" "$SSH_TGT" \
    "mkdir -p \$HOME/.openscientist/providers && chmod 700 \$HOME/.openscientist/providers" \
    || record_provider_failure "token-write" "could not prepare ~/.openscientist/providers on remote"

  tmp_env="$(mktemp)"
  trap 'rm -f "$tmp_env"' EXIT
  printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$TOKEN" > "$tmp_env"
  chmod 600 "$tmp_env"

  if ! with_timeout 15 "token-scp" -- \
    scp -o "ControlPath=$SSH_SOCK" -i "$SSH_KEY" -P "$SSH_PORT" -q \
        "$tmp_env" "$SSH_TGT:.openscientist/providers/claudecode.env"; then
    rm -f "$tmp_env"
    record_provider_failure "token-scp" "scp of token env file failed"
  fi
  rm -f "$tmp_env"

  ssh "${SSH_OPTS[@]}" "$SSH_TGT" \
    "chmod 600 \$HOME/.openscientist/providers/claudecode.env" 2>/dev/null || true

  # systemd PATH drop-in so kimi+plane units can find ~/.local/bin/claude.
  emit_progress info "systemd-path" "ensuring systemd PATH drop-in for kimi/plane"
  ssh "${SSH_OPTS[@]}" "$SSH_TGT" 'bash -s' <<'REMOTE' || true
set -e
UNIT_DIR="$HOME/.config/systemd/user"
for unit in kimi plane; do
  mkdir -p "$UNIT_DIR/$unit.service.d"
  cat > "$UNIT_DIR/$unit.service.d/path.conf" <<'UNIT'
[Service]
Environment=PATH=%h/.local/bin:/usr/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/sbin:/bin
UNIT
done
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user daemon-reload || true
systemctl --user restart kimi.service plane.service 2>/dev/null || true
REMOTE

  # ── stage: auth-probe ─────────────────────────────────────────────────────
  emit_progress info "auth-probe" "verifying claude auth status"
  auth_json=""
  auth_json=$(with_timeout 20 "auth-probe" -- ssh "${SSH_OPTS[@]}" "$SSH_TGT" \
    "set -a; . \$HOME/.openscientist/providers/claudecode.env 2>/dev/null; set +a; $CLAUDE_BIN auth status --json 2>&1" \
    || true)
  if printf '%s' "$auth_json" | jq -e '.loggedIn == true' >/dev/null 2>&1; then
    authed="true"
    auth_method=$(printf '%s' "$auth_json" | jq -r '.authMethod // "unknown"')
    emit_progress info "auth-probe" "authed via $auth_method"
  else
    # Some claude CLI versions don't support `auth status --json`. Fall back
    # to a minimal smoke that exercises the OAuth token: `claude --print` with
    # a one-token prompt. If it returns 200/output, auth is good even without
    # the structured probe.
    emit_progress warn "auth-probe" "auth status --json did not report loggedIn=true; trying claude --print fallback"
    smoke_out=$(with_timeout 30 "auth-print" -- ssh "${SSH_OPTS[@]}" "$SSH_TGT" \
      "set -a; . \$HOME/.openscientist/providers/claudecode.env 2>/dev/null; set +a; printf 'reply with: ok' | $CLAUDE_BIN --print --model claude-haiku-4-5 2>&1 | head -c 200" \
      || true)
    if printf '%s' "$smoke_out" | grep -qiE 'ok|hi|hello|sure'; then
      authed="true"
      auth_method="oauth-token"
      emit_progress info "auth-probe" "fallback print smoke returned content; treating as authed"
    else
      emit_progress warn "auth-probe" "claude --print fallback also failed; token may be invalid or remote CLI is too old: $(printf '%s' "$smoke_out" | head -c 200)"
    fi
  fi
fi

# ── stage: index-write ───────────────────────────────────────────────────────

ts="$(now_iso)"
index_update "$NAME" "$(cat <<JQ
  . + {
    services: ((.services // {}) + {
      providers: ((.services.providers // {}) + {
        claude: {
          installed: true,
          version: $(jq -Rsc <<<"$version"),
          authed: $authed,
          authMethod: $(if [[ "$auth_method" == "null" ]]; then printf 'null'; else jq -Rsc <<<"$auth_method"; fi),
          installedAt: "$ts",
          smokeTestedAt: "$ts"
        }
      })
    }),
    lastProviderError: ((.lastProviderError // {}) + { claude: null })
  }
JQ
)"

jq -nc \
  --arg name "$NAME" \
  --arg version "$version" \
  --argjson authed "$authed" \
  --arg method "$auth_method" \
  '{ok:true,name:$name,stage:"done",provider:"claude",version:$version,authed:$authed,authMethod:(if $method=="null" then null else $method end)}'

if [[ "$authed" != "true" ]]; then
  if [[ -z "$TOKEN" ]]; then
    cat >&2 <<HINT

[install-claude] Installed but no token provided — claude will fail at runtime
on the remote until auth is wired. Run on this laptop:

    claude setup-token

then paste the printed CLAUDE_CODE_OAUTH_TOKEN value back here, or:

    bash ${SCRIPT_DIR}/install-claude.sh $NAME --token-stdin <<< "<token>"
    bash ${SCRIPT_DIR}/install-claude.sh $NAME --token-file ~/path/to/token

HINT
  else
    cat >&2 <<HINT

[install-claude] Token written but auth probe did not confirm logged-in
status. If you have a recent claude CLI, the systemd units will still pick
up the env file at runtime — try `ssh $NAME 'claude --version' && ssh $NAME 'claude auth status --json'` to debug. If the CLI version on the remote is too old, npm-update it and rerun.

HINT
  fi
fi

emit_progress info "done" "claude installed: $version (authed=$authed)"
