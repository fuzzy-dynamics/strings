#!/usr/bin/env bash
# context.sh <file.wit> [--step N|N.M] [--out path]

source "$(dirname "$0")/_common.sh"
need jq

file=""
step=""
out=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat >&2 <<'USAGE'
usage: context.sh <file.wit> [--step N|N.M] [--out path]

Builds isolated verifier context using `wit verify`. With --out, writes the
context there and keeps JSON metadata on stdout.
USAGE
      exit 0
      ;;
    --step)
      [[ $# -ge 2 ]] || usage_error "--step requires a label"
      step="$2"
      shift 2
      ;;
    --out)
      [[ $# -ge 2 ]] || usage_error "--out requires a path"
      out="$2"
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
wit_bin="$(find_wit_cli)"
tmp_out="$(mktemp)"
tmp_err="$(mktemp)"
trap 'rm -f "$tmp_out" "$tmp_err"' EXIT

cmd=("$wit_bin" verify "$file")
[[ -n "$step" ]] && cmd+=("--step" "$step")

if run_capture "$tmp_out" "$tmp_err" "${cmd[@]}"; then
  ok=true
  code=0
else
  ok=false
  code=$?
fi

if [[ -n "$out" && "$ok" == true ]]; then
  mkdir -p "$(dirname "$out")"
  cp "$tmp_out" "$out"
fi

jq -n \
  --argjson ok "$ok" \
  --arg command "context" \
  --arg file "$file" \
  --arg step "$step" \
  --arg out "$out" \
  --arg wit_bin "$wit_bin" \
  --arg stdout "$(cat "$tmp_out")" \
  --arg stderr "$(cat "$tmp_err")" \
  --argjson exit_code "$code" \
  '{ok:$ok, command:$command, file:$file, step:(if $step|length > 0 then $step else null end), out:(if $out|length > 0 then $out else null end), wit_bin:$wit_bin, exit_code:$exit_code, stdout:$stdout, stderr:$stderr}'

exit "$code"
