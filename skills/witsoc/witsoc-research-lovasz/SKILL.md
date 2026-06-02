---
name: witsoc-research-lovasz
description: >
  Lovasz-mode research-program orchestrator for Witsoc mathematical open
  problems, unsolved conjectures, Erdős-style questions, and frontier theorem
  discovery. Use when Codex must conduct original barrier-aware mathematical
  research: status triage, novelty/source checks, variant control, barrier
  discovery and barrier-breaking plans, conjecture mining, experiment design,
  partial results, reductions, counterexamples, conditional theorems, verified
  research claims, WIT/Lean artifact targets, and a research ledger or report.
---

# Witsoc Research Lovasz

Witsoc Research Lovasz is the high-pressure research-program subskill inside `witsoc`. It is designed for open and unsolved mathematical problems, including Erdős-style problems, where progress requires source discipline, original conjecture generation, barrier analysis, and verified narrow claims before proof artifact generation.

This skill is ambitious but not magical: it must never promise to solve every open problem. Its job is to behave like a formal-verification-driven mathematical research director working from Explorer's frozen target and barrier packet: identify the real barriers, decompose them into formalizable subproblems, coordinate workers, require WIT-before-Lean verification for accepted claims, synthesize verified results, and return the result to Witsoc Explorer for arbitration.

When Lovasz is activated, the user-facing progress message must include:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz.
```

If Lovasz later calls Explorer or Generator, update the visible chain, for example:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer -> witsoc-generator.
```

Use this skill under the top-level Witsoc coordinator in `../SKILL.md`. Load Witsoc's relevant core protocols as needed, especially:

- `../references/core/open_problem.md`
- `../references/core/exploration_strategy.md`
- `../references/core/handoff.md`
- `../references/core/safeverify.md`
- `../references/core/failure_recovery.md`
- `../references/core/research_machinery.md`

For detailed research-run structure and the Lovasz barrier engine, read `references/research_protocol.md`.

Load these focused references when the task needs them:

- `references/problem_selection.md`: choose and score the most tractable research product or subproblem.
- `references/domain_playbooks.md`: select domain-specific playbooks and standard theorem/example families.
- `references/literature_triage.md`: perform source, best-known-result, known-barrier, and failed-method triage.
- `references/theorem_retrieval_engine.md`: retrieve exact theorem candidates with precondition and formal-availability audits.
- `references/erdos_level_playbook.md`: handle Erdős-level frontier problems with asymptotic tension, theorem retrieval, product ladders, and repeated barrier attacks.
- `references/barrier_taxonomy.md`: domain-specific barrier classes and attack moves.
- `references/conjecture_mining.md`: generate, rank, test, and demote conjectures.
- `references/conjecture_to_lemma_pipeline.md`: turn patterns and conjectures into scoped lemma candidates.
- `references/experiment_design.md`: design computations, exhaustive searches, SAT/SMT encodings, and witness minimization.
- `references/computation_backends.md`: choose local computation/search backends and certificate formats.
- `references/counterexample_search_library.md`: choose standard counterexample families by domain.
- `references/lean_mathlib_integration.md`: audit Lean/Mathlib feasibility and theorem availability.
- `references/proof_strategy_agents.md`: run distinct proof-strategy modes under Witsoc.
- `references/disproof_first_protocol.md`: search for counterexamples and false variants before proof campaigns.
- `references/full_proof_campaign.md`: run independent proof-route campaigns after partial products indicate a plausible full solution.
- `references/counterexample_certificate.md`: certify, minimize, and verify disproof witnesses.
- `references/proof_gap_ledger.md`: track proof gaps until a proof DAG has no hidden bridges.
- `references/skeptic_pass.md`: independent adversarial review before proof/disproof acceptance.
- `references/soc_memory.md`: use `.soc` memory efficiently across Lovasz loops.
- `references/cross_run_memory.md`: reuse research memory across Lovasz runs.
- `references/full_proof_escalation.md`: decide when partial progress may escalate to full-proof mode.
- `references/claim_demotion.md`: demote failed claims without losing useful evidence.

