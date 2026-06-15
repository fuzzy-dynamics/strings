---
name: witsoc
description: General mathematics skill and capability-discovery framework for OpenScientist. Use for mathematical problem solving, proof generation, proof critique, disproof, theorem formalization, premise search, lemma discovery, proof automation, Lean/Coq-adjacent planning, algorithms, complexity reductions, algebra, analysis, topology, number theory, combinatorics, graph theory, geometry, probability, logic, and scientific arguments whose correctness depends on chained premises. Acts as a research advisor: it exposes candidate routes, techniques, tools, and reasoning directions, and the reasoning agent selects among them. Routes serious work through internal subskills `witsoc-explorer`, `witsoc-research-lovasz`, and `witsoc-generator`; can answer small routine math questions directly.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc

Witsoc is the top-level mathematics coordinator. It is a research advisor,
not a script executor: its job is to expose relevant techniques, tools,
memory stores, and reasoning directions, present candidate approaches with
applicability conditions and tradeoffs, and reduce the cost of discovering a
working strategy. The reasoning agent — not the skill — chooses approaches,
combines techniques, forms hypotheses, and produces conclusions.

Keep the root context small: discover what the task actually needs, load only
the needed protocol files, run deterministic scripts for checks, and report
only statuses justified by evidence.

## Two Layers: Contracts vs. Strategy

Everything in this skill belongs to one of two layers. Confusing them is the
root failure mode in both directions: rigid runs treat strategy as contract;
dishonest runs treat contract as strategy.

**Contracts — non-negotiable.** These keep claims honest and are never a
matter of agent preference:

- target freeze and mutation records (`references/core/target_freeze.md`),
- claim acceptance and the legal status lattice (`references/core/claim_acceptance.md`, `references/core/status.md`),
- every status word backed by a named mechanism (kernel, receipt, checker),
- calibration sentinels stay unsolved; a "solve" there fails the run,
- Generator authorization and the separation of powers: Explorer arbitrates
  status, Lovasz attacks barriers and emits candidates, acceptance gates
  promote or reject claims, Generator writes artifacts and never upgrades
  mathematical truth,
- production gates before a final answer (`references/core/production_gates.md`),
- gate-enforced floors (per-barrier caps, mutation-before-retry, skeptic minima,
  ideation quotas): floors, not ceilings.

**Strategy — advisory.** Which route, technique, tool, decomposition,
ordering, or representation to use is the agent's decision. Wherever this
skill or its references say "use X" or "do A before B" about strategy, read
it as: *X is a candidate with a recorded track record; A-before-B is the
default ordering because it usually pays — evaluate applicability, consider
alternatives, choose deliberately, and record the choice.* Departing from a
default is legitimate; departing from a contract is not.

## Internal Subskills (composable building blocks)

The internal subskills live in this folder. Load a nested `SKILL.md` only
when that capability is needed. They are building blocks, not stations on an
assembly line — a task may compose them in non-default orders as long as the
contract layer (freeze, authorization, gates) is respected.

- `witsoc-explorer/SKILL.md`: problem freezing, status triage, theorem/premise search, counterexample pressure, proof-plan selection, handoff generation, and final arbitration.
- `witsoc-research-lovasz/SKILL.md`: research-program orchestration for open, frontier, blocked, olympiad, or serious proof targets; barrier attack, proof-DAG decomposition, worker packets, skeptic review, and verified partial products.
- `witsoc-generator/SKILL.md`: `.wit` generation/repair, structural checks, verifier contexts, receipt tracking, and optional Lean generation/checking.

Do not assume the first skill loaded contains all required knowledge. When a
capability gap appears — an unfamiliar domain, a missing tool, a technique
named but not described — actively discover further resources: nested
references, sibling skills, plugins, memory stores. Recursive expansion
(problem → relevant skill → its references → its subskills → further
techniques → expand promising branches) is the intended usage pattern,
bounded by recorded stop conditions and safety limits.

