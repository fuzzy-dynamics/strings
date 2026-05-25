#!/usr/bin/env bash
# cycle.sh <file.wit> [--out-dir dir]
#
# Runs the full Witsoc verification-prep cycle:
#   check -> audit -> verify context -> status
# This does not call an LLM verifier. Feed the generated verifier context to a
# skeptical verifier, then use receipt.sh to persist verdicts.

source "$(dirname "$0")/_common.sh"
need jq

file=""
out_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat >&2 <<'USAGE'
usage: cycle.sh <file.wit> [--out-dir dir]

Runs the full WIT verification-prep cycle: structural check, static audit,
verifier-context generation, and status.
Writes <basename>.verify.txt under --out-dir or next to the .wit file.
USAGE
      exit 0
      ;;
    --out-dir)
      [[ $# -ge 2 ]] || usage_error "--out-dir requires a directory"
      out_dir="$2"
      shift 2
      ;;
    -*)
      usage_error "unknown flag: $1"
      ;;
    *)
      [[ -z "$file" ]] || usage_error "only one .wit file is accepted"
      file="$1"
      shift
      ;;
  esac
done

require_wit_file "$file"
script_dir="$(cd "$(dirname "$0")" && pwd)"
base="$(basename "$file" .wit)"
if [[ -z "$out_dir" ]]; then
  out_dir="$(dirname "$file")"
fi
mkdir -p "$out_dir"
verify_out="$out_dir/$base.verify.txt"

tmp_check="$(mktemp)"
tmp_audit="$(mktemp)"
tmp_verify="$(mktemp)"
tmp_status="$(mktemp)"
trap 'rm -f "$tmp_check" "$tmp_audit" "$tmp_verify" "$tmp_status"' EXIT

set +e
"$script_dir/check.sh" "$file" >"$tmp_check"
check_code=$?
"$script_dir/audit.sh" "$file" >"$tmp_audit"
audit_code=$?
"$script_dir/verify.sh" "$file" --out "$verify_out" >"$tmp_verify"
verify_code=$?
"$script_dir/status.sh" "$file" >"$tmp_status"
status_code=$?
set -e

ok=false
if [[ "$check_code" -eq 0 && "$verify_code" -eq 0 && "$status_code" -eq 0 ]]; then
  ok=true
fi

jq -n \
  --argjson ok "$ok" \
  --arg command "cycle" \
  --arg file "$file" \
  --arg verify_out "$verify_out" \
  --argjson check "$(cat "$tmp_check")" \
  --argjson audit "$(cat "$tmp_audit")" \
  --argjson verify "$(cat "$tmp_verify")" \
  --argjson status "$(cat "$tmp_status")" \
  '{ok:$ok, command:$command, file:$file, verify_out:$verify_out, check:$check, audit:$audit, verify:$verify, status:$status}'

if [[ "$check_code" -ne 0 ]]; then exit "$check_code"; fi
if [[ "$verify_code" -ne 0 ]]; then exit "$verify_code"; fi
exit "$status_code"
