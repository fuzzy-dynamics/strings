#!/usr/bin/env python3
"""Emit Lovasz campaign templates for recurring open-problem barriers."""

from __future__ import annotations

import argparse
import json


INDUCED_TREE_TRIANGLE_FREE = {
    "campaign": "induced_trees_triangle_free_high_chromatic",
    "status": "template",
    "actual_lemma_queue": [
        {
            "lemma_id": "L_private_neighbor_leaf_extension",
            "statement": "Given an induced copy of T minus a leaf in a triangle-free high-chromatic graph, find a neighbor of the attachment vertex anticomplete to the rest of the embedded tree.",
            "unlocks": "leaf-extension induction for induced finite trees",
            "priority": 10,
            "status": "OPEN",
            "next_attempt": "search for finite obstruction and test neighborhood-hypergraph reformulation",
        },
        {
            "lemma_id": "L_chromatic_reservoir",
            "statement": "After embedding a partial induced tree, preserve a high-chromatic reservoir avoiding all forbidden chords to the current embedding.",
            "unlocks": "iterated induced tree embedding without chord creation",
            "priority": 9,
            "status": "OPEN",
            "next_attempt": "model forbidden chords as a covering problem and test on Mycielski/high-girth samples",
        },
        {
            "lemma_id": "L_compactness_chi_bounding_equivalence",
            "statement": "For fixed finite T, the infinite triangle-free induced-T-free question is equivalent to bounded chromatic number of finite {K3,T}-free graphs.",
            "unlocks": "formal reduction between infinite and finite formulations",
            "priority": 8,
            "status": "REDUCTION_CANDIDATE",
            "claim_scope": "candidate_only",
            "trust_boundary": "lovasz_candidate_only",
            "next_attempt": "formalize de Bruijn-Erdos/disjoint-union reduction in WIT/Lean if libraries permit",
        },
    ],
    "proof_dependency_dag": [
        {
            "node_id": "N0",
            "type": "actual_barrier_lemma",
            "statement": "Private-neighbor leaf-extension lemma for induced tree embeddings in triangle-free high-chromatic graphs.",
            "depends_on": [],
            "status": "OPEN",
            "relation_to_frozen_target": "Would give the natural induction for every fixed finite tree.",
            "counterexample_pressure": "K_{n,n} defeats degree-only variants; search for high-chromatic variants.",
            "theorem_precondition_gap": "Need high-chromatic reservoir not just high degree.",
            "next_exact_attempt": "Neighborhood-hypergraph reservoir lemma or finite obstruction search.",
        },
        {
            "node_id": "N1",
            "type": "counterexample_search",
            "statement": "Search finite triangle-free high-chromatic graph families omitting selected small induced trees.",
            "depends_on": ["N0"],
            "status": "OPEN",
            "relation_to_frozen_target": "A persistent finite family would refute the finite chi-bounding formulation.",
        },
        {
            "node_id": "N2",
            "type": "reduction",
            "statement": "Compactness/disjoint-union equivalence between infinite and finite formulations for fixed finite T.",
            "depends_on": [],
            "status": "REDUCTION_CANDIDATE",
            "claim_scope": "candidate_only",
            "trust_boundary": "lovasz_candidate_only",
            "relation_to_frozen_target": "Clarifies finite answer target and formalizes known-open classification.",
        },
    ],
    "worker_plan": [
        {
            "worker_type": "COUNTEREXAMPLE",
            "target_node_id": "N1",
            "exact_statement": "Find or rule out within bounded families a finite triangle-free high-chromatic graph omitting a selected induced finite tree T.",
            "expected_artifact": "counterexample_certificate",
            "forbidden_drift": "Do not omit non-induced copies; do not allow triangles; do not switch to a different tree without recording variant status.",
        },
        {
            "worker_type": "MINER",
            "target_node_id": "N0",
            "exact_statement": "Mine Mycielski, high-girth, random triangle-free, and critical graph samples for stable induced-tree extension/reservoir invariants.",
            "expected_artifact": "invariant_report",
            "forbidden_drift": "Do not mine non-triangle-free samples as evidence for the triangle-free target.",
        },
        {
            "worker_type": "SKEPTIC",
            "target_node_id": "N0",
            "exact_statement": "Audit the private-neighbor leaf-extension lemma for hidden high-degree/high-chromatic substitutions and chord-avoidance failures.",
            "expected_artifact": "counterexample_certificate",
            "forbidden_drift": "Do not accept a lemma that only controls adjacency to neighbors of the attachment vertex.",
        },
        {
            "worker_type": "FORMALIZER",
            "target_node_id": "N2",
            "exact_statement": "Formalize the compactness/disjoint-union equivalence for fixed finite T as a WIT target and Lean target if feasible.",
            "expected_artifact": "WIT",
            "forbidden_drift": "Do not formalize the full Gyarfas-Sumner conjecture; formalize only the equivalence/reduction.",
        },
    ],
}


