# Lean Verification Loop

Use this when Lean formalization is requested or when repairing Lean failures.

## Preferred Feedback Order

1. Use Lean LSP, REPL, `repl`, `minictx`, or another per-command checker when available.
2. Use `lake env lean <file>` or file-level checking for candidate files.
3. Use full `lake build` only for final confirmation, dependency-sensitive changes, or when the user explicitly requests it.

Do not run full `lake build` in a tight repair loop when per-tactic or per-file feedback is available.

## Cache Discipline

- Run dependency cache setup once per project when needed, for example `lake exe cache get`, before proof repair loops.
- Avoid changing imports unless the diagnostic requires it.
- If imports change, expect cache invalidation and record why the change is necessary.
- Do not trigger massive rebuilds accidentally while testing minor tactic changes.

## Loop

```text
freeze target -> edit proof body -> query LSP/REPL/file checker -> diagnose exact goal/error -> repair -> repeat -> final lake build -> SafeVerify
```

Rules:

- The default edit region is the proof body.
- Changing theorem signatures, definitions, domains, or hypotheses requires explicit target-freeze update approved by the user.
- Feed exact local goal state and diagnostic into the next repair.
- Final Lean success requires checker success plus SafeVerify target-preservation checks.
