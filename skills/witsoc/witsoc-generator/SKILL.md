---
name: witsoc-generator
description: Internal Witsoc proof-artifact generation subskill. Use inside the Witsoc subsystem to create, repair, structurally check, verifier-context-build, receipt-track, and optionally Lean-formalize `.wit` proof artifacts for mathematics and rigorous arguments. Use for WIT proofs, disproofs, formalizations, audits, reductions, algorithm correctness proofs, rejected-step repair, and Lean-adjacent proof artifacts. `wit check` is structural only; `wit verify` builds contexts only; semantic acceptance requires external verifier verdicts and a receipt; Lean output must pass `lake build`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Generator

Witsoc Generator is the artifact engine inside Witsoc. It converts mathematical intent or an Explorer handoff into a `.wit` proof artifact with explicit labels, dependencies, structural checking, verifier contexts, receipts, and optional Lean formalization.

The generator is not a chat-proof mode. If this subskill is used, create or update a `.wit` artifact unless the user only asks to inspect existing WIT files. For nontrivial new proof tasks, require an Explorer handoff before writing the WIT.

If the user explicitly asks for WIT code, `.wit`, or WIT plus Lean, WIT generation is mandatory. Do not return only a plan, prose proof, verifier discussion, or Lean formalization. The generator must either write a `.wit` artifact or report a concrete blocker with status `GAP`, `FAILED_ATTEMPT`, or `REJECTED`.

If generation, structural checking, verifier review, or Lean formalization fails for a serious problem, the generator must not end the run after the first blocked method. Preserve the failure and hand it back to top-level Witsoc/Explorer for alternate-method agents unless worker spawning is unavailable.

## Non-Negotiable Semantics

- `wit check` validates syntax, labels, scoping, imports, references, and proof structure. It does not verify mathematical truth.
- `wit verify` builds isolated contexts for a verifier. It does not verify mathematical truth.
- `wit receipt` records verifier verdicts. It trusts the provided verdict text; do not treat an incomplete or low-quality verifier output as strong evidence.
- `VERIFIED` requires structural success plus complete accepted verifier verdicts recorded in a receipt.
- `UNVERIFIED` means structurally valid with contexts generated but no accepted receipt.
- `OPEN` means the original research problem remains unsolved and the artifact is not claiming a full solution.
- `PARTIAL` means the artifact captures a subcase, lemma, bound, obstruction, computation, or other limited progress.
- `CONDITIONAL` means the artifact proves a result only under explicit extra assumptions, conjectures, or external facts.
- `CONJECTURE` means the artifact records a proposed statement or evidence target, not a proof.
- `FAILED_ATTEMPT` means the artifact records a failed proof route or rejected bridge as negative information.
- `GAP` means an explicit unresolved mathematical obligation remains.
- `REJECTED` means structural failure or semantic verifier rejection.

Never call a WIT proof `VERIFIED` because it “looks right,” because `wit check` passed, or because `wit verify` printed contexts.

For open problems, never let a partial artifact imply that the original problem is solved. The artifact title, status, theorem statement, and report must all distinguish the original open problem from the narrower result being recorded.

## Inputs

Generator can start from:

- a user theorem/problem,
- an explicit request for WIT code or WIT plus Lean,
- an existing `.wit` file,
- a Witsoc Explorer handoff,
- a rejected verifier context,
- a Lean/formalization target,
- an algorithm or reduction specification,
- an open-problem handoff for a partial result, conditional theorem, counterexample, obstruction, computation, conjecture, or failed attempt.

If the target is ambiguous, pin an interpretation before writing the artifact. If the ambiguity materially affects truth, ask or state the chosen interpretation.

## Reference Files

Load only as needed:

- `references/wit.md`: full `.wit` syntax and scoping reference.
- `references/soc.md`: `.soc` persistent memory format.
- `references/examples/composite_block.wit`: compact theorem example.
- `references/examples/grover_constant.wit`: nested case-analysis example.
- `references/examples/sat_reduction.wit`: reduction example.

If unsure about WIT syntax, read `references/wit.md` before editing.

## Script Surface

