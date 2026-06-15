#!/usr/bin/env python3
"""R1 unified run ledger — `witsoc ledger`.

One `run.sqlite3` per run, the DAG NODE as the single entity. Historically a
run's state was scattered across ~15 JSON ledgers with the same fact stored in
several files and a fleet of validators checking cross-file consistency; here
worker results, gap feedback, blueprint obligations, and skeptic reviews are
records ATTACHED to nodes, and the consistency validators become queries.

Migration stance (references/core/architecture.md): in R1 the ledger is a
derived index — tools keep writing their JSON artifacts, `ingest` (idempotent
upserts) refreshes the database after any phase, and `export` regenerates the
legacy files so existing consumers keep working. Original records are kept
verbatim in `raw` columns, so nothing is lossy.

Commands:
  ingest <run>        read every legacy ledger into run.sqlite3
  status <run>        the single-pane view (phase, escalation, nodes, frontier,
                      gaps, claim) that used to require reading ten files
  nodes <run>         node-centric joined view: node + attempts + reviews +
                      gap + blueprint state in one record
  consistency <run>   the cross-ledger validators as queries (exit 1 on error)
  export <run>        regenerate legacy JSON ledgers from the database
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from status_vocab import ACCEPTED_STATUSES, ALL_STATUSES, alias

LEDGER_NAME = "run.sqlite3"
FAILED_ATTEMPT_STATUSES = {"FAILED_ATTEMPT", "OPEN", "GAP", "REJECTED"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS nodes (
  node_id TEXT PRIMARY KEY, statement TEXT, lean_statement TEXT, lean_imports TEXT,
  type TEXT, status TEXT, target_hash TEXT, dependencies TEXT, skeptic_review_id TEXT,
  mutation_applied TEXT, raw TEXT, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS attempts (
  node_id TEXT, kind TEXT, worker_id TEXT, status TEXT, proof TEXT,
  failure_class TEXT, next_mutation TEXT, raw TEXT, updated_at INTEGER,
  PRIMARY KEY (node_id, kind, worker_id));
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY, node_id TEXT, verdict TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS gaps (
  node_id TEXT PRIMARY KEY, gap_class TEXT, mutation_round INTEGER,
  proposed_mutation TEXT, failed_statement_sha TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS blueprint (
  node_id TEXT PRIMARY KEY, status TEXT, attempts INTEGER, proof TEXT,
  last_failure TEXT, blocked_on_gaps TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS theory_gaps (
  gap_id TEXT PRIMARY KEY, identifier TEXT, status TEXT, raw TEXT);
CREATE TABLE IF NOT EXISTS lemma_queue (statement TEXT PRIMARY KEY, raw TEXT);
CREATE TABLE IF NOT EXISTS failures (
  fid TEXT PRIMARY KEY, method TEXT, statement TEXT, blocker TEXT, raw TEXT);
"""


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def connect(run: Path) -> sqlite3.Connection:
    run.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(run / LEDGER_NAME)
    con.executescript(_SCHEMA)
    return con


def _set_meta(con: sqlite3.Connection, key: str, value: Any) -> None:
    if value is None:
        return
    con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)))


