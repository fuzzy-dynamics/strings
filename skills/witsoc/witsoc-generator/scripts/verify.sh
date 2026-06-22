#!/usr/bin/env bash
# verify.sh <file.wit> [--step N|N.M] [--out path]

source "$(dirname "$0")/_common.sh"
need jq

file=""
step=""
out=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat >&2 <<'USAGE'
usage: verify.sh <file.wit> [--step N|N.M] [--out path]

Prepares a verifier prompt. This does not call an LLM; it enforces structural
checking and outputs isolated cold-reading contexts for a skeptical verifier.
Use receipt.sh after the verifier returns lines like:
  [1] ACCEPT: ...
  [2] REJECT: ...
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
script_dir="$(cd "$(dirname "$0")" && pwd)"
cmd=("$script_dir/context.sh" "$file")
[[ -n "$step" ]] && cmd+=("--step" "$step")
[[ -n "$out" ]] && cmd+=("--out" "$out")
"${cmd[@]}"
