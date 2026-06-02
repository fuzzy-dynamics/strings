#!/usr/bin/env python3
"""Typed wrapper for Lovasz bounded research-search helpers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


TOOLS = {
    "number-theory": "number_theory_search.py",
    "graph": "graph_search.py",
    "finite-model": "finite_model_search.py",
}


def tool_path(kind: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "witsoc-research-lovasz" / "scripts" / "experiments" / TOOLS[kind]


def inflate_counterexamples(kind: str, data: Any) -> list[dict[str, Any]]:
    inflated: list[dict[str, Any]] = []
    if kind == "graph":
        graphs = data.get("graphs", []) if isinstance(data, dict) else []
        for graph in graphs:
            if not isinstance(graph, dict):
                continue
            if graph.get("triangle_free") is True:
                inflated.append({
                    "family": "triangle_free_graphs_with_same_forbidden_triangle_pattern",
                    "seed": graph,
                    "parameter": "n >= seed.n with constructions preserving no triangles, e.g. bipartite blow-ups when applicable",
                    "status": "CONJECTURE",
                    "next_attempt": "prove preservation under the stated construction and generate WIT obstruction theorem",
                })
                break
    elif kind == "number-theory":
        rows = data.get("multiperfect", []) if isinstance(data, dict) else []
        if rows:
            ks = sorted({row.get("k") for row in rows if isinstance(row, dict) and row.get("k") is not None})
            inflated.append({
                "family": "numbers sharing sampled divisor-sum ratio pattern",
                "seed_k_values": ks,
                "parameter": "prime-exponent pattern from seed factorizations",
                "status": "CONJECTURE",
                "next_attempt": "symbolically prove sigma(n)/n pattern for parameterized prime exponents",
            })
    elif kind == "finite-model" and isinstance(data, dict) and data.get("witnesses"):
        inflated.append({
            "family": "tuples satisfying predicate schema",
            "seed_witnesses": data.get("witnesses", [])[:5],
            "parameter": "replace fixed coordinates by affine or monotone parameter constraints when predicate is preserved",
            "status": "CONJECTURE",
            "next_attempt": "derive symbolic predicate-preservation lemma for the parameterized tuple family",
        })
    return inflated


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded deterministic Lovasz search helper. Pass helper "
            "arguments after --, e.g. research_search.py graph -- --n 5."
        )
    )
    parser.add_argument("kind", nargs="?", choices=sorted(TOOLS))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parser.add_argument("--list", action="store_true", help="list available helper kinds")
    parser.add_argument("--inflate", action="store_true", help="try to generalize found witnesses/counterexamples into an obstruction family")
    ns = parser.parse_args()

    if ns.list:
        print(json.dumps({"available": sorted(TOOLS)}, indent=2))
        return 0
    if not ns.kind:
        parser.error("kind required unless --list is used")

    extra = list(ns.args)
    if extra and extra[0] == "--":
        extra = extra[1:]

    script = tool_path(ns.kind)
    if not script.exists():
        print(json.dumps({"error": "missing_search_helper", "kind": ns.kind, "path": str(script)}, indent=2), file=sys.stderr)
        return 2

    if not ns.inflate:
        completed = subprocess.run([sys.executable, str(script), *extra], check=False)
        return completed.returncode

    completed = subprocess.run([sys.executable, str(script), *extra], text=True, capture_output=True, check=False)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    try:
        data = json.loads(completed.stdout)
    except Exception:
        print(completed.stdout, end="")
        return completed.returncode

    data["inflation"] = {
        "status": "attempted",
        "obstruction_family_candidates": inflate_counterexamples(ns.kind, data),
    }
    print(json.dumps(data, indent=2, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
