# Erdős-Level Frontier Playbook

Use this when a problem has the flavor of an Erdős problem: short statement, asymptotic conclusion, sparse hypotheses, deep hidden structure, and likely need for partial progress before a full solution.

This playbook is deliberately general. It is for problems at the level of #1053, not for that problem alone.

## Recognition

Treat a problem as Erdős-level when it has several of:

- asymptotic target such as `o(·)`, `O(·)`, density, extremal threshold, or growth rate;
- simple object definition but difficult global behavior;
- known generic bounds that are too weak;
- likely dependence on prime factors, extremal examples, random constructions, containers, sieve, Fourier, spectral, or density-increment ideas;
- many plausible variants with different truth values;
- strong chance that the first useful output is a partial result, not the full theorem.

## Core Move: Identify The Tension

Before choosing an approach, write the central tension:

```markdown
### Central Tension
- Quantity to bound or force:
- Generic maximal/minimal behavior:
- Extra structure in the problem:
- Why generic bounds fail:
- What special structure might beat the generic barrier:
```

Example pattern:

```text
Generic objects can reach scale X, but objects satisfying the special equation/avoidance/density condition may be forced below X.
```

Most Erdős-level problems are solved, or partially advanced, by exploiting the special structure rather than improving the generic bound.

## Theorem Retrieval Spine

Build a ranked retrieval list before proof search:

```markdown
| Family | Candidate theorem | Needed form | Missing preconditions | Barrier if unavailable |
|---|---|---|---|---|
```

Common families:

- maximal order and normal order estimates,
- sieve and parity-barrier results,
- primitive divisor and lifting the exponent tools,
- density increment and regularity/container tools,
- probabilistic method and random construction lower bounds,
- extremal graph/set bounds,
- Fourier or spectral inequalities,
- inverse theorems,
- compactness and local-to-global principles,
- known classifications or finite obstruction theorems.

Promote a theorem only after exact statement and preconditions are audited.

## Product Ladder

Do not attack the full problem first unless the route is already unusually clear. Build a ladder:

```markdown
### Product Ladder
1. Computation or small cases:
2. Counterexample pressure for stronger variants:
3. Special family:
4. Bounded-parameter case:
5. Conditional theorem:
6. Structural lemma:
7. Reduction/equivalence:
8. Full theorem attempt:
```

Rules:

- Each rung must have a verification route.
- Each failed rung must teach a barrier or demote a false strengthening.
- Full theorem attempt is allowed only after lower rungs identify the right mechanism.

## Barrier Classes For This Level

Always check:

- **generic bound barrier:** known bound is sharp for all objects but maybe not for structured objects;
- **extremal construction barrier:** known examples nearly violate the desired conclusion;
- **local obstruction barrier:** congruence, parity, prime, graph-local, or boundary obstruction;
- **dependency-chain barrier:** satisfying the condition forces recursive dependencies;
- **constant-loss barrier:** existing tools prove the right shape but lose a fatal constant or logarithm;
- **rare-object barrier:** examples are so sparse that computation misleads;
- **variant drift barrier:** a neighboring variant is solved/false but the exact problem is not.

## Attack Portfolio

For Erdős-level problems, produce at least five attack families unless the source trail already settles the problem:

1. extremal or counterexample construction,
2. structural lemma route,
3. probabilistic or random-model route,
4. analytic/asymptotic estimate route,
5. computational search or finite-model route,
6. reduction to a known theorem or known barrier when available.

Rank by information value. A path that proves a useful obstruction can outrank a speculative full proof.

## Full-Solution Readiness

Before Lovasz allows full-solution mode, require:

- exact variant alignment,
- central tension resolved by a named mechanism,
- product ladder has at least one nontrivial verified or checked rung,
- no active counterexample pressure,
- theorem retrieval spine has audited external facts,
- Explorer can express the proof as a dependency DAG,
- Generator can artifact at least the key lemma or bounded subresult.

If these fail, continue with partial products rather than pretending the full problem is ready.
