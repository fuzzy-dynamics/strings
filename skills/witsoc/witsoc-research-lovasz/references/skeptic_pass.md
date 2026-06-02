# Skeptic Pass

Use this before Lovasz accepts a proof, disproof, full-proof escalation, or Generator handoff for a high-stakes open-problem claim.

## Skeptic Checklist

```markdown
### Skeptic Pass S<N>
- Claim reviewed:
- Frozen target matches original:
- Variant drift check:
- Quantifier check:
- Hidden hypothesis check:
- Source/theorem mismatch check:
- Circular dependency check:
- Counterexample pressure check:
- Proof gap ledger check:
- Computation certificate check:
- Formalization feasibility check:
- Verdict: accept | demote | reject | needs_explorer | needs_generator
- Required fixes:
```

## Attack Questions

- Did the proof prove a weaker theorem?
- Did it assume the desired conclusion in a lemma?
- Are all external theorem preconditions established?
- Does a known extremal example violate a step?
- Are computations exhaustive only in a finite stated range?
- Does the counterexample satisfy every hypothesis?
- Does the WIT/Lean target match the Lovasz frozen target?

## Verdict Rules

- `accept`: route to Explorer/Generator or final report with exact status.
- `demote`: apply `claim_demotion.md`.
- `reject`: record as `REJECTED` with blocker.
- `needs_explorer`: send exact gap or proof object to Explorer.
- `needs_generator`: send narrow checked claim to Generator.

No full proof or disproof of an open problem may be reported without a skeptic pass record.
