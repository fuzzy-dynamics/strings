---
name: witsoc
description: General mathematics skill and subsystem for OpenScientist. Use for every type of mathematical work: problem solving, proof generation, proof critique, disproof, theorem formalization, premise search, supply search, lemma discovery, proof automation, Lean/Coq-adjacent planning, algorithms, complexity reductions, algebra, analysis, topology, number theory, combinatorics, graph theory, geometry, probability, logic, and scientific arguments whose correctness depends on chained premises. Contains internal subskills `witsoc-research-lovasz` for open-problem research programs, `witsoc-explorer` for mathematical exploration, and `witsoc-generator` for WIT proof artifacts; can also work directly for small math questions.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc

Witsoc is the top-level mathematics workflow and owns its own internal subsystem. It decides whether a task needs direct solution, Explorer triage, Lovasz barrier attack, Generator artifacting, or a repair loop.

Use this skill for all mathematical tasks. For simple questions, answer directly with a clear derivation. For serious proof work, coordinate the internal subskills:

- `witsoc-research-lovasz/SKILL.md`: Lovasz-mode research-program orchestration for named open problems, unsolved conjectures, Erdős-style questions, frontier theorem discovery, barrier analysis, source/status triage, conjecture mining, disproof-first search, and verified partial research products.
- `witsoc-explorer/SKILL.md`: search, premise selection, lemma discovery, counterexample hunting, proof automation planning, open-problem research ledgers, and general mathematical exploration.
- `witsoc-generator/SKILL.md`: `.wit` proof generation, repair, structural checking, verifier-context construction, receipt tracking, and optional Lean formalization.

These subskills live inside this folder. If you need their full instructions, read the relevant nested `SKILL.md`; do not look for sibling top-level skill directories.

