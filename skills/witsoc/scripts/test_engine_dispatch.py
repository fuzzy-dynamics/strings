#!/usr/bin/env python3
"""Phase 4 wiring: the real engine dispatcher (mock prover for logic, one real solve).

Checks the dispatch maps approaches to engines with correct kernel-gated rungs, shares
CONTEXT across approaches (retrieval enriches imports, analogy sets bandit priors), and
that a campaign with the REAL prover reaches SOLVED on a solvable goal while a barren one
stops honestly — no invented rungs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_dispatch as ed
import witcore

ACC = "def fa : Nat → Nat → Nat\n  | 0, acc => acc\n  | (n+1), acc => fa n (acc + 1)"
LLEN = "def llen : List Nat → Nat\n  | [] => 0\n  | (_ :: xs) => llen xs + 1"


def prover_yes(statement, imports=""):
    return {"discharged": True, "proof": "by trivial"}


def prover_no(statement, imports=""):
    return {"discharged": False, "proof": None}


def main() -> int:
    failures: list[str] = []

    # 1. Rung mapping: a discharged target is L6/VERIFIED_LEAN; open is L0.
    d = ed.EngineDispatcher("∀ n : Nat, P n", prover=prover_yes)
    if d.execute("direct_prover", "t") != {"rung": "L6", "status": "VERIFIED_LEAN", "evidence": "by trivial", "partial": None}:
        failures.append("direct_prover on a discharged goal must be L6/VERIFIED_LEAN")
    if ed.EngineDispatcher("∀ n : Nat, P n", prover=prover_no).execute("direct_prover", "t")["rung"] != "L0":
        failures.append("direct_prover on an open goal must be L0")

    # 2. Applicability gating (no wasted prover call when the technique cannot apply).
    if ed.EngineDispatcher("∀ n : Nat, n + 0 = n", prover=prover_yes).execute("generalize_invariant", "t")["status"] != "not_applicable":
        failures.append("generalize_invariant must be not_applicable without an accumulator def")
    if ed.EngineDispatcher("∀ n : Nat, fa n 0 = n", preamble=ACC, prover=prover_yes).execute("generalize_invariant", "t")["rung"] != "L6":
        failures.append("generalize_invariant must run the prover on an accumulator goal")
    if ed.EngineDispatcher("∀ (l : List Nat), llen l = l.length", preamble=LLEN, prover=prover_yes).execute("structural_induction", "t")["rung"] != "L6":
        failures.append("structural_induction must run on a List goal")
    if ed.EngineDispatcher("∀ n : Nat, n + 0 = n", prover=prover_yes).execute("structural_induction", "t")["status"] != "not_applicable":
        failures.append("structural_induction must be not_applicable on a Nat goal")

    # 3. Context sharing: premise_retrieval enriches imports; analogy sets bandit priors.
    dpr = ed.EngineDispatcher("∀ a b : Nat, a * b = b * a", prover=prover_no)
    pr_out = dpr.execute("premise_retrieval", "t")
    if pr_out["status"] != "premises_retrieved" or "Nat.mul_comm" not in (pr_out.get("evidence") or []):
        failures.append(f"premise_retrieval should retrieve Nat.mul_comm into context, got {pr_out.get('evidence')}")
    dan = ed.EngineDispatcher("∀ n : Nat, fa n 0 = n", preamble=ACC, domain="number_theory", prover=prover_no)
    an_out = dan.execute("analogical_transfer", "t")
    if "generalize_the_invariant" not in (an_out.get("evidence") or []):
        failures.append("analogical_transfer should suggest generalize_the_invariant for an accumulator goal")
    if dan.context["priors"].get("generalize_invariant", 0) <= 0:
        failures.append("analogical_transfer must set a bandit prior on the mapped approach")

    # 4. CALIBRATION: a barren campaign (prover never discharges) stops honestly, never SOLVED.
    db = ed.EngineDispatcher("∀ n : Nat, hard n", prover=prover_no)
    sb = ed.campaign(db, "∀ n : Nat, hard n", max_steps=100)
    if sb["best_rung"] != "L0" or sb["status"] not in ("STALLED", "HONEST_STOP") or sb["status"] == "SOLVED":
        failures.append(f"barren campaign must stop honestly at L0, got {sb['status']}/{sb['best_rung']}")

    # 5. A solvable campaign reaches SOLVED (mock prover).
    se = ed.campaign(ed.EngineDispatcher("∀ n : Nat, easy n", prover=prover_yes), "∀ n : Nat, easy n", max_steps=12)
    if se["status"] != "SOLVED" or se["best_rung"] != "L6":
        failures.append(f"a solvable campaign must reach SOLVED/L6, got {se['status']}/{se['best_rung']}")

    # 6. REAL end-to-end (needs Lean): the accumulator goal is SOLVED by the actual prover
    #    (generalization), through the director — wiring confirmed against the kernel.
    if witcore.lean_verify_cached("#check @Nat.mul_comm\n", None).get("checked"):
        disp = ed.EngineDispatcher("∀ n : Nat, fa n 0 = n", preamble=ACC, prover=ed.real_prover())
        sr = ed.campaign(disp, "∀ n : Nat, fa n 0 = n", max_steps=3)
        if sr["status"] != "SOLVED" or sr["best_rung"] != "L6":
            failures.append(f"real campaign should SOLVE the accumulator goal via the prover, got {sr['status']}/{sr['best_rung']}")
        else:
            # the recorded evidence is a real proof the kernel accepts.
            proof = next((e["evidence"] for e in sr["attempt_ledger"] if e["rung"] == "L6"), None)
            if not proof or "hgen" not in str(proof):
                failures.append(f"the SOLVED evidence should be the generalization proof, got {proof}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("ENGINE_DISPATCH_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
