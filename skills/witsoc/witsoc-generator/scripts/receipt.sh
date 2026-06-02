#!/usr/bin/env bash
# receipt.sh <file.wit> [--from verifier.txt]

source "$(dirname "$0")/_common.sh"
need jq

file=""
from=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat >&2 <<'USAGE'
usage: receipt.sh <file.wit> [--from verifier-output.txt]
       cat verifier-output.txt | receipt.sh <file.wit>

Parses verifier verdicts, writes <file>.receipt.json, and updates -- Status:.
Verifier output format:
  [n] ACCEPT: reason
  [n.m] REJECT: reason
  [k] GAP: reason
USAGE
      exit 0
      ;;
    --from)
      [[ $# -ge 2 ]] || usage_error "--from requires a path"
      from="$2"
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
if [[ -n "$from" ]]; then
  [[ -f "$from" ]] || die "verifier output not found: $from"
fi

wit_bin="$(find_wit_cli)"
tmp_out="$(mktemp)"
tmp_err="$(mktemp)"
trap 'rm -f "$tmp_out" "$tmp_err"' EXIT

if [[ -n "$from" ]]; then
  if run_capture "$tmp_out" "$tmp_err" "$wit_bin" receipt "$file" <"$from"; then
    ok=true
    code=0
  else
    ok=false
    code=$?
  fi
else
  if [[ -t 0 ]]; then
    usage_error "receipt.sh needs --from or verifier output on stdin"
  fi
  if run_capture "$tmp_out" "$tmp_err" "$wit_bin" receipt "$file"; then
    ok=true
    code=0
  else
    ok=false
    code=$?
  fi
fi

receipt_path="$(receipt_path_for "$file")"
status="$(status_from_file "$file")"

jq -n \
  --argjson ok "$ok" \
  --arg command "receipt" \
  --arg file "$file" \
  --arg from "$from" \
  --arg receipt "$receipt_path" \
  --arg status "$status" \
  --arg wit_bin "$wit_bin" \
  --arg stdout "$(cat "$tmp_out")" \
  --arg stderr "$(cat "$tmp_err")" \
  --argjson exit_code "$code" \
  '{ok:$ok, command:$command, file:$file, from:(if $from|length > 0 then $from else null end), receipt:$receipt, status:$status, wit_bin:$wit_bin, exit_code:$exit_code, stdout:$stdout, stderr:$stderr}'

exit "$code"
