#!/usr/bin/env python3
"""Phase 6: curriculum-fed portfolios (deterministic, mock prover).

Checks a target splits into a difficulty-ordered ladder (easy first, target last) and
that, fed to an autonomous campaign, harvesting the easy rungs makes the hard target
compound — while calibration stays intact."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import curriculum_portfolio as cp
import autonomous_campaign as ac


def main() -> int:
    failures: list[str] = []

    # 1. A conjunction target splits into rungs, ordered easy -> hard, target last.
    target = "(a = a) ∧ (∀ n : Nat, n + 0 = n) ∧ (∀ n m : Nat, n * m = m * n ∧ n + m = m + n)"
    port = cp.build_portfolio(target)
    if port[-1]["id"] != "target" or port[-1]["lean_target"] != target:
        failures.append("the full target must be the LAST portfolio entry")
    rung_diffs = [p["difficulty"] for p in port[:-1]]
    if rung_diffs != sorted(rung_diffs):
        failures.append(f"rungs must be ordered easy->hard, got {rung_diffs}")
    if len(port) < 3:
        failures.append(f"a 3-way conjunction should yield >=2 rungs + target, got {len(port)}")

    # 2. Explicit sublemmas are used and ordered by difficulty.
    port2 = cp.build_portfolio("HARD_TARGET",
                               sublemmas=["∀ a b c d : Nat, a * b * c * d = d * c * b * a", "x = x"])
    if port2[0]["lean_target"] != "x = x":
        failures.append("the simplest sublemma should be the first rung")

    # 3. Curriculum-fed compounding: a campaign over the ladder harvests an easy rung's
    #    lemma "L" that the hard target needs, so the target is solved by the last step.
    portfolio = [
        {"id": "rung1", "lean_target": "∀ n : Nat, base_L n"},   # provides L
        {"id": "target", "lean_target": "∀ n : Nat, needs_L n"},  # needs L
    ]
    harvested = set()

    def make_prover(lib):
        def prove(statement, imports=""):
            if "base_L" in statement:
                harvested.add("L"); return {"discharged": True, "proof": "by base"}
            if "needs_L" in statement:
                return {"discharged": True, "proof": "by uses_L"} if "L" in harvested else {"discharged": False, "proof": None}
            return {"discharged": False, "proof": None}
        return prove

    with tempfile.TemporaryDirectory() as td:
        rep = ac.run(portfolio, Path(td) / "lib", iterations=1, max_steps=4, make_prover=make_prover)
        # within ONE iteration: rung1 harvests L (runs first), then target solves using it.
        if rep["best_rung_per_problem"].get("target") != "L6":
            failures.append("the hard target should solve once the easy rung's lemma is harvested (curriculum compounding)")
        if not rep["calibration_clean"]:
            failures.append("calibration must stay clean in a curriculum campaign")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("CURRICULUM_PORTFOLIO_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
