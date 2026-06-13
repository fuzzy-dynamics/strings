#!/usr/bin/env bash
# check.sh <file.wit|dir> [more files/dirs] -- structural validation.

source "$(dirname "$0")/_common.sh"
need jq

if [[ "${1:-}" == "--help" || $# -lt 1 ]]; then
  cat >&2 <<'USAGE'
usage: check.sh <file.wit|directory> [more files/dirs]

Runs Wit structural validation and emits one JSON document on stdout.
USAGE
  exit 0
fi

wit_bin="$(find_wit_cli)"
tmp_out="$(mktemp)"
tmp_err="$(mktemp)"
trap 'rm -f "$tmp_out" "$tmp_err"' EXIT

if run_capture "$tmp_out" "$tmp_err" "$wit_bin" check "$@"; then
  ok=true
  code=0
else
  ok=false
  code=$?
fi

jq -n \
  --argjson ok "$ok" \
  --arg command "check" \
  --arg wit_bin "$wit_bin" \
  --arg stdout "$(cat "$tmp_out")" \
  --arg stderr "$(cat "$tmp_err")" \
  --argjson exit_code "$code" \
  '{ok:$ok, command:$command, wit_bin:$wit_bin, exit_code:$exit_code, stdout:$stdout, stderr:$stderr}'

exit "$code"
