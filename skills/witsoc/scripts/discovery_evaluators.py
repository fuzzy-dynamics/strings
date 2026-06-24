#!/usr/bin/env python3
"""Hard, deterministic evaluators for the Witsoc discovery engine.

This module is the *moat* of the discovery engine: it scores candidate
mathematical objects with exact, deterministic checks. No LLM judgement is
involved anywhere in this file. A candidate is either valid or not, and its
fitness is a number derived from the object itself.

Each evaluator targets an Erdos-flavoured extremal/existence problem where the
answer is an explicit finite object (a construction or counterexample):

- cap_set                 : largest cap (no 3 collinear points) in F_3^d.
- no_three_ap             : largest subset of {0..n-1} with no 3-term AP
                            (Erdos-Turan).
- sidon_set               : largest B_2 / Sidon set in {1..n} (Erdos-Turan).
- triangle_free_chromatic : triangle-free graph on v vertices of maximum
                            chromatic number (Erdos: high girth + high chi).

All four properties are *hereditary* (any subset/subgraph of a valid object is
valid), which the evolutionary engine relies on for crossover by intersection.

Every evaluator exposes:
  describe(params)               -> str   (problem statement, used in LLM prompts)
  universe(params)               -> list  (the ground set the search lives in)
  seed(params, rng)              -> object (a valid starting candidate)
  mutate(object, params, rng)    -> object (a valid neighbour)
  crossover(a, b, params, rng)   -> object (a valid recombination)
  evaluate(object, params)       -> dict   ({valid, score, size, certificate})
  verify(object, params)         -> dict   (INDEPENDENT re-check of validity)
  objective                      = "maximize"

Objects are always canonical JSON-serialisable lists so they round-trip through
the engine's checkpoint files.

CLI:
  python3 discovery_evaluators.py list
  python3 discovery_evaluators.py describe --evaluator cap_set --params '{"d":4}'
  python3 discovery_evaluators.py evaluate --evaluator cap_set --params '{"d":4}' --object '[[0,0,0,0]]'
  python3 discovery_evaluators.py verify   --evaluator cap_set --params '{"d":4}' --object '<json>'
  python3 discovery_evaluators.py seed     --evaluator no_three_ap --params '{"n":40}' --seed 1
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path
from typing import Any, Callable

# Reuse the exact bounded graph routines for the chromatic evaluator.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # pragma: no cover - import guard
    from finite_graph_backend import adjacency, chromatic_number, triangle_free
except Exception:  # pragma: no cover - fallback if backend missing
    adjacency = chromatic_number = triangle_free = None  # type: ignore


# ---------------------------------------------------------------------------
# Generic greedy extension shared by all hereditary evaluators.
# ---------------------------------------------------------------------------
def greedy_extend(state: set, order: list, addable: Callable[[set, Any], bool]) -> set:
    """Add elements from `order` to `state` while validity (addable) holds."""
    for element in order:
        if element in state:
            continue
        if addable(state, element):
            state.add(element)
    return state


# ===========================================================================
# Evaluator: cap_set  (no three collinear points in F_3^d)
# ===========================================================================
class CapSet:
    name = "cap_set"
    objective = "maximize"
    domain = "additive-combinatorics"

    @staticmethod
    def _d(params: dict) -> int:
        return int(params.get("d", 4))

    @classmethod
    def describe(cls, params: dict) -> str:
        d = cls._d(params)
        return (
            f"Find the largest possible cap set in F_3^{d}: a set S of points in "
            f"{{0,1,2}}^{d} containing no three distinct collinear points "
            f"(equivalently no three distinct points a,b,c with a+b+c = 0 mod 3). "
            f"Maximise |S|. Known optimum is fragile; improving lower bounds for "
            f"large d is an open research target (cf. cap set / Erdos-Szemeredi)."
        )

    @classmethod
    def universe(cls, params: dict) -> list:
        d = cls._d(params)
        return [tuple(p) for p in itertools.product(range(3), repeat=d)]

    @staticmethod
    def _third(p: tuple, a: tuple) -> tuple:
        return tuple((-(p[i] + a[i])) % 3 for i in range(len(p)))

    @classmethod
    def _addable(cls, state: set, p: tuple) -> bool:
        # p is addable iff no existing a yields the collinearity-closing point in S.
        for a in state:
            if cls._third(p, a) in state:
                return False
        return True

    @classmethod
    def seed(cls, params: dict, rng: random.Random) -> list:
        order = cls.universe(params)
        rng.shuffle(order)
        state = greedy_extend(set(), order, cls._addable)
        return cls._canon(state)

    @classmethod
    def mutate(cls, obj: list, params: dict, rng: random.Random) -> list:
        state = {tuple(x) for x in obj}
        # Remove a small random subset to escape local maxima, then re-extend.
        if state:
            k = rng.randint(1, max(1, min(3, len(state))))
            for x in rng.sample(list(state), k):
                state.discard(x)
        order = cls.universe(params)
        rng.shuffle(order)
        greedy_extend(state, order, cls._addable)
        return cls._canon(state)

    @classmethod
    def crossover(cls, a: list, b: list, params: dict, rng: random.Random) -> list:
        # Intersection of two valid caps is a valid cap (heredity); then extend.
        sa = {tuple(x) for x in a}
        sb = {tuple(x) for x in b}
        state = sa & sb
        order = cls.universe(params)
        rng.shuffle(order)
        greedy_extend(state, order, cls._addable)
        return cls._canon(state)

    @staticmethod
    def _canon(state: set) -> list:
        return [list(p) for p in sorted(state)]

    @classmethod
    def verify(cls, obj: list, params: dict) -> dict:
        d = cls._d(params)
        pts = [tuple(x) for x in obj]
        if any(len(p) != d or any(c not in (0, 1, 2) for c in p) for p in pts):
            return {"ok": False, "reason": "point outside {0,1,2}^d"}
        if len(set(pts)) != len(pts):
            return {"ok": False, "reason": "duplicate points"}
        s = set(pts)
        # Independent O(|S|^3) brute-force check of every triple.
        for a, b, c in itertools.combinations(pts, 3):
            if all((a[i] + b[i] + c[i]) % 3 == 0 for i in range(d)):
                return {"ok": False, "reason": f"collinear triple {a},{b},{c}"}
        return {"ok": True, "size": len(s), "method": "brute-force triple scan"}

    @classmethod
    def evaluate(cls, obj: list, params: dict) -> dict:
        v = cls.verify(obj, params)
        if not v.get("ok"):
            return {"valid": False, "score": float("-inf"), "size": 0, "reason": v.get("reason")}
        size = len(obj)
        return {
            "valid": True,
            "score": float(size),
            "size": size,
            "certificate": {
                "problem": f"cap_set F_3^{cls._d(params)}",
                "points": obj,
                "size": size,
                "independent_verifier": "brute-force triple scan",
            },
        }


# ===========================================================================
# Evaluator: no_three_ap  (Erdos-Turan: no 3-term arithmetic progression)
# ===========================================================================
class NoThreeAP:
    name = "no_three_ap"
    objective = "maximize"
    domain = "additive-combinatorics"

    @staticmethod
    def _n(params: dict) -> int:
        return int(params.get("n", 40))

    @classmethod
    def describe(cls, params: dict) -> str:
        n = cls._n(params)
        return (
            f"Find the largest subset S of {{0,1,...,{n - 1}}} containing no "
            f"3-term arithmetic progression (no distinct a, a+d, a+2d all in S). "
            f"Maximise |S|. This is the Erdos-Turan problem r_3(n); dense "
            f"constructions (Behrend) are an active research lower-bound target."
        )

    @classmethod
    def universe(cls, params: dict) -> list:
        return list(range(cls._n(params)))

    @staticmethod
    def _addable(state: set, x: int) -> bool:
        # x must not be the middle of an AP nor an endpoint of one.
        for a in state:
            if (2 * x - a) in state:  # x middle: a, x, 2x-a
                return False
            if (2 * a - x) in state:  # a middle: x, a, 2a-x
                return False
        return True

    @classmethod
    def seed(cls, params: dict, rng: random.Random) -> list:
        order = cls.universe(params)
        rng.shuffle(order)
        return sorted(greedy_extend(set(), order, cls._addable))

    @classmethod
    def mutate(cls, obj: list, params: dict, rng: random.Random) -> list:
        state = set(obj)
        if state:
            k = rng.randint(1, max(1, min(3, len(state))))
            for x in rng.sample(list(state), k):
                state.discard(x)
        order = cls.universe(params)
        rng.shuffle(order)
        greedy_extend(state, order, cls._addable)
        return sorted(state)

    @classmethod
    def crossover(cls, a: list, b: list, params: dict, rng: random.Random) -> list:
        state = set(a) & set(b)
        order = cls.universe(params)
        rng.shuffle(order)
        greedy_extend(state, order, cls._addable)
        return sorted(state)

    @classmethod
    def verify(cls, obj: list, params: dict) -> dict:
        n = cls._n(params)
        if any((not isinstance(x, int)) or x < 0 or x >= n for x in obj):
            return {"ok": False, "reason": "element outside [0,n)"}
        if len(set(obj)) != len(obj):
            return {"ok": False, "reason": "duplicate element"}
        s = set(obj)
        srt = sorted(s)
        for i, a in enumerate(srt):
            for c in srt[i + 1:]:
                if (a + c) % 2 == 0 and (a + c) // 2 in s and (a + c) // 2 not in (a, c):
                    return {"ok": False, "reason": f"3-AP {a},{(a + c) // 2},{c}"}
        return {"ok": True, "size": len(s), "method": "brute-force AP scan"}

    @classmethod
    def evaluate(cls, obj: list, params: dict) -> dict:
        v = cls.verify(obj, params)
        if not v.get("ok"):
            return {"valid": False, "score": float("-inf"), "size": 0, "reason": v.get("reason")}
        size = len(obj)
        return {
            "valid": True,
            "score": float(size),
            "size": size,
            "certificate": {
                "problem": f"no_three_ap [0,{cls._n(params)})",
                "set": obj,
                "size": size,
                "independent_verifier": "brute-force AP scan",
            },
        }


# ===========================================================================
# Evaluator: sidon_set  (Erdos-Turan B_2 set: distinct pairwise sums)
# ===========================================================================
class SidonSet:
    name = "sidon_set"
    objective = "maximize"
    domain = "additive-combinatorics"

    @staticmethod
    def _n(params: dict) -> int:
        return int(params.get("n", 40))

    @classmethod
    def describe(cls, params: dict) -> str:
        n = cls._n(params)
        return (
            f"Find the largest Sidon set (B_2 set) inside {{1,...,{n}}}: a set S "
            f"whose pairwise sums a_i + a_j (i <= j) are all distinct. Maximise "
            f"|S|. The growth of the maximal Sidon set is an Erdos-Turan problem."
        )

    @classmethod
    def universe(cls, params: dict) -> list:
        return list(range(1, cls._n(params) + 1))

    @staticmethod
    def _sums(state: set) -> set:
        return {a + b for a in state for b in state if a <= b}

    @classmethod
    def _addable_with_sums(cls, state: set, sums: set, x: int) -> bool:
        if x in state:
            return False
        if (2 * x) in sums:
            return False
        for s in state:
            if (x + s) in sums:
                return False
        return True

    @classmethod
    def _greedy(cls, state: set, order: list) -> set:
        sums = cls._sums(state)
        for x in order:
            if cls._addable_with_sums(state, sums, x):
                # commit and update incremental sum set
                for s in state:
                    sums.add(x + s)
                sums.add(2 * x)
                state.add(x)
        return state

    @classmethod
    def seed(cls, params: dict, rng: random.Random) -> list:
        order = cls.universe(params)
        rng.shuffle(order)
        return sorted(cls._greedy(set(), order))

    @classmethod
    def mutate(cls, obj: list, params: dict, rng: random.Random) -> list:
        state = set(obj)
        if state:
            k = rng.randint(1, max(1, min(3, len(state))))
            for x in rng.sample(list(state), k):
                state.discard(x)
        order = cls.universe(params)
        rng.shuffle(order)
        cls._greedy(state, order)
        return sorted(state)

    @classmethod
    def crossover(cls, a: list, b: list, params: dict, rng: random.Random) -> list:
        state = set(a) & set(b)
        order = cls.universe(params)
        rng.shuffle(order)
        cls._greedy(state, order)
        return sorted(state)

    @classmethod
    def verify(cls, obj: list, params: dict) -> dict:
        n = cls._n(params)
        if any((not isinstance(x, int)) or x < 1 or x > n for x in obj):
            return {"ok": False, "reason": "element outside [1,n]"}
        if len(set(obj)) != len(obj):
            return {"ok": False, "reason": "duplicate element"}
        srt = sorted(obj)
        seen: dict[int, tuple] = {}
        for i in range(len(srt)):
            for j in range(i, len(srt)):
                s = srt[i] + srt[j]
                if s in seen:
                    return {"ok": False, "reason": f"sum collision {s}: {seen[s]} and {(srt[i], srt[j])}"}
                seen[s] = (srt[i], srt[j])
        return {"ok": True, "size": len(srt), "method": "pairwise-sum collision scan"}

    @classmethod
    def evaluate(cls, obj: list, params: dict) -> dict:
        v = cls.verify(obj, params)
        if not v.get("ok"):
            return {"valid": False, "score": float("-inf"), "size": 0, "reason": v.get("reason")}
        size = len(obj)
        return {
            "valid": True,
            "score": float(size),
            "size": size,
            "certificate": {
                "problem": f"sidon_set [1,{cls._n(params)}]",
                "set": obj,
                "size": size,
                "independent_verifier": "pairwise-sum collision scan",
            },
        }


# ===========================================================================
# Evaluator: triangle_free_chromatic  (Erdos: triangle-free, high chi)
# ===========================================================================
class TriangleFreeChromatic:
    name = "triangle_free_chromatic"
    objective = "maximize"
    domain = "graph"

    @staticmethod
    def _v(params: dict) -> int:
        return int(params.get("v", 8))

    @classmethod
    def describe(cls, params: dict) -> str:
        v = cls._v(params)
        return (
            f"Find a triangle-free graph on {v} vertices with the largest "
            f"possible chromatic number. Erdos proved triangle-free graphs of "
            f"arbitrarily high chromatic number exist; explicit small witnesses "
            f"(Grotzsch, Mycielski) realise chi=4 on 11 vertices."
        )

    @classmethod
    def universe(cls, params: dict) -> list:
        v = cls._v(params)
        return [(i, j) for i in range(v) for j in range(i + 1, v)]

    @classmethod
    def _addable(cls, state: set, e: tuple, v: int) -> bool:
        a, b = e
        nbr_a = {y for (x, y) in ((min(p), max(p)) for p in state) if x == a}
        nbr_a |= {x for (x, y) in ((min(p), max(p)) for p in state) if y == a}
        nbr_b = {y for (x, y) in ((min(p), max(p)) for p in state) if x == b}
        nbr_b |= {x for (x, y) in ((min(p), max(p)) for p in state) if y == b}
        return not (nbr_a & nbr_b)  # adding e is fine iff a,b share no common neighbour

    @classmethod
    def _greedy(cls, state: set, order: list, v: int) -> set:
        for e in order:
            if e in state:
                continue
            if cls._addable(state, e, v):
                state.add(e)
        return state

    @classmethod
    def seed(cls, params: dict, rng: random.Random) -> list:
        v = cls._v(params)
        order = cls.universe(params)
        rng.shuffle(order)
        return cls._canon(cls._greedy(set(), order, v))

    @classmethod
    def mutate(cls, obj: list, params: dict, rng: random.Random) -> list:
        v = cls._v(params)
        state = {tuple(e) for e in obj}
        if state:
            k = rng.randint(1, max(1, min(4, len(state))))
            for e in rng.sample(list(state), k):
                state.discard(e)
        order = cls.universe(params)
        rng.shuffle(order)
        cls._greedy(state, order, v)
        return cls._canon(state)

    @classmethod
    def crossover(cls, a: list, b: list, params: dict, rng: random.Random) -> list:
        v = cls._v(params)
        state = {tuple(e) for e in a} & {tuple(e) for e in b}
        order = cls.universe(params)
        rng.shuffle(order)
        cls._greedy(state, order, v)
        return cls._canon(state)

    @staticmethod
    def _canon(state: set) -> list:
        return [list(e) for e in sorted(state)]

    @classmethod
    def verify(cls, obj: list, params: dict) -> dict:
        if triangle_free is None or chromatic_number is None:
            return {"ok": False, "reason": "finite_graph_backend unavailable"}
        v = cls._v(params)
        edges = {(min(int(a), int(b)), max(int(a), int(b))) for a, b in obj}
        if any(a == b or a < 0 or b >= v for a, b in edges):
            return {"ok": False, "reason": "edge out of range"}
        if not triangle_free(v, edges):
            return {"ok": False, "reason": "graph contains a triangle"}
        chi = chromatic_number(v, edges)
        return {"ok": True, "chromatic_number": chi, "method": "exact backtracking colouring"}

    @classmethod
    def evaluate(cls, obj: list, params: dict) -> dict:
        v = cls.verify(obj, params)
        if not v.get("ok"):
            return {"valid": False, "score": float("-inf"), "size": 0, "reason": v.get("reason")}
        chi = int(v["chromatic_number"])
        return {
            "valid": True,
            "score": float(chi),
            "size": len(obj),
            "certificate": {
                "problem": f"triangle_free_chromatic on {cls._v(params)} vertices",
                "edges": obj,
                "chromatic_number": chi,
                "independent_verifier": "exact backtracking colouring",
            },
        }


class PotentialFunction:
    """Construction search (Phase 3): search for an AUXILIARY OBJECT a proof needs —
    here a potential/ranking function. Find V: states -> ℕ that strictly decreases
    along every transition (V[u] > V[v] for each edge u->v). A perfect V certifies the
    transition system is ACYCLIC / the process terminates. Calibration is built in: no
    such V exists when the system has a cycle, so the search CANNOT certify a false
    claim — the deterministic evaluator is the sole judge."""
    name = "potential_function"
    objective = "maximize"
    domain = "termination/acyclicity certificate"

    @staticmethod
    def _edges(params: dict) -> list:
        return [tuple(int(x) for x in e) for e in params.get("edges", [])]

    @classmethod
    def _n(cls, params: dict) -> int:
        if params.get("n"):
            return int(params["n"])
        return 1 + max((max(e) for e in cls._edges(params)), default=-1)

    @classmethod
    def describe(cls, params: dict) -> str:
        return ("Find a potential V: states -> ℕ with V[u] > V[v] on every transition "
                f"u->v of a {cls._n(params)}-state system. A perfect V certifies acyclicity / "
                "termination; none exists if the system has a cycle.")

    @classmethod
    def seed(cls, params: dict, rng: random.Random) -> list:
        n = cls._n(params)
        return [rng.randint(0, max(1, n)) for _ in range(n)]

    @classmethod
    def mutate(cls, obj: list, params: dict, rng: random.Random) -> list:
        if not obj:
            return obj
        v = list(obj)
        i = rng.randrange(len(v))
        v[i] = max(0, v[i] + rng.choice([-3, -2, -1, 1, 2, 3]))
        return v

    @classmethod
    def crossover(cls, a: list, b: list, params: dict, rng: random.Random) -> list:
        n = min(len(a), len(b))
        return [a[i] if rng.random() < 0.5 else b[i] for i in range(n)]

    @classmethod
    def verify(cls, obj: list, params: dict) -> dict:
        n = cls._n(params)
        if not (isinstance(obj, list) and len(obj) == n and all(isinstance(x, int) and x >= 0 for x in obj)):
            return {"ok": False, "reason": "V must be a length-n list of nonnegative ints"}
        edges = cls._edges(params)
        satisfied = sum(1 for (u, v) in edges if 0 <= u < n and 0 <= v < n and obj[u] > obj[v])
        return {"ok": True, "satisfied": satisfied, "total": len(edges),
                "certifies_acyclic": len(edges) > 0 and satisfied == len(edges)}

    @classmethod
    def evaluate(cls, obj: list, params: dict) -> dict:
        v = cls.verify(obj, params)
        if not v.get("ok"):
            return {"valid": False, "score": float("-inf"), "size": 0, "reason": v.get("reason")}
        total = v["total"]
        score = 1.0 if total == 0 else v["satisfied"] / total
        return {"valid": True, "score": score, "size": max(obj) if obj else 0,
                "certificate": {"problem": f"acyclicity of a {cls._n(params)}-state transition system",
                                "potential": list(obj), "satisfied_edges": v["satisfied"], "total_edges": total,
                                "certifies_acyclic": v["certifies_acyclic"],
                                "independent_verifier": "exact per-edge strict-decrease check"}}


EVALUATORS: dict[str, Any] = {
    CapSet.name: CapSet,
    NoThreeAP.name: NoThreeAP,
    SidonSet.name: SidonSet,
    TriangleFreeChromatic.name: TriangleFreeChromatic,
    PotentialFunction.name: PotentialFunction,
}


def get_evaluator(name: str) -> Any:
    if name not in EVALUATORS:
        raise SystemExit(f"unknown evaluator '{name}'. known: {sorted(EVALUATORS)}")
    return EVALUATORS[name]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    for cmd in ("describe", "universe", "seed", "evaluate", "verify"):
        p = sub.add_parser(cmd)
        p.add_argument("--evaluator", required=True)
        p.add_argument("--params", default="{}")
        if cmd in ("evaluate", "verify"):
            p.add_argument("--object", required=True)
        if cmd == "seed":
            p.add_argument("--seed", type=int, default=0)

    args = parser.parse_args()

    if args.cmd == "list":
        print(json.dumps({name: {"objective": ev.objective, "domain": ev.domain} for name, ev in EVALUATORS.items()}, indent=2))
        return 0

    ev = get_evaluator(args.evaluator)
    params = json.loads(args.params)

    if args.cmd == "describe":
        print(json.dumps({"evaluator": ev.name, "problem": ev.describe(params)}, indent=2))
    elif args.cmd == "universe":
        print(json.dumps({"evaluator": ev.name, "universe_size": len(ev.universe(params))}, indent=2))
    elif args.cmd == "seed":
        obj = ev.seed(params, random.Random(args.seed))
        print(json.dumps({"evaluator": ev.name, "object": obj, "evaluation": ev.evaluate(obj, params)}, indent=2))
    elif args.cmd == "evaluate":
        obj = json.loads(args.object)
        print(json.dumps({"evaluator": ev.name, "evaluation": ev.evaluate(obj, params)}, indent=2))
    elif args.cmd == "verify":
        obj = json.loads(args.object)
        print(json.dumps({"evaluator": ev.name, "verify": ev.verify(obj, params)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
