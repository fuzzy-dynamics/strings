---
name: witsoc-generator
description: Internal Witsoc proof-artifact generation subskill. Use inside the Witsoc subsystem to create, repair, structurally check, verifier-context-build, receipt-track, and optionally Lean-formalize `.wit` proof artifacts for mathematics and rigorous arguments. Use for WIT proofs, disproofs, formalizations, audits, reductions, algorithm correctness proofs, rejected-step repair, and Lean-adjacent proof artifacts. `wit check` is structural only; `wit verify` builds contexts only; semantic acceptance requires external verifier verdicts and a receipt; Lean output must pass `lake build`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Generator

Witsoc Generator is the artifact engine inside Witsoc. It converts an Explorer-accepted handoff into a `.wit` proof artifact with explicit labels, dependencies, structural checking, verifier contexts, receipts, and optional Lean formalization.

The generator is not a chat-proof mode and not a mathematical truth arbiter. If this subskill is used, create or update a `.wit` artifact unless the user only asks to inspect existing WIT files. For nontrivial new proof tasks, require an Explorer handoff before writing the WIT. For open/unsolved/unconfirmed targets, require that Explorer has accepted Lovasz's verification result for the narrow artifact target.

Generator is a specialist tool, not a strategy owner. It may report artifact
quality, repair options, verifier receipts, blocked labels, and route-back
recommendations. The orchestrator decides whether to retry locally, ask
Explorer for a new plan, send a mathematical barrier to Lovasz, spawn another
formalizer, or stop.

## Codex/Claude Contract

Generator is the artifact engine for Codex/Claude-style runs. It starts from an
accepted Explorer handoff, preserves the frozen target, creates or repairs
WIT/Lean artifacts, runs checks where available, and reports exact artifact
status. The orchestrator remains in charge of strategy and final reporting.
Generator should make artifact tradeoffs visible without treating its preferred
repair path as mandatory.

Preferred commands:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py llm-contract
python3 ~/.openscientist/skills/witsoc/witsoc.py generator obligations runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py generator packet runs/<task>
python3 ~/.openscientist/skills/witsoc/witsoc.py spawn-template generator --target "<problem>"
```

If the runtime is missing, repair it with:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

Do not start new nontrivial artifacts without Explorer handoff. Do not silently
mutate targets. `wit check` is structural only; verification needs receipts or
formal evidence plus SafeVerify.

Shared protocols live in the parent skill:

- `../references/core/status.md`
- `../references/core/llm_contract.md`
- `../references/core/handoff.md`
- `../references/core/failure_recovery.md`
- `../references/core/repair.md`
- `../references/core/goal_cache.md`
- `../references/core/safeverify.md`
- `../references/core/lean_verification.md`
- `../references/core/tooling.md`
- `../references/schemas/handoff.schema.json`
- `references/algorithmic_generator.md`: advisory algorithms for artifact quality, repair ranking, and Generator decision packets.

If the user explicitly asks for WIT code, `.wit`, or WIT plus Lean, WIT generation is mandatory. Do not return only a plan, prose proof, verifier discussion, or Lean formalization. The generator must either write a `.wit` artifact or report a concrete blocker with status `GAP`, `FAILED_ATTEMPT`, or `REJECTED`.

## Mandatory Verifier Loop

Generator's default behavior is a local repair loop, not one-shot artifact
writing:

```text
write/update WIT -> lint WIT -> wit check -> isolate failed label -> repair locally -> retry -> build verifier context -> attempt receipt/Lean when available -> packet/report
```

For every serious Generator pass, produce or update:

```text
proofs/<task>.wit
proofs/<task>.soc
runs/<task>/generator_obligation_graph.json
runs/<task>/generator_decision_packet.json
reports/witsoc_status.md
reports/witsoc_preview.md
reports/report.md
```

If a `.wit` artifact cannot be produced, write `proofs/<task>_blocker.md` with
the frozen target, exact failed method, missing premise, failed label if any,
and the route back to Explorer or Lovasz. Then refresh the top-level packet:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py generator obligations runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py generator packet runs/<task> --out runs/<task>/generator_decision_packet.json
python3 ~/.openscientist/skills/witsoc/witsoc.py next-action runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py proof-workflow runs/<task> --write
python3 ~/.openscientist/skills/witsoc/witsoc.py ui-summary runs/<task> --write
```

`generator_obligation_graph.json` is the Generator's algorithmic control
artifact. It must list proof obligations, dependencies, missing premises,
repair blockers, and the next obligation to attack. Treat it as a map for
artifact work, not as a restriction on the orchestrator's strategy.

