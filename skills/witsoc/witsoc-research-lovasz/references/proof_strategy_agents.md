# Proof Strategy Agents

Use this to simulate specialized mathematical agents under Witsoc. These are strategy modes, not separate top-level skills.

## Strategy Modes

### Minimal Counterexample Agent

- Assume smallest counterexample.
- Derive forced local structure.
- Search reducible configurations.
- Best for graph, combinatorics, algebraic classification, induction.

### Induction-Strengthening Agent

- Identify failed induction step.
- Strengthen invariant or conclusion.
- Change induction parameter.
- Best for sequences, graphs, recursive structures.

### Probabilistic Method Agent

- Identify random model.
- Compute expectation/variance/local lemma dependencies.
- Search threshold.
- Best for Ramsey, extremal, sparse constructions.

### Algebraic/Spectral Agent

- Encode objects as polynomials, matrices, ranks, eigenvalues, characters, or modules.
- Best for incidence, graph bounds, additive combinatorics, finite fields.

### Reduction Agent

- Map target to known theorem, equivalent variant, or barrier.
- Audit reversibility and loss.
- Best when theorem density is high.

### Computational Certificate Agent

- Build bounded exhaustive search or certificate.
- Minimize witnesses.
- Best for finite cases and counterexamples.

## Agent Record

```markdown
### Strategy Agent A<N>
- Mode:
- Target:
- Distinct from previous routes:
- First action:
- Expected evidence:
- Failure class to watch:
- Output:
```

Use at least three distinct modes before declaring a full proof campaign stuck.
