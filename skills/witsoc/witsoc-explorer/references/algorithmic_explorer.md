# Algorithmic Explorer Decision Support

Explorer algorithms are advisory. They rank theorem candidates, proof sketches,
and handoff readiness so the orchestrator can decide whether to continue
exploration, invoke Lovasz, or authorize Generator. They never assign
mathematical truth and never override Explorer/Generator verification gates.

## Scores

```text
theorem_candidate_score =
  0.25 * statement_match
+ 0.20 * precondition_match
+ 0.15 * formal_availability
+ 0.15 * dependency_relevance
+ 0.10 * source_trust
+ 0.10 * proof_reuse_potential
- 0.20 * precondition_gap_risk
```

```text
sketch_ev_score =
  0.25 * target_fidelity
+ 0.20 * dependency_coverage
+ 0.15 * formalization_readiness
+ 0.15 * novelty
+ 0.10 * falsifiability
+ 0.10 * theorem_support
+ 0.05 * user_value
- 0.25 * hidden_assumption_risk
- 0.20 * target_drift_risk
```

```text
handoff_readiness =
  0.20 * target_frozen
+ 0.20 * dependencies_named
+ 0.18 * proof_plan_present
+ 0.16 * generator_target_present
+ 0.10 * counterexample_pressure_done
+ 0.10 * source_status_recorded
- 0.24 * risk_open_or_ambiguous
```

## Packet

Use:

```bash
witsoc explorer packet runs/<task>
```

or the direct compatibility alias:

```bash
witsoc explorer-packet runs/<task>
```

The packet schema is `witsoc.explorer.decision_packet.v1` and includes ranked
theorems, ranked sketches, handoff readiness, generator authorization advice,
and a recommended next action. Every recommendation is advisory.

