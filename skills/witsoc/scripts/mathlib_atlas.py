#!/usr/bin/env python3
"""Mathlib import atlas query tool.

This consumes a precomputed JSON atlas when available. Expected shape:

{
  "nodes": [
    {
      "module": "Mathlib.Data.Nat.Basic",
      "symbols": ["Nat", "Nat.succ"],
      "doc": "natural numbers",
      "imports": ["Mathlib.Init.Data.Nat.Basic"]
    }
  ]
}

The tool ranks nodes by token similarity to a semantic query/signature and
PageRank centrality over the import graph, then returns a small import set.
If no atlas exists, it returns an empty result with a clear status.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ATLAS_PATHS = [
    Path("runs/mathlib_atlas.json"),
    Path("runs/mathlib_dependency_graph.json"),
    Path(".witsoc/mathlib_atlas.json"),
]


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_.'-]+", text.lower())


from witcore import cosine  # noqa: E402  -- shared substrate, was a local copy

def load_atlas(path: Path | None, external_cmd: str | None) -> dict[str, Any]:
    if external_cmd:
        completed = subprocess.run(external_cmd, shell=True, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"external atlas command exited {completed.returncode}")
        return json.loads(completed.stdout)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    for candidate in DEFAULT_ATLAS_PATHS:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"nodes": []}


def pagerank(nodes: list[dict[str, Any]], iterations: int = 30, damping: float = 0.85) -> dict[str, float]:
    modules = [str(node.get("module", "")) for node in nodes if node.get("module")]
    if not modules:
        return {}
    incoming: dict[str, set[str]] = defaultdict(set)
    outgoing: dict[str, set[str]] = defaultdict(set)
    module_set = set(modules)
    for node in nodes:
        module = str(node.get("module", ""))
        for imp in node.get("imports", []) or []:
            imp = str(imp)
            if imp in module_set:
                outgoing[module].add(imp)
                incoming[imp].add(module)
    n = len(modules)
    rank = {module: 1.0 / n for module in modules}
    for _ in range(iterations):
        new_rank = {module: (1.0 - damping) / n for module in modules}
        for module in modules:
            targets = outgoing.get(module) or set(modules)
            share = rank[module] / len(targets)
            for target in targets:
                new_rank[target] += damping * share
        rank = new_rank
    return rank


def node_text(node: dict[str, Any]) -> str:
    parts = [str(node.get("module", "")), str(node.get("doc", ""))]
    parts.extend(str(x) for x in node.get("symbols", []) or [])
    parts.extend(str(x) for x in node.get("theorems", []) or [])
    return " ".join(parts)


# Type-aware retrieval: an EXACT symbol-overlap signal. A goal that NAMES
# `Nat.divisors` must retrieve the divisors module even when doc words point
# elsewhere; a goal naming no qualified symbol gets overlap 0 everywhere, so
# ranking reduces to the cosine+pagerank order (no regression on core goals).
_QUALIFIED_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_']*)+)\b")
# Goal notation that implies a provider symbol without naming it.
_NOTATION_SYMBOLS = {"∑": "Finset.sum", "∏": "Finset.prod", "∣": "Dvd.dvd"}


def query_symbols(query: str, signature: str = "") -> set[str]:
    """Qualified declarations a goal names (`Nat.divisors`, `List.reverse`, …),
    plus symbols implied by notation (∑ -> Finset.sum)."""
    text = f"{query} {signature}"
    syms = set(_QUALIFIED_RE.findall(text))
    for nota, sym in _NOTATION_SYMBOLS.items():
        if nota in text:
            syms.add(sym)
    return syms


def symbol_overlap(qsyms: set[str], node: dict[str, Any]) -> float:
    """Fraction of the goal's named symbols this node PROVIDES. A node symbol
    counts when it equals the query symbol or is in the same family
    (`Nat.divisors_eq` provides for `Nat.divisors`) — but NOT the reverse: a
    generic namespace root (`Nat`) must not match a specific lemma."""
    if not qsyms:
        return 0.0
    provided = [str(s) for s in node.get("symbols", []) or []]
    hits = sum(1 for q in qsyms
               if any(s == q or s.startswith(q + "_") or s.startswith(q + ".") for s in provided))
    return hits / len(qsyms)


def query_atlas(atlas: dict[str, Any], query: str, signature: str, limit: int) -> dict[str, Any]:
    nodes = [node for node in atlas.get("nodes", []) if isinstance(node, dict) and node.get("module")]
    if not nodes:
        return {
            "status": "missing_atlas",
            "imports": [],
            "matches": [],
            "message": "No precomputed Mathlib atlas found. Provide --atlas or generate runs/mathlib_atlas.json.",
        }
    rank = pagerank(nodes)
    qvec = Counter(tokens(f"{query} {signature}"))
    qsyms = query_symbols(query, signature)
    scored = []
    for node in nodes:
        module = str(node["module"])
        sim = cosine(qvec, Counter(tokens(node_text(node))))
        centrality = rank.get(module, 0.0)
        symovl = symbol_overlap(qsyms, node)
        # exact symbol provision dominates; with no named symbols (symovl 0
        # everywhere) this reduces to the previous cosine+pagerank ranking.
        score = 0.55 * symovl + 0.35 * sim + 0.10 * centrality
        scored.append((score, sim, centrality, symovl, node))
    scored.sort(key=lambda item: (-item[0], str(item[4].get("module", ""))))
    matches = []
    imports: list[str] = []
    seen: set[str] = set()
    for score, sim, centrality, symovl, node in scored[:limit]:
        module = str(node["module"])
        if module not in seen:
            imports.append(module)
            seen.add(module)
        for imp in node.get("imports", []) or []:
            imp = str(imp)
            if imp not in seen:
                imports.append(imp)
                seen.add(imp)
        matches.append({
            "module": module,
            "score": score,
            "similarity": sim,
            "pagerank": centrality,
            "symbol_overlap": symovl,
            "symbols": node.get("symbols", []),
            "imports": node.get("imports", []),
        })
    return {"status": "ok", "imports": imports, "matches": matches}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="", help="Semantic mathematical query.")
    parser.add_argument("--signature", default="", help="Lean-ish type signature or theorem shape.")
    parser.add_argument("--atlas", type=Path, help="Precomputed atlas JSON path.")
    parser.add_argument("--external-cmd", help="Optional compiled backend command that prints atlas JSON.")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    try:
        atlas = load_atlas(args.atlas, args.external_cmd)
        payload = query_atlas(atlas, args.query, args.signature, args.limit)
    except Exception as exc:
        payload = {"status": "error", "error": str(exc), "imports": [], "matches": []}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") in {"ok", "missing_atlas"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
