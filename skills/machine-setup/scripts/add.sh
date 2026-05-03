#!/usr/bin/env bash
# add.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key K] [--port P]
#                [--force]
#
# Registers a new machine as status:"unprovisioned". Does NOT reach out to the
# machine — use install.sh next.
#
# Preferred path: --from-ssh-config <alias> reads `ssh -G <alias>`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TAG="machine-setup" source "$SCRIPT_DIR/../../_lib/provisioning.sh"

NAME=""
HOST=""
USER_ARG=""
KEY=""
PORT=""
FROM_ALIAS=""
FORCE=0

usage_msg='usage: add.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key KEYPATH] [--port P] [--force]'

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)              HOST="$2"; shift 2 ;;
    --user)              USER_ARG="$2"; shift 2 ;;
    --key)               KEY="$2";  shift 2 ;;
    --port)              PORT="$2"; shift 2 ;;
    --from-ssh-config)   FROM_ALIAS="$2"; shift 2 ;;
    --force)             FORCE=1; shift ;;
    -h|--help)
      echo "$usage_msg" >&2
      exit 0 ;;
    --*)
      printf '{"ok":false,"stage":"parse-args","message":"unknown flag: %s","usage":"%s"}\n' "$1" "$usage_msg"
      exit 2 ;;
    *)
      if [[ -z "$NAME" ]]; then NAME="$1"; else
        printf '{"ok":false,"stage":"parse-args","message":"unexpected positional: %s","usage":"%s"}\n' "$1" "$usage_msg"
        exit 2
      fi
      shift ;;
  esac
done

[[ -z "$NAME" ]] && { printf '{"ok":false,"stage":"parse-args","message":"missing <name>","usage":"%s"}\n' "$usage_msg"; exit 2; }
[[ "$NAME" == "local" ]] && { printf '{"ok":false,"stage":"parse-args","message":"name \"local\" is reserved for the laptop"}\n'; exit 2; }

PROVISIONING_NAME="$NAME"
export PROVISIONING_NAME
ensure_index

# Resolve from ssh_config if requested. Explicit flags override resolved.
if [[ -n "$FROM_ALIAS" ]]; then
  emit_progress info "ssh-config" "resolving $FROM_ALIAS from ~/.ssh/config"
  resolved=$(ssh -G "$FROM_ALIAS" 2>/dev/null) \
    || { printf '{"ok":false,"stage":"ssh-config","message":"ssh -G %s failed"}\n' "$FROM_ALIAS"; exit 1; }
  while IFS=' ' read -r field value; do
    case "$field" in
      hostname)     [[ -z "$HOST"     ]] && HOST="$value" ;;
      user)         [[ -z "$USER_ARG" ]] && USER_ARG="$value" ;;
      port)         [[ -z "$PORT"     ]] && PORT="$value" ;;
      identityfile) [[ -z "$KEY"      ]] && KEY="${value/#\~/$HOME}" ;;
    esac
  done <<<"$resolved"
  if [[ "$HOST" == "$FROM_ALIAS" && -z "$USER_ARG" ]]; then
    printf '{"ok":false,"stage":"ssh-config","message":"alias %s not in ~/.ssh/config; pass --host/--user/--key explicitly"}\n' "$FROM_ALIAS"
    exit 1
  fi
fi

[[ -z "$PORT" ]] && PORT=22

# Validate.
if [[ -z "$HOST" || -z "$USER_ARG" || -z "$KEY" ]]; then
  printf '{"ok":false,"stage":"parse-args","message":"missing required ssh fields (host, user, key)","usage":"%s"}\n' "$usage_msg"
  exit 2
fi
[[ "$PORT" =~ ^[0-9]+$ ]] || { printf '{"ok":false,"stage":"parse-args","message":"port must be an integer: %s"}\n' "$PORT"; exit 2; }
[[ -f "$KEY" ]]           || { printf '{"ok":false,"stage":"parse-args","message":"ssh key not found: %s"}\n' "$KEY"; exit 1; }

if machine_exists "$NAME"; then
  if (( FORCE )); then
    emit_progress warn "force" "--force given; overwriting existing entry"
  else
    existing="$(machine_get "$NAME")"
    printf '{"ok":false,"stage":"add","message":"machine already exists: %s — pass --force to overwrite","existing":%s}\n' "$NAME" "$existing"
    exit 1
  fi
fi

index_lock "$NAME"
trap_unhandled_errors

sock_path="$SSH_DIR/$NAME.sock"
key_mode=""
[[ -f "$KEY" ]] && key_mode="$(stat -c '%a' "$KEY" 2>/dev/null || printf '')"

entry=$(jq -n \
  --arg name "$NAME" \
  --arg host "$HOST" \
  --arg user "$USER_ARG" \
  --arg key  "$KEY" \
  --argjson port "$PORT" \
  --arg sock "$sock_path" \
  --arg mode "$key_mode" \
  --arg createdAt "$(now_iso)" \
  '{
     name: $name,
     ssh: {
       host: $host,
       user: $user,
       port: $port,
       keyPath: $key,
       keyMode: $mode,
       controlPath: $sock
     },
     remote: null,
     services: { providers: {} },
     status: "unprovisioned",
     bundleVersion: null,
     provisionedAt: null,
     lastVerifiedAt: null,
     lastError: null,
     lastProviderError: { claude: null, codex: null },
     createdAt: $createdAt
   }')

write_index "$(jq_index --arg n "$NAME" --argjson v "$entry" '.machines[$n] = $v')"
emit_progress info "done" "added machine: $NAME ($USER_ARG@$HOST:$PORT)"

jq -nc \
  --arg name "$NAME" \
  --arg host "$HOST" \
  --arg user "$USER_ARG" \
  --argjson port "$PORT" \
  '{ok:true,name:$name,stage:"done",ssh:{host:$host,user:$user,port:$port}}'
