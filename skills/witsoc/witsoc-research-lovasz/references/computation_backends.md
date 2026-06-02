# Computation Backends

Use this to choose the right computation backend and artifact format.

## Backend Selection

```markdown
### Computation Backend
- Problem type:
- Backend: exhaustive_python | random_search | SAT | SMT | ILP | graph_search | number_theory_search | finite_model | CAS
- Completeness: complete | bounded | heuristic
- Certificate type:
- Replay command:
- Output path:
```

## Available Local Scripts

- `scripts/experiments/graph_search.py`: enumerate small graphs and simple graph invariants.
- `scripts/experiments/number_theory_search.py`: exact arithmetic for divisor sums, multiplicative ratios, valuations, and bounded searches.
- `scripts/experiments/finite_model_search.py`: generic finite tuple/model search from a Python predicate module.

## Certificate Rules

- Every computation must write machine-readable output.
- Bounded searches must state bounds.
- Random searches must state seed.
- Counterexamples must be minimized when feasible.
- Repro commands go in `research.md`.
- Certificates go in `runs/<task>/experiments/`.
