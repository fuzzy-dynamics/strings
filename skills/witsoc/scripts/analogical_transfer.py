#!/usr/bin/env python3
"""Phase 3 (idea generator): analogical transfer of proof techniques.

The hardest gap is taste — knowing WHICH technique a barrier wants. This does the
mechanical part honestly: it featurizes a frozen target/barrier and matches it
against a curated knowledge base of solved-problem patterns ("this shape of problem
was historically cracked by technique Y / construction Z"), then emits RANKED,
SPECULATIVE technique suggestions for the Lovász barrier attack.

These are HINTS, not claims. Every suggestion is `status = OPEN_UNFALSIFIED`,
`arena = SPECULATIVE`; it only allocates the search's attention. The technique still
has to be carried out and the resulting lemma kernel-checked — analogy can never
manufacture a proof. (Same calibration spine as concept_generator/domain_barrier_lemmas.)

Usage:
  analogical_transfer.py --statement "<target/barrier>" [--domain D] [--k N]
      [--out technique_suggestions.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

OPEN = "OPEN_UNFALSIFIED"
ARENA = "SPECULATIVE"

# Curated analogy base: (technique, construction, trigger concepts, example, what-it-unlocks).
# Triggers are concept tags extracted from the goal by `concepts()` below.
KB: list[dict] = [
    {"technique": "generalize_the_invariant",
     "construction": "Strengthen the induction hypothesis: replace a fixed argument/constant by a universally quantified variable and prove the generalized identity, then specialize.",
     "triggers": ["recurrence", "accumulator", "induction", "nat"],
     "example": "tail-recursive sum: `f n 0` needs `∀ n a, f n a = a + g n`.",
     "unlocks": "goals where direct induction's hypothesis is too weak"},
    {"technique": "multiplicativity_euler_product",
     "construction": "Use multiplicativity: reduce the claim to prime powers and recombine via the Euler product / CRT.",
     "triggers": ["divisor", "sigma", "prime", "multiplicative", "number_theory"],
     "example": "σ and φ are multiplicative ⇒ check on p^k.",
     "unlocks": "arithmetic-function identities and bounds"},
    {"technique": "probabilistic_method_alteration",
     "construction": "Random construction + alteration: pick a random object, delete the few bad parts; or apply the Lovász Local Lemma to avoid all bad events.",
     "triggers": ["exists", "lower_bound", "set", "additive", "graph", "coloring"],
     "example": "Ramsey lower bounds; sets with no 3-AP via random+delete.",
     "unlocks": "existence / lower-bound goals over large structures"},
    {"technique": "extremal_stability",
     "construction": "Identify the (near-)extremal configuration; prove every other case is strictly dominated (stability), then close the unique extremal case.",
     "triggers": ["extremal", "graph", "forbidden_subgraph", "maximum", "minimum"],
     "example": "Turán / Erdős–Stone: the extremal graph is Turán's graph.",
     "unlocks": "extremal graph/set bounds"},
    {"technique": "density_increment",
     "construction": "If the set lacks the desired structure, pass to a subprogression / subspace where its relative density strictly increases; iterate to a contradiction.",
     "triggers": ["additive", "density", "progression", "set"],
     "example": "Roth's theorem: no 3-AP ⇒ density increment on a subprogression.",
     "unlocks": "additive-combinatorics structure theorems"},
    {"technique": "minimal_counterexample_descent",
     "construction": "Assume a minimal counterexample (by some size measure) and derive a strictly smaller one — infinite descent / well-ordering.",
     "triggers": ["nat", "integer", "forall", "divisor"],
     "example": "√2 irrational; FLT n=4 by descent.",
     "unlocks": "universal arithmetic statements"},
    {"technique": "local_global_reduction",
     "construction": "Separate local (mod p / p-adic) constraints from the global statement; solve locally everywhere then audit the lifting/obstruction.",
     "triggers": ["congruence", "mod", "prime", "number_theory", "diophantine"],
     "example": "Hasse principle; covering congruences.",
     "unlocks": "Diophantine solvability questions"},
    {"technique": "double_counting_pigeonhole",
     "construction": "Count a well-chosen quantity two ways, or apply pigeonhole to a carefully chosen map, to force the desired configuration.",
     "triggers": ["exists", "finite", "count", "set", "graph"],
     "example": "Erdős–Ko–Rado via shifting; many existence proofs.",
     "unlocks": "existence/counting goals over finite structures"},
    {"technique": "algebraization_spectral",
     "construction": "Encode the combinatorial object as a matrix/polynomial (adjacency, Laplacian, generating function) and bound it via eigenvalues / linear algebra.",
     "triggers": ["graph", "eigenvalue", "matrix", "spectral", "polynomial"],
     "example": "expander mixing lemma; combinatorial Nullstellensatz.",
     "unlocks": "pseudorandomness and algebraic extremal bounds"},
    {"technique": "ramsey_cup_cap_order_type",
     "construction": "Abstract the point set to its order type / oriented matroid, then force a long monotone (cup/cap) sub-configuration via Ramsey or Dilworth — the Erdős–Szekeres engine.",
     "triggers": ["convex_geometry", "geometry", "exists", "lower_bound", "set"],
     "example": "Erdős–Szekeres: 2^{n-2}+1 points in general position contain a convex n-gon.",
     "unlocks": "convex-position / order-type existence bounds"},
    {"technique": "polynomial_partitioning_incidence",
     "construction": "Encode points/lines as polynomial vanishing and cut space with a low-degree polynomial (polynomial partitioning) to bound incidences and distances.",
     "triggers": ["convex_geometry", "geometry", "incidence", "count"],
     "example": "Guth–Katz distinct distances; Szemerédi–Trotter via partitioning.",
     "unlocks": "incidence, distance, and extremal-geometry bounds"},
]

# Concept tags extracted from a goal's text (keyword families).
_CONCEPTS: list[tuple[str, tuple[str, ...]]] = [
    ("nat", ("nat", "ℕ")), ("integer", ("integer", "int", "ℤ")),
    ("forall", ("∀", "for all", "every")), ("exists", ("∃", "there exists", "exists")),
    ("divisor", ("divisor", "divisors", "divides", "∣", "dvd")),
    ("sigma", ("sigma", "σ", "sum of divisors", "perfect", "abundant")),
    ("prime", ("prime",)), ("multiplicative", ("multiplicative", "euler", "totient", "φ")),
    ("congruence", ("congruence", "residue")), ("mod", ("mod", "%", "≡")),
    ("diophantine", ("diophantine", "equation", "x y z", "rational")),
    ("convex_geometry", ("convex", "polygon", "general position", "convex position",
                         "convex hull", "order type")),
    ("geometry", ("points", "plane", "collinear", "incidence", "segment",
                  "distance", "polytope", "simplex")),
    ("incidence", ("incidence", "incidences", "lines", "collinear")),
    ("graph", ("graph", "vertex", "vertices", "edge", "clique", "tree", "cycle")),
    ("coloring", ("coloring", "colour", "chromatic")),
    ("forbidden_subgraph", ("forbidden", "subgraph", "triangle-free", "k_")),
    ("extremal", ("extremal", "turán", "turan", "maximum number", "largest")),
    ("maximum", ("maximum", "max", "largest", "supremum")), ("minimum", ("minimum", "min", "smallest")),
    ("additive", ("sumset", "a+a", "arithmetic progression", "additive", "sidon")),
    ("density", ("density", "dense")), ("progression", ("progression", "ap", "3-ap", "3-term")),
    ("set", ("set", "subset", "family", "collection")),
    ("lower_bound", ("lower bound", "at least", "≥", "lower-bound")),
    ("count", ("count", "number of", "cardinality", "|")),
    ("finite", ("finite", "finset")),
    ("recurrence", ("recurrence", "recursive", "| 0 =>", "| (n+1)")),
    ("accumulator", ("acc", "accumulator")),
    ("induction", ("induction", "inductive")),
    ("eigenvalue", ("eigenvalue", "spectral", "spectrum")),
    ("matrix", ("matrix", "adjacency", "laplacian")),
    ("polynomial", ("polynomial", "nullstellensatz")),
    ("number_theory", ("prime", "divisor", "modular", "diophantine", "integer")),
    ("spectral", ("spectral", "eigenvalue")),
]


def concepts(statement: str, domain: str = "") -> set[str]:
    text = f"{statement} {domain}".lower()
    tags: set[str] = set()
    for tag, kws in _CONCEPTS:
        if any(k in text for k in kws):
            tags.add(tag)
    return tags


def suggest(statement: str, domain: str = "", k: int = 4, atlas: Path | None = None) -> list[dict]:
    tags = concepts(statement, domain)
    scored = []
    for entry in KB:
        trig = set(entry["triggers"])
        overlap = tags & trig
        if not overlap:
            continue
        # Jaccard-ish relevance, with a small bonus for covering more of the triggers.
        score = len(overlap) / len(trig | tags) + 0.1 * len(overlap)
        scored.append((score, overlap, entry))
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, overlap, entry in scored[:k]:
        out.append({
            "technique": entry["technique"],
            "construction": entry["construction"],
            "matched_concepts": sorted(overlap),
            "analogy_example": entry["example"],
            "unlocks": entry["unlocks"],
            "relevance": round(score, 4),
            "status": OPEN,            # a HINT — never a claim
            "arena": ARENA,
            "next_action": "instantiate this technique as a concrete barrier lemma "
                           "(domain_barrier_lemmas / concept_generator), then kernel-dispatch it",
        })
    # GROWN analogies: the technique atlas (proof_autopsy) holds moves harvested
    # from this system's own kernel-verified closures — taste that compounds
    # across runs instead of staying a hand-curated list. Same calibration: hints only.
    try:
        from proof_autopsy import suggest_from_atlas
        seen = {s["technique"] for s in out}
        for s in suggest_from_atlas(statement, atlas_path=atlas, k=k):
            if s["technique"] not in seen:
                out.append(s)
    except Exception:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statement", required=True)
    ap.add_argument("--domain", default="")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    suggestions = suggest(args.statement, args.domain, args.k)
    # CALIBRATION (structural): every suggestion is a SPECULATIVE hint, never trusted.
    for s in suggestions:
        assert s["status"] == OPEN and s["arena"] == ARENA, "analogical transfer must not assign trust"
    result = {
        "schema": "witsoc.analogical_transfer.v1",
        "target": args.statement,
        "concepts": sorted(concepts(args.statement, args.domain)),
        "suggested_techniques": suggestions,
        "calibration": "suggestions are SPECULATIVE technique hints; they allocate the search's "
                       "attention only. The technique must be carried out and the resulting lemma "
                       "kernel-checked — analogy never manufactures a proof.",
    }
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
