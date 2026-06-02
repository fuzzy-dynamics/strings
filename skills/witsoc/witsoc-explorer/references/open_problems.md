# Open Problem Research Reference

Use this reference for known open problems, Erdős-style problems, conjectures, problem-list items, and hard research questions where a complete solution may not be realistic in one run.

## Core Rule

Do not optimize for a dramatic proof claim. Optimize for durable, checkable progress:

- exact status and variant control,
- a sourced map of what is known,
- a precise obstruction or failed approach,
- a special case, bound, conditional theorem, reduction, or computation,
- a formalizable lemma or subgoal,
- a `.wit` artifact only when the target is narrow enough to state honestly.

Default status is `OPEN` until the exact problem and exact variant have an externally checkable solution path.

## Source Triage

For current open/solved status, prefer sources in this order:

1. Original problem list, maintained problem page, or author-maintained notes.
2. Recent survey or monograph section with bibliographic trail.
3. Peer-reviewed paper or arXiv preprint proving a relevant result.
4. Formal library theorem if the question is formalization-oriented.
5. OEIS, MathWorld, Wikipedia, blog posts, or forum threads only as pointers to primary sources.

Record source reliability:

```text
Source:
What it establishes:
Variant covered:
Date/version:
Reliability: primary | survey | preprint | pointer | informal
Open caveat:
```

If source access is unavailable, state `status unconfirmed` and work from the user's statement as a conjectural target.

## Problem-State Ledger

Maintain a concise ledger for long or open-problem runs:

```text
Problem:
Canonical statement:
Variant in this run:
Status: OPEN | SOLVED | PARTIAL | CONDITIONAL | AMBIGUOUS | UNCONFIRMED
Source trail:
Known results:
Known counterexamples/obstructions:
Equivalent formulations:
Nearby stronger variants:
Nearby weaker variants:
Current target progress:
Approach log:
Failed approaches:
Computations:
Formalizable subgoals:
Next experiments:
```

Keep the original problem separate from narrower artifacts. A special case is not a solution to the original problem.

## Erdős-Style Problem Pattern

Many Erdős problems are intentionally broad, extremal, or parameterized. Before proving anything, normalize:

- object class: integers, graphs, sets, sequences, hypergraphs, metric spaces, probability spaces,
- parameters and asymptotic regime,
- forbidden structures or density assumptions,
- whether constants are absolute, effective, or asymptotic,
- exact quantifier order,
- known extremal examples and random constructions,
- whether the problem asks existence, threshold, bound, classification, or algorithm.

Useful progress types:

- prove the first nontrivial parameter case,
- improve a constant or exponent with all dependencies stated,
- recover a known bound by a simpler formalizable proof,
- find a counterexample to an overstrong variant,
- isolate the missing lemma in a famous approach,
- reduce the problem to a named conjecture or cleaner subproblem,
- build verified finite data for small parameters,
- document why a natural method cannot reach the conjectured bound.

## Approach Portfolio

For open problems, start with at least three distinct approach families when budget allows:

```text
Approach:
Target progress:
Method family:
Known precedent:
Required external facts:
Toy case:
Obstruction to test:
Artifact candidate:
Stop condition:
```

Common families:

- extremal/minimal-counterexample,
- probabilistic method or alteration,
- algebraic/combinatorial construction,
- spectral/linear algebra,
- entropy/compression,
- additive-combinatorial energy method,
- generating functions or analytic number theory,
- Ramsey/container method,
- graph limits/compactness,
- computational search or SAT/SMT encoding,
- reduction to a known conjecture,
- formalization of a small special case.

Do not count two variations of the same proof sketch as distinct unless the key method, external theorem, decomposition, or search space changes.

## Computation Discipline

Computational evidence can justify `CONJECTURE`, `PARTIAL`, or a finite-domain theorem. It does not prove an infinite statement unless the reduction to a finite exhaustive domain is explicit.

For computations, record:

```text
Claim tested:
Domain exhausted:
Code/tool:
Seed, parameters, and limits:
Independent check:
Result:
How it bears on the open problem:
```

Prefer producing a reproducible script or a WIT computation certificate for small finite claims.

## Artifact Handoff

Escalate to `witsoc-generator` only when the artifact target is narrow:

```text
Original open problem:
Artifact target:
Result type: special case | bound | conditional theorem | reduction | obstruction | counterexample | computation | failed attempt | conjecture
Statement:
Assumptions:
Evidence/proof sketch:
Known gaps:
Relationship to original problem:
Status:
```

Good artifact examples:

- `PARTIAL`: a theorem for all graphs with maximum degree at most 3.
- `CONDITIONAL`: the target follows from a named conjecture plus verified preconditions.
- `FAILED_ATTEMPT`: a proof route fails because a claimed inequality is false; include the counterexample.
- `CONJECTURE`: a sharpened subclaim supported by finite data and known examples.

Bad artifact examples:

- a `.wit` theorem claiming a famous open problem is solved from a fresh one-page sketch,
- a universal theorem from unbounded computation,
- a weakened theorem that silently replaces the user's target,
- a citation to "standard result" without exact statement and preconditions.

## Final Report Shape

For an open-problem run, report:

```text
Status:
Exact variant:
Sources checked:
Known facts:
Progress made:
Failed approaches:
Artifacts generated:
Open gaps:
Best next step:
```

Use `OPEN`, `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, `FAILED_ATTEMPT`, or `GAP` honestly. A credible open-problem answer often ends with a precise next lemma, counterexample search, or literature target rather than a proof.
