#!/usr/bin/env bash
# setup.sh <name> [--from-ssh-config ALIAS] [--host H --user U --key K] [--port P]
#
# One-shot "set up a machine" entry point. Runs the three core steps in order,
# without pausing for confirmation between them:
#   1. add.sh           — register the machine (skipped if already present).
#   2. reconnect-ssh.sh — open the SSH ControlMaster; idempotent.
#   3. install.sh       — rsync the bundle, run the remote installer, sync
#                         ~/.openscientist/auth.json.
#
# Use this whenever the user asks to "add / connect / provision / set up" a
# machine. All of those phrasings mean the same thing unless the user
# explicitly says otherwise.
#
# If no connection flags are passed, setup.sh defaults to
# `--from-ssh-config <name>` so that machines defined in ~/.ssh/config work
# with no further input. Any explicit --host/--user/--key/--port override
# values pulled from ssh_config (same semantics as add.sh).
#
# Output:
#   stdout — a single JSON line at end:
#            {"name":"osci-math","status":"ready","bundleVersion":"0.1.0+...","lastError":null}
#   stderr — human-readable progress from each sub-script.
#
# Exit codes:
#   0 — status reached "ready".
#   1 — usage error or add.sh/reconnect-ssh.sh failure.
#   2 — install.sh failure; check index.json.machines[name].lastError.
#
# install.sh is the long step — cold bundles can take several minutes. If your
# tool harness times out before it completes, DO NOT treat the timeout as
# failure. install.sh writes the final outcome to
# index.json.machines[$name].status (ready | error) before it exits; poll that
# field rather than trusting the shell exit code of a wrapped invocation.
source "$(dirname "$0")/_common.sh"
ensure_index

name=""
add_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-ssh-config|--host|--user|--key|--port)
      add_args+=("$1" "$2"); shift 2 ;;
    -*) die "unknown flag: $1 (usage: setup.sh <name> [--from-ssh-config ALIAS | --host H --user U --key K [--port P]])" ;;
    *)  [[ -z "$name" ]] && name="$1" || die "unexpected positional: $1"; shift ;;
  esac
done

[[ -z "$name" ]] && die "usage: setup.sh <name> [--from-ssh-config ALIAS | --host H --user U --key K [--port P]]"
[[ "$name" == "local" ]] && die 'cannot set up reserved machine "local"'

scripts_dir="$(dirname "$0")"

emit_summary() {
  local status="$1" lasterr="$2"
  local bundle
  bundle="$(machine_field "$name" "bundleVersion" 2>/dev/null || printf '')"
  jq -n \
    --arg n "$name" \
    --arg s "$status" \
    --arg b "$bundle" \
    --arg e "$lasterr" \
    '{
       name:          $n,
       status:        $s,
       bundleVersion: (if $b == "" then null else $b end),
       lastError:     (if $e == "" then null else $e end)
     }'
}

# Step 1 — add (or skip if already registered).
if machine_exists "$name"; then
  log "[1/3] $name already registered — skipping add"
else
  if [[ ${#add_args[@]} -eq 0 ]]; then
    log "[1/3] no connection flags given — defaulting to --from-ssh-config $name"
    add_args=(--from-ssh-config "$name")
  else
    log "[1/3] adding machine with explicit flags"
  fi
  if ! bash "$scripts_dir/add.sh" "$name" "${add_args[@]}" >&2; then
    emit_summary "error" "add.sh failed"
    exit 1
  fi
fi

# Step 2 — reconnect-ssh (idempotent).
log "[2/3] opening SSH ControlMaster"
if ! bash "$scripts_dir/reconnect-ssh.sh" "$name" >&2; then
  emit_summary "error" "reconnect-ssh.sh failed"
  exit 1
fi

# Step 3 — install plane + kimi.
log "[3/3] installing plane + kimi bundle (may take several minutes on a cold machine)"
if ! bash "$scripts_dir/install.sh" "$name" >&2; then
  status="$(machine_field "$name" "status")"
  lasterr="$(machine_field "$name" "lastError")"
  emit_summary "${status:-error}" "${lasterr:-install.sh failed}"
  exit 2
fi

status="$(machine_field "$name" "status")"
lasterr="$(machine_field "$name" "lastError")"
emit_summary "$status" "$lasterr"
