#!/usr/bin/env python3
"""Build the Mathlib import atlas that `mathlib_atlas.py` consumes for premise
selection.

Two modes:

  --mathlib-src DIR   Parse a real Mathlib (or any Lean) source tree: each .lean
                      file becomes a node {module, imports, symbols, doc} by
                      reading its `import` lines and top-level declarations. This
                      is the production path — point it at a mathlib checkout.

  (no source)         Emit a curated SEED atlas of common core/Mathlib modules so
                      premise selection returns useful imports even before a full
                      mathlib tree is indexed. Honestly partial: it covers the
                      areas Witsoc runs touch most (combinatorics, number theory,
                      finset/bigops, basic analysis), not all of mathlib.

Output goes to one of `mathlib_atlas.py`'s default lookup paths
(`.witsoc/mathlib_atlas.json` by default), so querying works with no extra flags.

Usage:
  build_mathlib_atlas.py [--mathlib-src DIR] [--out .witsoc/mathlib_atlas.json] [--max-files N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.]+)", re.MULTILINE)
_DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+|private\s+|protected\s+)?"
    r"(theorem|lemma|def|abbrev|instance|structure|class|inductive)\s+([A-Za-z_][A-Za-z0-9_'.]*)",
    re.MULTILINE,
)
_DOC_RE = re.compile(r"/--(.*?)-/", re.DOTALL)


def module_of(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def build_from_source(root: Path, max_files: int) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    files = sorted(root.rglob("*.lean"))[:max_files]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        imports = _IMPORT_RE.findall(text)
        symbols = [m.group(2) for m in _DECL_RE.finditer(text)]
        doc_m = _DOC_RE.search(text)
        doc = re.sub(r"\s+", " ", doc_m.group(1)).strip()[:240] if doc_m else ""
        nodes.append({
            "module": module_of(f, root),
            "imports": imports,
            "symbols": symbols[:80],
            "doc": doc,
        })
    return nodes


# Curated seed: module -> (doc, [symbols], [imports]). Kept small and honest.
SEED: dict[str, tuple[str, list[str], list[str]]] = {
    "Mathlib.Data.Nat.Basic": ("natural numbers, induction, basic arithmetic",
        ["Nat", "Nat.succ", "Nat.rec", "Nat.add_comm", "Nat.le_refl"], []),
    "Mathlib.Data.Int.Basic": ("integers, basic ring structure",
        ["Int", "Int.add", "Int.neg", "Int.le"], ["Mathlib.Data.Nat.Basic"]),
    "Mathlib.Data.Finset.Basic": ("finite sets, membership, union/inter",
        ["Finset", "Finset.card", "Finset.union", "Finset.inter", "Finset.filter"], ["Mathlib.Data.Nat.Basic"]),
    "Mathlib.Algebra.BigOperators.Basic": ("finite sums and products over a Finset",
        ["Finset.sum", "Finset.prod", "BigOperators"], ["Mathlib.Data.Finset.Basic"]),
    "Mathlib.Combinatorics.Pigeonhole": ("pigeonhole principle, double counting",
        ["Finset.exists_ne_map_eq_of_card_lt_of_maps_to", "Finset.exists_lt_card_fiber"],
        ["Mathlib.Data.Finset.Basic", "Mathlib.Algebra.BigOperators.Basic"]),
    "Mathlib.Combinatorics.SimpleGraph.Basic": ("simple graphs, adjacency, degree",
        ["SimpleGraph", "SimpleGraph.Adj", "SimpleGraph.degree", "SimpleGraph.neighborFinset"],
        ["Mathlib.Data.Finset.Basic"]),
    "Mathlib.Combinatorics.SimpleGraph.Clique": ("cliques, independent sets, clique number",
        ["SimpleGraph.IsClique", "SimpleGraph.cliqueNumber", "SimpleGraph.IsNClique"],
        ["Mathlib.Combinatorics.SimpleGraph.Basic"]),
    "Mathlib.Combinatorics.SimpleGraph.Coloring": ("proper colourings, chromatic number",
        ["SimpleGraph.Coloring", "SimpleGraph.chromaticNumber", "SimpleGraph.Colorable"],
        ["Mathlib.Combinatorics.SimpleGraph.Basic"]),
    "Mathlib.Combinatorics.Additive.Behrend": ("Behrend's construction; sets with no 3-term AP",
        ["Behrend.sphere", "Behrend.bound"], ["Mathlib.Combinatorics.Pigeonhole"]),
    "Mathlib.NumberTheory.Divisors": ("divisors, sum of divisors sigma",
        ["Nat.divisors", "Nat.sigma", "Nat.Perfect"], ["Mathlib.Data.Finset.Basic"]),
    "Mathlib.NumberTheory.ArithmeticFunction": ("arithmetic functions, multiplicativity",
        ["ArithmeticFunction", "ArithmeticFunction.sigma", "ArithmeticFunction.IsMultiplicative"],
        ["Mathlib.NumberTheory.Divisors"]),
    "Mathlib.Data.Nat.Prime.Basic": ("primality, prime factorisation",
        ["Nat.Prime", "Nat.factors", "Nat.factorization"], ["Mathlib.Data.Nat.Basic"]),
    "Mathlib.Data.Real.Basic": ("real numbers, ordered field",
        ["Real", "Real.instField", "Real.le_def"], ["Mathlib.Data.Int.Basic"]),
    "Mathlib.Analysis.SpecialFunctions.Log.Basic": ("real logarithm and its bounds",
        ["Real.log", "Real.log_le_sub_one_of_pos", "Real.add_pow_le_pow_mul_pow_of_sq_le_sq"],
        ["Mathlib.Data.Real.Basic"]),
    "Mathlib.Tactic.Linarith": ("linarith/nlinarith linear-arithmetic tactics",
        ["linarith", "nlinarith"], ["Mathlib.Data.Real.Basic"]),
    "Mathlib.Tactic.Positivity": ("positivity tactic for nonnegativity goals",
        ["positivity"], ["Mathlib.Data.Real.Basic"]),
    "Mathlib.Tactic.NormNum": ("norm_num numeric normalization", ["norm_num"], ["Mathlib.Data.Nat.Basic"]),
    "Mathlib.Tactic.Ring": ("ring/ring_nf commutative-ring normalization", ["ring", "ring_nf"], ["Mathlib.Data.Int.Basic"]),
}


def build_seed() -> list[dict[str, Any]]:
    return [{"module": mod, "doc": doc, "symbols": syms, "imports": imps}
            for mod, (doc, syms, imps) in SEED.items()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mathlib-src", type=Path, default=os.environ.get("WITSOC_MATHLIB_SRC"))
    ap.add_argument("--out", type=Path, default=Path(".witsoc/mathlib_atlas.json"))
    ap.add_argument("--max-files", type=int, default=6000)
    args = ap.parse_args()

    if args.mathlib_src and Path(args.mathlib_src).exists():
        nodes = build_from_source(Path(args.mathlib_src), args.max_files)
        source = f"parsed:{args.mathlib_src}"
    else:
        nodes = build_seed()
        source = "seed"

    atlas = {"schema": "witsoc.mathlib_atlas.v1", "source": source,
             "node_count": len(nodes), "nodes": nodes}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(atlas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "built", "source": source, "nodes": len(nodes), "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
