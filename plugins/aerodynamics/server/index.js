"use strict";

// Aerodynamics plugin server.
//
// Single endpoint of substance: /api/solve. Takes body type + flow params,
// runs an analytical potential-flow solve, returns:
//   { body: { positions, indices, a, b, c, length, type },
//     streamlines: [{ positions: [x,y,z,…], speeds: [s,s,…] }, ...],
//     info: { U, body, count, sMin, sMax, solve_count } }
//
// All math is closed-form; no native deps, no npm install required.

const http = require("http");
const path = require("path");

const { ellipsoidVelocity, velocityWithWake, traceStreamline } = require("./flow.js");
const { teardrop, sphere, ellipsoid } = require("./bodies.js");
const { loadStl } = require("./stl.js");

const PORT = parseInt(process.env.PORT || "0", 10);
const PLUGIN_ID = process.env.PLUGIN_ID || "aerodynamics";
const startedAt = new Date().toISOString();
let solveCount = 0;
let solveErrorCount = 0;

function sendJson(res, code, payload) {
  res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(payload));
}

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function buildBody(type) {
  switch ((type || "teardrop").toLowerCase()) {
    case "sphere":    return sphere({ radius: 6 });
    case "ellipsoid": return ellipsoid({ a: 14, b: 5, c: 7 });
    case "teardrop":
    default:          return teardrop({ length: 30, maxRadius: 6 });
  }
}

function buildStlBody(absPath) {
  // Reads + centers the STL, derives ellipsoid axes from the bounding box.
  // No indices: each consecutive triplet of vertex positions is one
  // triangle (the iframe sets `flatShading: true` so per-face normals
  // computed by Three.js look right).
  const stl = loadStl(absPath);
  return stl;
}

// Compute Cp (pressure coefficient) and a friction proxy at every vertex
// of the body mesh. We sample the analytical flow field just outside each
// vertex (offset along the position vector from origin), since the field
// returns zero exactly inside the body.
//
//   Cp     = 1 - (|v|/U∞)²            (Bernoulli, incompressible inviscid)
//   fric   = |v|/U∞                    (proportional to wall shear in our
//                                       proxy — true τ_w needs boundary-
//                                       layer integration; this is the
//                                       cheap inviscid analog)
//
// Returns { pressure: Float32Array, friction: Float32Array }.
function computeSurfaceFields(body, U) {
  const positions = body.positions;
  const N = positions.length / 3;
  const a = body.a, b = body.b, c = body.c;
  const pressure = new Array(N);
  const friction = new Array(N);

  for (let i = 0; i < N; i++) {
    const x = positions[i * 3];
    const y = positions[i * 3 + 1];
    const z = positions[i * 3 + 2];
    const r = Math.sqrt(x * x + y * y + z * z);
    if (r < 1e-6) {
      pressure[i] = 1.0;     // origin → stagnation
      friction[i] = 0.0;
      continue;
    }
    // Offset 2% outward along the radial direction so we sample the
    // exterior potential field, not the masked-zero interior.
    const eps = 0.02 * r + 0.001;
    const sx = x + (x / r) * eps;
    const sy = y + (y / r) * eps;
    const sz = z + (z / r) * eps;
    const v = ellipsoidVelocity(sx, sy, sz, U, a, b, c);
    const speed = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    const ratio = speed / U;
    // Clamp to physically reasonable ranges. The offset-from-origin trick
    // has artifacts near sharp tips where the ellipsoid approximation
    // breaks down — uncapped values can spike to thousands and would
    // squash the visualisation colormap. Cp ∈ [-3, 1] covers all common
    // streamlined / blunt bodies; friction proxy capped at 2.5×U.
    const cp = 1 - ratio * ratio;
    pressure[i] = cp < -3 ? -3 : (cp > 1 ? 1 : cp);
    friction[i] = ratio > 2.5 ? 2.5 : ratio;
  }

  return { pressure, friction };
}

