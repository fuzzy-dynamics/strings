#!/usr/bin/env python3
"""Small deterministic graph search helpers for Lovasz experiments.

This intentionally avoids external dependencies. It can enumerate all simple
graphs up to small n and report basic invariants or find graphs satisfying a
few built-in predicates.
"""

from __future__ import annotations

import argparse
import itertools
import json


def edges_of(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def graph_from_mask(n: int, mask: int) -> set[tuple[int, int]]:
    edges = edges_of(n)
    return {edge for idx, edge in enumerate(edges) if (mask >> idx) & 1}


def degree_sequence(n: int, edges: set[tuple[int, int]]) -> list[int]:
    deg = [0] * n
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    return sorted(deg, reverse=True)


def has_triangle(edges: set[tuple[int, int]]) -> bool:
    adj = {i: set() for edge in edges for i in edge}
    for i, j in edges:
        adj.setdefault(i, set()).add(j)
        adj.setdefault(j, set()).add(i)
    verts = list(adj)
    for a, b, c in itertools.combinations(verts, 3):
        if b in adj.get(a, ()) and c in adj.get(a, ()) and c in adj.get(b, ()):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True, help="number of vertices, keep small")
    parser.add_argument("--predicate", choices=["all", "triangle_free"], default="all")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    m = args.n * (args.n - 1) // 2
    out = []
    for mask in range(1 << m):
        edges = graph_from_mask(args.n, mask)
        if args.predicate == "triangle_free" and has_triangle(edges):
            continue
        out.append({
            "n": args.n,
            "edges": sorted(edges),
            "edge_count": len(edges),
            "degree_sequence": degree_sequence(args.n, edges),
            "triangle_free": not has_triangle(edges),
        })
        if len(out) >= args.limit:
            break

    print(json.dumps({"count": len(out), "graphs": out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
