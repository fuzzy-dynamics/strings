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

Lovasz is a specialist barrier tool for the orchestrator, not an autonomous
commander. It should produce barrier kernels, proof-DAG options, worker packet
suggestions, failed-method memory, evaluator gaps, and creative mathematical
openings. The orchestrator decides whether to run Lovasz narrowly, expand it
into a campaign, parallelize it with Explorer/Generator, reframe the target, or
ignore a Lovasz recommendation.

## Codex/Claude Contract

Lovasz is the barrier engine for open, unsolved, frontier, and blocked targets.
It should normally start only after Explorer supplies a frozen target and
barrier packet. The orchestrator remains in charge of strategy, budget, worker
assignment, and whether to continue, reframe, or stop. Lovasz should expose
ranked options and mathematical tradeoffs, not a single compulsory route.

Preferred commands:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py llm-contract
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz kernel runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz judge runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz autopsy runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py spawn-template lovasz --target "<problem>"
```

If the runtime is missing, repair it with:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

Known-open status is a starting point, not a final report. Lovasz must attack
actual barrier lemmas, maintain proof-DAG and failure memory, and return to
Explorer. It must not authorize Generator directly.

## Budgeted Lovasz Pass

Lovasz must be easy to activate while keeping one contract. The orchestrator
chooses budget and fanout. Every
Lovasz pass, even a small checkpoint, should try to produce:

```text
actual barrier lemma
one falsification or theorem-precondition test
one proof-DAG seed or updated node
one non-repeat mutation or honest stop reason
one next-action packet
```

When the orchestrator gives more budget, continue the same Lovasz pass into:

```text
validated proof DAG
worker packets/results when useful
skeptic review
formalization feasibility
Explorer return packet
report-quality grade
```

For every Lovasz pass, write or update `lovasz.soc` and emit:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz kernel runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz judge runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz autopsy runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz next-action runs/<task> --out runs/<task>/lovasz_next_action.json
python3 ~/.openscientist/skills/witsoc/witsoc.py next-action runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py proof-workflow runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py ui-summary runs/<task> --write --deep
```

Small Lovasz passes are enough for early deep-run checkpoints; sustained
barrier attack, worker fanout, and reportable open-problem products use the
same Lovasz contract with a larger budget.

## Lovasz Kernel Contract

Lovasz must expose a compact research kernel before sustained campaign
expansion, worker fanout, or final reporting. The kernel gives LLM agents a
machine-readable mathematical state without removing creative control from the
orchestrator.

Required kernel artifacts:

```text
runs/<task>/lovasz_kernel.json
runs/<task>/lovasz_blueprint.json
runs/<task>/proofs/lovasz_blueprint.wit
runs/<task>/actual_barrier_lemmas.json
runs/<task>/route_population.json
runs/<task>/evaluator_registry.json
runs/<task>/lovasz_process_judge.json
runs/<task>/lovasz_barrier_autopsy.json
```