// Heuristic aerodynamic coefficients. Pure inviscid potential flow gives
// d'Alembert's paradox (Cd ≡ 0), so we estimate from body slenderness +
// wake amplitude. These are *plausible* values, not solver-derived. Plugin
// authors swapping in a real CFD backend should replace this function.
function computeAeroCoeffs(body, U, wakeAmp) {
  const a = body.a, b = body.b, c = body.c;
  // Frontal area: cross-section in YZ plane, approximated as ellipse.
  const A = Math.PI * b * c;
  // Slenderness (length / max cross-section radius). Sphere ≈ 1, F1 car ≈ 5.
  const slenderness = a / Math.max(b, c);
  // Form drag: sphere baseline 0.47, decreases for slender bodies (1/√slen),
  // plus wake-induced drag scaling.
  const baseCd = 0.47 / Math.sqrt(Math.max(1, slenderness));
  const Cd = Math.max(0.05, baseCd + 0.55 * wakeAmp);
  // Lift: small downforce-like for non-spherical bodies, 0 for sphere.
  // Negative = downforce (typical aero convention for vehicle bodies).
  const downforce = slenderness > 1.3 ? 1 : 0;
  const Cl = -1.4 * downforce - 0.7 * wakeAmp * downforce;
  const Cl_f = Cl * 0.652;        // ~65% to front (typical F1)
  const Cl_r = Cl * 0.348;
  const CdA  = Cd * A;
  const L_D  = Cd > 1e-6 ? Cl / Cd : 0;

  // Force / power at the current free-stream U.
  const RHO = 1.225;
  const Fd_now = 0.5 * RHO * U * U * A * Cd;
  const P_now  = Fd_now * U;

  // Curves over a sane velocity range (m/s).
  const drag_curve = [];
  const power_curve = [];
  for (let u = 0; u <= 80; u += 5) {
    const fd = 0.5 * RHO * u * u * A * Cd;
    drag_curve.push({ u, Fd: fd });
    power_curve.push({ u, P_kW: (fd * u) / 1000 });
  }

  return {
    Cd, CdA, A,
    Cl, Cl_f, Cl_r, L_D,
    rho: RHO,
    drag_force_now: Fd_now,
    power_now_kW: P_now / 1000,
    drag_curve,
    power_curve,
  };
}

