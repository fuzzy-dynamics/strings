# Witsoc Research Lovasz Changes

This file summarizes the Lovasz-specific changes made during the Witsoc routing and discovery-engine upgrade.

## Role And Routing

- Lovasz is now defined as a formal-verification-driven research director for open, unsolved, unconfirmed, frontier-level, and blocked mathematical targets.
- Lovasz is no longer an initial router. Explorer must first freeze the problem and produce a barrier packet.
- Lovasz returns to Explorer for arbitration. It does not directly decide that Generator may solve an open problem unless explicitly allowed by the coordinator.
- Open-problem success is status-honest: the original problem is solved only if final WIT + Lean + SafeVerify verifies the original frozen target.

## Barrier Packet Requirements

Lovasz now requires Explorer to provide:

- frozen target statement,
- variant/status ledger,
- source trail and best-known results,
- known obstructions and failed methods,
- theorem-precondition gaps,
- counterexample families and boundary cases,
- formalization blockers,
- smallest tractable products,
- success criteria.

## Actual Barrier Lemma Discipline

- Lovasz must name the actual barrier lemma, reduction, obstruction certificate, or counterexample certificate before choosing weaker products.
- "No lemma found" is not a valid final Lovasz result. It must become a structured `FAILED_ATTEMPT` with attempted lemma schemas, falsification results, theorem-precondition gaps, and a next exact lemma or obstruction to test.
- Weakening the final conclusion is a last resort. Weaker products require a written explanation of how they feed back into the actual barrier lemma.
- Lovasz proof-DAG nodes can now include `actual_barrier_lemma`.

## Proof Dependency DAG

Lovasz must build a proof-dependency DAG whose nodes are one of:

- actual barrier lemma,
- lemma,
- reduction,
- special case,
- obstruction,
- counterexample search,
- computational certificate,
- conditional theorem,
- failed method to rule out.

The DAG must track dependencies, target fidelity, relation to the frozen target, and why any weaker or conditional node is still relevant.

## Worker Spawning

Lovasz now has a strict worker spawning protocol using `<spawn_worker>` JSON blocks.

Supported worker types:

- `SKEPTIC`
- `FORMALIZER`
- `COMPUTATION`
- `COUNTEREXAMPLE`
- `MINER`

All worker targets must trace back to an actual barrier lemma, formalization blocker, counterexample pressure point, or final synthesis audit obligation.

## MINER Worker

- Added `MINER` worker type.
- A MINER invokes `../scripts/empirical_miner.py` when available.
- It mines stable empirical invariants from generated finite structures.
- It pushes high-probability conjectures into `actual_lemma_queue`.
- MINER output is only `CONJECTURE` or bounded `CHECKED` evidence. It never upgrades a claim to `VERIFIED`.

## WIT, Lean, And Proof Worktrees

- Every proof worker must generate WIT before Lean.
- Lean must be generated from the WIT target.
- Every WIT/Lean proof target must run inside a dedicated session-scoped proof worktree.
- Worker results must record proof worktree path, session id, cleanup status, target hashes, and verification status.
- Verified artifacts require matching WIT target hash, Lean target hash, and frozen target hash.

## Skeptic Review

- Promising nontrivial nodes require independent skeptic review.
- A node cannot become `PROVED_SKETCH`, `CHECKED`, or `VERIFIED` without a passing `skeptic_review_id`.
- Skeptic review checks target drift, hidden assumptions, circularity, theorem-precondition gaps, WIT/Lean mismatch, and weaker-target substitution.

## Retry And Failure Memory

- Lovasz now maintains retry/failure memory.
- Repeating a failed method against the same target requires a recorded change in method, theorem, encoding, invariant, counterexample information, or formalization route.
- Failed routes are recorded so future Lovasz runs do not repeat them blindly.

## Actual Lemma Queue

- Lovasz now maintains `actual_lemma_queue`.
- Queue entries contain exact lemma statements, what they unlock, priority, status, and next exact attempt.
- Workers should pull from this queue before inventing side tasks or weaker variants.

## Final Synthesis Audit

Before final Generator, Lovasz must run a final synthesis audit confirming:

