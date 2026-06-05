# Plugin Integration

Use this protocol when WIT/Lean artifacts are generated or inspected.

## Registry-Aware UI

The Witsoc plugin should read `witsoc_artifacts.json` before scanning directories. If registry entries exist, prefer them over filesystem guesses.

## Open Generated Files

After generating or updating a `.wit` file:

```bash
"$PLANE_TOOL_BIN" plugins iframe use witsoc
"$PLANE_TOOL_BIN" plugins iframe bash witsoc open path/to/generated.wit
```

If structural checking is run:

```bash
"$PLANE_TOOL_BIN" plugins iframe bash witsoc check
```

If plugin activation fails, still report the artifact path and exact check status.

## Plugin State

When a plugin state endpoint is available, it should expose:

```json
{
  "target": {},
  "route": {},
  "lovasz": {},
  "dag": {},
  "artifacts": {},
  "next_actions": []
}
```

The UI must not infer mathematical verification from file presence alone.
