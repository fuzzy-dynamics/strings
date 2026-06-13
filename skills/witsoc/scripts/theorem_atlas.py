#!/usr/bin/env python3
"""Witsoc REFERENCE knowledge store (Part 1 of the two-part DB) — `witsoc atlas`.

The knowledge the system carries splits into two stores with opposite contracts
(see references/knowledge-stores.md):

  Part 1 (THIS TOOL)  reference atlas — common, curated theorems. Read-only to
                      runs, merged from several sources, indexed in SQLite so
                      any agent can query it fast without parsing 6MB of JSON.
  Part 2              live library — `lemma_library.py` / `witsoc library` at
                      witcore.global_library(). Deep runs harvest into it.

Reference sources, in priority order (first definition of a module wins):
  1. env WITSOC_ATLAS                 explicit single-file override (prover-compat)
  2. scripts/core_lemma_atlas.json    bundled curated core lemmas
  3. <reference_dir>/*.json           e.g. promoted_lemma_atlas.json, a Mathlib
                                      atlas dropped in by build_mathlib_atlas
  4. ~/.witsoc/mathlib_atlas.json     legacy location (back-compat read)

The SQLite index (<reference_dir>/atlas_index.sqlite3) stores every node with a
precomputed PageRank and an inverted token table; it is rebuilt automatically
whenever any source file changes (content fingerprint), so `search` is always
consistent with the JSON sources of truth.

The ONLY write path into the reference store is `promote`: it copies lemmas from
the live library whose trust tier is LEAN_VERIFIED (kernel receipt — never a
lower tier) into <reference_dir>/promoted_lemma_atlas.json, idempotently keyed
by statement hash. Curation is explicit; harvest never lands here on its own.

Subcommands:
  search   --query Q [--signature S] [--limit N]
  get      --module M
  stats
  paths
  reindex
  export   --out FILE.json        merged atlas usable as WITSOC_ATLAS by the prover
  promote  [--library DIR] [--limit N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import mathlib_atlas as ma  # noqa: E402  -- shared retrieval scoring
import witcore  # noqa: E402

INDEX_NAME = "atlas_index.sqlite3"
PROMOTED_NAME = "promoted_lemma_atlas.json"
# Bound the number of token-prefiltered candidates scored per query.
MAX_CANDIDATES = 4000


# --- sources -----------------------------------------------------------------
def reference_sources() -> list[Path]:
    """Existing atlas JSON files, highest priority first. Module-name collisions
    are resolved in this order (first wins)."""
    import os
    out: list[Path] = []
    env = os.environ.get("WITSOC_ATLAS")
    if env and Path(env).exists():
        out.append(Path(env).resolve())
    bundled = SCRIPT_DIR / "core_lemma_atlas.json"
    if bundled.exists():
        out.append(bundled.resolve())
    ref = witcore.reference_dir()
    if ref.is_dir():
        out.extend(sorted(p.resolve() for p in ref.glob("*.json")))
    legacy = witcore.witsoc_home() / "mathlib_atlas.json"
    if legacy.exists():
        out.append(legacy.resolve())
    seen: set[Path] = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def fingerprint(sources: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sources:
        st = p.stat()
        h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}\n".encode("utf-8"))
    return h.hexdigest()


def index_path() -> Path:
    return witcore.reference_dir() / INDEX_NAME


# --- index -------------------------------------------------------------------
def _pagerank_fast(nodes: list[dict[str, Any]], iterations: int = 30, damping: float = 0.85) -> dict[str, float]:
    """Same fixed-point as mathlib_atlas.pagerank, but dangling nodes (which it
    models as linking to ALL modules) are handled analytically — one shared
    dangling-mass term per iteration instead of an O(N) fan-out per dangling
    node. O(E+N) per iteration; on the 8k-node Mathlib atlas this is the
    difference between minutes and milliseconds of index build."""
    modules = [str(n.get("module", "")) for n in nodes if n.get("module")]
    if not modules:
        return {}
    module_set = set(modules)
    outgoing: dict[str, set[str]] = {}
    for node in nodes:
        module = str(node.get("module", ""))
        outs = {str(i) for i in node.get("imports", []) or [] if str(i) in module_set}
        if outs:
            outgoing[module] = outs
    n = len(modules)
    rank = {m: 1.0 / n for m in modules}
    for _ in range(iterations):
        dangling = sum(rank[m] for m in modules if m not in outgoing)
        base = (1.0 - damping) / n + damping * dangling / n
        new_rank = {m: base for m in modules}
        for module, targets in outgoing.items():
            share = damping * rank[module] / len(targets)
            for target in targets:
                new_rank[target] += share
        rank = new_rank
    return rank


def _load_nodes(path: Path) -> list[dict[str, Any]]:
    data = witcore.load_json(path, {})
    nodes = data.get("nodes", []) if isinstance(data, dict) else data
    return [n for n in nodes if isinstance(n, dict) and n.get("module")] if isinstance(nodes, list) else []


def build_index(sources: list[Path]) -> sqlite3.Connection:
    """Compile the JSON sources into the SQLite index: deduped nodes with
    precomputed PageRank plus an inverted token table for fast prefiltering."""
    ipath = index_path()
    ipath.parent.mkdir(parents=True, exist_ok=True)
    tmp = ipath.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    conn.executescript(
        """CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
           CREATE TABLE nodes (
               id INTEGER PRIMARY KEY,
               module TEXT UNIQUE NOT NULL,
               doc TEXT,
               symbols TEXT NOT NULL,
               imports TEXT NOT NULL,
               extra TEXT NOT NULL,
               source TEXT NOT NULL,
               pagerank REAL NOT NULL
           );
           CREATE TABLE tokens (token TEXT NOT NULL, node_id INTEGER NOT NULL);
           CREATE INDEX idx_tokens ON tokens (token);"""
    )
    merged: dict[str, tuple[dict[str, Any], str]] = {}
    for src in sources:
        for node in _load_nodes(src):
            module = str(node["module"])
            if module not in merged:  # first (highest-priority) source wins
                merged[module] = (node, str(src))
    nodes = [n for n, _ in merged.values()]
    rank = _pagerank_fast(nodes) if nodes else {}
    for node, src in merged.values():
        module = str(node["module"])
        core_keys = {"module", "doc", "symbols", "imports"}
        extra = {k: v for k, v in node.items() if k not in core_keys}
        cur = conn.execute(
            "INSERT INTO nodes (module, doc, symbols, imports, extra, source, pagerank) VALUES (?,?,?,?,?,?,?)",
            (module, str(node.get("doc", "")), json.dumps(node.get("symbols", []) or [], ensure_ascii=False),
             json.dumps(node.get("imports", []) or [], ensure_ascii=False),
             json.dumps(extra, ensure_ascii=False), src, rank.get(module, 0.0)),
        )
        nid = cur.lastrowid
        conn.executemany("INSERT INTO tokens (token, node_id) VALUES (?,?)",
                         [(t, nid) for t in set(ma.tokens(ma.node_text(node)))])
    conn.execute("INSERT INTO meta (key, value) VALUES ('fingerprint', ?)", (fingerprint(sources),))
    conn.execute("INSERT INTO meta (key, value) VALUES ('built_at', ?)", (str(time.time()),))
    conn.commit()
    conn.close()
    tmp.replace(ipath)
    return sqlite3.connect(ipath)


def ensure_index() -> tuple[sqlite3.Connection, bool, list[Path]]:
    """Open the index, rebuilding it when any source changed. Returns
    (connection, rebuilt, sources)."""
    sources = reference_sources()
    ipath = index_path()
    want = fingerprint(sources)
    if ipath.exists():
        try:
            conn = sqlite3.connect(ipath)
            row = conn.execute("SELECT value FROM meta WHERE key='fingerprint'").fetchone()
            if row and row[0] == want:
                return conn, False, sources
            conn.close()
        except sqlite3.Error:
            pass
    return build_index(sources), True, sources


def _row_node(row: tuple) -> dict[str, Any]:
    module, doc, symbols, imports, extra, source, pr = row
    node = {"module": module, "doc": doc, "symbols": json.loads(symbols),
            "imports": json.loads(imports), **json.loads(extra)}
    return {"node": node, "source": source, "pagerank": pr}


NODE_COLS = "module, doc, symbols, imports, extra, source, pagerank"


# --- commands ------------------------------------------------------------------
def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    conn, rebuilt, _ = ensure_index()
    qtext = f"{args.query} {args.signature}"
    qtoks = sorted(set(ma.tokens(qtext)))
    if not qtoks:
        return {"status": "empty_query", "matches": [], "imports": []}
    placeholders = ",".join("?" for _ in qtoks)
    rows = conn.execute(
        f"""SELECT {NODE_COLS} FROM nodes WHERE id IN (
                SELECT node_id FROM tokens WHERE token IN ({placeholders})
                GROUP BY node_id ORDER BY COUNT(*) DESC LIMIT ?)""",
        (*qtoks, MAX_CANDIDATES)).fetchall()
    qvec = Counter(ma.tokens(qtext))
    qsyms = ma.query_symbols(args.query, args.signature)
    scored = []
    for row in rows:
        rec = _row_node(row)
        node = rec["node"]
        sim = ma.cosine(qvec, Counter(ma.tokens(ma.node_text(node))))
        symovl = ma.symbol_overlap(qsyms, node)
        score = 0.55 * symovl + 0.35 * sim + 0.10 * rec["pagerank"]
        scored.append((score, sim, symovl, rec))
    scored.sort(key=lambda x: (-x[0], str(x[3]["node"]["module"])))
    matches, imports, seen = [], [], set()
    for score, sim, symovl, rec in scored[: args.limit]:
        node = rec["node"]
        for mod in [node["module"], *node.get("imports", [])]:
            mod = str(mod)
            if mod not in seen:
                seen.add(mod)
                imports.append(mod)
        entry = {"module": node["module"], "score": round(score, 6), "similarity": round(sim, 6),
                 "pagerank": round(rec["pagerank"], 6), "symbol_overlap": round(symovl, 6),
                 "symbols": node.get("symbols", []), "imports": node.get("imports", []),
                 "source": rec["source"]}
        if node.get("statement"):
            entry["statement"] = node["statement"]
        matches.append(entry)
    return {"status": "ok", "reindexed": rebuilt, "matches": matches, "imports": imports}


def cmd_get(args: argparse.Namespace) -> dict[str, Any]:
    conn, _, _ = ensure_index()
    row = conn.execute(f"SELECT {NODE_COLS} FROM nodes WHERE module=?", (args.module,)).fetchone()
    if not row:
        return {"status": "not_found", "module": args.module}
    rec = _row_node(row)
    return {"status": "ok", "source": rec["source"], "pagerank": rec["pagerank"], **rec["node"]}


def cmd_stats(args: argparse.Namespace) -> dict[str, Any]:
    conn, rebuilt, sources = ensure_index()
    total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    by_source = dict(conn.execute("SELECT source, COUNT(*) FROM nodes GROUP BY source").fetchall())
    return {"total_nodes": total, "by_source": by_source, "reindexed": rebuilt,
            "index": str(index_path()), "sources": [str(s) for s in sources]}


def cmd_paths(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "reference_dir": str(witcore.reference_dir()),
        "reference_sources": [str(s) for s in reference_sources()],
        "index": str(index_path()),
        "promoted_atlas": str(witcore.reference_dir() / PROMOTED_NAME),
        "live_library": str(witcore.global_library()),
    }


def cmd_reindex(args: argparse.Namespace) -> dict[str, Any]:
    sources = reference_sources()
    conn = build_index(sources)
    total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    return {"status": "reindexed", "total_nodes": total,
            "index": str(index_path()), "sources": [str(s) for s in sources]}


def cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    """Merged single-file atlas, schema-compatible with WITSOC_ATLAS / the
    prover's default_atlas() — point a run at curated knowledge in one file."""
    conn, _, sources = ensure_index()
    rows = conn.execute(f"SELECT {NODE_COLS} FROM nodes ORDER BY module").fetchall()
    nodes = [_row_node(r)["node"] for r in rows]
    witcore.save_json(args.out, {"_comment": "merged witsoc reference atlas (theorem_atlas.py export)",
                                 "nodes": nodes})
    return {"status": "exported", "nodes": len(nodes), "out": str(args.out),
            "sources": [str(s) for s in sources]}


