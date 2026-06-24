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
    "geometry": [
        {"target": "algebra_polynomial",
         "encoding": "encode points/incidences as polynomial (non)vanishing; apply the polynomial method / combinatorial Nullstellensatz",
         "preserves": "collinearity & incidence ↔ polynomial roots; degrees of freedom ↔ degree",
         "unlocks": ["polynomial partitioning", "Schwartz–Zippel", "Guth–Katz dimension counts"],
         "reflects": "an incidence/extremal-geometry bound becomes a degree/dimension bound"},
        {"target": "extremal_combinatorics",
         "encoding": "abstract the geometric configuration to its order-type / oriented-matroid, then count via Ramsey/Dilworth-type extremal arguments",
         "preserves": "convex-position & general-position predicates ↔ forbidden sub-configurations",
         "unlocks": ["Erdős–Szekeres cup–cap", "Ramsey bounds", "Dilworth/Mirsky chains"],
         "reflects": "a convexity obstruction becomes a forbidden monotone sub-configuration"},
    ],
    "combinatorics": [
        {"target": "linear_algebra_method",
         "encoding": "associate each set/object with a vector (incidence/inclusion or characteristic vector) over a field; an extremal family becomes a set of (near-)independent vectors",
         "preserves": "set intersections ↔ inner products; a forbidden intersection pattern ↔ a rank/independence constraint",
         "unlocks": ["dimension/rank bounds", "Frankl–Wilson", "tensor-power trick", "polynomial space method"],
         "reflects": "an extremal set-system bound becomes a dimension bound in a vector space"},
        {"target": "entropy_compression",
         "encoding": "encode a random member of the family by its structure; bound the family size by the entropy / a reversible encoding (spread + sunflower / entropy method)",
         "preserves": "family size ↔ encoding length; spread structure ↔ conditional entropy",
         "unlocks": ["Shearer's inequality", "spread/sunflower lemmas", "Lovász Local Lemma / entropy compression"],
         "reflects": "an extremal cardinality bound becomes an entropy / encoding-length bound"},
    ],
    "analysis": [
        {"target": "functional_analysis_operator",
         "encoding": "recast functions as vectors in a Banach/Hilbert space and the operation as a bounded operator; pointwise claims become operator-norm / spectral statements",
         "preserves": "convergence ↔ norm convergence; a kernel/transform ↔ an operator",
         "unlocks": ["duality / Hahn–Banach", "spectral theorem", "interpolation", "compactness in weak topology"],
         "reflects": "a pointwise obstruction becomes an unbounded-operator / divergent-norm obstruction"},
        {"target": "harmonic_fourier",
         "encoding": "pass to the Fourier/spectral side; smoothness and decay trade places",
         "preserves": "convolution ↔ multiplication; regularity ↔ frequency decay",
         "unlocks": ["Plancherel", "stationary phase", "Littlewood–Paley", "uncertainty principles"],
         "reflects": "a concentration obstruction becomes a frequency-support obstruction"},
    ],
    "algebra": [
        {"target": "representation_theory",
         "encoding": "act the group/ring on a vector space; structural questions become module/character statements",
         "preserves": "subgroup structure ↔ submodules; conjugacy ↔ characters",
         "unlocks": ["character orthogonality", "Schur's lemma", "Maschke / semisimplicity"],
         "reflects": "a structural obstruction becomes a non-trivial module decomposition"},
        {"target": "commutative_algebra_geometry",
         "encoding": "pass between an ideal and its vanishing locus (Nullstellensatz); algebra ↔ geometry of Spec",
         "preserves": "ideal containment ↔ subvariety inclusion; primes ↔ points",
         "unlocks": ["Hilbert basis/Nullstellensatz", "localization", "dimension theory"],
         "reflects": "a solvability obstruction becomes an empty/positive-dimensional variety"},
    ],
    "topology": [
        {"target": "algebraic_topology",
         "encoding": "apply a homology/homotopy functor; continuous obstructions become computable invariants",
         "preserves": "continuous maps ↔ induced homomorphisms; holes ↔ nontrivial classes",
         "unlocks": ["Borsuk–Ulam", "Lefschetz/Brouwer fixed points", "Mayer–Vietoris", "exact sequences"],
         "reflects": "a no-continuous-map obstruction becomes a nonzero (co)homology class"},
        {"target": "combinatorial_topology",
         "encoding": "triangulate / model the space as a simplicial complex or nerve; topology becomes finite combinatorics",
         "preserves": "covers ↔ nerves; connectivity ↔ complex connectivity",
         "unlocks": ["nerve lemma", "discrete Morse theory", "topological combinatorics (Lovász/Kneser)"],
         "reflects": "a topological obstruction becomes a property of a finite complex"},
    ],
    "probability": [
        {"target": "concentration_method",
         "encoding": "treat the quantity as a function of independent randomness; bound deviations by concentration",
         "preserves": "typical value ↔ expectation; rare events ↔ exponential tails",
         "unlocks": ["Azuma/McDiarmid", "Chernoff", "Talagrand", "second moment / Paley–Zygmund"],
         "reflects": "an existence obstruction becomes a positive-probability lower bound"},
        {"target": "martingale_stopping",
         "encoding": "expose the randomness step by step as a filtration; the process becomes a (sub/super)martingale",
         "preserves": "fair increments ↔ martingale; deadlines ↔ stopping times",
         "unlocks": ["optional stopping", "martingale convergence", "concentration via bounded differences"],
         "reflects": "a global expectation obstruction becomes a stopped-process identity"},
    ],
    "logic": [
        {"target": "model_theory",
         "encoding": "study the class of models of the theory; syntactic questions become semantic/structural ones",
         "preserves": "provability ↔ truth in all models; consistency ↔ a model exists",
         "unlocks": ["compactness", "Löwenheim–Skolem", "types / saturation", "quantifier elimination"],
         "reflects": "an unprovability obstruction becomes two models disagreeing"},
        {"target": "proof_complexity_sat",
         "encoding": "encode the statement as a propositional/first-order formula; hardness becomes proof-length / refutation complexity",
         "preserves": "validity ↔ unsatisfiability of the negation; a proof ↔ a refutation",
         "unlocks": ["resolution lower bounds", "interpolation", "SAT/SMT certificates"],
         "reflects": "a no-short-proof obstruction becomes a resolution-width lower bound"},
    ],
}