def _meta(con: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


# --- ingest --------------------------------------------------------------------
def ingest(run: Path) -> dict:
    con = connect(run)
    now = int(time.time())
    counts: dict[str, int] = {}

    manifest = load(run / "lovasz_run.json", {})
    if isinstance(manifest, dict):
        _set_meta(con, "phase", manifest.get("phase"))
        _set_meta(con, "target_hash", manifest.get("target_hash"))
        _set_meta(con, "target", manifest.get("source_target_text"))
        _set_meta(con, "campaign", manifest.get("campaign"))

    dag = load(run / "proof_dependency_dag.json", [])
    for i, n in enumerate(x for x in (dag if isinstance(dag, list) else []) if isinstance(x, dict)):
        nid = str(n.get("node_id") or n.get("id") or f"node{i}")
        con.execute(
            "INSERT OR REPLACE INTO nodes (node_id, statement, lean_statement, lean_imports,"
            " type, status, target_hash, dependencies, skeptic_review_id, mutation_applied,"
            " raw, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (nid, str(n.get("statement") or ""), n.get("lean_statement"),
             str(n.get("lean_imports") or ""), str(n.get("type") or "lemma"),
             str(n.get("status") or "OPEN"), str(n.get("target_hash") or ""),
             json.dumps([str(d) for d in (n.get("dependencies") or [])]),
             str(n.get("skeptic_review_id") or "") or None,
             str(n.get("mutation_applied") or "") or None,
             json.dumps(n, ensure_ascii=False), now))
        counts["nodes"] = counts.get("nodes", 0) + 1

    workers = load(run / "worker_results.json", [])
    for w in (x for x in (workers if isinstance(workers, list) else []) if isinstance(x, dict)):
        con.execute(
            "INSERT OR REPLACE INTO attempts (node_id, kind, worker_id, status, proof,"
            " failure_class, next_mutation, raw, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(w.get("node_id") or ""), str(w.get("worker_type") or "WORKER"),
             str(w.get("worker_id") or "anonymous"), str(w.get("status") or ""),
             next((e[len("proof="):] for e in (w.get("evidence") or [])
                   if isinstance(e, str) and e.startswith("proof=")), None),
             str(w.get("failure_class") or ""), str(w.get("next_mutation") or ""),
             json.dumps(w, ensure_ascii=False), now))
        counts["attempts"] = counts.get("attempts", 0) + 1

    reviews = load(run / "skeptic_reviews.json", [])
    for r in (x for x in (reviews if isinstance(reviews, list) else []) if isinstance(x, dict)):
        if not r.get("review_id"):
            continue
        con.execute("INSERT OR REPLACE INTO reviews (review_id, node_id, verdict, raw) VALUES (?,?,?,?)",
                    (str(r["review_id"]), str(r.get("node_id") or "") or None,
                     str(r.get("verdict") or ""), json.dumps(r, ensure_ascii=False)))
        counts["reviews"] = counts.get("reviews", 0) + 1

    feedback = load(run / "gap_feedback.json", {})
    for nid, g in (feedback.get("nodes", {}) if isinstance(feedback, dict) else {}).items():
        if not isinstance(g, dict):
            continue
        con.execute("INSERT OR REPLACE INTO gaps (node_id, gap_class, mutation_round,"
                    " proposed_mutation, failed_statement_sha, raw) VALUES (?,?,?,?,?,?)",
                    (str(nid), str(g.get("gap_class") or ""), int(g.get("mutation_round") or 0),
                     str(g.get("proposed_mutation") or ""), str(g.get("failed_statement_sha") or ""),
                     json.dumps(g, ensure_ascii=False)))
        counts["gaps"] = counts.get("gaps", 0) + 1

    bp = load(run / "blueprint.json", {})
    if isinstance(bp, dict):
        for nid, ob in (bp.get("obligations") or {}).items():
            if not isinstance(ob, dict):
                continue
            con.execute("INSERT OR REPLACE INTO blueprint (node_id, status, attempts, proof,"
                        " last_failure, blocked_on_gaps, raw) VALUES (?,?,?,?,?,?,?)",
                        (str(nid), str(ob.get("status") or ""), int(ob.get("attempts") or 0),
                         ob.get("proof"), ob.get("last_failure"),
                         json.dumps(ob.get("blocked_on_gaps") or []),
                         json.dumps(ob, ensure_ascii=False)))
            counts["blueprint"] = counts.get("blueprint", 0) + 1
        for gid, gap in (bp.get("theory_gaps") or {}).items():
            if not isinstance(gap, dict):
                continue
            con.execute("INSERT OR REPLACE INTO theory_gaps (gap_id, identifier, status, raw)"
                        " VALUES (?,?,?,?)",
                        (str(gid), str(gap.get("identifier") or ""), str(gap.get("status") or ""),
                         json.dumps(gap, ensure_ascii=False)))
            counts["theory_gaps"] = counts.get("theory_gaps", 0) + 1

    queue = load(run / "actual_lemma_queue.json", [])
    for l in (x for x in (queue if isinstance(queue, list) else []) if isinstance(x, dict)):
        if l.get("statement"):
            con.execute("INSERT OR REPLACE INTO lemma_queue (statement, raw) VALUES (?,?)",
                        (str(l["statement"]), json.dumps(l, ensure_ascii=False)))
            counts["lemma_queue"] = counts.get("lemma_queue", 0) + 1

    soc = run / "lovasz.soc"
    if soc.exists():
        try:
            from lovasz_soc_memory import parse_failed_entries
            for f in parse_failed_entries(soc.read_text(encoding="utf-8")):
                if not f.get("id"):
                    continue
                con.execute("INSERT OR REPLACE INTO failures (fid, method, statement, blocker, raw)"
                            " VALUES (?,?,?,?,?)",
                            (str(f["id"]), str(f.get("method") or ""), str(f.get("statement") or ""),
                             str(f.get("blocker") or ""), json.dumps(f, ensure_ascii=False)))
                counts["failures"] = counts.get("failures", 0) + 1
        except Exception:
            pass

    claim = load(run / "solve_claim.json", None)
    if isinstance(claim, dict):
        _set_meta(con, "solve_claim", claim)
        counts["solve_claim"] = 1
    audit = load(run / "mathematical_solve_audit.json", None)
    if isinstance(audit, dict):
        _set_meta(con, "math_solve_audit", {"verdict": audit.get("verdict"),
                                            "failures": len(audit.get("failures", []))})

    con.commit()
    con.close()
    return {"schema": "witsoc.run_ledger.ingest.v1", "run_dir": str(run),
            "ledger": str(run / LEDGER_NAME), "ingested": counts}


