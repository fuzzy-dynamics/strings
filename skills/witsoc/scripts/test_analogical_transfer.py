#!/usr/bin/env python3
"""Phase 3: analogical-transfer technique suggester (deterministic, no Lean).

Checks that a barrier's shape retrieves the RIGHT historical technique, and that
suggestions are structurally SPECULATIVE (a hint can never become a solve)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analogical_transfer as at


def techniques(statement: str, domain: str = "") -> list[str]:
    return [s["technique"] for s in at.suggest(statement, domain, k=4)]


def main() -> int:
    failures: list[str] = []

    # 1. The accumulator/recurrence barrier retrieves "generalize the invariant".
    t = techniques("∀ n : Nat, fa n 0 = n", "number_theory")
    if "generalize_the_invariant" not in t:
        failures.append(f"accumulator barrier should suggest generalize_the_invariant, got {t}")

    # 2. A divisor/perfect-number barrier retrieves multiplicativity.
    t = techniques("∀ n : Nat, perfect n → even n  (sum of divisors sigma)", "number_theory")
    if "multiplicativity_euler_product" not in t:
        failures.append(f"divisor barrier should suggest multiplicativity, got {t}")

    # 3. An existence / lower-bound over a large set retrieves the probabilistic method.
    t = techniques("there exists a set with no 3-term arithmetic progression of density at least c", "additive_combinatorics")
    if not ({"probabilistic_method_alteration", "density_increment"} & set(t)):
        failures.append(f"additive existence barrier should suggest probabilistic/density technique, got {t}")

    # 4. An extremal graph barrier retrieves extremal stability.
    t = techniques("the maximum number of edges in a triangle-free graph on n vertices (extremal, forbidden subgraph)", "graph_theory")
    if "extremal_stability" not in t:
        failures.append(f"extremal graph barrier should suggest extremal_stability, got {t}")

    # 5. An unrelated/empty goal yields no spurious high-confidence suggestion.
    if at.suggest("True", "", 4) and at.suggest("True", "", 4)[0]["relevance"] > 0.5:
        failures.append("a contentless goal must not get a high-relevance technique")

    # 6. CALIBRATION: every suggestion is OPEN_UNFALSIFIED / SPECULATIVE (a hint, not a claim).
    for s in at.suggest("∀ n : Nat, fa n 0 = n", "number_theory", 4):
        if s["status"] != at.OPEN or s["arena"] != at.ARENA:
            failures.append(f"suggestion must be SPECULATIVE/OPEN_UNFALSIFIED, got {s['status']}/{s['arena']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("ANALOGICAL_TRANSFER_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