If generation, structural checking, verifier review, or Lean formalization fails for a serious problem, the generator must not end the run after the first blocked method. Preserve the failure and hand it back to top-level Witsoc/Explorer for alternate-method agents unless worker spawning is unavailable.

Generator may not upgrade claim status. It can report that a WIT structural check passed, verifier context was built, a receipt was accepted, or Lean passed, but Explorer/top-level Witsoc owns the final status assignment for the mathematical target. If WIT or Lean fails, report the exact failure to Explorer; Explorer decides whether this is a Generator repair, an Explorer proof-plan issue, or a Lovasz mathematical barrier.

## Non-Negotiable Semantics

Use `../references/core/status.md`. In short: `wit check` is structural only, `wit verify` builds verifier contexts only, `wit receipt` records external verdicts, and `VERIFIED` requires complete accepted receipt discipline.

For open problems, never let a partial artifact imply that the original problem is solved. The artifact title, status, theorem statement, and report must all distinguish the original open problem from the narrower result being recorded.

## Inputs

Generator can start from:

- an explicit request for WIT code or WIT plus Lean,
- an existing `.wit` file,
- a Witsoc Explorer handoff,
- a rejected verifier context,
- a Lean/formalization target,
- an algorithm or reduction specification,
- an open-problem handoff for a partial result, conditional theorem, counterexample, obstruction, computation, conjecture, or failed attempt.

For nontrivial theorem/problem targets, even if the user explicitly requests WIT/Lean, Explorer must freeze and accept the target before Generator executes. Existing `.wit` inspection or local artifact repair may start directly at Generator.

If the target is ambiguous, pin an interpretation before writing the artifact. If the ambiguity materially affects truth, ask or state the chosen interpretation.

## Reference Files

Load only as needed:

- `../references/wit.md`: full `.wit` syntax and scoping reference.
- `../references/soc.md`: `.soc` persistent memory format.
- `../references/core/handoff.md`: structured `handoff.json` state-machine contract.
- `../references/core/tooling.md`: deterministic tool/API discipline.
- `../references/core/safeverify.md`: target-freezing and anti-cheating checks.
- `../references/core/lean_verification.md`: Lean LSP/REPL/cache-aware loop.
- `../references/schemas/handoff.schema.json`: Explorer-to-Generator handoff schema.
- `../references/schemas/witsoc-handoff-schema.json`: strict Generator blueprint schema.
- `../references/examples/handoff_solved_problem.json`: solved-problem handoff example.
- `../references/examples/handoff_open_problem.json`: open-problem handoff example.
- `../references/examples/handoff_v1_blueprint.json`: strict Generator blueprint example.
- `../scripts/validate_handoff.py`: deterministic handoff validator.
- `../references/examples/composite_block.wit`: compact theorem example.
- `../references/examples/grover_constant.wit`: nested case-analysis example.
- `../references/examples/sat_reduction.wit`: reduction example.

If unsure about WIT syntax, read `../references/wit.md` before editing.

## Script Surface

Prefer explicit API tools such as `run_wit_check`, `run_wit_cycle`, and `run_target_freeze_check` when the environment provides them. If no typed tool exists, use deterministic scripts or native `wit` CLI.

Resolve scripts through Plane so global and space skill overrides work. Do not
assume skills have been materialized under `$KIMI_WORK_DIR`.

```bash
"$PLANE_TOOL_BIN" skill-run witsoc/scripts/check.sh path/to/file.wit
"$PLANE_TOOL_BIN" skill-run witsoc/scripts/cycle.sh path/to/file.wit
VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_handoff.py)"
python3 "$VALIDATOR" runs/<task>/handoff.json
```

Use `skill-run` for shell scripts. Use `skill-which` plus `python3` for
`validate_handoff.py`. Treat these scripts as a compatibility layer;
`../references/core/tooling.md` defines the long-term typed CLI/API target.

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
| `validate_handoff.py <handoff.json>` | Validate the handoff, including Lovasz proof-DAG, worker evidence, and assembly invariants. |

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

Every final response after generator work must include this compact artifact
block:

```text
Artifacts:
- WIT: <path|none>
- Lean: <path|none>
- Receipt: <path|none>
- Status: STRUCTURE_OK=<yes/no/not run>; CONTEXT_BUILT=<yes/no/not run>; RECEIPT_ACCEPTED=<yes/no/not run>; LEAN_VERIFIED=<yes/no/not run>
- Plugin: <opened/open failed/not attempted>
```

