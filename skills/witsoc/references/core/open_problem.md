# Open Problem Protocol

Use this for known open problems, Erdős-style problems, conjectures, prize problems, problem-list items, and hard research tasks where closure is unlikely in one run.

Default status is `OPEN` until the exact problem and variant have an externally checkable solution path.

Prioritize:

- exact statement and variant control,
- source trail and known status,
- obstruction families and counterexamples to stronger variants,
- special cases, bounds, reductions, computations, and conditional theorems,
- formalizable subgoals,
- failed approaches as reusable evidence.

## Open-Solution Protocol

For Lovasz and other open-problem runs, optimize for reducing the actual open
part rather than generating polished partial solutions. A run must keep pressure
on the frozen target unless it records an explicit reason why a narrower result
is the honest endpoint.

Required loop:

1. Freeze a machine-checkable target early. Record exact definitions,
   quantifiers, variants, sources, known status, and target hashes before
   attacking the problem.
2. Run adversarial proof breaking. Every promising route must receive an
   independent skeptic pass for counterexamples, hidden assumptions, circularity,
   theorem-precondition gaps, target drift, and weaker-target substitution.
3. Use computational search as a first-class worker where applicable. Prefer
   finite model search, exhaustive small-case checks, SAT/SMT encodings,
   randomized experiments, witness minimization, and replayable certificates
   before committing to a prose proof route.
4. Maintain a proof-dependency DAG. Each node must state its exact claim,
   dependencies, role in the frozen target, verification status, artifact paths,
   and remaining gaps.
5. Separate research modes. Do not blend statement normalization, literature
   audit, counterexample search, proof construction, formalization, and skeptic
   review into one undifferentiated narrative.
6. Classify failures. Every blocked route should be assigned a reusable failure
   class, such as false claim, target drift, theorem-precondition gap, missing
   barrier lemma, artifact issue, computational obstruction, or genuine
   mathematical barrier.
7. Account for novelty. Distinguish sourced known results, recovered folklore,
   recombinations of known tools, new conjectures, new computations, and claims
   requiring formal verification.

Required ledgers for a deep open-problem run:

- `statement-ledger.md`: frozen statement, variants, sources, status, hashes.
- `proof-dag.md`: nodes, dependencies, worker assignments, verification state.
- `computational-search.md`: search space, code/commands, seeds, witnesses,
  certificates, negative evidence, and replay notes.
- `failure-taxonomy.md`: blocked routes, failure classes, diagnostics, next
  mutation or reason to stop.
- `novelty-ledger.md`: what is known, what was rediscovered, what appears new,
  and what evidence supports each classification.

Worker modes should produce narrow artifacts:

| Mode | Purpose | Required output |
|---|---|---|
| Statement normalizer | Freeze the exact target and variants | statement ledger and target hashes |
| Literature auditor | Separate known results from conjectural or informal claims | source/status ledger |
| Counterexample worker | Try to falsify the target or stronger variants | minimized witnesses or negative search certificate |
| Computational-search worker | Explore finite cases or encodings | replayable script/log/certificate |
| Proof builder | Attack one DAG node | proof sketch, WIT target, or verified artifact |
| Formalization scout | Check formal-library feasibility and theorem preconditions | dependency audit and formalization blockers |
| Skeptic worker | Kill or demote promising claims | skeptic verdict and failure class |
| Synthesis checker | Test whether nodes compose back to the frozen target | DAG assembly report |

The final report for a deep open-problem run must include:

- statement ledger summary,
- proof DAG summary,
- computational evidence summary,
- failure taxonomy,
- novelty accounting,
- remaining open part,
- verified narrow result or honest stop condition.

Open-problem handoffs to Generator must target a narrow artifact:

```text
special case | bound | conditional theorem | reduction | obstruction | counterexample | computation | failed attempt | conjecture
```

Do not ask Generator to write a proof of the whole open problem unless the proof path has already survived adversarial exploration and target-freezing checks.

For detailed source triage and Erdős-style workflow, Explorer should also read `witsoc-explorer/references/open_problems.md`.
