#!/usr/bin/env python3
"""Phase C: dispatch the Prover (close_obligation.py) per proof-DAG node.

Lovasz decomposes a hard target into a proof-dependency DAG. This turns the
decomposition into actual kernel work: for every node that carries a formalizable
Lean goal (`lean_statement`), it runs the Prover, gates the result through the
PROVER_ATTEMPT honesty validator (validate_prover_result), and writes a
schema-conforming Lovasz worker-result packet (`FORMALIZER`). Nodes without a
formalized goal are recorded honestly as needing formalization first — never as
progress.

A kernel proof maps to `CHECKED` here (SafeVerify/target-freeze is a separate
gate that upgrades it to `VERIFIED_LEAN`); `OBLIGATION_OPEN` maps to
`OPEN`/`FAILED_ATTEMPT`; no toolchain maps to `GAP`. No node is ever marked above
the evidence the kernel actually produced.

Usage:
  lovasz_prover_dispatch.py <run_dir> [--search] [--limit N] [--session-id S]
      [--out worker_results.json] [--emit-dir DIR] [--workers N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import validate_prover_result as vpr  # noqa: E402


# Prover legal status -> Lovasz worker-result schema status.
STATUS_MAP = {
    "VERIFIED": "VERIFIED_LEAN",
    "CHECKED": "CHECKED",
    "FAILED_ATTEMPT": "FAILED_ATTEMPT",
    "OPEN": "OPEN",
    "GAP": "GAP",
}
FAILURE_CLASS_MAP = {
    "VERIFIED": "none",
    "CHECKED": "none",
    "FAILED_ATTEMPT": "genuine_mathematical_barrier",
    "OPEN": "missing_barrier_lemma",
    "GAP": "artifact_issue",
}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_+-]+", "-", text.strip()).strip("-").lower()
    return s or "node"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_nodes(run: Path, limit: int) -> list[dict]:
    """Merge proof-DAG nodes with actual-lemma-queue entries, preferring a
    `lean_statement` field wherever it appears."""
    dag = load(run / "proof_dependency_dag.json", [])
    lemmas = load(run / "actual_lemma_queue.json", [])
    lemma_lean = {}
    for l in lemmas if isinstance(lemmas, list) else []:
        if isinstance(l, dict) and l.get("statement"):
            lemma_lean[str(l["statement"])] = l
    nodes = []
    for n in (dag if isinstance(dag, list) else []):
        if not isinstance(n, dict):
            continue
        statement = str(n.get("statement") or n.get("exact_statement") or "")
        lemma = lemma_lean.get(statement, {})
        nodes.append({
            "node_id": str(n.get("node_id") or n.get("id") or slug(statement) or "node"),
            "statement": statement,
            "lean_statement": n.get("lean_statement") or lemma.get("lean_statement"),
            "lean_imports": n.get("lean_imports") or n.get("preamble") or lemma.get("lean_imports") or "",
            "target_hash": str(n.get("target_hash") or sha(statement or "node")),
            "dependency_path_to_target": n.get("dependency_path_to_target") or [],
        })
    return nodes[:limit]


def run_prover(lean_statement: str, imports: str, search: bool, emit: Path | None, workers: int) -> dict:
    cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
           "--lean-statement", lean_statement, "--name", "lovasz_node",
           "--out-ledger", "/dev/null", "--workers", str(workers)]
    if imports:
        cmd += ["--imports", imports]
    if search:
        cmd += ["--search"]
    if emit:
        emit.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["--emit", str(emit)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {"label": "OBLIGATION_OPEN", "discharged": False}
    except Exception as exc:
        return {"label": "OBLIGATION_OPEN", "discharged": False, "_error": str(exc)}


def packet_for_node(node: dict, search: bool, emit_dir: Path | None, workers: int, session_id: str, run: Path) -> dict:
    node_id = node["node_id"]
    target_hash = node["target_hash"]
    proof_worktree = str(run / "worktrees" / f"witsoc-proof-{session_id}-{slug(node_id)}")
    base = {
        "worker_id": f"prover-{slug(node_id)}",
        "worker_type": "FORMALIZER",
        "node_id": node_id,
        "claim": node["statement"] or node.get("lean_statement") or node_id,
        "target_hash": target_hash,
        "dependencies": node.get("dependency_path_to_target") or [],
        "artifacts": [],
        "session_id": session_id,
        "proof_worktree": proof_worktree,
    }

    lean_statement = node.get("lean_statement")
    if not lean_statement:
        # Honest: a node with no formalized goal is NOT progress.
        return {
            **base,
            "status": "OPEN",
            "evidence": ["no lean_statement on this node; Prover cannot attempt it"],
            "failure_class": "theorem_precondition_gap",
            "next_mutation": "Explorer/Lovasz must formalize this node into a Lean goal before Prover dispatch.",
        }

    emit = (emit_dir / f"{slug(node_id)}.lean") if emit_dir else None
    record = run_prover(str(lean_statement), str(node.get("lean_imports") or ""), search, emit, workers)

    # Cross-check the frozen node target against the statement the Prover proved.
    ns = argparse.Namespace(safeverify_passed=False, safeverify=None,
                            frozen_target_sha256=None, assert_status=None)
    record.setdefault("statement", str(lean_statement))
    legal, detail = vpr.legal_status(record, ns)

    proof = record.get("proof")
    evidence = [f"prover_label={record.get('label')}"]
    if proof:
        evidence.append(f"proof={proof}")
    evidence.append(f"search_nodes={record.get('search_nodes', 0)}")
    artifacts = []
    lean_path = record.get("lean_path") or (str(emit) if (emit and emit.exists()) else None)
    if lean_path:
        artifacts.append(lean_path)

    packet = {
        **base,
        "status": STATUS_MAP.get(legal, "OPEN"),
        "evidence": evidence,
        "artifacts": artifacts,
        "failure_class": FAILURE_CLASS_MAP.get(legal, "none"),
        "next_mutation": record.get("next_mutation") or (
            "SafeVerify/target-freeze to upgrade CHECKED->VERIFIED_LEAN" if legal == "CHECKED"
            else "mutate one axis: stronger invariant, premise search, or alternate encoding"),
        "prover_legal_status": legal,
    }
    if lean_path:
        packet["lean_path"] = lean_path
    return packet


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--search", action="store_true", help="Escalate to compound proof search per node.")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--session-id", default="manual")
    ap.add_argument("--out", type=Path, default=None, help="Worker-results path (default <run_dir>/worker_results.json).")
    ap.add_argument("--emit-dir", type=Path, default=None, help="Directory to emit per-node Lean (default <run_dir>/prover_lean).")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--record-library", action="store_true",
                    help="harvest kernel-verified nodes into the lemma library (cross-run compounding)")
    ap.add_argument("--library", type=Path, default=None, help="lemma library dir (default: global)")
    args = ap.parse_args()

    run = args.run_dir
    out = args.out or (run / "worker_results.json")
    emit_dir = args.emit_dir or (run / "prover_lean")

    nodes = collect_nodes(run, args.limit)
    packets = [packet_for_node(n, args.search, emit_dir, args.workers, args.session_id, run) for n in nodes]

    # Phase E harvest: kernel-verified nodes compound into the lemma library.
    if args.record_library:
        import witcore  # noqa: E402
        library = args.library if args.library is not None else witcore.global_library()
        tier_for = {"VERIFIED_LEAN": "LEAN_VERIFIED", "CHECKED": "WIT_STRUCTURE"}
        for node, pkt in zip(nodes, packets):
            tier = tier_for.get(pkt.get("status"))
            lean_stmt = node.get("lean_statement")
            if not tier or not lean_stmt:
                continue
            proof = next((e[len("proof="):] for e in pkt.get("evidence", []) if isinstance(e, str) and e.startswith("proof=")), "")
            add = [sys.executable, str(SCRIPT_DIR / "lemma_library.py"), "--library", str(library), "add",
                   "--statement", str(lean_stmt), "--tier", tier,
                   "--provenance", f"lovasz_prover_dispatch:{proof}" if proof else "lovasz_prover_dispatch",
                   "--target-hash", str(node.get("target_hash"))]
            if pkt.get("lean_path"):
                add += ["--lean", pkt["lean_path"]]
            try:
                subprocess.run(add, capture_output=True, text=True, timeout=30, check=False)
            except Exception:
                pass

    # Merge with any existing worker_results.json (a list), replacing same node_id
    # FORMALIZER results from a prior dispatch.
    existing = load(out, [])
    existing = existing if isinstance(existing, list) else []
    new_ids = {(p["node_id"], p["worker_type"]) for p in packets}
    merged = [w for w in existing if isinstance(w, dict) and (w.get("node_id"), w.get("worker_type")) not in new_ids]
    merged.extend(packets)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "schema": "witsoc.lovasz_prover_dispatch.v1",
        "run_dir": str(run),
        "dispatched": len(packets),
        "worker_results": str(out),
        "status_counts": {},
    }
    for p in packets:
        summary["status_counts"][p["status"]] = summary["status_counts"].get(p["status"], 0) + 1
    (run / "prover_dispatch.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