Use:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz kernel runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz judge runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz autopsy runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py lovasz packet runs/<task> --out runs/<task>/lovasz_orchestrator_packet.json
```

`lovasz_barrier_autopsy.json` is the Lovasz failure-analysis artifact. It
clusters failed methods, repeated theorem-precondition gaps, target drift,
formalization bottlenecks, counterexample pressure, and genuine mathematical
barriers. Use it after any repeated failure before spending more budget on the
same route.

The kernel must answer:

- What is the frozen target and target hash?
- What exact actual barrier lemma, obstruction, or counterexample certificate
  is currently attacked?
- Which proof-DAG node is selected and how does it point back to the target?
- Which evaluator or acceptance test checks target fidelity, falsification
  pressure, theorem preconditions, and formalization readiness?
- Which route population exists, and which route is currently best?
- Which `.soc` memory risk suggests a one-axis mutation instead of retry?
- What is the single best next mathematical action?

The process judge scores target fidelity, barrier clarity, evaluator coverage,
proof-graph health, route diversity, memory use, skeptic pressure,
formalization pressure, and next-action sharpness. A low score is not a command
to stop; it is a command to repair Lovasz state before wasting budget.

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
- `../references/core/llm_contract.md`
- `../references/core/exploration_strategy.md`
- `../references/core/handoff.md`
- `../references/core/safeverify.md`
- `../references/core/failure_recovery.md`
- `../references/core/research_machinery.md`

Python execution rule: when Lovasz runs or records Python-based tools,
experiments, replay commands, or scripts, use `python3` explicitly. Do not use
bare `python` in commands, worker instructions, or reproducibility notes.

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
- `references/historical_benchmark_suite.md`: evaluate Lovasz on solved-but-hidden historical problems before trusting open-problem behavior.
- `references/counterexample_certificate.md`: certify, minimize, and verify disproof witnesses.
- `references/proof_gap_ledger.md`: track proof gaps until a proof DAG has no hidden bridges.
- `references/skeptic_pass.md`: independent adversarial review before proof/disproof acceptance.
- `references/soc_memory.md`: use `.soc` memory efficiently across Lovasz loops.
- `references/cross_run_memory.md`: reuse research memory across Lovasz runs.
- `references/full_proof_escalation.md`: decide when partial progress may escalate to full-proof mode.
- `references/claim_demotion.md`: demote failed claims without losing useful evidence.
- `references/algorithmic_research.md`: advisory algorithms for proof-DAG priority, one-axis mutation selection, worker-result ranking, next-action choice, and Lovasz orchestrator packets.

Use `.soc` memory as the primary approach-failure and decision-support memory.
Initialize it with `../scripts/lovasz_soc_memory.py init`, read `context`
before selecting a route, query it before repeating any method, and append every
failed route to `FAILED_APPROACHES` with a do-not-repeat condition. Also update
`CURRENT`, `BARRIERS`, `REUSABLE_TOOLS`, and `ORCHESTRATOR_NOTES` whenever a
run learns something useful for routing. Failure JSONL and markdown ledgers may
exist for validators, but Lovasz must keep `lovasz.soc` as the compact run
memory used for efficient dispatch.

For open-solution campaigns, enforce
`../references/core/open_problem.md#open-solution-protocol`. This is mandatory
for Lovasz runs that are trying to move from partial progress toward an open
solution: use a frozen statement ledger, proof-dependency DAG, computational
search records where applicable, separate worker modes, skeptic proof breaking,
failure taxonomy, and novelty accounting.

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

Lovasz is a gated research state machine. Every run must maintain `lovasz_run.json` as the authoritative manifest with one current phase:

```text
EXPLORER_PACKET_REQUIRED
TARGET_FROZEN
BARRIER_LEDGERS_READY
DISPROOF_FIRST_DONE
PROOF_DAG_READY
WORKERS_DISPATCHED
WORKER_RESULTS_SCORED
SKEPTIC_REVIEW_DONE
FORMALIZATION_SCORED
EXPLORER_RETURN_READY
NO_GO
```

Do not skip phase gates. Use `../scripts/lovasz_run_manifest.py` to create/update the manifest and `../scripts/validate_lovasz_phase.py` before advancing. The manifest must carry the frozen `target_hash`, ledger paths, validator names, allowed next phases, and blocking gaps.

Lovasz status labels are not free-form. Use `../scripts/status_lattice.py` to reject unsupported upgrades. A research step may propose `CONJECTURE`, `CHECKED_BOUNDED`, `FAILED_ATTEMPT`, or `GAP`; only the acceptance layer may upgrade to `VERIFIED_WIT`, `VERIFIED_LEAN`, `VERIFIED_EXTERNAL`, `PARTIAL`, or `CONDITIONAL`, and only with evidence/receipts plus target hash.

