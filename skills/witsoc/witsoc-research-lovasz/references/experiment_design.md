# Experiment Design Protocol

Use this before running computations or model searches. Experiments should produce reproducible evidence, counterexamples, witnesses, or conjecture pressure.

## Experiment Types

- exhaustive small-case enumeration,
- random or heuristic search,
- extremal construction search,
- SAT/SMT/ILP encoding,
- symbolic algebra or recurrence expansion,
- graph generation and invariant measurement,
- finite-field or modular testing,
- witness minimization,
- proof-sketch stress testing.

## Experiment Plan

```markdown
### E<N>: <experiment>
- Question:
- Product supported:
- Input domain:
- Search bounds:
- Method:
- Determinism: deterministic | randomized
- Seed if randomized:
- Expected witness format:
- Success criterion:
- Failure criterion:
- Output path:
- Repro command:
```

## Design Rules

- Start with the smallest domain that can falsify the claim.
- Include degenerate cases: empty, zero, one, equality, disconnected, singular, boundary dimension, low prime.
- Search for counterexamples before searching for confirming examples.
- When a witness is found, minimize it.
- When no witness is found, record the exact search bounds; do not imply the unrestricted claim is true.
- Prefer structured encodings over ad hoc string manipulation.
- Keep scripts in `runs/<task>/experiments/` and record commands in `research.md`.

## SAT/SMT/ILP Encodings

Use encodings when the problem is finite and constraints are crisp:

```markdown
- Variables:
- Constraints:
- Symmetry breaking:
- Objective if any:
- Solver:
- Completeness bound:
- Certificate or model path:
```

## Witness Handling

Every counterexample or extremal object should have:

- machine-readable form,
- human-readable summary,
- independent verification check,
- minimality or non-minimality status,
- relation to the original problem and variant.