When a task routes through Lovasz, the user-facing progress message must include:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.
```

## Route Advisor

Start every nontrivial mathematical task by *choosing* a route, not by
pattern-matching to a prescribed one. Candidate routes with applicability
conditions, tradeoffs, and historical failure cases live in
`references/core/routing.md`. The candidates in summary:

| Candidate route | Fits when | Main risk if misapplied |
|---|---|---|
| Direct answer (`L0_DIRECT`/`L1_SKETCH`) | small routine calculation or proof | overclaiming on a target that deserved adversarial pressure |
| Explorer only | lookup, premise search, exploration, counterexample hunting | stopping at literature status when the user asked for progress |
| Explorer -> Lovasz -> Explorer | serious prove/show, open, blocked, frontier, olympiad | cost; mitigated by the olympiad fast lane |
| Generator-first | inspection/repair of an existing `.wit`/Lean artifact | masking a mathematical blocker as a syntax issue |
| Explorer -> Generator | routine accepted target needing artifacts | skipping Lovasz on a target that was not actually routine |

Two routing rules are contract, not advice: (1) an open-style target the user
asked to solve/attack must reach Lovasz before final status unless a concrete
operational blocker is recorded (see Discovery Requirement); (2) Generator
runs only with Explorer authorization for nontrivial targets. Everything else
— including skipping Lovasz after a kernel-verified routine closure, or
starting at Generator for artifact repair — is the agent's call, recorded in
the route state (`scripts/route.py`, `scripts/validate_route_state.py`).

## Strategy Doctrine (advisory — load when exploring)

The strategy-layer practices that shape *how* you explore — the capability
discovery loop (retrieval before invention), tree search over linear plans,
and primitives over wrappers — live in `references/core/strategy_doctrine.md`.
Load it for nontrivial exploration. The one tool worth naming up front:
`witsoc decide options --statement "<goal>"` assembles ≥2 candidate approaches
from the LIVE stores (technique atlas, L5 priors, L4 failure warnings, past
decisions) with a recommended default — prefer it over reciting doctrine from
memory; record choices (`witsoc decide record`) and outcomes
(`witsoc decide resolve`) so defaults are LEARNED. Contracts are never
decision points.

## Required Contracts

For serious mathematical work, load and follow only the relevant contracts:

- Architecture map (groups, run ledger, migration path): `references/core/architecture.md`; `witsoc map` prints it.
- Service boundary (Witsoc supports, Lovasz generates candidates, gates accept): `references/core/services.md`.
- Target freeze and mutations: `references/core/target_freeze.md`.
- Claim acceptance and legal status transitions: `references/core/claim_acceptance.md`.
- Status labels and verification discipline: `references/core/status.md`.
- Artifact registration and stale artifact rules: `references/core/artifact_policy.md`.
- Production-complete gates and quality levels: `references/core/production_gates.md`.
- Open-problem rules: `references/core/open_problem.md`.
- Generator authorization: `references/core/generator_gate.md`.
- Handoffs and state machine: `references/core/handoff.md`.
- Failure recovery and repeated-failure stop conditions: `references/core/failure_recovery.md`.
- Lean/SafeVerify checking loop: `references/core/lean_verification.md` and `references/core/safeverify.md`.
- Deterministic tooling and CLI conventions: `references/core/tooling.md`.
- The Intelligence Bus — engines emit requests, the ORCHESTRATOR fulfills them and re-runs (you are the fleet): `references/core/intelligence_bus.md`.
- Benchmark/orchestrator discipline: `references/core/harness_discipline.md`.

Advisory companions (strategy layer, load when exploring):

- Technique discovery and transfer playbook: `references/core/technique_discovery.md`.
- Primitive capability catalog: `references/core/capability_catalog.md`.
- Exploration strategy (profiling, ontology, ranking): `references/core/exploration_strategy.md`.

Do not duplicate these protocols in task-local prompts. Load a protocol when the route reaches that concern.

## Coordination Pattern (default, with invariant gates)

For serious proof work, the default coordination pattern is:

```text
INTAKE -> EXPLORER_TRIAGE
EXPLORER_TRIAGE -> DIRECT_ANSWER | EXPLORER_PROOF_PLAN | LOVASZ_BARRIER_PACKET
LOVASZ_BARRIER_PACKET -> LOVASZ_ATTACK -> EXPLORER_REVIEW
EXPLORER_REVIEW -> LOVASZ_BARRIER_PACKET | GENERATOR_HANDOFF | HONEST_STOP
GENERATOR_HANDOFF -> GENERATE_WIT -> CHECK_WIT -> BUILD_CONTEXT -> OPTIONAL_LEAN -> REPORT
GENERATOR_FAILURE -> EXPLORER_REVIEW
```

The invariants here are the *gates between phases* — a frozen target before
attack, an Explorer review of every Lovasz return, authorization before
Generator, validation before report — not the order or choice of exploratory
moves within a phase. Within phases, technique selection, branching, and
ordering belong to the agent.
Explorer review is auditable: `scripts/validate_explorer_review.py` validates
`explorer_return_packet.json` and blocks `GENERATOR_READY` unless one selected
product has downstream evidence, a dependency path to the target, formalization
readiness, acceptable report quality, and no open-core reduction blocker.
The cross-phase state is also auditable: `scripts/research_state.py` derives
`witsoc_research_state.json` from existing ledgers, and
`scripts/validate_research_state.py` checks target hashes, open/research
coverage, Lovasz review, and Generator authorization before final reporting.

Explorer owns target freezing, status triage, proof-plan arbitration, Lovasz
packet creation, Generator authorization, and final arbitration. Lovasz
attacks mathematical barriers and returns evidence, demotions, proof-DAG
state, worker outcomes, and recommended next targets. Generator writes and
repairs artifacts but does not upgrade mathematical truth.

Repeat Explorer -> Lovasz -> Explorer until there is a verified/checked
result, a narrow accepted artifact target, a partial/conditional result, a
counterexample/obstruction, or a documented honest stop.

## Discovery Requirement

If the user asks to prove, disprove, solve, make progress on, or deep-run an open-style target, do not stop at literature/status classification alone.

If Explorer classifies the target as `OPEN`, `UNSOLVED`, `UNCONFIRMED`, unsupported by known results, blocked by a structural gap, or requiring a new theorem, create a Lovasz barrier packet and run a complete Lovasz pass immediately unless there is a concrete operational blocker. A status-only Explorer report is incomplete at that point.

A complete Lovasz campaign must include the actual lemma queue, proof-DAG or barrier records, worker evidence when available, failure memory/gap feedback, result scoring, formalization feasibility, synthesis audit, report grading, Explorer return packet, and Explorer review. A prose-only barrier summary is not enough for a claimed deep run.
The Lovasz production gates also materialize `lovasz_campaign_state.json`,
`lovasz_doctor.json`, `lovasz_loop_health.json`, and
`lovasz_synthesis_audit.json`; these are the operational health record for the
barrier campaign.

## Claim Status

Never substitute confidence for evidence. Use these labels conservatively:

- `VERIFIED`: formal/verifier evidence supports the exact frozen target, such as `LEAN_VERIFIED` with SafeVerify/target checks or accepted receipts covering all obligations.
- `CHECKED`: deterministic computation, kernel result, or structural check supports the exact claim.
- `PROVED_SKETCH`: coherent informal proof sketch without formal verification.
- `PARTIAL` or `CONDITIONAL`: special cases, bounds, reductions, conditionals, or computational products.
- `CONJECTURE`: evidence without proof.
- `OPEN`, `GAP`, `FAILED_ATTEMPT`, or `REJECTED`: no full supported proof of the frozen target.

Do not write bare “verified” in user-facing text unless the sentence names the mechanism, for example `LEAN_VERIFIED` or `RECEIPT_ACCEPTED`.

## Two-Stage Success Rule (Frontier Targets)

Solving an open problem has two distinct success stages; never conflate them:

- `MATHEMATICAL_SOLVE`: the complete informal proof DAG composes to the frozen target with every node closed (`PROVED_SKETCH` or better), a skeptic fleet (≥3 independent passing reviews per node), no open gaps, and audited theorem preconditions. Audited deterministically by `scripts/validate_mathematical_solve.py`. A `MATHEMATICAL_SOLVE` triggers a formalization campaign as its own subsequent program — it is never itself reported as a solve.
- `FORMAL_SOLVE`: the existing bar — WIT + Lean + SafeVerify verifies the original frozen target.

For `frontier_attack` portfolio problems, neither stage is reportable as a solve of the named problem until the solve-claim protocol (`scripts/solve_claim_protocol.py`) reaches `SOLVE_ACCEPTED`: passing math-solve audit, an explicit Lean/SafeVerify receipt validated by `scripts/validate_lean_receipt.py` for `FORMAL_SOLVE`, at least one verified independent re-derivation by a fleet with no access to the original proof, and a `NOVEL_CANDIDATE` novelty verdict. Human review may be recorded as additional evidence, but is not the default machine-verified solve gate. Calibration sentinels (`frozen_calibration`) remain frozen: a solve there still fails the campaign.

## Quality Levels

Use the levels from `references/core/production_gates.md`:

- `L0_DIRECT`: direct answer with reasoning.
- `L1_SKETCH`: informal proof/disproof sketch.
- `L2_CHECKED_DERIVATION`: deterministic calculation, bounded check, or structural check.
- `L3_WIT_ARTIFACT`: WIT artifact produced.
- `L4_WIT_LEAN_ATTEMPTED`: WIT plus Lean attempted.
- `L5_WIT_LEAN_VERIFIED`: WIT plus Lean/SafeVerify verified.
- `L6_RESEARCH_PRODUCT`: Lovasz research product with checked/verified artifacts and Explorer review.

The final answer must not imply a higher level than the run achieved.

## Tooling

Prefer deterministic Witsoc scripts and native WIT/Lean tools for routing, validation, structural checks, receipt parsing, target-freeze checks, and report grading. Use `scripts/witsoc.py` as the unified entrypoint when available; otherwise use the specific script named by the relevant protocol.

For open, unsolved, frontier, or deep-research targets, the self-enforcing Witsoc path is:

```bash
WITSOC="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)"
python3 "$WITSOC" run-open runs/<task> --prompt "<frozen target or user request>" --loops 0 --limit 0
python3 "$WITSOC" finalize runs/<task> --require-route
```

`run-open` writes `witsoc_run_controller.json` with every gate, command, exit code, and artifact path. If any gate fails, report `FAILED_GATE` plus the first failing gate and exact repair target; do not replace the failed gate with prose judgment.

Distinguish the two layers in tooling too: for *strategy* tooling (search, mining, synthesis, proving), `references/core/capability_catalog.md` presents candidates and applicability — the agent chooses among them and may compose them in new ways. For *contract* tooling (validators, checkers, receipt parsers), the named script is the mechanism, and an LLM may not stand in for it.

Common scripts are listed and explained in `references/core/tooling.md`. Do not load or summarize the entire scripts directory unless debugging the toolchain.

For serious finalization, run the applicable validators when the scripts are available:

- route state: `scripts/route.py`, `scripts/validate_route_state.py`
- handoffs: `scripts/validate_handoff.py`, `scripts/validate_generator_handoff.py`
- Generator outputs: `scripts/lint_wit_quality.py`, `scripts/generator_manifest.py`
- Lovasz runs: `scripts/validate_lovasz_phase.py`, `scripts/validate_proof_dag_integrity.py`, `scripts/validate_lovasz_run.py`, `scripts/validate_open_problem_run.py`
- Lovasz campaign loops: `scripts/proof_gap_to_barrier_feedback.py` (failure classification + re-dispatch contract)
- reports: `scripts/open_problem_report.py`, `scripts/grade_witsoc_report.py`, `scripts/explorer_return_packet.py`
- controller/final status: `scripts/witsoc_controller.py` via `python3 scripts/witsoc.py run-open|finalize|validate-all`
- Lean receipts: `scripts/validate_lean_receipt.py`; placeholder/environment-only Lean output is `ENV_CHECK_ONLY`, never `VERIFIED_LEAN`

Register generated WIT, Lean, SOC, receipt, Lake log, proof-worktree record, and report artifacts in `witsoc_artifacts.json` when artifact tooling is available.

## WIT And Lean

If the user explicitly asks for WIT code, `.wit`, or WIT plus Lean, WIT generation is mandatory unless blocked by an exact reason. Do not satisfy that request with only prose or Lean.

Generator may run only after Explorer authorization for nontrivial targets. It is forbidden when the target is open/blocked without a Lovasz return packet, the accepted product is only speculative, target hashes disagree without a mutation record, formalization feasibility is poor, or required proof-DAG dependencies remain open. New artifacts should pass `scripts/generator_preflight.py` before writing and `scripts/generator_receipt_gate.py` before any status-bearing report.

When Lean is requested, generate Lean from the frozen WIT target, attempt final `lake build` when feasible, and report `LEAN_VERIFIED` only when Lean and target-freeze/SafeVerify checks pass. A backend/tool result that auto-generates a placeholder theorem or only checks that Lean is operational must be classified `ENV_CHECK_ONLY`; run `scripts/validate_lean_receipt.py` before using any Lean result as claim evidence. If Lean repair is blocked, say `Lean code generation failed` and name the blocker.

If WIT/Lean artifacts are generated and the Witsoc plugin is available, open the generated file in the plugin iframe. If plugin activation fails, still return artifact paths and check status.

## Citation Calibration

Cite only when the answer depends on the source: solved/open status claims, exact external theorems, best-known bounds, priority claims, or borrowed constructions. Cite at the point of use with enough detail to find the result. Do not cite routine algebra or standard named facts unless exact preconditions matter. Never invent a citation; if no source was checked, say the claim is unconfirmed.

## Before Final Answer

For serious mathematical, WIT, Lean, Lovasz, or Generator runs, apply `references/core/production_gates.md` before responding:

- route state checked or limitation stated,
- frozen target and target hash stated when serious proof work used them,
- status justified by the claim acceptance contract,
- generated/cited artifacts registered or paths shown,
- WIT/Lean/receipt/plugin statuses stated exactly,
- Lovasz return reviewed when Lovasz ran,
- Generator authorization checked when artifacts were generated,
- achieved quality level stated.

For small math answers, simply provide the result and reasoning.

For serious Witsoc responses, end with:

```text
Artifacts:
- WIT: <path|none>
- Lean: <path|none>
- Receipt: <path|none>
- Status: STRUCTURE_OK=<yes/no/not run>; CONTEXT_BUILT=<yes/no/not run>; RECEIPT_ACCEPTED=<yes/no/not run>; LEAN_VERIFIED=<yes/no/not run>
- Plugin: <opened/open failed/not attempted>
```
