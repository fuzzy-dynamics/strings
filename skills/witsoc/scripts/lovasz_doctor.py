#!/usr/bin/env python3
"""Diagnose Lovasz campaign health and exact next repairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import lovasz_campaign_state as lcs  # noqa: E402


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def diagnose(state: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    actions: list[str] = []
    spine = state.get("barrier_spine", {})
    breadth = state.get("breadth", {})
    formal = state.get("formalization", {})
    results = state.get("results", {})
    learning = state.get("learning", {})
    explorer = state.get("explorer_return", {})

    if spine.get("barriers", 0) == 0 or spine.get("barrier_nodes", 0) == 0:
        blockers.append("missing depth spine: no barrier_attacks or actual_barrier_lemma DAG node")
        actions.append("run barrier-attack init or lovasz-top-tier prepare")
    if spine.get("main_barrier_workers", 0) == 0 and results.get("worker_results", 0) > 0:
        blockers.append("workers ran but none attacked the main barrier")
        actions.append("dispatch actual_barrier_lemma nodes before side products")
    if formal.get("formalizable_nodes", 0) == 0:
        warnings.append("no DAG node has lean_statement; prover dispatch cannot attack real obligations")
        actions.append("formalize at least one main barrier node")
    if results.get("candidate_only", 0) and results.get("accepted", 0):
        warnings.append("candidate and accepted statuses coexist; verify acceptance came from downstream gates")
    if learning.get("gap_feedback_nodes", 0) and learning.get("mutation_records", 0) == 0:
        blockers.append("gap feedback exists but no mutation ledger was recorded")
        actions.append("run gap-feedback and barrier-attack mutate before redispatch")
    if learning.get("theory_revisions", 0) == 0 and results.get("worker_results", 0) > 0:
        warnings.append("workers ran but problem theory has no revisions")
        actions.append("update problem_theory.json with the learned failure mechanism")
    if breadth.get("serendipity", 0) > max(1, int(max(1, breadth.get("queue", 0)) * 0.2)):
        warnings.append("serendipity lane exceeds 20% of queue")
        actions.append("defer side lemmas until main barrier has pressure")
    if results.get("worker_results", 0) and not explorer.get("exists"):
        warnings.append("worker results exist but no Explorer return packet has been finalized")
        actions.append("run campaign_driver.py --finalize")

    health = "RED" if blockers else ("YELLOW" if warnings else "GREEN")
    return {
        "schema": "witsoc.lovasz_doctor.v1",
        "health": health,
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": list(dict.fromkeys(actions)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    state = load(args.run_dir / "lovasz_campaign_state.json", None)
    if not isinstance(state, dict):
        state = lcs.assemble(args.run_dir)
    result = diagnose(state)
    out = args.out or (args.run_dir / "lovasz_doctor.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["health"] != "RED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
