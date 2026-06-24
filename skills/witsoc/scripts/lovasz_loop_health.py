#!/usr/bin/env python3
"""Detect Lovasz campaign loops that keep looping without learning."""

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


def records(path: Path) -> list[dict[str, Any]]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def assess(run: Path) -> dict[str, Any]:
    workers = records(run / "worker_results.json")
    mutations = records(run / "mutation_ledger.json")
    theory = load(run / "problem_theory.json", {})
    scores = load(run / "lovasz_result_scores.json", {})
    feedback = load(run / "gap_feedback.json", {})
    top_score = max((float(s.get("score") or 0) for s in scores.get("scores", []) if isinstance(s, dict)), default=0.0) if isinstance(scores, dict) else 0.0
    method_counts: dict[str, int] = {}
    for w in workers:
        method = str(w.get("method_family") or w.get("worker_type") or w.get("role") or "unknown")
        method_counts[method] = method_counts.get(method, 0) + 1
    repeated = [m for m, c in method_counts.items() if c >= 3]
    theory_revisions = max(0, int(theory.get("version", 1) or 1) - 1) if isinstance(theory, dict) else 0
    feedback_nodes = len(feedback.get("nodes", {})) if isinstance(feedback, dict) and isinstance(feedback.get("nodes"), dict) else 0
    stuck_reasons = []
    if workers and theory_revisions == 0:
        stuck_reasons.append("no theory diff after worker activity")
    if feedback_nodes and not mutations:
        stuck_reasons.append("gap feedback has no mutation records")
    if repeated and not mutations:
        stuck_reasons.append("method family repeated without mutation ledger")
    if workers and top_score <= 0:
        stuck_reasons.append("no positive candidate score")
    return {
        "schema": "witsoc.lovasz_loop_health.v1",
        "run_dir": str(run),
        "stuck": bool(stuck_reasons),
        "reasons": stuck_reasons,
        "top_score": top_score,
        "theory_revisions": theory_revisions,
        "mutation_records": len(mutations),
        "recommended_actions": [
            "pivot barrier",
            "change encoding",
            "run counterexample/disproof mode",
            "run retrieval/analogy",
            "ask Intelligence Bus",
            "honest stop",
        ] if stuck_reasons else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = assess(args.run_dir)
    out = args.out or (args.run_dir / "lovasz_loop_health.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["stuck"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
