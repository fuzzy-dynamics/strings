#!/usr/bin/env bash
# show.sh <id> — dump one sandbox's full record.
source "$(dirname "$0")/_common.sh"
ensure_index

id="${1:-}"
[[ -z "$id" ]] && die "usage: show.sh <id>"
sandbox_exists "$id" || die "no such sandbox: $id"

sandbox_get "$id"