def cmd_promote(args: argparse.Namespace) -> dict[str, Any]:
    """The ONLY live->reference path: copy LEAN_VERIFIED (kernel receipt) lemmas
    from the live library into the promoted reference atlas. Idempotent by
    statement hash; lower trust tiers are structurally excluded."""
    library = args.library or witcore.global_library()
    db = Path(library) / "lemmas.db"
    if not db.exists():
        return {"status": "no_library", "library": str(library)}
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT id, statement, wit_path, lean_path, trust_tier, target_hash, provenance"
        " FROM lemmas WHERE trust_tier='LEAN_VERIFIED' ORDER BY id LIMIT ?", (args.limit,)).fetchall()
    out_path = witcore.reference_dir() / PROMOTED_NAME
    existing = witcore.load_json(out_path, {})
    nodes = existing.get("nodes", []) if isinstance(existing, dict) else []
    by_module = {n.get("module"): n for n in nodes if isinstance(n, dict)}
    promoted = []
    for lid, statement, wit_path, lean_path, tier, target_hash, provenance in rows:
        assert tier == "LEAN_VERIFIED", "promotion is restricted to kernel-verified lemmas"
        key = hashlib.sha256(statement.encode("utf-8")).hexdigest()[:16]
        module = f"library.{key}"
        if module in by_module:
            continue
        node = {
            "module": module,
            "doc": statement,
            "symbols": sorted(ma.query_symbols(statement)),
            "imports": [],
            "statement": statement,
            "trust_tier": tier,
            "library_id": lid,
            "target_hash": target_hash,
            "provenance": provenance,
            "wit_path": wit_path,
            "lean_path": lean_path,
        }
        by_module[module] = node
        promoted.append(module)
    if promoted:
        witcore.save_json(out_path, {
            "_comment": "kernel-verified lemmas promoted from the live library (witsoc atlas promote)",
            "nodes": sorted(by_module.values(), key=lambda n: str(n.get("module"))),
        })
    return {"status": "promoted", "new": len(promoted), "modules": promoted,
            "total_promoted": len(by_module), "out": str(out_path), "library": str(library)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--signature", default="")
    p_search.add_argument("--limit", type=int, default=5)

    p_get = sub.add_parser("get")
    p_get.add_argument("--module", required=True)

    sub.add_parser("stats")
    sub.add_parser("paths")
    sub.add_parser("reindex")

    p_exp = sub.add_parser("export")
    p_exp.add_argument("--out", type=Path, required=True)

    p_pro = sub.add_parser("promote")
    p_pro.add_argument("--library", type=Path, default=None,
                       help="Live library dir (default: witcore.global_library()).")
    p_pro.add_argument("--limit", type=int, default=10000)

    args = parser.parse_args()
    handlers = {"search": cmd_search, "get": cmd_get, "stats": cmd_stats, "paths": cmd_paths,
                "reindex": cmd_reindex, "export": cmd_export, "promote": cmd_promote}
    print(json.dumps(handlers[args.cmd](args), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
