#!/usr/bin/env python3
"""Phase 2: type-aware premise retrieval + a premise hit-rate (recall@K) harness.

The host has no Mathlib, so this measures the RETRIEVAL ALGORITHM on a synthetic
atlas fixture (a real Mathlib checkout would replace the fixture, same code). The
key upgrade: an exact symbol-overlap signal so a goal that NAMES `Nat.divisors`
retrieves the divisors module even when doc words point elsewhere — without
disturbing core goals that name no qualified symbol (symbol-overlap 0 => the old
cosine ranking)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mathlib_atlas as ma

ATLAS = {"nodes": [
    {"module": "M.NumberTheory.Divisors", "symbols": ["Nat.divisors", "Nat.sigma", "Nat.Perfect"],
     "doc": "divisors and the sum of divisors sigma", "imports": []},
    {"module": "M.NumberTheory.Prime", "symbols": ["Nat.Prime", "Nat.factors"],
     "doc": "primality and prime factorization", "imports": []},
    {"module": "M.Data.List.Basic", "symbols": ["List.reverse", "List.length", "List.append"],
     "doc": "basic operations on lists", "imports": []},
    {"module": "M.Algebra.BigOperators", "symbols": ["Finset.sum", "Finset.prod"],
     "doc": "sums and products over a finite set", "imports": []},
    {"module": "M.Data.Nat.Basic", "symbols": ["Nat", "Nat.succ", "Nat.add_comm"],
     "doc": "natural number basics, sums of naturals", "imports": []},
]}

# (goal text, the module that actually provides the needed premise)
QUERIES = [
    ("∀ n : Nat, Nat.divisors n = Nat.divisors n", "M.NumberTheory.Divisors"),
    ("∀ p : Nat, Nat.Prime p → 2 ≤ p", "M.NumberTheory.Prime"),
    ("∀ (l : List Nat), List.reverse (List.reverse l) = l", "M.Data.List.Basic"),
    ("∑ x ∈ s, f x = 0", "M.Algebra.BigOperators"),  # notation ∑ -> Finset.sum
]


def top_modules(query: str, k: int) -> list[str]:
    res = ma.query_atlas(ATLAS, query, "", k)
    return [m["module"] for m in res.get("matches", [])]


def main() -> int:
    failures: list[str] = []

    # Recall@1 and Recall@3 over the fixture (the measurement).
    hit1 = sum(1 for q, exp in QUERIES if exp in top_modules(q, 1))
    hit3 = sum(1 for q, exp in QUERIES if exp in top_modules(q, 3))
    r1, r3 = hit1 / len(QUERIES), hit3 / len(QUERIES)
    print(f"premise retrieval: recall@1={r1:.2f} recall@3={r3:.2f} ({hit1}/{len(QUERIES)}, {hit3}/{len(QUERIES)})")
    if r1 < 1.0:
        failures.append(f"type-aware retrieval should get recall@1=1.0 on the fixture, got {r1}")

    # Discriminating case: doc words ("sum", "naturals") overlap MORE with Nat.Basic,
    # but the goal NAMES Nat.divisors — symbol-aware retrieval must still pick Divisors.
    misleading = "sum over naturals of Nat.divisors n basics"
    top = top_modules(misleading, 1)
    if top[:1] != ["M.NumberTheory.Divisors"]:
        failures.append(f"named symbol must beat doc-word overlap, top was {top[:1]}")

    # No-regression: a goal naming NO qualified symbol has symbol-overlap 0 on every
    # node, so ranking reduces to the previous cosine+pagerank order.
    res = ma.query_atlas(ATLAS, "a * b = b * a commutative", "", 5)
    if any(m["symbol_overlap"] != 0.0 for m in res["matches"]):
        failures.append("a goal with no qualified symbols must have symbol_overlap 0 everywhere")

    # The generic namespace root `Nat` must NOT count as providing `Nat.divisors`.
    if ma.symbol_overlap({"Nat.divisors"}, {"symbols": ["Nat", "Nat.succ"]}) != 0.0:
        failures.append("a namespace root must not match a specific lemma symbol")
    if ma.symbol_overlap({"Nat.divisors"}, {"symbols": ["Nat.divisors_eq"]}) <= 0.0:
        failures.append("a same-family lemma (Nat.divisors_eq) should match Nat.divisors")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("PREMISE_RETRIEVAL_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
