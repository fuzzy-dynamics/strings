# Theorem Retrieval Engine

Use this before committing to a proof route. It turns a target into theorem families, exact candidate statements, precondition audits, and formal-availability checks.

## Retrieval Pipeline

```markdown
### Retrieval R<N>
- Target subgoal:
- Domain playbook:
- Search terms:
- Theorem family:
- Candidate theorem:
- Exact statement needed:
- Missing preconditions:
- Can weaken target instead:
- Formal availability: yes | no | partial | unknown
- Source:
- Source type:
- Date checked:
- Use decision: use | reject | local replacement | search more
```

## Rules

- Never cite a theorem by vibe. Record exact statement and preconditions.
- Prefer the weakest theorem that solves the local subgoal.
- Record rejected candidates to avoid repeated bad retrieval.
- If a theorem is unavailable formally, write a local replacement plan.
- If a theorem is as hard as the original problem, promote it to `proof_gaps.md`.

## Formal Availability

For Lean/Mathlib tasks, pair this with `lean_mathlib_integration.md`.

Record:

- import path if known,
- theorem names if known,
- whether hypotheses match,
- local adapters needed,
- failed search queries.
