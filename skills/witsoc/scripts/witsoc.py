#!/usr/bin/env python3
"""Unified Witsoc command-line entrypoint.

R0 architecture: every tool belongs to exactly one GROUP — the structural map
the flat scripts/ directory does not show. Files stay flat on disk (the
external `skill-which witsoc/scripts/<name>.py` resolution contract depends on
it); the grouping is the authoritative logical layout:

  engines    strategy-free services: input in, certificate/result out
  campaign   Lovasz-owned solver machinery: loops, dispatch, budgets, evolution
  knowledge  the stores: atlases, libraries, ledgers, registries
  gates      honesty: validators, skeptics, audits, claim protocols
  core       run substrate: WIT cycle, routing, artifacts, the run ledger

Invocation: `witsoc <cmd>` (flat, backwards compatible), `witsoc <group> <cmd>`
(grouped), `witsoc <group>` (list a group), `witsoc map` (whole architecture),
`witsoc services` (the boundary-contract registry).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

# The structural map (R0). One group per tool; `witsoc map` prints it and the
# flat passthrough is derived from it, so a tool cannot exist outside the map.
GROUPS: dict[str, dict[str, str]] = {
    "engines": {
        "prove": "close_obligation.py",
        "tiered-prove": "prover_tiers.py",
        "sat": "sat_backend.py",
        "opt": "opt_backend.py",
        "reduction-hunt": "reduction_hunt.py",
        "counterexample-search": "counterexample_search.py",
        "construction-search": "construction_search.py",
        "formula-synthesis": "formula_synthesis.py",
        "definition-synthesis": "definition_synthesis.py",
        "lemma-repair": "lemma_repair.py",
        "evolve": "program_evolve.py",
        "conjecture-pipeline": "conjecture_to_lemma_pipeline.py",
        "speculative-arena": "speculative_arena.py",
        "analogical-transfer": "analogical_transfer.py",
        "interestingness": "interestingness.py",
        "ontology-pivot": "ontology_pivot.py",
        "concept-generator": "concept_generator.py",
        "domain-barrier-lemmas": "domain_barrier_lemmas.py",
        "goal-structure": "goal_structure.py",
        "pose-variants": "pose_variants.py",
        "discovery-lift": "discovery_lift.py",
        "proof-autopsy": "proof_autopsy.py",
        "formalization-feasibility": "formalization_feasibility.py",
        "fleet": "sampler_fleet.py",
    },
    "campaign": {
        "next": "next_action.py",
        "bus-apply": "bus_apply_replies.py",
        "engine-dispatch": "engine_dispatch.py",
        "campaign": "autonomous_campaign.py",
        "research-campaign": "research_campaign.py",
        "flywheel": "flywheel.py",
        "portfolio": "portfolio.py",
        "curriculum-portfolio": "curriculum_portfolio.py",
        "attackability": "attackability.py",
        "lovasz-manifest": "lovasz_run_manifest.py",
        "budget-gate": "campaign_budget_gate.py",
        "gap-feedback": "proof_gap_to_barrier_feedback.py",
        "spawn-workers": "spawn_workers_from_dag.py",
        "worker-dispatch": "lovasz_worker_dispatch.py",
        "lovasz-prover-dispatch": "lovasz_prover_dispatch.py",
        "decompose-problem": "decompose_problem.py",
        "sketch-tournament": "sketch_tournament.py",
        "sketch-population": "sketch_population.py",
        "ideate": "ideate.py",
        "run": "campaign_driver.py",
        "theory": "problem_theory.py",
        "nexus": "nexus_loop.py",
        "dialectic": "dialectic.py",
        "cluster": "cluster_campaign.py",
        "pool": "lemma_pool.py",
        "narrative": "informal_proof.py",
        "self-play": "self_play.py",
        "rediscovery": "rediscovery_benchmark.py",
        "battery": "prover_battery.py",
        "olympiad": "olympiad.py",
        "open-rungs": "open_rungs.py",
        "rung-saturation": "rung_saturation.py",
        "barrier-attack": "barrier_attack.py",
        "lovasz-top-tier": "lovasz_top_tier.py",
        "lovasz-agent-packets": "lovasz_agent_packets.py",
        "open-frontier": "open_frontier.py",
        "result-ladder": "result_ladder.py",
        "soc-memory": "lovasz_soc_memory.py",
        "blueprint": "blueprint_campaign.py",
        "synthesize-ledgers": "synthesize_open_ledgers.py",
        "explorer-return": "explorer_return_packet.py",
        "open-problem-report": "open_problem_report.py",
        "summarize-lovasz": "summarize_lovasz_run.py",
    },
    "knowledge": {
        "decide": "decision_ledger.py",
        "fc-ingest": "formal_conjectures_ingest.py",
        "memory": "knowledge_store.py",
        "retrieve": "retrieval_v2.py",
        "bank": "proof_bank.py",
        "tactics": "tactic_ngrams.py",
        "atlas": "theorem_atlas.py",
        "library": "lemma_library.py",
        "predicates": "predicate_registry.py",
        "literature": "literature_engine.py",
        "novelty": "novelty_triage.py",
        "discoveries": "discovery_ledger.py",
        "mathlib-autopsy": "mathlib_autopsy.py",
    },
    "gates": {
        "validate-route-state": "validate_route_state.py",
        "validate-run": "validate_lovasz_run.py",
        "validate-generator-handoff": "validate_generator_handoff.py",
        "validate-open-problem": "validate_open_problem_run.py",
        "validate-dag-integrity": "validate_proof_dag_integrity.py",
        "validate-lovasz-phase": "validate_lovasz_phase.py",
        "validate-prover": "validate_prover_result.py",
        "validate-math-solve": "validate_mathematical_solve.py",
        "validate-lean-receipt": "validate_lean_receipt.py",
        "solve-claim": "solve_claim_protocol.py",
        "refute-deterministic": "refute_deterministic.py",
        "status-lattice": "status_lattice.py",
        "score-lovasz": "score_lovasz_results.py",
        "grade-report": "grade_witsoc_report.py",
        "lint-wit": "lint_wit_quality.py",
    },
    "core": {
        "bus": "request_bus.py",
        "controller": "witsoc_controller.py",
        "init": "init.sh",
        "check": "check.sh",
        "verify": "verify.sh",
        "context": "context.sh",
        "status": "status.sh",
        "artifacts": "artifacts.py",
        "package": "generator_package.py",
        "generator-manifest": "generator_manifest.py",
        "ledger": "run_ledger.py",
    },
}

# Boundary contract (references/core/services.md): witsoc exposes SERVICES —
# deterministic, certificate-emitting, strategy-free engines — and Lovasz is
# the solver that decides what to call and when. `witsoc services` prints this
# registry. role: service = callable engine; solver = Lovasz-owned campaign
# machinery (requires a Lovasz run context or an explicit --standalone);
# validator = honesty/audit gate; scheduler = portfolio-level launcher.
SERVICES = {
    "prove": {"script": "close_obligation.py", "role": "service",
              "contract": "kernel-gated prover; emits proof or honest OBLIGATION_OPEN"},
    "ledger": {"script": "run_ledger.py", "role": "service",
               "contract": "R1 unified run ledger: one run.sqlite3, nodes as the single entity; "
                           "ingest/status/nodes/consistency/export — validators as queries"},
    "memory": {"script": "knowledge_store.py", "role": "service",
               "contract": "R4 knowledge substrate: global cross-run failure memory (L4) + bandit "
                           "priors by goal signature (L5) + the P4 compounding surface "
                           "(`context` assembles .soc/sqlite memory into bus requests; `flow` is "
                           "the is-the-flywheel-turning gauge); attention only, never trust"},
    "decide": {"script": "decision_ledger.py", "role": "service",
               "contract": "P2 options-not-orders: live option tables (techniques + L5 priors + L4 "
                           "failure warnings + decision track record, with a recommended default) and "
                           "the decision ledger whose resolved outcomes feed the priors; attention "
                           "only — contracts are never decision points"},
    "fc-ingest": {"script": "formal_conjectures_ingest.py", "role": "service",
                  "contract": "P2 breadth intake: index google-deepmind/formal-conjectures (1.9k "
                              "research statements) with honest context/solved-in-literature flags and "
                              "attention-only attackability; portfolio emission is review-gated, never "
                              "auto-merged"},
    "next": {"script": "next_action.py", "role": "service",
             "contract": "THE one next action for an orchestrator (bus -> gate -> seed -> crank -> "
                         "finalize, with the exact command); sequencing advice only, never truth — "
                         "the answer to the turn-discipline failure mode"},
    "run": {"script": "campaign_driver.py", "role": "solver",
            "contract": "R5 campaign driver: one turn of the Lovasz crank (budget -> in-process "
                        "dispatch -> gap feedback -> theory update -> L2 re-ideation -> L6 "
                        "serendipity cap -> escalation -> ledger); --finalize = production gates"},
    "theory": {"script": "problem_theory.py", "role": "solver",
               "contract": "A1 problem theory: the living causal model (formulations, example zoo, "
                           "enemy profile, failure mechanisms, main attack); every loop must diff it; "
                           "prompt-context feeds every fleet request"},
    "nexus": {"script": "nexus_loop.py", "role": "solver",
              "contract": "A3 Nexus loop: fleet proposals iterate against real Lean compiler "
                          "diagnostics (prove + formalize); deterministic saturation first; kernel "
                          "replay is the only acceptance"},
    "dialectic": {"script": "dialectic.py", "role": "solver",
                  "contract": "A2 Lakatos engine: failed nodes become kernel-gated refutation "
                              "targets; witnesses and exhausted searches both feed the enemy profile"},
    "evolve": {"script": "program_evolve.py", "role": "service",
               "contract": "A4 program-space construction evolution: fleet-mutated construct(n) "
                           "programs, exploit-hardened exact evaluators, parametric scoring, "
                           "independent re-verification of records"},
    "cluster": {"script": "cluster_campaign.py", "role": "solver",
                "contract": "A6 cluster campaigns: pose variants, attack the family under one "
                            "shared theory, transfer every outcome (proved rungs, refutations)"},
    "rediscovery": {"script": "rediscovery_benchmark.py", "role": "validator",
                    "contract": "A7 rediscovery benchmark: hidden-answer grading of the solving "
                                "machinery; WRONG_VALUE = soundness alarm, calibration rows must stay OPEN"},
    "olympiad": {"script": "olympiad.py", "role": "service",
                 "contract": "local-first olympiad fast lane: profile domain/style, run bounded "
                             "kernel-gated proving, and fall back to Lovasz on failure"},
    "open-rungs": {"script": "open_rungs.py", "role": "service",
                   "contract": "rung-first open-problem target builder; emits special cases, "
                               "bounded searches, reductions, and obstruction targets without "
                               "upgrading the original open problem"},
    "rung-saturation": {"script": "rung_saturation.py", "role": "service",
                        "contract": "deterministic open-problem rung saturation: expands seed rungs, "
                                    "domain barriers, and formal probes into scored OPEN obligations"},
    "barrier-attack": {"script": "barrier_attack.py", "role": "solver",
                       "contract": "Lovasz V2 barrier campaign prep: named barriers + saturated rungs "
                                   "merged into the DAG/lemma queue; mutations are one-axis and untrusted"},
    "lovasz-top-tier": {"script": "lovasz_top_tier.py", "role": "validator",
                        "contract": "top-tier Lovasz preparation/audit: barrier core, rung saturation, "
                                    "hole-free Lean, strict roles, failure memory, novelty discipline, "
                                    "solve protocol, engine portfolio, loop learning, rediscovery, and "
                                    "success metrics"},
    "lovasz-agent-packets": {"script": "lovasz_agent_packets.py", "role": "validator",
                             "contract": "strict packet templates/validation for Builder, Destroyer, "
                                         "Reducer, Formalizer, Historian, Strategist, and Skeptic roles; "
                                         "coordination only, never trust promotion"},
    "open-frontier": {"script": "open_frontier.py", "role": "solver",
                      "contract": "open-problem novelty and solve-escalation workbench: packages "
                                  "candidate products, records novelty bundles, registers checked "
                                  "evidence, and reports solve-claim gate status"},
    "retrieve": {"script": "retrieval_v2.py", "role": "service",
                 "contract": "Ω3 retrieval v2: hierarchy-informalized corpus, two-stage "
                             "retrieve+rerank, GLOBAL premise sets, sketch-retrieve-reflect; the "
                             "prover consumes it automatically when a corpus exists"},
    "pool": {"script": "lemma_pool.py", "role": "solver",
             "contract": "Ω2 lemma pool: propose/mine (real residual diagnostics)/prove-pending/"
                         "reuse; PROVED = kernel verdict, harvested into the library; intractable "
                         "abandoned with evidence"},
    "tiered-prove": {"script": "prover_tiers.py", "role": "service",
                     "contract": "Ω1 tiered proving: light/medium/heavy budgets; external SOTA "
                                 "adapters via WITSOC_PROVER_FLEET, every adapter proof kernel-replayed"},
    "narrative": {"script": "informal_proof.py", "role": "solver",
                  "contract": "Ω4 dual informal/formal proving (Rethlas/Archon shape): compose the "
                              "informal narrative, ground it step-by-step (formalize + tiered prove), "
                              "gaps feed the lemma pool; PROVED_SKETCH-grade scaffolding"},
    "self-play": {"script": "self_play.py", "role": "solver",
                  "contract": "Ω5/Ω9 self-play: frontier-calibrated conjecture rounds (STP band "
                              "steering) + the prover/attacker formalization game generating "
                              "verified corpus; kernel verdicts on both sides"},
    "bank": {"script": "proof_bank.py", "role": "service",
             "contract": "Ω6 proof bank: kernel-gated simplification before archiving + the "
                         "signature-matched few-shot surface every Nexus prompt embeds"},
    "tactics": {"script": "tactic_ngrams.py", "role": "service",
                "contract": "W3 tactic n-grams: sequences mined from verified proofs by goal "
                            "signature; the prover consumes them automatically as candidates"},
    "opt": {"script": "opt_backend.py", "role": "service",
            "contract": "W4 ILP/SDP: exact branch-and-bound ILP (OPTIMAL/INFEASIBLE = exhaustive, "
                        "budget stop = honest UNKNOWN) + sdp-round (numeric -> rational -> exact "
                        "PSD via flag-algebra elimination); external solvers slot in when installed"},
    "validate-prover": {"script": "validate_prover_result.py", "role": "validator",
                        "contract": "maps prover labels to legal statuses; never upgrades"},
    "premises": {"script": "premise_retrieval.py", "role": "service",
                 "contract": "atlas retrieval + per-symbol Lean resolution; never assumes a premise exists"},
    "techniques": {"script": "analogical_transfer.py", "role": "service",
                   "contract": "technique retrieval by goal-signature overlap; search priors only, never trust"},
    "fleet": {"script": "sampler_fleet.py", "role": "service",
              "contract": "F2 sampler fleet over the cmd: bridge; wide untrusted generation, "
                          "everything born OPEN_UNFALSIFIED — verification is the only filter. "
                          "With no cmd fleet configured, falls back to the Intelligence Bus "
                          "(the orchestrator IS the fleet)"},
    "bus": {"script": "request_bus.py", "role": "service",
            "contract": "P0 Intelligence Bus: engines emit self-contained typed requests; the "
                        "ORCHESTRATOR (any harness, interactive or scheduled) fulfills and re-runs. "
                        "No credentials/network in witsoc; replies are OPEN_UNFALSIFIED candidates, "
                        "never a status upgrade; pending-request ceiling is a runaway backstop"},
    "bus-apply": {"script": "bus_apply_replies.py", "role": "validator",
                  "contract": "kernel-replays fulfilled Intelligence Bus proof replies and merges only "
                              "checked evidence into worker/DAG state; replies never self-upgrade"},
    "mathlib-autopsy": {"script": "mathlib_autopsy.py", "role": "service",
                        "contract": "F2 technique mining from Lean source trees into the global atlas; "
                                    "provenance mathlib_source, retrieval hints only"},
    "counterexample": {"script": "counterexample_search.py", "role": "service",
                       "contract": "bounded counterexample-search packets with recorded bounds"},
    "sat": {"script": "sat_backend.py", "role": "service",
            "contract": "verified SAT certificates: re-verified witness or checked refutation of a "
                        "finite instance (ramsey/vdw/schur/graph-coloring/covering/dimacs, "
                        "cube-and-conquer via --cubes); CHECKED-grade only, kernel bridge via --prove"},
    "reduction-hunt": {"script": "reduction_hunt.py", "role": "service",
                       "contract": "detect finite-reducible signatures in a frozen target, scan instance "
                                   "families to a witness/refutation bracket, emit DAG node drafts; "
                                   "CHECKED-grade only"},
    "construct": {"script": "construction_search.py", "role": "service",
                  "contract": "evolutionary object search over registered deterministic evaluators"},
    "formalize": {"script": "formalization_feasibility.py", "role": "service",
                  "contract": "WIT/Lean readiness scoring; routes weak targets back, never proves"},
    "predicates": {"script": "predicate_registry.py", "role": "service",
                   "contract": "W1 formalization bridge: predicate->Lean registry; mined conjectures "
                               "are dispatchable Lean by construction, unregistered = honest blocker"},
    "blueprint": {"script": "blueprint_campaign.py", "role": "service",
                  "contract": "F3 blueprint formalization campaign: persistent obligation ledger from a "
                              "proof DAG, dependency-ordered dispatch, theory-gap (library-campaign) mode"},
    "novelty": {"script": "novelty_triage.py", "role": "service",
                "contract": "is-it-new verdicts; metadata only, never a trust upgrade; default external "
                            "checker = the literature engine's arXiv probe (match=KNOWN, no-match=UNCHECKED)"},
    "literature": {"script": "literature_engine.py", "role": "service",
                   "contract": "F4 literature loop: arXiv search, dated per-problem source ledgers, "
                               "staleness gate, novelty probe; offline = honest network_unavailable"},
    "attackability": {"script": "attackability.py", "role": "service",
                      "contract": "F4 strategic problem selection: deterministic attackability signals "
                                  "(finite reduction, formalization, technique density, literature); "
                                  "allocates attention only"},
    "skeptic-check": {"script": "refute_deterministic.py", "role": "validator",
                      "contract": "deterministic adversarial refutation; demote-only"},
    "atlas": {"script": "theorem_atlas.py", "role": "service",
              "contract": "read-only reference store; promote is the only writer"},
    "library": {"script": "lemma_library.py", "role": "service",
                "contract": "live read-write lemma store with trust tiers"},
    "discoveries": {"script": "discovery_ledger.py", "role": "validator",
                    "contract": "durable claim ledger; publishable = kernel-grade AND novel AND human-gated"},
    "budget-gate": {"script": "campaign_budget_gate.py", "role": "validator",
                    "contract": "L3 campaign budget + one-way escalation ladder; owns the campaign block"},
    "gap-feedback": {"script": "proof_gap_to_barrier_feedback.py", "role": "validator",
                     "contract": "L1 failure classification + one-axis mutation contract for re-dispatch"},
    "validate-math-solve": {"script": "validate_mathematical_solve.py", "role": "validator",
                            "contract": "F0 stage-1 audit: all DAG nodes closed, skeptic fleet, no gaps; "
                                        "precondition for a solve claim, never a reportable solve"},
    "solve-claim": {"script": "solve_claim_protocol.py", "role": "validator",
                    "contract": "F0 frontier solve gate: audit + formal receipt + independent "
                                "re-derivation + novelty; only SOLVE_ACCEPTED is reportable"},
    "validate-lean-receipt": {"script": "validate_lean_receipt.py", "role": "validator",
                              "contract": "rejects Lean ENV_CHECK_ONLY/placeholder output; "
                                          "VERIFIED_LEAN requires explicit theorem code, hashes, "
                                          "and SafeVerify/faithfulness evidence"},
    "engine-dispatch": {"script": "engine_dispatch.py", "role": "solver",
                        "contract": "research-director actuator; Lovasz-owned, needs run context or --standalone"},
    "campaign": {"script": "autonomous_campaign.py", "role": "solver",
                 "contract": "portfolio flywheel; Lovasz-owned, needs run context or --standalone"},
    "research-campaign": {"script": "research_campaign.py", "role": "scheduler",
                          "contract": "nightly portfolio pass; launches Lovasz-context campaigns per problem"},
}


def run_script(script: str, args: list[str]) -> int:
    path = SCRIPT_DIR / script
    if script.endswith(".py"):
        cmd = [sys.executable, str(path), *args]
    else:
        cmd = ["bash", str(path), *args]
    return subprocess.call(cmd)


def flat_passthrough() -> dict[str, str]:
    """The flat command table, derived from GROUPS. A name colliding across
    groups would be a structural bug — fail loudly, never shadow silently."""
    flat: dict[str, str] = {}
    for group, commands in GROUPS.items():
        for cmd, script in commands.items():
            if cmd in flat and flat[cmd] != script:
                raise SystemExit(f"witsoc GROUPS collision: {cmd!r} maps to both "
                                 f"{flat[cmd]!r} and {script!r}")
            flat[cmd] = script
    return flat


def print_map() -> None:
    import json
    print(json.dumps({
        "schema": "witsoc.architecture.v1",
        "layout": "files flat on disk (skill-which contract); GROUPS is the logical structure",
        "reference": "references/core/architecture.md",
        "groups": {g: sorted(cmds) for g, cmds in GROUPS.items()},
        "counts": {g: len(cmds) for g, cmds in GROUPS.items()},
    }, indent=2, ensure_ascii=False))


def main() -> int:
    passthrough = flat_passthrough()
    argv = sys.argv[1:]

    if argv and argv[0] == "services":
        import json
        print(json.dumps({"schema": "witsoc.services.v1",
                          "boundary": "witsoc never decides strategy; Lovasz never verifies itself",
                          "reference": "references/core/services.md",
                          "services": SERVICES}, indent=2, ensure_ascii=False))
        return 0
    if argv and argv[0] == "map":
        print_map()
        return 0
    if argv and argv[0] in {"run-open", "finalize", "validate-all"}:
        return run_script("witsoc_controller.py", [argv[0], *argv[1:]])
    # grouped invocation: `witsoc <group> <cmd> args...` / `witsoc <group>` lists
    if argv and argv[0] in GROUPS:
        group = GROUPS[argv[0]]
        if len(argv) == 1:
            import json
            print(json.dumps({"group": argv[0], "commands": dict(sorted(group.items()))}, indent=2))
            return 0
        if argv[1] in group:
            return run_script(group[argv[1]], argv[2:])
        print(f"unknown command {argv[1]!r} in group {argv[0]!r}; "
              f"available: {', '.join(sorted(group))}", file=sys.stderr)
        return 2
    # flat invocation (backwards compatible)
    if argv and argv[0] in passthrough:
        return run_script(passthrough[argv[0]], argv[1:])

    parser = argparse.ArgumentParser(prog="witsoc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route")
    p_route.add_argument("prompt", nargs="*")
    p_route.add_argument("--field", choices=["route", "announcement", "reason", "chain", "confidence", "state", "json"], default="json")
    p_route.add_argument("--state-out", default=None)
    p_route.add_argument("--no-state", action="store_true")

    for cmd in passthrough:
        sub.add_parser(cmd)

    args = parser.parse_args()

    if args.cmd == "route":
        route_args = ["--field", args.field]
        if args.state_out:
            route_args += ["--state-out", args.state_out]
        if args.no_state:
            route_args += ["--no-state"]
        route_args += args.prompt
        return run_script("route.py", route_args)
    if args.cmd in passthrough:
        return run_script(passthrough[args.cmd], [])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
