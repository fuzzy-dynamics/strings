"use strict";

// Witsoc plugin server.
//
// Pure-Node HTTP fronter that shells out to `data/venv/bin/wit`. Endpoints:
//   GET  /health                                 → liveness
//   GET  /api/info                               → venv path + wit version
//   GET  /api/list?dir=<abs>                     → recursive .wit + .soc list
//   GET  /api/file?path=<abs>                    → raw text
//   PUT  /api/file?path=<abs>                    → body = new content
//   POST /api/check?path=<abs>                   → wit check stdout/stderr/exit
//   POST /api/verify?path=<abs>[&step=N.M]       → wit verify stdout
//   POST /api/context?path=<abs>                 → wit context stdout
//   POST /api/receipt?path=<abs>                 → body = verifier output → wit receipt (stdin)
//   GET  /api/receipt?path=<abs>                 → current .wit.receipt.json (or null)
//   POST /api/parse?path=<abs>                   → JSON proof tree (regex parser fallback)
//   GET  /api/soc?path=<abs>                     → parsed .soc (queue + insights + progress)
//   POST /api/soc?path=<abs>                     → write .soc (body = full text)

const fs = require("fs");
const http = require("http");
const path = require("path");
const { execFile } = require("child_process");

const PORT = parseInt(process.env.PORT || "0", 10);
const PLUGIN_ID = process.env.PLUGIN_ID || "witsoc";
const PLUGIN_DIR = path.resolve(__dirname, "..");
const VENV_DIR = process.env.WITSOC_VENV || path.join(PLUGIN_DIR, "data", "venv");
const WIT = path.join(VENV_DIR, "bin", "wit");

const startedAt = new Date().toISOString();

function sendJson(res, code, payload) {
  res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(payload));
}
function sendText(res, code, text, contentType = "text/plain; charset=utf-8") {
  res.writeHead(code, { "Content-Type": contentType, "Cache-Control": "no-store" });
  res.end(text);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}
function runWit(args, stdin = null, timeoutMs = 60000) {
  return new Promise((resolve) => {
    const child = execFile(WIT, args, { timeout: timeoutMs, maxBuffer: 4 * 1024 * 1024 }, (err, stdout, stderr) => {
      resolve({
        ok: !err,
        exit_code: err ? (err.code || 1) : 0,
        signal: err ? err.signal || null : null,
        stdout: stdout.toString(),
        stderr: stderr.toString(),
        timed_out: err ? !!err.killed : false,
      });
    });
    if (stdin != null && child.stdin) {
      child.stdin.write(stdin);
      child.stdin.end();
    }
  });
}

// ─── .wit parser (regex, fallback when wit binary unavailable) ────────────
//
// Walks the source for top-level `MODULE`, `THEOREM`, `LEMMA`, `PROPOSITION`,
// `COROLLARY`, `CONJECTURE`, `PROOF OF`, and step labels like `[1]`, `[2.1]`
// with their keyword + claim text. This isn't a full parser — it lets the
// iframe show a tree even if the venv hasn't been built yet, or if witsoc's
// CLI exits with a parse error we'd like to surface gracefully.
function parseWitText(source) {
  const lines = source.split(/\r?\n/);
  const result = {
    status: "UNVERIFIED",
    module: null,
    claims: [],   // [{kind, name, line}]
    proofs: [],   // [{name, steps: [{label, keyword, claim, by, line}], qed}]
  };

  // Header line "-- Status: VERIFIED|UNVERIFIED|REJECTED"
  for (const line of lines) {
    const m = line.match(/^--\s*Status:\s*(\w+)/i);
    if (m) { result.status = m[1].toUpperCase(); break; }
    if (!line.startsWith("--") && line.trim() !== "") break;
  }

  // MODULE name
  for (const line of lines) {
    const m = line.match(/^\s*MODULE\s+([A-Za-z_][\w]*)/);
    if (m) { result.module = m[1]; break; }
  }

  // Claims and proofs
  let cur = null;            // current proof being parsed
  const KIND_RE = /^\s*(THEOREM|LEMMA|PROPOSITION|COROLLARY|CONJECTURE)\s+([A-Za-z_][\w]*)/;
  const PROOF_RE = /^\s*PROOF\s+OF\s+([A-Za-z_][\w]*)/;
  const STEP_RE  = /^\s*\[([\d.]+)\]\s+(HAVE|SHOW|ASSUME|LET|CONSIDER|SUFFICES|CASE|CITE|GAP)\b\s*(.*)$/;
  const QED_RE   = /^\s*QED(?:\s+\[([\d.]+)\])?\s*(?:BY\s+(.*))?$/i;
  const BY_RE    = /^\s*BY\s+(.*)$/;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    let m;
    if ((m = line.match(KIND_RE))) {
      result.claims.push({ kind: m[1], name: m[2], line: i + 1 });
      continue;
    }
    if ((m = line.match(PROOF_RE))) {
      cur = { name: m[1], steps: [], qed: null, line: i + 1 };
      result.proofs.push(cur);
      continue;
    }
    if (cur && (m = line.match(STEP_RE))) {
      cur.steps.push({
        label: m[1],
        keyword: m[2],
        claim: m[3].trim(),
        by: null,
        line: i + 1,
      });
      continue;
    }
    if (cur && cur.steps.length && (m = line.match(BY_RE))) {
      // Attach BY to the previous step (and any continuation lines).
      const last = cur.steps[cur.steps.length - 1];
      last.by = (last.by ? last.by + " " : "") + m[1].trim();
      continue;
    }
    if (cur && (m = line.match(QED_RE))) {
      cur.qed = { label: m[1] || null, by: m[2] || null, line: i + 1 };
    }
  }
  return result;
}

