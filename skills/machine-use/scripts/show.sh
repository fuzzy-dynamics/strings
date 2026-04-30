#!/usr/bin/env bash
# show.sh <name> — print full record for one machine.
source "$(dirname "$0")/_common.sh"
ensure_index

name="${1:-}"
[[ -z "$name" ]] && die "usage: show.sh <name>"

if [[ "$name" == "local" ]]; then
  jq -n --arg a "$(active_machine)" '{name:"local", status:"ready", active:($a == "local")}'
  exit 0
fi

machine_exists "$name" || die "no such machine: $name"
active="$(active_machine)"
machine_get "$name" | jq --arg n "$name" --arg a "$active" '. + {name: $n, active: ($n == $a)}'
