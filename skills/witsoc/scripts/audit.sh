#!/usr/bin/env bash
# audit.sh <file.wit> -- static quality audit before semantic verification.

source "$(dirname "$0")/_common.sh"
need jq

if [[ "${1:-}" == "--help" || $# -ne 1 ]]; then
  cat >&2 <<'USAGE'
usage: audit.sh <file.wit>

Runs structural check plus proof-style heuristics that catch common weak spots:
GAPs, CITE steps, vague BY justifications, and missing receipts.
USAGE
  exit 0
fi

file="$1"
require_wit_file "$file"
script_dir="$(cd "$(dirname "$0")" && pwd)"
receipt_path="$(receipt_path_for "$file")"

tmp_check="$(mktemp)"
tmp_warn="$(mktemp)"
trap 'rm -f "$tmp_check" "$tmp_warn"' EXIT

set +e
"$script_dir/check.sh" "$file" >"$tmp_check"
check_code=$?
set -e

grep -nE '^[[:space:]]*\[[0-9.]+\][[:space:]]+GAP|^[[:space:]]*\[[0-9.]+\][[:space:]]+CITE|BY .*([Cc]learly|[Oo]bvious|[Tt]rivial|[Ss]tandard argument|[Ss]traightforward)' "$file" >"$tmp_warn" || true

warnings_json="$(
  jq -Rn '
    [inputs
     | capture("(?<line>[0-9]+):(?<text>.*)")
     | .line = (.line | tonumber)
     | .kind = (if .text|test("\\] GAP") then "gap"
                elif .text|test("\\] CITE") then "cite"
                elif .text|test("BY .*([Cc]learly|[Oo]bvious|[Tt]rivial|[Ss]tandard argument|[Ss]traightforward)") then "weak_justification"
                else "note" end)]
  ' <"$tmp_warn"
)"

status="$(status_from_file "$file")"
has_receipt=false
[[ -f "$receipt_path" ]] && has_receipt=true

jq -n \
  --arg file "$file" \
  --arg status "$status" \
  --arg receipt_path "$receipt_path" \
  --argjson has_receipt "$has_receipt" \
  --argjson structural "$(cat "$tmp_check")" \
  --argjson warnings "$warnings_json" \
  '{ok:($structural.ok and ($warnings|length == 0) and (($status != "VERIFIED") or $has_receipt)), file:$file, status:$status, receipt_path:$receipt_path, has_receipt:$has_receipt, structural:$structural, warnings:$warnings}'

exit "$check_code"
