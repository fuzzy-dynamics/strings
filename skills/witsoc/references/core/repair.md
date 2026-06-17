# Repair Protocol

Before editing after a WIT verifier rejection, structural failure, Lean/LSP/REPL/compiler failure, or SafeVerify rejection, diagnose the failure.

Repair diagnosis:

```json
{
  "rejected_label": "label or goal",
  "claim": "rejected claim",
  "cited_premises": [],
  "evidence": "checker/verifier/compiler output",
  "failure_class": "wrong_tactic | missing_premise | target_drift | ...",
  "likely_cause": "minimal explanation",
  "repair": "minimal repair",
  "risk": "what could still fail",
  "new_labels_introduced": []
}
```

Failure classes:

- `wrong_tactic`
- `wrong_theorem`
- `missing_premise`
- `missing_hypothesis`
- `unknown_identifier`
- `theorem_precondition_not_proved`
- `algebra_logic_error`
- `type_mismatch`
- `coercion_issue`
- `unsolved_goal`
- `quantifier_or_domain_mismatch`
- `out_of_scope_reference`
- `target_drift`
- `forbidden_escape`
- `import_missing`
- `vacuous_proof`
- `case_not_closed`
- `step_too_compressed`
- `false_statement`

Allowed repairs:

- split a compressed step into local substeps,
- add a helper lemma with all preconditions,
- cite a precise external theorem and prove its preconditions,
- replace an unavailable theorem with a local weaker lemma,
- weaken a false intermediate claim without weakening the final theorem,
- add a hypothesis only when the original task allows it,
- mark `GAP`,
- hand back to Explorer for premise search, theorem replacement, or counterexample hunting.

Do not submit cosmetic rewrites. Every repair must reduce a real obligation while preserving the frozen target.