function solveFlow(params) {
  const bodyType = params.body || "teardrop";
  const stlPath  = params.stl_path || null;
  // U_display is the physical free-stream velocity (m/s) — drives aero
  // coefficient curves only. The streamline solver uses a normalised
  // U=1.0 because incompressible inviscid flow is scale-invariant in
  // velocity: streamline geometry doesn't depend on U_∞. Decoupling this
  // way means dragging the velocity slider doesn't break integration
  // step sizing.
  const U_display = clamp(parseFloat(params.U) || 1.0, 0.05, 200);
  const U         = 1.0;
  const N         = clamp(parseInt(params.n) || 80, 4, 400);
  const yRows  = clamp(parseInt(params.yRows) || 5, 1, 24);
  // Body-relative Y offset for the streamline-seed grid. -2..+2 covers a
  // sane range for any body. Lets the iframe slide a single sheet up/down
  // through the flow without re-seeding multiple rows.
  const yOffsetRel = clamp(parseFloat(params.yOffset) || 0, -3, 3);
  const zOffsetRel = clamp(parseFloat(params.zOffset) || 0, -3, 3);
  const steps      = clamp(parseInt(params.maxSteps) || 220, 20, 2000);
  // dt is intentionally NOT a fixed-time step — that breaks for STLs whose
  // units are millimetres / metres / kilometres differently. We pick it so
  // each RK4 step advances ~4 % of body half-length in the free-stream
  // direction, regardless of body scale. Streamlines therefore have a
  // body-scale-invariant point count (~150 sample points across the
  // domain). User can still override with ?dt=… if they want.
  const dtOverride = parseFloat(params.dt);
  // Wake amplitude (0 = clean potential flow, 1 = strong vortex shedding).
  // Default 0.55 gives a visible chaotic wake without overwhelming the
  // upstream streamline pattern. Note: `|| default` would mis-handle
  // wake=0 since 0 is falsy — use NaN check explicitly.
  const wakeRaw = parseFloat(params.wake);
  const wakeAmp = Number.isNaN(wakeRaw) ? 0.55 : clamp(wakeRaw, 0, 2);

  const body = stlPath ? buildStlBody(stlPath) : buildBody(bodyType);
  const a = body.a, b = body.b, c = body.c;

  // Body-scale-invariant integration step. ~150 RK4 evaluations to cross
  // the entire computation domain (xStart -3a → xEnd 3a) at U_solve=1.
  const dt = Number.isNaN(dtOverride) ? Math.max(0.001, a * 0.04) : clamp(dtOverride, 0.001, a * 1.0);

  // Velocity field: potential flow base + curl-noise wake behind body.
  const velocityFn = (p) => velocityWithWake(p[0], p[1], p[2], U, a, b, c, wakeAmp);

  // Seed streamlines:
  //   x: far upstream (-3a)
  //   y: rows from just below body axis up to top of body × 1.4
  //   z: spread laterally across body span × 1.6
  const xStart = -3 * a;
  const xEnd   =  3 * a;
  const ySpan  = b * 2.4;                          // total vertical span across rows
  const yMid   = b * 0.4 + b * yOffsetRel;          // base height + Y-slider offset
  const zMid   = 0       + c * zOffsetRel;          // lateral offset (Z slider)
  const zSpan  = c * 2.6;

  const streamlines = [];
  for (let row = 0; row < yRows; row++) {
    const yT = yRows === 1 ? 0.5 : row / (yRows - 1);
    const y = yMid - ySpan / 2 + ySpan * yT;
    for (let i = 0; i < N; i++) {
      const z = zMid - zSpan + (2 * zSpan * i) / Math.max(1, N - 1);
      const trace = traceStreamline(velocityFn, [xStart, y, z], dt, steps, xEnd);
      if (trace.positions.length >= 6) streamlines.push(trace);
    }
  }

  // Speed + turbulence ranges for normalised colouring.
  let sMin = Infinity, sMax = 0;
  let tMin = Infinity, tMax = 0;
  for (const sl of streamlines) {
    for (const s of sl.speeds) {
      if (s < sMin) sMin = s;
      if (s > sMax) sMax = s;
    }
    for (const t of (sl.turbs || [])) {
      if (t < tMin) tMin = t;
      if (t > tMax) tMax = t;
    }
  }
  if (!Number.isFinite(sMin)) { sMin = 0; sMax = 1; }
  if (!Number.isFinite(tMin)) { tMin = 0; tMax = 0; }

  // Surface scalar fields — pressure coefficient (Bernoulli) and a friction
  // proxy (normalised tangential speed). Sampled at each body vertex by
  // nudging slightly outward from origin along the position vector and
  // evaluating the analytical velocity field there. Works for our convex
  // / star-shaped bodies (teardrop, sphere, ellipsoid, typical STLs).
  const surface = computeSurfaceFields(body, U);
  let cpMin = Infinity, cpMax = -Infinity, frMin = Infinity, frMax = -Infinity;
  for (let i = 0; i < surface.pressure.length; i++) {
    const cp = surface.pressure[i];
    const fr = surface.friction[i];
    if (cp < cpMin) cpMin = cp; if (cp > cpMax) cpMax = cp;
    if (fr < frMin) frMin = fr; if (fr > frMax) frMax = fr;
  }
  if (!Number.isFinite(cpMin)) { cpMin = 0; cpMax = 1; frMin = 0; frMax = 1; }

  const aero = computeAeroCoeffs(body, U_display, wakeAmp);

  solveCount++;

  return {
    body: {
      positions: body.positions,
      indices: body.indices || null,
      a, b, c,
      length: body.length,
      type: body.type,
      triangle_count: body.triangle_count || (body.indices ? body.indices.length / 3 : body.positions.length / 9),
      stl_path: stlPath || null,
      pressure: surface.pressure,
      friction: surface.friction,
    },
    streamlines,
    aero,
    info: {
      U: U_display, U_solve: U,
      body: stlPath ? "stl" : bodyType, n_per_row: N, rows: yRows,
      y_offset: yOffsetRel,
      z_offset: zOffsetRel,
      wake_amplitude: wakeAmp,
      streamline_count: streamlines.length,
      s_min: sMin, s_max: sMax,
      t_min: tMin, t_max: tMax,
      cp_min: cpMin, cp_max: cpMax,
      friction_min: frMin, friction_max: frMax,
      solve_count: solveCount,
    },
  };
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (u.pathname === "/health") {
    return sendJson(res, 200, {
      ok: true, plugin: PLUGIN_ID, pid: process.pid,
      started_at: startedAt, uptime_seconds: Math.round(process.uptime()),
    });
  }

  if (u.pathname === "/api/info") {
    return sendJson(res, 200, {
      plugin: PLUGIN_ID, pid: process.pid, port: PORT,
      node: process.version,
      started_at: startedAt, uptime_seconds: Math.round(process.uptime()),
      solve_count: solveCount,
      solve_error_count: solveErrorCount,
      bodies: ["teardrop", "sphere", "ellipsoid"],
    });
  }

  if (u.pathname === "/api/solve") {
    try {
      const params = Object.fromEntries(u.searchParams);
      const result = solveFlow(params);
      return sendJson(res, 200, result);
    } catch (err) {
      solveErrorCount++;
      return sendJson(res, 500, {
        error: "solve_failed", message: err.message,
        stack: String(err.stack || "").split("\n").slice(0, 5).join("\n"),
      });
    }
  }

  // Solve against an STL file from disk. Path must be absolute.
  if (u.pathname === "/api/solve-stl") {
    try {
      const params = Object.fromEntries(u.searchParams);
      const stlPath = params.path;
      if (!stlPath) {
        return sendJson(res, 400, { error: "path_required" });
      }
      if (!path.isAbsolute(stlPath)) {
        return sendJson(res, 400, { error: "path_must_be_absolute", path: stlPath });
      }
      const result = solveFlow({ ...params, stl_path: stlPath });
      return sendJson(res, 200, result);
    } catch (err) {
      solveErrorCount++;
      return sendJson(res, 500, {
        error: "solve_stl_failed", message: err.message,
        stack: String(err.stack || "").split("\n").slice(0, 5).join("\n"),
      });
    }
  }

  sendJson(res, 404, { error: "not_found", path: u.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(`[aerodynamics] listening on 127.0.0.1:${server.address().port}, pid=${process.pid}\n`);
});

const shutdown = (signal) => {
  process.stdout.write(`[aerodynamics] received ${signal}, exiting\n`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT",  () => shutdown("SIGINT"));