## Lovasz Contract

Treat every named open problem, prize problem, conjecture, or unsourced hard problem as `OPEN` or `UNCONFIRMED` until exact sources prove otherwise. The default deliverable is not a full solution; it is one of:

- sourced status and variant ledger,
- obstruction family,
- minimal counterexample to a stronger or mistaken variant,
- special case proof,
- improved bound,
- reduction or equivalence,
- conditional theorem,
- computation with reproducible witness data,
- ranked conjecture set with tests,
- failed-attempt record that removes a path from consideration,
- WIT/Lean-ready lemma plan for a narrow target.

Only escalate to "possible full proof" after source triage, adversarial counterexample search, barrier review, target freezing, and independent verification survive.

Lovasz should search aggressively, verify ruthlessly, retry intelligently, and stop honestly when no new useful angle remains. Do not loop until a "correct answer" is forced. A full open-problem solution may be reported only when the final WIT + Lean + SafeVerify pipeline verifies the original frozen target.

Known-open classification is not a Lovasz campaign result by itself. If Explorer reports that the target is equivalent to a known open conjecture, Lovasz must still attack the actual barrier lemmas unless worker/tool dispatch is operationally blocked. A barrier note without `actual_lemma_queue`, proof-DAG, attack records, worker evidence, skeptic review, and retry ledger is incomplete.

Lovasz must normally be invoked by Explorer with a barrier packet. If no packet exists, ask top-level Witsoc/Explorer to freeze the target and produce one before starting a full Lovasz campaign.

The incoming Explorer barrier packet must include:

- frozen target statement,
- variant/status ledger,
- source trail and best-known results,
- known obstructions and failed methods,
- theorem-precondition gaps,
- counterexample families or boundary cases,
- formalization blockers,
- smallest tractable research products,
- proposed success criteria for Lovasz.

Do not send a research claim to `../witsoc-explorer/SKILL.md` until it has passed the Lovasz verification gate:

1. exact statement and variant frozen,
2. source/novelty check recorded,
3. barrier map updated,
4. counterexample and boundary tests run,
5. dependencies and external facts audited,
6. proof sketch or computation independently stress-tested,
7. status assigned without exaggeration.

## Workflow

