#!/usr/bin/env python3
"""Deterministic empirical invariant miner for Witsoc/Lovasz.

The miner generates bounded finite structures, computes simple properties, and
reports stable predicates/relations as conjecture candidates. It is empirical:
all output is CONJECTURE or CHECKED bounded evidence, never a proof.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


def graph_edges(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def graph_from_mask(n: int, mask: int) -> set[tuple[int, int]]:
    edges = graph_edges(n)
    return {edge for idx, edge in enumerate(edges) if (mask >> idx) & 1}


def cycle_graph(n: int) -> set[tuple[int, int]]:
    if n < 3:
        raise ValueError("cycle graphs require n >= 3")
    return {tuple(sorted((i, (i + 1) % n))) for i in range(n)}


def mycielski_step(n: int, edges: set[tuple[int, int]]) -> tuple[int, set[tuple[int, int]]]:
    out = set(edges)
    apex = 2 * n
    for u, v in edges:
        out.add(tuple(sorted((u, v + n))))
        out.add(tuple(sorted((v, u + n))))
    for u in range(n):
        out.add((u + n, apex))
    return 2 * n + 1, out


def mycielski_sequence(iterations: int) -> list[tuple[int, set[tuple[int, int]]]]:
    n = 5
    edges = cycle_graph(n)
    out = [(n, edges)]
    for _ in range(iterations):
        n, edges = mycielski_step(n, edges)
        out.append((n, edges))
    return out


def graph_props(n: int, edges: set[tuple[int, int]]) -> dict[str, Any]:
    deg = [0] * n
    adj = {i: set() for i in range(n)}
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
        adj[i].add(j)
        adj[j].add(i)
    triangles = 0
    for a, b, c in itertools.combinations(range(n), 3):
        if b in adj[a] and c in adj[a] and c in adj[b]:
            triangles += 1
    return {
        "n": n,
        "edge_count": len(edges),
        "max_degree": max(deg) if deg else 0,
        "min_degree": min(deg) if deg else 0,
        "is_regular": len(set(deg)) <= 1,
        "triangle_count": triangles,
        "triangle_free": triangles == 0,
        "degree_sum": sum(deg),
        "degree_sum_equals_2_edges": sum(deg) == 2 * len(edges),
    }


def generate_graphs(max_n: int, limit: int, graph_family: str, iterations: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if graph_family == "cycles":
        for n in range(3, max_n + 1):
            props = graph_props(n, cycle_graph(n))
            props["graph_family"] = "cycle"
            props["girth_lower_bound"] = n
            out.append(props)
            if len(out) >= limit:
                return out
        return out
    if graph_family == "mycielski":
        for step, (n, edges) in enumerate(mycielski_sequence(iterations)):
            props = graph_props(n, edges)
            props["graph_family"] = "mycielski"
            props["mycielski_step"] = step
            props["known_chromatic_lower_bound"] = 3 + step
            out.append(props)
            if len(out) >= limit:
                return out
        return out
    for n in range(1, max_n + 1):
        m = n * (n - 1) // 2
        for mask in range(1 << m):
            props = graph_props(n, graph_from_mask(n, mask))
            props["graph_family"] = "exhaustive"
            out.append(props)
            if len(out) >= limit:
                return out
    return out


def factor(n: int) -> dict[int, int]:
    d: dict[int, int] = {}
    p = 2
    while p * p <= n:
        while n % p == 0:
            d[p] = d.get(p, 0) + 1
            n //= p
        p += 1 if p == 2 else 2
    if n > 1:
        d[n] = d.get(n, 0) + 1
    return d


def sigma_from_factor(f: dict[int, int]) -> int:
    total = 1
    for p, a in f.items():
        total *= (p ** (a + 1) - 1) // (p - 1)
    return total


def generate_number_theory(limit: int) -> list[dict[str, Any]]:
    out = []
    for n in range(1, limit + 1):
        f = factor(n)
        sigma = sigma_from_factor(f)
        abundancy = Fraction(sigma, n)
        out.append({
            "n": n,
            "sigma": sigma,
            "omega": len(f),
            "Omega": sum(f.values()),
            "is_square": int(math.isqrt(n) ** 2 == n),
            "is_multiperfect": abundancy.denominator == 1,
            "k_if_multiperfect": abundancy.numerator if abundancy.denominator == 1 else None,
            "sigma_ge_n": sigma >= n,
        })
    return out


def det2(matrix: tuple[int, int, int, int]) -> int:
    a, b, c, d = matrix
    return a * d - b * c


def generate_matrices(bound: int, limit: int) -> list[dict[str, Any]]:
    out = []
    values = range(-bound, bound + 1)
    for matrix in itertools.product(values, repeat=4):
        tr = matrix[0] + matrix[3]
        det = det2(matrix)
        out.append({
            "matrix": matrix,
            "trace": tr,
            "det": det,
            "singular": det == 0,
            "trace_even": tr % 2 == 0,
            "det_zero_implies_singular": (det != 0) or (det == 0),
        })
        if len(out) >= limit:
            break
    return out


def load_external(generator_bin: str, args: list[str]) -> list[dict[str, Any]]:
    completed = subprocess.run([generator_bin, *args], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"generator exited {completed.returncode}")
    rows = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# --- Sequence fingerprint families (creativity program K3) --------------------
# Matching a computed sequence against a known family is the "this is secretly
# the Catalan numbers" moment — a classic source of conjectured closed forms.
def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _catalan(n: int) -> int:
    return math.comb(2 * n, n) // (n + 1) if n >= 0 else 0


SEQUENCE_FAMILIES: dict[str, Any] = {
    "squares": lambda n: n * n,
    "cubes": lambda n: n ** 3,
    "triangular": lambda n: n * (n + 1) // 2,
    "fibonacci": _fib,
    "catalan": _catalan,
    "powers_of_2": lambda n: 2 ** n if n <= 62 else None,
    "factorial": lambda n: math.factorial(n) if n <= 20 else None,
    "double": lambda n: 2 * n,
}


def _stable_props(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    stable = []
    for key in keys:
        values = [row.get(key) for row in rows if key in row]
        if values and all(value == values[0] for value in values):
            stable.append({"property": key, "value": values[0], "support": len(values)})
    return stable


def mine_inequalities(rows: list[dict[str, Any]], numeric_keys: list[str],
                      max_constant: int = 64, min_support: int = 3) -> list[dict[str, Any]]:
    """Best-constant bound conjectures: a ≤ c·b with the minimal observed integer c.
    Bounds are the bread of combinatorics; the tight rows feed extremal mining."""
    out = []
    # 0/1-indicator columns make meaningless right-hand sides (`a <= c*indicator`
    # is a conditional constant, not a bound) — exclude them from the right.
    binary = {k for k in numeric_keys
              if {r[k] for r in rows if k in r} <= {0, 1}}
    for a, b in itertools.permutations(numeric_keys, 2):
        if b in binary:
            continue
        support_rows = [r for r in rows if a in r and b in r and r[b] > 0 and r[a] >= 0]
        if len(support_rows) < min_support:
            continue
        c = max(-(-r[a] // r[b]) for r in support_rows)  # ceil division, minimal valid c
        if c < 1 or c > max_constant:
            continue
        tight = [r for r in support_rows if r[a] == c * r[b]]
        if c == 1 and len(tight) == len(support_rows):
            continue  # plain equality — already reported by numeric_equalities
        out.append({"left": a, "right": b, "constant": c, "support": len(support_rows),
                    "tight_count": len(tight),
                    "tight_everywhere": len(tight) == len(support_rows)})
    out.sort(key=lambda x: (-x["tight_count"] / max(1, x["support"]), x["constant"]))
    return out


def mine_equality_cases(rows: list[dict[str, Any]], inequalities: list[dict[str, Any]],
                        keys: list[str], top: int = 8) -> list[dict[str, Any]]:
    """Tightness/extremal mining: where a bound is tight, what structure is forced?
    Properties stable on the tight rows but NOT stable globally are conjectured
    extremal-structure characterizations — historically the richest lemma source."""
    globally_stable = {s["property"] for s in _stable_props(rows, keys)}
    out = []
    for ineq in inequalities[:top]:
        if ineq["tight_everywhere"] or ineq["tight_count"] < 2:
            continue
        a, b, c = ineq["left"], ineq["right"], ineq["constant"]
        tight_rows = [r for r in rows if a in r and b in r and r[b] > 0 and r[a] == c * r[b]]
        forced = [s for s in _stable_props(tight_rows, keys)
                  if s["property"] not in globally_stable and s["property"] not in (a, b)]
        for s in forced:
            out.append({"bound": f"{a} <= {c}*{b}", "tight_rows": len(tight_rows),
                        "forced_property": s["property"], "forced_value": s["value"]})
    return out


def mine_sequence_fingerprints(rows: list[dict[str, Any]], numeric_keys: list[str],
                               min_support: int = 4) -> list[dict[str, Any]]:
    """Match computed integer sequences (indexed by an `n` column) against known
    families, allowing an index shift of -1/0/+1."""
    indexed = sorted((r for r in rows if isinstance(r.get("n"), int)), key=lambda r: r["n"])
    if len(indexed) < min_support:
        return []
    out = []
    for key in numeric_keys:
        if key == "n":
            continue
        pts = [(r["n"], r[key]) for r in indexed if isinstance(r.get(key), int)]
        if len(pts) < min_support or len({v for _, v in pts}) <= 1:
            continue
        for fam, fn in SEQUENCE_FAMILIES.items():
            for shift in (-1, 0, 1):
                try:
                    expected = [fn(n + shift) for n, _ in pts]
                except Exception:
                    continue
                if None in expected:
                    continue
                if all(v == e for (_, v), e in zip(pts, expected)):
                    out.append({"property": key, "family": fam, "shift": shift,
                                "support": len(pts)})
                    break
            else:
                continue
            break
    return out


def mine(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"stable_properties": [], "implications": [], "numeric_equalities": [],
                "inequalities": [], "equality_cases": [], "sequence_fingerprints": []}
    keys = sorted({key for row in rows for key in row if isinstance(row.get(key), (bool, int, float))})
    stable = []
    for key in keys:
        values = [row.get(key) for row in rows if key in row]
        if values and all(value == values[0] for value in values):
            stable.append({"property": key, "value": values[0], "support": len(values)})

    bool_keys = [key for key in keys if all(isinstance(row.get(key), bool) for row in rows if key in row)]
    implications = []
    for a, b in itertools.permutations(bool_keys, 2):
        support = [row for row in rows if a in row and b in row]
        if support and all((not row[a]) or row[b] for row in support):
            implications.append({"if": a, "then": b, "support": len(support)})

    numeric_equalities = []
    numeric_keys = [key for key in keys if all(isinstance(row.get(key), int) and not isinstance(row.get(key), bool) for row in rows if key in row)]
    for a, b in itertools.combinations(numeric_keys, 2):
        support = [row for row in rows if a in row and b in row]
        if support and all(row[a] == row[b] for row in support):
            numeric_equalities.append({"left": a, "right": b, "support": len(support)})
    inequalities = mine_inequalities(rows, numeric_keys)
    return {
        "stable_properties": stable,
        "implications": implications,
        "numeric_equalities": numeric_equalities,
        "inequalities": inequalities,
        "equality_cases": mine_equality_cases(rows, inequalities, keys),
        "sequence_fingerprints": mine_sequence_fingerprints(rows, numeric_keys),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["graphs", "number_theory", "matrices"], required=True)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-n", type=int, default=5)
    parser.add_argument("--matrix-bound", type=int, default=2)
    parser.add_argument("--graph-family", choices=["exhaustive", "cycles", "mycielski"], default="exhaustive")
    parser.add_argument("--iterations", type=int, default=3, help="Iterations for generated graph families such as Mycielski.")
    parser.add_argument("--generator-bin", help="Optional compiled generator producing JSONL rows.")
    parser.add_argument("--generator-arg", action="append", default=[])
    args = parser.parse_args()

    try:
        if args.generator_bin:
            rows = load_external(args.generator_bin, args.generator_arg)
        elif args.domain == "graphs":
            rows = generate_graphs(args.max_n, args.limit, args.graph_family, args.iterations)
        elif args.domain == "number_theory":
            rows = generate_number_theory(args.limit)
        else:
            rows = generate_matrices(args.matrix_bound, args.limit)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2

    result = {
        "status": "checked_bounded",
        "domain": args.domain,
        "sample_size": len(rows),
        "invariants": mine(rows),
        "actual_lemma_queue_candidates": [],
    }
    for item in result["invariants"]["stable_properties"][:20]:
        result["actual_lemma_queue_candidates"].append({
            "statement": f"{item['property']} == {item['value']} on sampled {args.domain} objects",
            "status": "CONJECTURE",
            "support": item["support"],
            "next_attempt": "falsify on larger bounds, then formalize exact scoped lemma",
        })
    for item in result["invariants"]["inequalities"][:10]:
        tight = "tight everywhere (scaled equality)" if item["tight_everywhere"] else \
            f"tight on {item['tight_count']}/{item['support']} samples"
        result["actual_lemma_queue_candidates"].append({
            "statement": f"{item['left']} <= {item['constant']}*{item['right']} on sampled "
                         f"{args.domain} objects ({tight})",
            "status": "CONJECTURE",
            "support": item["support"],
            "next_attempt": "falsify on larger bounds; if it holds, characterize the equality cases",
        })
    for item in result["invariants"]["equality_cases"][:10]:
        result["actual_lemma_queue_candidates"].append({
            "statement": f"extremal structure: objects with {item['bound']} tight all satisfy "
                         f"{item['forced_property']} == {item['forced_value']}",
            "status": "CONJECTURE",
            "support": item["tight_rows"],
            "next_attempt": "verify the forced structure on larger extremal samples, then prove "
                            "the characterization as a stability lemma",
        })
    for item in result["invariants"]["sequence_fingerprints"][:10]:
        shift = f"(n{item['shift']:+d})" if item["shift"] else "(n)"
        result["actual_lemma_queue_candidates"].append({
            "statement": f"{item['property']}(n) == {item['family']}{shift} on sampled "
                         f"{args.domain} objects",
            "status": "CONJECTURE",
            "support": item["support"],
            "next_attempt": "extend the index range; if the closed form survives, prove it by induction",
        })
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
