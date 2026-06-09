#!/usr/bin/env python3
"""Phase 1: deep search across the induction-generalization barrier.

`proof_search.generalization_candidates` proposes a STRONGER auxiliary lemma
(generalizing a constant accumulator argument), proves it by induction, and
specializes it — closing goals that one-level induction provably cannot. Every
candidate is a whole, kernel-gated proof, so a wrong generalization just fails."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_search as ps

# additive accumulator: fa n acc = acc + n
FA = "def fa : Nat → Nat → Nat\n  | 0, acc => acc\n  | (n+1), acc => fa n (acc + 1)"
# additive-by-2 accumulator: fc n acc = acc + 2*n
FC = "def fc : Nat → Nat → Nat\n  | 0, acc => acc\n  | (n+1), acc => fc n (acc + 2)"


def main() -> int:
    failures: list[str] = []

    # 1. Generation: an accumulator goal yields generalized two-level candidates,
    #    each a `have hgen ... := (by ... induction ...)` proof. (Deterministic.)
    cands = ps.generalization_candidates("∀ n : Nat, fa n 0 = n", FA)
    if not cands:
        failures.append("generalization_candidates must fire on an accumulator goal")
    if not all("hgen" in c and "induction" in c for c in cands):
        failures.append("every generalization candidate must build+use a generalized aux lemma")

    # 2. A goal with NO 2-arg accumulator def yields nothing (no spurious work).
    if ps.generalization_candidates("∀ n : Nat, n + 0 = n", ""):
        failures.append("generalization must not fire without a 2-arg accumulator def")
    if ps.generalization_candidates("∀ n : Nat, dbl n = 2 * n",
                                    "def dbl : Nat → Nat\n  | 0 => 0\n  | (n+1) => dbl n + 2"):
        failures.append("generalization must not fire on a 1-arg recursive def")

    # 3. End to end (needs Lean): the additive accumulator barrier is now CLOSED by
    #    the generalization route — a goal direct induction cannot reach.
    r = ps.search("∀ n : Nat, fa n 0 = n", FA, None, None, None, max_nodes=300, workers=12)
    if r.get("label") == "UNCHECKED_NO_TOOLCHAIN":
        print("GENERALIZATION_SEARCH_TESTS_SKIP (no Lean toolchain)")
        return 0 if not failures else 1
    if not r.get("discharged"):
        failures.append(f"fa accumulator should close via generalization, got {r.get('label')}")
    elif (r.get("trace") or {}).get("strategy") != "generalization":
        failures.append(f"strategy should be generalization, got {(r.get('trace') or {}).get('strategy')!r}")
    elif "hgen" not in r.get("proof", ""):
        failures.append("closing proof must use the generalized aux lemma")

    # 4. A second additive accumulator (adds 2 each step) also closes via generalization.
    r2 = ps.search("∀ n : Nat, fc n 0 = 2 * n", FC, None, None, None, max_nodes=300, workers=12)
    if not r2.get("discharged"):
        failures.append(f"fc accumulator should close via generalization, got {r2.get('label')}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("GENERALIZATION_SEARCH_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
