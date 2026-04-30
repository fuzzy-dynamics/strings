#!/usr/bin/env bash
# active.sh — print the currently active machine name.
source "$(dirname "$0")/_common.sh"
ensure_index
active_machine
