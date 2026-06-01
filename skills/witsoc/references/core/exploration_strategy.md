# Exploration Strategy

Use this before theorem search. Explorer should profile the problem, map it to a mathematical ontology, run backward chaining from the conclusion, and then search.

## Phase 0: Problem Profiling

Record:

```json
{
  "object_types": ["combinatorics"],
  "difficulty": "D3",
  "proof_styles": ["extremal", "probabilistic"],
  "known_theorem_density": "MEDIUM",
  "search_implications": ["try extremal examples before named theorem search"]
}
```

Object types:

- `algebra`
- `combinatorics`
- `geometry`
- `graph_theory`
- `number_theory`
- `analysis`
- `logic`
- `topology`
- `probability`
- `algorithms`

Difficulty:

- `D1`: routine calculation or direct known theorem.
- `D2`: short proof with one main idea.
- `D3`: multi-lemma proof, olympiad-level, or moderate formalization risk.
- `D4`: research-level local result, many possible approaches, substantial theorem search.
- `D5`: open-problem-scale, likely partial progress only.

Proof styles:

- `constructive`
- `extremal`
- `induction`
- `contradiction`
- `invariant`
- `probabilistic`
- `algebraic`
- `geometric`
- `analytic`
- `computational`

Known theorem density:

- `LOW`: likely needs construction, examples, or original lemmas.
- `MEDIUM`: named tools may help, but preconditions must be built.
- `HIGH`: theorem retrieval and premise selection dominate.

## Ontology Mapping

Identify mathematical structure before search:

```json
{
  "primary_structure": "graph",
  "features": ["bipartite", "matching"],
  "theorem_families": ["Hall", "Konig", "Menger", "max-flow min-cut"],
  "canonical_encodings": ["bipartite graph", "network flow"],
  "search_queries": ["Hall condition", "matching duality"]
}
```

Starter mappings:

- Graph -> bipartite -> matching -> Hall, Konig, max-flow min-cut.
- Graph -> connectivity -> cuts/paths -> Menger, ear decomposition.
- Graph -> coloring -> critical graph -> degeneracy, Brooks, discharging.
- Integers -> divisibility -> valuations -> modular arithmetic, LTE, p-adics.
- Integers -> primes -> congruences -> CRT, Dirichlet candidates, quadratic reciprocity.
- Sets -> extremal size -> forbidden pattern -> Erdos-Ko-Rado, sunflower, containers.
- Sequences -> recurrence -> generating functions, invariants, characteristic polynomials.
- Geometry -> incidence -> crossing/counting -> Szemeredi-Trotter, polynomial method.
- Analysis -> compactness/continuity -> EVT, fixed point, dominated convergence.
- Algebra -> groups/rings/modules -> homomorphism kernels, structure theorems, localization.

Treat mappings as retrieval hints, not proof dependencies.

## Theorem Retrieval Ranking

When ontology mapping or backward chaining suggests named tools, store ranked theorem candidates before committing to an external fact.

Record:

```json
{
  "theorem": "Hall's marriage theorem",
  "canonical_statement": "finite bipartite matching criterion",
  "similarity": 0.81,
  "prerequisites_satisfied": 0.9,
  "formal_availability": "YES",
  "expected_utility": "HIGH",
  "reason": "target asks for a matching under neighborhood-style hypotheses",
  "missing_preconditions": ["finite bipartite graph"],
  "weakest_usable_form": "Hall condition corollary for left-perfect matching",
  "source": "Mathlib theorem search or named textbook/survey",
  "source_type": "formal_library",
  "date_checked": "2026-05-31",
  "claim_supported": "finite bipartite matching criterion",
  "confidence_would_drop_if": ["graph is not finite", "neighborhood condition is weaker than Hall"],
  "rank": 1
}
```

Ranking factors:

- semantic similarity to the target or backward subgoal,
- percentage of preconditions already satisfied,
- formal/library availability,
- expected utility for unlocking proof objects or reducing gap count,
- cost of proving missing preconditions,
- whether a weaker local corollary suffices.

Use ranked theorem retrieval as a filter. Only promote a candidate to `external_facts` after its statement, preconditions, availability, and local replacement plan are clear.

Rejected theorem candidates are also useful. Record theorem-like matches that are not used:

```json
{
  "theorem": "Compactness theorem",
  "reason_rejected": "target space is not compact",
  "source": "analysis theorem list",
  "source_type": "survey",
  "date_checked": "2026-05-31",
  "blocked_by": ["compactness precondition fails"]
}
```

