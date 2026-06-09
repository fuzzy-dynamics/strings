#!/usr/bin/env python3
"""Phase 3 (idea generator): construction search — invent the auxiliary object.

witsoc's trust root only FILTERS; the hard part of an open problem is PRODUCING the
construction (invariant, potential/ranking function, gadget, extremal config) the
proof turns on. This searches that space with the discovery-engine evaluator
interface and hands a kernel-checkable artifact to the Prover.

GENERATION vs JUDGEMENT (the calibration spine): generation (seed/mutate/crossover)
is cheap and untrusted; the DETERMINISTIC evaluator is the sole judge. A construction
is `CHECKED` only when the evaluator certifies it exactly (score 1.0); the evaluator
cannot certify a false claim (e.g. no potential function certifies a CYCLIC system),
so the search can never manufacture a solve. The emitted `formalization_target` is the
certificate's Lean form (a finite `by decide` goal) for an independent kernel re-check.

Usage:
  construction_search.py --evaluator potential_function --params '{"edges":[[0,1],[1,2]]}'
      [--generations 120] [--pop 24] [--seed 0] [--out construction.json]
  construction_search.py --list
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from discovery_evaluators import EVALUATORS, get_evaluator  # noqa: E402


def search(evaluator: str, params: dict, generations: int, pop: int, seed: int) -> dict | None:
    """A small deterministic evolutionary search over the construction space using the
    evaluator interface (the same one discovery_engine drives at island scale)."""
    ev = get_evaluator(evaluator)
    rng = random.Random(seed)

    def scored(obj):
        r = ev.evaluate(obj, params)
        return (r["score"], r["size"], obj) if r.get("valid") else None

    population = [m for m in (scored(ev.seed(params, rng)) for _ in range(pop)) if m]
    for _ in range(generations):
        population.sort(key=lambda m: (-m[0], m[1]))
        population = population[:pop]
        if population and population[0][0] >= 1.0:
            break  # certified — the evaluator accepts it exactly
        parents = population[: max(2, pop // 2)] or population
        children = []
        for _ in range(pop):
            if len(parents) >= 2 and rng.random() < 0.5:
                a, b = rng.sample(parents, 2)
                obj = ev.crossover(a[2], b[2], params, rng)
            elif parents:
                obj = ev.mutate(rng.choice(parents)[2], params, rng)
            else:
                obj = ev.seed(params, rng)
            m = scored(obj)
            if m:
                children.append(m)
        population += children
    population.sort(key=lambda m: (-m[0], m[1]))
    return {"score": population[0][0], "size": population[0][1], "object": population[0][2]} if population else None


def _decide_target(evaluator: str, params: dict, obj: list) -> str | None:
    """The certificate's kernel form: for a potential function, the finite conjunction
    of strict decreases V[u] > V[v] (a `by decide` goal the Prover re-checks)."""
    if evaluator != "potential_function":
        return None
    edges = [tuple(int(x) for x in e) for e in params.get("edges", [])]
    if not edges:
        return None
    conj = " ∧ ".join(f"({obj[u]} > {obj[v]})" for (u, v) in edges)
    return conj


def build(evaluator: str, params: dict, generations: int, pop: int, seed: int) -> dict:
    best = search(evaluator, params, generations, pop, seed)
    if best is None:
        return {"schema": "witsoc.construction_search.v1", "evaluator": evaluator,
                "certified": False, "status": "FAILED_ATTEMPT", "reason": "no valid construction found"}
    ev = get_evaluator(evaluator)
    cert = ev.evaluate(best["object"], params).get("certificate", {})
    certified = best["score"] >= 1.0
    out = {
        "schema": "witsoc.construction_search.v1",
        "evaluator": evaluator,
        "objective": getattr(ev, "objective", "maximize"),
        "best_construction": best["object"],
        "score": round(best["score"], 4),
        "certified": certified,
        "certificate": cert if certified else None,
        # CHECKED only when the evaluator certifies exactly; else honest negative.
        "status": "CHECKED" if certified else "FAILED_ATTEMPT",
        "formalization_target": (_decide_target(evaluator, params, best["object"]) if certified else None),
        "formalization_tactic": "by decide" if certified else None,
        "calibration": ("a construction is CHECKED only when the deterministic evaluator certifies it "
                        "exactly (score 1.0); the evaluator is the sole judge and cannot certify a false "
                        "claim (e.g. no potential function certifies a cyclic system)."),
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evaluator", help="construction evaluator (e.g. potential_function)")
    ap.add_argument("--params", default="{}", help="JSON params for the evaluator")
    ap.add_argument("--generations", type=int, default=120)
    ap.add_argument("--pop", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--list", action="store_true", help="list available evaluators")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.list:
        print(json.dumps({"evaluators": sorted(EVALUATORS)}, indent=2))
        return 0
    if not args.evaluator:
        print("--evaluator required (or --list)", file=sys.stderr)
        return 2
    result = build(args.evaluator, json.loads(args.params), args.generations, args.pop, args.seed)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("certified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