The status label must be inherited from the accepted handoff or mechanically justified by checks/receipts. Do not upgrade a `CONJECTURE`, `PARTIAL`, `PROVED_SKETCH`, or `CHECKED` handoff to `VERIFIED` unless complete formal/verifier evidence exists and SafeVerify passes.

When an artifact or Lean translation fails, also write a failure note beside the artifact, for example `runs/<task>/approach_N_failure.md`, containing:

- frozen theorem target,
- failed method,
- failed artifact path,
- exact `wit check`, verifier, or Lean diagnostic,
- rejected step or missing premise,
- repair attempts already made,
- methods that the next agents must avoid,
- two suggested alternate method families.

Return that failure note to Explorer. Explorer decides whether to send the unchanged target back to Generator for repair or to Lovasz for a new barrier attack.

A good `.wit` file:

- starts with a valid proof header status: `-- Status: UNVERIFIED`, `-- Status: GAP`, `-- Status: REJECTED`, or `-- Status: VERIFIED` when a receipt says so,
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
2. If nontrivial, get or create an Explorer handoff. If the target is open/unsolved/unconfirmed/frontier-level/blocked, require an Explorer-reviewed Lovasz result.
3. Run `../scripts/validate_generator_handoff.py` on `handoff_v1.json`, with route-state input when available, before writing new artifacts.
4. Create or enter a session-scoped proof worktree for this exact artifact target. Do not generate the WIT or Lean proof in the coordinator root, a previous proof target's worktree, or an unrelated Lean project.
5. Write a `.wit` artifact inside that proof worktree, then preserve a copy in the run artifact directory and register it in `witsoc_artifacts.json`.
6. Activate the Witsoc plugin iframe and open the generated `.wit` file.
7. Run structural check and `../scripts/lint_wit_quality.py` when tools are available.
8. Build verifier context when tools are available; generated context logs must be registered as artifacts.
9. If Lean is requested, generate Lean from the WIT target after WIT exists, in the same session-scoped proof worktree for that artifact target, then register `.lean` and Lake logs.
10. If Lean was not already requested and the WIT structural check passes, ask the user whether to generate a Lean 4 proof from this WIT proof and verify it with `lake build`.
11. Record `target_fidelity`, `skeptic_review_id`, `wit_target_sha256`, `lean_target_sha256`, and `frozen_target_sha256` for the generated artifact. If the artifact is final synthesis output, require `final_synthesis_audit` from Explorer/Lovasz before generation.
12. Write or update `generator_artifacts.json` with `../scripts/generator_manifest.py`; target-hash drift is a hard failure.
13. Final response includes proof worktree path/status, `.wit` path or inline WIT code, plugin activation status, structural check status, WIT lint status, Lean status, target-fidelity status, skeptic-review id, artifact registry path, generator manifest path, and hash-provenance status.

Proof worktree rule:

- Each WIT/Lean proof target gets its own worktree named from the session id and proof id, for example `witsoc-proof-${OSCI_SESSION_ID}-${proof_id}`.
- If the Plane orchestrator is spawning a generator worker, it should pass that path with `launch-worker --worktree <path>`.
- If Generator is already running inside a worker, it must still create a nested proof worktree or explicitly record that the worker worktree is dedicated to this single proof target.
- Never reuse another proof target's worktree for a different WIT/Lean proof.
- Record `session_id`, `proof_id`, `proof_worktree`, `proof_worktree_dedicated`, and `worktree_status` in the handoff, worker result, or final report.
- Record WIT/Lean target hashes and frozen target hash. A Lean proof cannot be reported as `VERIFIED` unless the Lean target hash matches the WIT target hash and the frozen target hash.

Generator-worker cleanup requirement:

- If a temporary private Lean project or proof worktree is created, delete it after the worker finishes, whether verification succeeds or fails, unless the coordinator explicitly marks it preserved for inspection.
- Preserve `.wit` artifacts, Lean source snippets, logs, receipts, SafeVerify records, and reports outside the deleted project.
- If using a shared Lean project, do not delete it unless the Lovasz/coordinator handoff says this worker is the last active user.
- Report cleanup status in the worker result.

Forbidden behavior for explicit WIT requests:

- stopping after exploration only,
- returning only a natural-language proof,
- returning only Lean,
- saying WIT “could be generated” without generating it,
- treating a proof sketch as the requested WIT artifact.

Plugin activation command after writing any `.wit` artifact:

The Witsoc UI plugin is external to the strings repo. On a fresh system,
install it from the verified plugin index before opening the iframe. Plugin
installation requires `oras`, `cosign`, and `tar` on the host.

