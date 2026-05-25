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

- `witsoc-explorer/SKILL.md`: search, premise selection, lemma discovery, counterexample hunting, proof automation planning, and general mathematical exploration.
- `witsoc-generator/SKILL.md`: `.wit` proof generation, repair, structural checking, verifier-context construction, receipt tracking, and optional Lean formalization.

These subskills live inside this folder. If you need their full instructions, read the relevant nested `SKILL.md`; do not look for sibling top-level skill directories.

## Routing

Use this WITSOC-specific routing table before choosing a subskill, model, or tool:

| Task | WITSOC route |
|---|---|
| Simple math answer | Top-level `witsoc`; answer directly with a clear derivation. |
| Hard proof exploration | `witsoc-explorer`; normalize the target, test obstructions, compare strategies, and produce a lemma plan. |
| Open problem / Erdős-style research problem | `witsoc-explorer` first in Open Problem Mode; track known status, variants, conjectures, failed attempts, proof sketches, partial results, formal subgoals, and obstruction families. Use `witsoc-generator` only for precise partial results, conditional theorems, counterexamples, or lemmas worth artifacting. |
| Counterexample search | `witsoc-explorer` plus computation where useful; minimize and verify the counterexample before presenting it. |
| Premise / lemma discovery | `witsoc-explorer`; supply search and dependency planning. |
| WIT generation | `witsoc-generator`; create a `.wit` artifact. |
| User explicitly asks for WIT code | Mandatory `witsoc-generator`; produce a `.wit` artifact or report a concrete blocker. Do not answer with only exploration, prose, or Lean. |
| User asks for WIT code plus Lean proof | Mandatory `witsoc-generator`; first generate/check WIT, then generate Lean from that WIT. The final response must include the WIT artifact path and either Lean build success or `Lean code generation failed`. |
| Deep run proving a theorem with WIT/Lean requested | Use both subskills, but the run is not complete until Generator has produced a `.wit` artifact, run structural checks/context generation, and attempted Lean if requested. |
| WIT repair after rejection | `witsoc-generator` for edits; call `witsoc-explorer` when rejected steps need new premises, lemmas, or a different strategy. |
| Lean build error / failed formal proof | `witsoc-generator` Repair Diagnosis Protocol first; classify the failure, cite compiler/verifier evidence, propose the minimal repair, then retry without changing the frozen theorem target. If the same failure class repeats, invoke the Failure Recovery Ladder instead of reporting final failure. |
| Multiple partial proof sketches | `witsoc-explorer` Proof Sketch Protocol to compare gaps and choose the next mutation; `witsoc-generator` artifacts only for the selected sketch or precise subresult. |
| Repeated subgoal or familiar failure | Use Goal Cache Protocol if available; otherwise record the reusable subgoal/tactic or failure pattern in proof sketch notes. |
| External theorem blocks progress | `witsoc-explorer` External Theorem Replacement Policy; pin the exact needed statement and preconditions, search for formal availability or a local replacement, then hand a precise obligation to Generator. |
| Sketch ranking / prioritization | `witsoc-explorer` Rater Mode; rank sketches for search priority only, never for verification. |
| Structural checking | Deterministic `wit check` or WITSOC `check.sh`; no LLM. |
| Verifier context building | Deterministic `wit verify` or WITSOC `verify.sh`; context only, not proof. |
| Semantic verification | Skeptical external verifier output plus `wit receipt`; never treat `wit check` or `wit verify` as semantic proof. |
| Lean/formalization planning | `witsoc-generator` with Explorer handoff when needed; return Lean only after `lake build` succeeds. |
| Script execution | Deterministic WITSOC scripts or native `wit` CLI; do not use an LLM for structural checks, context building, status, or receipt parsing. |

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

1. Explorer pins the exact target, hypotheses, useful facts, examples, likely counterexamples, and lemma plan.
2. Generator turns the selected plan into a `.wit` artifact.
3. Generator runs structural check and builds verifier contexts.
4. Explorer can review rejected steps, search missing premises, or discover replacement lemmas.
5. Generator repairs the `.wit`, records receipts when verifier verdicts are available, and asks about Lean generation.

## Failure Recovery Ladder

For a serious problem, Witsoc must not give up after one failed approach. A failure is useful research evidence, but it must trigger diversification before the run is declared blocked.

Use this ladder whenever `wit check`, verifier review, Lean build, literature search, counterexample search, or proof construction fails in a way that blocks the main target:

1. Record the failed attempt in `.soc` or the session plan with:
   - approach name,
   - exact theorem target,
   - failure class,
   - rejected step, diagnostic, or missing theorem,
   - repair already tried,
   - reusable lesson.
