# openjscad plugin

Embeds [OpenJSCAD](https://github.com/jscad/OpenJSCAD.org) — programmatic CAD via JavaScript — as a side-panel iframe in OpenScientist.

## What you get

- **Left sidebar**: every `.jscad` file in the orchestrator's worktree (auto-refreshed every 8s) plus three bundled samples
- **Right pane**: interactive 3D viewer (Three.js + OrbitControls) showing the selected file's geometry
- **Toolbar**: toggle axes / wireframe, refresh, render-to-STL render count + dimensions tag

## Surfaces

| Contribution | What it does |
|---|---|
| `bin/jscad-list` | List `.jscad` files under `$KIMI_WORK_DIR` |
| `bin/jscad-render <in> [out]` | Render a `.jscad` to STL via the running server |
| `bin/bash` | Dispatcher: `info`, `list`, `render`, `help` |
| `server` | Node HTTP server that loads `@jscad/modeling`, executes a `.jscad` file's `main()`, serializes the result to STL |
| `ui/index.html` | The two-pane editor UI |

## How it bundles

The plugin is **fully self-contained** — no system-level Python or `jscad` CLI required. On first activation, `bin/ensure-deps`:

1. Runs `npm install` for `@jscad/modeling` + `@jscad/stl-serializer` into `data/node_modules/`
2. Downloads pinned Three.js r147 (UMD-friendly) into `ui/vendor/`

Subsequent activations skip both steps. First activation takes ~30-60s; later ones spawn in <2s.

## Iframe commands

```bash
"$PLANE_TOOL_BIN" plugins iframe bash openjscad --help
"$PLANE_TOOL_BIN" plugins iframe bash openjscad show /path/to/foo.jscad
"$PLANE_TOOL_BIN" plugins iframe bash openjscad wireframe
"$PLANE_TOOL_BIN" plugins iframe bash openjscad axes
"$PLANE_TOOL_BIN" plugins iframe bash openjscad refresh
```

## Plugin commands (host-side)

```bash
"$PLANE_TOOL_BIN" plugins activate     openjscad
"$PLANE_TOOL_BIN" plugins iframe use   openjscad
"$PLANE_TOOL_BIN" plugins bash         openjscad info
"$PLANE_TOOL_BIN" plugins bash         openjscad list
"$PLANE_TOOL_BIN" plugins bash         openjscad render shapes.jscad
```

## Writing a `.jscad` file

```js
// shapes.jscad
const { primitives, transforms, booleans } = require("@jscad/modeling");

function main() {
  const a = primitives.cube({ size: 30 });
  const b = transforms.translate([15, 15, 15], primitives.sphere({ radius: 22 }));
  return booleans.intersect(a, b);
}

module.exports = { main };
```

Drop it in your worktree, click it in the sidebar — the right pane renders in <1s for typical models.

## Architecture note

**The iframe never talks directly to JSCAD's WebGL renderer.** Instead the plugin server runs `@jscad/modeling` server-side, serializes geometry to STL, and the iframe renders the STL with Three.js. Two reasons: (1) avoids bundling the heavyweight `@jscad/regl-renderer` browser deps, (2) STL is a universal interchange — same plugin could feed any 3D viewer.

The trade-off: changes to a `.jscad` file require a re-render round-trip (network + Node eval), so very rapid iteration is slower than a pure-browser jscad playground. For typical CAD work this is invisible.
