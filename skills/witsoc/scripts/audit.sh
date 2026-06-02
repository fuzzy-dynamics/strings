#!/usr/bin/env bash
# audit.sh <file.wit> -- static quality audit before semantic verification.

source "$(dirname "$0")/_common.sh"
need jq

if [[ "${1:-}" == "--help" || $# -ne 1 ]]; then
  cat >&2 <<'USAGE'
usage: audit.sh <file.wit>

Runs structural check plus proof-style heuristics that catch common weak spots:
GAPs, CITE steps, vague BY justifications, missing preconditions, claim drift
risks, unclosed case splits, vague theorem references, Lean syntax, hidden
assumptions, and receipt issues.
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

grep -nE '^[[:space:]]*\[[0-9.]+\][[:space:]]+GAP|^[[:space:]]*\[[0-9.]+\][[:space:]]+CITE|^[[:space:]]*\[[0-9.]+\].*BY[[:space:]]+(\[[0-9.]+\][[:space:]]*)+\.?[[:space:]]*$|BY .*([Cc]learly|[Oo]bvious|[Tt]rivial|[Ss]tandard([[:space:]]+(argument|theorem|result))?|[Ss]traightforward|[Ww]ell-known|[Cc]lassical result)|^[[:space:]]*\[[0-9.]+\].*(theorem|lemma)[[:space:]]+[A-Za-z0-9_]+[[:space:]]*:=|^[[:space:]]*\[[0-9.]+\].*(:=|^[[:space:]]*by[[:space:]]|[[:space:]](exact|rw|simp)[[:space:]])|[Pp]recondition|[Aa]ssume without proof|[Rr]emains to show|[Ff]inal claim|[Cc]ase .*not closed|[Aa]ssum(e|ing).*(nonzero|non-zero|finite|compact|measurable|positive)|[Rr]equires .*(nonzero|non-zero|finite|compact|measurable|positive)' "$file" >"$tmp_warn" || true

warnings_json="$(
  jq -Rn '
    [inputs
     | capture("(?<line>[0-9]+):(?<text>.*)")
     | .line = (.line | tonumber)
     | .kind = (if .text|test("\\] GAP") then "gap"
                elif .text|test("\\] CITE") then "cite"
                elif .text|test("^\\s*\\[[0-9.]+\\].*BY\\s+(\\[[0-9.]+\\]\\s*)+\\.?\\s*$|BY .*([Cc]learly|[Oo]bvious|[Tt]rivial|[Ss]tandard(\\s+(argument|theorem|result))?|[Ss]traightforward)") then "weak_justification"
                elif .text|test("[Ww]ell-known|[Cc]lassical result|[Ss]tandard\\s+(theorem|result)") then "vague_external_theorem"
                elif .text|test("(theorem|lemma)\\s+[A-Za-z0-9_]+\\s*:=|:=|^\\s*by\\s|\\s(exact|rw|simp)\\s") then "possible_lean_syntax"
                elif .text|test("[Pp]recondition|[Aa]ssume without proof") then "unproven_precondition"
                elif .text|test("[Ff]inal claim") then "final_claim_drift_risk"
                elif .text|test("[Cc]ase .*not closed|[Rr]emains to show") then "unclosed_case_or_obligation"
                elif .text|test("[Aa]ssum(e|ing).*(nonzero|non-zero|finite|compact|measurable|positive)|[Rr]equires .*(nonzero|non-zero|finite|compact|measurable|positive)") then "hidden_assumption_risk"
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
