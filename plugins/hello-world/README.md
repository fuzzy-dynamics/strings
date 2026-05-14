# hello-world

Reference plugin for the OpenScientist plugin architecture (v1).

Demonstrates the `bin/` contribution surface — a single shell script that prints
a greeting and dumps the plugin's runtime context.

## Files

```
hello-world/
├── plugin.json   ← manifest
├── bin/
│   └── hello     ← the only tool this plugin exposes
└── README.md
```

## Try it

```bash
"$PLANE_TOOL_BIN" plugins list
"$PLANE_TOOL_BIN" plugins view hello-world
"$PLANE_TOOL_BIN" plugins activate hello-world
"$PLANE_TOOL_BIN" plugins use hello-world

# v1 ships without $PATH integration — run the bin directly for now:
~/.openscientist/plugins/hello-world/bin/hello "openscientist"
```

`plugins use hello-world` records the use in `$PLANE_SESSION_DIR/plugins.json`.
