---
name: witsoc
description: Hard-math and proof workflow for OpenScientist. Use whenever the user asks to prove, disprove, solve, formalize, verify, critique, repair, or find gaps in a mathematical/theoretical claim, proof, reduction, algorithm invariant, correctness argument, or rigorous derivation. Covers olympiad and Putnam problems, research conjectures, paper-proof formalization, Lean/Coq-adjacent planning, complexity reductions, algorithms, algebra, analysis, topology, number theory, combinatorics, graph theory, geometry, probability, logic, and scientific arguments whose correctness depends on chained premises. Every Witsoc use must create or update a `.wit` semi-formal proof artifact. After the WIT artifact exists, ask the user whether the agent should generate Lean 4 code based on the WIT proof. If the user says yes, the Lean code must be verified in the `math` sandbox with `lake build`; on every build error, feed the exact error back into the Lean-generation/repair loop and rebuild until it succeeds or the loop is genuinely blocked. Return Lean code only after `lake build` succeeds. If Lean cannot be corrected, report exactly that Lean code generation failed. A plain chat proof is not sufficient for explicit Witsoc requests.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc

Witsoc is OpenScientist's hard-math proof workflow. It sits between informal math and full proof assistants: agents write natural mathematical language, but in a strict `.wit` structure where each step has an explicit label and cited dependencies. The checker validates syntax, labels, scoping, imports, and references. Semantic verification is performed by a skeptical LLM/verifier reading isolated contexts generated from those cited dependencies.

If the user says "use witsoc", a chat proof is not enough. Produce a `.wit` artifact. After the WIT proof is available, ask whether to generate Lean 4 code from it.

## What Witsoc Can Actually Do

Witsoc has three layers:

- **Wit language:** `.wit` files with `MODULE`, claims, proofs, reductions, algorithms, labeled steps, `BY` justifications, `CITE`, `GAP`, `IMPORT`, `EXPORT`, and receipts.
- **Soc memory:** `.soc` files for long solve loops, recording approaches, insights, queues, and progress.
- **Optional Lean verification:** a WIT -> Lean 4 translation checked in the `math` sandbox with `lake build`, run only after the user agrees to generate Lean code.

Default Witsoc verification does **not** prove semantics by itself. `wit verify` builds verifier contexts. A separate verifier agent/LLM must issue verdict lines, then `wit receipt` records them.

## Default Deliverable

For every Witsoc task, deliver:

1. `.wit` proof artifact.
2. Structural result from `check.sh` or `wit check`.
3. Verifier context from `verify.sh`, `context.sh`, or `cycle.sh`.
4. Status:
   - `VERIFIED`: structural check passed and receipt has all `ACCEPT`.
   - `UNVERIFIED`: structurally valid, verifier contexts generated, no accepted receipt yet.
   - `GAP`: an unresolved proof obligation is explicitly present.
   - `REJECTED`: structural check failed or a verifier rejected a step.
5. Ask the user whether to generate Lean 4 code from the `.wit` proof.
6. If the user agrees, Lean 4 code generated from the `.wit` proof, but only if `lake build` passed in the `math` sandbox.
7. If Lean generation was requested, Lean status:
   - `Lean VERIFIED`: `lake build` passed and the file contains no forbidden placeholders.
   - `Lean FAILED`: Lean generation or repair could not produce code that builds; say `Lean code generation failed`.

Never call a proof `VERIFIED` from structural checking alone.

## Reference Files

Load only what you need:

- `references/wit.md`: full `.wit` syntax and scoping reference.
- `references/soc.md`: `.soc` persistent memory format.
- `references/examples/composite_block.wit`: compact theorem example.
- `references/examples/grover_constant.wit`: nested case-analysis example.

If writing a `.wit` file and you are unsure about syntax, read `references/wit.md` first.

## Workflow

### 1. Pin the Target

Write down the exact statement before proving:

- variables and domains,
- hypotheses,
- definitions,
- conclusion,
- whether the task is proof, disproof, formalization, audit, reduction, or algorithm correctness.

Do not silently strengthen the theorem. If ambiguous, state the interpretation.

### 2. Explore with Soc Discipline

For hard problems, scout before formalizing:

- generate 2-4 approaches,
- test small examples and likely counterexamples,
- identify known theorems and their hypotheses,
- split the claim into lemmas,
- record failed paths and useful insights in `runs/<problem>/notes.md` or a `.soc` file.