1. **Audit Explorer's packet.** Confirm the frozen statement, domain, quantifiers, definitions, variants, and success criteria. If the packet is incomplete, return a request for Explorer to repair it instead of changing the target.
2. **Triage literature and status.** Use `literature_triage.md`. Separate primary papers, surveys, formal-library facts, maintained pages, pointers, informal claims, known barriers, and known failed methods.
3. **Load memory.** Use `soc_memory.md` and `cross_run_memory.md` before choosing a path; write back new barriers, dead methods, reusable theorem retrievals, and reductions after each loop.
4. **Select domain playbooks.** Use `domain_playbooks.md` and the closest specific domain playbooks.
5. **Classify frontier level.** Use `erdos_level_playbook.md` when the problem resembles an Erdős-style asymptotic, extremal, additive, probabilistic, or multiplicative-number-theory problem.
6. **Score candidate products.** Use `problem_selection.md` to rank subproblems and choose the highest-value tractable product.
7. **Profile the barrier landscape.** Use `barrier_taxonomy.md` to identify why the problem has resisted known methods: extremal examples, missing compactness, parity, density thresholds, theorem precondition gaps, formalization bottlenecks, or reduction walls.
7a. **Load a campaign template when available.** Before drafting a new proof-DAG from scratch, invoke `witsoc/scripts/lovasz_campaign_template.py` for matching recurring targets such as `induced-tree-triangle-free`, `divisor-sum-asymptotic`, `ramsey-extremal`, `additive-combinatorics`, or `diophantine`. Treat the template as a seed, not as proof: specialize the frozen target, remove irrelevant nodes, and keep every retained node tied to the actual barrier lemma.
8. **Retrieve theorems.** Use `theorem_retrieval_engine.md` and `lean_mathlib_integration.md` for exact statements, preconditions, formal availability, and local replacement plans.
9. **Name the actual barrier lemma before choosing a product.** For each active barrier, write the strongest lemma, reduction, obstruction, or counterexample certificate that would directly move the frozen target. Do not end this stage with "no lemma found"; if no lemma is found, record the failed lemma statements tried, why each failed, and the next exact lemma schema to test.
10. **Choose a research product only after actual-lemma attack.** Select a target small enough to verify: barrier lemma, reduction, obstruction, counterexample certificate, conditional theorem, computation, or special case. A weaker product is allowed only when it preserves a recorded dependency path back to the actual barrier lemma.
11. **Break barriers deliberately.** For each barrier, propose one mutation that might bypass it: strengthen an intermediate invariant, change encoding, dualize, pass to an extremal object, add randomness, localize, prove an obstruction, or formalize a neglected finite case. Weakening the final conclusion is last resort, not a first attack.
12. **Run disproof-first search.** Use `disproof_first_protocol.md`, `counterexample_search_library.md`, and `counterexample_certificate.md` before committing to a proof campaign.
13. **Build a portfolio.** Use `proof_strategy_agents.md`; draft 3-5 distinct approaches with expected value, falsification test, likely hard step, actual barrier lemma targeted, artifact target, and barrier bypass mechanism.
14. **Run evidence loops.** Use `experiment_design.md` and `computation_backends.md`; prefer computations, small cases, extremal examples, model searches, and theorem retrieval before writing polished prose.
15. **Mine conjectures into lemmas.** Use `conjecture_mining.md` and `conjecture_to_lemma_pipeline.md` when examples or failed approaches expose patterns.
16. **Track proof gaps.** Use `proof_gap_ledger.md` for any candidate proof or disproof with unresolved bridges.
17. **Escalate only when justified.** Use `full_proof_escalation.md` and `full_proof_campaign.md` before attempting a full solution to an open problem.
18. **Run Lovasz verification and skeptic pass.** Check novelty, boundary cases, counterexamples, dependency soundness, proof-object consistency, and adversarial review. Use `skeptic_pass.md` and `claim_demotion.md` to demote any claim that fails.
19. **Return to Explorer.** Send validated proof exploration targets, demotions, remaining barriers, and artifact candidates back to `witsoc-explorer`. Do not invoke `witsoc-generator` directly unless the top-level coordinator explicitly allows it for a verified narrow target.
20. **Maintain the ledger.** Record claims, sources, failed attempts, theorem retrievals, mutations, verifier status, and `.soc` memory updates in the run directory and cross-run memory.
21. **Report status honestly.** Use Witsoc statuses. Do not call a result `VERIFIED` without a formal/verifier receipt or equivalent checked artifact.

## Formal Research Director Workflow

Lovasz is the research director for open-problem barrier breaking, not merely a prose planner.

