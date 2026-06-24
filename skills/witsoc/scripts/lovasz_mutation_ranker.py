#!/usr/bin/env python3
"""Rank one-axis Lovasz mutations from gap feedback and prior failures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AXES_BY_GAP = {
    "genuine_barrier": ["invariant", "encoding", "object_class", "statement_strength", "method"],
    "formalization_block": ["formalization_target", "encoding", "statement_strength", "method"],
    "precondition_gap": ["theorem_source", "statement_strength", "formalization_target", "method"],
    "prover_search_gap": ["method", "theorem_source", "formalization_target", "encoding"],
}


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict[str, Any]]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def rank(run: Path) -> dict[str, Any]:
    feedback = load(run / "gap_feedback.json", {})
    ledger = records(run / "mutation_ledger.json")
    used_axes = {str(m.get("mutation_axis") or m.get("axis") or "") for m in ledger}
    nodes = feedback.get("nodes") if isinstance(feedback, dict) and isinstance(feedback.get("nodes"), dict) else {}
    rankings = []
    for node_id, gap in nodes.items():
        if not isinstance(gap, dict):
            continue
        gap_class = str(gap.get("gap_class") or "genuine_barrier")
        axes = AXES_BY_GAP.get(gap_class, AXES_BY_GAP["genuine_barrier"])
        scored = []
        for i, axis in enumerate(axes):
            score = 100 - i * 8
            if axis in used_axes:
                score -= 25
            if axis == str(gap.get("proposed_mutation") or ""):
                score += 10
            scored.append({"axis": axis, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        rankings.append({
            "node_id": node_id,
            "gap_class": gap_class,
            "recommended_axis": scored[0]["axis"],
            "axis_scores": scored,
            "status": "attention_only",
        })
    return {"schema": "witsoc.lovasz_mutation_ranking.v1", "run_dir": str(run), "rankings": rankings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = rank(args.run_dir)
    out = args.out or (args.run_dir / "lovasz_mutation_ranking.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
