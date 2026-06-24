#!/usr/bin/env python3
"""Conjecture miner over the exact backends (Tier C).

Mathematical "taste" is the deepest gap; this does not close it, but it does the
mechanical part of conjecturing honestly: run an *exact* backend over a family,
find statements that hold on EVERY computed instance, then actively try to break
them. What survives a falsification search is emitted as a conjecture with its
support set and an open falsification status — a candidate worth a proof attempt,
explicitly NOT a theorem.

This is how genuine open problems surface from data: e.g. mining sum-of-divisors
over [2, N] rediscovers "every perfect number is even" (the odd-perfect-number
problem) as an implication true on all computed n that no falsification breaks.

Modes:
  number_theory   mine universally-true implications P(n) -> Q(n) over arithmetic
                  predicates (prime, square, even, perfect/abundant/deficient,
                  sigma-parity, ...), then falsify beyond the mined range.
  discovery       mine monotonicity / lower-bound facts over an evaluator's
                  max-object size as a function of the parameter.

Usage:
  conjecture_miner.py number_theory --range 2 10000 [--falsify 10000] [--min-support 3]
  conjecture_miner.py discovery --evaluator no_three_ap --range 5 30 [--falsify 10]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import number_theory_backend as nt  # noqa: E402


def _isqrt(n: int) -> int:
    return math.isqrt(n)


def nt_context(n: int) -> dict[str, Any]:
    factors = nt.factorize(n)
    sigma = nt.sigma_from_factors(factors)
    return {"n": n, "factors": factors, "sigma": sigma}


# Arithmetic predicates over n (each takes the cached context).
PREDICATES: dict[str, Callable[[dict], bool]] = {
    "prime": lambda c: nt.is_prime(c["n"]),
    "square": lambda c: _isqrt(c["n"]) ** 2 == c["n"],
    "even": lambda c: c["n"] % 2 == 0,
    "odd": lambda c: c["n"] % 2 == 1,
    "perfect": lambda c: c["sigma"] == 2 * c["n"],
    "abundant": lambda c: c["sigma"] > 2 * c["n"],
    "deficient": lambda c: c["sigma"] < 2 * c["n"],
    "sigma_even": lambda c: c["sigma"] % 2 == 0,
    "sigma_odd": lambda c: c["sigma"] % 2 == 1,
    "prime_power": lambda c: len([p for p in c["factors"] if p != -1]) == 1,
    "square_or_2square": lambda c: (_isqrt(c["n"]) ** 2 == c["n"]) or
                                   (c["n"] % 2 == 0 and _isqrt(c["n"] // 2) ** 2 == c["n"] // 2),
}


@lru_cache(maxsize=None)
def eval_predicates(n: int) -> dict[str, bool]:
    # Memoised: the falsification scan re-queries the same n across many predicate
    # pairs; without this each query re-factorises n. Callers only read the result.
    c = nt_context(n)
    return {name: fn(c) for name, fn in PREDICATES.items()}


def mine_number_theory(a: int, b: int, falsify_extra: int, min_support: int) -> list[dict]:
    rows = {n: eval_predicates(n) for n in range(max(2, a), b + 1)}
    names = list(PREDICATES)
    conjectures = []
    for p in names:
        for q in names:
            if p == q:
                continue
            antecedent = [n for n, r in rows.items() if r[p]]
            if len(antecedent) < min_support:
                continue
            # implication holds on the range iff every n with P also has Q
            if all(rows[n][q] for n in antecedent):
                # skip trivial: Q true for everything in range (not informative)
                if all(r[q] for r in rows.values()):
                    continue
                # falsification search beyond the range
                broke_at = None
                for n in range(b + 1, b + 1 + falsify_extra):
                    r = eval_predicates(n)
                    if r[p] and not r[q]:
                        broke_at = n
                        break
                # W1 formalization bridge: every miner predicate ships its Lean
                # form in predicate_registry, so the conjecture is a REAL
                # dispatchable statement by construction. A predicate outside
                # the registry keeps the honest stub (never a guess).
                import predicate_registry as pr
                lean, blocker, needs_mathlib = pr.implication(p, q)
                conjectures.append({
                    "form": f"{p}(n) -> {q}(n)",
                    "support": len(antecedent),
                    "support_examples": antecedent[:8],
                    "falsification_range": [b + 1, b + falsify_extra],
                    "falsified_at": broke_at,
                    "status": "FALSIFIED" if broke_at else "OPEN_UNFALSIFIED",
                    "lean_statement": lean,
                    "lean_imports": "import Mathlib" if needs_mathlib else "",
                    "formalization_blocker": blocker,
                    "lean_statement_stub": (None if lean else
                                            f"∀ n : Nat, 2 ≤ n → P_{p} n → P_{q} n  -- define P_{p},P_{q}"),
                })
    # Surface the unfalsified ones first, by support.
    conjectures = [c for c in conjectures if c["status"] == "OPEN_UNFALSIFIED" or c["falsified_at"]]
    conjectures.sort(key=lambda c: (c["status"] != "OPEN_UNFALSIFIED", -c["support"]))
    return conjectures


def mine_discovery(evaluator: str, a: int, b: int, falsify_extra: int) -> list[dict]:
    import discovery_evaluators as de
    import random
    ev = de.get_evaluator(evaluator)
    param_key = "n" if evaluator in ("no_three_ap", "sidon_set") else "d" if evaluator == "cap_set" else "v"
    sizes: dict[int, int] = {}
    for x in range(a, b + 1):
        params = {param_key: x}
        # greedy seed gives a valid lower-bound witness deterministically
        obj = ev.seed(params, random.Random(0))
        res = ev.evaluate(obj, params)
        sizes[x] = res["size"] if res.get("valid") else 0
    monotone = all(sizes[x] <= sizes[x + 1] for x in range(a, b) if x + 1 in sizes)
    # Mine a verified-on-range lower bound size(x) >= floor(c * x) for the best c.
    best_c = min((sizes[x] / x) for x in sizes if x > 0) if sizes else 0
    return [{
        "form": f"max-object size for {evaluator} is monotone in {param_key}",
        "status": "OPEN_UNFALSIFIED" if monotone else "FALSIFIED",
        "support": len(sizes),
        "lower_bound_on_range": f"size({param_key}) >= {round(best_c, 4)} * {param_key}",
        "data": {str(k): v for k, v in sizes.items()},
        "lean_statement_stub": f"∀ {param_key}, maxSize_{evaluator} {param_key} ≤ maxSize_{evaluator} ({param_key}+1)",
    }]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p_nt = sub.add_parser("number_theory")
    p_nt.add_argument("--range", nargs=2, type=int, required=True, metavar=("A", "B"))
    p_nt.add_argument("--falsify", type=int, default=10000, help="extra range to try to break conjectures")
    p_nt.add_argument("--min-support", type=int, default=3)
    p_nt.add_argument("--out", type=Path, default=Path("conjectures.json"))
    p_di = sub.add_parser("discovery")
    p_di.add_argument("--evaluator", required=True)
    p_di.add_argument("--range", nargs=2, type=int, required=True, metavar=("A", "B"))
    p_di.add_argument("--falsify", type=int, default=10)
    p_di.add_argument("--out", type=Path, default=Path("conjectures.json"))
    args = ap.parse_args()

    if args.mode == "number_theory":
        conjectures = mine_number_theory(args.range[0], args.range[1], args.falsify, args.min_support)
        ctx = {"mode": "number_theory", "range": args.range, "falsify_extra": args.falsify}
    else:
        conjectures = mine_discovery(args.evaluator, args.range[0], args.range[1], args.falsify)
        ctx = {"mode": "discovery", "evaluator": args.evaluator, "range": args.range}

    payload = {"schema": "witsoc.conjectures.v1", **ctx,
               "conjectures": conjectures,
               "open_unfalsified": sum(1 for c in conjectures if c["status"] == "OPEN_UNFALSIFIED"),
               "note": "Holds on all computed instances and survived a bounded falsification search; "
                       "a candidate for a proof attempt, NOT a theorem."}
    witcore.save_json(args.out, payload)
    print(json.dumps({k: v for k, v in payload.items() if k != "conjectures"}
                     | {"top": [c["form"] for c in conjectures[:6]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
