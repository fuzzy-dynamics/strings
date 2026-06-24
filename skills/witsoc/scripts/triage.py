#!/usr/bin/env python3
"""Target triage + foundation-aware routing (Tiers D & E).

"Solve all open problems" is impossible (undecidability, incompleteness,
independence, proof-length). The practical consequence is that compute must be
*routed*: don't run a prover forever on a statement that is likely independent of
the foundation, or chase a proof whose minimal length is astronomical. This tool
classifies a target and recommends a route, and it treats independence /
infeasibility as legitimate terminal outcomes rather than failures.

Classes (heuristic — flagged as such, never asserted):
  DECIDABLE_FINITE    bounded/finite claim -> discovery search or certified SMT/SAT
  LIKELY_PROVABLE     a finitely-checkable or formalizable theorem -> prove pipeline
  LIKELY_INDEPENDENT  resisted both proof and disproof + set-theoretic signals
                      -> attempt relative-consistency / independence (outcome class)
  LIKELY_INFEASIBLE   explicit astronomical bound / proof-length signal -> record, do
                      not burn compute

Evidence (optional, from the run dir): disproof_first.json, formalization_*,
conjectures.json, obligation ledgers, proof_dependency_dag.json.

Usage:
  triage.py --target "for all n>=2, 4/n = 1/x+1/y+1/z" [--run-dir DIR] [--out triage.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

FINITE_SIGNALS = [r"\bfor all n\s*(<=|≤|<)\s*\d", r"\bn\s*(<=|≤|<)\s*\d", r"\bfinite\b",
                  r"\bbounded\b", r"\bsmall case", r"\bup to\b", r"≤\s*\d+", r"\bmod\b"]
INDEPENDENCE_SIGNALS = [r"\bZFC\b", r"\bcontinuum\b", r"\bcardinal", r"\bevery set\b",
                        r"\baxiom of choice\b", r"\bmeasurable\b", r"\bforcing\b", r"\bultrafilter\b"]
INFEASIBLE_SIGNALS = [r"\bRamsey\b.*\bR\(\s*[6-9]", r"10\^\{?\d{3,}", r"Ackermann", r"TREE\(\d"]


def hits(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    t = args.target
    finite = hits(FINITE_SIGNALS, t)
    independence = hits(INDEPENDENCE_SIGNALS, t)
    infeasible = hits(INFEASIBLE_SIGNALS, t)

    # Evidence from a run dir, if provided.
    ev: dict[str, Any] = {}
    if args.run_dir:
        dp = witcore.records(args.run_dir / "disproof_first.json")
        ev["disproof_attempts"] = len(dp)
        ev["disproof_found_counterexample"] = any(
            str(r.get("outcome", "")).lower().startswith("counterexample") for r in dp)
        obligations = witcore.records(args.run_dir / "formalization_obligations.json")
        ev["obligations_open"] = sum(1 for o in obligations if o.get("label") == "OBLIGATION_OPEN")
        ev["obligations_discharged"] = sum(1 for o in obligations if o.get("proof_discharged") or o.get("discharged"))
        conj = witcore.load_json(args.run_dir / "conjectures.json", {})
        ev["unfalsified_conjectures"] = conj.get("open_unfalsified", 0) if isinstance(conj, dict) else 0
        dag = witcore.records(args.run_dir / "proof_dependency_dag.json")
        ev["disproof_and_proof_both_failed"] = (
            ev.get("disproof_attempts", 0) > 0 and not ev.get("disproof_found_counterexample")
            and ev.get("obligations_open", 0) > 0 and ev.get("obligations_discharged", 0) == 0)

    # Decide (priority: infeasible > independent > finite > provable).
    if infeasible:
        cls, route, outcome = "LIKELY_INFEASIBLE", ["record_infeasible"], "INFEASIBLE"
    elif independence and ev.get("disproof_and_proof_both_failed"):
        cls, route, outcome = "LIKELY_INDEPENDENT", ["independence_probe"], "RELATIVE_CONSISTENCY"
    elif independence:
        cls, route, outcome = "LIKELY_INDEPENDENT", ["prove", "independence_probe"], "INDEPENDENT"
    elif finite:
        cls, route, outcome = "DECIDABLE_FINITE", ["discovery_or_smt", "recheck"], None
    else:
        cls, route, outcome = "LIKELY_PROVABLE", ["autoformalize", "decompose", "prove", "recheck"], None

    result = {
        "schema": "witsoc.triage.v1",
        "target": t,
        "classification": cls,
        "recommended_route": route,
        "terminal_outcome_if_stuck": outcome,
        "signals": {"finite": finite, "independence": independence, "infeasible": infeasible},
        "evidence": ev,
        "note": "Heuristic routing, not a proof of class. INDEPENDENT/RELATIVE_CONSISTENCY/"
                "INFEASIBLE are legitimate terminal outcomes, not failures.",
    }
    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
