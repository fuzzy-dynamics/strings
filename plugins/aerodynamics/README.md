# aerodynamics plugin

Visualizes potential-flow streamlines around a 3D body — the "wind tunnel in the iframe" effect from your reference image.

## What you get

- **Sky-blue 3D scene** with a white streamlined body and a fan of streamlines passing over and around it
- **Color encodes speed**: green where flow is at free-stream, yellow/orange where it accelerates over the body's bulge
- **Toolbar**: body selector (teardrop / sphere / ellipsoid), streamlines-per-row slider, vertical-rows slider, U∞ slider, **Solve** + **rotate** buttons
- **HUD + legend** at the bottom-left / top-right show body type, streamline count, U∞, and the speed range

## How it works (short version)

The server (Node, no npm deps) implements two analytical primitives:

| Primitive | Closed form |
|---|---|
| 3D doublet + uniform free-stream around a sphere | Lamb (1932) §95: `φ(x,y,z) = U·x · (1 + R³/(2r³))`, `v = ∇φ` |
| Ellipsoid approximation | rescale (x,y,z) → (x/a, y/b, z/c), evaluate sphere field, rescale velocity by (a,b,c) |

For each seeded streamline, RK4 integrates `dx/dt = v(x)` until the line passes the body. The iframe receives `{body: {positions, indices, …}, streamlines: [{positions, speeds}, …]}` and renders:

- Body: `MeshStandardMaterial` (off-white, soft roughness)
- Streamlines: one `THREE.Line` per trace with **per-vertex colors** mapped from local speed (green → yellow-green → yellow → orange)

This isn't a Navier-Stokes solver — it's *inviscid potential flow*. There's no separation, no boundary layer, no wake. But it produces visually correct streamline deflection over arbitrary axisymmetric bodies and runs in milliseconds.

## Surfaces

| Contribution | Purpose |
|---|---|
| `bin/aero-solve [body] [n] [rows] [U]` | Solve & dump JSON via the running server |
| `bin/bash` | Dispatcher: `info`, `solve`, `help` |
| `server` | Pure-JS HTTP solver — no Python, no npm deps, no system libs |
| `ui` | Three.js scene with toolbar + iframe-command bridge |

## Iframe commands

```bash
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics --help
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics body teardrop
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics streamlines 120
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics rows 8
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics speed 1.5
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics solve
"$PLANE_TOOL_BIN" plugins iframe bash aerodynamics rotate
```

## To activate

```bash
"$PLANE_TOOL_BIN" plugins activate    aerodynamics    # ~5s first time (downloads Three.js)
"$PLANE_TOOL_BIN" plugins iframe use  aerodynamics
```

The iframe solves with default parameters as soon as it loads — you should see streamlines flowing over the teardrop body within ~1s.

## Roadmap

- v0.2: load a `.stl` body (uses ellipsoid fit for the flow approximation)
- v0.2: arrow glyphs at sample points (velocity vector field overlay)
- v0.3: viscous correction term — boundary-layer thickness via Blasius solution
- v0.3: lift / drag estimates from pressure integration over the body surface
- v0.4: real CFD via OpenFOAM (out-of-process, async; results streamed back)