Lovasz returns to Explorer through `explorer_return_packet.json`, not prose alone. Generate it with `../scripts/explorer_return_packet.py`; it must list accepted products, selected products, demoted claims, remaining barriers, formalization score, report grade, and `recommended_action`.

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
3. **Load memory.** Use `soc_memory.md` and `cross_run_memory.md` before choosing a path. Run `lovasz_soc_memory.py context runs/<task>` before serious routing; write back current state, new barriers, dead methods, reusable theorem retrievals, tools, reductions, and orchestrator-facing notes after each loop.
4. **Select domain playbooks.** Use `domain_playbooks.md` and the closest specific domain playbooks.
5. **Classify frontier level.** Use `erdos_level_playbook.md` when the problem resembles an Erdős-style asymptotic, extremal, additive, probabilistic, or multiplicative-number-theory problem.
6. **Score candidate products.** Use `problem_selection.md` to rank subproblems and choose the highest-value tractable product.
6a. **Build a result ladder.** Run `../scripts/result_ladder.py runs/<task> --write` before attempting a full proof. The ladder should try toy cases, bounded searches, special classes, obstructions, conditional theorems, improved bounds, and reductions before full-target escalation.
7. **Profile the barrier landscape.** Use `barrier_taxonomy.md` to identify why the problem has resisted known methods: extremal examples, missing compactness, parity, density thresholds, theorem precondition gaps, formalization bottlenecks, or reduction walls.
7a. **Load a campaign template when available.** Before drafting a new proof-DAG from scratch, invoke `../scripts/lovasz_campaign_template.py` for matching recurring targets such as `induced-tree-triangle-free`, `divisor-sum-asymptotic`, `ramsey-extremal`, `additive-combinatorics`, or `diophantine`. Treat the template as a seed, not as proof: specialize the frozen target, remove irrelevant nodes, and keep every retained node tied to the actual barrier lemma.
8. **Retrieve theorems.** Use `theorem_retrieval_engine.md` and `lean_mathlib_integration.md` for exact statements, preconditions, formal availability, and local replacement plans.
9. **Name the actual barrier lemma before choosing a product.** For each active barrier, write the strongest lemma, reduction, obstruction, or counterexample certificate that would directly move the frozen target. Do not end this stage with "no lemma found"; if no lemma is found, record the failed lemma statements tried, why each failed, and the next exact lemma schema to test.
10. **Choose a research product only after actual-lemma attack.** Select a target small enough to verify: barrier lemma, reduction, obstruction, counterexample certificate, conditional theorem, computation, or special case. A weaker product is allowed only when it preserves a recorded dependency path back to the actual barrier lemma.
11. **Break barriers deliberately.** For each barrier, propose one mutation that might bypass it: strengthen an intermediate invariant, change encoding, dualize, pass to an extremal object, add randomness, localize, prove an obstruction, or formalize a neglected finite case. Weakening the final conclusion is last resort, not a first attack.
12. **Run disproof-first search.** Use `disproof_first_protocol.md`, `counterexample_search_library.md`, and `counterexample_certificate.md` before committing to a proof campaign.
12a. **Decompose the target into smaller subproblems.** Run `../scripts/decompose_problem.py --write` after target freeze and before worker dispatch. The decomposition must create proof-DAG nodes for definition audit, counterexample pressure, theorem-precondition bridge, actual barrier lemma, formalizable core, hypothesis isolation, and any domain-specific finite search or reduction nodes. Every node must keep `target_hash` and `dependency_path_to_target`.
12b. **Synthesize missing machine ledgers, then validate them before worker dispatch.** If the prose ledgers contain tagged facts but the JSON ledgers are missing, run `../scripts/synthesize_open_ledgers.py` first. Then require `actual_lemma_queue.json`, `disproof_first.json`, `theorem_precondition_audit.json`, `product_selection.json`, `mutation_ledger.json`, `failure_memory.jsonl` or `failure_memory.md`, and proof-DAG nodes with dependency paths to the frozen target. Use `../scripts/validate_open_problem_run.py`.
12c. **Generate counterexample-search packets.** Run `../scripts/counterexample_search.py` to create bounded falsification packets for the relevant finite domains. A no-witness result is only evidence under stated bounds; an explicit witness can refute.
12d. **Validate proof-DAG integrity before worker dispatch.** Run `../scripts/validate_proof_dag_integrity.py` so accepted nodes cannot depend on conjectures, rejected nodes, missing artifacts, cycles, or target-drifted dependency paths.
13. **Build a portfolio.** Use `proof_strategy_agents.md`; draft 3-5 distinct approaches with expected value, falsification test, likely hard step, actual barrier lemma targeted, artifact target, and barrier bypass mechanism.
14. **Run evidence loops.** Use `experiment_design.md` and `computation_backends.md`; prefer computations, small cases, extremal examples, model searches, and theorem retrieval before writing polished prose.
15. **Mine conjectures into lemmas.** Use `conjecture_mining.md` and `conjecture_to_lemma_pipeline.md` when examples or failed approaches expose patterns.
16. **Track proof gaps.** Use `proof_gap_ledger.md` for any candidate proof or disproof with unresolved bridges.
17. **Escalate only when justified.** Use `full_proof_escalation.md` and `full_proof_campaign.md` before attempting a full solution to an open problem.
18. **Run Lovasz verification and skeptic pass.** Check novelty, boundary cases, counterexamples, dependency soundness, proof-object consistency, and adversarial review. Use `skeptic_pass.md` and `claim_demotion.md` to demote any claim that fails. Then run `../scripts/status_lattice.py` so accepted statuses cannot appear without evidence.
19. **Score worker results.** Run `../scripts/score_lovasz_results.py` against `worker_results.json`, with `witsoc_artifacts.json` when available, and write `lovasz_result_scores.json`. Explorer reviews higher-score results first, but scores never replace verification.
20. **Score formalization feasibility.** Run `../scripts/formalization_feasibility.py` before any Generator handoff. If the result is `POOR_FORMALIZATION_TARGET` or `NEEDS_MATHLIB_THEOREM_SEARCH`, route back to Explorer/Lovasz repair instead of asking Generator to invent missing formal context.
21. **Generate barrier, summary, and report-quality ledgers.** Run `../scripts/summarize_lovasz_run.py`, `../scripts/open_problem_report.py`, and `../scripts/grade_witsoc_report.py` before returning to Explorer.
22. **Return to Explorer.** Generate `explorer_return_packet.json` and send validated proof exploration targets, demotions, remaining barriers, and artifact candidates back to `witsoc-explorer`. Do not invoke `witsoc-generator` directly unless the top-level coordinator explicitly allows it for a verified narrow target.
23. **Maintain the ledger.** Record claims, sources, failed attempts, theorem retrievals, mutations, verifier status, artifact registry entries, and `.soc` memory updates in the run directory and cross-run memory.
24. **Report status honestly.** Use Witsoc statuses. Do not call a result `VERIFIED` without a formal/verifier receipt or equivalent checked artifact.