_DOMAIN_KEYWORDS = [
    ("geometry", ("point", "points", "plane", "convex", "polygon", "polytope",
                  "general position", "collinear", "incidence", "segment",
                  "distance", "triangle", "lattice point", "simplex", "halfplane")),
    ("graph_theory", ("graph", "vertex", "vertices", "edge", "edges", "clique",
                      "chromatic", "colouring", "coloring", "independent set",
                      "hamiltonian", "bipartite", "subgraph", "degree")),
    ("number_theory", ("prime", "divisor", "divisors", "modular", "congruence",
                       "diophantine", "integer", "perfect number", "gcd", "totient")),
    ("additive_combinatorics", ("sumset", "progression", "arithmetic progression",
                                "3-ap", "density", "sidon", "additive")),
    ("combinatorics", ("set system", "sunflower", "petals", "hypergraph", "uniform family",
                       "intersecting family", "family of sets", "union-closed", "shattering",
                       "vc dimension", "extremal set", "sperner", "covering design", "k-uniform")),
    ("analysis", ("continuous", "differentiable", "integral", "measure", "metric space",
                  "banach", "hilbert", "norm", "convergence", "lipschitz", "fourier",
                  "harmonic", "sobolev", "operator", "bounded function")),
    ("algebra", ("group", "subgroup", "ring", "ideal", "field extension", "module",
                 "homomorphism", "galois", "representation", "vector space", "matrix group",
                 "polynomial ring", "variety", "nullstellensatz")),
    ("topology", ("topological space", "homotopy", "homology", "cohomology", "manifold",
                  "simplicial", "fixed point", "compactness", "fundamental group",
                  "homeomorphism", "fibration", "cw complex", "borsuk")),
    ("probability", ("random", "probability", "expectation", "variance", "martingale",
                     "distribution", "almost surely", "concentration", "markov chain",
                     "stochastic", "random graph", "coupling", "chernoff")),
    ("logic", ("satisfiability", "first-order", "propositional", "model", "theory",
               "consistency", "decidable", "resolution", "cnf", "quantifier", "proof system",
               "completeness theorem", "undecidable")),
    ("order_theory", ("poset", "partial order", "lattice order", "antichain", "chain")),
]


def infer_domain(statement: str, domain: str = "") -> str:
    """Score every domain by keyword hits and return the best — scoring (not
    first-match) so a single collision keyword can't capture the classification
    (e.g. 'vertices of a polygon' should be geometry, not graph_theory). An
    explicit, recognized `domain` always wins."""
    if domain in PIVOTS:
        return domain
    text = f"{statement} {domain}".lower()
    scores: list[tuple[int, str]] = []
    for i, (dom, kws) in enumerate(_DOMAIN_KEYWORDS):
        hits = sum(1 for k in kws if k in text)
        if hits:
            # tie-break by table order (earlier = more specific), so negate index
            scores.append((hits * 100 - i, dom))
    if scores:
        return max(scores)[1]
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
