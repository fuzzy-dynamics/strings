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


def records(path: Path) -> list[dict]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


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
    return {
        "schema": "witsoc.report_quality_grade.v1",
        "run_dir": str(run),
        "score": score,
        "grade": grade(score),
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
