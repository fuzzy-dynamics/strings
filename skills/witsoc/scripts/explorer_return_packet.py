#!/usr/bin/env python3
"""Generate a formal Lovasz-to-Explorer return packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ACCEPTED = {"VERIFIED", "CHECKED", "PROVED_SKETCH", "PARTIAL", "CONDITIONAL", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL", "CHECKED_BOUNDED", "CHECKED_SYMBOLIC"}
OPENISH = {"OPEN", "GAP", "CONJECTURE", "FAILED_ATTEMPT", "REJECTED", "DEMOTED"}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


from witcore import records  # noqa: E402  -- shared substrate, was a local copy

def grade_value(grade: str) -> int:
    return {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}.get(str(grade).upper(), 0)


def choose_action(accepted: list[dict], barriers: list[dict], formal: dict, grade: dict) -> str:
    label = str(formal.get("label") or "")
    grade_letter = str(grade.get("grade") or "")
    has_verified = any(str(x.get("status") or "").upper() in {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL"} for x in accepted)
    if has_verified and label in {"FORMALIZATION_READY", "NEEDS_LOCAL_DEFINITIONS"} and grade_value(grade_letter) >= 4:
        return "generator_ready"
    if accepted:
        return "explorer_review_partial"
    if barriers and label in {"POOR_FORMALIZATION_TARGET", "NEEDS_MATHLIB_THEOREM_SEARCH"}:
        return "relaunch_lovasz"
    if barriers:
        return "repair"
    return "stop_open"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    run = args.run_dir
    # R4/L4: returning to Explorer is the natural sync point — this run's
    # failure memory joins the global store so future runs see it. Guarded.
    try:
        import knowledge_store
        knowledge_store.sync_run(run)
    except Exception:
        pass
    manifest = load(run / "lovasz_run.json", {})
    formal = load(run / "formalization_feasibility.json", {})
    grade = load(run / "report_quality_grade.json", {})
    summary = load(run / "lovasz_summary.json", {})
    dag = records(run / "proof_dependency_dag.json")
    products = records(run / "product_selection.json")
    accepted = [n for n in dag if str(n.get("status") or "").upper() in ACCEPTED]
    barriers = []
    for n in dag:
        if str(n.get("status") or "").upper() in OPENISH:
            barriers.append({
                "node_id": n.get("node_id") or n.get("id"),
                "statement": n.get("statement"),
                "status": n.get("status"),
                "next_exact_experiment_or_lemma": n.get("next_exact_experiment_or_lemma") or n.get("next_mutation"),
            })
    demoted = [n for n in dag if str(n.get("status") or "").upper() in {"REJECTED", "DEMOTED"}]
    packet = {
        "schema": "witsoc.explorer_return_packet.v1",
        "target_hash": manifest.get("target_hash") or "",
        "source_target_text": manifest.get("source_target_text") or "",
        "recommended_action": choose_action(accepted, barriers, formal, grade),
        "accepted_products": [
            {
                "node_id": n.get("node_id") or n.get("id"),
                "status": n.get("status"),
                "statement": n.get("statement"),
                "evidence": n.get("evidence"),
                "dependency_path_to_target": n.get("dependency_path_to_target") or n.get("path_to_target"),
            }
            for n in accepted
        ],
        "selected_products": [p for p in products if p.get("selected") is True],
        "demoted_claims": [
            {
                "node_id": n.get("node_id") or n.get("id"),
                "status": n.get("status"),
                "statement": n.get("statement"),
                "reason": n.get("failure_class") or n.get("reason"),
            }
            for n in demoted
        ],
        "remaining_barriers": barriers,
        "formalization": {
            "score": formal.get("score"),
            "label": formal.get("label"),
            "recommendation": formal.get("recommendation"),
        },
        "report_quality": {
            "score": grade.get("score"),
            "grade": grade.get("grade"),
            # Progress (verifiable math) vs structural (scaffolding) — surface
            # both so a scaffolding-inflated grade can't read as real progress.
            "progress_score": grade.get("progress_score"),
            "progress_grade": grade.get("progress_grade"),
            "headline": grade.get("headline"),
            "gaps": grade.get("gaps", []),
        },
        "summary": {
            "status_counts": summary.get("status_counts", {}),
            "worker_status_counts": summary.get("worker_status_counts", {}),
        },
    }
    out = args.out or (run / "explorer_return_packet.json")
    out.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
