#!/usr/bin/env python3
"""Phase 4: the persistent research director + bandit (deterministic, mock outcomes).

Checks that the controller ALLOCATES effort sensibly (converges on a productive
approach, retires dead-ends), that state COMPOUNDS across sessions, and that it stops
HONESTLY — never upgrading a claim, never looping until a 'solve'."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_state as rs

TARGET = "∀ n : Nat, hard_open_target n"


def main() -> int:
    failures: list[str] = []

    # 1. Bandit converges: one approach yields a verified L4 partial, others nothing.
    #    The controller should try that approach far more than the rest over time.
    def execute_productive(approach, target):
        if approach == "construction_search":
            return {"rung": "L4", "status": "CHECKED", "partial": "verified barrier lemma"}
        return {"rung": "L0", "status": "OPEN"}

    st = rs.new_state(TARGET)
    # run several sessions; state persists across them
    for _ in range(3):
        st = rs.run_campaign(TARGET, execute_productive, max_steps=20, state=st)
    tries = st["approach_stats"]
    if tries["construction_search"]["tries"] < max(tries[a]["tries"] for a in rs.APPROACHES if a != "construction_search"):
        failures.append("bandit should allocate the MOST tries to the productive approach")
    if st["best_rung"] != "L4":
        failures.append(f"best_rung should track the verified L4 partial, got {st['best_rung']}")
    if not st["partial_results"]:
        failures.append("a verified L4 partial must be recorded")
    if st["sessions"] != 3:
        failures.append(f"state must compound across sessions, got sessions={st['sessions']}")

    # 2. CALIBRATION: the controller never invents a rung. With every approach failing,
    #    best_rung stays L0, dead-ends fill, and the campaign STOPS honestly (not SOLVED).
    def execute_barren(approach, target):
        return {"rung": "L0", "status": "OPEN"}

    st2 = rs.run_campaign(TARGET, execute_barren, max_steps=100)
    if st2["best_rung"] != "L0":
        failures.append("with no progress, best_rung must stay L0 (no invented rung)")
    if st2["status"] not in ("STALLED", "HONEST_STOP"):
        failures.append(f"a barren campaign must stop honestly, got {st2['status']}")
    if st2["status"] == "SOLVED":
        failures.append("a campaign must NEVER report SOLVED without a verified L6")

    # 2b. Dead-end retirement: an approach that fails DEADEND_STREAK times in a row is
    #     retired and never selected again.
    st2b = rs.new_state(TARGET)
    for _ in range(rs.DEADEND_STREAK):
        rs.record(st2b, "ontology_pivot", {"rung": "L0"})
    if "ontology_pivot" not in st2b["dead_ends"]:
        failures.append("an approach failing DEADEND_STREAK times must be retired as a dead-end")
    for _ in range(50):
        if rs.select_approach(st2b) == "ontology_pivot":
            failures.append("a retired dead-end approach must never be selected again")
            break

    # 3. SOLVED only at a verified L6.
    def execute_solver(approach, target):
        return {"rung": "L6", "status": "VERIFIED_LEAN"} if approach == "direct_prover" else {"rung": "L0"}
    st3 = rs.run_campaign(TARGET, execute_solver, max_steps=20)
    if st3["best_rung"] == "L6" and st3["status"] != "SOLVED":
        failures.append("a verified L6 outcome must set status SOLVED")

    # 4. Persistence: save/load round-trips the compounding state.
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "state.json"
        rs.save(p, st)
        reloaded = rs.load(p)
        if reloaded["target_hash"] != st["target_hash"] or reloaded["best_rung"] != st["best_rung"]:
            failures.append("state must round-trip through save/load")
        if reloaded["attempt_ledger"] != st["attempt_ledger"]:
            failures.append("the attempt ledger must persist intact")

    # 5. Priors steer first picks: an analogical-transfer suggestion is tried among the first.
    fresh = rs.new_state(TARGET)
    picks = []
    for _ in range(len(rs.APPROACHES)):
        a = rs.select_approach(fresh, priors={"speculative_arena": 5.0})
        picks.append(a)
        rs.record(fresh, a, {"rung": "L0"})
    if "speculative_arena" not in picks[:3]:
        failures.append(f"a strong prior should make that approach an early pick, got {picks[:3]}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("RESEARCH_STATE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
