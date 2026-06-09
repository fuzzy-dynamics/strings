#!/usr/bin/env python3
"""Phase 4 move: the adversarial ONTOLOGY PIVOT.

When a barrier lemma resists the native-domain methods (fails twice without new
information), the Lovász playbook forbids another native attack and requires a
structure-preserving map to an ORTHOGONAL domain, where a different theory becomes
available (combinatorics → spectral graph theory, number theory → finite algebra,
order theory → topology, additive combinatorics → Fourier/linear algebra, …). This
proposes such pivots: source/target objects, the preservation law, which theorem
families open up, and the reflected obstruction — as SPECULATIVE leads that still
point back to the frozen target.

CALIBRATION: a pivot is a research DIRECTION, never a result. Every proposal is
`OPEN_UNFALSIFIED`/`SPECULATIVE`; the mapped subgoal must still be carried out and
kernel-checked. Analogy/pivot never manufactures a proof.

Usage:
  ontology_pivot.py --statement "<barrier>" [--domain D] [--k N] [--out J]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"

# source domain -> orthogonal target domains, each a functorial encoding with the
# theory it unlocks and the obstruction it reflects.
PIVOTS: dict[str, list[dict]] = {
    "graph_theory": [
        {"target": "spectral_graph_theory",
         "encoding": "encode the graph as its adjacency/Laplacian matrix; combinatorial quantities become eigenvalue/eigenvector statements",
         "preserves": "adjacency structure ↔ matrix entries; degree ↔ row sums",
         "unlocks": ["eigenvalue interlacing", "expander mixing lemma", "Cheeger inequality", "rank bounds"],
         "reflects": "a combinatorial obstruction becomes a spectral gap / rank obstruction"},
        {"target": "algebra_polynomial",
         "encoding": "encode incidences as polynomial (non)vanishing; use the combinatorial Nullstellensatz / polynomial method",
         "preserves": "forbidden configurations ↔ polynomial roots",
         "unlocks": ["combinatorial Nullstellensatz", "Schwartz–Zippel", "dimension arguments"],
         "reflects": "an extremal bound becomes a degree/dimension bound"},
    ],
    "number_theory": [
        {"target": "finite_algebra",
         "encoding": "work in ℤ/mℤ or a finite field; arithmetic constraints become finite-algebra / character-sum statements",
         "preserves": "congruences ↔ ring identities; multiplicativity ↔ characters",
         "unlocks": ["character sums", "Gauss/Jacobi sums", "finite-field geometry"],
         "reflects": "a local obstruction becomes a non-vanishing character sum"},
        {"target": "additive_fourier",
         "encoding": "encode the set as an indicator and pass to its Fourier transform",
         "preserves": "additive structure ↔ large Fourier coefficients",
         "unlocks": ["Fourier/L^p inequalities", "circle method", "Plancherel"],
         "reflects": "an additive obstruction becomes a spectrum/large-coefficient obstruction"},
    ],
    "additive_combinatorics": [
        {"target": "fourier_linear_algebra",
         "encoding": "pass to the Fourier transform of the indicator; structure ↔ spectrum",
         "preserves": "sumset growth ↔ Fourier concentration",
         "unlocks": ["Bogolyubov/Freiman machinery", "Plancherel", "Bohr sets"],
         "reflects": "small doubling becomes Fourier concentration on a Bohr set"},
        {"target": "ergodic_dynamics",
         "encoding": "transfer to a measure-preserving system via Furstenberg correspondence",
         "preserves": "density configurations ↔ recurrence",
         "unlocks": ["multiple recurrence", "structure/randomness dichotomy"],
         "reflects": "a density obstruction becomes a non-recurrence obstruction"},
    ],
    "order_theory": [
        {"target": "topology",
         "encoding": "give the order its Alexandrov/Scott topology; order properties become topological ones",
         "preserves": "≤ ↔ specialization order; directed sups ↔ limits",
         "unlocks": ["compactness", "continuity/closure arguments"],
         "reflects": "an order obstruction becomes a non-closed / non-compact witness"},
    ],
}

_DOMAIN_KEYWORDS = [
    ("graph_theory", ("graph", "vertex", "vertices", "edge", "clique", "tree", "chromatic", "triangle")),
    ("number_theory", ("prime", "divisor", "divisors", "modular", "congruence", "diophantine", "integer", "perfect")),
    ("additive_combinatorics", ("sumset", "progression", "arithmetic progression", "3-ap", "density", "sidon", "additive")),
    ("order_theory", ("poset", "order", "lattice", "monotone", "chain", "antichain")),
]


def infer_domain(statement: str, domain: str = "") -> str:
    if domain in PIVOTS:
        return domain
    text = f"{statement} {domain}".lower()
    for dom, kws in _DOMAIN_KEYWORDS:
        if any(k in text for k in kws):
            return dom
    return domain or "other"


def pivots(statement: str, domain: str = "", k: int = 3) -> list[dict]:
    dom = infer_domain(statement, domain)
    out = []
    for p in PIVOTS.get(dom, [])[:k]:
        out.append({
            "source_domain": dom,
            "target_domain": p["target"],
            "encoding": p["encoding"],
            "preservation_law": p["preserves"],
            "unlocks_theory": p["unlocks"],
            "reflected_obstruction": p["reflects"],
            "status": OPEN, "arena": ARENA,
            "next_action": "state the mapped subgoal in the target domain, keep its dependency path to "
                           "the frozen target, then kernel-dispatch / search there",
        })
    return out


def suggest(statement: str, domain: str = "", k: int = 3) -> dict:
    dom = infer_domain(statement, domain)
    ps = pivots(statement, domain, k)
    for p in ps:
        assert p["status"] == OPEN and p["arena"] == ARENA, "ontology pivot must not assign trust"
    return {
        "schema": "witsoc.ontology_pivot.v1",
        "target": statement,
        "source_domain": dom,
        "pivots": ps,
        "calibration": "pivots are SPECULATIVE research directions; the mapped subgoal must still be "
                       "carried out and kernel-checked. A pivot never manufactures a proof.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statement", required=True)
    ap.add_argument("--domain", default="")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    result = suggest(args.statement, args.domain, args.k)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
