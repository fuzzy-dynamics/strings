#!/usr/bin/env python3
"""Ω4 dual informal/formal proving — `witsoc narrative`.

The Rethlas/Archon configuration — an informal reasoning agent constructing
the candidate argument plus a formal agent that decomposes it and
"autonomously fills nontrivial gaps" — is the published configuration that
actually SOLVED an open problem (commutative algebra, formally verified,
"essentially no human involvement"). Witsoc had both halves; this module is
the explicit narrative object connecting them:

  compose  the fleet writes the PROOF NARRATIVE for a goal: a strategy plus
           ordered steps, each with claim, justification, and named premise
           needs — with the problem theory and retrieval reflection embedded
           (steps the library cannot support get revised before any formal
           work starts);
  ground   the formal pass per step: formalize the claim (Nexus compiler-
           feedback loop), prove it (tiered prover, light→medium), feed
           unproved steps into the LEMMA POOL as bridging targets;
           statuses per step: SKETCHED -> FORMALIZED -> PROVED | GAPPED;
  status   the narrative scoreboard; a fully PROVED narrative is DAG-ready.

Honesty: a narrative is PROVED_SKETCH-grade scaffolding; only kernel verdicts
mark steps PROVED, and the narrative never touches node/claim statuses — it
PRODUCES proof-DAG candidates for the acceptance layer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

NARRATIVE_NAME = "narratives.json"


def _store(run: Path) -> dict:
    data = witcore.load_json(run / NARRATIVE_NAME, None)
    if isinstance(data, dict) and data.get("schema") == "witsoc.narratives.v1":
        return data
    return {"schema": "witsoc.narratives.v1", "narratives": {}}


def _save(run: Path, store: dict) -> None:
    witcore.save_json(run / NARRATIVE_NAME, store)


def _theory(run: Path) -> dict | None:
    try:
        import problem_theory as pt
        if pt.theory_path(run).exists():
            return pt.prompt_context(run)
    except Exception:
        pass
    return None


def compose(run: Path, goal: str, narrative_id: str = "main") -> dict:
    """The informal agent: strategy + steps with premise needs, retrieval-
    checked (unsupported needs revise the strategy via reflect)."""
    import sampler_fleet as sf
    fleet = sf.samplers()
    if not fleet:
        return {"composed": False, "reason": "no sampler fleet configured (the informal agent IS the fleet)"}
    reflection = None
    try:
        import retrieval_v2 as rv
        if rv.corpus_path().exists():
            reflection = rv.reflect(goal)
    except Exception:
        pass
    reply = witcore.run_sampler(fleet[0]["command"], {
        "task": "compose_proof_narrative",
        "goal": goal,
        "problem_theory": _theory(run) or {},
        "retrieval_reflection": ({"strategy": reflection.get("strategy"),
                                  "unsupported_needs": reflection.get("unsupported_needs")}
                                 if reflection else {}),
        "rules": "Return {strategy, steps: [{claim, justification, premises_needed}]} — a complete "
                 "informal proof: 3-8 steps, ONE mathematical move per step, every external fact in "
                 "premises_needed. Avoid steps whose needs the library reported unsupported.",
    })
    if not (isinstance(reply, dict) and reply.get("steps")):
        return {"composed": False, "reason": "fleet returned no usable narrative"}
    steps = []
    for i, s in enumerate(reply["steps"][:8], start=1):
        if not (isinstance(s, dict) and s.get("claim")):
            continue
        steps.append({"step_id": f"s{i}", "claim": str(s["claim"]),
                      "justification": str(s.get("justification") or ""),
                      "premises_needed": [str(p) for p in (s.get("premises_needed") or [])][:5],
                      "status": "SKETCHED", "lean_statement": None, "proof": None})
    store = _store(run)
    store["narratives"][narrative_id] = {
        "narrative_id": narrative_id, "goal": goal,
        "strategy": str(reply.get("strategy") or ""), "steps": steps,
        "note": "PROVED_SKETCH-grade scaffolding; only kernel verdicts mark steps PROVED",
    }
    _save(run, store)
    return {"composed": True, "narrative_id": narrative_id, "steps": len(steps),
            "strategy": store["narratives"][narrative_id]["strategy"]}


def ground(run: Path, narrative_id: str = "main", tier: str = "light",
           limit: int = 8) -> dict:
    """The formal agent: per SKETCHED step, formalize (Nexus loop) then prove
    (tiered); unproved formalized steps become lemma-pool bridging targets —
    the 'autonomously fill nontrivial gaps' mechanism."""
    store = _store(run)
    narrative = store["narratives"].get(narrative_id)
    if not narrative:
        raise SystemExit(f"no narrative {narrative_id!r}; run `witsoc narrative compose` first")
    import prover_tiers
    theory = _theory(run)
    worked = 0
    for step in narrative["steps"]:
        if worked >= limit or step["status"] not in ("SKETCHED", "FORMALIZED", "GAPPED"):
            continue
        worked += 1
        if not step["lean_statement"]:
            try:
                import nexus_loop as nx
                out = nx.fleet_formalize(step["claim"], theory=theory)
            except Exception:
                out = {"formalized": False}
            if out.get("formalized"):
                step["lean_statement"] = out["lean_statement"]
                step["status"] = "FORMALIZED"
            else:
                step["status"] = "GAPPED"
                step["gap"] = "formalization: " + str(out.get("reason") or "no elaborating statement")
                continue
        record = prover_tiers.prove(str(step["lean_statement"]), tier=tier, theory=theory,
                                    name=f"narr_{narrative_id}_{step['step_id']}")
        if record.get("discharged"):
            step["status"] = "PROVED"
            step["proof"] = record["proof"]
            step["via"] = record.get("via")
        else:
            step["status"] = "GAPPED"
            step["gap"] = f"proof: {record.get('label')}"
            try:
                import lemma_pool as lp
                lp.propose(run, str(step["lean_statement"]),
                           origin=f"narrative:{narrative_id}:{step['step_id']}")
            except Exception:
                pass
    _save(run, store)
    return status(run, narrative_id)


def status(run: Path, narrative_id: str = "main") -> dict:
    store = _store(run)
    narrative = store["narratives"].get(narrative_id)
    if not narrative:
        raise SystemExit(f"no narrative {narrative_id!r}")
    counts: dict[str, int] = {}
    for s in narrative["steps"]:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    proved_all = counts.get("PROVED", 0) == len(narrative["steps"]) and narrative["steps"]
    return {"narrative_id": narrative_id, "goal": narrative["goal"],
            "strategy": narrative["strategy"], "steps": len(narrative["steps"]),
            "by_status": counts, "fully_proved": bool(proved_all),
            "gaps": [{"step": s["step_id"], "gap": s.get("gap")} for s in narrative["steps"]
                     if s["status"] == "GAPPED"],
            "dag_ready": ("every step kernel-proved: emit DAG nodes through the acceptance layer"
                          if proved_all else "gaps remain; the lemma pool holds the bridging targets")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_c = sub.add_parser("compose")
    p_c.add_argument("run_dir", type=Path)
    p_c.add_argument("--goal", required=True)
    p_c.add_argument("--id", default="main")
    p_g = sub.add_parser("ground")
    p_g.add_argument("run_dir", type=Path)
    p_g.add_argument("--id", default="main")
    p_g.add_argument("--tier", choices=("light", "medium", "heavy"), default="light")
    p_s = sub.add_parser("status")
    p_s.add_argument("run_dir", type=Path)
    p_s.add_argument("--id", default="main")
    args = ap.parse_args()
    if args.cmd == "compose":
        result = compose(args.run_dir, args.goal, args.id)
    elif args.cmd == "ground":
        result = ground(args.run_dir, args.id, args.tier)
    else:
        result = status(args.run_dir, args.id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
