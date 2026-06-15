#!/usr/bin/env python3
"""Score Explorer approaches for search priority, not acceptance."""

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


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def score_sketch(sketch: dict[str, Any]) -> dict[str, Any]:
    lemmas = as_list(sketch.get("lemmas")) + as_list(sketch.get("proof_objects"))
    gaps = as_list(sketch.get("gaps")) + as_list(sketch.get("remaining_goals"))
    fidelity = float(sketch.get("target_fidelity", 0.7) or 0.7)
    ev = float(sketch.get("ev", 0.0) or 0.0)
    dependency = 1.0 if sketch.get("dependency_path_to_target") or not lemmas else 0.6
    formal = 1.0 if sketch.get("lean_statement") or sketch.get("formalization_plan") else 0.5
    falsification = 1.0 if sketch.get("falsification_test") or sketch.get("counterexamples_checked") else 0.6
    repairability = max(0.2, 1.0 - 0.12 * len(gaps))
    score = 100 * (0.30 * fidelity + 0.20 * dependency + 0.20 * formal + 0.15 * falsification + 0.15 * repairability)
    if ev:
        score = 0.7 * score + 30 * ev
    return {
        "sketch_id": sketch.get("sketch_id") or sketch.get("id"),
        "score": round(score, 2),
        "target_fidelity": fidelity,
        "formalization_signal": formal,
        "repairability": round(repairability, 2),
        "status": "SEARCH_PRIORITY_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    handoff = load(args.run_dir / "handoff.json", {})
    sketches = as_list(handoff.get("sketches")) if isinstance(handoff, dict) else []
    scores = sorted([score_sketch(s) for s in sketches if isinstance(s, dict)], key=lambda x: x["score"], reverse=True)
    result = {
        "schema": "witsoc.explorer_approach_scores.v1",
        "run_dir": str(args.run_dir),
        "status": "attention_only_never_acceptance",
        "scores": scores,
        "selected_sketch_id": scores[0]["sketch_id"] if scores else None,
    }
    out = args.out or (args.run_dir / "explorer_approach_scores.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
