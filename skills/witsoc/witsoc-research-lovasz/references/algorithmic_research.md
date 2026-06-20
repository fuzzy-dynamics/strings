# Algorithmic Research Decision Support

Lovasz algorithms are advisory mathematical decision support. They rank proof
DAG nodes, worker results, gap mutations, and next actions so the orchestrator
can allocate attention more effectively. They do not decide truth, authorize
Generator, or constrain the orchestrator's creative strategy.

## Boundary

Lovasz algorithms may:

- rank open proof-DAG nodes by target relevance and unlock value;
- identify the best next actual barrier lemma to attack;
- rank one-axis mutations after gap feedback;
- rank worker results for Explorer review and reporting;
- recommend worker types for a node;
- recommend whether to continue, pivot, repair, or return to Explorer;
- expose report risks and required validators.

Lovasz algorithms must not:

- upgrade a claim status;
- call an open problem solved;
- replace verification, skeptic review, or Explorer arbitration;
- prevent the orchestrator from running a creative alternate plan;
- turn a ranking into a mandatory workflow.

The orchestrator owns strategy, fanout, budget, ordering, and reframing.
Lovasz owns mathematical structure, barriers, evidence, and rigor signals.

## Scores

All scores are normalized to `[0, 1]`.

### Proof-DAG Node Priority

```text
node_priority =
  0.30 * dependency_centrality
+ 0.20 * unlock_value
+ 0.15 * formalization_feasibility
+ 0.15 * evidence_availability
+ 0.10 * counterexample_pressure
+ 0.10 * theorem_connectivity
- 0.25 * repeat_failure_risk
```

Use this to decide which open DAG node should receive workers first.

### Mutation Priority

```text
mutation_score =
  0.30 * gap_class_match
+ 0.20 * one_axis_clarity
+ 0.20 * expected_unlock
+ 0.15 * verifier_friendliness
+ 0.15 * novelty_against_failures
- 0.35 * used_axis_penalty
```

Use this after `gap_feedback.json` exists. A mutation changes one axis only.
Repeated axes are penalized unless the ledger explains new information.

### Worker Result Priority

```text
result_score =
  0.30 * evidence_strength
+ 0.25 * target_fidelity
+ 0.15 * dependency_path_quality
+ 0.12 * composability
+ 0.08 * novelty
+ 0.10 * formalization_readiness
- 0.30 * gap_penalty
```

Use this to decide what Explorer should review first and what can be reported
honestly as verified, checked, partial, candidate-only, or failure learning.

### Next Action

Priority order:

```text
failed gate -> repair_gate
strong reportable result -> send_to_explorer_review
high-value open DAG node -> spawn_or_assign_workers
available non-repeat mutation -> apply_one_axis_mutation
only weak evidence remains -> stop_with_honest_partial_report
missing ledgers -> request_explorer_packet or reseed_attack_surface
```

## Scripts

- `../scripts/rank_lovasz_dag.py`: ranks open proof-DAG nodes.
- `../scripts/select_lovasz_mutation.py`: ranks one-axis gap mutations.
- `../scripts/rank_lovasz_results.py`: ranks worker results for reportability.
- `../scripts/lovasz_next_action.py`: recommends the next Lovasz action.
- `../scripts/lovasz_orchestrator_packet.py`: emits the combined orchestrator
  packet.

The same tools are reachable through `witsoc.py`:

```bash
python3 ../scripts/witsoc.py lovasz-rank-dag runs/<task>
python3 ../scripts/witsoc.py lovasz-select-mutation runs/<task>
python3 ../scripts/witsoc.py lovasz-rank-results runs/<task>
python3 ../scripts/witsoc.py lovasz-next-action runs/<task>
python3 ../scripts/witsoc.py lovasz-packet runs/<task>
```

Every packet includes `advisory: true`.