2. Keep the original theorem target frozen unless the user explicitly changes it.
3. Launch or request at least two independent alternate-method agents when Plane/OpenScientist worker spawning is available:
   - one agent should pursue a different proof strategy or external theorem route,
   - one agent should pursue a different formalization, counterexample, obstruction, or simplification route.
4. The alternate agents must be told not to repeat the failed method. Their prompts should include the recorded failure and ask for a genuinely different route.
5. If all alternate agents fail, run a critic/synthesis pass that compares failures, identifies the common blocker, and decides whether to:
   - spawn a more targeted lemma/premise-search agent,
   - narrow the artifact to a conditional or partial result,
   - mark the original target `GAP`, `PARTIAL`, `CONDITIONAL`, `FAILED_ATTEMPT`, or `OPEN`.
6. Only report final failure after this diversification has happened or after worker spawning is unavailable and the same blocker has repeated under at least two distinct methods.

Do not keep retrying the same proof sketch, same Lean encoding, or same external theorem bridge. A retry must change the mathematical method, decomposition, formalization target, source theorem, or search space.

Suggested worker prompt shape:

```text
The current Witsoc attempt failed.
Frozen target: <exact theorem>.
Failed method: <method>.
Failure class: <compiler/verifier/math blocker>.
Do not repeat: <specific route>.
Try a distinct route: <strategy family>.
Return: proof sketch or counterexample, WIT/Lean implications, exact gaps, and whether this route should replace the current plan.
```

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

If structural checking is run, also push the check command to the iframe:

```bash
"$PLANE_TOOL_BIN" plugins iframe bash witsoc check
```

If the plugin command is unavailable, mention that plugin activation failed, but still return the `.wit` artifact and check status. If structural checking, verifier review, or Lean generation fails, follow the Failure Recovery Ladder before presenting the problem as finally failed.

Subskill boundaries:

- Explorer does not write final `.wit` except for very small tasks.
- Generator avoids broad theorem search unless a repair requires it.
- Top-level Witsoc coordinates the loop and decides when to return to Explorer.

## Status Discipline

Never call a proof `VERIFIED` from a chat proof, `wit check`, or `wit verify` alone.

- `wit check`: structural validity only.
- `wit verify`: verifier-context generation only; it does not verify the math.
- `wit receipt`: records external verifier verdicts.
- The prover and verifier must be separate agents; the same agent that wrote or repaired the proof must not supply the semantic verifier verdicts.
- `VERIFIED`: structural check passed and a complete receipt covers accepted verifier verdicts.
- `UNVERIFIED`: structurally valid and contexts generated, but no accepted receipt.
- `OPEN`: the problem is known or currently treated as unsolved; no complete proof or disproof is being claimed.
- `PARTIAL`: a lemma, bound, family of cases, obstruction, computation, or conditional result has been produced, but the original open problem remains unsolved.
- `CONDITIONAL`: the result depends on an explicit unproved assumption, conjecture, or external theorem whose preconditions are not fully established here.
- `CONJECTURE`: a proposed statement supported by evidence or analogy, not a theorem.
- `FAILED_ATTEMPT`: a documented approach did not close the target and should be preserved as negative information.
- `GAP`: an explicit unresolved obligation remains.
- `REJECTED`: structural failure or verifier rejection.

For open problems, default to `OPEN`, `PARTIAL`, or `CONDITIONAL`. Do not report that an Erdős-style or otherwise open problem is solved unless there is an externally checkable proof path, adversarial review has not found a blocker, and any generated WIT or formal artifact follows the receipt/checker discipline above.

For failed proof attempts, preserve the failure class, exact rejected step or compiler diagnostic, attempted repair, and reusable lesson. A failed formal sketch is research evidence, not disposable scratch work.

SafeVerify discipline applies to all Lean/formal outputs: do not accept artifacts that use forbidden placeholders, weaken the theorem target, introduce fake bridge lemmas, or change definitions to make the theorem trivial. Lean compiler success is necessary for Lean verification, but target preservation and anti-cheating checks are also required.

Stop rather than thrash when the same failure class repeats without progress, when all active sketches depend on the same unresolved bridge, when a needed external theorem cannot be located or replaced within budget, or when the search budget is exhausted. Report `GAP`, `PARTIAL`, or `FAILED_ATTEMPT` with the best evidence instead of presenting a vague failure.

Before reporting `VERIFIED`, enforce all of:

- all obligations have verdicts,
- the final `SHOW` is covered,
- no `GAP` or `REJECTED` labels remain,
- receipt status matches the `.wit` header,
- verifier output is not truncated or suspiciously incomplete.

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

If Lean generation is requested, use internal `witsoc-generator` and return Lean only after `lake build` succeeds. If Lean repair is blocked, say `Lean code generation failed`.
