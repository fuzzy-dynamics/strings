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

## Temporary Project Cleanup

Generator workers may create temporary Lean projects only when needed for verification. Every WIT/Lean proof target must run in a session-scoped proof worktree.

- Create one proof worktree per proof target or worker node, named from the session id and proof/node id, for example `witsoc-proof-${OSCI_SESSION_ID}-${node_id}`.
- If the Plane orchestrator spawns a worker, pass the proof worktree with `launch-worker --worktree <path>`.
- If the worker's current worktree is already dedicated to this single proof target, record that explicitly; otherwise create a separate proof worktree before writing WIT or Lean.
- Do not reuse a proof worktree for a different WIT/Lean proof target.
- If a worker creates a private Lean project or proof worktree, delete it after the worker finishes, whether verification succeeds or fails, unless the coordinator explicitly marks it preserved for inspection.
- Before deletion, preserve required artifacts outside the project/worktree: `.wit` files, Lean source snippets, logs, receipts, SafeVerify records, and final reports.
- If multiple workers share one Lean project, do not delete it until the last worker is done.
- Lovasz or the coordinator must track shared-project ownership and active users.
- After the final worker using a shared project completes, preserve required artifacts and delete the shared project.
- Cleanup status, `session_id`, `proof_worktree`, and whether the worktree was dedicated must be included in the worker result.

## Loop

```text
freeze target -> edit proof body -> query LSP/REPL/file checker -> diagnose exact goal/error -> repair -> repeat -> final lake build -> SafeVerify
```

Rules:

- The default edit region is the proof body.
- Changing theorem signatures, definitions, domains, or hypotheses requires explicit target-freeze update approved by the user.
- Feed exact local goal state and diagnostic into the next repair.
- Final Lean success requires checker success plus SafeVerify target-preservation checks.