Scripts live at:

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/witsoc/witsoc-generator/scripts
```

Invoke with `bash <path>` because executable bits may not survive sync.

| Script | Purpose |
|---|---|
| `init.sh --name N --claim X [--given H] [--out file.wit]` | Create a `.wit` skeleton; refuses overwrite. |
| `check.sh <file.wit|dir> [...]` | Run structural validation. |
| `audit.sh <file.wit>` | Static audit for `GAP`, `CITE`, vague `BY`, and receipt issues. |
| `context.sh <file.wit> [--step N] [--out path]` | Build raw isolated verifier context. |
| `verify.sh <file.wit> [--step N] [--out path]` | Structural gate plus verifier-context output. Does not call an LLM. |
| `cycle.sh <file.wit> [--out-dir dir]` | Run the full verification-prep cycle: check, audit, verifier-context build, and status; writes `<name>.verify.txt`. |
| `receipt.sh <file.wit> --from verifier.txt` | Parse verdicts, write `.wit.receipt.json`, update status. |
| `status.sh <file.wit>` | Summarize status, receipt, and structural result. |

Fallback native CLI:

```bash
wit check path/to/file.wit
wit verify path/to/file.wit --step 3
wit verify path/to/file.wit
wit context path/to/file.wit
cat verdicts.txt | wit receipt path/to/file.wit
```

## Artifact Contract

Every serious generator output should have:

- exact target statement,
- relationship to the original open problem, if applicable,
- `.wit` file path,
- inline WIT code when the user explicitly requested code in the answer and no file path is enough,
- Witsoc plugin activation status,
- structural check result,
- verifier context path or output,
- audit/status result,
- receipt path if one exists,
- status label,
- rejected labels or gaps,
- short proof idea.

When an artifact or Lean translation fails, also write a failure note beside the artifact, for example `runs/<task>/approach_N_failure.md`, containing:

- frozen theorem target,
- failed method,
- failed artifact path,
- exact `wit check`, verifier, or Lean diagnostic,
- rejected step or missing premise,
- repair attempts already made,
- methods that the next agents must avoid,
- two suggested alternate method families.

A good `.wit` file:

- starts with `-- Status: UNVERIFIED` for ordinary proof artifacts, or the narrowest applicable open-problem status for research artifacts, unless a receipt says otherwise,
- has one `MODULE`,
- states all domains and hypotheses,
- has a theorem/reduction/algorithm target aligned with the user request,
- uses one mathematical move per labeled step,
- cites exact dependencies in `BY`,
- closes every case,
- ends every proof with final `QED BY ...`,
- uses `GAP` instead of fake bridges,
- avoids Lean syntax inside WIT.

Audit weak spots include:

- label-only justifications such as `BY [3].` or `BY obvious`,
- unproven theorem preconditions,
- final claim drift,
- unclosed case splits,
- vague external theorem references,
- accidental Lean syntax in WIT,
- hidden assumptions such as nonzero, finite, compact, measurable, or positive.

## WIT Writing Protocol

### 0. Mandatory WIT Generation Triggers

Generate or update WIT when the user says any of:

- “provide WIT code”
- “write a `.wit` proof”
- “give WIT and Lean”
- “prove this with WIT”
- “deep run proving X theorem, provide WIT code and Lean proof”

Required behavior:

1. Freeze the exact theorem target.
2. If nontrivial, get or create an Explorer handoff.
3. Write a `.wit` artifact.
4. Activate the Witsoc plugin iframe and open the generated `.wit` file.
5. Run structural check when tools are available.
6. Build verifier context when tools are available.
7. If Lean is requested, generate Lean from the WIT target after WIT exists.
8. Final response includes `.wit` path or inline WIT code, plugin activation status, structural check status, and Lean status.

Forbidden behavior for explicit WIT requests:

- stopping after exploration only,
- returning only a natural-language proof,
- returning only Lean,
- saying WIT “could be generated” without generating it,
- treating a proof sketch as the requested WIT artifact.

Plugin activation command after writing any `.wit` artifact:

```bash
"$PLANE_TOOL_BIN" plugins iframe use witsoc
"$PLANE_TOOL_BIN" plugins iframe bash witsoc open path/to/generated.wit
```

After `check.sh` or `wit check` succeeds or fails, push the check action to the iframe when available:

```bash
"$PLANE_TOOL_BIN" plugins iframe bash witsoc check
```

Do not treat plugin activation failure as proof failure. Report it separately as a UI/plugin issue while preserving the WIT artifact path.

### 0.1 Failure Diversification Handoff

Use this protocol before returning a final `GAP`, `FAILED_ATTEMPT`, or `REJECTED` for a nontrivial theorem:

1. Freeze the target and summarize the failed route.
2. Write the failure note described above.
3. Ask top-level Witsoc/Explorer to spawn alternate-method agents when Plane/OpenScientist spawning is available.
4. Suggested alternates:
   - different proof strategy or external theorem source,
   - different formalization decomposition,
   - counterexample/obstruction search,
   - lemma discovery or premise search,
   - weakened conditional theorem only if the original target remains explicitly marked as unresolved.
5. Do not ask a new agent to "fix this proof" unless the repair route is materially different. Prefer "try a distinct route and explain why it avoids the recorded failure."

Only stop locally without spawning alternates when the failure is purely mechanical and immediately repairable, or when worker spawning is unavailable and at least two materially different local methods have already failed.

For nontrivial problems, start from an Explorer handoff package containing target, definitions, hypotheses, conclusion, strategy, lemma sequence, dependency graph, external facts, theorem preconditions, case split, known gaps, counterexamples checked, and formalization notes. Do not substitute broad theorem search inside Generator for this handoff; return to Explorer when a repair needs new lemmas or premises.

For open-problem handoffs, require a narrower artifact target before writing WIT:

```text
Open problem:
Current status: OPEN | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT
Artifact target:
Result type: lemma | conditional theorem | counterexample | obstruction | computation | failed attempt
Statement:
Assumptions:
Evidence:
Proof sketch or computation:
Known gaps:
Why this helps the open problem:
```

If the handoff asks for a full solution to a known open problem without adversarial exploration and a precise proof path, return to Explorer instead of writing a proof artifact.

### 1. Freeze The Target

Record:

```text
Name:
Kind: theorem | lemma | disproof | reduction | algorithm correctness | audit
Original open problem, if any:
Artifact status: UNVERIFIED | OPEN | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT | GAP
Variables and domains:
Hypotheses:
Definitions:
Conclusion:
External facts allowed:
```

Do not silently strengthen the theorem. Do not weaken the conclusion to make the proof easy.

### 2. Build An Obligation Graph

Before writing the final `.wit`, sketch:

```text
Goal -> Lemma A, Lemma B, Case split C
Lemma A -> hypotheses + definition
Lemma B -> Lemma A + external theorem T
Case C -> subcases C1, C2
```

Each node should become either a WIT step, a helper claim, a `CITE`, or a `GAP`.

### 3. Choose Granularity

Use enough labels that a skeptical verifier can judge each step locally.

Split a step if it combines:

- algebra plus inequality,
- existence plus uniqueness,
- theorem invocation plus precondition check,
- construction plus correctness,
- forward plus reverse direction,
- termination plus complexity,
- multiple case branches.

### 4. Write WIT

Canonical theorem skeleton:

```wit
-- Status: UNVERIFIED
MODULE module_name