# --- views ----------------------------------------------------------------------
def node_view(run: Path) -> list[dict]:
    con = connect(run)
    out = []
    for row in con.execute("SELECT node_id, statement, lean_statement, type, status,"
                           " dependencies, skeptic_review_id, mutation_applied FROM nodes"):
        nid = row[0]
        attempts = [{"kind": k, "worker_id": w, "status": s, "failure_class": f}
                    for k, w, s, f in con.execute(
                        "SELECT kind, worker_id, status, failure_class FROM attempts"
                        " WHERE node_id = ?", (nid,))]
        reviews = [r[0] for r in con.execute(
            "SELECT review_id FROM reviews WHERE node_id = ? AND verdict = 'pass'", (nid,))]
        gap = con.execute("SELECT gap_class, mutation_round, proposed_mutation FROM gaps"
                          " WHERE node_id = ?", (nid,)).fetchone()
        bp = con.execute("SELECT status, attempts, proof FROM blueprint WHERE node_id = ?",
                         (nid,)).fetchone()
        out.append({
            "node_id": nid, "statement": row[1], "lean_statement": row[2], "type": row[3],
            "status": row[4], "dependencies": json.loads(row[5] or "[]"),
            "skeptic_review_id": row[6], "mutation_applied": row[7],
            "attempts": attempts, "passing_reviews": reviews,
            "gap": ({"gap_class": gap[0], "mutation_round": gap[1], "proposed_mutation": gap[2]}
                    if gap else None),
            "blueprint": ({"status": bp[0], "attempts": bp[1], "proof": bp[2]} if bp else None),
        })
    con.close()
    return out


def status_summary(run: Path) -> dict:
    con = connect(run)
    by_status = dict(con.execute("SELECT status, COUNT(*) FROM nodes GROUP BY status"))
    bp_status = dict(con.execute("SELECT status, COUNT(*) FROM blueprint GROUP BY status"))
    campaign = _meta(con, "campaign", {}) or {}
    claim = _meta(con, "solve_claim")
    summary = {
        "schema": "witsoc.run_ledger.status.v1",
        "run_dir": str(run),
        "phase": _meta(con, "phase"),
        "target_hash": _meta(con, "target_hash"),
        "escalation_level": campaign.get("escalation_level"),
        "nodes_by_status": by_status,
        "blueprint_by_status": bp_status,
        "ready_frontier": [r[0] for r in con.execute(
            "SELECT node_id FROM blueprint WHERE status = 'READY'")],
        "open_gaps": con.execute("SELECT COUNT(*) FROM gaps").fetchone()[0],
        "attempts": con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0],
        "recorded_failures": con.execute("SELECT COUNT(*) FROM failures").fetchone()[0],
        "solve_claim": (claim or {}).get("status") if claim else None,
        "math_solve_audit": _meta(con, "math_solve_audit"),
    }
    con.close()
    return summary


