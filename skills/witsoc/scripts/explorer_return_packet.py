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


def reduction_block(run: Path) -> dict | None:
    """The conjecture-distance assessment, read straight from the reduction
    ledger so it reaches Explorer even when the grade file was not saved."""
    try:
        import reduction_ledger as rl
        led = rl._load(rl.ledger_path(run), None)
        if isinstance(led, dict) and led.get("schema") == rl.SCHEMA:
            return rl.assess(led)
    except Exception:
        pass
    return None


def choose_action(accepted: list[dict], barriers: list[dict], formal: dict, grade: dict,
                  reduction: dict | None = None) -> str:
    label = str(formal.get("label") or "")
    grade_letter = str(grade.get("grade") or "")
    has_verified = any(str(x.get("status") or "").upper() in {"VERIFIED", "VERIFIED_WIT", "VERIFIED_LEAN", "VERIFIED_EXTERNAL"} for x in accepted)
    # Conjecture-distance guard: while the reduction's open_core is open (or the
    # target is otherwise not reduced), the run is NOT solve-ready no matter how
    # the seeded nodes graded — closing easy obligations is not closing the
    # conjecture. Never escalate to generator_ready in that state.
    open_core_blocks = bool(reduction and not reduction.get("reduced")
                            and reduction.get("band") != "REDUCED")
    if (has_verified and label in {"FORMALIZATION_READY", "NEEDS_LOCAL_DEFINITIONS"}
            and grade_value(grade_letter) >= 4 and not open_core_blocks):
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
    reduction = reduction_block(run)
    packet = {
        "schema": "witsoc.explorer_return_packet.v1",
        "target_hash": manifest.get("target_hash") or "",
        "source_target_text": manifest.get("source_target_text") or "",
        "recommended_action": choose_action(accepted, barriers, formal, grade, reduction),
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
        # Conjecture-distance: how far the run is from the TARGET (obligations
        # discharged, open_core open, band) — the honest signal Explorer arbitrates on.
        "reduction": ({
            "band": reduction["band"],
            "obligations_discharged": reduction["obligations_discharged"],
            "obligations_total": reduction["obligations_total"],
            "open_core_open": reduction["open_core_open"],
            "reduced": reduction["reduced"],
            "note": reduction["cap_note"],
        } if reduction else None),
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
