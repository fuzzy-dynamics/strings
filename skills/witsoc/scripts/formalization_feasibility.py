#!/usr/bin/env python3
"""Score whether a Witsoc/Lovasz target is ready for WIT/Lean formalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


GOOD_STATUS = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}
BAD_STATUS = {"CONJECTURE", "FAILED_ATTEMPT", "GAP", "OPEN", "REJECTED"}
FORMAL_YES = {"lean", "mathlib", "wit", "available", "formalized", "yes"}
FORMAL_PARTIAL = {"partial", "nearby", "needs_adapter", "needs_local_definitions"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def text_blob(run: Path) -> str:
    pieces: list[str] = []
    for name in ("research.md", "claims.md", "barriers.md", "verification.md", "sources.md"):
        path = run / name
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(pieces).lower()


def formal_status_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in FORMAL_YES:
        return "yes"
    if text in FORMAL_PARTIAL:
        return "partial"
    if any(token in text for token in FORMAL_YES):
        return "yes"
    if any(token in text for token in FORMAL_PARTIAL):
        return "partial"
    return "unknown"


def score_run(run: Path) -> dict:
    handoff = load(run / "handoff_v1.json", {})
    dag = records(run / "proof_dependency_dag.json")
    lemmas = records(run / "actual_lemma_queue.json")
    audit = records(run / "theorem_precondition_audit.json")
    workers = records(run / "worker_results.json")
    products = records(run / "product_selection.json")
    artifacts = load(run / "generator_artifacts.json", {}).get("artifacts", [])
    blob = text_blob(run)

    score = 35
    reasons: list[str] = []
    blockers: list[str] = []

    target = handoff.get("frozen_target") or handoff.get("target") or handoff.get("statement")
    if target or dag:
        score += 8
        reasons.append("frozen target or proof DAG present")
    else:
        score -= 18
        blockers.append("missing frozen target/proof DAG")

    definition_terms = ("definition", "def ", "structure", "predicate", "notation", "hypothesis")
    if any(term in blob for term in definition_terms) or handoff.get("definitions"):
        score += 10
        reasons.append("definitions or local predicates are recorded")
    else:
        score -= 12
        blockers.append("definitions are not explicit enough for formalization")

    if dag:
        accepted = [n for n in dag if str(n.get("status") or "").upper() in GOOD_STATUS]
        open_nodes = [n for n in dag if str(n.get("status") or "").upper() in BAD_STATUS]
        score += min(16, 4 * len(accepted))
        if open_nodes:
            score -= min(20, 4 * len(open_nodes))
            blockers.append(f"{len(open_nodes)} DAG node(s) remain conjectural/open/failed")
        if len(dag) > 12:
            score -= min(12, len(dag) - 12)
            reasons.append("large proof DAG increases formalization risk")

    formal_yes = 0
    formal_partial = 0
    missing_preconditions = 0
    for item in audit:
        status = formal_status_value(item.get("formal_availability"))
        if status == "yes":
            formal_yes += 1
        elif status == "partial":
            formal_partial += 1
        missing = item.get("missing_preconditions")
        if missing not in (None, "", []):
            missing_preconditions += 1
    score += min(18, 6 * formal_yes + 3 * formal_partial)
    if audit and not formal_yes and not formal_partial:
        score -= 15
        blockers.append("theorem audit has no Lean/mathlib/WIT availability")
    if missing_preconditions:
        score -= min(18, 6 * missing_preconditions)
        blockers.append(f"{missing_preconditions} theorem audit item(s) have missing preconditions")

    verified_workers = [w for w in workers if str(w.get("status") or "").upper() in {"VERIFIED", "CHECKED"}]
    if verified_workers:
        score += min(12, 4 * len(verified_workers))
        reasons.append("verified/check worker evidence exists")
    elif workers:
        score -= 8
        blockers.append("worker results exist but none are verified/check status")

    artifact_types = {str(a.get("type") or "").lower() for a in artifacts if isinstance(a, dict)}
    if {"wit", "lean"} & artifact_types:
        score += 10
        reasons.append("formal artifacts already exist")
    elif products:
        score += 4
        reasons.append("research product selected for downstream artifacting")

    if lemmas:
        exact_subcases = [x for x in lemmas if x.get("smallest_formalizable_subcase")]
        score += min(10, 3 * len(exact_subcases))
        unresolved = [x for x in lemmas if str(x.get("status") or "").upper() in BAD_STATUS]
        if unresolved:
            score -= min(12, 3 * len(unresolved))

    score = max(0, min(100, score))
    if score >= 78 and not blockers:
        label = "FORMALIZATION_READY"
        recommendation = "lean"
    elif score >= 62:
        label = "NEEDS_LOCAL_DEFINITIONS"
        recommendation = "wit_then_lean"
    elif score >= 45:
        label = "NEEDS_MATHLIB_THEOREM_SEARCH"
        recommendation = "explorer_repair"
    else:
        label = "POOR_FORMALIZATION_TARGET"
        recommendation = "wit_only_or_lovasz_redecompose"

    return {
        "schema": "witsoc.formalization_feasibility.v1",
        "run_dir": str(run),
        "score": score,
        "label": label,
        "recommendation": recommendation,
        "counts": {
            "dag_nodes": len(dag),
            "actual_lemmas": len(lemmas),
            "theorem_audit_items": len(audit),
            "formal_available": formal_yes,
            "formal_partial": formal_partial,
            "worker_results": len(workers),
            "verified_or_checked_workers": len(verified_workers),
        },
        "reasons": reasons,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = score_run(args.run_dir)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
