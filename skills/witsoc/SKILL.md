---
name: witsoc
description: General mathematics skill and subsystem for OpenScientist. Use for every type of mathematical work: problem solving, proof generation, proof critique, disproof, theorem formalization, premise search, supply search, lemma discovery, proof automation, Lean/Coq-adjacent planning, algorithms, complexity reductions, algebra, analysis, topology, number theory, combinatorics, graph theory, geometry, probability, logic, and scientific arguments whose correctness depends on chained premises. Contains internal subskills `witsoc-research-lovasz` for open-problem research programs, `witsoc-explorer` for mathematical exploration, and `witsoc-generator` for WIT proof artifacts; can also work directly for small math questions.
metadata:
  skill-author: OpenScientist
category: research
---

# Witsoc

Witsoc is the mathematics skill for the orchestrator. It owns mathematical
contracts, route advice, evidence standards, validators, diagnostics, and
artifact/report discipline. The orchestrator remains in charge of strategy:
fanout, ordering, budget, agent assignment, reframing, and which Witsoc
recommendations to use. Witsoc recommendations are defaults and affordances, not
commands, except where they enforce claim honesty.

Use this skill for all mathematical tasks. For simple questions, answer directly with a clear derivation. For serious proof work, coordinate the internal subskills:

- `witsoc-research-lovasz/SKILL.md`: Lovasz-mode research-program orchestration for named open problems, unsolved conjectures, Erdős-style questions, frontier theorem discovery, barrier analysis, source/status triage, conjecture mining, disproof-first search, and verified partial research products.
- `witsoc-explorer/SKILL.md`: search, premise selection, lemma discovery, counterexample hunting, proof automation planning, open-problem research ledgers, and general mathematical exploration.
- `witsoc-generator/SKILL.md`: `.wit` proof generation, repair, structural checking, verifier-context construction, receipt tracking, and optional Lean formalization.

These subskills live inside this folder. If you need their full instructions, read the relevant nested `SKILL.md`; do not look for sibling top-level skill directories.

## Codex/Claude Contract

For Codex, Claude Code, and other shell-capable orchestrators, Witsoc is a
packet-first mathematical decision-support layer. The orchestrator stays in
charge of strategy, fanout, worker assignment, budget, reframing, and final
decisions. Witsoc provides routing advice, evidence gates, target-freeze
discipline, worker templates, recovery commands, and report standards.

