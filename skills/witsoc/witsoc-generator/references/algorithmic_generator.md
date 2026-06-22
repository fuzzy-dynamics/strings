# Algorithmic Generator Decision Support

Generator algorithms are advisory. They rank WIT/Lean artifacts, repair
candidates, and return-to-Explorer risk. They never upgrade mathematical status:
receipts, Lean/SafeVerify, and Explorer acceptance still decide trust.

## Scores

```text
repair_candidate_score =
  0.25 * diagnostic_match
+ 0.20 * local_edit_distance_smallness
+ 0.20 * preserves_frozen_target
+ 0.15 * expected_verifier_gain
+ 0.10 * premise_availability
+ 0.10 * prior_success_pattern
- 0.25 * target_drift_risk
- 0.20 * circularity_risk
```

```text
artifact_quality_score =
  0.25 * target_hash_match
+ 0.20 * verifier_receipt_strength
+ 0.15 * dependency_completeness
+ 0.15 * proof_structure_quality
+ 0.10 * minimality
+ 0.10 * reproducibility
+ 0.05 * report_clarity
- 0.30 * unresolved_gap_penalty
```

## Packet

Use:

```bash
witsoc generator packet runs/<task>
```

or the direct compatibility alias:

```bash
witsoc generator-packet runs/<task>
```

The packet schema is `witsoc.generator.decision_packet.v1` and includes ranked
artifacts, ranked repairs, the best artifact, the best repair, a recommended
next action, and whether Generator should return to Explorer. Every
recommendation is advisory.

