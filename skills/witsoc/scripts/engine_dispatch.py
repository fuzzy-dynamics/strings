#!/usr/bin/env python3
"""Phase 4 wiring: the REAL engine dispatcher for the research director.

`research_state.py` is the controller (bandit + state); this is the actuator. It maps
each approach to its real engine, shares a CONTEXT between approaches (premise_retrieval
adds imports the prover then uses; analogical_transfer sets bandit priors; conjecture
mining / construction search / speculative arena produce candidate bridges), and returns
a kernel-gated outcome with a rung. A campaign then = select_approach -> execute ->
record, looping until an honest stop.

CALIBRATION: every rung comes from a KERNEL-GATED engine result — the prover discharges
the goal (L6), a construction/conjecture is evaluator/kernel-CHECKED (L2), a
counterexample is a verified disproof (L1), a verified `H->T` reduction is L2, a
promoted bridge is L6. Informational approaches (retrieval, analogy) return L0 and only
enrich the context. The dispatcher never invents a rung; the controller never upgrades one.

The prover is injectable (`prover=`), so the dispatch logic is unit-tested without Lean;
the default shells `close_obligation.py --search` (the real kernel-gated prover).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import research_state as rs  # noqa: E402
import proof_search as ps    # noqa: E402  -- applicability checks (recursive_defs2, structural)
import witcore               # noqa: E402  -- live-library default for deep runs

# analogical-transfer technique -> the research-director approach that carries it out.
_TECH2APPROACH = {
    "generalize_the_invariant": "generalize_invariant",
    "multiplicativity_euler_product": "premise_retrieval",
    "probabilistic_method_alteration": "construction_search",
    "extremal_stability": "construction_search",
    "density_increment": "conjecture_mining",
    "minimal_counterexample_descent": "counterexample_search",
    "local_global_reduction": "speculative_arena",
    "double_counting_pigeonhole": "construction_search",
    "algebraization_spectral": "ontology_pivot",
}


def real_prover(lake_dir: Path | None = None, search: bool = True, timeout: int = 600,
                library: Path | None = None, search_max_nodes: int | None = None):
    """Shell the kernel-gated prover. When `library` is given the prover REUSES it
    (`--use-library` + value model) and HARVESTS discharged proofs into it
    (`--record-library`) — so a campaign compounds across problems and iterations.
    `search_max_nodes` caps the per-goal search so an open goal fails fast (the search
    reports BUDGET_EXHAUSTED) instead of dominating a campaign."""
    def prove(statement: str, imports: str = "") -> dict:
        # MATHLIB MODE: the emitted file needs the Mathlib import for the
        # narrowed ring/nlinarith candidates to resolve; campaign preambles
        # carry defs, not imports, so prepend it here (deep-run path only).
        if os.environ.get("WITSOC_LAKE_ENV") and "import Mathlib" not in imports:
            imports = ("import Mathlib.Tactic\n" + imports).strip()
        cmd = [sys.executable, str(SCRIPT_DIR / "close_obligation.py"),
               "--lean-statement", statement, "--out-ledger", "/dev/null"]
        if search:
            cmd.append("--search")
            if search_max_nodes is not None:
                cmd += ["--search-max-nodes", str(search_max_nodes)]
        if imports:
            cmd += ["--imports", imports]
        if lake_dir:
            cmd += ["--lake-dir", str(lake_dir)]
        if library is not None:
            cmd += ["--library", str(library), "--use-library", "--record-library"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            d = json.loads(r.stdout) if r.stdout.strip() else {}
        except Exception:
            d = {}
        return {"discharged": bool(d.get("discharged")), "proof": d.get("proof"),
                "label": d.get("label")}
    return prove


class EngineDispatcher:
    def __init__(self, lean_target: str, preamble: str = "", imports: str = "",
                 lake_dir: Path | None = None, domain: str = "other",
                 atlas: Path | None = None, prover=None):
        self.lean_target = lean_target
        self.preamble = preamble
        self.lake_dir = lake_dir
        self.domain = domain
        self.atlas = atlas
        # Deep runs (director campaigns) push into and reuse the LIVE knowledge
        # store by default, so results compound across runs and stay visible to
        # other agents. Inject `prover=` (tests) or real_prover(library=...) to
        # point elsewhere; WITSOC_HOME/WITSOC_LEMMA_LIBRARY redirect the store.
        self.prover = prover or real_prover(lake_dir, library=witcore.global_library())
        self.context = {"imports": imports, "premises": [], "bridges": [], "priors": {}}

    # --- shared helpers ---------------------------------------------------
    def _imports(self) -> str:
        base = self.preamble
        extra = self.context["imports"]
        return (base + ("\n" + extra if extra else "")).strip()

    def _prove_target(self) -> dict:
        return self.prover(self.lean_target, self._imports())

    @staticmethod
    def _solved(r: dict) -> dict:
        if r.get("discharged"):
            return {"rung": "L6", "status": "VERIFIED_LEAN", "evidence": r.get("proof"),
                    "partial": None}
        return {"rung": "L0", "status": "OPEN"}

    # --- approaches -------------------------------------------------------
    def execute(self, approach: str, target: str) -> dict:
        return getattr(self, f"_a_{approach}", self._a_unimplemented)()

    def _a_unimplemented(self) -> dict:
        return {"rung": "L0", "status": "not_implemented"}

    def _a_direct_prover(self) -> dict:
        return self._solved(self._prove_target())

    def _a_generalize_invariant(self) -> dict:
        if not (ps.recursive_defs2(self.preamble) and ps.generalization_candidates(self.lean_target, self.preamble)):
            return {"rung": "L0", "status": "not_applicable"}
        return self._solved(self._prove_target())

    def _a_structural_induction(self) -> dict:
        if not ps.structural_induction_candidates(self.lean_target, self.preamble):
            return {"rung": "L0", "status": "not_applicable"}
        return self._solved(self._prove_target())

    def _a_premise_retrieval(self) -> dict:
        try:
            import premise_retrieval as pr
            atlas = self.atlas or (SCRIPT_DIR / "core_lemma_atlas.json")
            pkt = pr.retrieve_packet(self.lean_target, atlas, self.lake_dir, validate=False)
        except Exception:
            return {"rung": "L0", "status": "retrieval_failed"}
        added = [i for i in pkt.get("recommended_imports", []) if i not in self.context["imports"]]
        if added:
            self.context["imports"] = (self.context["imports"] + "\n" + "\n".join(added)).strip()
        self.context["premises"] = pkt.get("retrieved_symbols", [])
        # informational: enriches context, does not itself advance the target.
        return {"rung": "L0", "status": "premises_retrieved", "evidence": pkt.get("retrieved_symbols")}

    def _a_analogical_transfer(self) -> dict:
        try:
            import analogical_transfer as at
            sugg = at.suggest(self.lean_target, self.domain)
        except Exception:
            return {"rung": "L0", "status": "analogy_failed"}
        for s in sugg:
            a = _TECH2APPROACH.get(s["technique"])
            if a:
                self.context["priors"][a] = self.context["priors"].get(a, 0.0) + s["relevance"]
        return {"rung": "L0", "status": "techniques_suggested",
                "evidence": [s["technique"] for s in sugg]}

    def _a_speculative_arena(self) -> dict:
        bridges = self.context.get("bridges") or []
        if not bridges:
            return {"rung": "L0", "status": "no_bridges"}
        try:
            import speculative_arena as sa
            rep = sa.explore(self.lean_target, bridges, self.prover, self._imports(), promote=True)
        except Exception:
            return {"rung": "L0", "status": "arena_failed"}
        if rep.get("promoted"):
            return {"rung": "L6", "status": "VERIFIED_LEAN",
                    "evidence": rep["promoted"].get("composed_target_proof")}
        if rep.get("sufficient_bridges"):
            return {"rung": "L2", "status": "CHECKED",
                    "partial": f"reduction: target follows from {rep['sufficient_bridges']}",
                    "barrier": {"kind": "sufficient_bridge", "bridges": rep["sufficient_bridges"]}}
        return {"rung": "L0", "status": "no_sufficient_bridge"}

    def _a_construction_search(self) -> dict:
        # only meaningful when a construction evaluator applies (e.g. a termination /
        # acyclicity claim). Generic targets: not applicable.
        spec = self.context.get("construction")
        if not spec:
            return {"rung": "L0", "status": "not_applicable"}
        try:
            import construction_search as cs
            res = cs.build(spec["evaluator"], spec.get("params", {}), 150, 24, 0)
        except Exception:
            return {"rung": "L0", "status": "construction_failed"}
        if res.get("certified"):
            return {"rung": "L2", "status": "CHECKED", "partial": "verified construction certificate",
                    "evidence": res.get("formalization_target")}
        return {"rung": "L0", "status": "no_construction"}

    def _a_conjecture_mining(self) -> dict:
        """Wired (was a `not_wired_here` stub the bandit kept paying for): mine
        empirical conjectures, rank by interestingness, formalize survivors, and
        feed the dispatchable ones into the shared context as ARENA BRIDGES and
        premises — so speculative_arena and the prover can use them. Mining is
        INFORMATIONAL for the target itself (L0): a mined lemma advances the
        rung only after the kernel-gated engines prove something with it."""
        if self.domain not in ("number_theory", "additive_combinatorics"):
            return {"rung": "L0", "status": "not_applicable"}
        if self.context.get("mined_bridges_done"):
            return {"rung": "L0", "status": "already_mined"}
        try:
            import conjecture_to_lemma_pipeline as cl
            conjectures = cl.mine(self.domain, 2, 600, 1500, 3)
            rep = cl.pipeline(conjectures, domain=self.domain, target_hash="conjecture_mining",
                              top=4, target_lean=self.lean_target, library=None,
                              range_size=600, formalizer=None, translators=None, threshold=0.4)
        except Exception:
            return {"rung": "L0", "status": "mining_failed"}
        added = []
        for node in rep.get("nodes", []):
            ls = node.get("lean_statement")
            if ls and ls not in [b.get("lean_statement") for b in self.context["bridges"]]:
                self.context["bridges"].append({"id": node.get("node_id"), "lean_statement": ls})
                added.append(node.get("node_id"))
        self.context["mined_bridges_done"] = True
        if not added:
            return {"rung": "L0", "status": "nothing_dispatchable",
                    "evidence": [f"ranked={rep.get('ranked_count', 0)}"]}
        # bridges feed the arena on its next selection — give it a prior bump.
        self.context["priors"]["speculative_arena"] = self.context["priors"].get("speculative_arena", 0.0) + 0.5
        return {"rung": "L0", "status": "conjectures_mined",
                "evidence": [f"bridges_added={added}",
                             f"ranked={rep.get('ranked_count', 0)}",
                             f"disproofs={len(rep.get('disproofs') or [])}"]}

    def _a_counterexample_search(self) -> dict:
        spec = self.context.get("counterexample")
        if not spec:
            return {"rung": "L0", "status": "not_applicable"}
        # a found witness disproves the target (L1); honest L0 otherwise.
        return {"rung": "L1", "status": "REFUTED", "evidence": spec} if spec.get("witness") else {"rung": "L0", "status": "no_counterexample"}

    def _a_ontology_pivot(self) -> dict:
        try:
            import ontology_pivot as op
            res = op.suggest(self.lean_target, self.domain)
        except Exception:
            return {"rung": "L0", "status": "pivot_failed"}
        self.context["pivots"] = res["pivots"]
        # informational: a pivot is a research direction (orthogonal-domain encoding),
        # not a result. It records leads for the campaign; it never advances the rung.
        return {"rung": "L0", "status": "pivots_suggested",
                "evidence": [p["target_domain"] for p in res["pivots"]]}

    def _a_invention(self) -> dict:
        """Invention Mode (definition_synthesis): when the campaign carries labeled
        example rows (context['invention'] = {rows, label_key, forbid?}), search the
        expression grammar for a separating invariant. INFORMATIONAL (L0): an
        invented definition is a CONJECTURE-grade research lead; it advances the
        rung only after a kernel-gated engine proves something with it."""
        spec = self.context.get("invention")
        if not (isinstance(spec, dict) and spec.get("rows") and spec.get("label_key")):
            return {"rung": "L0", "status": "not_applicable"}
        if self.context.get("invention_done"):
            return {"rung": "L0", "status": "already_invented"}
        try:
            import definition_synthesis as ds
            rep = ds.synthesize(spec["rows"], spec["label_key"],
                                forbid=tuple(spec.get("forbid", ())),
                                actual_barrier_lemma=str(spec.get("actual_barrier_lemma", "")))
        except Exception:
            return {"rung": "L0", "status": "invention_failed"}
        self.context["invention_done"] = True
        defs = rep.get("definitions", [])
        if not defs:
            return {"rung": "L0", "status": "no_separating_definition",
                    "evidence": [f"near_misses={len(rep.get('near_misses', []))}"]}
        self.context["invented_definitions"] = defs
        self.context["invented_lemma_candidates"] = rep.get("lemma_candidates", [])
        return {"rung": "L0", "status": "definitions_synthesized",
                "evidence": [f"{d['name']}: {d['expression']} {d['direction']} {d['threshold']}"
                             for d in defs[:3]]}

    def _a_finite_reduction(self) -> dict:
        """F1 finite-reduction arm (sat_backend + reduction_hunt): run the
        verified SAT backend on a finite encoding of the target or a barrier
        lemma. The encoding comes from context['finite_reduction'] =
        {encoder, params} when the campaign carries one, otherwise the arm
        SELF-SEEDS via reduction_hunt.detect over the target/preamble text. A
        CHECKED certificate (re-verified witness or checked refutation) is L2
        bounded evidence — the historically dominant route to machine-settled
        conjectures. The kernel bridge (close_obligation on the decidable Lean
        form) is the only path above L2."""
        spec = self.context.get("finite_reduction")
        if not (isinstance(spec, dict) and spec.get("encoder") and isinstance(spec.get("params"), dict)):
            spec = None
            try:
                import reduction_hunt as rh
                families = rh.detect(f"{self.lean_target} {self.preamble}")
            except Exception:
                families = []
            if families:
                if self.context.get("finite_reduction_done"):
                    return {"rung": "L0", "status": "already_checked"}
                result = rh.run_family(families[0], max_decisions=200_000, scan_cap=6)
                self.context["finite_reduction_done"] = True
                self.context["finite_reduction_hunt"] = result
                if result["dag_node_drafts"]:
                    evidence = [d["statement"] for d in result["dag_node_drafts"][:3]]
                    return {"rung": "L2", "status": "checked_bracket", "evidence": evidence}
                return {"rung": "L0", "status": "hunt_no_checked_fact",
                        "evidence": [str(result.get("next_escalation"))]}
            return {"rung": "L0", "status": "not_applicable"}
        if self.context.get("finite_reduction_done"):
            return {"rung": "L0", "status": "already_checked"}
        try:
            import sat_backend as sb
            encoder = str(spec["encoder"])
            params = spec["params"]
            if encoder == "ramsey":
                enc = sb.encode_ramsey(int(params["n"]), int(params.get("s", 3)), int(params.get("t", 3)))
            elif encoder == "vdw":
                enc = sb.encode_vdw(int(params["n"]), int(params.get("k", 3)))
            elif encoder == "schur":
                enc = sb.encode_schur(int(params["n"]))
            else:
                return {"rung": "L0", "status": "unknown_encoder"}
            outcome = sb.solve_internal(enc["num_vars"], enc["clauses"],
                                        int(spec.get("max_decisions", 200_000)))
        except Exception:
            return {"rung": "L0", "status": "finite_reduction_failed"}
        self.context["finite_reduction_done"] = True
        if outcome["result"] == "SAT":
            if not sb.verify_witness(enc["clauses"], outcome.get("witness") or {}):
                return {"rung": "L0", "status": "witness_verification_failed"}
            self.context["finite_reduction_certificate"] = {"result": "SAT", **{k: enc[k] for k in ("statement", "sat_means")}}
            return {"rung": "L2", "status": "checked_witness",
                    "evidence": [enc["sat_means"], f"witness re-verified over {len(enc['clauses'])} clauses"]}
        if outcome["result"] == "UNSAT":
            self.context["finite_reduction_certificate"] = {"result": "UNSAT", **{k: enc[k] for k in ("statement", "unsat_means")}}
            return {"rung": "L2", "status": "checked_refutation",
                    "evidence": [enc["unsat_means"], f"refutation={outcome.get('refutation')}"]}
        return {"rung": "L0", "status": "budget_exhausted",
                "evidence": [str(outcome.get("reason"))]}


def campaign(dispatcher: EngineDispatcher, target: str, max_steps: int = 12,
             state: dict | None = None) -> dict:
    """Drive a real campaign: pull bandit priors from the dispatcher's evolving context
    (so analogical_transfer steers later picks), select, execute, record.

    R4/L5: priors from the global knowledge store (mean reward per approach for
    this goal's SIGNATURE, learned from past campaigns) merge in under the
    context priors, and every outcome is recorded back — a structurally
    familiar target starts informed instead of uniform. Guarded throughout."""
    state = state or rs.new_state(target)
    state["sessions"] += 1
    try:
        import knowledge_store as ks
        learned = ks.priors_for(target)
    except Exception:
        ks, learned = None, {}
    for _ in range(max_steps):
        if state["status"] != "ACTIVE":
            break
        priors = {**learned, **(dispatcher.context.get("priors") or {})}
        approach = rs.select_approach(state, priors)
        if approach is None:
            state["status"] = "HONEST_STOP"
            break
        outcome = dispatcher.execute(approach, target)
        rs.record(state, approach, outcome)
        if ks is not None:
            try:
                ks.record_outcome(target, approach, rs.RUNG_REWARD.get(outcome.get("rung", "L0"), 0.0))
            except Exception:
                pass
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lean-target", required=True)
    ap.add_argument("--preamble", default="")
    ap.add_argument("--imports", default="")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--domain", default="other")
    ap.add_argument("--atlas", type=Path, default=None)
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--state", type=Path, default=None)
    ap.add_argument("--lovasz-run", type=Path, default=None,
                    help="Lovasz run dir (with lovasz_run.json) this campaign belongs to")
    ap.add_argument("--standalone", action="store_true",
                    help="explicit opt-out of the Lovasz run context (recorded in output)")
    args = ap.parse_args()

    # Ownership gate (references/core/services.md): the dispatcher is SOLVER
    # machinery — it runs inside a Lovasz campaign, not bare. The named run's
    # budget gate decides whether dispatch may proceed; charges land there too.
    if args.lovasz_run is None and not args.standalone:
        print(json.dumps({"error": "engine_dispatch is Lovasz-owned: pass --lovasz-run <dir> "
                                   "(with lovasz_run.json) or an explicit --standalone"}), file=sys.stderr)
        return 2
    import campaign_budget_gate as bg
    if args.lovasz_run is not None:
        if not (args.lovasz_run / "lovasz_run.json").exists():
            print(json.dumps({"error": f"no lovasz_run.json in {args.lovasz_run}; "
                                       "run lovasz_run_manifest.py first"}), file=sys.stderr)
            return 2
        gate = bg.check(args.lovasz_run)
        if not gate["dispatch_allowed"]:
            print(json.dumps({"error": "campaign budget gate blocks dispatch",
                              "required_action": gate["required_action"],
                              "escalation_level": gate["escalation_level"]}, indent=2))
            return 1

    # Campaigns (the deep-run entry point) default to MATHLIB MODE when a built
    # mathlib4 is on the host — the reach unlock for ring/nlinarith/decide.
    # WITSOC_CORE_ONLY=1 opts out; unit tests inject provers and are unaffected.
    lake_dir = witcore.enable_mathlib_mode(args.lake_dir)
    disp = EngineDispatcher(args.lean_target, args.preamble, args.imports, lake_dir, args.domain, args.atlas)
    st = rs.load(args.state) if (args.state and args.state.exists()) else None
    st = campaign(disp, args.lean_target, args.max_steps, st)
    if args.state:
        rs.save(args.state, st)
    if args.lovasz_run is not None:
        bg.charge(args.lovasz_run, attempts=1)
    print(json.dumps({"status": st["status"], "best_rung": st["best_rung"],
                      "dead_ends": st["dead_ends"], "partial_results": st["partial_results"],
                      "lovasz_run": str(args.lovasz_run) if args.lovasz_run else None,
                      "standalone": bool(args.standalone),
                      "ledger_tail": st["attempt_ledger"][-6:]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