// ─── .soc parser ─────────────────────────────────────────────────────────

function parseSocText(source) {
  const lines = source.split(/\r?\n/);
  const result = {
    goal: null,
    progress_a: null,
    progress_b: null,
    insights_since: null,
    queue: [],     // [{done: bool, text, line}]
    insights: [],  // [{text, line}]
    log: [],       // [{text, line}]
  };
  let section = null;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    let m;
    if ((m = line.match(/^\s*GOAL:\s*(.*)$/i))) { result.goal = m[1].trim(); continue; }
    if ((m = line.match(/^\s*PROGRESS:\s*(\d+)\s*\/\s*(\d+)/i))) {
      result.progress_a = parseInt(m[1], 10);
      result.progress_b = parseInt(m[2], 10);
      continue;
    }
    if ((m = line.match(/^\s*INSIGHTS_SINCE_LAST_UPDATE:\s*(\d+)/i))) {
      result.insights_since = parseInt(m[1], 10); continue;
    }
    if (/^\s*QUEUE:/i.test(line))    { section = "queue";    continue; }
    if (/^\s*INSIGHTS:/i.test(line)) { section = "insights"; continue; }
    if (/^\s*LOG:/i.test(line))      { section = "log";      continue; }

    if (section === "queue" && (m = line.match(/^\s*-\s*\[([ x])\]\s*(.*)$/))) {
      result.queue.push({ done: m[1] === "x", text: m[2].trim(), line: i + 1 });
    } else if (section === "insights" && (m = line.match(/^\s*-\s*(.*)$/))) {
      const txt = m[1].trim();
      if (txt && txt !== "(none yet)") result.insights.push({ text: txt, line: i + 1 });
    } else if (section === "log" && (m = line.match(/^\s*-\s*(.*)$/))) {
      const txt = m[1].trim();
      if (txt) result.log.push({ text: txt, line: i + 1 });
    }
  }
  return result;
}

// ─── List walker ─────────────────────────────────────────────────────────

function listFiles(rootDir, exts, maxDepth = 8, max = 500) {
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
      else if (entry.isFile() && exts.some((x) => entry.name.toLowerCase().endsWith(x))) {
        out.push({ path: full, name: entry.name, rel: path.relative(rootDir, full) });
      }
    }
  }
  walk(rootDir, 0);
  return out;
}

// ─── Receipt I/O ─────────────────────────────────────────────────────────

function receiptPath(witPath) { return witPath + ".receipt.json"; }
function readReceipt(witPath) {
  const p = receiptPath(witPath);
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return null; }
}

