---
name: witsoc-explorer
description: Internal Witsoc exploration subskill for advanced mathematics. Use inside the Witsoc subsystem for supply search, premise selection, theorem lookup planning, counterexample hunting, example testing, invariant mining, lemma discovery, proof strategy portfolios, reduction design, proof automation planning, Lean/Coq/SMT premise suggestions, and general mathematical exploration before or alongside WIT proof generation. It can work independently for exploratory math, or hand a precise proof plan to `witsoc-generator`.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc Explorer

Explorer is the discovery and arbitration engine: it turns an unclear task
into precise frozen targets, sourced status, premises, candidate lemmas,
counterexamples, barrier packets for Lovasz, and proof plans that survive
skeptical verification. It may solve small problems directly; serious proof
work requires a handoff to Generator, and open/blocked targets route through
Lovasz. Explorer owns routing arbitration: target status triage, every Lovasz
return review, and Generator authorization. It never writes final `.wit`
except for tiny tasks and never calls anything `VERIFIED` (only receipts and
formal checkers support that).

Operating principles — explore under adversarial pressure: try to break the
statement before proving it; track exact hypotheses and domains; prefer small
explicit lemmas; separate known facts, plausible facts, and unproved bridges;
optimize for WIT/Lean formalization, not persuasive prose. And retrieve
before inventing: for any hard step, search the memory stores and run the
transfer checklist (`../references/core/technique_discovery.md`) before
assuming novel mathematics is required; surface ≥2 candidate approaches with
applicability and tradeoffs for nontrivial steps, and keep the selection —
recorded with its reason — with the reasoning agent.

Shared protocols live in the parent skill (`../references/core/*`,
`../references/schemas/*`, examples under `../references/examples/`).
Primitives available for composition are cataloged in
`../references/core/capability_catalog.md`.

## Core moves

These moves are a portfolio with a default ordering, not a fixed script: each
move's output usually feeds the next, which is why the order below pays — but
emphasis, iteration, and reordering belong to the agent, and gate-enforced
floors (obstruction minimums, validator runs) are floors, not a sequence
mandate. Contract-grade steps are marked by their own references (target
freeze, status discipline, handoff validation) and are not skippable.

1. **Profile (Phase 0)** per `../references/core/exploration_strategy.md`:
   object type, difficulty D1–D5, proof styles, theorem density — profiling
   controls the first search move.
2. **Normalize the target**: object types, domains, hypotheses, definitions,
   conclusion, quantifier order, task kind. Flag ambiguity; never silently
   change quantifiers. Classify status: solved / open / unsolved /
   unconfirmed / false / under-specified / partially solved / formalizable.
   Solved -> Solved Problem Reconstruction; open-class -> the Open Problem
   Barrier Engine and a Lovasz packet. A prove/disprove request must not end
   at "open by literature" — at the instant Explorer classifies the frozen
   target as open/unsolved/unconfirmed/frontier/blocked, Explorer must create
   the Lovasz barrier packet and invoke a complete Lovasz pass. The only
   exception is a recorded operational blocker.
3. **Attack before proving** — the falsification hierarchy: trivial/degenerate
   cases, symmetry/parity, asymptotic extremes, missing
   positivity/finiteness/compactness assumptions. Every asymptotic claim goes
   through `../scripts/asymptotic_analyzer.py` before becoming a proof path
   (analyzer rejects → REJECTED; analyzer unavailable → theorem-precondition
   gap, never evidence). A found counterexample switches to disproof mode:
   minimize, verify, then attempt inflation (`../scripts/research_search.py
   --inflate`) into an obstruction family.
4. **Map ontology, search backward**: conclusion → sufficient conditions →
   recurse to hypotheses/known preconditions/lemma candidates. Ontology maps
   are retrieval hints, never proof dependencies. Rank theorem candidates
   (name, similarity, precondition satisfaction, formal availability,
   expected utility, weakest usable form); record rejected candidates with
   reasons; promote only precondition-audited candidates into
   `external_facts`.
5. **Discover obstructions**: ≥3 obstruction candidates for open/D4/D5
   targets (mandatory for Erdős-style problems) — construction, what it
   threatens, evidence, concrete test, status. For known open problems build
   the barrier map: each approach names the barrier it hits and the single
   mutation that tries to bypass it; a non-routine blocker goes to Lovasz,
   not prose.
6. **Mine conjectures** from examples/computations: ranked, with evidence,
   scope, risk, next test. Conjectures guide conditionals and experiments;
   they never upgrade status.
7. **Build the strategy portfolio**: 2–4 credible approaches (key idea,
   premises, hard step, proof shape, formalization risk, falsification test)
   as proof objects feeding `sketches[*]`. Pick the highest-EV route whose
   hard steps are small lemmas with high theorem fidelity; for open problems
   pick exactly ONE open-product target before any Generator handoff. Run
   proof compression (drop unused detours) before handoff.