Use the root launcher from any working directory:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py llm-contract
python3 ~/.openscientist/skills/witsoc/witsoc.py subskills
python3 ~/.openscientist/skills/witsoc/witsoc.py route --field json "<task>"
python3 ~/.openscientist/skills/witsoc/witsoc.py spawn-template explorer --target "<problem>"
```

Read `references/core/llm_contract.md` only when the task needs the detailed
agent contract. Witsoc recommends; the orchestrator decides. Witsoc may block
unsupported claim-status upgrades, but must not block creative search,
reframing, alternate strategies, or extra worker fanout.

## Runtime Preflight

Before using any Witsoc script command, check that the local runtime exists in
the Witsoc skill folder:

```text
scripts/witsoc.py
src/witsoc/cli.py
```

If either file is missing, do not treat Witsoc as ready just because `SKILL.md`
exists. Restore the runtime first with the canonical absolute command:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

The safest local entrypoint is the root launcher, which performs this preflight
and restore automatically before delegating to `scripts/witsoc.py`:

```bash
python3 ~/.openscientist/skills/witsoc/witsoc.py --help
python3 ~/.openscientist/skills/witsoc/witsoc.py route "deep run prove or disprove this open conjecture"
```

After restore, verify:

```bash
python3 ~/.openscientist/skills/witsoc/scripts/witsoc.py --help
python3 ~/.openscientist/skills/witsoc/witsoc.py --help
```

Only proceed with Witsoc script-based routing, validators, decision packets, or
Lovasz/Explorer/Generator tooling after this preflight passes. If `bootstrap.py`
is missing too, install the PyPI package and materialize the skill runtime:

```bash
python3 -m pip install -U witsoc
python3 -m witsoc restore-skill --target ~/.openscientist/skills/witsoc --replace
```

The canonical OpenScientist skill directory is:

```text
~/.openscientist/skills/witsoc
```

If the local `scripts/` tree, `src/` package, or `scripts/witsoc.py` entrypoint
is missing in that folder, restore Witsoc from PyPI before trying to recreate
the scripts manually:

```bash
python3 -m pip install -U witsoc
python3 -m witsoc restore-skill --target ~/.openscientist/skills/witsoc --replace
```

If this root-level `bootstrap.py` file is still present, it also survives
deletion of `scripts/` and `src/`:

```bash
python3 ~/.openscientist/skills/witsoc/bootstrap.py --replace
```

PyPI page:

```text
https://pypi.org/project/witsoc/
```

After installation, verify with:

```bash
python3 ~/.openscientist/skills/witsoc/scripts/witsoc.py --help
python3 ~/.openscientist/skills/witsoc/scripts/witsoc.py install-help
python3 -m witsoc restore-skill --target ~/.openscientist/skills/witsoc --check
```

When a task routes through Lovasz, the user-facing progress message must include:

```text
Using witsoc with witsoc-explorer -> witsoc-research-lovasz -> witsoc-explorer.
```

Shared protocols live under `references/core/`. Load only the protocol needed for the current task:

- `references/core/routing.md`: fast path, subskill responsibility boundaries, and recovery routing.
- `references/core/routing_tests.md`: worked routing examples and the `test_route.py` regression cases.
- `references/core/target_freeze.md`: canonical target records, target hashes, and explicit target mutation records.
- `references/core/claim_acceptance.md`: evidence requirements and legal acceptance of mathematical claims.
- `references/core/artifact_policy.md`: artifact registry, proof worktrees, stale artifact rules, and metadata requirements.
- `references/core/generator_gate.md`: rules for when Generator may and may not run.
- `references/core/production_gates.md`: before-final-answer checklist, production-complete criteria, and quality levels.
- `references/core/orchestrator_fit.md`: boundary between orchestrator strategy and Witsoc math affordances.
- `references/core/algorithmic_strategy.md`: advisory scoring algorithms for lanes, barriers, products, stop/continue, and portfolios.
- `references/core/interactive_intake.md`: optional user questions, deep-run preview, and mission-menu guidance.
- `references/core/plugin_integration.md`: registry-aware Witsoc plugin behavior and iframe activation.
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
- `scripts/validate_handoff.py`: deterministic handoff validation and arithmetic checks, including the Lovasz proof-DAG and worker-result invariants.
- `scripts/init_lovasz_run.py`: create the standard Lovasz run ledger skeleton before worker dispatch.
- `scripts/validate_lovasz_run.py`: reject incomplete Lovasz runs missing required ledgers, DAG, worker results, skeptic reviews, or partial-result closure fields.
- `scripts/validate_spawn_packet.py`: validate Lovasz spawn requests and worker result packets.
- `scripts/test_route.py`: deterministic routing regression tests.
- `scripts/witsoc.py`: unified CLI entrypoint for route/init/check/verify/status/artifacts/validation.
- `scripts/artifacts.py`: session artifact registry for generated WIT, Lean, SOC, logs, receipts, and proof worktrees.
- `scripts/validate_route_state.py`: reject invalid phase jumps or completion with required route phases still pending.
- `scripts/validate_generator_handoff.py`: reject Generator starts without a valid Explorer handoff and route authorization.
- `scripts/lint_wit_quality.py`: WIT quality lint for vague justifications, unresolved gaps, missing references, placeholders, and circular/self references.
- `scripts/generator_manifest.py`: create `generator_artifacts.json`, enforce target-hash consistency, and register Generator outputs.
- `scripts/score_lovasz_results.py`: score worker results by evidence quality, target fidelity, artifact status, and composability.
- `scripts/summarize_lovasz_run.py`: generate `lovasz_summary.json` and extract/update `barriers.md`.
- `scripts/validate_open_problem_run.py`: enforce actual lemma queue, disproof-first pressure, theorem-precondition audit, product selection, mutation ledger, failure memory, and dependency paths.
- `scripts/open_problem_report.py`: generate a human-readable open-problem report from Lovasz/Witsoc ledgers.
- `scripts/synthesize_open_ledgers.py`: synthesize draft actual-lemma, theorem-audit, mutation, product, and failure ledgers from research notes before validation.
- `scripts/decompose_problem.py`: break a frozen target into smaller proof-DAG nodes and actual-lemma queue entries while preserving target hash and dependency paths.
- `scripts/validate_proof_dag_integrity.py`: reject cyclic, dependency-missing, target-drifting, or unsupported accepted proof-DAG nodes.
- `scripts/spawn_workers_from_dag.py`: generate deterministic Lovasz worker spawn packets from the proof DAG and actual lemma queue.
- `scripts/lovasz_worker_dispatch.py`: enrich spawn packets with `.soc` repeat-risk checks and write a dispatch manifest.
- `scripts/lovasz_soc_memory.py`: initialize/query/update `lovasz.soc` with failed approaches, reusable insights, and imported failure JSONL.
- `scripts/result_ladder.py`: generate a tractable result ladder and `product_selection.json` for open-problem campaigns.
- `scripts/formalization_feasibility.py`: score WIT/Lean readiness and route weak targets back to Explorer/Lovasz repair.
- `scripts/counterexample_search.py`: generate bounded counterexample-search packets for graph, finite-model, SAT/SMT, number-theory, additive, Ramsey/extremal, finite-algebra, analysis, algebra, topology, and probability domains.
- `scripts/rank_mission_menu.py`, `scripts/select_barrier.py`, `scripts/select_best_product.py`, `scripts/stop_continue.py`, and `scripts/allocate_portfolio.py`: advisory decision-support algorithms. They rank options and explain tradeoffs; they never upgrade claim status or override the orchestrator.
- `scripts/rank_lovasz_dag.py`, `scripts/select_lovasz_mutation.py`, `scripts/rank_lovasz_results.py`, `scripts/lovasz_next_action.py`, and `scripts/lovasz_orchestrator_packet.py`: Lovasz advisory algorithms for proof-DAG priority, one-axis mutation choice, worker-result reportability, next action, and combined orchestrator state.
- `scripts/explorer_decision_packet.py` and `scripts/generator_decision_packet.py`: Explorer/Generator advisory packets for theorem/sketch/handoff ranking and artifact/repair ranking.
- `scripts/grade_witsoc_report.py`: grade report production quality from ledgers, artifacts, proof DAG, worker evidence, skeptic reviews, and formalization readiness.
- `scripts/lovasz_run_manifest.py`: create/update `lovasz_run.json`, the authoritative Lovasz phase manifest.
- `scripts/validate_lovasz_phase.py`: enforce Lovasz phase gates and allowed phase transitions.
- `scripts/status_lattice.py`: validate claim/product statuses and reject unsupported status upgrades.
- `scripts/explorer_return_packet.py`: generate `explorer_return_packet.json` with accepted products, demotions, remaining barriers, and recommended Explorer action.
- `references/schemas/lovasz-spawn-worker.schema.json`: strict schema for Lovasz worker spawn requests.
- `references/schemas/lovasz-worker-result.schema.json`: strict schema for Lovasz worker result packets.

## Routing

Use this WITSOC-specific routing table before choosing a subskill, model, or tool. Intake always starts at top-level `witsoc`; serious mathematical work then starts with Explorer.

| Task | WITSOC route |
|---|---|
| Simple math answer | Top-level `witsoc`; answer directly with a clear derivation. |
| Hard proof exploration | `witsoc-explorer`; Phase 0 profile the problem, freeze the exact target, triage solved/open/unconfirmed/false/under-specified status, map ontology, rank theorem candidates, run backward chaining, run falsification hierarchy, test obstructions/barriers, compare proof objects, EV-rank sketches, and produce `runs/<task>/handoff.json` plus strict `runs/<task>/handoff_v1.json` when Generator is needed. |
| Open problem / Erdős-style research problem | `witsoc-explorer` first. Explorer freezes the statement and status, then writes a Lovasz barrier packet if the target is open, unsolved, unconfirmed, frontier-level, or blocked. Lovasz attacks that packet and returns claims/barriers/gaps to Explorer. Explorer reviews and either sends a new barrier packet to Lovasz, demotes the target, stops honestly, or authorizes Generator for a narrow accepted result. |
| Deep run proving/disproving an open-style target | `witsoc-explorer` first, then mandatory `witsoc-research-lovasz`, then return to `witsoc-explorer` if Explorer cannot settle the target as solved/false/routine. A report that only says "open/unsupported by known results" is not complete unless Lovasz has already attempted barrier breaking and Explorer has reviewed Lovasz output, or the run records a concrete blocker preventing Lovasz dispatch. |
| Counterexample search | `witsoc-explorer` plus computation where useful; minimize and verify the counterexample before presenting it. |
| Premise / lemma discovery | `witsoc-explorer`; supply search and dependency planning. |
| WIT generation | `witsoc-explorer` first for nontrivial theorem targets, then `witsoc-generator` after Explorer accepts the frozen target and proof plan. Existing `.wit` inspection/repair can start at Generator. |
| User explicitly asks for WIT code | Explorer freezes and judges the target first unless this is an existing `.wit` repair. Generator is mandatory after Explorer accepts the target; it must produce a `.wit` artifact or report a concrete blocker. Do not answer with only exploration, prose, or Lean. |
| User asks for WIT code plus Lean proof | Explorer first, Generator second for routine accepted targets. For open/blocked targets, route Explorer -> Lovasz -> Explorer -> Generator. Generator must generate/check WIT, generate Lean from that frozen WIT target, attempt Lean verification, and report artifact paths plus exact WIT/Lean status. |
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
- Freeze the target before serious proof work and reject unexplained target-hash drift.
- Accept claims only through the claim acceptance contract.
- State the achieved quality level before final reporting.

Use internal `witsoc-explorer` first when the task is serious proof work, theorem proving, WIT/Lean generation, an open problem, an unsolved conjecture, or a research-like target. Explorer owns problem freezing, status triage, source trail, theorem-candidate ranking, counterexample pressure, proof-path selection, and final arbitration of whether Lovasz or Generator may proceed.

Use internal `witsoc-research-lovasz` only after Explorer has produced a barrier packet for an open, unsolved, unconfirmed, frontier-level, or blocked target. Lovasz owns barrier attack as a formal-verification-driven research director: barrier classification, proof-dependency DAG decomposition, worker dispatch for independent subproblems, WIT-before-Lean verification requirements, one-axis mutations, conjecture/lemma mining, reductions, special cases, conditional theorems, obstruction results, computational certificates, verification gates, and honest demotion of unsupported claims. Lovasz may spawn as many independent agents as the runtime, budget, and task warrant, provided each spawned agent has an exact DAG node or audit obligation and target-drift guardrails. Lovasz returns to Explorer; it does not decide that Generator may solve an open problem.

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

Generator is forbidden when the target is open/blocked and no Lovasz return packet exists, the accepted product is only a conjecture, target hashes disagree without a mutation record, Explorer has not authorized artifact generation, formalization feasibility is `POOR_FORMALIZATION_TARGET`, or the proof DAG has an open dependency needed for the claimed theorem. Load `references/core/generator_gate.md` before invoking Generator on nontrivial targets.

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

## Target And Claim Contracts

For serious mathematical work, load `references/core/target_freeze.md` and maintain a frozen target statement plus target hash. If the target changes, record the change in `target_mutation.json` or `target_mutations.jsonl` with old hash, new hash, mutation kind, reason, authorization, and whether it weakens the original.

A claim is accepted only if it satisfies `references/core/claim_acceptance.md`:

- exact statement,
- stable claim or DAG node id,
- matching target hash,
- dependency path to target,
- legal status transition,
- evidence receipt or checked artifact,
- skeptic review for strong claims,
- registered artifact when an artifact is cited.

Anything else is `OPEN`, `GAP`, `CONJECTURE`, `FAILED_ATTEMPT`, `REJECTED`, `PARTIAL`, or `CONDITIONAL`; do not report it as a full solution.

## Quality Levels

Use the quality levels from `references/core/production_gates.md`:

- `L0_DIRECT`: direct answer with reasoning.
- `L1_SKETCH`: informal proof/disproof sketch.
- `L2_CHECKED_DERIVATION`: deterministic calculation, bounded check, or structural check.
- `L3_WIT_ARTIFACT`: WIT artifact produced.
- `L4_WIT_LEAN_ATTEMPTED`: WIT plus Lean attempted.
- `L5_WIT_LEAN_VERIFIED`: WIT plus Lean/SafeVerify verified.
- `L6_RESEARCH_PRODUCT`: Lovasz research product with checked/verified artifacts and Explorer review.

The final answer must not imply a higher level than the run actually achieved.

## Open-Solution Discipline

For open, unsolved, unconfirmed, frontier-level, or blocked targets, load
`references/core/open_problem.md` and enforce its Open-Solution Protocol.
Lovasz campaigns must include statement freezing, adversarial proof breaking,
computational search where applicable, a proof-dependency DAG, separated worker
modes, failure taxonomy, and novelty accounting. A run that produces only a
polished partial sketch without these ledgers should be demoted to
`FAILED_ATTEMPT`, `CONJECTURE`, or `PARTIAL` rather than treated as an open
solution.

Before Lovasz worker dispatch, initialize a run directory:

```bash
INIT="$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/init_lovasz_run.py)"
python3 "$INIT" "$PLANE_SESSION_DIR/lovasz-run" --target "$FROZEN_TARGET"
```

## Witsoc Preflight

Before a mathematics, proof, WIT, Lean, open-problem, or research-style run is
reported complete, run the Witsoc route and handoff validators when the scripts
are available:

```bash
resolve_witsoc_script() {
  local rel="witsoc/scripts/$1"
  local resolved=""
  if [ -n "${PLANE_TOOL_BIN:-}" ]; then
    resolved="$("$PLANE_TOOL_BIN" skill-which "$rel" 2>/tmp/witsoc_skill_which.err || true)"
    if [ -n "$resolved" ] && [ -e "$resolved" ]; then
      printf "%s\n" "$resolved"
      return 0
    fi
  fi
  for base in \
    "${WITSOC_SKILL_DIR:-}" \
    "${KIMI_WORK_DIR:-}/.openscientist/skills/witsoc" \
    "${KIMI_WORK_DIR:-}/.openscientist/strings/skills/witsoc" \
    "${HOME:-}/.openscientist/strings/skills/witsoc"; do
    [ -n "$base" ] || continue
    if [ -e "$base/scripts/$1" ]; then
      printf "%s\n" "$base/scripts/$1"
      return 0
    fi
  done
  if [ -s /tmp/witsoc_skill_which.err ]; then
    printf "Witsoc script resolution failed for %s; skill-which stderr: %s\n" "$rel" "$(cat /tmp/witsoc_skill_which.err)" >&2
  fi
  return 1
}

