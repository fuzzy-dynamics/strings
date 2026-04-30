#!/usr/bin/env bash
# list.sh — print all sandboxes as a JSON array.
source "$(dirname "$0")/_common.sh"
ensure_index

jq_index '
  (.active // "") as $active
  | .sandboxes | to_entries | map({
      id:     .key,
      label:  (.value.label // .key),
      status: (.value.status // "unknown"),
      image:  (.value.image // null),
      active: (.key == $active)
    })
'