## Formal Research Director Workflow

Lovasz is the research director for open-problem barrier breaking, not merely a prose planner.

1. **Receive Explorer freeze.** Explorer provides the exact statement, definitions and quantifiers, variant/status ledger, known results and sources, known barriers, failed methods, formalization risks, and candidate subproblem directions. Initialize or update `lovasz_run.json` with `../scripts/lovasz_run_manifest.py`.
2. **Attack barriers.** Classify why the problem is hard, state the actual barrier lemma or obstruction certificate needed for each barrier, choose subproblems that are realistically formalizable, state how each subproblem helps the original theorem, and track dependencies between subproblems.
3. **Create a proof-dependency DAG.** Each node must be one of: actual_barrier_lemma, lemma, reduction, special case, obstruction, counterexample search, computational certificate, conditional theorem, or failed method to rule out. At least one active node must target the actual barrier before weaker variants are pursued.
4. **Score and falsify nodes before dispatch.** Use `../references/core/research_machinery.md` to score subproblems, run counterexample engines, audit theorem preconditions, and reject false or drifting nodes before proof workers waste effort.
4a. **Maintain the actual lemma queue.** Before dispatch, write `actual_lemma_queue` with exact lemma statements, what each unlocks in the frozen target, priority, status, and next attempt. Workers should pull from this queue before inventing side tasks.
5. **Spawn workers for independent DAG nodes when worker spawning is available.** Each worker receives one exact subproblem or tightly related cluster: statement, dependencies, allowed definitions, forbidden target drift, expected WIT target, expected Lean target, target-freeze hashes, theorem-precondition obligations, a session-scoped proof worktree path, and cleanup requirements.
5a. **Gate dispatch through SOC memory.** Generate dispatch packets with `../scripts/lovasz_worker_dispatch.py runs/<task> --write`. If `.soc` contains a matching failed method, dispatch is blocked until the packet records a distinct method family or a one-axis mutation in `mutation_ledger.json`.
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
11a. **Write `.soc` updates immediately.** On every `FAILED_ATTEMPT`, `REJECTED`, target-drift diagnosis, or theorem-precondition blocker, append a concise entry with `../scripts/lovasz_soc_memory.py add-failure`. On every new bottleneck, use `add-barrier`. On every reusable method or theorem pattern, use `add-tool`. On every important strategic warning or optional parallel split, use `add-note`. Do not wait until final synthesis.
12. **Run the assembly checker.** Check that all dependencies are covered, no hidden assumptions were introduced, local lemmas compose into the frozen target, definitions are consistent, every external theorem precondition is discharged, no conjecture is used as a theorem, there are no DAG cycles, and no worker solved a weakened theorem.
12a. **Run the final synthesis audit before Generator.** Final Generator may run only when `final_synthesis_audit` confirms DAG composition, no conjecture-as-theorem, no hidden assumptions, no weaker theorem substitution, external preconditions discharged, target hashes match, and WIT/Lean target hashes match.
13. **Classify synthesis gaps.** Each gap is one of: artifact issue, missing actual barrier lemma, theorem-precondition gap, false claim, target drift, or genuine mathematical barrier.
14. **Retry from a different angle when useful.** Use a new decomposition, alternate proof strategy, stronger intermediate invariant, different encoding, obstruction, counterexample search, reduction, conditional theorem, special case, or weaker formalizable theorem. Do not choose the weaker theorem until the actual barrier lemma has at least two recorded direct attacks or a counterexample/precondition obstruction proves it is currently not the right target.
15. **Stop honestly.** Stop when the original theorem is formally verified, a verified partial/special/conditional result is obtained that directly informs the actual barrier, all high-value actual-barrier routes fail, failures repeat without new information, or no tractable formalizable subproblem remains.
16. **Prepare final Generator only after a coherent verified proof DAG exists.** The final Generator must produce a final WIT artifact for the original frozen target or explicitly narrower target, generate Lean from that WIT, run Lean verification, run SafeVerify, and report exact WIT path, Lean path, logs, and status.

