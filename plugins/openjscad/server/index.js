"use strict";

// openjscad plugin server.
//
// Spawned by plane-server's lifecycle. Loads @jscad/modeling from the
// bundled node_modules (created by bin/ensure-deps).
//
// Endpoints:
//   GET /health                      → liveness ping
//   GET /api/info                    → version, pid, uptime, render counters
//   GET /api/list?dir=<abs>          → list .jscad files under <dir>
//   GET /api/render?path=<abs>[&color=<hex>]
//                                    → JSON {groups:[{color,positions}]}
//                                      Per-polygon colors from jscad's
//                                      colors.colorize() are preserved;
//                                      bucket by color → one mesh per
//                                      bucket on the client.
//   GET /api/render-stl?path=<abs>   → binary STL (for export / 3D printing)

const fs = require("fs");
const http = require("http");
const path = require("path");

const PORT = parseInt(process.env.PORT || "0", 10);
const PLUGIN_ID = process.env.PLUGIN_ID || "openjscad";
const PLUGIN_DIR = path.resolve(__dirname, "..");
const NODE_MODULES = path.join(PLUGIN_DIR, "data", "node_modules");

const modeling = require(path.join(NODE_MODULES, "@jscad/modeling"));
const stlSerializer = require(path.join(NODE_MODULES, "@jscad/stl-serializer"));
const modelingPackage = require(path.join(NODE_MODULES, "@jscad/modeling", "package.json"));

const startedAt = new Date().toISOString();
let renderCount = 0;
let renderErrorCount = 0;

function sendJson(res, code, payload) {
  res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(payload));
}

// ─── .jscad sandbox loader ───────────────────────────────────────────────

function loadJscadModule(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const dir = path.dirname(filePath);
  const Module = require("module");
  const fileRequire = Module.createRequire(path.join(dir, "noop.js"));

  const customRequire = (name) => {
    if (name === "@jscad/modeling") return modeling;
    if (name === "@jscad/stl-serializer") return stlSerializer;
    if (name.startsWith("@jscad/")) {
      try { return require(path.join(NODE_MODULES, name)); } catch { /* fall through */ }
    }
    return fileRequire(name);
  };

  const mod = { exports: {} };
  const wrapped = new Function("require", "module", "exports", "__filename", "__dirname", source);
  wrapped(customRequire, mod, mod.exports, filePath, dir);
  return mod.exports;
}

function defaultParams(jscadModule) {
  if (typeof jscadModule.getParameterDefinitions !== "function") return {};
  const defs = jscadModule.getParameterDefinitions() || [];
  const values = {};
  for (const p of defs) {
    if (p.initial !== undefined) values[p.name] = p.initial;
    else if (p.default !== undefined) values[p.name] = p.default;
  }
  return values;
}

function evalJscad(filePath) {
  const mod = loadJscadModule(filePath);
  const main = mod.main || mod.default || (typeof mod === "function" ? mod : null);
  if (!main) throw new Error("no_main_export — file must export `main` (or `default`)");
  const params = defaultParams(mod);
  const result = main(params);
  return Array.isArray(result) ? result : [result];
}

// ─── Color helpers ───────────────────────────────────────────────────────

const DEFAULT_COLOR = [0.42, 0.65, 1.0, 1.0];

function parseColorParam(s) {
  if (!s || typeof s !== "string") return null;
  let t = s.trim();
  if (t.startsWith("#")) t = t.slice(1);
  if (/^[0-9a-f]{6}$/i.test(t)) {
    return [
      parseInt(t.slice(0, 2), 16) / 255,
      parseInt(t.slice(2, 4), 16) / 255,
      parseInt(t.slice(4, 6), 16) / 255,
      1.0,
    ];
  }
  if (/^[0-9a-f]{8}$/i.test(t)) {
    return [
      parseInt(t.slice(0, 2), 16) / 255,
      parseInt(t.slice(2, 4), 16) / 255,
      parseInt(t.slice(4, 6), 16) / 255,
      parseInt(t.slice(6, 8), 16) / 255,
    ];
  }
  // rgb(...) form: comma-separated 0..1 or 0..255
  const m = t.match(/^([0-9.]+)\s*[, ]\s*([0-9.]+)\s*[, ]\s*([0-9.]+)(?:\s*[, ]\s*([0-9.]+))?$/);
  if (m) {
    const nums = [m[1], m[2], m[3], m[4] || "1"].map(Number);
    const looks255 = nums.slice(0, 3).some((n) => n > 1.5);
    return looks255 ? [nums[0] / 255, nums[1] / 255, nums[2] / 255, nums[3] || 1] : nums;
  }
  return null;
}

function colorKey(c) {
  return c.map((v) => Number(v).toFixed(3)).join(",");
}

// ─── Geometry → JSON groups (bucketed by color) ──────────────────────────

function appendTriangulatedPolygon(positions, poly) {
  const v = poly.vertices;
  for (let i = 1; i < v.length - 1; i++) {
    positions.push(v[0][0], v[0][1], v[0][2]);
    positions.push(v[i][0], v[i][1], v[i][2]);
    positions.push(v[i + 1][0], v[i + 1][1], v[i + 1][2]);
  }
}

