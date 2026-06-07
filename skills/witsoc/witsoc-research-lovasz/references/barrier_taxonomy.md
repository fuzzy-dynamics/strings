# Barrier Taxonomy

Use this to classify why an open or hard problem resists attack. A barrier is useful only if it suggests a test, obstruction, or bypass mutation.

## Universal Barriers

- **Extremal barrier:** known or suspected examples nearly violate the target.
- **Parity/modular barrier:** congruence, parity, sign, or residue class prevents a naive argument.
- **Threshold barrier:** truth changes around a density, size, rank, dimension, or smoothness threshold.
- **Compactness barrier:** finite cases do not pass to infinite objects, or infinitary arguments lose effectivity.
- **Regularity barrier:** available tools require smoothness, measurability, pseudorandomness, or bounded complexity.
- **Independence/randomness barrier:** dependencies break probabilistic or averaging arguments.
- **Precondition barrier:** a named theorem is close but one hypothesis is missing.
- **Formalization barrier:** a sketch hides definitions or side conditions that block WIT/Lean.
- **Reduction barrier:** a tempting transformation changes the problem or loses equivalence.

## Domain Barriers

### Graph Theory And Extremal Combinatorics

- sharp examples: complete multipartite graphs, random graphs, projective/norm graphs, blow-ups, cages;
- local-to-global failure: degree conditions do not force global structure;
- coloring barriers: critical graphs, list assignments, degeneracy gaps;
- matching/cut barriers: Hall/Menger/min-cut preconditions fail;
- spectral barriers: eigenvalue bounds are too coarse or not tight.

### Ramsey And Erdős-Style Problems

- small Ramsey witnesses do not scale;
- probabilistic lower bounds beat constructive intuition;
- container or regularity methods lose constants;
- inductive recurrences are too weak;
- diagonal and off-diagonal variants behave differently.

### Additive Combinatorics

- density increment loses too much density;
- Bohr set or Fourier uniformity hypotheses are missing;
- sumset estimates are non-sharp at the target scale;
- structured/random decomposition leaves uncontrolled error;
- local field or torsion variants diverge from integer variants.

### Number Theory

- local obstruction at primes or valuations;
- ineffective constants in analytic tools;
- equidistribution unavailable at required scale;
- Diophantine finiteness does not give construction;
- sieve parity barrier.

### Geometry And Topology

- compactness or boundary regularity gap;
- incidence bounds lose at degeneracies;
- homological obstruction absent in low dimension;
- metric embedding distortion;
- transversality or smoothness preconditions fail.

### Algebra And Logic

- classification theorem too heavy or unavailable formally;
- representation not faithful to original object;
- undecidability or independence risk;
- model-theoretic compactness changes finite content;
- rank/dimension invariant too weak.

## Barrier Record

For each barrier write:

```markdown
### B<N>: <barrier name>
- Domain:
- Threatens:
- Evidence:
- Known extremal examples:
- Actual barrier lemma or obstruction certificate needed:
- Direct attacks attempted on actual lemma:
- Weaker-product justification, if any:
- Test:
- Bypass mutation:
- If real, convert to product:
- Status: suspected | tested | bypassed | converted_to_obstruction | rejected
```

Record bypassed and rejected barriers in `.soc` memory so future Lovasz runs do not repeat them blindly.