This prevents repeated bad retrieval.

## Confidence Calibration

Every score that affects search priority should state what would lower confidence:

- theorem similarity,
- prerequisite satisfaction,
- probability of completion,
- verifier friendliness,
- proof object confidence,
- conjecture rank.

Use calibration notes such as:

```text
Confidence would drop if the graph is infinite, if the theorem requires simple graphs, or if the available formal theorem has a stronger codomain.
```

Do not assign high scores without a falsifiable reason they could decrease.

## Source Discipline

For solved/open status and theorem candidates, record:

```json
{
  "source": "exact source or search result",
  "source_type": "primary | survey | preprint | formal_library | maintained_page | pointer | informal | none",
  "date_checked": "YYYY-MM-DD",
  "claim_supported": "specific status or theorem claim supported by this source"
}
```

Use pointer/informal sources only as leads unless they cite primary or formal sources.

## Solved Problem Reconstruction

When the problem is known solved, Explorer's goal is not to invent a fresh proof first. It must reconstruct the canonical proof landscape and verify exact alignment.

Record:

```json
{
  "literature_anchor": "canonical theorem or framework",
  "canonical_proof_landscape": ["standard proof route", "common corollary"],
  "target_domain": "exact structures in the user problem",
  "library_domain": "canonical theorem constraints",
  "domain_alignment": "exact | narrower | broader | mismatch | unknown",
  "boundary_checks": {
    "finiteness": "required and satisfied",
    "compactness": "not applicable",
    "smoothness": "C1 is enough",
    "nonzero": "x != 0 required",
    "nonsingular": "not applicable",
    "relative_primality": "gcd(a,b)=1 required"
  },
  "premise_minimization": {
    "direct_definition_unfolding": "fails because ...",
    "weakest_standard_tool": "specific corollary or local lemma",
    "avoided_heavy_machinery": ["full classification theorem"]
  }
}
```

Rules:

- Compare target domain and library theorem domain before using the theorem.
- Explicitly check finiteness, compactness, bounded variation, smoothness, nonzero, nonsingular, measurability, positivity, and relative-primality constraints when relevant.
- Prefer direct definition unfolding before external theorem invocation.
- If an external theorem is needed, isolate the weakest corollary or local sub-clause that solves the target.
- Do not hand a major theorem to Generator when a local lemma or elementary corollary suffices.

## Backward Chaining

For each conclusion, ask recursively:

```json
{
  "goal": "target conclusion",
  "would_follow_from": [
    {
      "subgoal": "sufficient condition",
      "justification": "theorem, definition, or planned lemma",
      "dependencies": [],
      "risk": "precondition not yet proved"
    }
  ]
}
```

Use backward chains to generate subgoals, theorem-family searches, and proof objects. For olympiad-style problems, backward chaining often outranks forward theorem search.

## Obstruction Discovery

Before trying to prove an open problem or D4/D5 target, ask why it might be false or hard.

Record at least three obstruction candidates when possible:

```json
{
  "id": "obstruction_1",
  "description": "lattice/grid configurations",
  "threatens": "desired lower bound",
  "evidence": "known extremal examples",
  "test": "check small grids or known construction",
  "status": "active"
}
```

Obstructions guide useful partial progress: counterexamples to stronger variants, barriers to methods, and sharpness examples.

## Open Problem Barrier Engine

For open or Erdős-style problems, shift from "prove the target" to "map the barrier" and "produce a finite or conditional product."

Barrier map:

```json
{
  "id": "barrier_1",
  "classical_obstruction": "Relativization / Natural Proofs / parity problem / lattice examples",
  "applies_to": "which naive strategy it blocks",
  "local_counter_strategy": "how a proposed mutation tries to bypass it",
  "degeneracy_stress_test": "n -> infinity, singular inputs, perfect powers, disconnected graphs, etc.",
  "status": "active"
}
```

Before strategy selection, record why naive historical approaches fail when that information is known. This prevents regenerating standard false proofs.

Open-product target: choose exactly one narrow product for Generator:

- `finite_counterexample`: minimize a boundary case showing a stronger variant is false.
- `obstruction_lemma`: prove that any counterexample must satisfy restrictive structural properties.
- `conditional_step`: prove `A -> B`, with `A` as an explicit unproved conjecture or external theorem.

Keep the boundary pristine: the original open problem remains `OPEN` unless a full proof has survived adversarial review and verification discipline.

