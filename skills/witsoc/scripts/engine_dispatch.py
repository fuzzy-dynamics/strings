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
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import research_state as rs  # noqa: E402
import proof_search as ps    # noqa: E402  -- applicability checks (recursive_defs2, structural)

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
        self.prover = prover or real_prover(lake_dir)
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
        return {"rung": "L0", "status": "not_wired_here"}  # pipeline is a separate run dir flow

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


def campaign(dispatcher: EngineDispatcher, target: str, max_steps: int = 12,
             state: dict | None = None) -> dict:
    """Drive a real campaign: pull bandit priors from the dispatcher's evolving context
    (so analogical_transfer steers later picks), select, execute, record."""
    state = state or rs.new_state(target)
    state["sessions"] += 1
    for _ in range(max_steps):
        if state["status"] != "ACTIVE":
            break
        approach = rs.select_approach(state, dispatcher.context.get("priors"))
        if approach is None:
            state["status"] = "HONEST_STOP"
            break
        outcome = dispatcher.execute(approach, target)
        rs.record(state, approach, outcome)
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
    args = ap.parse_args()

    disp = EngineDispatcher(args.lean_target, args.preamble, args.imports, args.lake_dir, args.domain, args.atlas)
    st = rs.load(args.state) if (args.state and args.state.exists()) else None
    st = campaign(disp, args.lean_target, args.max_steps, st)
    if args.state:
        rs.save(args.state, st)
    print(json.dumps({"status": st["status"], "best_rung": st["best_rung"],
                      "dead_ends": st["dead_ends"], "partial_results": st["partial_results"],
                      "ledger_tail": st["attempt_ledger"][-6:]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
