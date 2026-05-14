"use strict";

// hello-world plugin server.
//
// Spawned by the plane-server's plugin lifecycle when the plugin is activated.
// Listens on $PORT (allocated by the plane), exposes /health for readiness
// probing and a tiny /api surface the iframe consumes via the plane proxy.

const http = require("http");
const os = require("os");

const PORT = parseInt(process.env.PORT || "0", 10);
const PLUGIN_ID = process.env.PLUGIN_ID || "hello-world";
const PLUGIN_DATA_DIR = process.env.PLUGIN_DATA_DIR || "<unset>";

const startedAt = new Date().toISOString();
let greetCount = 0;
const greetLog = [];

function sendJson(res, code, payload) {
  res.writeHead(code, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(payload));
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/health") {
    return sendJson(res, 200, {
      ok: true,
      plugin: PLUGIN_ID,
      pid: process.pid,
      started_at: startedAt,
      uptime_seconds: Math.round(process.uptime()),
    });
  }

  if (url.pathname === "/api/info") {
    return sendJson(res, 200, {
      plugin: PLUGIN_ID,
      pid: process.pid,
      port: PORT,
      hostname: os.hostname(),
      node: process.version,
      data_dir: PLUGIN_DATA_DIR,
      started_at: startedAt,
      uptime_seconds: Math.round(process.uptime()),
      greet_count: greetCount,
    });
  }

  if (url.pathname === "/api/greet") {
    const name = (url.searchParams.get("name") || "world").slice(0, 80);
    greetCount += 1;
    const entry = { ts: new Date().toISOString(), name, count: greetCount };
    greetLog.push(entry);
    while (greetLog.length > 10) greetLog.shift();
    return sendJson(res, 200, {
      greeting: `Hello, ${name}!`,
      ts: entry.ts,
      count: greetCount,
      recent: greetLog.slice(-5).reverse(),
    });
  }

  if (url.pathname === "/api/log") {
    return sendJson(res, 200, { entries: greetLog.slice().reverse() });
  }

  sendJson(res, 404, { error: "not_found", path: url.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  // Print on a single line so the supervisor can parse if it ever wants to.
  process.stdout.write(
    `[hello-world] listening on 127.0.0.1:${server.address().port}, pid=${process.pid}\n`,
  );
});

const shutdown = (signal) => {
  process.stdout.write(`[hello-world] received ${signal}, exiting\n`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
};
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
