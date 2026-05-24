# Evolution Tab

Evolution Tab renders `evolution.json` as a causal graph for deep runs. It is intentionally iframe-only: the plugin reads a small session artifact allowlist through the host bridge and sends steering actions back as structured run mail.

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
- `os.session.children()`
- `os.run.steer({ operation, targetSessionId, pathId, nodeId, note, params })`

The host limits steering to the active run, its parent, or its direct child sessions.
