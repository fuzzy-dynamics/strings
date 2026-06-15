#!/usr/bin/env python3
"""Audit Lovasz final synthesis before Explorer return."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SOLVE_WORDS = ("solved", "full solve", "proof of the original", "resolved")


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def records(path: Path) -> list[dict[str, Any]]:
    data = load(path, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def audit(run: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    scores = load(run / "lovasz_result_scores.json", {})
    explorer = load(run / "explorer_return_packet.json", {})
    summary = load(run / "lovasz_summary.json", {})
    theory = load(run / "problem_theory.json", {})
    solve_claim = load(run / "solve_claim.json", {})
    dag = records(run / "proof_dependency_dag.json")
    score_rows = scores.get("scores") if isinstance(scores, dict) and isinstance(scores.get("scores"), list) else []
    top = score_rows[:3]
    remaining = [n for n in dag if str(n.get("status") or "OPEN").upper() in {"OPEN", "OPEN_UNFALSIFIED", "GAP", "CONJECTURE", "FAILED_ATTEMPT"}]
    text = json.dumps({"explorer": explorer, "summary": summary}, ensure_ascii=False).lower()
    if any(word in text for word in SOLVE_WORDS) and solve_claim.get("status") != "SOLVE_ACCEPTED":
        errors.append("solve/full-resolution language present without SOLVE_ACCEPTED")
    if not top and records(run / "worker_results.json"):
        warnings.append("worker results exist but no Lovasz result scores were produced")
    if remaining and isinstance(explorer, dict) and explorer.get("recommended_action") in {"generator_ready", "GENERATOR_READY"}:
        errors.append("GENERATOR_READY while DAG still has open/GAP/conjectural nodes")
    theory_revisions = max(0, int(theory.get("version", 1) or 1) - 1) if isinstance(theory, dict) else 0
    result = {
        "schema": "witsoc.lovasz_synthesis_audit.v1",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "top_candidates": top,
        "remaining_barriers": len(remaining),
        "theory_revisions": theory_revisions,
        "status_ceiling": "candidate_only_until_downstream_gates",
        "not_full_solve_reason": None if solve_claim.get("status") == "SOLVE_ACCEPTED" else "solve_claim_protocol has not accepted a solve",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    result = audit(args.run_dir)
    out = args.out or (args.run_dir / "lovasz_synthesis_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
