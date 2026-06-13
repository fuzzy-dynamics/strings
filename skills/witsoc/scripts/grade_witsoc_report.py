#!/usr/bin/env python3
"""Assign a production-quality grade to a Witsoc/Lovasz research report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def substantive(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines())


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 68:
        return "C"
    if score >= 55:
        return "D"
    return "F"


# Status vocabularies for the PROGRESS score. A node is "closed" only with
# kernel/verifier-grade evidence; "partial" is informal-but-real; everything
# else is unclosed.
CLOSED_STATUSES = {"CHECKED", "VERIFIED", "LEAN_VERIFIED", "PROOF_DISCHARGED",
                   "RECEIPT_ACCEPTED"}
PARTIAL_STATUSES = {"PROVED_SKETCH", "PARTIAL", "CONDITIONAL"}


def _node_status(node: dict) -> str:
    return str(node.get("status") or "").upper()


def _skeptic_passes_by_node(skeptic: list) -> dict[str, int]:
    """Count corroborating (non-refuting) skeptic reviews per node id."""
    by_node: dict[str, int] = {}
    for rev in skeptic:
        if not isinstance(rev, dict):
            continue
        node_id = str(rev.get("node_id") or rev.get("target_node") or rev.get("node") or "")
        refuted = rev.get("refuted")
        verdict = str(rev.get("verdict") or rev.get("status") or "").upper()
        # A review corroborates unless it explicitly refutes / demotes.
        passes = (refuted is False) or (refuted is None and verdict not in
                                        {"REFUTED", "DEMOTED", "REJECTED", "FAILED"})
        if passes:
            by_node[node_id] = by_node.get(node_id, 0) + 1
    return by_node


def progress_evaluate(run: Path) -> dict:
    """A PROGRESS-weighted score, orthogonal to the structural one.

    The structural grade rewards scaffolding presence (ledgers, dependency
    paths, a report); a run that proves NOTHING can still score a C there. This
    score instead measures verifiable mathematical bite: closed proof-DAG nodes
    dominate, formalization is light credit, and a run with zero closed nodes is
    hard-capped into the F/D band no matter how complete its scaffolding is.
    """
    dag = records(run / "proof_dependency_dag.json")
    workers = records(run / "worker_results.json")
    skeptic = records(run / "skeptic_reviews.json")
    products = records(run / "product_selection.json")

    total = len(dag)
    closed = [n for n in dag if _node_status(n) in CLOSED_STATUSES]
    partial = [n for n in dag if _node_status(n) in PARTIAL_STATUSES]
    formalized = [n for n in dag if str(n.get("lean_statement") or "").strip()]
    n_closed, n_partial, n_formal = len(closed), len(partial), len(formalized)

    components: dict[str, float] = {}

    # 1. Closure ratio (50) — kernel/verifier-gated nodes of the target DAG.
    components["closure_ratio"] = (50.0 * n_closed / total) if total else 0.0
    # 2. Partial informal progress (15) — sketches/special cases.
    components["partial_progress"] = (15.0 * n_partial / total) if total else 0.0
    # 3. Formalization readiness (10) — dispatchable goals; formalizing is not
    #    proving, so this is deliberately light.
    components["formalization_readiness"] = (10.0 * n_formal / total) if total else 0.0
    # 4. Skeptic corroboration (15) — only meaningful on closed nodes; ≥3
    #    independent passing reviews per closed node saturates (Two-Stage rule).
    passes = _skeptic_passes_by_node(skeptic)
    if n_closed:
        closed_ids = {str(n.get("node_id")) for n in closed}
        depth = sum(min(3, passes.get(nid, 0)) for nid in closed_ids)
        components["skeptic_corroboration"] = 15.0 * depth / (3 * n_closed)
    else:
        components["skeptic_corroboration"] = 0.0
    # 5. Verified product (10) — a SELECTED product carrying real evidence.
    verified_product = any(
        p.get("selected") is True and str(p.get("status") or "").upper() in
        (CLOSED_STATUSES | PARTIAL_STATUSES)
        for p in products
    )
    components["verified_product"] = 10.0 if verified_product else 0.0

    raw = sum(components.values())

    # Honesty cap: zero closed nodes => no verifiable progress on the target,
    # regardless of formalization/scaffolding. Cap below the C band.
    capped = raw
    cap_applied = False
    if n_closed == 0 and raw > 25:
        capped = 25.0
        cap_applied = True

    score = int(round(max(0.0, min(100.0, capped))))
    notes: list[str] = []
    if total == 0:
        notes.append("no proof DAG: nothing to make progress on")
    if n_closed == 0:
        notes.append("ZERO kernel/verifier-closed nodes — no verifiable progress on the target")
    if cap_applied:
        notes.append("progress score hard-capped at 25 (no closed nodes)")
    if n_formal and n_closed == 0:
        notes.append(f"{n_formal}/{total} nodes formalized but none proved — dispatchable, not progress")

    return {
        "progress_score": score,
        "progress_grade": grade(score),
        "components": {k: round(v, 2) for k, v in components.items()},
        "counts": {
            "dag_nodes": total,
            "closed_nodes": n_closed,
            "partial_nodes": n_partial,
            "formalized_nodes": n_formal,
            "closure_ratio": round(n_closed / total, 3) if total else 0.0,
        },
        "cap_applied": cap_applied,
        "notes": notes,
    }


def evaluate(run: Path) -> dict:
    score = 0
    strengths: list[str] = []
    gaps: list[str] = []

    required_ledgers = [
        "actual_lemma_queue.json",
        "disproof_first.json",
        "theorem_precondition_audit.json",
        "product_selection.json",
        "mutation_ledger.json",
        "proof_dependency_dag.json",
    ]
    present = [name for name in required_ledgers if (run / name).exists()]
    score += 4 * len(present)
    if len(present) == len(required_ledgers):
        strengths.append("all core Lovasz open-problem ledgers are present")
    else:
        gaps.append(f"missing core ledgers: {sorted(set(required_ledgers) - set(present))}")

    lemmas = records(run / "actual_lemma_queue.json")
    products = records(run / "product_selection.json")
    dag = records(run / "proof_dependency_dag.json")
    workers = records(run / "worker_results.json")
    skeptic = records(run / "skeptic_reviews.json")
    artifacts = load(run / "generator_artifacts.json", {}).get("artifacts", [])
    if not artifacts:
        artifacts = load(run / "witsoc_artifacts.json", {}).get("artifacts", [])
    summary = load(run / "lovasz_summary.json", {})
    feasibility = load(run / "formalization_feasibility.json", {})
    open_report = run / "open_problem_report.md"

    if lemmas:
        exact = [x for x in lemmas if x.get("statement") and x.get("why_it_matters") and x.get("next_mutation")]
        score += min(12, 3 * len(exact))
        if exact:
            strengths.append("actual barrier lemmas include statements, relevance, and next mutations")
        else:
            gaps.append("barrier lemmas lack exact statements/relevance/next mutations")
    else:
        gaps.append("no actual barrier lemma queue")

    selected = [p for p in products if p.get("selected") is True]
    if selected:
        score += 8
        strengths.append("selected research product is explicit")
    else:
        gaps.append("no selected research product")

    dag_with_paths = [n for n in dag if n.get("dependency_path_to_target") or n.get("path_to_target")]
    if dag and len(dag_with_paths) == len(dag):
        score += 10
        strengths.append("proof DAG nodes carry dependency paths to the target")
    elif dag:
        score += 4
        gaps.append("some proof DAG nodes lack dependency paths")
    else:
        gaps.append("no proof dependency DAG")

    verified_workers = [w for w in workers if str(w.get("status") or "").upper() in {"VERIFIED", "CHECKED"}]
    partial_workers = [w for w in workers if str(w.get("status") or "").upper() in {"PARTIAL", "CONDITIONAL", "PROVED_SKETCH"}]
    if verified_workers:
        score += 12
        strengths.append("verified/check worker evidence exists")
    elif partial_workers:
        score += 6
        strengths.append("partial worker evidence exists")
        gaps.append("no verified/check worker result")
    else:
        gaps.append("no substantive worker evidence")

    if skeptic:
        score += 8
        strengths.append("skeptic reviews recorded")
    else:
        gaps.append("missing skeptic reviews")

    artifact_records = [a for a in artifacts if isinstance(a, dict)]
    formal_artifacts = [a for a in artifact_records if str(a.get("type") or "").lower() in {"wit", "lean"}]
    if formal_artifacts:
        score += 10
        strengths.append("formal WIT/Lean artifacts are recorded")
    elif artifact_records:
        score += 5
        strengths.append("supporting artifacts are recorded")
        gaps.append("no WIT/Lean artifact recorded")
    else:
        gaps.append("no artifact registry entries")

    if summary:
        score += 6
        strengths.append("Lovasz summary exists")
    else:
        gaps.append("missing lovasz_summary.json")

    if feasibility:
        score += 6
        strengths.append("formalization feasibility was scored")
        if feasibility.get("label") in {"POOR_FORMALIZATION_TARGET", "NEEDS_MATHLIB_THEOREM_SEARCH"}:
            gaps.append(f"formalization still weak: {feasibility.get('label')}")
    else:
        gaps.append("formalization feasibility not scored")

    if substantive(open_report):
        score += 8
        strengths.append("human-readable open-problem report exists")
    else:
        gaps.append("human-readable report missing or empty")

    score = max(0, min(100, score))
    progress = progress_evaluate(run)

    # Headline: the structural grade alone is misleading when scaffolding is
    # complete but nothing is proved — surface BOTH and flag the gap explicitly.
    gap = score - progress["progress_score"]
    if progress["progress_score"] >= score - 10:
        headline = (f"structural {grade(score)}({score}) / "
                    f"progress {progress['progress_grade']}({progress['progress_score']})")
    else:
        headline = (f"structural {grade(score)}({score}) but progress "
                    f"{progress['progress_grade']}({progress['progress_score']}) — "
                    f"scaffolding outruns verified math by {gap} pts")
        gaps.append("structural grade is scaffolding-inflated: progress grade is "
                    f"{progress['progress_grade']} ({progress['progress_score']}/100)")

    return {
        "schema": "witsoc.report_quality_grade.v2",
        "run_dir": str(run),
        "headline": headline,
        # Structural score (scaffolding presence) — kept under the original keys
        # for back-compat with consumers that read `score`/`grade`.
        "score": score,
        "grade": grade(score),
        "structural_score": score,
        "structural_grade": grade(score),
        # Progress score (verifiable mathematical bite).
        "progress_score": progress["progress_score"],
        "progress_grade": progress["progress_grade"],
        "progress": progress,
        "counts": {
            "actual_lemmas": len(lemmas),
            "products": len(products),
            "dag_nodes": len(dag),
            "worker_results": len(workers),
            "verified_or_checked_workers": len(verified_workers),
            "skeptic_reviews": len(skeptic),
            "artifacts": len(artifact_records),
        },
        "strengths": strengths,
        "gaps": gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = evaluate(args.run_dir)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