Before returning to Explorer, run the production gates when available:

```bash
SCORE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/score_lovasz_results.py)"
LOVASZ_PACKET="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_orchestrator_packet.py)"
LOVASZ_KERNEL="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_kernel.py)"
LOVASZ_JUDGE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_judge.py)"
SUMMARY="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/summarize_lovasz_run.py)"
VALIDATE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_run.py)"
MANIFEST="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_run_manifest.py)"
PHASE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_phase.py)"
LATTICE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/status_lattice.py)"
RETURN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/explorer_return_packet.py)"
DECOMPOSE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/decompose_problem.py)"
SYNTH="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/synthesize_open_ledgers.py)"
DAG_INTEGRITY="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_proof_dag_integrity.py)"
SPAWN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/spawn_workers_from_dag.py)"
FALSIFY="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/counterexample_search.py)"
FORMAL="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/formalization_feasibility.py)"
GRADE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/grade_witsoc_report.py)"
python3 "$MANIFEST" runs/<task>
python3 "$PHASE" runs/<task>
python3 "$DECOMPOSE" runs/<task> --write --out runs/<task>/problem_decomposition.json
python3 "$SYNTH" runs/<task>
python3 "$FALSIFY" runs/<task> --out runs/<task>/counterexample_search_templates.json
python3 "$DAG_INTEGRITY" runs/<task> --artifact-registry "$PLANE_SESSION_DIR/witsoc_artifacts.json"
python3 "$SPAWN" runs/<task>
python3 "$LATTICE" runs/<task>
python3 "$SCORE" runs/<task>/worker_results.json --registry "$PLANE_SESSION_DIR/witsoc_artifacts.json" --out runs/<task>/lovasz_result_scores.json
python3 "$SUMMARY" runs/<task>
python3 "$VALIDATE" runs/<task> --mode deep --artifact-registry "$PLANE_SESSION_DIR/witsoc_artifacts.json"
OPEN_VALIDATE="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_open_problem_run.py)"
OPEN_REPORT="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/open_problem_report.py)"
python3 "$OPEN_VALIDATE" runs/<task>
python3 "$FORMAL" runs/<task> --out runs/<task>/formalization_feasibility.json
python3 "$LOVASZ_KERNEL" runs/<task> --write
python3 "$LOVASZ_JUDGE" runs/<task> --write
python3 "$LOVASZ_PACKET" runs/<task> --out runs/<task>/lovasz_orchestrator_packet.json
python3 "$OPEN_REPORT" runs/<task>
python3 "$GRADE" runs/<task> --out runs/<task>/report_quality_grade.json
python3 "$RETURN" runs/<task> --out runs/<task>/explorer_return_packet.json
python3 "$MANIFEST" runs/<task> --phase EXPLORER_RETURN_READY
python3 "$PHASE" runs/<task>
```