THEOREM module_name:
  GIVEN:
    - hypotheses
  CLAIM:
    conclusion.

PROOF OF module_name:
  [1] ASSUME setup fact.
      BY hypothesis.
  [2] HAVE intermediate claim.
      BY [1], named method or theorem.
  [3] SHOW conclusion.
      BY [2], final assembly.
  QED BY [3].
```

Rules:

- Labels are sequential inside each scope.
- No forward, self, or cross-case references.
- Every nontrivial `BY` names local labels and method/theorem.
- `CITE` may introduce an external theorem, but downstream use must still be checked.
- `GAP` is honest and preferable to handwaving.
- Avoid `BY obvious`, `BY clearly`, `BY standard`, `BY Mathlib`, and bare `BY [n]` for nontrivial inferences.

## Specialized Artifact Modes

### Open-Problem Partial Artifacts

For Erdős-style and other open-problem work, write artifacts that make the scope narrow and explicit. Acceptable artifact targets include:

- a proved special case,
- a conditional theorem,
- a counterexample to a stronger variant,
- an obstruction lemma,
- a computation certificate or exhaustive finite check,
- a conjecture statement with evidence,
- a failed attempt showing exactly where a bridge breaks.

Rules:

- The `.wit` header should use `-- Status: UNVERIFIED`, `-- Status: OPEN`, `-- Status: PARTIAL`, `-- Status: CONDITIONAL`, `-- Status: CONJECTURE`, `-- Status: FAILED_ATTEMPT`, or `-- Status: GAP` as appropriate unless a receipt upgrades a proof artifact.
- The theorem or claim must state the narrower artifact target, not the full open problem, unless the full proof is actually being artifacted.
- Record the original open problem in comments or setup context.
- Use `GAP` for the unresolved bridge from the partial result to the original open problem.
- Do not convert computational evidence into a universal proof unless the finite exhaustive domain and checker are explicit.
- Do not hide failed attempts; a precise failed bridge can be an artifact when it prevents repeated bad work.

Expected report fields:

```text
Original open problem:
Artifact target:
Result type:
Status:
What is proved or recorded:
What remains open:
GAP or failed labels:
Verifier context:
Next useful Explorer task:
```

### Disproof

A disproof artifact should prove that the counterexample satisfies every hypothesis and violates the conclusion.

Required structure:

- define the counterexample,
- verify hypotheses,
- show conclusion fails,
- conclude the original universal claim is false.

### Reductions

Use `REDUCTION`, `FROM`, `TO`, `PRESERVING`, then `PROOF OF`.

Checklist:

- construction is well-defined,
- forward direction,
- reverse direction,
- resource/polynomial bound,
- preserved property,
- edge cases.

### Algorithm Correctness

State:

- `INPUT`,
- `OUTPUT`,
- `REQUIRES`,
- `ENSURES`,
- invariants,
- termination measure,
- runtime and space claims.

Separate:

- initialization,
- invariant preservation,
- exit implies postcondition,
- termination,
- complexity.

### Audits

For an existing proof:

- preserve the original claim,
- identify each unsupported step,
- mark false or missing bridges,
- propose minimal repairs,
- produce a repaired `.wit` only if requested or clearly needed.

## Structural Check And Context Build

Preferred cycle:

```bash
bash "$SCRIPTS/check.sh" path/to/file.wit
bash "$SCRIPTS/audit.sh" path/to/file.wit
bash "$SCRIPTS/verify.sh" path/to/file.wit --out path/to/file.verify.txt
bash "$SCRIPTS/status.sh" path/to/file.wit
```

Or:

```bash
bash "$SCRIPTS/cycle.sh" path/to/file.wit
```

If structural checking fails, repair the `.wit` before building semantic contexts.

Standard user request:

```text
run full WIT verification-prep cycle for this file
```

Expected report:

```text
Status:
Structural check:
Audit warnings:
Verifier context path:
Receipt:
Rejected/GAP labels:
Next action:
```

## Semantic Verification Protocol

A verifier must judge each generated context skeptically. It should reject unless the target step follows from exactly the cited premises and allowed method.

Expected verdict format:

```text
[1] ACCEPT: reason
[2] REJECT: reason
[3.1] GAP: reason
```

Persist verdicts:

```bash
bash "$SCRIPTS/receipt.sh" path/to/file.wit --from verifier-output.txt
bash "$SCRIPTS/status.sh" path/to/file.wit
```

Before reporting `VERIFIED`, enforce all receipt completeness checks:

- all obligations have verdicts,
- the final `SHOW` is covered,
- no `GAP` or `REJECTED` labels remain,
- receipt status matches the `.wit` header,
- verifier output is not truncated or suspiciously incomplete.

Current receipt parsing may accept only parsed verdict lines, so do not treat a suspiciously incomplete receipt as high assurance.

## Repair Protocol

Before editing after any WIT verifier rejection, structural failure, or Lean/compiler failure, diagnose the failure. Do not jump directly to a rewrite.

For every rejection:

```text
Rejected label:
Claim:
Cited premises:
Verifier reason:
Failure class:
Compiler/build evidence, if any:
Likely cause:
Repair:
Risk:
New labels introduced:
```

Failure classes:

- wrong_tactic
- wrong_theorem
- missing premise
- missing_hypothesis
- unknown_identifier
- theorem precondition not proved
- algebra/logic error
- type_mismatch
- coercion_issue
- unsolved_goal
- quantifier or domain mismatch
- out-of-scope reference
- target drift
- forbidden_escape
- import_missing
- vacuous_proof
- case not closed
- step too compressed
- false statement.

Repair choices:

- split into substeps,
- add a helper lemma,
- cite a precise external theorem,
- prove theorem preconditions,
- weaken a false intermediate claim without weakening the final theorem,
- add a legitimate hypothesis only if the original task allows it,
- mark `GAP`,
- hand back to Explorer for premise search or counterexample hunting.

Do not resubmit cosmetic rewrites. Every repair must reduce a real obligation.

For Lean failures, preserve the frozen theorem target. A repair may change proof terms, tactics, helper lemmas, imports when allowed, or decomposition, but it must not silently change variables, hypotheses, definitions, or conclusion.

### Lean Compiler Loop Mode

Use this mode when the user requests Lean, a formal proof, or repair of a Lean build failure.

Loop:

```text
freeze theorem target -> generate/edit proof -> run lake build -> diagnose failure -> repair -> repeat until verified, stopped, or budget exhausted
```

Rules:

- Freeze the theorem statement before repair begins.
- Default edit region is the proof body; changing imports or helper lemmas must be justified by the diagnosis.
- Every retry must cite the exact compiler, checker, or verifier error it addresses.
- Feed exact build errors and local goal state into the next repair.
- Do not change variables, hypotheses, definitions, domains, or conclusion to make the proof easier.
- If the loop exhausts its budget, report `GAP`, `PARTIAL`, or `FAILED_ATTEMPT` with the best current sketch and failure class.

Lean loop report:

```text
Status:
Frozen theorem:
Lean file:
Iterations:
Latest failure class:
Current compiler status:
SafeVerify status:
Next repair:
```

### SafeVerify Rules

Lean compiler success is necessary but not sufficient. Before reporting Lean success, enforce:

- no `sorry`, `admit`, `axiom`, `constant`, `opaque`, `unsafe`, or equivalent escape hatch,
- theorem target is unchanged from the frozen signature,
- theorem is not weakened to `True`, `Nonempty`, a toy proposition, or an easier domain,
- definitions are not changed to make the theorem trivial,
- no fake bridge lemmas, comments-as-proof, or postulated paper results,
- every helper theorem used by name is imported, locally proved, or explicitly part of the allowed context,
- no hidden extra assumptions appear in helper lemmas or theorem binders.

If SafeVerify fails, classify the failure as `forbidden_escape`, `target_drift`, `vacuous_proof`, `unknown_identifier`, or `missing_hypothesis` as appropriate and repair before retrying.

### Repair Memory Discipline

Record failed formal attempts as reusable evidence.

Template:

```text
Attempt id:
Artifact path:
Failure class:
Diagnostic excerpt:
Repair attempted:
Outcome:
Reusable lesson:
```

Rules:

- Preserve exact compiler/verifier diagnostics when available.
- Record the repair that was attempted, not just the final result.
- If a repair succeeds, record which failure class it fixed.
- If a repair fails, record whether it repeated the same failure or produced a new one.
- Do not discard failed sketches that reveal a false lemma, missing precondition, or unavailable external theorem.

### Goal Cache Protocol

Use cached subgoals or proof snippets only when their context matches.

Cache entry:

```text
Goal:
Normalized context:
Successful tactic/proof step:
Required premises:
Source sketch:
Failure count:
Success count:
```

Rules:

- Check for a matching cached goal before inventing a new tactic or helper lemma.
- Verify that hypotheses, domains, coercions, and target shape match before reuse.
- Record successful tactics, proof snippets, or WIT steps with their required premises.
- If a cached route fails, record the failure class and do not retry it unchanged.

### Stop Conditions

Stop the repair loop and report honestly when:

- the same failure class repeats three times without reducing the obligation,
- every attempted repair requires changing the frozen theorem target,
- a required external theorem is unavailable or unformalized within budget,
- all active sketches depend on the same unresolved bridge,
- SafeVerify repeatedly rejects the only building candidates,
- the configured iteration or user budget is exhausted.

Blocked output template:

```text
Status: GAP | FAILED_ATTEMPT | PARTIAL
Target:
Best sketch:
Where it failed:
Failure class:
What was tried:
Why it did not close:
Reusable lesson:
Next useful mutation:
```

### Proof Sketch Repair

When repairing a partial proof sketch, keep the sketch lineage explicit:

```text
Sketch id:
Parent sketch:
Target theorem:
Current artifact:
Solved pieces:
Remaining goals:
Compiler/verifier status:
Failure class:
Repair mutation:
Outcome:
Status: PARTIAL | CONDITIONAL | GAP | FAILED_ATTEMPT | UNVERIFIED
```

Rules:

- A proof sketch is not a verified proof.
- Mutate one repair dimension at a time where possible.
- Mark `FAILED_ATTEMPT` when a route is shown not to work as stated.
- Mark `GAP` when the route may still work but has an unresolved bridge.
- Mark `PARTIAL` when the sketch proves a useful subgoal or special case without closing the original target.
- Return to Explorer if the repair requires new theorem search, a different lemma plan, or a counterexample hunt.

## Optional Lean Formalization

Ask before Lean unless the user explicitly requested it.

If Lean is requested:

1. Use the `.wit` theorem target; do not weaken it.
2. Translate definitions and hypotheses faithfully.
3. Use actual Mathlib theorem names or prove helpers locally.
4. Do not introduce `sorry`, `admit`, `axiom`, `constant`, `opaque`, fake bridge lemmas, or comments-as-proof.
5. Run Lean Compiler Loop Mode.
6. Apply SafeVerify Rules after every building candidate.
7. Feed exact build errors into the repair loop.
8. Return Lean code only after the build succeeds and SafeVerify passes.

Lean status is separate:

- `Lean VERIFIED`: `lake build` passed and no forbidden placeholders exist.
- `Lean FAILED`: the repair loop could not produce building Lean; say `Lean code generation failed`.

If running from a normal Gecko/local directory where sandbox execution is unavailable, use a deep-run/sandbox-capable environment or report that Lean build could not be run here. Do not claim Lean verification without `lake build`.

## Optional Harness

Use the harness only when configured and appropriate:

```bash
export GEMINI_API_KEY=...
export WITSOC_HARNESS_INTERACTIVE_LEAN=1
cd witsoc
harness/env/bin/uvicorn harness.main:app --reload
```

Then POST to `/prove` with `problem_statement`, `max_wit_iterations`, and `max_lean_iterations`.

The harness can run informal proof planning, WIT generation, deterministic WIT checking, WIT semantic LLM review, Lean formalization, Lake build, contract checks, and Lean semantic review. Harness WIT semantic acceptance may be advisory depending on configuration; do not conflate it with a `.wit.receipt.json`.

## Reporting Template

```text
Status:
WIT file:
Structural check:
Audit:
Verifier context:
Receipt:
Rejected/GAP labels:
Lean requested:
Lean status:
Proof idea:
Next action:
```

For stopped or blocked formalization:

```text
Status: GAP | FAILED_ATTEMPT | PARTIAL
Target:
Best sketch:
Where it failed:
Failure class:
What was tried:
Why it did not close:
Reusable lesson:
Next useful mutation:
```

Use precise language:

- “structurally valid” means check passed.
- “verifier contexts generated” means `wit verify` ran.
- “semantically accepted” means verifier verdicts accepted the obligations.
- “VERIFIED” requires complete accepted receipt discipline.

## Micro-Examples

Vague `BY`:

```wit
-- Bad
[4] HAVE x > 0.
    BY obvious.

-- Good
[4] HAVE x > 0.
    BY [1] and the hypothesis that x is a positive real.
```

Missing theorem precondition:

```wit
-- Bad
[6] HAVE f attains a maximum on K.
    BY extreme value theorem.

-- Good
[6] HAVE K is compact and f is continuous on K.
    BY [2], [5].
[7] HAVE f attains a maximum on K.
    BY [6] and the extreme value theorem.
```

Missing citation:

```wit
-- Bad
[3] HAVE every finite tree has a leaf.
    BY standard.

-- Good
[3] CITE finite-tree leaf theorem: every finite tree with at least two vertices has at least two leaves.
[4] HAVE T has a leaf.
    BY [1], [2], [3].
```