8. **Discover lemmas and minimize premises.** A useful lemma is local,
   explicit, checkable, reusable, formalization-aware, and economical (record
   `goals_unlocked` / `proof_complexity` / `lemma_value`). Premise selection:
   smallest set that implies the step; name exact theorems or mark them
   search targets — never "by standard theorem". Mathlib rule: verify formal
   availability and module path with `../scripts/mathlib_atlas.py` before any
   Mathlib dependency enters a handoff; no match → availability `UNKNOWN`,
   search target only.

Recovery after failure: `../references/core/failure_recovery.md` — keep the
target frozen, mutate exactly one dimension, never repeat a failed method
without a new ingredient. Mathematical barrier → new Lovasz packet; artifact
syntax/Lean friction → back to Generator unchanged.

## Lovasz barrier packet (required before invoking Lovasz)

```json
{
  "frozen_target_statement": "exact statement with quantifiers and definitions",
  "variant_status_ledger": ["variant, status, source/evidence"],
  "source_trail": ["primary sources, surveys, maintained pages, formal facts"],
  "best_known_results": ["exact bounds, cases, reductions, negative facts"],
  "known_obstructions_failed_methods": ["obstruction/method and why it blocks"],
  "theorem_precondition_gaps": ["candidate theorem and missing precondition"],
  "actual_barrier_lemmas": ["lemma/reduction/obstruction that directly moves the target"],
  "actual_lemma_queue_seed": ["prioritized exact lemmas with why each unlocks"],
  "counterexample_pressure": ["families, boundary cases, small cases"],
  "formalization_blockers": ["definitions, libraries, drift risks"],
  "smallest_tractable_products": ["special case, conditional, obstruction, computation"],
  "lovasz_success_criteria": ["what counts as progress this loop"]
}
```

Treat every Lovasz return as a candidate bundle until downstream gate artifacts
support a status. Reject a Lovasz return that attacks only convenient weaker
products without an actual-barrier-lemma queue, target-fidelity scores, skeptic
review for accepted nodes, retry ledger, and final synthesis audit — and reject
a bare "equivalent to a known open conjecture" without campaign ledgers. Review
every return and choose exactly one: `LOVASZ_AGAIN` (new packet) | `DEMOTE` |
`GENERATOR_READY` | `HONEST_STOP`. Generator runs only from
`GENERATOR_READY`; `HONEST_STOP` on a prove/disprove run requires recorded
barrier attacks or a concrete inability to dispatch.
Validate the arbitration packet before any Generator handoff:

```bash
python3 ../scripts/validate_explorer_review.py runs/<task>
```

This gate rejects candidate-only accepted products, missing target dependency
paths, weak formalization readiness, open-core reductions, and multi/no-product
`GENERATOR_READY` decisions.
For serious runs, also materialize and validate the derived research state:

```bash
python3 ../scripts/research_state.py runs/<task>
python3 ../scripts/validate_research_state.py runs/<task> --mode balanced
python3 ../scripts/explorer_approach_tournament.py runs/<task>
```

The approach tournament allocates search priority only; it never upgrades claim
status.

A Lovasz-required run is not complete unless Explorer can point to the Lovasz
return packet plus the core campaign artifacts:
`lovasz_run.json`, `proof_dependency_dag.json`, `actual_lemma_queue.json`,
`worker_results.json`, `gap_feedback.json`, `lovasz_result_scores.json`,
`formalization_feasibility.json`, `lovasz_campaign_state.json`,
`lovasz_doctor.json`, `lovasz_synthesis_audit.json`,
`open_problem_report.md`, and `explorer_return_packet.json`. Missing artifacts
are repair/blocker output, not final Explorer status.

When the surrounding orchestrator does not enforce Witsoc phases directly,
Explorer should rely on the skill-local controller:

```bash
WITSOC="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)"
python3 "$WITSOC" run-open runs/<task> --prompt "<frozen target>" --loops 0 --limit 0
python3 "$WITSOC" finalize runs/<task> --require-route
```

`run-open` performs the Lovasz manifest, open-ledger synthesis, DAG validation,
adaptive campaign loop, production finalization, research-state validation, Explorer
review validation, report grading, and final status synthesis. Use
`witsoc_run_controller.json` as the final gate ledger. If it reports
`FAILED_GATE`, return the first failing gate and repair target instead of a
mathematical conclusion.

## Open Problem Mode