## Partial Result Closure Audit

Lovasz may produce partial progress, but a partial result is not acceptable just
because it is interesting. Every `PARTIAL` or `CONDITIONAL` result for an
open/unsolved/unconfirmed target must expose the exact remaining barrier and try
to close it before the result is routed downstream.

Required closure fields for each partial or conditional DAG node, worker result,
or generator artifact:

- `remaining_gap_statement`: the exact theorem, lemma, precondition,
  computation, or formalization gap that prevents the frozen target from being
  solved.
- `why_not_full_solution`: why the current result does not prove the original
  frozen target.
- `known_result_comparison`: whether the result is new, a restatement, a weaker
  known theorem, a finite check, or a variant of a sourced result.
- `novelty_status`: one of `new`, `known`, `variant`, `unknown`, or
  `not_applicable`.
- `next_exact_experiment_or_lemma`: the next precise lemma, theorem retrieval,
  computation, counterexample search, or formalization target.
- `closure_attempts`: at least two distinct attempts to close the remaining gap.
  Each attempt records `method_family`, `attempt`, `result`, and
  `remaining_blocker`.

Required skeptic classification for any accepted partial or conditional result:

- `claim_classification`: one of `target_drift`, `known_result_restatement`,
  `hidden_assumption`, `finite_evidence_only`, `genuine_progress`, or
  `needs_repair`.

If a partial result cannot supply this audit, demote it to `CONJECTURE`,
`FAILED_ATTEMPT`, or `GAP` rather than routing it as usable progress.

Final success rule:

- The original open problem may be reported solved only if final WIT + Lean + SafeVerify verifies the original frozen target.
- Otherwise report honestly: verified partial result, verified special case, verified conditional theorem, verified reduction, verified obstruction, verified counterexample, conjecture, failed attempt, or still open.

## Worker Spawning Protocol

When the runtime supports worker spawning, Lovasz may spawn as many independent,
concurrent, or sequential sub-workers as it wants for Proof Dependency DAG
nodes, subject only to the available runtime, budget, and task constraints. Do
not impose an artificial fixed cap such as one worker per phase or a small
portfolio size when additional independent agents would improve coverage,
falsification, computation, formalization, or skeptic review. Every worker
target must trace back to an `actual_barrier_lemma`, a formalization blocker, a
counterexample pressure point, or a final synthesis audit obligation.

Spawn requests must be strict JSON wrapped in `<spawn_worker>` tags:

```text
<spawn_worker>
{
  "worker_type": "SKEPTIC | FORMALIZER | COMPUTATION | COUNTEREXAMPLE | MINER",
  "target_node_id": "dag_node_id",
  "exact_statement": "The precise mathematical claim, lemma, invariant family, computation, or counterexample target.",
  "expected_artifact": "Lean | WIT | python_script | counterexample_certificate | invariant_report",
  "forbidden_drift": "State exactly what the worker is not allowed to weaken or change.",
  "stop_condition": "State the exact evidence, counterexample, verifier result, or time/budget condition that ends the worker."
}
</spawn_worker>
```

Every spawn request must validate against
`../references/schemas/lovasz-spawn-worker.schema.json` using
`../scripts/validate_spawn_packet.py --kind spawn` when a filesystem packet is
created. Do not dispatch vague workers whose target is not an exact DAG node,
actual barrier lemma, formalization blocker, counterexample pressure point, or
synthesis audit obligation.

Worker types:

- `SKEPTIC`: independently checks target drift, hidden assumptions, circularity, theorem-precondition gaps, WIT/Lean target mismatch, and weaker-target substitution.
- `FORMALIZER`: generates WIT first, then Lean from the WIT target, inside a session-scoped proof worktree, and returns Lean/SafeVerify receipts plus target hashes.
- `COMPUTATION`: runs deterministic bounded computations with exact command, bounds, random seed if any, and output hash.
- `COUNTEREXAMPLE`: searches for, minimizes, and certifies counterexamples; if one is found, it must propose whether the witness generalizes into an obstruction family.
- `MINER`: invokes `../scripts/empirical_miner.py` when available, mines stable empirical invariants from generated domain objects, and pushes high-probability conjectures into `actual_lemma_queue` with falsification data, target-fidelity estimate, and next exact proof attempt. MINER output is `CONJECTURE` or `CHECKED` bounded evidence only; it never upgrades a claim to `VERIFIED`.

