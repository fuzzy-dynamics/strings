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
import goal_structure as gs  # noqa: E402
import refute_deterministic as rd  # noqa: E402
import witcore  # noqa: E402


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
    "FAILED_ATTEMPT": "prover_search_gap",
    "OPEN": "missing_barrier_lemma",
    "GAP": "artifact_issue",
}


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import slug  # noqa: E402  -- shared substrate, was a local copy

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_nodes(run: Path, limit: int = 0) -> list[dict]:
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
        if str(n.get("status") or "").upper() in {"CHECKED", "VERIFIED", "VERIFIED_LEAN", "REJECTED"}:
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
    return nodes[:limit] if limit and limit > 0 else nodes


def run_prover(lean_statement: str, imports: str, search: bool, emit: Path | None, workers: int | None) -> dict:
    """R3: the prover runs IN-PROCESS (close_obligation.close_goal) — no per-node
    python spawn, shared module imports and Lean verification cache across the
    whole dispatch batch. Search budgets bound the work; any failure is an
    honest OBLIGATION_OPEN."""
    import close_obligation as co
    workers = witcore.local_prover_worker_count(workers)
    try:
        if emit:
            emit.parent.mkdir(parents=True, exist_ok=True)
        return co.close_goal(lean_statement, name="lovasz_node", imports=imports,
                             search=search, workers=workers, emit=emit)
    except Exception as exc:
        return {"label": "OBLIGATION_OPEN", "discharged": False, "_error": str(exc)}


def split_and_recombine(lean_statement: str, imports: str, search: bool, workers: int | None) -> dict | None:
    """GAP-GRANULARITY actuator: a node whose conclusion is a top-level
    conjunction is two (or more) obligations. Prove each conjunct separately,
    then recombine with the anonymous constructor — and kernel-re-check the
    COMBINED proof against the ORIGINAL statement, so nothing is trusted that
    the kernel did not see whole. Returns None when the statement is not
    conjunctive; a result dict (discharged or honest failure detail) otherwise."""
    workers = witcore.local_prover_worker_count(workers)
    subs = gs.conjunction_split(lean_statement)
    if not 2 <= len(subs) <= 4:
        return None
    sub_records: list[dict] = []
    for s in subs:
        r = run_prover(s, imports, search, None, workers)
        if not r.get("discharged"):
            return {"discharged": False, "split_attempted": True, "subgoals": subs,
                    "failed_conjunct": s, "failed_label": r.get("label")}
        sub_records.append(r)
    proofs = [str(r["proof"]) for r in sub_records]
    import close_obligation as co
    for cand in gs.recombination_candidates(subs, proofs):
        if witcore.lean_verify_cached(co.lean_source("lovasz_node", lean_statement, imports, cand), None).get("verified"):
            return {"discharged": True, "proof": cand, "label": "PROOF_DISCHARGED",
                    "split_recombined": True, "subgoals": subs, "sub_proofs": proofs,
                    "candidates_tried": sum(int(r.get("candidates_tried") or 0) for r in sub_records),
                    "search_nodes": sum(int(r.get("search_nodes") or 0) for r in sub_records)}
    return {"discharged": False, "split_attempted": True, "subgoals": subs,
            "sub_proofs": proofs, "recombination_failed": True}


def packet_for_node(node: dict, search: bool, emit_dir: Path | None, workers: int | None, session_id: str, run: Path) -> dict:
    workers = witcore.local_prover_worker_count(workers)
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
        bus_request = None
        try:
            import request_bus as rb
            manifest = load(run / "lovasz_run.json", {})
            payload = {
                "task": "formalize",
                "node_id": node_id,
                "statement": node["statement"] or node_id,
                "target": str(manifest.get("source_target_text") or manifest.get("target") or ""),
                "target_hash": target_hash,
                "instructions": (
                    "Return a BARE Lean PROPOSITION for this node only — a term of "
                    "type Prop, NOT a declaration. Reply shape: "
                    "{\"lean_statement\": \"...\", \"imports\": \"...\", "
                    "\"notes\": \"ambiguities or assumptions\"}. The statement must be "
                    "usable directly as `(fun h : <lean_statement> => h)`: do NOT wrap "
                    "it in `theorem`/`lemma`/`def`/`example`, name it, or append "
                    "`:= <proof>`; fold hypotheses into the Prop with `∀`/`→`. "
                    "GOOD: `∀ n : Nat, 0 < n → n - 1 < n`. BAD: `theorem foo : ... := by ...`. "
                    "Do not add axioms, sorry, or a proof. If ambiguous, choose the "
                    "smallest formalizable subcase and state the scope in notes."
                ),
            }
            bus_request = rb.emit(payload, role="formalize", priority=8, d=run / "bus")
        except Exception as exc:
            bus_request = {"status": "emit_failed", "error": str(exc)}
        return {
            **base,
            "status": "OPEN",
            "granularity": gs.granularity(None),
            "evidence": ["no lean_statement on this node; Prover cannot attempt it"],
            "failure_class": "theorem_precondition_gap",
            "next_mutation": "Explorer/Lovasz must formalize this node into a Lean goal before Prover dispatch.",
            "bus_formalize_request": bus_request,
        }

    gran = gs.granularity(str(lean_statement))
    emit = (emit_dir / f"{slug(node_id)}.lean") if emit_dir else None
    imports = str(node.get("lean_imports") or "")
    record = run_prover(str(lean_statement), imports, search, emit, workers)

    # Conjunctive node + direct miss -> prove each conjunct, recombine, and
    # kernel-re-check the combined proof against the ORIGINAL statement.
    split_info = None
    if not record.get("discharged") and gran["flag"] == "conjunctive":
        split_info = split_and_recombine(str(lean_statement), imports, search, workers)
        if split_info and split_info.get("discharged"):
            record = {**record, **split_info}
            if emit:
                import close_obligation as co
                emit.parent.mkdir(parents=True, exist_ok=True)
                emit.write_text(co.lean_source("lovasz_node", str(lean_statement), imports,
                                               str(record["proof"])), encoding="utf-8")
                record["lean_path"] = str(emit)

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
        "granularity": gran,
        "evidence": evidence,
        "artifacts": artifacts,
        "failure_class": FAILURE_CLASS_MAP.get(legal, "none"),
        "next_mutation": record.get("next_mutation") or (
            "SafeVerify/target-freeze to upgrade CHECKED->VERIFIED_LEAN" if legal == "CHECKED"
            else "mutate one axis: stronger invariant, premise search, or alternate encoding"),
        "prover_legal_status": legal,
    }
    if record.get("split_recombined"):
        packet["split_recombined"] = True
        packet["evidence"].append(f"split_subgoals={record.get('subgoals')}")
    elif split_info and split_info.get("split_attempted"):
        packet["split_attempted"] = True
        if split_info.get("failed_conjunct"):
            packet["evidence"].append(f"split_failed_on={split_info['failed_conjunct']}")
    if lean_path:
        packet["lean_path"] = lean_path
    return packet


