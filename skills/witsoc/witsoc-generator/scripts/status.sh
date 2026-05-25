#!/usr/bin/env bash
# status.sh <file.wit> -- summarize structural and receipt status.

source "$(dirname "$0")/_common.sh"
need jq

if [[ "${1:-}" == "--help" || $# -ne 1 ]]; then
  cat >&2 <<'USAGE'
usage: status.sh <file.wit>

Emits one JSON document with status header, receipt summary, structural check
result, and best-effort receipt completeness checks.
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
  receipt_json="$(jq '{final_verdict, iteration, timestamp, rejected_steps, partial_score, gaps, step_verdicts}' "$receipt_path")"
else
  receipt_json="null"
fi

obligations_json="$(
  { grep -nE '^[[:space:]]*\[[0-9.]+\][[:space:]]+(HAVE|SHOW|SUFFICES|CASE|CITE|GAP|CONSIDER)' "$file" || true; } \
    | jq -Rn '[inputs | capture("(?<line>[0-9]+):[[:space:]]*(?<label>\\[[0-9.]+\\])[[:space:]]+(?<keyword>[A-Z]+)") | .line=(.line|tonumber)]'
)"
final_show_json="$(
  { grep -nE '^[[:space:]]*\[[0-9.]+\][[:space:]]+SHOW[[:space:]]' "$file" || true; } \
    | tail -1 \
    | jq -Rn '[inputs | capture("(?<line>[0-9]+):[[:space:]]*(?<label>\\[[0-9.]+\\])") | .line=(.line|tonumber)] | .[0] // null'
)"
gap_labels_json="$(
  { grep -nE '^[[:space:]]*\[[0-9.]+\][[:space:]]+GAP' "$file" || true; } \
    | jq -Rn '[inputs | capture("(?<line>[0-9]+):[[:space:]]*(?<label>\\[[0-9.]+\\])") | .line=(.line|tonumber)]'
)"

jq -n \
  --arg file "$file" \
  --arg status "$status" \
  --arg receipt_path "$receipt_path" \
  --argjson has_receipt "$([[ -f "$receipt_path" ]] && echo true || echo false)" \
  --argjson check "$(cat "$tmp")" \
  --argjson receipt "$receipt_json" \
  --argjson obligations "$obligations_json" \
  --argjson final_show "$final_show_json" \
  --argjson gap_labels "$gap_labels_json" \
  'def verdict_labels: (($receipt.step_verdicts // []) | map(.label));
   def missing_obligations: ($obligations | map(select(.label as $l | (verdict_labels | index($l) | not))));
   def final_show_covered: ($final_show == null or (verdict_labels | index($final_show.label)) != null);
   def rejected_labels: ($receipt.rejected_steps // []);
   def receipt_matches_header: ($receipt == null or $receipt.final_verdict == $status);
   def completeness:
     if $receipt == null then
       {ok:false, reason:"no_receipt", obligations:$obligations, missing_obligations:$obligations, final_show:$final_show, final_show_covered:false, gap_labels:$gap_labels, rejected_labels:[]}
     else
       {ok:((missing_obligations|length == 0) and final_show_covered and ($gap_labels|length == 0) and (rejected_labels|length == 0) and receipt_matches_header),
        obligations:$obligations,
        missing_obligations:missing_obligations,
        final_show:$final_show,
        final_show_covered:final_show_covered,
        gap_labels:$gap_labels,
        rejected_labels:rejected_labels,
        receipt_matches_header:receipt_matches_header,
        suspiciously_incomplete:((missing_obligations|length > 0) or (final_show_covered|not))}
     end;
   {ok:($check.ok and (($receipt == null) or receipt_matches_header) and ($status != "VERIFIED" or completeness.ok)),
    file:$file,
    status:$status,
    receipt_path:$receipt_path,
    has_receipt:$has_receipt,
    structural:$check,
    receipt:$receipt,
    receipt_completeness:completeness}'

exit "$check_code"