Lovasz must wait for `worker_results.json`, artifact paths, target hashes, and skeptic review records before marking any DAG node `CHECKED` or `VERIFIED`.

Every worker result must use the standard result packet shape:

```json
{
  "worker_id": "worker id",
  "worker_type": "SKEPTIC | FORMALIZER | COMPUTATION | COUNTEREXAMPLE | MINER | PROOF_BUILDER | LITERATURE_AUDITOR | SYNTHESIS_CHECKER",
  "node_id": "dag node id",
  "claim": "exact claim investigated",
  "status": "VERIFIED | CHECKED | PROVED_SKETCH | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT | REJECTED | GAP | OPEN",
  "target_hash": "frozen or node target hash",
  "dependencies": [],
  "evidence": ["source, command, verifier log, witness, or proof note"],
  "artifacts": [],
  "failure_class": "none | false_claim | target_drift | theorem_precondition_gap | missing_barrier_lemma | artifact_issue | computational_obstruction | genuine_mathematical_barrier | hidden_assumption | circularity | weaker_target_substitution",
  "next_mutation": "next exact attempt or stop reason"
}
```

Validate filesystem worker-result packets against
`../references/schemas/lovasz-worker-result.schema.json` using
`../scripts/validate_spawn_packet.py --kind result`.

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
  lovasz_kernel.json
  lovasz_blueprint.json
  lovasz_process_judge.json
  actual_barrier_lemmas.json
  route_population.json
  evaluator_registry.json
  worker_results.json
  proof_worktrees.json
  actual_lemma_queue.json
  retry_ledger.json
  skeptic_reviews.json
  closure_attempts.json
  theorem_retrieval_audit.json
  final_synthesis_audit.json
  verified_lemma_library.md
  failure_memory.md
  experiments/
  handoff.json
  handoff_v1.json
```

Use `lovasz_run.json` as the authoritative phase manifest. Use `lovasz.soc` as persistent working memory for reusable insights, dead approaches, progress counters, and recovery queues. Use `research.md` as the main ledger. Use `claims.md` for numbered mathematical claims with status, dependencies, and evidence. Use `sources.md` for source trails and exact status claims. Use `barriers.md` for barrier hypotheses, bypass attempts, and defeated approaches. Use `proof_dependency_dag.json`, `lovasz_kernel.json`, `lovasz_blueprint.json`, `lovasz_process_judge.json`, `actual_barrier_lemmas.json`, `route_population.json`, `evaluator_registry.json`, and `worker_results.json` for machine-checkable Lovasz orchestration state. Use `actual_lemma_queue.json` to keep the real missing lemmas foregrounded. Use `counterexample_search_templates.json` to preserve bounded falsification packets. Use `formalization_feasibility.json` to prevent premature WIT/Lean routing. Use `report_quality_grade.json` to expose missing production evidence before final response. Use `explorer_return_packet.json` as the only structured Lovasz-to-Explorer return. Use `retry_ledger.json` to prevent repeating failed methods unchanged. Use `skeptic_reviews.json` for independent target-drift/hidden-assumption/circularity/weaker-target review and partial-result classification. Use `closure_attempts.json` to record last-mile gap-closing attempts before accepting partial products. Use `theorem_retrieval_audit.json` to record nearby theorem statements, preconditions, formal availability, rejected theorem uses, and missing hypotheses for each serious DAG node. Use `proof_worktrees.json` to track each session-scoped proof worktree by `session_id`, `node_id`, `proof_id`, `path`, `owner_worker`, `dedicated`, and `cleanup_status`. Use `final_synthesis_audit.json` before final Generator. Use `verified_lemma_library.md` for reusable formally verified nodes and `failure_memory.md` for failed routes that should not be repeated without new information. Use `verification.md` for the Lovasz verification gate. Produce Witsoc handoffs only after a narrow target passes verification.

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
- `PARTIAL`: a bounded, special, conditional, or computational result with evidence, remaining gap, novelty comparison, skeptic classification, and at least two closure attempts.
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