// ─── HTTP server ─────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (u.pathname === "/health") {
    return sendJson(res, 200, {
      ok: true, plugin: PLUGIN_ID, pid: process.pid,
      started_at: startedAt, uptime_seconds: Math.round(process.uptime()),
    });
  }

  if (u.pathname === "/api/info") {
    let witVersion = null;
    if (fs.existsSync(WIT)) {
      try {
        const pkg = path.join(VENV_DIR, "lib");
        const r = await new Promise((resolve) => {
          execFile(path.join(VENV_DIR, "bin", "python"), ["-c",
            "import importlib.metadata as m;\ntry:\n  print(m.version('wit-lang'))\nexcept Exception:\n  print(m.version('witsoc'))"
          ], { timeout: 5000 }, (err, stdout) => resolve(stdout || ""));
        });
        witVersion = (r || "").trim().split("\n")[0] || null;
      } catch (_) { witVersion = null; }
    }
    return sendJson(res, 200, {
      plugin: PLUGIN_ID, pid: process.pid, port: PORT,
      venv: VENV_DIR, wit: WIT, wit_version: witVersion,
      wit_available: fs.existsSync(WIT),
    });
  }

  if (u.pathname === "/api/list") {
    const dir = u.searchParams.get("dir");
    if (!dir) return sendJson(res, 400, { error: "dir_required" });
    if (!fs.existsSync(dir)) return sendJson(res, 404, { error: "dir_not_found", dir });
    const files = listFiles(dir, [".wit", ".soc"]);
    const wits = files.filter((f) => f.name.toLowerCase().endsWith(".wit"));
    const socs = files.filter((f) => f.name.toLowerCase().endsWith(".soc"));
    return sendJson(res, 200, { dir, wit_files: wits, soc_files: socs });
  }

  if (u.pathname === "/api/file") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (req.method === "GET") {
      try { return sendText(res, 200, fs.readFileSync(p, "utf8")); }
      catch (err) { return sendJson(res, 404, { error: "read_failed", message: err.message }); }
    }
    if (req.method === "PUT") {
      try {
        const body = await readBody(req);
        fs.mkdirSync(path.dirname(p), { recursive: true });
        fs.writeFileSync(p, body);
        return sendJson(res, 200, { ok: true, bytes: body.length });
      } catch (err) {
        return sendJson(res, 500, { error: "write_failed", message: err.message });
      }
    }
    return sendJson(res, 405, { error: "method_not_allowed" });
  }

  if (u.pathname === "/api/check") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (!fs.existsSync(WIT)) return sendJson(res, 503, { error: "wit_unavailable", message: "venv not provisioned; activate the plugin" });
    const r = await runWit(["check", p]);
    return sendJson(res, 200, r);
  }

  if (u.pathname === "/api/verify") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (!fs.existsSync(WIT)) return sendJson(res, 503, { error: "wit_unavailable" });
    const step = u.searchParams.get("step");
    const args = step ? ["verify", p, "--step", step] : ["verify", p];
    const r = await runWit(args);
    return sendJson(res, 200, r);
  }

  if (u.pathname === "/api/context") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (!fs.existsSync(WIT)) return sendJson(res, 503, { error: "wit_unavailable" });
    const r = await runWit(["context", p]);
    return sendJson(res, 200, r);
  }

  if (u.pathname === "/api/receipt") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (req.method === "GET") {
      return sendJson(res, 200, { receipt: readReceipt(p) });
    }
    if (req.method === "POST") {
      if (!fs.existsSync(WIT)) return sendJson(res, 503, { error: "wit_unavailable" });
      const body = await readBody(req);
      const r = await runWit(["receipt", p], body);
      return sendJson(res, 200, { ...r, receipt: readReceipt(p) });
    }
    return sendJson(res, 405, { error: "method_not_allowed" });
  }

  if (u.pathname === "/api/parse") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    try {
      const source = fs.readFileSync(p, "utf8");
      const parsed = parseWitText(source);
      return sendJson(res, 200, { path: p, parsed, receipt: readReceipt(p) });
    } catch (err) {
      return sendJson(res, 500, { error: "parse_failed", message: err.message });
    }
  }

  if (u.pathname === "/api/soc") {
    const p = u.searchParams.get("path");
    if (!p) return sendJson(res, 400, { error: "path_required" });
    if (req.method === "GET") {
      try {
        const source = fs.readFileSync(p, "utf8");
        return sendJson(res, 200, { path: p, parsed: parseSocText(source), source });
      } catch (err) { return sendJson(res, 404, { error: "read_failed", message: err.message }); }
    }
    if (req.method === "POST") {
      try {
        const body = await readBody(req);
        fs.writeFileSync(p, body);
        return sendJson(res, 200, { ok: true, bytes: body.length, parsed: parseSocText(body) });
      } catch (err) { return sendJson(res, 500, { error: "write_failed", message: err.message }); }
    }
    return sendJson(res, 405, { error: "method_not_allowed" });
  }

  sendJson(res, 404, { error: "not_found", path: u.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  process.stdout.write(`[witsoc] listening on 127.0.0.1:${server.address().port}, pid=${process.pid}\n`);
});

const shutdown = (signal) => {
  process.stdout.write(`[witsoc] received ${signal}, exiting\n`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT",  () => shutdown("SIGINT"));
