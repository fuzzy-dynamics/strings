# Lean And Mathlib Integration

Use this before Generator attempts Lean for open-problem products or theorem candidates.

## Feasibility Record

```markdown
### Lean Feasibility
- Formal target:
- Definitions needed:
- Mathlib theorem candidates:
- Imports:
- Missing libraries:
- External facts requiring local proof:
- Expected lemma count:
- Risk: LOW | MEDIUM | HIGH
- Decision: lean_now | wit_only | postpone | local_kernel
```

## Rules

- Do not promise Lean success until `lake build` or equivalent check passes.
- Prefer a tiny formal kernel over the whole open problem.
- If Mathlib lacks a major theorem, record a local replacement or demote the artifact target.
- Use target-freeze checks before and after formalization.
- A Lean theorem must match the Lovasz frozen target, not a convenient weaker statement.

## Theorem Search Notes

Record:

- exact theorem names if found,
- failed search strings,
- import paths,
- precondition adapters,
- coercion/domain risks.