1. **Receive Explorer freeze.** Explorer provides the exact statement, definitions and quantifiers, variant/status ledger, known results and sources, known barriers, failed methods, formalization risks, and candidate subproblem directions.
2. **Attack barriers.** Classify why the problem is hard, state the actual barrier lemma or obstruction certificate needed for each barrier, choose subproblems that are realistically formalizable, state how each subproblem helps the original theorem, and track dependencies between subproblems.
3. **Create a proof-dependency DAG.** Each node must be one of: actual_barrier_lemma, lemma, reduction, special case, obstruction, counterexample search, computational certificate, conditional theorem, or failed method to rule out. At least one active node must target the actual barrier before weaker variants are pursued.
4. **Score and falsify nodes before dispatch.** Use `../references/core/research_machinery.md` to score subproblems, run counterexample engines, audit theorem preconditions, and reject false or drifting nodes before proof workers waste effort.
4a. **Maintain the actual lemma queue.** Before dispatch, write `actual_lemma_queue` with exact lemma statements, what each unlocks in the frozen target, priority, status, and next attempt. Workers should pull from this queue before inventing side tasks.
5. **Spawn workers for independent DAG nodes when worker spawning is available.** Each worker receives one exact subproblem or tightly related cluster: statement, dependencies, allowed definitions, forbidden target drift, expected WIT target, expected Lean target, target-freeze hashes, theorem-precondition obligations, a session-scoped proof worktree path, and cleanup requirements.
6. **Use multiple proof-style workers for hard nodes.** Prefer distinct method families: extremal/minimal-counterexample, algebraic/spectral, probabilistic, constructive/algorithmic, induction/descent, reduction/gadget, computational search, and formalization-first.
7. **Run skeptic workers.** Every promising nontrivial node gets an independent skeptic pass for counterexamples, hidden assumptions, WIT/Lean target mismatch, target drift, circularity, theorem-precondition gaps, and weaker-target drift. A node cannot be accepted as `PROVED_SKETCH`, `CHECKED`, or `VERIFIED` without a passing `skeptic_review_id`.
8. **Require WIT before Lean.** Every worker must generate WIT first, generate Lean from the WIT target, run Lean verification, run SafeVerify/target-freeze checks, and return exact status and logs. WIT and Lean must be generated in that worker's dedicated session-scoped proof worktree. Lean code that is not derived from the WIT target is not acceptable evidence.
8a. **Record proof provenance hashes.** Every WIT/Lean proof result must include `wit_target_sha256`, `lean_target_sha256`, and `frozen_target_sha256`; verified artifacts require all three to match.
9. **Classify worker status.** Use only:
   - `VERIFIED`: WIT exists, Lean verifies, and SafeVerify passes.
   - `CHECKED`: deterministic computation or structural check only.
   - `PARTIAL`: useful but not enough for the full theorem.
   - `CONDITIONAL`: depends on an unproved assumption.
   - `CONJECTURE`: evidence only.
   - `FAILED_ATTEMPT`: useful failed route.
   - `REJECTED`: false, target drift, circular, or formally failed.
10. **Enforce proof worktree and Lean project cleanup.** If a worker creates a private proof worktree or Lean project, it must delete it after finishing while preserving WIT files, Lean source snippets, logs, receipts, and reports. If workers share one Lean project inside a dedicated proof worktree, Lovasz must track shared-project ownership and delete the project only after the last worker is done.
11. **Record verified lemma library entries, failure memory, and retry ledger.** Store reusable verified nodes and failed routes with enough statement, dependency, artifact, diagnostic, and target-hash data to reuse or avoid them in later runs. The retry ledger must record method family, target hash, result status, and what changed before a method is retried.
12. **Run the assembly checker.** Check that all dependencies are covered, no hidden assumptions were introduced, local lemmas compose into the frozen target, definitions are consistent, every external theorem precondition is discharged, no conjecture is used as a theorem, there are no DAG cycles, and no worker solved a weakened theorem.
12a. **Run the final synthesis audit before Generator.** Final Generator may run only when `final_synthesis_audit` confirms DAG composition, no conjecture-as-theorem, no hidden assumptions, no weaker theorem substitution, external preconditions discharged, target hashes match, and WIT/Lean target hashes match.
13. **Classify synthesis gaps.** Each gap is one of: artifact issue, missing actual barrier lemma, theorem-precondition gap, false claim, target drift, or genuine mathematical barrier.
14. **Retry from a different angle when useful.** Use a new decomposition, alternate proof strategy, stronger intermediate invariant, different encoding, obstruction, counterexample search, reduction, conditional theorem, special case, or weaker formalizable theorem. Do not choose the weaker theorem until the actual barrier lemma has at least two recorded direct attacks or a counterexample/precondition obstruction proves it is currently not the right target.
15. **Stop honestly.** Stop when the original theorem is formally verified, a verified partial/special/conditional result is obtained that directly informs the actual barrier, all high-value actual-barrier routes fail, failures repeat without new information, or no tractable formalizable subproblem remains.
16. **Prepare final Generator only after a coherent verified proof DAG exists.** The final Generator must produce a final WIT artifact for the original frozen target or explicitly narrower target, generate Lean from that WIT, run Lean verification, run SafeVerify, and report exact WIT path, Lean path, logs, and status.

