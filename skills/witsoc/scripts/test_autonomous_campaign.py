#!/usr/bin/env python3
"""Phase 6: autonomous campaigns / the flywheel at scale (mock prover, deterministic).

Checks the runner ORCHESTRATES a compounding portfolio (a problem becomes solvable only
after an earlier one's lemma is harvested, so the capability curve rises across
iterations), and ENFORCES calibration at scale (a frozen-calibration problem is never
solved; one violation fails the whole campaign)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autonomous_campaign as ac

# P2 is solvable only AFTER P1's lemma "L" is harvested. P2 is listed FIRST, so in
# iteration 1 it runs before P1 (fails); by iteration 2, L is harvested (P2 solves).
PORTFOLIO = [
    {"id": "P2", "lean_target": "∀ n : Nat, depends_on_L n"},
    {"id": "P1", "lean_target": "∀ n : Nat, base_lemma_L n"},
    {"id": "CAL", "lean_target": "∀ n : Nat, calibration_open n", "tier": "frozen_calibration"},
]


def compounding_make_prover(harvested: set):
    def make_prover(lib):
        def prove(statement, imports=""):
            if "calibration_open" in statement:
                return {"discharged": False, "proof": None}          # never
            if "base_lemma_L" in statement:
                harvested.add("L")
                return {"discharged": True, "proof": "by base"}
            if "depends_on_L" in statement:
                return {"discharged": True, "proof": "by uses_L"} if "L" in harvested else {"discharged": False, "proof": None}
            return {"discharged": False, "proof": None}
        return prove
    return make_prover


def main() -> int:
    failures: list[str] = []

    # 1. Compounding across iterations + calibration held.
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / "lib"
        rep = ac.run(PORTFOLIO, lib, iterations=2, max_steps=6,
                     make_prover=compounding_make_prover(set()))
        it1, it2 = rep["log"][0]["solved"], rep["log"][1]["solved"]
        if not (it2 > it1):
            failures.append(f"capability must rise across iterations (compounding), got iter1={it1} iter2={it2}")
        if rep["verdict"] != "FLYWHEEL_TURNS":
            failures.append(f"a compounding portfolio should report FLYWHEEL_TURNS, got {rep['verdict']}")
        if not rep["calibration_clean"] or rep["calibration_violations"]:
            failures.append(f"the calibration problem must never be solved, got {rep['calibration_violations']}")
        if rep["best_rung_per_problem"]["CAL"] != "L0":
            failures.append("the calibration problem must stay at L0 across the whole campaign")
        if rep["best_rung_per_problem"]["P2"] != "L6":
            failures.append("P2 should reach L6 once its dependency lemma is harvested")

    # 2. Calibration ENFORCEMENT: a prover that (wrongly) solves the calibration problem
    #    fails the whole campaign — the sacred invariant at the autonomous level.
    def cheating_make_prover(lib):
        return lambda statement, imports="": {"discharged": True, "proof": "by cheat"}
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / "lib"
        rep2 = ac.run(PORTFOLIO, lib, iterations=1, max_steps=4, make_prover=cheating_make_prover)
        if rep2["calibration_clean"] or not rep2["calibration_violations"]:
            failures.append("a fake solve of the calibration problem must be flagged a violation")

    # 3. Barren portfolio: nothing solved, but the campaign completes honestly (no crash,
    #    calibration clean, PLATEAU).
    def barren_make_prover(lib):
        return lambda statement, imports="": {"discharged": False, "proof": None}
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / "lib"
        rep3 = ac.run(PORTFOLIO, lib, iterations=2, max_steps=4, make_prover=barren_make_prover)
        if rep3["log"][-1]["solved"] != 0 or rep3["verdict"] != "PLATEAU" or not rep3["calibration_clean"]:
            failures.append(f"a barren portfolio must be an honest PLATEAU, got {rep3['verdict']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("AUTONOMOUS_CAMPAIGN_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
