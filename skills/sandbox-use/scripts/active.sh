#!/usr/bin/env bash
# active.sh [<host-path>] — print the ids of running sandboxes.
#
# With no args: every sandbox whose container is currently running, as a
# JSON array of ids.
#
# With <host-path>: filter to sandboxes whose live bind set includes that
# path (i.e. the "active for this path" predicate — which sandboxes have
# this directory mounted in?). Useful for the frontend to ask "which
# sandbox am I bound to for this space?" and for agents to discover the
# right --sandbox id from their CWD.
source "$(dirname "$0")/_common.sh"
ensure_index

probe="${1:-}"
ids=()
while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  ids+=("$id")
done < <(jq_index -r '.sandboxes | keys[]')

result=()
for id in "${ids[@]:-}"; do
  name="$(container_name "$id")"
  container_running "$name" || continue
  if [[ -z "$probe" ]]; then
    result+=("$id")
    continue
  fi
  while IFS= read -r b; do
    [[ -z "$b" ]] && continue
    if [[ "$probe" == "$b" || "$probe" == "$b"/* ]]; then
      result+=("$id")
      break
    fi
  done < <(container_bindings "$name")
done

if [[ ${#result[@]} -eq 0 ]]; then
  printf '[]\n'
else
  printf '%s\n' "${result[@]}" | jq -R . | jq -s .
fi
