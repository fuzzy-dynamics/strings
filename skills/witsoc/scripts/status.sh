#!/usr/bin/env bash
# status.sh <file.wit> -- summarize structural and receipt status.

source "$(dirname "$0")/_common.sh"
need jq

if [[ "${1:-}" == "--help" || $# -ne 1 ]]; then
  cat >&2 <<'USAGE'
usage: status.sh <file.wit>

Emits one JSON document with status header, receipt summary, and structural
check result.
USAGE
  exit 0
fi

file="$1"
require_wit_file "$file"
script_dir="$(cd "$(dirname "$0")" && pwd)"
receipt_path="$(receipt_path_for "$file")"
status="$(status_from_file "$file")"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
set +e
"$script_dir/check.sh" "$file" >"$tmp"
check_code=$?
set -e

if [[ -f "$receipt_path" ]]; then
  receipt_json="$(jq '{final_verdict, iteration, timestamp, rejected_steps, partial_score, gaps}' "$receipt_path")"
else
  receipt_json="null"
fi

jq -n \
  --arg file "$file" \
  --arg status "$status" \
  --arg receipt_path "$receipt_path" \
  --argjson has_receipt "$([[ -f "$receipt_path" ]] && echo true || echo false)" \
  --argjson check "$(cat "$tmp")" \
  --argjson receipt "$receipt_json" \
  '{ok:($check.ok and (($receipt == null) or ($receipt.final_verdict == $status))), file:$file, status:$status, receipt_path:$receipt_path, has_receipt:$has_receipt, structural:$check, receipt:$receipt}'

exit "$check_code"