- DAG edges compose,
- no conjecture is used as a theorem,
- no hidden assumptions exist,
- no weaker theorem is substituted for the frozen target,
- external theorem preconditions are discharged,
- target hashes match,
- WIT and Lean target hashes match.

## Discovery Machinery

Lovasz now requires deterministic discovery machinery before relying on prose-only invention:

- empirical invariant mining,
- exact bounded finite-graph search for graph-theory barriers,
- SMT-driven reduction synthesis,
- counterexample search and inflation,
- formalizer and skeptic workers.

SMT synthesis rules:

- finite reduction gadgets must not be designed by prose alone,
- Lovasz/Explorer should encode gadget boundaries as SMT-LIB,
- `sat` is only a candidate gadget,
- `unsat` plus unsat core is obstruction evidence.

Campaign templates:

- Added reusable Lovasz campaign seeds through `witsoc/scripts/lovasz_campaign_template.py`.
- Current templates include `induced-tree-triangle-free`, `divisor-sum-asymptotic`, `ramsey-extremal`, `additive-combinatorics`, and `diophantine`.
- Lovasz must specialize templates to the frozen target and treat them as proof-DAG seeds, not proof evidence.

Finite graph barrier machinery:

- Added `witsoc/scripts/finite_graph_backend.py` for exact bounded triangle-free, chromatic-number, and induced-tree-containment checks on small graphs.
- The extremal graph playbook now requires this backend before claiming a finite answer for small induced-tree targets.
- The empirical miner now supports deterministic cycle and Mycielski graph families for high-chromatic triangle-free counterexample pressure.

Reduction templates:

- Added WIT templates for compactness/disjoint-union and finite chi-bounding reductions.
- These templates keep a valid WIT header status such as `UNVERIFIED` plus a separate `-- Template: true` marker; they only formalize the reduction skeleton and do not settle a frontier theorem without a verified finite chi-bound or obstruction family.

## Adversarial Ontology Pivot

- If an actual barrier lemma fails twice using native-domain methods, Lovasz may not simply repeat native-domain attacks.
- Lovasz must pivot to an orthogonal Mathlib domain through a functorial or structure-preserving mapping.
- The pivot must define source objects, target objects, preservation laws, reflected obstructions, and newly available theorem families.
- Pivoted subgoals must still trace back to the frozen target and actual barrier lemma.

## Symmetry-Maximizing Definition Generator

- Added Invention Mode for cases where empirical mining finds a stable pattern but no existing functional expression fits.
- Lovasz must output a localized grammar-search constraint rather than inventing broad prose concepts.
- The grammar-search record includes allowed primitives, constructors, type/domain restrictions, symmetry objective, depth bound, positive/negative examples, and relation to the actual barrier lemma.
- Invented concepts start as `CONJECTURE` until falsified, formalized, and checked.

## Status Discipline

Lovasz uses only honest claim statuses:

- `REJECTED`
- `FAILED_ATTEMPT`
- `CONJECTURE`
- `PARTIAL`
- `CONDITIONAL`
- `PROVED_SKETCH`
- `CHECKED`
- `VERIFIED`

`VERIFIED` requires formal/verifier evidence. A proof sketch, computation, or mined invariant cannot be promoted to verified without WIT/Lean/SafeVerify evidence.

## Partial Closure Audit

- Open-problem `PARTIAL` and `CONDITIONAL` products now require a machine-readable closure audit.
- Each partial/conditional DAG node, worker result, or generator artifact must record the exact remaining gap, why the result is not a full solution, known-result comparison, novelty status, next exact experiment or lemma, and at least two distinct closure attempts.
- Accepted partial/conditional DAG nodes, worker results, and generator artifacts require a skeptic review with `claim_classification`.
- Skeptic classifications of `target_drift`, `known_result_restatement`, `hidden_assumption`, or `needs_repair` block acceptance as usable partial progress.

## Historical Benchmarks

- Added `references/historical_benchmark_suite.md` for solved-but-hidden frontier-style tests.
- Benchmark scoring now emphasizes key-lemma discovery, theorem-precondition accuracy, closure pressure, partial-result discipline, and final status honesty.
