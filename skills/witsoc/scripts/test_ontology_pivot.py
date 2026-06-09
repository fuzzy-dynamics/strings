#!/usr/bin/env python3
"""Phase 4: the adversarial ontology pivot (deterministic, no Lean).

Checks a stuck barrier maps to the RIGHT orthogonal domain with a usable theory, that
proposals are structurally SPECULATIVE (a direction, never a result), and that the
dispatcher exposes it as an informational (L0) approach."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ontology_pivot as op
import engine_dispatch as ed


def targets(statement, domain=""):
    return [p["target_domain"] for p in op.pivots(statement, domain, k=3)]


def main() -> int:
    failures: list[str] = []

    # 1. Graph barrier -> spectral / polynomial method.
    t = targets("the maximum number of edges in a triangle-free graph on n vertices", "graph_theory")
    if "spectral_graph_theory" not in t:
        failures.append(f"a graph barrier should pivot to spectral graph theory, got {t}")

    # 2. Number-theory barrier -> finite algebra / Fourier.
    t = targets("∀ n, perfect n → even n (sum of divisors)", "number_theory")
    if not ({"finite_algebra", "additive_fourier"} & set(t)):
        failures.append(f"a number-theory barrier should pivot to finite algebra / Fourier, got {t}")

    # 3. Additive-combinatorics barrier -> Fourier / ergodic.
    t = targets("a set with no 3-term arithmetic progression and density at least c", "additive_combinatorics")
    if not ({"fourier_linear_algebra", "ergodic_dynamics"} & set(t)):
        failures.append(f"an additive barrier should pivot to Fourier/ergodic, got {t}")

    # 4. Domain inference from the statement text alone (no explicit domain).
    if op.infer_domain("a triangle-free graph with chromatic number k") != "graph_theory":
        failures.append("domain inference should detect graph_theory from the statement")

    # 5. CALIBRATION: every pivot is a SPECULATIVE direction with a preservation law and
    #    a reflected obstruction — never a result.
    res = op.suggest("∀ n, perfect n → even n", "number_theory")
    for p in res["pivots"]:
        if p["status"] != op.OPEN or p["arena"] != op.ARENA:
            failures.append("a pivot must be OPEN_UNFALSIFIED/SPECULATIVE")
        if not p.get("preservation_law") or not p.get("reflected_obstruction") or not p.get("unlocks_theory"):
            failures.append("a pivot must state the preservation law, the unlocked theory, and the reflected obstruction")

    # 6. Dispatcher integration: ontology_pivot is an informational (L0) approach that
    #    records leads in context, never advancing the rung.
    d = ed.EngineDispatcher("a triangle-free graph on n vertices", domain="graph_theory",
                            prover=lambda s, imports="": {"discharged": False})
    out = d.execute("ontology_pivot", "t")
    if out["rung"] != "L0" or out["status"] != "pivots_suggested":
        failures.append(f"ontology_pivot must be an informational L0 approach, got {out}")
    if "spectral_graph_theory" not in (out.get("evidence") or []):
        failures.append("the dispatcher should surface the spectral pivot for a graph goal")
    if not d.context.get("pivots"):
        failures.append("ontology_pivot must record pivot leads into the campaign context")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("ONTOLOGY_PIVOT_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