DIVISOR_SUM_ASYMPTOTIC = {
    "campaign": "divisor_sum_exact_subsequence_asymptotic",
    "status": "template",
    "actual_lemma_queue": [
        {
            "lemma_id": "L_exact_subsequence_saving",
            "statement": "For exact multiperfect numbers sigma(n)=k*n, identify a structural condition forcing sigma(n)/n = o(log log n) on that subsequence.",
            "unlocks": "little-oh strengthening beyond Gronwall's maximal-order envelope",
            "priority": 10,
            "status": "OPEN",
            "next_attempt": "separate record-high abundancy constructions from exact integer abundancy constraints",
        },
        {
            "lemma_id": "L_large_k_prime_support",
            "statement": "If sigma(n)=k*n and k grows, prove or disprove that omega(n) and the prime-exponent pattern impose log log n / k -> infinity.",
            "unlocks": "rules out positive-proportion k/log log n counterexample sequences",
            "priority": 9,
            "status": "OPEN",
            "next_attempt": "mine known multiperfect records and constrained divisor-product equations",
        },
        {
            "lemma_id": "L_constructive_counterfamily",
            "statement": "Search for a parametric exact multiperfect construction with k >= c*log log n along an infinite family.",
            "unlocks": "potential disproof of the little-oh statement",
            "priority": 8,
            "status": "OPEN",
            "next_attempt": "SMT/Diophantine encoding of divisor-sum product constraints for bounded prime support growth",
        },
    ],
    "proof_dependency_dag": [
        {
            "node_id": "N0",
            "type": "actual_barrier_lemma",
            "statement": "Exact integer abundancy must create a saving over the Gronwall envelope.",
            "depends_on": [],
            "status": "OPEN",
            "relation_to_frozen_target": "This is the missing step in proving k=o(log log n).",
        },
        {
            "node_id": "N1",
            "type": "counterexample_search",
            "statement": "Search bounded prime-exponent divisor-sum equations for high k/log log n exact multiperfect candidates.",
            "depends_on": ["N0"],
            "status": "OPEN",
            "relation_to_frozen_target": "A scalable family would refute the target; failures identify arithmetic obstructions.",
        },
        {
            "node_id": "N2",
            "type": "asymptotic_obstruction",
            "statement": "Audit every proposed O/o transition with the asymptotic analyzer before using it in proof synthesis.",
            "depends_on": [],
            "status": "CHECKED_REQUIRED",
            "relation_to_frozen_target": "Prevents replacing O(log log n) with o(log log n) by envelope confusion.",
        },
    ],
    "worker_plan": [
        {
            "worker_type": "MINER",
            "target_node_id": "N1",
            "exact_statement": "Mine exact multiperfect records and bounded divisor-product equations for stable structural constraints.",
            "expected_artifact": "invariant_report",
            "forbidden_drift": "Do not use abundant numbers that are not exact integer-abundancy multiperfect numbers.",
        },
        {
            "worker_type": "COMPUTATION",
            "target_node_id": "N1",
            "exact_statement": "Run bounded search over prime supports and exponents for sigma(n)/n integer and large k/log log n.",
            "expected_artifact": "python_script",
            "forbidden_drift": "Do not report finite ratios as asymptotic proof.",
        },
        {
            "worker_type": "SKEPTIC",
            "target_node_id": "N2",
            "exact_statement": "Reject any step deriving little-oh from Gronwall/Robin maximal-order bounds alone.",
            "expected_artifact": "obstruction_report",
            "forbidden_drift": "Do not accept O(log log n) as evidence for o(log log n).",
        },
    ],
}