```bash
"$PLANE_TOOL_BIN" plugins available
"$PLANE_TOOL_BIN" plugins list
# If witsoc is not listed locally:
"$PLANE_TOOL_BIN" plugins install witsoc
```

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

For nontrivial problems, start from `runs/<task>/handoff.json` conforming to `../references/schemas/handoff.schema.json`. It must contain the problem profile, source citations, solved-problem map if relevant, ontology map, ranked and rejected theorem candidates, search budget, proof compression record, backward chains, falsification results, obstructions, barrier map, open-product target for open problems, conjectures, proof objects, frozen target, artifact target, selected sketch, lemma arrays with economics, obligation graph, external facts with verification records, theorem preconditions, mutation tracker, known gaps, counterexamples checked, target-freeze hashes, and formalization notes. Do not substitute broad theorem search inside Generator for this handoff; return to Explorer when a repair needs new lemmas or premises.

For WIT generation, execute only `runs/<task>/handoff_v1.json`. Treat `handoff.json` as context, not as executable proof instructions. If local execution is available, run:

```bash
VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_handoff.py)"
GENERATOR_VALIDATOR="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_generator_handoff.py)"
python3 "$VALIDATOR" runs/<task>/handoff.json
python3 "$VALIDATOR" runs/<task>/handoff_v1.json
python3 "$GENERATOR_VALIDATOR" runs/<task>/handoff_v1.json --route-state "$PLANE_SESSION_DIR/witsoc_route_state.json" --manifest-out runs/<task>/generator_handoff_validation.json
```

If validation fails, return to Explorer with the exact validation errors. Do not invent new helper lemmas unless a structural check explicitly fails. Do not cite any theorem outside `external_dependencies`.

After writing WIT, run:

```bash
LINTER="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lint_wit_quality.py)"
MANIFEST="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/generator_manifest.py)"
python3 "$LINTER" path/to/artifact.wit --json > path/to/artifact.wit.lint.json
python3 "$MANIFEST" --manifest runs/<task>/generator_artifacts.json --artifact path/to/artifact.wit --type wit --target-hash "$FROZEN_TARGET_SHA256" --route-state "$PLANE_SESSION_DIR/witsoc_route_state.json" --proof-worktree "$WITSOC_PROOF_WORKTREE"
```

For open-problem handoffs, require a narrower artifact target before writing WIT: special case, bound, conditional theorem, reduction, obstruction, counterexample, computation, failed attempt, conjecture, or lemma.

If the handoff asks for a full solution to a known open problem without adversarial exploration and a precise proof path, return to Explorer instead of writing a proof artifact.

For finite/infinite graph-theory reductions, prefer the checked WIT templates under `../references/examples/` instead of creating a prose reduction from scratch:

- `compactness_disjoint_union_reduction.wit`
- `finite_chi_bounding_compactness_template.wit`

These templates are reduction skeletons only. Preserve `-- Template: true` and keep the WIT header `UNVERIFIED` until the exact frozen target, external compactness theorem, and all side conditions are instantiated and checked.

### 1. Freeze The Target

Record:

```text
Name:
Kind: theorem | lemma | disproof | reduction | algorithm correctness | audit
Original open problem, if any:
WIT header status: UNVERIFIED | VERIFIED | GAP | REJECTED
Research/result status: OPEN | PARTIAL | CONDITIONAL | CONJECTURE | FAILED_ATTEMPT | CHECKED | PROVED_SKETCH | VERIFIED | GAP | REJECTED
Variables and domains:
Hypotheses:
Definitions:
Conclusion:
External facts allowed:
```

Do not silently strengthen the theorem. Do not weaken the conclusion to make the proof easy. Record target-freeze hashes from `../references/core/safeverify.md` before writing or repairing artifacts.

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
MODULE [module_name]

THEOREM [module_name]:
  GIVEN:
    - [hyp_name]: hypotheses
  CLAIM:
    conclusion.

PROOF OF [module_name]:
  [1] ASSUME setup fact.
      BY [hyp_name].
  [2] HAVE intermediate claim.
      BY [1], @{named method or theorem}.
  [3] SHOW conclusion.
      BY [2], final assembly.
  QED BY [3].
