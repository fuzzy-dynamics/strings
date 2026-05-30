# Evolution Tab

Evolution Tab renders `evolution.json` as a causal graph for deep runs. It is intentionally iframe-only: the plugin reads a small session artifact allowlist through the host bridge and sends steering actions back as structured run mail.

The renderer understands both explicit `nodes`/`edges` graphs and the deep-run
`missions[].candidates[]` schema. Candidate nodes can carry first-class run
metadata:

- `worker_session_id`, `worker_session_ids`, `sessionId`, or `worker.sessionId`
- `created_at`, `started_at`, `updated_at`, `completed_at`
- `selected`, `winning`, `blocked`, `pruned`, `merged`, or matching `status` / `state`
- `sources`, `source_links`, `evidence_sources`, `commits`

Source entries can point at session artifacts (`report.md`, `findings.md`,
`claims.md`, `progress.md`, `plan.json`), commits, URLs, or worker session IDs.
The inspector previews readable artifacts inline.

## Commands

```bash
"$PLANE_TOOL_BIN" plugins iframe use evolution-tab
"$PLANE_TOOL_BIN" plugins iframe bash evolution-tab focus <path-or-node-id>
"$PLANE_TOOL_BIN" plugins iframe bash evolution-tab compare <path-a> <path-b>
"$PLANE_TOOL_BIN" plugins iframe bash evolution-tab replay end
```

## Bridge APIs Used

- `os.session.readArtifact("evolution.json")`
- `os.session.readArtifact("plan.json")`
- `os.session.readArtifact("plugins.json")`
- `os.session.readArtifact("state/agents.json")`
- `os.session.readArtifact("report.md")`
- `os.session.readArtifact("findings.md")`
- `os.session.readArtifact("claims.md")`
- `os.session.readArtifact("progress.md")`
- `os.session.children()`
- `os.run.steer({ operation, targetSessionId, pathId, nodeId, note, params })`

The host limits steering to the active run, its parent, or its direct child sessions.