RAMSEY_EXTREMAL = {
    "campaign": "ramsey_extremal_barrier_campaign",
    "status": "template",
    "actual_lemma_queue": [
        {
            "lemma_id": "L_threshold_constant",
            "statement": "Identify the sharp threshold constant or exponent separating the construction regime from the forcing regime.",
            "unlocks": "turns broad Ramsey/extremal target into a bounded asymptotic inequality",
            "priority": 10,
            "status": "OPEN",
            "next_attempt": "mine extremal constructions and pass every asymptotic transition through the analyzer",
        },
        {
            "lemma_id": "L_container_or_random_lower_bound",
            "statement": "Either prove a container/regularity upper bound or construct a random/probabilistic lower-bound family matching the barrier.",
            "unlocks": "narrows the gap to a precise exponent/constant",
            "priority": 9,
            "status": "OPEN",
            "next_attempt": "split into deterministic small-model search and asymptotic proof audit",
        },
    ],
    "proof_dependency_dag": [
        {
            "node_id": "N0",
            "type": "actual_barrier_lemma",
            "statement": "Sharp threshold/exponent barrier for the frozen Ramsey/extremal statement.",
            "depends_on": [],
            "status": "OPEN",
            "relation_to_frozen_target": "Controls whether the target is provable, false, or only partial at current strength.",
        },
        {
            "node_id": "N1",
            "type": "counterexample_search",
            "statement": "Enumerate and mutate finite extremal witnesses at small sizes; inflate any witness into a candidate family.",
            "depends_on": ["N0"],
            "status": "OPEN",
            "relation_to_frozen_target": "Supplies obstruction pressure before proof synthesis.",
        },
    ],
    "worker_plan": [
        {
            "worker_type": "COUNTEREXAMPLE",
            "target_node_id": "N1",
            "exact_statement": "Search bounded finite graphs/hypergraphs for extremal witnesses against the frozen statement.",
            "expected_artifact": "counterexample_certificate",
            "forbidden_drift": "Do not change forbidden subgraph, color count, or density threshold without variant-ledger entry.",
        },
        {
            "worker_type": "MINER",
            "target_node_id": "N0",
            "exact_statement": "Mine extremal samples for stable degree, density, independence, clique, and chromatic invariants.",
            "expected_artifact": "invariant_report",
            "forbidden_drift": "Do not use non-extremal random samples as threshold evidence without labeling them exploratory.",
        },
    ],
}