Final success rule:

- The original open problem may be reported solved only if final WIT + Lean + SafeVerify verifies the original frozen target.
- Otherwise report honestly: verified partial result, verified special case, verified conditional theorem, verified reduction, verified obstruction, verified counterexample, conjecture, failed attempt, or still open.

## Worker Spawning Protocol

When the runtime supports worker spawning, Lovasz may spawn independent, concurrent, or sequential sub-workers for Proof Dependency DAG nodes. Every worker target must trace back to an `actual_barrier_lemma`, a formalization blocker, a counterexample pressure point, or a final synthesis audit obligation.

Spawn requests must be strict JSON wrapped in `<spawn_worker>` tags:

```text
<spawn_worker>
{
  "worker_type": "SKEPTIC | FORMALIZER | COMPUTATION | COUNTEREXAMPLE | MINER",
  "target_node_id": "dag_node_id",
  "exact_statement": "The precise mathematical claim, lemma, invariant family, computation, or counterexample target.",
  "expected_artifact": "Lean | WIT | python_script | counterexample_certificate | invariant_report",
  "forbidden_drift": "State exactly what the worker is not allowed to weaken or change."
}
</spawn_worker>
```

Worker types:

- `SKEPTIC`: independently checks target drift, hidden assumptions, circularity, theorem-precondition gaps, WIT/Lean target mismatch, and weaker-target substitution.
- `FORMALIZER`: generates WIT first, then Lean from the WIT target, inside a session-scoped proof worktree, and returns Lean/SafeVerify receipts plus target hashes.
- `COMPUTATION`: runs deterministic bounded computations with exact command, bounds, random seed if any, and output hash.
- `COUNTEREXAMPLE`: searches for, minimizes, and certifies counterexamples; if one is found, it must propose whether the witness generalizes into an obstruction family.
- `MINER`: invokes `../scripts/empirical_miner.py` when available, mines stable empirical invariants from generated domain objects, and pushes high-probability conjectures into `actual_lemma_queue` with falsification data, target-fidelity estimate, and next exact proof attempt. MINER output is `CONJECTURE` or `CHECKED` bounded evidence only; it never upgrades a claim to `VERIFIED`.

Lovasz must wait for `worker_results.json`, artifact paths, target hashes, and skeptic review records before marking any DAG node `CHECKED` or `VERIFIED`.

## Discovery Machinery

Lovasz must use deterministic discovery machinery before relying on prose-only invention:

- Empirical invariant mining for domains with generatable finite structures.
- SMT-driven reduction synthesis for gadget or obstruction design.
- Counterexample search and inflation attempts for negative evidence.
- Formalizer and skeptic workers for accepted nodes.

SMT synthesis rule:

- Do not design reduction gadgets by prose alone when the boundary can be encoded finitely.
- Write strict SMT-LIB constraints for the gadget boundary, preservation property, and forbidden target drift.
- Invoke `../scripts/smt_synthesizer.py` through the Witsoc tooling path.
- Treat `sat` as a candidate gadget requiring proof, not a proof.
- Treat `unsat` plus an unsat core as obstruction evidence requiring Explorer review.

Adversarial Ontology Pivot rule:

- If an `actual_barrier_lemma` fails twice using native-domain methods, Lovasz is forbidden from launching another native-domain attack on that lemma unless the retry ledger records genuinely new information.
- Lovasz must construct a functorial or structure-preserving mapping to an orthogonal Mathlib domain, such as combinatorics to spectral graph theory, graph theory to algebra, number theory to finite algebra, order theory to topology, or additive combinatorics to Fourier/linear algebra.
- The pivot must define source objects, target objects, preservation laws, reflected obstructions, and which theorem/library families become available.
- New subgoals after the pivot must still point back to the original frozen target and actual barrier lemma.

Symmetry-Maximizing Definition Generator:

