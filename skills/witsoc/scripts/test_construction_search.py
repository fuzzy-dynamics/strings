#!/usr/bin/env python3
"""Phase 3: construction search (deterministic, no Lean needed for the core checks).

Verifies the engine FINDS a certifying auxiliary object (a potential function) when
one exists, INDEPENDENTLY re-checks it, and — the calibration property — CANNOT
certify a false claim (a cyclic system has no potential function)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construction_search as cs
from discovery_evaluators import EVALUATORS, get_evaluator


def main() -> int:
    failures: list[str] = []

    if "potential_function" not in EVALUATORS:
        failures.append("potential_function evaluator must be registered")

    # 1. Acyclic system: a certifying potential exists -> CHECKED, score 1.0.
    acyclic = {"edges": [[0, 1], [1, 2], [2, 3], [0, 3], [0, 2]]}
    r = cs.build("potential_function", acyclic, generations=150, pop=24, seed=0)
    if not r["certified"] or r["status"] != "CHECKED" or r["score"] < 1.0:
        failures.append(f"acyclic system should be certified CHECKED, got {r['status']}/{r['score']}")
    else:
        # INDEPENDENT re-check: the evaluator must agree the construction is exact (not
        # trusting the search's own say-so).
        ev = get_evaluator("potential_function")
        v = ev.verify(r["best_construction"], acyclic)
        if not v.get("certifies_acyclic"):
            failures.append("the returned potential must independently satisfy EVERY edge")
        if not r["formalization_target"] or r["formalization_tactic"] != "by decide":
            failures.append("a certified construction must emit a `by decide` formalization target")

    # 2. CALIBRATION: a cyclic system has NO potential function -> never certified.
    cyclic = {"edges": [[0, 1], [1, 2], [2, 0]]}
    rc = cs.build("potential_function", cyclic, generations=300, pop=24, seed=0)
    if rc["certified"]:
        failures.append("a cyclic system must NEVER be certified (no potential function exists)")
    if rc["status"] != "FAILED_ATTEMPT" or rc["certificate"] is not None:
        failures.append(f"uncertified construction must be FAILED_ATTEMPT with no certificate, got {rc['status']}")

    # 3. The certificate's kernel form is exactly the per-edge strict decreases.
    if r.get("certified"):
        V = r["best_construction"]
        for (u, w) in acyclic["edges"]:
            if not (V[u] > V[w]):
                failures.append(f"certificate violated on edge {u}->{w}: V[{u}]={V[u]} !> V[{w}]={V[w]}")

    # 4. A larger random DAG still gets certified (the search scales a bit).
    dag = {"edges": [[i, j] for i in range(6) for j in range(6) if i < j]}  # transitive tournament = a DAG
    rd = cs.build("potential_function", dag, generations=300, pop=30, seed=1)
    if not rd["certified"]:
        failures.append(f"a 6-node DAG should be certifiable, got score {rd['score']}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("CONSTRUCTION_SEARCH_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
