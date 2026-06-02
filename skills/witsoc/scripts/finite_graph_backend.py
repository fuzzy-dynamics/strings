#!/usr/bin/env python3
"""Exact bounded finite-graph backend for Witsoc.

This script is intentionally exponential and deterministic. It is for small
graphs, counterexample pressure, and finite certificates only. It never proves
an asymptotic or infinite theorem by itself.
"""

from __future__ import annotations

import argparse
import itertools
import json
from typing import Any


Edge = tuple[int, int]


def canon_edge(a: int, b: int) -> Edge:
    if a == b:
        raise ValueError("loops are not supported")
    return (a, b) if a < b else (b, a)


def all_edges(n: int) -> list[Edge]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


def graph_from_mask(n: int, mask: int) -> set[Edge]:
    edges = all_edges(n)
    return {edge for index, edge in enumerate(edges) if (mask >> index) & 1}


def adjacency(n: int, edges: set[Edge]) -> list[set[int]]:
    adj = [set() for _ in range(n)]
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    return adj


def triangle_free(n: int, edges: set[Edge]) -> bool:
    adj = adjacency(n, edges)
    for a, b, c in itertools.combinations(range(n), 3):
        if b in adj[a] and c in adj[a] and c in adj[b]:
            return False
    return True


def is_k_colorable(n: int, edges: set[Edge], k: int) -> bool:
    adj = adjacency(n, edges)
    order = sorted(range(n), key=lambda v: len(adj[v]), reverse=True)
    colors = [-1] * n

    def dfs(pos: int) -> bool:
        if pos == n:
            return True
        v = order[pos]
        forbidden = {colors[u] for u in adj[v] if colors[u] >= 0}
        for color in range(k):
            if color in forbidden:
                continue
            colors[v] = color
            if dfs(pos + 1):
                return True
            colors[v] = -1
        return False

    return dfs(0)


def chromatic_number(n: int, edges: set[Edge]) -> int:
    if not edges:
        return 1 if n else 0
    for k in range(1, n + 1):
        if is_k_colorable(n, edges, k):
            return k
    return n


def parse_tree(spec: str) -> tuple[int, set[Edge], str]:
    if spec.startswith("path:"):
        vertices = int(spec.split(":", 1)[1])
        if vertices < 1:
            raise ValueError("path vertex count must be positive")
        return vertices, {canon_edge(i, i + 1) for i in range(vertices - 1)}, f"path_{vertices}"
    if spec.startswith("star:"):
        leaves = int(spec.split(":", 1)[1])
        if leaves < 1:
            raise ValueError("star leaf count must be positive")
        return leaves + 1, {canon_edge(0, i) for i in range(1, leaves + 1)}, f"star_{leaves}_leaves"
    if spec.startswith("edges:"):
        raw = json.loads(spec.split(":", 1)[1])
        edges = {canon_edge(int(a), int(b)) for a, b in raw}
        vertices = 0
        for a, b in edges:
            vertices = max(vertices, a + 1, b + 1)
        if vertices == 0:
            raise ValueError("edge-list tree must contain at least one edge")
        if len(edges) != vertices - 1:
            raise ValueError("edge-list spec is not a tree: edge count must be vertices - 1")
        if not connected(vertices, edges):
            raise ValueError("edge-list spec is not connected")
        return vertices, edges, "custom_tree"
    raise ValueError("tree spec must be path:<vertices>, star:<leaves>, or edges:<json-edge-list>")


def connected(n: int, edges: set[Edge]) -> bool:
    if n == 0:
        return True
    adj = adjacency(n, edges)
    seen = {0}
    stack = [0]
    while stack:
        v = stack.pop()
        for u in adj[v]:
            if u not in seen:
                seen.add(u)
                stack.append(u)
    return len(seen) == n


