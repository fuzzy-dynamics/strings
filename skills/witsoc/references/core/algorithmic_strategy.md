# Algorithmic Strategy

Witsoc algorithms provide decision support. They rank lanes, barriers,
products, mutations, and stop/continue options. They never decide mathematical
truth and never override the orchestrator's strategy authority.

## Boundary

Algorithms may:

- score candidate actions;
- explain why an option is promising or risky;
- surface alternatives;
- recommend validators;
- penalize repeated failures;
- identify the best reportable product.

Algorithms must not:

- emit `SOLVED`, `VERIFIED`, or `CHECKED` unless copying an existing validated
  ledger status with its evidence;
- authorize Generator;
- claim a full solution;
- block the orchestrator from trying a creative route;
- turn an advisory ranking into a hard workflow.

Validators decide trust. The orchestrator decides strategy.

## Shared Scoring Dimensions

Scores are normalized to `[0, 1]` and should include reasons.

- `target_relevance`: how directly the option connects to the frozen target.
- `evidence_potential`: chance of producing checkable evidence.
- `verifier_friendliness`: how likely the result can be checked/formalized.
- `uncertainty_reduction`: how much the option clarifies the open core.
- `novelty_potential`: chance of producing nontrivial progress.
- `dependency_centrality`: how much a DAG node blocks the target.
- `cost`: rough runtime/human/agent cost.
- `repeat_risk`: chance this repeats a known failed approach.
- `user_value`: usefulness for the requested deliverable.

## Core Algorithms

### Attackability

Estimate whether the target should be attacked by formalization, computation,
counterexample pressure, barrier decomposition, or creative ideation.

```text
attackability =
  0.25 * formalization_readiness
+ 0.20 * counterexample_searchability
+ 0.20 * known_theorem_connectivity
+ 0.15 * decomposition_potential
+ 0.10 * computational_tractability
+ 0.10 * novelty_or_user_value
- 0.20 * repeat_failure_risk
- 0.15 * foundation_or_status_risk
```

### Lane Ranking

Rank a deep-run mission menu.

```text
lane_score =
  0.30 * expected_evidence_gain
+ 0.20 * target_relevance
+ 0.15 * verifier_friendliness
+ 0.15 * uncertainty_reduction
+ 0.10 * novelty_potential
+ 0.10 * cheapness
- 0.25 * repeat_risk
```

### Barrier Selection

Choose which barrier or DAG node is worth attacking next.

```text
node_score =
  0.35 * dependency_centrality
+ 0.25 * unlock_value
+ 0.15 * formalization_readiness
+ 0.15 * evidence_available
+ 0.10 * theorem_connectivity
- 0.25 * repeat_failure_risk
```

### Mutation Selection

Select a one-axis mutation from the current gap class.

```text
mutation_score =
  0.30 * gap_match
+ 0.20 * novelty_against_failure_memory
+ 0.20 * verification_friendliness
+ 0.15 * expected_unlock
+ 0.15 * cheapness
```

### Best Product Selection

Rank the current products for reportability.

```text
product_score =
  0.35 * evidence_strength
+ 0.25 * target_fidelity
+ 0.15 * dependency_path_quality
+ 0.10 * novelty
+ 0.10 * formalization_readiness
+ 0.05 * user_value
- 0.30 * remaining_gap_penalty
```

### Stop/Continue

Decide whether the run needs repair, bus fulfillment, continuation, honest stop,
or user input.

```text
failed_gate -> repair_gate
bus_pending -> continue_after_bus
reviewed verified/checkable product -> stop_honestly_with_product
open barrier and next mutation -> continue
all lanes failed with failure classes -> stop_honestly_with_barrier_report
target unclear -> ask_user
otherwise -> continue_lowest_cost_uncertainty_reduction
```

### Portfolio Allocation

Suggest worker allocation from ranked lanes.

```text
workers_i = round(total_workers * lane_score_i / sum(lane_scores))
```

Constraints:

- at least one skeptic lane when promoting a product;
- at least one counterexample lane for open-style targets when available;
- at most 40% idea-generation unless no formalizable rung exists;
- at least one formalization lane if WIT/Lean is requested and available.

Every allocation is advisory.
