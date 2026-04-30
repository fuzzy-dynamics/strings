#!/usr/bin/env bash
# add.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key K] [--port P]
#
# Registers a new machine as status:"unprovisioned". Does NOT reach out to the
# machine — use install.sh next.
#
# Preferred path: `--from-ssh-config <alias>` reads `ssh -G <alias>` to resolve
# host / user / port / IdentityFile from the user's existing SSH config.
# Any explicit --host/--user/--key/--port override the resolved values.
# Fall back to explicit flags only when the alias isn't in ssh_config or is
# missing required fields.
source "$(dirname "$0")/_common.sh"
ensure_index

name=""
host=""
user=""
key=""
port=""
from_alias=""

usage() { die "usage: add.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key KEYPATH] [--port P]"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)             host="$2"; shift 2 ;;
    --user)             user="$2"; shift 2 ;;
    --key)              key="$2";  shift 2 ;;
    --port)             port="$2"; shift 2 ;;
    --from-ssh-config)  from_alias="$2"; shift 2 ;;
    -*)                 usage ;;
    *)                  [[ -z "$name" ]] && name="$1" || usage; shift ;;
  esac
done

# Resolve from ssh_config if requested. Explicit flags override resolved values.
if [[ -n "$from_alias" ]]; then
  log "resolving $from_alias from ~/.ssh/config ..."
  resolved=$(ssh -G "$from_alias" 2>/dev/null) || die "ssh -G $from_alias failed"
  while IFS=' ' read -r field value; do
    case "$field" in
      hostname)     [[ -z "$host" ]] && host="$value" ;;
      user)         [[ -z "$user" ]] && user="$value" ;;
      port)         [[ -z "$port" ]] && port="$value" ;;
      identityfile) [[ -z "$key"  ]] && key="${value/#\~/$HOME}" ;;
    esac
  done <<<"$resolved"
  # ssh -G always returns `hostname <alias>` for unknown aliases.
  # If host matches the alias literally and no user was found, bail cleanly.
  if [[ "$host" == "$from_alias" && -z "$user" ]]; then
    die "alias '$from_alias' not in ~/.ssh/config — pass --host/--user/--key explicitly"
  fi
fi

[[ -z "$port" ]] && port=22

[[ -z "$name" || -z "$host" || -z "$user" || -z "$key" ]] && usage
[[ "$name" == "local" ]] && die 'name "local" is reserved for the laptop'
machine_exists "$name" && die "machine already exists: $name"
[[ -f "$key" ]] || die "ssh key not found: $key"
[[ "$port" =~ ^[0-9]+$ ]] || die "port must be an integer: $port"

sock_path="$SSH_DIR/$name.sock"
key_mode=""
[[ -f "$key" ]] && key_mode="$(stat -c '%a' "$key" 2>/dev/null || printf '')"

entry="$(jq -n \
  --arg name "$name" \
  --arg host "$host" \
  --arg user "$user" \
  --arg key  "$key" \
  --argjson port "$port" \
  --arg sock "$sock_path" \
  --arg mode "$key_mode" \
  --arg createdAt "$(now_iso)" \
  '{
     name:          $name,
     host:          $host,
     user:          $user,
     port:          $port,
     ssh: {
       keyPath:       $key,
       keyPresent:    true,
       keyMode:       $mode,
       controlSocket: $sock
     },
     remote:        null,
     services:      {plane:null, kimi:null, providers:{}},
     spaces:        {},
     status:        "unprovisioned",
     bundleVersion: null,
     provisionedAt: null,
     lastError:     null,
     createdAt:     $createdAt
   }')"

write_index "$(jq_index --arg n "$name" --argjson v "$entry" '.machines[$n] = $v')"
log "added machine: $name ($user@$host:$port)"
log "next: run install.sh $name"