def frozen_target_hash(run: Path) -> str | None:
    """The run's frozen target hash, for the deterministic skeptic's drift check.
    Absent (e.g. a standalone concept-generator dir) -> None -> drift not checked."""
    for fname, keys in (("lovasz_run.json", ("target_hash",)),
                        ("handoff_v1.json", ("target_hash", "frozen_target_hash"))):
        data = load(run / fname, {})
        if isinstance(data, dict):
            for k in keys:
                if data.get(k):
                    return str(data[k])
    return None


def apply_skeptic_gate(nodes: list[dict], packets: list[dict], frozen_hash: str | None) -> None:
    """Mechanical skeptic pass (was an LLM-discipline step in SKILL.md only):
    run refute_deterministic on every dispatched node+result. DEMOTE-ONLY —
    target drift / circularity / supplied counterexample -> REJECTED, unresolved
    citations -> GAP. Never upgrades anything."""
    for node, pkt in zip(nodes, packets):
        proof = next((e[len("proof="):] for e in pkt.get("evidence", [])
                      if isinstance(e, str) and e.startswith("proof=")), "")
        subject = {**node, "proof": proof, "evidence": pkt.get("evidence", [])}
        try:
            verdict = rd.refute(subject, frozen_hash, str(node.get("lean_imports") or ""))
        except Exception as exc:  # the gate must never block dispatch output
            pkt["skeptic_review"] = {"error": str(exc)}
            continue
        pkt["skeptic_review"] = {"refuted": verdict["refuted"],
                                 "demoted_status": verdict["demoted_status"],
                                 "refutations": verdict["refutations"]}
        if verdict["demoted_status"] == "REJECTED":
            pkt["status"] = "REJECTED"
            pkt["failure_class"] = "artifact_issue"
        elif verdict["demoted_status"] == "GAP" and pkt["status"] in ("VERIFIED_LEAN", "CHECKED"):
            pkt["status"] = "GAP"
            pkt["failure_class"] = "theorem_precondition_gap"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--search", action="store_true", help="Escalate to compound proof search per node.")
    ap.add_argument("--limit", type=int, default=0,
                    help="maximum DAG nodes to dispatch; 0 means all currently eligible nodes")
    ap.add_argument("--session-id", default="manual")
    ap.add_argument("--out", type=Path, default=None, help="Worker-results path (default <run_dir>/worker_results.json).")
    ap.add_argument("--emit-dir", type=Path, default=None, help="Directory to emit per-node Lean (default <run_dir>/prover_lean).")
    ap.add_argument("--workers", type=int, default=None,
                    help="local prover thread fanout, not Lovasz subagent fanout (default: WITSOC_PROVER_WORKERS or 4; capped at 10)")
    ap.add_argument("--record-library", action="store_true",
                    help="harvest kernel-verified nodes into the lemma library (cross-run compounding)")
    ap.add_argument("--library", type=Path, default=None, help="lemma library dir (default: global)")
    args = ap.parse_args()

    run = args.run_dir
    out = args.out or (run / "worker_results.json")
    emit_dir = args.emit_dir or (run / "prover_lean")

    nodes = collect_nodes(run, args.limit)
    workers = witcore.local_prover_worker_count(args.workers)
    packets = [packet_for_node(n, args.search, emit_dir, workers, args.session_id, run) for n in nodes]

    # Deterministic skeptic gate: drift / circularity / counterexample /
    # citation audit on every packet. Demote-only; results land in the packet.
    apply_skeptic_gate(nodes, packets, frozen_target_hash(run))

    # Phase E harvest: kernel-verified nodes compound into the lemma library.
    if args.record_library:
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
    import run_ledger
    run_ledger.auto_ingest(run)  # R1.5: the unified ledger stays fresh
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
