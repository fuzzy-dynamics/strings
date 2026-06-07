# Historical Benchmark Suite

Use this protocol to test whether Lovasz is making real research progress rather
than producing attractive partial artifacts. The benchmark uses solved or
well-understood historical problems while hiding the final proof route from the
active run.

## Benchmark Classes

Include problems in four classes:

- solved frontier theorem: historically hard but now standard;
- false conjecture: plausible statement with a known counterexample;
- partial-progress trap: natural special cases exist but do not solve the full
  target;
- theorem-precondition trap: a nearby theorem almost applies but misses a
  hypothesis.

## Run Setup

For each benchmark, provide only:

- frozen target statement,
- definitions and allowed background level,
- source status label hidden from the worker,
- budget,
- forbidden lookup notes for the final known proof if needed.

Do not reveal the key lemma, counterexample, or named solution theorem in the
prompt unless the benchmark is specifically testing theorem retrieval.

## Required Metrics

Score every run on:

- target fidelity: did Lovasz preserve the original statement?
- key-lemma discovery: did it name the historical barrier lemma or a close
  equivalent?
- counterexample pressure: did it test the false or overstrong variants?
- theorem-precondition accuracy: did it reject almost-applicable theorems with
  missing hypotheses?
- partial-result discipline: did every partial result include a remaining gap,
  novelty comparison, closure attempts, and next exact lemma?
- closure pressure: did Lovasz try to close the exact remaining gap before
  stopping at partial progress?
- final status honesty: did it avoid upgrading sketches, computations, or known
  restatements to solved claims?

## Seed Problems

Use small, inspectable seeds first:

- five-color theorem vs four-color theorem distinction;
- Mantel theorem with a Turan-theorem temptation;
- Ramsey `R(3,3)=6` with finite exhaustive proof pressure;
- Eulerian graph characterization with connectedness precondition;
- Hall marriage theorem special cases before the full theorem;
- Cauchy theorem for finite groups with cyclic-group-only trap;
- compactness/disjoint-union finite reduction for chi-bounding statements;
- false strengthened graph or number-theory variants with explicit finite
  counterexamples.

## Acceptance Rule

A Lovasz prompt, template, or validator change improves the system only if it
raises at least one metric without reducing target fidelity or final status
honesty. Treat a run that finds an elegant partial result but misses the known
barrier lemma as partial success, not a solved benchmark.
