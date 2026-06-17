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


def mine(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"stable_properties": [], "implications": [], "numeric_equalities": []}
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
    return {
        "stable_properties": stable,
        "implications": implications,
        "numeric_equalities": numeric_equalities,
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
