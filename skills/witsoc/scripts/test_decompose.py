#!/usr/bin/env python3
"""Tests for Item 1: decompose_problem.py dispatchable barrier-lemma nodes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decompose_problem as dp
import concept_generator as cg


def main() -> int:
    failures: list[str] = []

    nodes, lemmas = dp.decompose("for all n, n + 0 = n", "h" * 64,
                                 lean_target="∀ n : Nat, n + 0 = n", domain="number_theory")
    disp = [n for n in nodes if n.get("lean_statement")]
    if len(disp) < 4:
        failures.append(f"expected >=4 dispatchable nodes with lean_statement, got {len(disp)}")
    KNOWN_FALSIF = {"counterexample_search", "number_theory_search", "finite_graph_search",
                    "finite_model_or_smt", "manual_or_formalization_required"}
    for n in disp:
        if n.get("arena") != cg.ARENA:
            failures.append(f"dispatchable node must be SPECULATIVE: {n.get('node_id')}")
        if n.get("status") not in ("OPEN", "OPEN_UNFALSIFIED"):
            failures.append(f"dispatchable node must be OPEN/OPEN_UNFALSIFIED: {n.get('node_id')}")
        ft = n.get("falsification_test") or {}
        if ft.get("kind") not in KNOWN_FALSIF:
            failures.append(f"dispatchable node must carry a falsification_test with a known kind: {n.get('node_id')} -> {ft.get('kind')}")
    # lemma queue carries lean_statement projections
    if sum(1 for l in lemmas if l.get("lean_statement")) < 4:
        failures.append("actual_lemma_queue must carry lean_statement entries")
    # nothing above OPEN
    if any(l.get("status") not in ("OPEN", "OPEN_UNFALSIFIED") for l in lemmas):
        failures.append("decompose must not emit any lemma above OPEN")

    # no concept nodes when there is no Lean target and the statement is prose
    nodes2, _ = dp.decompose("some informal graph-theory statement about chromatic number", "g" * 64)
    if any(n.get("lean_statement") for n in nodes2):
        failures.append("prose target without --lean-target should not yield lean_statement nodes")
    # but generic audit scaffold still present
    if not any(n["type"] == "actual_barrier_lemma" for n in nodes2):
        failures.append("generic barrier-lemma scaffold must remain")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("DECOMPOSE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