ADDITIVE_COMBINATORICS = {
    "campaign": "additive_combinatorics_structure_randomness_campaign",
    "status": "template",
    "actual_lemma_queue": [
        {
            "lemma_id": "L_structure_randomness_split",
            "statement": "Decompose the target set/function into structured and uniform components with a quantified error term strong enough for the frozen conclusion.",
            "unlocks": "connects density increment, Fourier, or energy methods to the original target",
            "priority": 10,
            "status": "OPEN",
            "next_attempt": "test finite cyclic groups and mine energy/Fourier invariants",
        },
        {
            "lemma_id": "L_density_increment",
            "statement": "If the target configuration is absent, prove a density increment on a controlled substructure.",
            "unlocks": "iterative proof or explicit obstruction",
            "priority": 9,
            "status": "OPEN",
            "next_attempt": "formalize a finite-group special case and test iteration losses symbolically",
        },
    ],
    "proof_dependency_dag": [
        {
            "node_id": "N0",
            "type": "actual_barrier_lemma",
            "statement": "Quantified structure/randomness or density-increment lemma with losses matching the target.",
            "depends_on": [],
            "status": "OPEN",
            "relation_to_frozen_target": "This is usually where open additive-combinatorics statements fail or become partial.",
        },
        {
            "node_id": "N1",
            "type": "computational_certificate",
            "statement": "Bounded finite-group search for configurations, obstructions, and candidate invariants.",
            "depends_on": ["N0"],
            "status": "OPEN",
            "relation_to_frozen_target": "Guides which lemma should be attacked formally.",
        },
    ],
    "worker_plan": [
        {
            "worker_type": "MINER",
            "target_node_id": "N1",
            "exact_statement": "Mine finite cyclic/vector-space samples for stable sumset, energy, density, and configuration-count invariants.",
            "expected_artifact": "invariant_report",
            "forbidden_drift": "Do not switch ambient group or density convention without recording a variant.",
        },
        {
            "worker_type": "FORMALIZER",
            "target_node_id": "N0",
            "exact_statement": "Formalize the narrow finite-group lemma before any asymptotic generalization is claimed.",
            "expected_artifact": "WIT",
            "forbidden_drift": "Do not hide quantitative loss terms.",
        },
    ],
}


DIOPHANTINE = {
    "campaign": "diophantine_local_global_campaign",
    "status": "template",
    "actual_lemma_queue": [
        {
            "lemma_id": "L_local_obstruction",
            "statement": "Find a congruence, valuation, descent, or height obstruction that rules out the target solutions.",
            "unlocks": "disproof or conditional classification",
            "priority": 10,
            "status": "OPEN",
            "next_attempt": "bounded search over primes/moduli and SMT-style constraint synthesis",
        },
        {
            "lemma_id": "L_parametric_family",
            "statement": "If solutions exist, generalize a bounded solution into a parametrized family and verify it symbolically.",
            "unlocks": "constructive theorem or counterexample family",
            "priority": 9,
            "status": "OPEN",
            "next_attempt": "inflate computational witnesses into algebraic identities",
        },
    ],
    "proof_dependency_dag": [
        {
            "node_id": "N0",
            "type": "counterexample_search",
            "statement": "Bounded integer/rational search with modular and height filters.",
            "depends_on": [],
            "status": "OPEN",
            "relation_to_frozen_target": "Finds examples, disproofs, or local obstruction candidates.",
        },
        {
            "node_id": "N1",
            "type": "actual_barrier_lemma",
            "statement": "Descent/local-global/height lemma explaining the bounded evidence.",
            "depends_on": ["N0"],
            "status": "OPEN",
            "relation_to_frozen_target": "Turns computation into proof or honest partial result.",
        },
    ],
    "worker_plan": [
        {
            "worker_type": "COMPUTATION",
            "target_node_id": "N0",
            "exact_statement": "Run bounded Diophantine search and modular obstruction scans.",
            "expected_artifact": "python_script",
            "forbidden_drift": "Do not treat bounded absence as proof of global insolubility.",
        },
        {
            "worker_type": "FORMALIZER",
            "target_node_id": "N1",
            "exact_statement": "Formalize any proposed congruence, descent, or parametric identity as WIT first and Lean where feasible.",
            "expected_artifact": "WIT",
            "forbidden_drift": "Do not omit side conditions such as nonzero denominators, coprimality, or positivity.",
        },
    ],
}


TEMPLATES = {
    "additive-combinatorics": ADDITIVE_COMBINATORICS,
    "diophantine": DIOPHANTINE,
    "divisor-sum-asymptotic": DIVISOR_SUM_ASYMPTOTIC,
    "induced-tree-triangle-free": INDUCED_TREE_TRIANGLE_FREE,
    "ramsey-extremal": RAMSEY_EXTREMAL,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", choices=sorted(TEMPLATES), required=True)
    args = parser.parse_args()
    print(json.dumps(TEMPLATES[args.template], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
