---
name: witsoc
description: General mathematics skill and subsystem for OpenScientist. Use for every type of mathematical work: problem solving, proof generation, proof critique, disproof, theorem formalization, premise search, supply search, lemma discovery, proof automation, Lean/Coq-adjacent planning, algorithms, complexity reductions, algebra, analysis, topology, number theory, combinatorics, graph theory, geometry, probability, logic, and scientific arguments whose correctness depends on chained premises. Contains internal subskills `witsoc-explorer` for mathematical exploration and `witsoc-generator` for WIT proof artifacts; can also work directly for small math questions.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc

Witsoc is the top-level mathematics workflow and owns its own internal subsystem. It decides whether a task needs exploration, proof-artifact generation, or both.

Use this skill for all mathematical tasks. For simple questions, answer directly with a clear derivation. For serious proof work, coordinate the internal subskills:

- `witsoc-explorer/SKILL.md`: search, premise selection, lemma discovery, counterexample hunting, proof automation planning, open-problem research ledgers, and general mathematical exploration.
- `witsoc-generator/SKILL.md`: `.wit` proof generation, repair, structural checking, verifier-context construction, receipt tracking, and optional Lean formalization.

These subskills live inside this folder. If you need their full instructions, read the relevant nested `SKILL.md`; do not look for sibling top-level skill directories.

Shared protocols live under `references/core/`. Load only the protocol needed for the current task:

- `references/core/status.md`: canonical status labels and verification discipline.
- `references/core/handoff.md`: state-machine routing and structured `handoff.json`.
- `references/core/failure_recovery.md`: failure records, diversification, and stop conditions.
- `references/core/open_problem.md`: common open-problem rules.
- `references/core/exploration_strategy.md`: Phase 0 profiling, solved-problem reconstruction, ontology mapping, theorem retrieval ranking, backward chaining, falsification hierarchy, barrier analysis, conjecture mining, proof objects, theorem replacement, mutation tracking, and lemma economics.
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

## Routing

Use this WITSOC-specific routing table before choosing a subskill, model, or tool:

| Task | WITSOC route |
|---|---|
| Simple math answer | Top-level `witsoc`; answer directly with a clear derivation. |
| Hard proof exploration | `witsoc-explorer`; Phase 0 profile the problem, triage solved/open status, map ontology, rank theorem candidates, run backward chaining, run falsification hierarchy, test obstructions/barriers, compare proof objects, EV-rank sketches, and produce `runs/<task>/handoff.json` plus strict `runs/<task>/handoff_v1.json` when Generator is needed. |
| Open problem / Erdős-style research problem | `witsoc-explorer` first in Open Problem Mode; read `references/core/open_problem.md` and, for detailed source triage, `witsoc-explorer/references/open_problems.md`. Track exact status, source trail, variants, conjectures, failed attempts, proof sketches, partial results, formal subgoals, computations, and obstruction families. Use `witsoc-generator` only for precise partial results, conditional theorems, counterexamples, computations, failed-attempt artifacts, or lemmas worth artifacting. |
| Counterexample search | `witsoc-explorer` plus computation where useful; minimize and verify the counterexample before presenting it. |
| Premise / lemma discovery | `witsoc-explorer`; supply search and dependency planning. |
| WIT generation | `witsoc-generator`; create a `.wit` artifact. |
| User explicitly asks for WIT code | Mandatory `witsoc-generator`; produce a `.wit` artifact or report a concrete blocker. Do not answer with only exploration, prose, or Lean. |
| User asks for WIT code plus Lean proof | Mandatory `witsoc-generator`; first generate/check WIT, then generate Lean from that WIT. The final response must include the WIT artifact path and either Lean build success or `Lean code generation failed`. |
| Deep run proving a theorem with WIT/Lean requested | Use both subskills, but the run is not complete until Generator has produced a `.wit` artifact, run structural checks/context generation, and attempted Lean if requested. |
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

Use internal `witsoc-explorer` when the task is underspecified, hard, research-like, search-heavy, or needs:

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

Use both for substantial problems. The Explorer -> Generator handoff is mandatory before writing WIT on nontrivial problems:

1. Explorer pins the problem profile, solved-problem map when relevant, ontology map, ranked theorem candidates, backward chains, falsification results, obstructions/barriers, selected open-product target, conjectures, exact target, hypotheses, definitions, likely counterexamples, proof objects, lemma plan with economics, external verification records, mutation tracker, proof sketches, EV scores, and target-freeze hashes.
2. Explorer writes `runs/<task>/handoff.json` conforming to `references/schemas/handoff.schema.json`.
3. Explorer writes `runs/<task>/handoff_v1.json` conforming to `references/schemas/witsoc-handoff-schema.json`.
4. The orchestrator validates both files before Generator is invoked.
5. Generator reads only `handoff_v1.json`, writes the `.wit` artifact, and runs deterministic checks.
6. Rejections move the state to Repair or Explorer using `references/core/repair.md` and `references/core/failure_recovery.md`.
7. Generator records receipts when verifier verdicts are available and uses `references/core/lean_verification.md` if Lean is requested.

## Shared Protocols

Do not duplicate common rules in task-local prompts. For serious proof work, load the relevant shared protocols:

- Status and verification: `references/core/status.md`.
- Structured state and handoffs: `references/core/handoff.md`.
- Failure recovery and stop conditions: `references/core/failure_recovery.md`.
- SafeVerify target freezing: `references/core/safeverify.md`.
- Repair diagnosis: `references/core/repair.md`.
- Goal cache: `references/core/goal_cache.md`.
- Exploration strategy: `references/core/exploration_strategy.md`.
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

```bash
"$PLANE_TOOL_BIN" plugins iframe use witsoc
"$PLANE_TOOL_BIN" plugins iframe bash witsoc open path/to/generated.wit
```

If structural checking is run, also push the check action to the iframe:

```bash
"$PLANE_TOOL_BIN" plugins iframe bash witsoc check
```

If the plugin command is unavailable, mention that plugin activation failed, but still return the `.wit` artifact and check status. If structural checking, verifier review, or Lean generation fails, use `references/core/failure_recovery.md` before presenting the problem as finally failed.

Subskill boundaries:

- Explorer does not write final `.wit` except for very small tasks.
- Generator avoids broad theorem search unless a repair requires it.
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
