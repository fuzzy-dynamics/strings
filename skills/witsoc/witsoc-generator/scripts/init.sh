#!/usr/bin/env bash
# init.sh --name module_name --claim "..." [--given "..."] [--kind THEOREM] [--out file.wit]

source "$(dirname "$0")/_common.sh"
need jq

name=""
kind="THEOREM"
claim=""
out=""
givens=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      cat >&2 <<'USAGE'
usage: init.sh --name module_name --claim "statement" [options]

Options:
  --kind THEOREM|LEMMA|PROPOSITION|COROLLARY|CONJECTURE
  --given "hypothesis"       may be repeated
  --out path.wit             default: session proof worktree/<module_name>.wit

Creates a verifier-friendly .wit skeleton with UNVERIFIED status.
USAGE
      exit 0
      ;;
    --name)
      [[ $# -ge 2 ]] || usage_error "--name requires a value"
      name="$2"
      shift 2
      ;;
    --kind)
      [[ $# -ge 2 ]] || usage_error "--kind requires a value"
      kind="$2"
      shift 2
      ;;
    --claim)
      [[ $# -ge 2 ]] || usage_error "--claim requires a value"
      claim="$2"
      shift 2
      ;;
    --given)
      [[ $# -ge 2 ]] || usage_error "--given requires a value"
      givens+=("$2")
      shift 2
      ;;
    --out)
      [[ $# -ge 2 ]] || usage_error "--out requires a path"
      out="$2"
      shift 2
      ;;
    *)
      usage_error "unknown argument: $1"
      ;;
  esac
done

[[ -n "$name" ]] || usage_error "--name is required"
[[ -n "$claim" ]] || usage_error "--claim is required"
[[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "module name must be identifier-like: $name"
case "$kind" in
  THEOREM|LEMMA|PROPOSITION|COROLLARY|CONJECTURE) ;;
  *) die "unsupported kind: $kind" ;;
esac
[[ -n "$out" ]] || out="$(default_artifact_path "$name" wit)"
[[ "$out" == *.wit ]] || die "--out must end in .wit"
[[ ! -e "$out" ]] || die "refusing to overwrite existing file: $out"

mkdir -p "$(dirname "$out")"
{
  printf '%s\n' "-- Status: UNVERIFIED"
  printf '%s\n\n' "MODULE $name"
  printf '%s\n' "$kind $name:"
  if [[ "${#givens[@]}" -gt 0 ]]; then
    printf '%s\n' "  GIVEN:"
    for given in "${givens[@]}"; do
      printf '    - %s\n' "$given"
    done
  fi
  printf '%s\n' "  CLAIM:"
  printf '    %s\n\n' "$claim"
  printf '%s\n\n' "PROOF OF $name:"
  printf '%s\n' "  [1] GAP: proof not yet supplied."
  printf '%s\n' "  QED BY [1]."
} >"$out"

register_witsoc_artifact "$out" "wit" "witsoc-generator" "created"

jq -n \
  --argjson ok true \
  --arg command "init" \
  --arg file "$out" \
  --arg name "$name" \
  --arg kind "$kind" \
  '{ok:$ok, command:$command, file:$file, name:$name, kind:$kind}'
