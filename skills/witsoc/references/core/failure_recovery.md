# Failure Recovery

Use this when `wit check`, verifier review, Lean checking, literature search, counterexample search, or proof construction blocks a serious target.

## Failure Record

Write the failure into `.soc`, `handoff.json`, or a failure note:

```json
{
  "approach_id": "approach_1",
  "frozen_target": "exact theorem or artifact target",
  "method": "method family",
  "failure_class": "missing_premise | target_drift | false_statement | ...",
  "diagnostic": "checker/verifier/compiler/literature evidence",
  "rejected_step": "label or subgoal if applicable",
  "repairs_tried": ["repair attempted"],
  "do_not_repeat": ["specific route"],
  "reusable_lesson": "what this rules out",
  "next_method_families": ["distinct method 1", "distinct method 2"]
}
```

## Recovery Ladder

1. Keep the original theorem target frozen unless the user explicitly changes it.
2. Do not retry the same method unchanged. A retry must change proof method, decomposition, formalization target, external theorem, or search space.
3. When worker spawning is available, run at least two independent alternate-method agents:
   - one proof-strategy or theorem-source alternative,
   - one formalization, counterexample, obstruction, or simplification alternative.
4. Tell alternate agents what failed and what not to repeat.
5. If all alternates fail, run a synthesis pass and decide whether to produce a narrower artifact, mark the target `GAP`, `PARTIAL`, `CONDITIONAL`, `FAILED_ATTEMPT`, or keep it `OPEN`.
6. Only report final failure after diversification, or when worker spawning is unavailable and at least two materially distinct local routes hit the same blocker.

## Stop Conditions

Stop the current branch and report honestly when:

- the same failure class repeats three times without reducing the obligation,
- every repair would change the frozen theorem target,
- all active sketches depend on the same unresolved bridge,
- a needed external theorem is unavailable or unformalized within budget,
- counterexample pressure shows the statement is probably false or missing a hypothesis,
- SafeVerify rejects all building candidates,
- the configured user or run budget is exhausted.

Failure output:

```text
Status: GAP | FAILED_ATTEMPT | PARTIAL | CONDITIONAL | OPEN
Target:
Best sketch:
Where it failed:
Failure class:
What was tried:
Why it did not close:
Reusable lesson:
Next useful mutation:
```