WITSOC_PREFLIGHT_DIR="${PLANE_SESSION_DIR:-${KIMI_WORK_DIR:-$PWD}}"
ROUTER="$(resolve_witsoc_script route.py || true)"
if [ -n "$ROUTER" ]; then
  python3 "$ROUTER" --field json --state-out "$WITSOC_PREFLIGHT_DIR/witsoc_route_state.json" "${ORIGINAL_USER_TASK:-}" > "$WITSOC_PREFLIGHT_DIR/witsoc_route.json"
fi
VALIDATOR="$(resolve_witsoc_script validate_handoff.py || true)"
LOVASZ_RUN_VALIDATOR="$(resolve_witsoc_script validate_lovasz_run.py || true)"
ROUTE_STATE_VALIDATOR="$(resolve_witsoc_script validate_route_state.py || true)"
[ -z "$ROUTE_STATE_VALIDATOR" ] || [ ! -f "$WITSOC_PREFLIGHT_DIR/witsoc_route_state.json" ] || python3 "$ROUTE_STATE_VALIDATOR" "$WITSOC_PREFLIGHT_DIR/witsoc_route_state.json" --for-final-report > "$WITSOC_PREFLIGHT_DIR/witsoc_route_state.validate.log"
for HANDOFF in "$WITSOC_PREFLIGHT_DIR"/handoff*.json "${KIMI_WORK_DIR:-}"/runs/*/handoff*.json; do
  [ -f "$HANDOFF" ] || continue
  [ -z "$VALIDATOR" ] || python3 "$VALIDATOR" "$HANDOFF" > "$HANDOFF.validate.log"
done
for LOVASZ_RUN in "$WITSOC_PREFLIGHT_DIR"/lovasz-run "${KIMI_WORK_DIR:-}"/runs/*/lovasz-run; do
  [ -d "$LOVASZ_RUN" ] || continue
  [ -z "$LOVASZ_RUN_VALIDATOR" ] || python3 "$LOVASZ_RUN_VALIDATOR" "$LOVASZ_RUN" --mode deep > "$LOVASZ_RUN/validate_lovasz_run.log"
