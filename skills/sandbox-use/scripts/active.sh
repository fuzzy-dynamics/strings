#!/usr/bin/env bash
# active.sh — print the currently active sandbox id, or nothing if none.
source "$(dirname "$0")/_common.sh"
ensure_index

printf '%s\n' "$(active_sandbox)"