Soc may speculate; Wit may not. Exploration notes are not proof artifacts.

### 3. Write `.wit`

Use this shape:

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

- Every top-level proof has final `QED BY ...`.
- Every `CASE` has matching `[n] QED BY ...`.
- Labels are sequential inside each scope.
- No forward, self, or cross-case references.
- `BY` cites local labels, import refs (`alias.theorem`), named methods, exact theorem names, or citations.
- Use `CITE` for external results; verifier accepts the cited claim as given but downstream use must still be valid.
- Use `GAP` instead of unsupported bridges.
- For reductions, use `REDUCTION`, `FROM`, `TO`, `PRESERVING`, then `PROOF OF`.
- For algorithms, state `REQUIRES`, `ENSURES`, invariants, termination, and complexity separately; put correctness in a theorem proof.

Avoid Lean syntax inside `.wit`: no `P : Prop`, `theorem ... := by`, tactics, `import Mathlib`, or proof terms as `BY` justifications. Cite Mathlib facts as external theorem names in `BY`, not as WIT imports.

### 4. Check and Build Verifier Contexts

Prefer the skill scripts:

```bash
SCRIPTS=${KIMI_WORK_DIR}/.openscientist/skills/witsoc/scripts
bash "$SCRIPTS/check.sh" path/to/file.wit
bash "$SCRIPTS/audit.sh" path/to/file.wit
bash "$SCRIPTS/verify.sh" path/to/file.wit --out path/to/file.verify.txt
```

or one command:

```bash
bash "$SCRIPTS/cycle.sh" path/to/file.wit
```

Fallback to native CLI:

```bash
wit check path/to/file.wit
wit verify path/to/file.wit --step 3
wit verify path/to/file.wit
wit context path/to/file.wit
```

`wit check` proves only structural validity. `wit verify` prints contexts for verifier review.

### 5. Verify Semantics

Ask a separate skeptical verifier to judge each generated context. The verifier must default to reject unless the step follows from cited premises.

Verdict format required by `receipt.sh` / `wit receipt`:

```text
[1] ACCEPT: reason
[2] REJECT: reason
[3.1] GAP: reason
```

Then persist the result:

```bash
bash "$SCRIPTS/receipt.sh" path/to/file.wit --from verifier-output.txt
bash "$SCRIPTS/status.sh" path/to/file.wit
```

or:

```bash
cat verifier-output.txt | wit receipt path/to/file.wit
```

The receipt updates `-- Status:` to `VERIFIED` only if all parsed verdicts are `ACCEPT`; any `REJECT` or `GAP` becomes machine status `REJECTED`. In user-facing reporting, call an explicit unresolved obligation `GAP`.

### 6. Repair

For rejected steps:

- split into Lamport substeps,
- cite missing premises,
- add missing hypotheses if legitimate,
- weaken false claims,
- replace vague citations,
- prove a helper lemma,
- or mark `GAP`.

Do not resubmit the same proof with cosmetic changes. Each iteration must reduce a real obligation.

### 7. Ask Before Lean 4 Formalization

After `check.sh`/`wit check` reports a structurally valid `.wit` file, ask the user whether the agent should generate Lean 4 code based on the WIT proof. Do not start Lean formalization unless the user says yes or the original user request already explicitly asked for Lean output.

If the user says yes:

1. Read the `.wit`, verifier context, and any accepted receipt.
2. Translate the same theorem target into Lean 4; do not weaken the statement.
3. Create a Lean/Lake project or use the existing one under the run directory.
4. Put the generated theorem in a Lean file, usually `Main.lean` or `Output/Basic.lean`.
5. Run `lake build` inside the `math` sandbox.
6. If `lake build` fails, copy the exact Lean/Lake error into the next repair prompt or internal repair notes, correct the Lean code, and rebuild.
7. Repeat the error-feedback repair loop until `lake build` succeeds or correction is genuinely blocked.
8. Return Lean code to the user only after `lake build` succeeds. If correction is blocked, do not return non-building Lean as a result; say `Lean code generation failed` and include the final build error summary.

Lean proof requirements:

- No `sorry`, `admit`, `axiom`, `constant`, `opaque`, unsafe escape hatches, fake bridge lemmas, or comments-as-proof.
- No vacuous theorem weakening such as proving `True`, changing the domain, or replacing the target with an easier proposition.
- Prefer Mathlib theorem names and tactics when they exactly apply.
- Prove local helper lemmas when Mathlib lacks the needed fact.
- Keep theorem assumptions and conclusion faithful to the `.wit` theorem.
- If the `.wit` proof used `CITE`, either use an actually available Lean/Mathlib theorem or prove the needed helper locally; do not postulate it.