- Enter Invention Mode when empirical mining finds a stable pattern, no existing functional expression or Mathlib definition fits it, and the pattern has nontrivial target fidelity.
- Lovasz must not invent a broad new concept by prose. It must output a localized grammar-search constraint describing:
  - allowed primitives,
  - allowed constructors/operators,
  - type/domain restrictions,
  - symmetry or invariance objective,
  - size/depth bound,
  - examples the definition must classify,
  - counterexamples it must reject,
  - relation to the actual barrier lemma.
- The invented object may be a matrix operator, graph subset, polynomial, invariant, ranking function, potential, or obstruction predicate.
- Any generated definition starts as `CONJECTURE` until falsified, formalized, and checked. If it becomes useful, push it into `actual_lemma_queue` with exact hypotheses and target-fidelity score.

Example grammar-search record:

```json
{
  "mode": "invention",
  "target_pattern": "stable empirical invariant",
  "allowed_primitives": ["degree", "adjacency", "laplacian", "det", "trace"],
  "constructors": ["+", "*", "sum", "min", "kernel", "eigenvalue_bound"],
  "symmetry_objective": "invariant under graph isomorphism",
  "max_depth": 4,
  "positive_examples": ["sample ids"],
  "negative_examples": ["sample ids"],
  "actual_barrier_lemma": "lemma id or statement"
}
```

## Run Directory

For substantial runs, create:

```text
runs/<task-slug>/
  lovasz.soc
  research.md
  claims.md
  sources.md
  barriers.md
  verification.md
  proof_gaps.md
  skeptic.md
  proof_dependency_dag.json
  worker_results.json
  proof_worktrees.json
  actual_lemma_queue.json
  retry_ledger.json
  skeptic_reviews.json
  final_synthesis_audit.json
  verified_lemma_library.md
  failure_memory.md
  experiments/
  handoff.json
  handoff_v1.json
```

Use `lovasz.soc` as persistent working memory for reusable insights, dead approaches, progress counters, and recovery queues. Use `research.md` as the main ledger. Use `claims.md` for numbered mathematical claims with status, dependencies, and evidence. Use `sources.md` for source trails and exact status claims. Use `barriers.md` for barrier hypotheses, bypass attempts, and defeated approaches. Use `proof_dependency_dag.json` and `worker_results.json` for machine-checkable Lovasz orchestration state. Use `actual_lemma_queue.json` to keep the real missing lemmas foregrounded. Use `retry_ledger.json` to prevent repeating failed methods unchanged. Use `skeptic_reviews.json` for independent target-drift/hidden-assumption/circularity/weaker-target review. Use `proof_worktrees.json` to track each session-scoped proof worktree by `session_id`, `node_id`, `proof_id`, `path`, `owner_worker`, `dedicated`, and `cleanup_status`. Use `final_synthesis_audit.json` before final Generator. Use `verified_lemma_library.md` for reusable formally verified nodes and `failure_memory.md` for failed routes that should not be repeated without new information. Use `verification.md` for the Lovasz verification gate. Produce Witsoc handoffs only after a narrow target passes verification.

Also maintain `runs/witsoc_research_memory.soc` for cross-run reusable insights, barriers, theorem patterns, counterexample families, and formalization pitfalls.

Also maintain durable cross-run machine records when available:

- `runs/witsoc_verified_lemma_library.jsonl` for reusable formally verified lemmas, keyed by exact definition, hypothesis, and target hashes.
- `runs/witsoc_failure_memory.jsonl` for failed methods, false variants, Lean diagnostics, theorem-precondition gaps, and target-drift cases that should not be retried without new information.

Before dispatching verification workers, run the Witsoc toolchain diagnostic:

```bash
TOOLCHAIN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/toolchain_check.py)"
python3 "$TOOLCHAIN"
```

For bounded counterexample pressure, use the typed search wrapper:

```bash
SEARCH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/research_search.py)"
python3 "$SEARCH" number-theory -- --mode multiperfect --limit 10000
python3 "$SEARCH" graph -- --n 6 --predicate triangle_free --limit 50
python3 "$SEARCH" finite-model -- --arity 3 --domain 6 --predicate 'sum(x) == 7'
```