## Falsification Pass Hierarchy

Run this before approach portfolio generation:

| Layer | Action | Target defect |
|---|---|---|
| `trivial_degenerate` | Evaluate at `0`, `1`, empty object, identity, singleton, or equality case. | Missing initialization or boundary. |
| `symmetry_parity` | Change signs, swap variables, reverse orientation, check parity or modular class. | Hidden sign, orientation, or invariant error. |
| `asymptotic_extremes` | Push parameters to infinity, limits, singular inputs, sparse/dense extremes. | Divergence, truncation, or false asymptotic intuition. |

Record the outcome of each layer. A failed layer should either produce a counterexample, a missing hypothesis, or a narrower target.

## Conjecture Mining

When examples or computations reveal a pattern, generate ranked conjectures:

```json
{
  "id": "conjecture_1",
  "statement": "precise conjecture",
  "evidence": ["n=1..8 checked"],
  "scope": "finite graphs with ...",
  "risk": "fails for sparse random examples",
  "rank": 0.72,
  "next_test": "search n=9 counterexamples"
}
```

Conjectures are not theorems. Use them to direct experiments, conditional results, and lemma discovery.

## Proof Objects

Store compositional proof objects, not only prose sketches:

```json
{
  "id": "proof_object_1",
  "target": "claim",
  "dependencies": ["lemma_1", "external_fact_1"],
  "subgoals": ["goal_1", "goal_2"],
  "confidence": 0.55,
  "gap_count": 2,
  "theorem_fidelity": 0.9,
  "formalization_risk": 0.4
}
```

Proof objects feed EV-ranked sketches and Generator handoffs.

## Search Budgets

Record budget before search:

```json
{
  "time_budget": "short | medium | long | explicit limit",
  "attempt_budget": 4,
  "computation_budget": "finite n <= 10",
  "stop_conditions": ["same blocker twice", "external theorem unavailable"]
}
```

Budgets prevent open-problem thrashing. If the budget is exhausted, report the best `PARTIAL`, `CONDITIONAL`, `FAILED_ATTEMPT`, or `GAP` state.

## Proof Compression

Before Generator writes WIT, compress the selected route into the smallest obligation graph that preserves theorem fidelity.

Record:

```json
{
  "selected_sketch_id": "sketch_1",
  "compression_goal": "remove unused detours and heavyweight theorem branches",
  "removed_obligations": ["unneeded case split"],
  "kept_obligations": ["target-critical lemma"],
  "target_fidelity_preserved": true,
  "risk": "compressed proof relies on one external theorem"
}
```

Compression must not weaken the target, hide theorem preconditions, or remove gaps.

## External Verification

Before relying on a major external theorem, record:

```json
{
  "theorem_name": "exact theorem",
  "source_library_availability": "Mathlib4 top-level | local library | unformalized paper | unknown",
  "exact_statement_needed": "sub-clause or corollary",
  "preconditions": ["finite", "compact", "NoZeroDivisors R"],
  "local_replacement_plan": "weaker lemma sufficient here",
  "downstream_risk": "if unavailable this artifact is GAP"
}
```

If the theorem is hallucinated, unavailable, or unformalized, Generator must see a `GAP` or local replacement plan rather than a vague citation.

## Mutation Tracker

When an approach fails, mutate exactly one dimension at a time:

- `strengthen_induction_hypothesis`: add an invariant or stronger induction claim.
- `domain_weakening`: temporarily narrow to a simpler algebraic/topological/combinatorial structure to locate the break.
- `duality_transformation_shift`: move to a dual formulation, such as primal-dual LP, Fourier/frequency domain, complement graph, or categorical dual.

Record:

```json
{
  "from_sketch": "sketch_1",
  "mutation": "duality_transformation_shift",
  "reason": "original route hits unresolved cut condition",
  "changed_dimension": "representation only",
  "unchanged_constraints": ["target theorem", "hypotheses"]
}
```

Do not rewrite the whole context after failure. Mutation tracking makes failures comparable and prevents drift.

## Lemma Economics

Rank lemmas by value before investing in them:

```text
lemma_value = goals_unlocked / proof_complexity
```

Record:

```json
{
  "goals_unlocked": 5,
  "proof_complexity": 2,
  "lemma_value": 2.5
}
```

Prefer lemmas that unlock many subgoals, reduce gap count, lower formalization risk, or replace expensive external theorems. Avoid low-value lemmas unless they are necessary for target fidelity.
