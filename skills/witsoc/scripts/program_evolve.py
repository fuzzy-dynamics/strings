#!/usr/bin/env python3
"""A4 program-space construction evolution — `witsoc evolve`.

The FunSearch/AlphaEvolve recipe — the proven route to record bounds (cap
sets, kissing numbers, Ramsey constructions): evolve PROGRAMS that generate
objects, not the objects themselves; programs are compact, generalizable,
and the fleet can mutate them meaningfully. Lessons from Tao's AlphaEvolve
methodology baked in as enforced contract:

  EXPLOIT-HARDENED EVALUATORS  the single critical engineering ("AlphaEvolve
    is extremely good at locating exploits"): exact integer arithmetic only,
    admissibility violations raise ERRORS (never scored), conservative
    timeouts, and every record claim is independently RE-VERIFIED by a fresh
    evaluation before it appears in the report;
  PARAMETRIC GENERALIZATION  programs implement `construct(n)`; fitness is
    the score VECTOR across an n-grid, so constructions that generalize beat
    point solutions, and the best program's objects at each n are reported
    for kernel-bridging;
  RICH PROMPTS  every fleet mutation request carries the evaluator
    definition, the current best programs WITH scores, and the problem theory.

Restricted execution: candidate code runs in a whitelisted namespace (math,
itertools, Fraction, comprehensions) with forbidden-token screening and a
time budget — the fleet is operator-configured, the screen catches accidents.
Trust: everything here is CHECKED-grade construction evidence at most; the
kernel bridge (sat/decide) is the only upgrade path.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import sampler_fleet as sf  # noqa: E402
import witcore  # noqa: E402

FORBIDDEN_TOKENS = ("import", "__", "open(", "exec", "eval", "getattr", "setattr",
                    "globals", "locals", "compile", "input", "os.", "sys.")
EVAL_TIME_BUDGET = 5.0


class Inadmissible(Exception):
    """Admissibility violations are ERRORS, never scores (the anti-exploit rule)."""


# --- exploit-hardened evaluators (exact integer arithmetic only) -----------------
def _check_subset(obj: Any, n: int) -> list[int]:
    if not isinstance(obj, (list, set, tuple)):
        raise Inadmissible(f"construct({n}) must return a collection of ints")
    items = list(obj)
    if any(not isinstance(x, int) or isinstance(x, bool) for x in items):
        raise Inadmissible("non-integer element (exact arithmetic only)")
    if len(set(items)) != len(items):
        raise Inadmissible("duplicate elements")
    if any(x < 1 or x > n for x in items):
        raise Inadmissible(f"element outside [1, {n}]")
    return sorted(items)


def eval_sum_free(obj: Any, n: int) -> dict:
    """Largest sum-free subset of [1..n]: no x + y = z (x, y, z in the set)."""
    items = _check_subset(obj, n)
    member = set(items)
    for x in items:
        for y in items:
            if x <= y and (x + y) in member:
                raise Inadmissible(f"not sum-free: {x} + {y} = {x + y}")
    return {"score": len(items), "object": items}


def eval_ap_free(obj: Any, n: int) -> dict:
    """Largest subset of [1..n] with no 3-term arithmetic progression."""
    items = _check_subset(obj, n)
    member = set(items)
    for x in items:
        for y in items:
            if x < y and (2 * y - x) in member:
                raise Inadmissible(f"3-AP: {x}, {y}, {2 * y - x}")
    return {"score": len(items), "object": items}


def eval_sidon(obj: Any, n: int) -> dict:
    """Largest Sidon set in [1..n]: pairwise sums all distinct."""
    items = _check_subset(obj, n)
    sums: set[int] = set()
    for i, x in enumerate(items):
        for y in items[i:]:
            if (x + y) in sums:
                raise Inadmissible(f"repeated pairwise sum {x + y}")
            sums.add(x + y)
    return {"score": len(items), "object": items}


def eval_min_overlap(obj: Any, n: int) -> dict:
    """Erdős minimum-overlap problem (an AlphaEvolve-verified target shape):
    A ⊆ [1..2n] with |A| = n; B = complement; M(A) = max_k |{(a,b) ∈ A×B :
    a − b = k}|. Score is −M so the shared maximize-mean fitness MINIMIZES the
    overlap. Exact integer counting only."""
    items = _check_subset(obj, 2 * n)
    if len(items) != n:
        raise Inadmissible(f"|A| must be exactly n={n}, got {len(items)}")
    a_set = set(items)
    b = [x for x in range(1, 2 * n + 1) if x not in a_set]
    counts: dict[int, int] = {}
    for x in items:
        for y in b:
            k = x - y
            counts[k] = counts.get(k, 0) + 1
    m = max(counts.values()) if counts else 0
    return {"score": -m, "object": items}


def eval_difference_basis(obj: Any, n: int) -> dict:
    """Smallest restricted difference basis: A ⊆ [0..n] whose pairwise
    differences cover every d ∈ [1..n] (admissibility — a non-covering set is
    an ERROR, never a score). Score is −|A| so maximizing minimizes size.
    Sparse rulers / perfect difference sets territory."""
    if not isinstance(obj, (list, tuple)):
        raise Inadmissible("construct(n) must return a list")
    items = sorted({int(x) for x in obj})
    if any(not 0 <= x <= n for x in items):
        raise Inadmissible("elements must lie in [0..n]")
    diffs = {abs(x - y) for i, x in enumerate(items) for y in items[i + 1:]}
    missing = next((d for d in range(1, n + 1) if d not in diffs), None)
    if missing is not None:
        raise Inadmissible(f"difference {missing} not covered")
    return {"score": -len(items), "object": items}


EVALUATORS: dict[str, dict] = {
    "sum_free": {"fn": eval_sum_free, "maximize": True,
                 "description": "largest subset of [1..n] with no x+y=z inside the set"},
    "ap_free": {"fn": eval_ap_free, "maximize": True,
                "description": "largest subset of [1..n] with no 3-term arithmetic progression"},
    "sidon": {"fn": eval_sidon, "maximize": True,
              "description": "largest Sidon set in [1..n] (all pairwise sums distinct)"},
    "min_overlap": {"fn": eval_min_overlap, "maximize": True,
                    "description": "Erdős minimum overlap: choose A (|A|=n) in [1..2n] minimizing "
                                   "max_k #{(a,b) in A x complement : a-b=k}; score = -M(A)",
                    "seeds": ["def construct(n):\n    return list(range(1, n + 1))"]},
    "difference_basis": {"fn": eval_difference_basis, "maximize": True,
                         "description": "smallest A in [0..n] whose pairwise differences cover "
                                        "1..n (sparse ruler); score = -|A|; non-coverage is "
                                        "inadmissible, never a penalty",
                         "seeds": ["def construct(n):\n    return list(range(0, n + 1))"]},
}

SEED_PROGRAMS = [
    "def construct(n):\n    return [x for x in range(1, n + 1) if x > n // 2]",  # top half (sum-free classic)
    "def construct(n):\n    return [x for x in range(1, n + 1) if x % 2 == 1]",  # odds (sum-free classic)
    "def construct(n):\n    return [1] if n >= 1 else []",                       # minimal admissible
]


# --- restricted execution ---------------------------------------------------------
def run_program(code: str, n: int) -> Any:
    if any(t in code for t in FORBIDDEN_TOKENS):
        raise Inadmissible("forbidden token in program")
    namespace: dict[str, Any] = {
        "__builtins__": {"range": range, "len": len, "set": set, "list": list, "sorted": sorted,
                         "min": min, "max": max, "sum": sum, "abs": abs, "enumerate": enumerate,
                         "int": int, "True": True, "False": False, "zip": zip, "all": all, "any": any},
        "math": math, "itertools": itertools, "Fraction": Fraction,
    }
    exec(code, namespace)  # operator-configured fleet; token screen catches accidents
    construct = namespace.get("construct")
    if not callable(construct):
        raise Inadmissible("program defines no construct(n)")
    start = time.time()
    result = construct(n)
    if time.time() - start > EVAL_TIME_BUDGET:
        raise Inadmissible("evaluation time budget exceeded")
    return result


def score_program(code: str, evaluator: dict, n_grid: list[int]) -> dict:
    """Score VECTOR across the n-grid; any inadmissibility poisons the program."""
    scores: dict[str, int] = {}
    objects: dict[str, list[int]] = {}
    for n in n_grid:
        try:
            out = evaluator["fn"](run_program(code, n), n)
        except Inadmissible as exc:
            return {"admissible": False, "reason": f"n={n}: {exc}"}
        except Exception as exc:
            return {"admissible": False, "reason": f"n={n}: {type(exc).__name__}: {exc}"}
        scores[str(n)] = out["score"]
        objects[str(n)] = out["object"]
    fitness = sum(scores.values()) / len(scores)
    return {"admissible": True, "scores": scores, "fitness": round(fitness, 4), "objects": objects}


def _descriptor(p: dict) -> tuple:
    """Behavior bin for diversity retention: program-size bucket x the shape of
    the score curve (which n it does best at, relative to the others). Two
    programs in the same bin compete; different bins coexist."""
    code = str(p.get("program") or "")
    scores = p.get("scores") or {}
    best_n = max(scores, key=lambda k: scores[k]) if scores else ""
    return (len(code) // 120, best_n)


def _elite_retention(population: list[dict], cap: int = 12) -> list[dict]:
    """MAP-elites-lite: keep the best program PER BEHAVIOR BIN first, then fill
    remaining slots by raw fitness. Best-only truncation collapses the search
    into one basin; elites keep structurally different approaches alive."""
    seen_bins: set[tuple] = set()
    elites: list[dict] = []
    rest: list[dict] = []
    for p in population:  # population arrives fitness-sorted
        d = _descriptor(p)
        if d not in seen_bins:
            seen_bins.add(d)
            elites.append(p)
        else:
            rest.append(p)
    out = (elites + rest)[:cap]
    out.sort(key=lambda p: -p["fitness"])
    return out


def _diverse_elites(population: list[dict], exclude_top: int, rotate: int) -> list[dict]:
    """Inspiration picks: elites from bins OTHER than the leaders', rotated
    deterministically by generation so successive prompts see different bins."""
    top_bins = {_descriptor(p) for p in population[:exclude_top]}
    others = [p for p in population[exclude_top:] if _descriptor(p) not in top_bins]
    if not others:
        return []
    start = rotate % len(others)
    return others[start:] + others[:start]


def evolve(evaluator_name: str, *, generations: int = 4, n_grid: list[int] | None = None,
           seeds: list[str] | None = None, theory: dict | None = None,
           per_sampler: int = 1) -> dict:
    evaluator = EVALUATORS[evaluator_name]
    n_grid = n_grid or [12, 24, 48]
    population: list[dict] = []
    for code in (seeds or SEED_PROGRAMS) + list(evaluator.get("seeds") or []):
        s = score_program(code, evaluator, n_grid)
        if s.get("admissible"):
            population.append({"program": code, **s, "origin": "seed"})
    population.sort(key=lambda p: -p["fitness"])

    fleet = sf.samplers()
    history: list[dict] = []
    for gen in range(1, generations + 1):
        if not fleet:
            history.append({"generation": gen, "note": "no sampler fleet; seeds only"})
            break
        # P3 diversity sampling (MAP-elites-lite): the prompt carries the top
        # performers PLUS rotating elites from OTHER behavior bins, so the
        # fleet cross-pollinates instead of hill-climbing one basin.
        diverse = _diverse_elites(population, exclude_top=2, rotate=gen)
        request = {
            "task": "evolve_program",
            "evaluator": {"name": evaluator_name, "description": evaluator["description"],
                          "contract": "define construct(n) -> list[int]; admissibility violations "
                                      "score NOTHING (errors, not penalties); exact ints only"},
            "n_grid": n_grid,
            "best_programs": [{"program": p["program"], "fitness": p["fitness"],
                               "scores": p["scores"]} for p in population[:2]],
            "inspiration_programs": [{"program": p["program"], "fitness": p["fitness"],
                                      "note": "structurally different elite — graft ideas, don't copy"}
                                     for p in diverse[:2]],
            "problem_theory": theory or {},
            "rules": "Return {program: \"def construct(n): ...\"} — improve on the best programs, "
                     "or combine them with the inspiration programs' ideas. Generalize across n; "
                     "no imports.",
        }
        improved = 0
        for result in sf.sample(request, per_sampler=per_sampler):
            code = str(result["reply"].get("program") or "")
            if not code.strip():
                continue
            s = score_program(code, evaluator, n_grid)
            if s.get("admissible"):
                population.append({"program": code, **s,
                                   "origin": f"fleet:{result['sampler_id']}@gen{gen}"})
                improved += 1
        population.sort(key=lambda p: -p["fitness"])
        population = _elite_retention(population, cap=12)
        history.append({"generation": gen, "admissible_offspring": improved,
                        "best_fitness": population[0]["fitness"] if population else None,
                        "behavior_bins": len({_descriptor(p) for p in population})})

    best = population[0] if population else None
    reverified = None
    if best:
        # Tao's rule: never trust the search's own score — independently
        # re-verify the record claim with a fresh evaluation.
        reverified = score_program(best["program"], evaluator, n_grid)
    return {
        "schema": "witsoc.program_evolve.v1",
        "evaluator": evaluator_name,
        "n_grid": n_grid,
        "generations_run": len(history),
        "history": history,
        "best": ({"program": best["program"], "fitness": best["fitness"],
                  "scores": best["scores"], "origin": best["origin"],
                  "objects": best["objects"]} if best else None),
        "reverified": ({"ok": bool(reverified.get("admissible"))
                              and reverified.get("scores") == best.get("scores"),
                        "detail": reverified} if best else None),
        "trust": "CHECKED-grade construction evidence at most; kernel bridge is the upgrade path",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evaluator", choices=sorted(EVALUATORS), required=True)
    ap.add_argument("--generations", type=int, default=4)
    ap.add_argument("--n-grid", default="12,24,48")
    ap.add_argument("--per-sampler", type=int, default=1)
    ap.add_argument("--run-dir", type=Path, default=None, help="embed this run's problem theory")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    theory = None
    if args.run_dir is not None:
        try:
            import problem_theory as pt
            if pt.theory_path(args.run_dir).exists():
                theory = pt.prompt_context(args.run_dir)
        except Exception:
            theory = None
    report = evolve(args.evaluator, generations=args.generations,
                    n_grid=[int(x) for x in args.n_grid.split(",")],
                    theory=theory, per_sampler=args.per_sampler)
    if args.out:
        witcore.save_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