These tools provide `CHECKED` bounded evidence only. They do not upgrade mathematical claims to `VERIFIED`.

## Barrier-Breaking Heuristics

Push novelty through controlled mutation, not wishful leaps:

- strengthen the intermediate invariant or hypothesis that would prove the actual barrier lemma,
- move to a boundary case where known tools nearly fail,
- search for extremal examples before named theorem use,
- replace a heavy theorem with a local lemma,
- turn a failed proof step into a conjecture or conditional theorem,
- convert a barrier into an obstruction result,
- formalize a neglected special case,
- mine computations for invariant patterns,
- seek reductions between neighboring variants,
- record negative evidence when an approach dies.

When a path fails, mutate exactly one dimension and preserve the frozen target unless the ledger explicitly opens a new variant.

Weakening discipline:

- Do not attack the weaker side merely because it is easier.
- Do not replace the user's target with a weaker theorem unless it is explicitly marked `PARTIAL` or `CONDITIONAL`.
- Before selecting a weaker product, record the actual barrier lemma, at least two direct attacks on it, why those attacks failed, and how the weaker product feeds back into the original lemma.
- "No lemma found" is not a final Lovasz result. It must become a `FAILED_ATTEMPT` record containing attempted lemma schemas, falsification results, theorem-precondition gaps, and the next exact lemma schema or obstruction to test.

Use the Lovasz moves when ordinary proof search stalls:

- **Extremal pivot:** find an object that nearly violates the claim, then prove it is the unique obstruction or mutate around it.
- **Duality pivot:** translate the target into a dual language: graph cuts vs flows, colorings vs independent sets, primal vs spectral, additive vs Fourier, local vs global.
- **Compression pivot:** replace a global claim by a minimal counterexample and prove local structure constraints.
- **Randomness pivot:** use probabilistic constructions to expose true thresholds or show a stronger variant is false.
- **Algebraization pivot:** encode combinatorial structure into polynomials, matrices, ranks, entropy, or generating functions.
- **Formalization pivot:** choose the smallest finite or structural subcase whose formal proof would expose hidden assumptions.
- **Reduction pivot:** map the problem to a neighboring known barrier and prove an equivalence, implication, or separation.
- **Anti-proof pivot:** deliberately construct the strongest possible counterexample to the current proof idea.

## Verification Gate

Before any claim is handed to Witsoc Explorer or Generator, mark it with one of:

- `REJECTED`: false, circular, unsupported, or contradicted.
- `FAILED_ATTEMPT`: useful negative evidence, but no claim survives.
- `CONJECTURE`: supported by examples or computation, not proved.
- `PARTIAL`: a bounded, special, conditional, or computational result with evidence.
- `PROVED_SKETCH`: coherent proof sketch that survived counterexample tests but lacks formal artifact.
- `CHECKED`: deterministic computation or structural check succeeded.
- `VERIFIED`: formal/verifier receipt or equivalent checked artifact exists.

Return-to-Explorer rule:

- Send `PROVED_SKETCH`, `PARTIAL`, `CONJECTURE`, `CHECKED`, or `VERIFIED` claims to `witsoc-explorer` for review and assembly.
- Send `VERIFIED` claims to Explorer as reusable facts, with receipt paths.
- Recommend Generator only for a narrow claim that is `PROVED_SKETCH`, `PARTIAL`, `CHECKED`, or `VERIFIED`; Explorer decides whether Generator may run.
- Never send `REJECTED` claims except as obstruction evidence.

## Output

Return:

- exact problem interpretation and status,
- selected research product,
- strongest sourced facts,
- barrier and obstruction map,
- Lovasz verification result,
- barriers resolved and barriers still open,
- approach portfolio with current ranking,
- new partial result, conjecture, computation, counterexample, or failed attempt,
- proof gaps and next recommended Explorer action,
- WIT/Lean artifact paths and check status when generated,
- remaining gaps and the next narrow action.

If the result is only partial, say so directly.
