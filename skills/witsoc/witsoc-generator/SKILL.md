---
name: witsoc-generator
description: Internal Witsoc proof-artifact generation subskill. Use inside the Witsoc subsystem to create, repair, structurally check, verifier-context-build, receipt-track, and optionally Lean-formalize `.wit` proof artifacts for mathematics and rigorous arguments. Use for WIT proofs, disproofs, formalizations, audits, reductions, algorithm correctness proofs, rejected-step repair, and Lean-adjacent proof artifacts. `wit check` is structural only; `wit verify` builds contexts only; semantic acceptance requires external verifier verdicts and a receipt; Lean output must pass `lake build`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Generator

Generator is the artifact engine: it converts an Explorer-accepted handoff
into a `.wit` artifact with labels, dependencies, structural checks, verifier
contexts, receipts, and optional Lean. It is not a truth arbiter: it never
upgrades claim status (Explorer/top-level own status), never invents
mathematics beyond the accepted handoff, and sends mathematical blockers back
to Explorer. Nontrivial new proofs require an Explorer handoff;
open/unsolved/unconfirmed targets additionally require an Explorer-reviewed
Lovasz result. Existing `.wit` inspection/repair may start here directly.

Non-negotiable semantics (`../references/core/status.md`): `wit check` =
structural only; `wit verify` = context building only; `wit receipt` records
external verdicts; `VERIFIED` requires complete accepted receipt discipline.
For open problems the artifact title, statement, status, and report must all
distinguish the narrow recorded result from the original open problem (which
stays `OPEN` in comments, with `GAP` for the unresolved bridge).

References: `../references/wit.md` (full syntax — read it when unsure),
`../references/soc.md`, core protocols under `../references/core/*`, schemas
and worked examples under `../references/schemas/*` and
`../references/examples/*` (including the compactness reduction WIT templates
— keep `-- Template: true` and `UNVERIFIED` until fully instantiated), and
`../references/core/generator_harness.md` (the optional uvicorn `/prove`
harness).

## Mandatory WIT triggers and required behavior

"Provide WIT code", "write a `.wit` proof", "WIT + Lean", "prove with WIT" —
WIT generation is mandatory; never satisfy these with exploration prose,
plan-only answers, or Lean alone. Required sequence:

1. Freeze the exact target (kind, hypotheses, definitions, conclusion,
   allowed external facts; target-freeze hashes per
   `../references/core/safeverify.md`). Never strengthen silently or weaken
   to make the proof easy.
2. For nontrivial targets, get or create the Explorer handoff; execute ONLY
   `handoff_v1.json` (treat `handoff.json` as context). Validate first:
   `../scripts/validate_handoff.py` on both files, then
   `../scripts/validate_generator_handoff.py` with route state. Validation
   failure returns to Explorer with the exact errors. Do not invent helper
   lemmas unless a structural check fails; cite nothing outside
   `external_dependencies`. A full-open-problem handoff without adversarial
   exploration goes back to Explorer unwritten.
3. Work in a session-scoped proof worktree per artifact target
   (`witsoc-proof-${OSCI_SESSION_ID}-${proof_id}`); never reuse another
   target's worktree; record `session_id`, `proof_worktree`,
   `worktree_status` in results; delete temporary projects after finishing,
   preserving WIT/Lean/logs/receipts outside.
4. Write the `.wit`, copy to the run artifact directory, register in
   `witsoc_artifacts.json`, open the Witsoc plugin iframe
   (`"$PLANE_TOOL_BIN" plugins iframe bash witsoc open <file>`; install via
   `plugins install witsoc` if absent — plugin failure is reported separately,
   never proof failure).
5. Run structural check + `../scripts/lint_wit_quality.py`; build verifier
   context; register logs.
6. Lean only from the WIT target (ask first unless requested); update
   `../scripts/generator_manifest.py` (target-hash drift is a hard failure);
   record `target_fidelity`, `skeptic_review_id`, and the three target hashes
   (`wit/lean/frozen` — all must match for VERIFIED). Final synthesis output
   requires `final_synthesis_audit` before generation.
7. Final response includes worktree path/status, `.wit` path (or inline code
   when explicitly requested), plugin status, check/lint/Lean statuses, and
   hash provenance.

## Script surface

Prefer typed API tools (`run_wit_check`, `run_wit_cycle`,
`run_target_freeze_check`) when available; otherwise resolve through Plane
(`"$PLANE_TOOL_BIN" skill-run witsoc/scripts/<script>.sh` / `skill-which` +
`python3`): `init.sh` (skeleton), `check.sh` (structural), `audit.sh` (static
audit), `context.sh` / `verify.sh` (verifier context; no LLM), `cycle.sh`
(full prep cycle), `receipt.sh --from verifier.txt`, `status.sh`. Native
fallback: `wit check|verify|context|receipt`.

