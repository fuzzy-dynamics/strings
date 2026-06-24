#!/usr/bin/env python3
"""F4 attackability scoring — `witsoc attackability`.

"Named frontier conjecture" spans everything from problems that fall to a
finite reduction plus verified search, to problems whose missing idea has
eluded everyone. The first machine solve comes from the attackable end — so
problem selection must be strategic, not sentimental. This scorer ranks
portfolio entries by deterministic attackability signals:

  finite_reduction   does reduction_hunt detect a finite-reducible signature
                     in the statement? (the historically decisive route)
  formalization      is there a frozen lean_target, and do mined-predicate
                     statements expand through the predicate registry?
  technique_density  how many technique-atlas/curated analogies fire on the
                     statement (transfer proximity)
  literature         does a literature ledger exist, is it fresh, and does it
                     show recent activity (live techniques)?
  computation_domain is the domain one where verified computation bites?

Scores allocate ATTENTION (which problem gets the frontier_attack slot and
the campaign budget); they never say anything about truth or difficulty
ground-truth. The output names the missing signal for every low scorer —
"raise it by running literature triage / registering predicates / finding a
finite reduction" — so scoring doubles as a worklist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import portfolio as pf  # noqa: E402

COMPUTATION_DOMAINS = {"combinatorics", "graph_theory", "extremal", "additive_combinatorics",
                       "number_theory", "ramsey_theory"}

# A6 selection v2: the two empirically validated predictors join the weights —
# AlphaEvolve "success correlated inversely with prior literature effort"
# (scarcity) and "performed best on variational optimization problems"
# (variational formulability). Tao's boundary rule lives in the optional
# per-entry `boundary_fraction` field (an Explorer estimate of how much of the
# proof existing techniques already cover).
WEIGHTS = {"finite_reduction": 0.30, "formalization": 0.20,
           "technique_density": 0.10, "literature": 0.10, "computation_domain": 0.10,
           "literature_scarcity": 0.10, "variational": 0.10}

_VARIATIONAL_RE = __import__("re").compile(
    r"\b(maximum|minimum|maximal|minimal|largest|smallest|least|greatest|extremal|"
    r"at most|at least|upper bound|lower bound|optimi[sz]|longest|shortest|densest|fewest)\b",
    __import__("re").IGNORECASE)


def _text(p: dict) -> str:
    return " ".join(str(p.get(k) or "") for k in ("title", "informal", "lean_target", "domain"))


def score_problem(p: dict, max_age_days: int = 90) -> dict:
    signals: dict[str, float] = {}
    advice: list[str] = []

    try:
        import reduction_hunt as rh
        families = rh.detect(_text(p))
    except Exception:
        families = []
    signals["finite_reduction"] = 1.0 if families else 0.0
    if not families:
        advice.append("no finite-reducible signature detected; hunt for a finite reduction "
                      "(reduction pivot, compactness, quantifier elimination)")

    lean = bool(p.get("lean_target"))
    signals["formalization"] = 1.0 if lean else 0.0
    if not lean:
        advice.append("no frozen lean_target; formalize the statement or register its "
                      "predicates (witsoc predicates register)")

    try:
        from analogical_transfer import suggest
        hints = suggest(str(p.get("lean_target") or p.get("informal") or ""),
                        str(p.get("domain") or ""), k=5)
    except Exception:
        hints = []
    signals["technique_density"] = min(1.0, len(hints) / 3.0)
    if not hints:
        advice.append("no technique-atlas analogy fires; seed the atlas "
                      "(witsoc mathlib-autopsy) or grow it via proof autopsies")

    try:
        import literature_engine as le
        ledger = le.ledger_for(str(p.get("id")))
    except Exception:
        ledger = None
    if ledger is None:
        signals["literature"] = 0.0
        advice.append("no literature ledger; run `witsoc literature triage` for this problem")
    else:
        import time
        age_days = (int(time.time()) - int(ledger.get("checked_epoch", 0))) / 86400
        fresh = age_days <= max_age_days
        recent = sum(1 for s in ledger.get("sources", [])
                     if str(s.get("year", "0")).isdigit() and int(s["year"]) >= 2020)
        signals["literature"] = (0.5 if fresh else 0.2) + min(0.5, recent * 0.1)
        if not fresh:
            advice.append(f"literature ledger is {age_days:.0f} days old; re-triage before campaigning")

    signals["computation_domain"] = 1.0 if str(p.get("domain")) in COMPUTATION_DOMAINS else 0.0

    # scarcity needs a FRESH ledger to mean anything: an unstudied problem
    # with a dated triage scores high; no ledger = unknown, not a bonus.
    if ledger is None:
        signals["literature_scarcity"] = 0.0
    else:
        sources = len(ledger.get("sources", []))
        signals["literature_scarcity"] = 1.0 if sources <= 3 else (0.5 if sources <= 10 else 0.1)

    signals["variational"] = 1.0 if _VARIATIONAL_RE.search(_text(p)) else 0.0
    if not signals["variational"]:
        advice.append("not variational as stated; look for an equivalent extremal/optimization "
                      "formulation (the empirically winning shape)")
    boundary = p.get("boundary_fraction")
    if isinstance(boundary, (int, float)) and 0 <= boundary <= 1:
        # Tao's boundary rule as a multiplier peaked near 0.9: techniques
        # covering ~90% with a real gap left is the winnable regime.
        signals["boundary_factor"] = round(1.0 - abs(0.9 - float(boundary)), 3)

    total = round(sum(WEIGHTS[k] * v for k, v in signals.items() if k in WEIGHTS), 4)
    if "boundary_factor" in signals:
        total = round(total * (0.5 + 0.5 * signals["boundary_factor"]), 4)
    return {"id": p.get("id"), "tier": p.get("tier"), "domain": p.get("domain"),
            "attackability": total,
            "signals": {k: round(v, 3) for k, v in signals.items()},
            "raise_it_by": advice,
            "finite_families_detected": [f["encoder"] for f in families]}


def rank(data: dict, max_age_days: int) -> dict:
    scored = [score_problem(p, max_age_days) for p in data["problems"]
              if p.get("tier") != "frozen_calibration"]
    scored.sort(key=lambda r: -r["attackability"])
    return {
        "schema": "witsoc.attackability.v1",
        "ranking": scored,
        "frontier_candidates": [r["id"] for r in scored[:3] if r["attackability"] >= 0.5],
        "note": ("attackability allocates attention and campaign budget only — it says nothing "
                 "about truth. The first machine solve comes from the attackable end; load the "
                 "frontier_attack tier accordingly."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--portfolio", type=Path, default=pf.DEFAULT_PORTFOLIO)
    ap.add_argument("--max-age-days", type=int, default=90)
    args = ap.parse_args()
    data = pf.load(args.portfolio)
    print(json.dumps(rank(data, args.max_age_days), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