When a task routes through Lovasz, the user-facing progress message must include:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz.
```

Shared protocols live under `references/core/`. Load only the protocol needed for the current task:

- `references/core/status.md`: canonical status labels and verification discipline.
- `references/core/handoff.md`: state-machine routing and structured `handoff.json`.
- `references/core/failure_recovery.md`: failure records, diversification, and stop conditions.
- `references/core/open_problem.md`: common open-problem rules.
- `references/core/exploration_strategy.md`: Phase 0 profiling, solved-problem reconstruction, ontology mapping, theorem retrieval ranking, backward chaining, falsification hierarchy, barrier analysis, conjecture mining, proof objects, theorem replacement, mutation tracking, and lemma economics.
- `references/core/research_machinery.md`: Lovasz proof-DAG decomposition, subproblem scoring, counterexample engines, theorem precondition audit, proof-style workers, skeptic workers, verified lemma library, failure memory, and final assembly checks.
- `references/core/repair.md`: failure diagnosis and repair classes.
- `references/core/goal_cache.md`: reusable subgoal/tactic cache rules.
- `references/core/safeverify.md`: target freezing and anti-cheating checks.
- `references/core/lean_verification.md`: Lean LSP/REPL/cache-aware checking loop.
- `references/core/tooling.md`: deterministic tool/API discipline and CLI consolidation target.
- `references/schemas/handoff.schema.json`: strict Explorer-to-Generator handoff schema.
- `references/schemas/witsoc-handoff-schema.json`: strict Generator blueprint schema for `handoff_v1.json`.
- `references/examples/handoff_solved_problem.json` and `references/examples/handoff_open_problem.json`: concrete valid handoff examples.
- `references/examples/handoff_v1_blueprint.json`: minimal Generator blueprint example.
- `scripts/validate_handoff.py`: deterministic handoff validation and arithmetic checks.
- `scripts/validate_proof_dag.py`: deterministic Lovasz proof-DAG and worker-result validation.

## Routing

Use this WITSOC-specific routing table before choosing a subskill, model, or tool. Intake always starts at top-level `witsoc`; serious mathematical work then starts with Explorer.

| Task | WITSOC route |
|---|---|
| Simple math answer | Top-level `witsoc`; answer directly with a clear derivation. |
| Hard proof exploration | `witsoc-explorer`; Phase 0 profile the problem, freeze the exact target, triage solved/open/unconfirmed/false/under-specified status, map ontology, rank theorem candidates, run backward chaining, run falsification hierarchy, test obstructions/barriers, compare proof objects, EV-rank sketches, and produce `runs/<task>/handoff.json` plus strict `runs/<task>/handoff_v1.json` when Generator is needed. |
| Open problem / Erdős-style research problem | `witsoc-explorer` first. Explorer freezes the statement and status, then writes a Lovasz barrier packet if the target is open, unsolved, unconfirmed, frontier-level, or blocked. Lovasz attacks that packet and returns claims/barriers/gaps to Explorer. Explorer reviews and either sends a new barrier packet to Lovasz, demotes the target, stops honestly, or authorizes Generator for a narrow accepted result. |
| Deep run proving/disproving an open-style target | `witsoc-explorer` first, then mandatory `witsoc-research-lovasz` if Explorer cannot settle the target as solved/false/routine. A report that only says "open/unsupported by known results" is not complete unless Lovasz has already attempted barrier breaking or the run records a concrete blocker preventing Lovasz dispatch. |
| Counterexample search | `witsoc-explorer` plus computation where useful; minimize and verify the counterexample before presenting it. |
| Premise / lemma discovery | `witsoc-explorer`; supply search and dependency planning. |
| WIT generation | `witsoc-explorer` first for nontrivial theorem targets, then `witsoc-generator` after Explorer accepts the frozen target and proof plan. Existing `.wit` inspection/repair can start at Generator. |
| User explicitly asks for WIT code | Explorer freezes and judges the target first unless this is an existing `.wit` repair. Generator is mandatory after Explorer accepts the target; it must produce a `.wit` artifact or report a concrete blocker. Do not answer with only exploration, prose, or Lean. |
| User asks for WIT code plus Lean proof | Explorer first, Generator second. Generator must generate/check WIT, generate Lean from that frozen WIT target, attempt Lean verification, and report artifact paths plus exact WIT/Lean status. |
| Deep run proving a theorem with WIT/Lean requested | Explorer starts the run; Lovasz is inserted for open/blocked barriers; Generator runs only after Explorer accepts the assembled target and any Lovasz verification gate has passed. The run is not complete until Generator has produced a `.wit` artifact, run structural checks/context generation, and attempted Lean if requested. |
| WIT repair after rejection | `witsoc-generator` for edits; call `witsoc-explorer` when rejected steps need new premises, lemmas, or a different strategy. |
| Lean build error / failed formal proof | `witsoc-generator` Repair Diagnosis Protocol first; classify the failure, cite compiler/verifier evidence, propose the minimal repair, then retry without changing the frozen theorem target. If the same failure class repeats, use `references/core/failure_recovery.md` before reporting final failure. |
| Multiple partial proof sketches | `witsoc-explorer` structured Proof Sketch Protocol with EV ranking in `handoff.json`; `witsoc-generator` artifacts only for the selected sketch or precise subresult. |
| Repeated subgoal or familiar failure | Use Goal Cache Protocol if available; otherwise record the reusable subgoal/tactic or failure pattern in proof sketch notes. |
| External theorem blocks progress | `witsoc-explorer` External Theorem Replacement Policy; pin the exact needed statement and preconditions, search for formal availability or a local replacement, then hand a precise obligation to Generator. |
| Sketch ranking / prioritization | `witsoc-explorer` Rater Mode; rank sketches for search priority only, never for verification. |
| Structural checking | Deterministic `wit check` or WITSOC `check.sh`; no LLM. |
| Verifier context building | Deterministic `wit verify` or WITSOC `verify.sh`; context only, not proof. |
| Semantic verification | Skeptical external verifier output plus `wit receipt`; never treat `wit check` or `wit verify` as semantic proof. |
| Lean/formalization planning | `witsoc-generator` with Explorer handoff when needed; prefer Lean LSP/REPL/per-file checks during repair, run final `lake build`, then SafeVerify. |
| Tool execution | Prefer explicit WITSOC API tools when available; otherwise deterministic WITSOC scripts or native `wit` CLI. Do not use an LLM for structural checks, context building, target-freeze checks, status, or receipt parsing. |

Operating principles:

- Prefer deterministic tooling where possible.
- Use strong models for discovery and repair, skeptical models for verification.
- Never substitute confidence for receipts.

Use internal `witsoc-explorer` first when the task is serious proof work, theorem proving, WIT/Lean generation, an open problem, an unsolved conjecture, or a research-like target. Explorer owns problem freezing, status triage, source trail, theorem-candidate ranking, counterexample pressure, proof-path selection, and final arbitration of whether Lovasz or Generator may proceed.

Use internal `witsoc-research-lovasz` only after Explorer has produced a barrier packet for an open, unsolved, unconfirmed, frontier-level, or blocked target. Lovasz owns barrier attack as a formal-verification-driven research director: barrier classification, proof-dependency DAG decomposition, worker dispatch for independent subproblems, WIT-before-Lean verification requirements, one-axis mutations, conjecture/lemma mining, reductions, special cases, conditional theorems, obstruction results, computational certificates, verification gates, and honest demotion of unsupported claims. Lovasz returns to Explorer; it does not decide that Generator may solve an open problem.

Use internal `witsoc-explorer` for:

- definitions and theorem lookup,
- supply search or premise selection,
- lemma discovery,
- example/counterexample testing,
- proof strategy comparison,
- decomposition into subgoals,
- automation/tactic planning.

Use internal `witsoc-generator` when the task needs:

- a `.wit` artifact,
- explicit WIT code in the final answer,
- proof, disproof, formalization, or audit,
- checking or repairing an existing `.wit`,
- verifier contexts or receipts,
- Lean generation from a WIT proof.

## Discovery Attempt Requirement

For prompts that ask to prove, disprove, solve, make progress on, or deep-run an open-style mathematical target, Witsoc must not stop after literature/status classification alone.

If Explorer concludes:

- `OPEN`,
- `UNSOLVED`,
- `UNCONFIRMED`,
- unsupported by known results,
- blocked by a structural gap,
- "requires a new theorem,"
- or "not proved by standard asymptotics,"

then Explorer must create a Lovasz barrier packet and route to Lovasz before the run can be called complete.

A completion critic must reject the run as incomplete if all of the following hold:

- the original user asked for a proof/disproof/deep research attempt,
- Explorer or workers classified the problem as open/unsupported,
- no Lovasz proof-DAG/barrier attack was attempted,
- no concrete operational blocker prevented Lovasz dispatch.

Acceptable final states after Lovasz are: formally verified solution, verified partial/special/conditional result, verified obstruction/counterexample/reduction, conjecture with evidence, failed attempt with failure memory, or still open after documented barrier attacks. "Known results do not prove it" is a finding, not a complete discovery run.

For targets classified as equivalent to a known open conjecture, "open by literature" is not a completed prove/disprove run. Witsoc must either run a Lovasz campaign against the actual barrier lemmas or record a concrete operational blocker. A single prose barrier artifact does not satisfy the Lovasz campaign requirement; require `actual_lemma_queue`, proof-DAG, barrier attack records, worker evidence when available, skeptic review, and retry ledger.

## Explorer-Lovasz-Generator Loop

For every serious mathematical task, use this state machine:

```text
INTAKE -> EXPLORER_TRIAGE
EXPLORER_TRIAGE -> DIRECT_ANSWER | EXPLORER_PROOF_PLAN | LOVASZ_BARRIER_PACKET
LOVASZ_BARRIER_PACKET -> LOVASZ_ATTACK -> EXPLORER_REVIEW
EXPLORER_REVIEW -> LOVASZ_BARRIER_PACKET | GENERATOR_HANDOFF | HONEST_STOP
GENERATOR_HANDOFF -> GENERATE_WIT -> CHECK_WIT -> BUILD_CONTEXT -> OPTIONAL_LEAN -> REPORT
GENERATOR_FAILURE -> EXPLORER_REVIEW
```

Explorer must create the Lovasz barrier packet before invoking Lovasz. The packet must include:

- frozen target statement,
- variant/status ledger,
- source trail and best-known results,
- known obstructions and failed methods,
- theorem-precondition gaps,
- counterexample families or boundary cases,
- formalization blockers,
- smallest tractable research products,
- proposed success criteria for Lovasz.

Lovasz must return to Explorer with:

- barriers resolved,
- barriers still open,
- claims with status: `REJECTED`, `FAILED_ATTEMPT`, `CONJECTURE`, `PARTIAL`, `PROVED_SKETCH`, `CHECKED`, or `VERIFIED`,
- proof-dependency DAG nodes, worker outcomes, and formal verification evidence when workers were used,
- evidence and source links,
- counterexample/search results,
- proof gaps,
- next recommended target.

Explorer reviews Lovasz output and decides whether the result is enough to assemble a coherent proof/disproof/partial result, whether another barrier packet should be sent back to Lovasz, whether the target must be demoted, or whether Generator may now be invoked.

Repeat Explorer -> Lovasz -> Explorer until one of these stop states occurs:

- solved/routine proof plan ready,
- verified partial result ready,
- checked computational/counterexample result ready,
- conditional theorem ready,
- formalizable narrow lemma ready,
- no honest progress path remains.

Only after Explorer accepts the assembled target and Lovasz verification has passed may Generator run. Generator may not upgrade claim status or decide open-problem truth. If WIT or Lean fails, Generator reports the failure to Explorer; Explorer decides whether to route back to Generator for artifact repair or to Lovasz for a mathematical barrier.

When Lovasz decomposes a target into multiple subproblems, each worker must generate WIT first, generate Lean from that WIT target, run Lean verification, run SafeVerify/target-freeze checks, preserve required artifacts/logs, and clean up temporary Lean projects according to `references/core/lean_verification.md`. Lovasz may synthesize only verified or honestly classified nodes, and final Generator may run only after the proof DAG composes back to the frozen target or an explicitly narrower target.

Every WIT/Lean proof artifact must be generated inside a session-scoped proof worktree. Use a separate worktree for each proof target or worker node, named from the session id and proof/node id, for example `witsoc-proof-${OSCI_SESSION_ID}-${node_id}`. Preserve WIT, Lean source, logs, receipts, SafeVerify records, and reports in the run artifact directory; delete or mark the proof worktree cleanup status according to `references/core/lean_verification.md`. Handoffs and worker results must record `session_id`, `proof_worktree`, and `worktree_status`.

Use both Explorer and Generator for substantial formalization problems. The Explorer -> Generator handoff is mandatory before writing WIT on nontrivial problems:

1. Explorer pins the problem profile, solved-problem map when relevant, ontology map, ranked theorem candidates, backward chains, falsification results, obstructions/barriers, selected open-product target, conjectures, exact target, hypotheses, definitions, likely counterexamples, proof objects, lemma plan with economics, external verification records, mutation tracker, proof sketches, EV scores, and target-freeze hashes.
2. Explorer writes `runs/<task>/handoff.json` conforming to `references/schemas/handoff.schema.json`.
3. Explorer writes `runs/<task>/handoff_v1.json` conforming to `references/schemas/witsoc-handoff-schema.json`.
4. The orchestrator validates both files before Generator is invoked.
5. For Lovasz-directed work, the orchestrator also runs `scripts/validate_proof_dag.py` on `handoff.json`.
6. Generator reads only `handoff_v1.json`, writes the `.wit` artifact, and runs deterministic checks. Generator must not invent mathematical truth beyond the accepted handoff.
7. Rejections move the state to Repair or Explorer using `references/core/repair.md` and `references/core/failure_recovery.md`.
8. Generator records receipts when verifier verdicts are available and uses `references/core/lean_verification.md` if Lean is requested.

## Shared Protocols

Do not duplicate common rules in task-local prompts. For serious proof work, load the relevant shared protocols:

- Status and verification: `references/core/status.md`.
- Structured state and handoffs: `references/core/handoff.md`.
- Failure recovery and stop conditions: `references/core/failure_recovery.md`.
- SafeVerify target freezing: `references/core/safeverify.md`.
- Repair diagnosis: `references/core/repair.md`.
- Goal cache: `references/core/goal_cache.md`.
- Exploration strategy: `references/core/exploration_strategy.md`.
- Research machinery: `references/core/research_machinery.md`.
- Lean checking loop: `references/core/lean_verification.md`.
- Tooling: `references/core/tooling.md`.

Explicit WIT request contract:

- If the user asks for “WIT code”, “.wit”, “provide WIT”, or “WIT + Lean”, producing WIT is mandatory.
- Do not satisfy such a request with only an exploration summary, natural-language proof, proof sketch, or Lean code.
- If a deep run delegates work to other agents, the orchestrator must dispatch or require a Generator step that writes the `.wit` artifact.
- Whenever a `.wit` artifact is generated or updated, activate the Witsoc plugin iframe and open the generated file.
- If WIT cannot be produced, return `GAP`, `FAILED_ATTEMPT`, or `REJECTED` with the exact blocker and the best partial sketch.
- If Lean is also requested, Lean must be generated from the WIT target, not from an unrelated informal theorem statement.
- Final output must include either the `.wit` path or an inline WIT code block, plus structural check status.

Witsoc plugin activation after `.wit` generation:

The Witsoc UI plugin is external to the strings repo. On a fresh system, check
the verified plugin index and install it before opening the iframe. Plugin
installation requires `oras`, `cosign`, and `tar` on the host.

```bash
"$PLANE_TOOL_BIN" plugins available
"$PLANE_TOOL_BIN" plugins list
# If witsoc is not listed locally:
"$PLANE_TOOL_BIN" plugins install witsoc
```

Then open the generated file in the plugin iframe:

```bash
"$PLANE_TOOL_BIN" plugins iframe use witsoc
"$PLANE_TOOL_BIN" plugins iframe bash witsoc open path/to/generated.wit
```

If structural checking is run, also push the check action to the iframe:

```bash
"$PLANE_TOOL_BIN" plugins iframe bash witsoc check
```

If the plugin command is unavailable, mention that plugin activation failed, but still return the `.wit` artifact and check status. If structural checking, verifier review, or Lean generation fails, use `references/core/failure_recovery.md` before presenting the problem as finally failed.

Final status honesty:

- `VERIFIED` only if formal/verifier evidence supports it.
- `CHECKED` only for deterministic computation or structural checks.
- `PROVED_SKETCH` only for a coherent but not formal proof sketch.
- `PARTIAL` for special cases, bounds, reductions, conditionals, or computational products.
- `CONJECTURE` for evidence without proof.
- `FAILED_ATTEMPT` or `REJECTED` when appropriate.

Subskill boundaries:

- Explorer does not write final `.wit` except for very small tasks, and it arbitrates all Lovasz and Generator returns.
- Lovasz does not perform initial intake and does not route directly to Generator unless the top-level coordinator explicitly allows it for a verified narrow target.
- Generator avoids broad theorem search, does not upgrade claim status, and sends mathematical blockers back to Explorer.
- Top-level Witsoc coordinates the loop and decides when to return to Explorer.

## Default Output

For a small math answer, provide the result and reasoning.

For a serious proof task, provide:

- exact theorem/problem interpretation,
- exploration summary if used,
- open-problem status, if applicable,
- proof-sketch status, partial results, conjectures, failed approaches, or known gaps, if applicable,
- `.wit` path if generated,
- inline WIT code or `.wit` path when explicitly requested,
- structural check result,
- verifier-context path or summary,
- receipt path if any,
- current status,
- failure output if blocked or stopped,
- next useful step.

If Lean generation is requested, use internal `witsoc-generator`, prefer LSP/REPL/per-file checks during repair, and return Lean only after final `lake build` plus SafeVerify succeeds. If Lean repair is blocked, say `Lean code generation failed`.
