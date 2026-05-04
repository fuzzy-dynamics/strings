#!/usr/bin/env bash
# install-codex.sh <name>
#
# Installs Codex CLI on a remote machine. Per machine-provisioning-spec.md
# §4.3:
#   - Requires state="ready" (base machine working).
#   - Failed provider install does NOT demote machine to broken; sets
#     lastProviderError.codex and services.providers.codex.installed=false.
#   - Idempotent: re-running re-verifies via smoke test.
#   - Installer sha256 short-circuit: skips download if cached locally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-use" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

NAME="${1:-}"
if [[ -z "$NAME" ]]; then
  printf '{"ok":false,"stage":"parse-args","message":"usage: install-codex.sh <name>"}\n'
  exit 2
fi
if [[ "$NAME" == "local" ]]; then
  printf '{"ok":false,"stage":"precheck","message":"local machine is implicit; install codex via your usual package manager"}\n'
  exit 1
fi

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME
ensure_index
machine_exists "$NAME" || { printf '{"ok":false,"stage":"precheck","message":"no such machine: %s"}\n' "$NAME"; exit 1; }

status="$(machine_field "$NAME" "status")"
if [[ "$status" != "ready" ]]; then
  printf '{"ok":false,"stage":"precheck","message":"machine status is %s, expected ready (run install.sh first)"}\n' "$status"
  exit 1
fi

if ! ssh_master_alive "$NAME"; then
  printf '{"ok":false,"stage":"precheck","message":"SSH ControlMaster not alive; run reconnect-ssh.sh first"}\n'
  exit 1
fi

# Helper: record a provider failure WITHOUT demoting machine state.
record_provider_failure() {
  local stage="$1" message="$2"
  local ts; ts="$(now_iso)"
  index_update "$NAME" "$(cat <<JQ
    . + {
      lastProviderError: ((.lastProviderError // {}) + {
        codex: { stage: "$stage", message: $(jq -Rsc <<<"$message"), ts: "$ts" }
      }),
      services: ((.services // {}) + {
        providers: ((.services.providers // {}) + {
          codex: ((.services.providers.codex // {}) + { installed: false })
        })
      })
    }
JQ
  )"
  jq -nc --arg name "$NAME" --arg stage "$stage" --arg msg "$message" \
    '{ok:false,name:$name,stage:$stage,message:$msg,provider:"codex"}'
  exit 1
}

# ── stage: download (with sha256 short-circuit) ──────────────────────────────

CACHE_DIR="$OPENSCIENTIST_HOME/cache/installers"
mkdir -p "$CACHE_DIR"

emit_progress info "download" "fetching Codex installer"

# Codex CLI is distributed as an npm package. The installer here is
# really `npm install -g @openai/codex` run on the remote — no
# laptop-side artifact. We record the npm package version as the "installer
# sha" surrogate so reruns can short-circuit on version stability.

# Resolve ssh args once. with_timeout uses GNU timeout, which can only exec
# binaries — wrap `ssh` (a real binary) directly rather than the bash
# function `ssh_run`.
mapfile -t SSH_OPTS < <(ssh_base_opts "$NAME")
SSH_TGT="$(ssh_target "$NAME")"

# ── stage: install ───────────────────────────────────────────────────────────

emit_progress info "install" "running npm install -g @openai/codex on remote"
install_log=""
if ! install_log=$(with_timeout 90 "install" -- \
  ssh "${SSH_OPTS[@]}" "$SSH_TGT" "npm install -g @openai/codex 2>&1"); then
  record_provider_failure "install" "npm install failed: $(printf %s "$install_log" | tail -3)"
fi

# ── stage: smoke ─────────────────────────────────────────────────────────────

emit_progress info "smoke" "codex --version"
version=""
if ! version=$(with_timeout 15 "smoke" -- \
  ssh "${SSH_OPTS[@]}" "$SSH_TGT" "codex --version 2>&1"); then
  record_provider_failure "smoke" "codex --version failed; check PATH on the remote"
fi
version=$(printf '%s' "$version" | head -1 | tr -d '\r\n')
[[ -z "$version" ]] && record_provider_failure "smoke" "codex --version returned empty"

emit_progress info "smoke" "$version"

# ── stage: index-write ───────────────────────────────────────────────────────

ts="$(now_iso)"
# Use printf %s | jq -Rsc rather than `jq -Rsc <<<...` (bash `<<<` appends \n).
version_json="$(printf '%s' "$version" | jq -Rsc .)"
index_update "$NAME" "$(cat <<JQ
  . + {
    services: ((.services // {}) + {
      providers: ((.services.providers // {}) + {
        codex: {
          installed: true,
          version: $version_json,
          installedAt: "$ts",
          smokeTestedAt: "$ts"
        }
      })
    }),
    lastProviderError: ((.lastProviderError // {}) + { codex: null })
  }
JQ
)"

jq -nc \
  --arg name "$NAME" \
  --arg version "$version" \
  '{ok:true,name:$name,stage:"done",provider:"codex",version:$version}'

emit_progress info "done" "codex installed: $version"