```

Rules:

- Labels are sequential inside each scope.
- No forward, self, or cross-case references.
- Prefer bracketed structural references for local declarations, imported declarations, named hypotheses, and steps: `[lemma_name]`, `[alias.theorem]`, `[hyp_name]`, `[3]`.
- Use `@name` or `@{full citation text}` for external citations accepted as given.
- In a `CASE [n]`, cite the introduced case hypothesis as `[n.0]` inside that case.
- `CITE` may introduce an external theorem, but downstream use must still be checked through the CITE step's label.
- `GAP` is honest and preferable to handwaving; use `GAP EXPECTING [subproblem]` when the missing bridge is a named lemma or subproblem.
- Avoid `BY obvious`, `BY clearly`, `BY standard`, `BY Mathlib`, and bare `BY [n]` for nontrivial inferences.
- Legacy unbracketed declaration names still parse, but new artifacts should use the bracketed Language v2 target syntax.

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

- The `.wit` header should use only the proof-status labels from `../references/wit.md`: `UNVERIFIED`, `VERIFIED`, `GAP`, or `REJECTED`.
- Put open-problem classifications such as `OPEN`, `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, or `FAILED_ATTEMPT` in the handoff, report fields, comments, or adjacent notes rather than in the WIT `-- Status:` header.
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

Use typed API tools when available. Preferred order:

```text
run_wit_check -> run_wit_audit -> run_wit_context or run_wit_verify -> run_wit_status -> run_target_freeze_check
```

When typed tools are unavailable, use scripts:

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

Use `../references/core/repair.md`. Before editing after WIT verifier rejection, structural failure, Lean/LSP/REPL/compiler failure, or SafeVerify rejection, produce a structured repair diagnosis and preserve it in the run state.

For Lean failures, preserve the frozen theorem target. A repair may change proof terms, tactics, helper lemmas, imports when allowed, or decomposition, but it must not silently change variables, hypotheses, definitions, or conclusion.

### Lean Compiler Loop Mode

Use this mode when the user requests Lean, a formal proof, or repair of a Lean build failure.

Use `../references/core/lean_verification.md`. Prefer Lean LSP, REPL, `repl`, `minictx`, or per-file checking for repair iterations. Run full `lake build` for final confirmation or dependency-sensitive changes, not every minor tactic edit.

Before the loop, handle dependency cache setup once when needed, for example `lake exe cache get`. Avoid import changes unless the diagnostic requires them and record why the cache-invalidating change is necessary.

When a linear Lean tactic repair stalls, run a single-ply parallel tactic scan instead of repeating the same tactic path:

```bash
TACTIC_SCAN="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lean_tactic_scan.py)"
python3 "$TACTIC_SCAN" --file runs/<task>/frozen_lean_target.lean
```

Configure the Lean REPL/checker with `WITSOC_LEAN_REPL_CMD` or pass `--repl-cmd`. The scan tries single distinct tactics such as `intro`, `cases`, `simp`, `ring`, and `induction`, scores resulting states by goal count and diagnostic reduction, prunes dead ends, and returns the top three branches. This is a one-step breadth scan, not a multi-step tree search. Treat its output as search guidance only; final success still requires a normal Lean checker pass plus SafeVerify.

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

Use `../references/core/safeverify.md`. Lean compiler success is necessary but not sufficient. Before semantic review or final success, run target-freeze diff/hash checks for the original source text, canonical target, `GIVEN`, `CLAIM`, and definitions. SafeVerify failures are `REJECTED` until repaired.

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

Use `../references/core/goal_cache.md`. Reuse cached subgoals or proof snippets only when their context matches.

### Stop Conditions

Use `../references/core/failure_recovery.md` for stop conditions and blocked output.

### Proof Sketch Repair

When repairing a partial proof sketch, update the matching `sketches[*]` object in `handoff.json`: preserve `sketch_id`, `parent_sketch_id`, target theorem, solved pieces, remaining goals, failure class, repair mutation in `next_mutation`, status, and EV fields.

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
5. Use Lean LSP/REPL/per-file feedback during repair where available.
6. Run final `lake build`.
7. Apply SafeVerify target-freeze checks after every building candidate.
8. Feed exact local goal/checker errors into the repair loop.
9. Return Lean code only after final build succeeds and SafeVerify passes.

Lean status is separate:

- `Lean VERIFIED`: final `lake build` passed, target-freeze checks passed, and no forbidden placeholders exist.
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
    BY [1], [x_positive].
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
    BY [6], @extreme_value_theorem.
```

Missing citation:

```wit
-- Bad
[3] HAVE every finite tree has a leaf.
    BY standard.

-- Good
[3] CITE @{finite-tree leaf theorem}: every finite tree with at least two vertices has at least two leaves.
    BY @{standard graph theory}.
[4] HAVE T has a leaf.
    BY [1], [2], [3].
```