# --- consistency: the cross-ledger validators as queries -------------------------
def consistency(run: Path) -> dict:
    con = connect(run)
    errors: list[str] = []
    nodes = {nid: {"status": status, "deps": json.loads(deps or "[]"), "review": review}
             for nid, status, deps, review in con.execute(
                 "SELECT node_id, status, dependencies, skeptic_review_id FROM nodes")}
    review_ids = {r[0] for r in con.execute("SELECT review_id FROM reviews")}

    for nid, n in nodes.items():
        status = alias(n["status"])
        if alias(n["status"]) not in ALL_STATUSES and n["status"] not in ALL_STATUSES:
            errors.append(f"node {nid!r}: status {n['status']!r} is not in the vocabulary")
        if status in ACCEPTED_STATUSES:
            if not n["review"]:
                errors.append(f"accepted node {nid!r} has no skeptic_review_id")
            elif n["review"] not in review_ids:
                errors.append(f"accepted node {nid!r} references unknown review {n['review']!r}")
            for dep in n["deps"]:
                if dep not in nodes:
                    errors.append(f"accepted node {nid!r} depends on unknown node {dep!r}")
                elif alias(nodes[dep]["status"]) not in ACCEPTED_STATUSES:
                    errors.append(f"accepted node {nid!r} depends on non-accepted node {dep!r} "
                                  f"(status {nodes[dep]['status']!r})")

    # cycle check over dependencies
    state: dict[str, int] = {}

    def visit(nid: str) -> bool:
        if state.get(nid) == 1:
            return True
        if state.get(nid) == 2:
            return False
        state[nid] = 1
        for dep in nodes.get(nid, {}).get("deps", []):
            if dep in nodes and visit(dep):
                return True
        state[nid] = 2
        return False

    if any(visit(nid) for nid in nodes):
        errors.append("dependency cycle among nodes")

    # a failed latest attempt requires gap feedback (the L1 contract)
    gap_nodes = {r[0] for r in con.execute("SELECT node_id FROM gaps")}
    for nid, status in con.execute(
            "SELECT node_id, status FROM attempts WHERE rowid IN"
            " (SELECT MAX(rowid) FROM attempts GROUP BY node_id)"):
        if status in FAILED_ATTEMPT_STATUSES and nid in nodes and nid not in gap_nodes:
            errors.append(f"node {nid!r} has a failed latest attempt but no gap_feedback record "
                          "(run `witsoc gap-feedback` after the worker batch)")

    # blueprint integrity: VERIFIED requires a proof
    for nid, proof in con.execute("SELECT node_id, proof FROM blueprint WHERE status = 'VERIFIED'"):
        if not proof:
            errors.append(f"blueprint obligation {nid!r} is VERIFIED without a recorded proof")

    con.close()
    return {"schema": "witsoc.run_ledger.consistency.v1", "run_dir": str(run),
            "valid": not errors, "errors": errors,
            "note": "cross-ledger validators expressed as queries over the unified ledger"}


# --- export: regenerate legacy ledgers for current consumers ---------------------
def export(run: Path) -> dict:
    con = connect(run)
    written = []

    dag = []
    for (raw, status, review, mutation) in con.execute(
            "SELECT raw, status, skeptic_review_id, mutation_applied FROM nodes"):
        node = json.loads(raw)
        node["status"] = status
        if review:
            node["skeptic_review_id"] = review
        if mutation:
            node["mutation_applied"] = mutation
        dag.append(node)
    if dag:
        (run / "proof_dependency_dag.json").write_text(
            json.dumps(dag, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append("proof_dependency_dag.json")

    workers = [json.loads(r[0]) for r in con.execute("SELECT raw FROM attempts")]
    if workers:
        (run / "worker_results.json").write_text(
            json.dumps(workers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append("worker_results.json")

    reviews = [json.loads(r[0]) for r in con.execute("SELECT raw FROM reviews")]
    if reviews:
        (run / "skeptic_reviews.json").write_text(
            json.dumps(reviews, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append("skeptic_reviews.json")

    bp_rows = list(con.execute("SELECT node_id, raw FROM blueprint"))
    if bp_rows:
        bp = {"schema": "witsoc.blueprint.v1", "run_dir": str(run),
              "target_hash": _meta(con, "target_hash") or "",
              "obligations": {nid: json.loads(raw) for nid, raw in bp_rows},
              "theory_gaps": {gid: json.loads(raw) for gid, raw in
                              con.execute("SELECT gap_id, raw FROM theory_gaps")},
              "note": "exported from run.sqlite3 (run_ledger export)"}
        (run / "blueprint.json").write_text(
            json.dumps(bp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append("blueprint.json")

    con.close()
    return {"schema": "witsoc.run_ledger.export.v1", "run_dir": str(run), "written": written}


def auto_ingest(run: Path) -> None:
    """R1.5 hook: writers call this after writing their JSON artifacts so the
    ledger is always fresh without the agent remembering. Guarded — a ledger
    failure must never block the tool that did the real work."""
    try:
        ingest(Path(run))
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("ingest", "status", "nodes", "consistency", "export"):
        p = sub.add_parser(name)
        p.add_argument("run_dir", type=Path)
    args = ap.parse_args()

    if args.cmd == "ingest":
        result: Any = ingest(args.run_dir)
    elif args.cmd == "status":
        result = status_summary(args.run_dir)
    elif args.cmd == "nodes":
        result = {"nodes": node_view(args.run_dir)}
    elif args.cmd == "consistency":
        result = consistency(args.run_dir)
    else:
        result = export(args.run_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("valid", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
