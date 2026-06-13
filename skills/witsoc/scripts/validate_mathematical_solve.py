#!/usr/bin/env python3
"""F0 two-stage success rule, stage 1 — `witsoc validate-math-solve`.

A MATHEMATICAL_SOLVE is the informal-proof success stage for a frontier
target: the complete proof DAG composes to the frozen target with every node
closed and adversarially reviewed, before (and separately from) the
FORMAL_SOLVE stage (WIT + Lean + SafeVerify). Without this split, a correct
frontier proof would sit forever at PROVED_SKETCH because day-one full
formalization is unreachable; with it, a mathematical solve triggers a
formalization campaign as its own subsequent program.

This validator is the deterministic audit for MATHEMATICAL_SOLVE readiness.
It checks, on a Lovasz run directory:

  A. every DAG node is either STRONG (verified/checked/proved-sketch) or an
     explicitly dead route (FAILED_ATTEMPT/REJECTED/DEMOTED) — no OPEN, GAP,
     CONJECTURE, PARTIAL, or CONDITIONAL node remains;
  B. every STRONG node has evidence, a target hash, a skeptic_review_id, and
     a SKEPTIC FLEET: >= --min-skeptics independent reviews (distinct
     review_id, verdict pass, all four drift/assumption/circularity/weaker
     checks true) — one skeptic pass is not enough at frontier stakes;
  C. STRONG-node dependencies resolve only to STRONG nodes (no
     conjecture-as-dependency, no dependency on a dead route) and are acyclic;
  D. no STRONG node appears in gap_feedback.json (no unresolved worker gap);
  E. theorem_precondition_audit.json exists with no unresolved preconditions;
  F. disproof-first search ran (disproof_first.json nonempty);
  G. the run manifest carries the frozen target hash.

Verdict MATHEMATICAL_SOLVE_READY is a precondition for opening a solve claim
(solve_claim_protocol.py); it is NEVER itself a reportable solve.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from status_vocab import STRONG_STATUSES, alias

DEAD_ROUTE_STATUSES = {"FAILED_ATTEMPT", "REJECTED", "DEMOTED"}
SKEPTIC_CHECK_FIELDS = ("target_drift_checked", "hidden_assumptions_checked",
                        "circularity_checked", "weaker_target_checked")
UNRESOLVED_PRECONDITION = {"OPEN", "GAP", "MISSING", "UNRESOLVED"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def node_id_of(node: dict, index: int) -> str:
    return str(node.get("node_id") or node.get("id") or f"<index {index}>")


def fleet_reviews(reviews: list[dict], node_id: str) -> list[dict]:
    """Distinct passing fleet reviews for one node."""
    seen: set[str] = set()
    out = []
    for review in reviews:
        if str(review.get("node_id") or "") != node_id:
            continue
        rid = str(review.get("review_id") or "")
        if not rid or rid in seen:
            continue
        if review.get("verdict") != "pass":
            continue
        if not all(review.get(f) is True for f in SKEPTIC_CHECK_FIELDS):
            continue
        seen.add(rid)
        out.append(review)
    return out


def has_cycle(strong_ids: set[str], deps: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for dep in deps.get(node, []):
            if dep in strong_ids and visit(dep):
                return True
        state[node] = 2
        return False

    return any(visit(n) for n in strong_ids)


def audit(run: Path, min_skeptics: int) -> dict:
    failures: list[str] = []

    manifest = load(run / "lovasz_run.json", {})
    target_hash = str(manifest.get("target_hash") or "") if isinstance(manifest, dict) else ""
    if not target_hash:
        failures.append("lovasz_run.json missing frozen target_hash")

    dag = load(run / "proof_dependency_dag.json", [])
    dag = [n for n in dag if isinstance(n, dict)] if isinstance(dag, list) else []
    if not dag:
        failures.append("proof_dependency_dag.json missing or empty")

    reviews = load(run / "skeptic_reviews.json", [])
    reviews = [r for r in reviews if isinstance(r, dict)] if isinstance(reviews, list) else []

    strong: dict[str, dict] = {}
    for index, node in enumerate(dag):
        nid = node_id_of(node, index)
        status = alias(node.get("status"))
        if status in STRONG_STATUSES:
            strong[nid] = node
        elif status in DEAD_ROUTE_STATUSES:
            continue  # honest dead routes may remain, unreferenced
        else:
            failures.append(f"node {nid!r} not closed: status {node.get('status')!r} "
                            "(a mathematical solve leaves no OPEN/GAP/CONJECTURE/PARTIAL/CONDITIONAL node)")

    if dag and not strong:
        failures.append("no STRONG (verified/checked/proved-sketch) node in the DAG")

    deps: dict[str, list[str]] = {}
    for nid, node in strong.items():
        for field in ("evidence", "target_hash"):
            if node.get(field) in (None, "", []):
                failures.append(f"STRONG node {nid!r} missing {field}")
        if not node.get("skeptic_review_id"):
            failures.append(f"STRONG node {nid!r} missing skeptic_review_id")
        fleet = fleet_reviews(reviews, nid)
        if len(fleet) < min_skeptics:
            failures.append(f"STRONG node {nid!r} has {len(fleet)} passing fleet reviews; "
                            f"frontier acceptance requires >= {min_skeptics} independent skeptics")
        node_deps = [str(d) for d in (node.get("dependencies") or [])]
        deps[nid] = node_deps
        for dep in node_deps:
            if dep not in strong:
                failures.append(f"STRONG node {nid!r} depends on {dep!r}, which is not a STRONG node "
                                "(no conjecture-as-dependency, no dependency on a dead route)")

    if strong and has_cycle(set(strong), deps):
        failures.append("dependency cycle among STRONG nodes")

    gap_feedback = load(run / "gap_feedback.json", {})
    gap_nodes = gap_feedback.get("nodes", {}) if isinstance(gap_feedback, dict) else {}
    for nid in strong:
        if nid in gap_nodes:
            failures.append(f"STRONG node {nid!r} still has an unresolved entry in gap_feedback.json")

    precond = load(run / "theorem_precondition_audit.json", None)
    if precond is None:
        failures.append("theorem_precondition_audit.json missing (external theorem preconditions unaudited)")
    else:
        entries = precond if isinstance(precond, list) else precond.get("entries", []) if isinstance(precond, dict) else []
        for index, entry in enumerate(e for e in entries if isinstance(e, dict)):
            label = str(entry.get("theorem") or entry.get("id") or f"<index {index}>")
            if entry.get("missing_preconditions"):
                failures.append(f"theorem precondition audit: {label!r} has missing preconditions")
            if str(entry.get("status") or "").strip().upper() in UNRESOLVED_PRECONDITION:
                failures.append(f"theorem precondition audit: {label!r} unresolved (status {entry.get('status')!r})")

    disproof = load(run / "disproof_first.json", None)
    if not disproof:
        failures.append("disproof_first.json missing or empty (adversarial counterexample search did not run)")

    return {
        "schema": "witsoc.mathematical_solve_audit.v1",
        "run_dir": str(run),
        "target_hash": target_hash,
        "min_skeptics": min_skeptics,
        "counts": {"dag_nodes": len(dag), "strong_nodes": len(strong),
                   "skeptic_reviews": len(reviews)},
        "verdict": "MATHEMATICAL_SOLVE_READY" if not failures else "NOT_READY",
        "failures": failures,
        "note": ("MATHEMATICAL_SOLVE_READY is a precondition for solve_claim_protocol, never a "
                 "reportable solve; FORMAL_SOLVE (WIT + Lean + SafeVerify) remains a separate stage."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--min-skeptics", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = audit(args.run_dir, args.min_skeptics)
    out = args.out or (args.run_dir / "mathematical_solve_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "MATHEMATICAL_SOLVE_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