Use `sandbox-use` for Lean commands:

```bash
"$PLANE_TOOL_BIN" skill-view sandbox-use/SKILL.md
"$PLANE_TOOL_BIN" skill-run sandbox-use/scripts/activate.sh math --mount "$PWD"
"$PLANE_TOOL_BIN" skill-run sandbox-use/scripts/exec.sh --sandbox math -- lake build
```

If the current directory is already under `~/.openscientist`, the extra `--mount "$PWD"` is optional. If `exec.sh` exits 126, activate again with `--mount "$PWD"` and retry.

Report Lean status separately from WIT status:

- `Lean VERIFIED`: `lake build` passed with no forbidden placeholders.
- `Lean FAILED`: build failed after the repair loop, or correction would require weakening/postulating the theorem.

## Agent-Callable Scripts

Scripts live at `${KIMI_WORK_DIR}/.openscientist/skills/witsoc/scripts/`; invoke with `bash <path>` because executable bits may not survive sync.

| Script | Purpose |
|---|---|
| `init.sh --name N --claim X [--given H] [--out file.wit]` | Create a `.wit` skeleton; refuses overwrite. |
| `check.sh <file.wit|dir> [...]` | Run structural validation. |
| `audit.sh <file.wit>` | Static audit for `GAP`, `CITE`, vague `BY`, and receipt issues. |
| `context.sh <file.wit> [--step N] [--out path]` | Build raw isolated verifier context. |
| `verify.sh <file.wit> [--step N] [--out path]` | Structural gate + verifier-context output. Does not call an LLM. |
| `cycle.sh <file.wit> [--out-dir dir]` | Run check, audit, verify context, and status; writes `<name>.verify.txt`. |
| `receipt.sh <file.wit> --from verifier.txt` | Parse verdicts, write `.wit.receipt.json`, update status. |
| `status.sh <file.wit>` | Summarize status, receipt, and structural result. |

All scripts emit JSON on stdout.

## Optional Lean Harness

Use the harness only when the environment is configured and the user agreed to Lean generation:

```bash
export GEMINI_API_KEY=...
export GEMINI_MODEL=gemini-3.1-pro-preview   # optional
export WITSOC_HARNESS_INTERACTIVE_LEAN=1     # optional stronger Lean path
cd witsoc
harness/env/bin/uvicorn harness.main:app --reload
```

Then POST to `/prove` with `problem_statement`, `max_wit_iterations`, and `max_lean_iterations`. The harness runs informal proof planning, WIT generation, deterministic WIT checking, WIT semantic verifier, Lean formalization, Lake build, contract checks, and Lean semantic verification. It can fail from provider auth/quota/network, missing Lean/Lake, or recursion/verification loops. If it fails, fall back to the manual WIT -> Lean -> `lake build` loop above when possible.

## Quality Bar

A good Witsoc proof:

- states all variable domains and hidden assumptions,
- has one mathematical move per step,
- cites exact premises and methods,
- makes case splits explicit and closed,
- checks theorem preconditions before using named results,
- keeps final `SHOW` aligned with the theorem `CLAIM`,
- has structural check output and verifier context,
- has a receipt before being called `VERIFIED`.

Reject or repair:

- `BY clearly`, `BY obvious`, `BY standard argument`, `BY Mathlib`, or bare `BY [2]` for a nontrivial step,
- external theorem citations that are too vague to audit,
- examples used as universal proof,
- missing nonzero/positivity/compactness/measurability/finiteness assumptions,
- cross-case references,
- theorem target drift,
- Lean syntax disguised as WIT.

## Reporting

Report:

- status,
- `.wit` path,
- structural check result,
- verifier context path,
- receipt path if any,
- whether Lean generation was requested,
- Lean file path, if Lean generation was requested and succeeded,
- `lake build` result from the `math` sandbox, if Lean generation was requested,
- rejected labels or gaps,
- short proof idea.

Be precise: "structurally valid and verifier contexts generated" means `UNVERIFIED`, not `VERIFIED`.
Only include Lean code in the answer when Lean generation was requested and the reported Lean status is `Lean VERIFIED`. If Lean verification failed after repair, write `Lean code generation failed` instead of presenting the failed Lean code as an answer.
