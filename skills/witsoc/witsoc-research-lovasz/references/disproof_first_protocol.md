# Disproof-First Protocol

Use this for every open, unsolved, conjectural, or prove/disprove task before committing to a proof campaign. A disproof, if valid, is usually cheaper and more decisive than a proof.

## Disproof Passes

Run these in order:

1. **Definition stress:** empty, zero, one, equality, singleton, disconnected, singular, low dimension, low prime, boundary exponent.
2. **Quantifier stress:** swap quantifiers, test nonuniform choices, check whether "for all" hides exceptional families.
3. **Variant stress:** test stronger, weaker, and neighboring variants separately.
4. **Known obstruction stress:** use barrier taxonomy and source trail to import known extremal examples.
5. **Random/model search:** generate random objects under the hypotheses.
6. **Structured search:** grids, complete multipartite objects, prime powers, finite fields, lattices, cyclic groups, sparse/dense extremes.
7. **Solver search:** SAT/SMT/ILP/exhaustive search when the statement is finite.

## Disproof Record

```markdown
### Disproof Pass D<N>
- Target statement:
- Search domain:
- Method:
- Bounds:
- Candidate witness:
- Verification status:
- Outcome: no_witness | witness_found | variant_false | inconclusive
- Next search:
```

## Rules

- A missing counterexample is not evidence of proof unless the search is exhaustive in a stated finite domain.
- If a witness is found, switch immediately to `counterexample_certificate.md`.
- If a stronger variant is false, preserve the counterexample and demote the stronger variant.
- If the original target survives meaningful disproof pressure, record the search bounds in `verification.md` and continue to proof campaign only if the product ladder supports it.