done
```

If `witsoc_route.json` contains `required_followup:
"witsoc-research-lovasz"`, do not complete a status-only open-problem report.
The run must contain Lovasz evidence such as `proof_dependency_dag`,
`worker_results`, or `lovasz_barrier_attack`, or a concrete
`lovasz_dispatch_blocker`, and Explorer must review Lovasz output before final
reporting or Generator authorization. If `witsoc_route_state.json` has
`generator_authorized: false`, Generator may not write a new artifact yet. If
WIT/Lean artifacts were generated, every proof must record the session-scoped
proof worktree used to generate it.

Every generated WIT, Lean, SOC, receipt, Lake log, proof worktree record, and
final report should be registered in `witsoc_artifacts.json`. Prefer:

```bash
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)" artifacts register path/to/artifact.wit --type wit --owner-phase witsoc-generator
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/witsoc.py)" artifacts list
```

The Witsoc plugin reads this registry first and uses filesystem scanning only
as fallback.

For Generator production readiness, run:

```bash
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_generator_handoff.py)" runs/<task>/handoff_v1.json --route-state "$PLANE_SESSION_DIR/witsoc_route_state.json"
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lint_wit_quality.py)" path/to/artifact.wit --json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/generator_manifest.py)" --manifest runs/<task>/generator_artifacts.json --artifact path/to/artifact.wit --type wit --target-hash "$FROZEN_TARGET_SHA256"
```

For Lovasz production readiness, run:

```bash
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_run_manifest.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_phase.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_soc_memory.py)" init runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/result_ladder.py)" runs/<task> --write
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/decompose_problem.py)" runs/<task> --write --out runs/<task>/problem_decomposition.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/synthesize_open_ledgers.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/counterexample_search.py)" runs/<task> --out runs/<task>/counterexample_search_templates.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_proof_dag_integrity.py)" runs/<task> --artifact-registry "$PLANE_SESSION_DIR/witsoc_artifacts.json"
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/spawn_workers_from_dag.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_worker_dispatch.py)" runs/<task> --write
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/status_lattice.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/score_lovasz_results.py)" runs/<task>/worker_results.json --registry "$PLANE_SESSION_DIR/witsoc_artifacts.json" --out runs/<task>/lovasz_result_scores.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/summarize_lovasz_run.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_run.py)" runs/<task> --artifact-registry "$PLANE_SESSION_DIR/witsoc_artifacts.json"
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_open_problem_run.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/formalization_feasibility.py)" runs/<task> --out runs/<task>/formalization_feasibility.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/open_problem_report.py)" runs/<task>
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/grade_witsoc_report.py)" runs/<task> --out runs/<task>/report_quality_grade.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/explorer_return_packet.py)" runs/<task> --out runs/<task>/explorer_return_packet.json
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/lovasz_run_manifest.py)" runs/<task> --phase EXPLORER_RETURN_READY
python3 "$("$PLANE_TOOL_BIN" skill-which witsoc/scripts/validate_lovasz_phase.py)" runs/<task>
```

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
5. For Lovasz-directed work, `scripts/validate_handoff.py` also enforces the Lovasz proof-DAG and worker-result invariants on `handoff.json`.
6. Generator reads only `handoff_v1.json`, writes the `.wit` artifact, and runs deterministic checks. Generator must not invent mathematical truth beyond the accepted handoff.
7. Rejections move the state to Repair or Explorer using `references/core/repair.md` and `references/core/failure_recovery.md`.
8. Generator records receipts when verifier verdicts are available and uses `references/core/lean_verification.md` if Lean is requested.

## Shared Protocols

Do not duplicate common rules in task-local prompts. For serious proof work, load the relevant shared protocols:

- Routing and subskill boundaries: `references/core/routing.md`.
- Target freeze and mutation: `references/core/target_freeze.md`.
- Claim acceptance: `references/core/claim_acceptance.md`.
- Artifact policy: `references/core/artifact_policy.md`.
- Generator gate: `references/core/generator_gate.md`.
- Production gates and quality levels: `references/core/production_gates.md`.
- Plugin integration: `references/core/plugin_integration.md`.
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
- After a structurally valid `.wit` proof artifact exists and Lean was not already requested, ask the user whether to generate a Lean 4 proof from that WIT proof and verify it with `lake build`.
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

Failure recovery routing:

- Lean syntax, import, namespace, or local context failure: Generator repair.
- WIT lint or structural failure: Generator repair.
- Missing mathematical lemma: Explorer repair, or Lovasz if it is an open/blocked barrier.
- DAG integrity failure: Lovasz repair.
- Target mismatch: Explorer target-freeze repair.
- Poor formalization feasibility: Explorer/Lovasz decomposition repair.
- Worker disagreement: skeptic review plus result merger.
- Repeated same failure class: apply `references/core/failure_recovery.md` before stopping.

Final status honesty:

- `VERIFIED` only if formal/verifier evidence supports it.
- `CHECKED` only for deterministic computation or structural checks.
- `PROVED_SKETCH` only for a coherent but not formal proof sketch.
- `PARTIAL` for special cases, bounds, reductions, conditionals, or computational products.
- `CONJECTURE` for evidence without proof.
- `FAILED_ATTEMPT` or `REJECTED` when appropriate.

Use user-safe verification labels in final reports:

- `STRUCTURE_OK`: `wit check` or equivalent structural validation passed.
- `CONTEXT_BUILT`: verifier context was generated; this is not semantic proof.
- `RECEIPT_ACCEPTED`: `.wit.receipt.json` exists and complete accepted verdicts cover the obligations.
- `LEAN_VERIFIED`: Lean/Lake verification passed and SafeVerify/target-freeze checks passed.
- `OPEN`, `GAP`, `PARTIAL`, `CONDITIONAL`, `CONJECTURE`, `FAILED_ATTEMPT`, or `REJECTED`: no full verified proof of the frozen target is available.

Do not write bare "verified" in user-facing text unless the sentence names the mechanism, such as `RECEIPT_ACCEPTED` or `LEAN_VERIFIED`.

Subskill boundaries:

- Explorer does not write final `.wit` except for very small tasks, and it arbitrates all Lovasz and Generator returns.
- Lovasz does not perform initial intake and does not route directly to Generator unless the top-level coordinator explicitly allows it for a verified narrow target.
- Generator avoids broad theorem search, does not upgrade claim status, and sends mathematical blockers back to Explorer.
- Top-level Witsoc coordinates the loop and decides when to return to Explorer.

## Before Final Answer

For serious mathematical, WIT, Lean, Lovasz, or Generator runs, apply `references/core/production_gates.md` before final response:

- route state checked,
- frozen target and target hash stated,
- target-hash consistency checked,
- accepted statuses justified by the claim acceptance contract,
- artifacts registered or paths shown,
- WIT/Lean status stated exactly,
- Lovasz return packet reviewed when Lovasz ran,
- Generator authorization checked when artifacts were generated,
- report grade or production gaps stated when Lovasz ran,
- achieved quality level stated.

Production complete only if there is no unexplained target mismatch, illegal status upgrade, accepted claim without evidence, unregistered cited artifact, skipped required Lovasz phase, or Generator handoff before Explorer authorization.

## Default Output

For a small math answer, provide the result and reasoning.

For a serious proof task, provide:

- exact theorem/problem interpretation,
- achieved quality level,
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

End every serious Witsoc response with this short artifact block, using `none`
or `not run` explicitly rather than omitting fields:

```text
Artifacts:
- WIT: <path|none>
- Lean: <path|none>
- Receipt: <path|none>
- Status: STRUCTURE_OK=<yes/no/not run>; CONTEXT_BUILT=<yes/no/not run>; RECEIPT_ACCEPTED=<yes/no/not run>; LEAN_VERIFIED=<yes/no/not run>
- Plugin: <opened/open failed/not attempted>
```

If Lean generation is requested, use internal `witsoc-generator`, prefer LSP/REPL/per-file checks during repair, and return Lean only after final `lake build` plus SafeVerify succeeds. If Lean repair is blocked, say `Lean code generation failed`.
