#!/usr/bin/env bash
# list.sh — print all machines as a JSON array (including the reserved "local" row).
source "$(dirname "$0")/_common.sh"
ensure_index

jq_index '
  (.active // "local") as $active
  | [{name: "local", status: "ready", host: null, bundleVersion: null, active: ($active == "local")}]
    + (.machines | to_entries | map({
        name:          .key,
        status:        (.value.status // "unknown"),
        host:          (.value.host // null),
        bundleVersion: (.value.bundleVersion // null),
        active:        (.key == $active)
      }))
'