## Writing WIT

Build an obligation graph first (goal → lemmas → cases; every node becomes a
step, helper claim, CITE, or GAP). Granularity: split any step combining
algebra+inequality, existence+uniqueness, theorem+precondition,
construction+correctness, both directions, termination+complexity, or case
branches. Canonical skeleton:

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

Rules: sequential labels per scope; no forward/self/cross-case references;
bracketed structural references (`[lemma_name]`, `[hyp]`, `[3]`; case
hypothesis `[n.0]`); `@name`/`@{citation}` for external facts; `CITE`
introduces an external theorem whose downstream use cites the CITE label;
`GAP` (optionally `GAP EXPECTING [subproblem]`) over handwaving; never `BY
obvious/clearly/standard/Mathlib` or bare `BY [n]` for nontrivial inferences;
theorem preconditions proved in their own step before the invocation; no Lean
syntax inside WIT. A good artifact closes every case, ends `QED BY ...`, and
states all domains and hypotheses. Audit targets: label-only justifications,
unproven preconditions, claim drift, unclosed splits, vague citations, hidden
assumptions (nonzero/finite/compact/measurable/positive).

Specialized artifacts — disproof: define the counterexample, verify every
hypothesis, show the conclusion fails, conclude the universal claim false.
Reductions: `REDUCTION/FROM/TO/PRESERVING` + both directions, resource bound,
edge cases. Algorithm correctness: INPUT/OUTPUT/REQUIRES/ENSURES, invariants,
termination measure, complexity — initialization/preservation/exit/
termination/complexity as separate steps. Audits: preserve the original
claim, mark unsupported steps and false bridges, minimal repairs.

## Verification and repair

Cycle: check → audit → context build → status → target-freeze check. A
verifier judges each context skeptically (`[n] ACCEPT/REJECT/GAP: reason`);
persist with `receipt.sh`. Before reporting `VERIFIED`: all obligations have
verdicts, the final SHOW is covered, no GAP/REJECTED labels, receipt matches
the header, output not truncated.

Lean generation policy: do not emit theorem declarations closed by `sorry`,
`admit`, local `axiom`, `constant`, `opaque`, `unsafe`, or placeholder bridges.
When no proof is available, emit at most a statement-check obligation and report
`OBLIGATION_OPEN`; when no faithful Lean statement is available, emit no Lean
file and report the blocker. A `.lean` deliverable must be a proof artifact, not
a draft full of holes.

Repair (`../references/core/repair.md`): structured diagnosis before editing;
preserve the frozen theorem — repairs change proof terms/tactics/helpers/
decomposition, never variables/hypotheses/definitions/conclusion. Lean loop
(`../references/core/lean_verification.md`): prefer LSP/REPL/per-file checks
during iteration, final `lake build`, then SafeVerify target-freeze checks
(compiler success is necessary, not sufficient; SafeVerify failure is
REJECTED). When a linear tactic repair stalls, run the one-ply scan
`../scripts/lean_tactic_scan.py` (search guidance only). The in-process
prover (`../scripts/close_obligation.py` — portfolio, minimization, library
search, compound search) and the blueprint campaign
(`../scripts/blueprint_campaign.py`, for MATHEMATICAL_SOLVE DAGs and their
theory gaps) are the formalization workhorses. No `sorry`/`admit`/`axiom`/
placeholder bridges; Lean is `Lean VERIFIED` only after `lake build` +
SafeVerify, else say `Lean code generation failed`.

Record failed attempts as reusable evidence (attempt id, artifact path,
failure class, diagnostic excerpt, repair attempted, outcome, lesson) and
write the failure note (`runs/<task>/approach_N_failure.md`: frozen target,
failed method/artifact, exact diagnostic, repairs tried, methods to avoid,
two alternate families) before returning a final GAP/FAILED_ATTEMPT/REJECTED.
Ask top-level Witsoc/Explorer to spawn alternate-method agents rather than
retrying the same route; stop locally only for immediately repairable
mechanical failures or when spawning is unavailable and two distinct methods
already failed. Proof-sketch repairs update the matching `sketches[*]` entry
(one mutation dimension at a time; FAILED_ATTEMPT / GAP / PARTIAL honestly).

## Reporting

```text
Status: / WIT file: / Structural check: / Audit: / Verifier context: /
Receipt: / Rejected-GAP labels: / Lean requested: / Lean status: /
Proof idea: / Next action:
```

plus the standard artifact block from the top-level SKILL.md. Precise
language: "structurally valid" = check passed; "verifier contexts generated"
= `wit verify` ran; "semantically accepted" = verdicts accepted;
`VERIFIED` = complete accepted receipt discipline only.