function renderToGroups(filePath, override) {
  const geometries = evalJscad(filePath);
  const geom3 = modeling.geometries.geom3;

  // Override path: ignore per-polygon colors; one bucket only.
  if (override) {
    const positions = [];
    for (const geom of geometries) {
      if (!geom || typeof geom3.toPolygons !== "function") continue;
      const polys = geom3.toPolygons(geom);
      for (const poly of polys) appendTriangulatedPolygon(positions, poly);
    }
    return [{ color: override, positions }];
  }

  // Default: bucket by polygon color, falling back to geom-level color, then DEFAULT.
  const buckets = new Map();
  for (const geom of geometries) {
    if (!geom || typeof geom3.toPolygons !== "function") continue;
    const polys = geom3.toPolygons(geom);
    const geomDefault = (geom.color && geom.color.length >= 3) ? geom.color : DEFAULT_COLOR;
    for (const poly of polys) {
      const c = (poly.color && poly.color.length >= 3) ? poly.color : geomDefault;
      const rgba = [
        Number(c[0]),
        Number(c[1]),
        Number(c[2]),
        c[3] !== undefined ? Number(c[3]) : 1,
      ];
      const key = colorKey(rgba);
      let bucket = buckets.get(key);
      if (!bucket) {
        bucket = { color: rgba, positions: [] };
        buckets.set(key, bucket);
      }
      appendTriangulatedPolygon(bucket.positions, poly);
    }
  }
  return Array.from(buckets.values());
}

function renderToStl(filePath) {
  const geometries = evalJscad(filePath);
  const chunks = stlSerializer.serialize({ binary: true }, ...geometries);
  const buffers = chunks.map((c) =>
    typeof c === "string" ? Buffer.from(c, "binary") : Buffer.from(c.buffer || c),
  );
  return Buffer.concat(buffers);
}

// ─── List .jscad under a dir ─────────────────────────────────────────────

function listJscadFiles(rootDir, maxDepth = 6, max = 500) {
  const out = [];
  const skip = new Set(["node_modules", ".git", ".venv", "__pycache__", "dist", "build"]);
  function walk(dir, depth) {
    if (depth > maxDepth || out.length >= max) return;
    let entries = [];
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      if (out.length >= max) return;
      if (skip.has(entry.name) || entry.name.startsWith(".")) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full, depth + 1);
      else if (entry.isFile() && entry.name.toLowerCase().endsWith(".jscad")) {
        out.push({ path: full, name: entry.name, rel: path.relative(rootDir, full) });
      }
    }
  }
  walk(rootDir, 0);
  return out;
}

// ─── HTTP server ────────────────────────────────────────────────────────

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
      modeling_version: modelingPackage.version,
      node: process.version,
      started_at: startedAt,
      uptime_seconds: Math.round(process.uptime()),
      render_count: renderCount,
      render_error_count: renderErrorCount,
    });
  }

  if (u.pathname === "/api/list") {
    const dir = u.searchParams.get("dir");
    if (!dir) return sendJson(res, 400, { error: "dir_required" });
    if (!fs.existsSync(dir)) return sendJson(res, 404, { error: "dir_not_found", dir });
    return sendJson(res, 200, { dir, files: listJscadFiles(dir) });
  }

  if (u.pathname === "/api/render") {
    const filePath = u.searchParams.get("path");
    if (!filePath) return sendJson(res, 400, { error: "path_required" });
    if (!fs.existsSync(filePath)) return sendJson(res, 404, { error: "file_not_found", path: filePath });
    const override = parseColorParam(u.searchParams.get("color"));
    try {
      const groups = renderToGroups(filePath, override);
      const totalTris = groups.reduce((n, g) => n + g.positions.length / 9, 0);
      renderCount += 1;
      return sendJson(res, 200, {
        path: filePath,
        groups,
        triangle_count: totalTris,
        color_count: groups.length,
        render_count: renderCount,
      });
    } catch (err) {
      renderErrorCount += 1;
      return sendJson(res, 500, {
        error: "render_failed",
        message: err.message,
        stack: String(err.stack || "").split("\n").slice(0, 5).join("\n"),
      });
    }
  }

  if (u.pathname === "/api/render-stl") {
    const filePath = u.searchParams.get("path");
    if (!filePath) return sendJson(res, 400, { error: "path_required" });
    if (!fs.existsSync(filePath)) return sendJson(res, 404, { error: "file_not_found", path: filePath });
    try {
      const buf = renderToStl(filePath);
      renderCount += 1;
      res.writeHead(200, {
        "Content-Type": "application/sla",
        "Content-Length": buf.length,
        "Cache-Control": "no-store",
        "X-Render-Count": String(renderCount),
      });
      return res.end(buf);
    } catch (err) {
      renderErrorCount += 1;
      return sendJson(res, 500, {
        error: "render_failed",
        message: err.message,
        stack: String(err.stack || "").split("\n").slice(0, 5).join("\n"),
      });
    }
  }

  sendJson(res, 404, { error: "not_found", path: u.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(
    `[openjscad] listening on 127.0.0.1:${server.address().port}, pid=${process.pid}, modeling=${modelingPackage.version}\n`,
  );
});

const shutdown = (signal) => {
  process.stdout.write(`[openjscad] received ${signal}, exiting\n`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