def induced_edge_set(vertices: tuple[int, ...], graph_edges: set[Edge]) -> set[Edge]:
    index = {vertex: i for i, vertex in enumerate(vertices)}
    out: set[Edge] = set()
    vertex_set = set(vertices)
    for a, b in graph_edges:
        if a in vertex_set and b in vertex_set:
            out.add(canon_edge(index[a], index[b]))
    return out


def isomorphic_to_tree(induced_edges: set[Edge], tree_n: int, tree_edges: set[Edge]) -> bool:
    if len(induced_edges) != len(tree_edges):
        return False
    target = tree_edges
    for perm in itertools.permutations(range(tree_n)):
        mapped = {canon_edge(perm[a], perm[b]) for a, b in induced_edges}
        if mapped == target:
            return True
    return False


def contains_induced_tree(n: int, edges: set[Edge], tree_n: int, tree_edges: set[Edge]) -> bool:
    if tree_n > n:
        return False
    for vertices in itertools.combinations(range(n), tree_n):
        if isomorphic_to_tree(induced_edge_set(vertices, edges), tree_n, tree_edges):
            return True
    return False


def graph_record(n: int, edges: set[Edge], tree: tuple[int, set[Edge], str] | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "n": n,
        "edges": sorted([list(edge) for edge in edges]),
        "edge_count": len(edges),
        "triangle_free": triangle_free(n, edges),
        "chromatic_number": chromatic_number(n, edges),
    }
    if tree is not None:
        tree_n, tree_edges, tree_name = tree
        record["tree"] = tree_name
        record["contains_induced_tree"] = contains_induced_tree(n, edges, tree_n, tree_edges)
    return record


def iter_graphs(n: int, max_graphs: int | None) -> Any:
    total_edges = n * (n - 1) // 2
    count = 0
    for mask in range(1 << total_edges):
        yield graph_from_mask(n, mask)
        count += 1
        if max_graphs is not None and count >= max_graphs:
            return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, required=True, help="Number of vertices.")
    parser.add_argument("--max-graphs", type=int, help="Optional cap on enumerated graphs.")
    parser.add_argument("--triangle-free", action="store_true")
    parser.add_argument("--min-chromatic", type=int, default=0)
    parser.add_argument("--tree", help="Tree target: path:<vertices>, star:<leaves>, or edges:<json-edge-list>.")
    parser.add_argument("--omit-induced-tree", action="store_true")
    parser.add_argument("--limit", type=int, default=20, help="Maximum matching records to emit.")
    args = parser.parse_args()

    if args.n < 0:
        raise SystemExit("--n must be nonnegative")
    tree = parse_tree(args.tree) if args.tree else None
    matches = []
    checked = 0
    for edges in iter_graphs(args.n, args.max_graphs):
        checked += 1
        if args.triangle_free and not triangle_free(args.n, edges):
            continue
        chi = chromatic_number(args.n, edges)
        if chi < args.min_chromatic:
            continue
        contains_tree = None
        if tree is not None:
            contains_tree = contains_induced_tree(args.n, edges, tree[0], tree[1])
            if args.omit_induced_tree and contains_tree:
                continue
        record = {
            "n": args.n,
            "edges": sorted([list(edge) for edge in edges]),
            "edge_count": len(edges),
            "triangle_free": triangle_free(args.n, edges),
            "chromatic_number": chi,
        }
        if tree is not None:
            record["tree"] = tree[2]
            record["contains_induced_tree"] = contains_tree
        matches.append(record)
        if len(matches) >= args.limit:
            break

    print(json.dumps({
        "status": "checked_bounded",
        "checked_graphs": checked,
        "n": args.n,
        "filters": {
            "triangle_free": args.triangle_free,
            "min_chromatic": args.min_chromatic,
            "tree": tree[2] if tree else None,
            "omit_induced_tree": args.omit_induced_tree,
        },
        "matches": matches,
        "claim_status": "CHECKED",
        "scope": "bounded finite graph enumeration only",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