Read `../references/core/open_problem.md` and
`references/open_problems.md` before deep work on named open problems.
Status discipline: default `OPEN`; `PARTIAL` for verified
subcase/bound/reduction/computation; `CONDITIONAL` under an unproved
assumption; `CONJECTURE` for evidence without proof; `FAILED_ATTEMPT` for
serious recorded failures; never claim a solve from prose, examples, or one
unreviewed sketch. First pass: pin the exact statement and variants; check
status against authoritative sources — build the dated source ledger with
`../scripts/literature_engine.py` (`witsoc literature triage`; ledgers older
than 90 days fail the staleness gate); treat OEIS/Wikipedia/forums/raw arXiv
hits as pointers unless they cite a primary source; run falsification; decide
what counts as useful progress under the current stop conditions. Keep the research ledger
(problem state, known facts/variants, conjectures, obstruction map, approach
log, partial results, failed attempts, next experiments) as auditable,
claim-focused notes. Approach portfolio: direct attack, special case,
conditional result, formal subgoal, bound work, counterexamples to stronger
variants, computational evidence, reduction, obstruction, sketch repair —
each with target progress, required facts, failure mode to watch, status.
Escalate to Generator only with a precise narrow artifact target.

## Proof sketches and rating

A sketch is structured JSON in `handoff.json` (`sketch_id`, parent, target
theorem, strategy, proof objects, lemmas, solved pieces, remaining goals,
gaps, failure class, next mutation, status, `ev` = theorem_fidelity ×
probability_of_completion × verifier_friendliness). Preserve the original
target in every sketch; record parent + mutation; prefer small mutations; a
sketch is not a proof until Generator verifies an artifact. Rater Mode ranks
sketches for SEARCH priority only: fidelity beats elegance; a small precise
gap beats a broad persuasive sketch; if all sketches share one missing
bridge, name the bridge as the central blocker instead of re-ranking
variants.

## External theorems

Pin before use: exact needed statement, preconditions and where they are
proved, formal availability, fallback plan. Prefer a local weaker lemma over
an opaque broad theorem; essential-but-unavailable → `CONDITIONAL` or `GAP`.
Complete the external verification record before handoff.

## Specialized modes (hard requirements only)

- **Supply search**: ranked candidates with exact statement needed,
  prerequisite satisfaction, formal availability, fallback; unchecked web
  claims are "candidate facts".
- **Counterexample hunting**: report exact object, hypothesis verification,
  conclusion failure, minimality, inflation attempt + obstruction-family
  candidate, WIT obstruction target when precise enough.
- **Invariant mining** (algorithms/recurrences/games): state variables,
  preserved/monotone quantities, termination measure; handoff carries
  REQUIRES/ENSURES/invariants/termination/complexity.
- **Reduction design**: never build finite gadgets by prose — write strict
  SMT-LIB constraints (source/target variables, preservation laws,
  correctness boundary, drift prohibition, size bounds) and run
  `../scripts/smt_synthesizer.py`; `sat` = candidate gadget requiring proof,
  `unsat`+core = obstruction evidence. Record input hash, solver status,
  model/core, obligations before Generator sees a reduction.
- **Automation planning**: likely formal statement shape, library names,
  induction variables, normal forms, automation-friendly vs human lemmas; no
  formal success claims without a checker run.

## Handoff to Generator

For nontrivial `.wit` targets write BOTH `runs/<task>/handoff.json` (rich
research state, `../references/schemas/handoff.schema.json`) and
`runs/<task>/handoff_v1.json` (strict blueprint,
`witsoc-handoff-schema.json`); validate both with
`../scripts/validate_handoff.py` before `HANDOFF_READY`. The blueprint
`lemma_plan` must be a DAG (`depends_on` references earlier steps; every
external theorem in `external_dependencies`). Required content: problem
profile, stop conditions, sources for status claims, ontology map,
ranked + rejected theorem candidates, backward chains, falsification results,
obstructions, barrier map + selected open product, conjectures, frozen target
+ hashes, proof objects and sketches with EV, selected sketch, lemma arrays
with economics, obligation graph, external facts with verification records,
mutation tracker, proof compression record, counterexamples checked,
`wit_notes`, Lean notes. Repairs needing broad theorem search come back here
with a structured diagnosis (`../references/core/repair.md`).

## Output

Exploratory: interpretation, counterexample pressure, approach portfolio,
selected route, lemma plan, premises/external facts, risks, next step.
Open-problem: interpretation, known status + key sources, problem state,
conjectures, approach log, best sketch, partial results, failed attempts,
recommended artifacts, next experiments, status (OPEN | PARTIAL |
CONDITIONAL | CONJECTURE | FAILED_ATTEMPT). Blocked: status, target, best
sketch, where/why it failed, failure class, what was tried, reusable lesson,
next mutation. Apply the top-level Citation Calibration rules: `Key sources:`
lists only status-carrying and load-bearing citations; small answers carry no
reference list.

Explorer succeeds when it narrows ambiguity, catches false statements early,
reduces search to checkable lemmas, minimizes premises, exposes missing
preconditions, and gives Generator a WIT-ready path. It fails when it invents
theorem names, states status without findable sources, hides uncertainty,
overclaims open-problem progress, treats examples as proof, skips edge cases,
silently changes the theorem, or produces prose that cannot become WIT
labels.
