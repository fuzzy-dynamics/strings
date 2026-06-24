#!/usr/bin/env python3
"""Layer 1: foundation triage — bound the in-principle walls, never pretend to
defeat them.

A cheap, deterministic classifier run in Explorer BEFORE a Lovasz campaign. It
flags targets whose KNOWN structure is independence / large-cardinal-consistency /
undecidable-or-infeasible, and routes them to a terminal `FOUNDATION_OUTCOMES`
state (INDEPENDENT / RELATIVE_CONSISTENCY / INFEASIBLE, see witcore.py) so a
campaign is not wasted on a theorem that cannot be proved in the working
foundation.

Hard guarantees (structural, not prose):
  * It can NEVER discharge / solve / upgrade. The only outputs are an advisory
    flag and a terminal NON-solve. `is_solve` is always False.
  * A terminal foundation outcome is reachable ONLY behind `human_gate=true` AND a
    written `independence_argument`. Without both it is `NEEDS_HUMAN_GATE`
    (advisory) — never auto-terminal, never auto-solved.
  * It is CONSERVATIVE: only explicit, well-known markers flag. A merely hard or
    open problem (Erdős–Straus, odd perfect, Collatz, RH, ...) does NOT flag — it
    is left for the normal campaign. This preserves calibration: ambiguity
    resolves toward "not a foundation outcome", i.e. keep working / do not claim.

Usage:
  foundation_triage.py "<statement>" [--human-gate]
      [--independence-argument "<text>"] [--route-spec route_spec.json] [--out J]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402  -- FOUNDATION_OUTCOMES vocabulary

MIN_ARGUMENT_LEN = 40  # an independence_argument must be a real paragraph, not "yes"

# (regex, outcome, marker label). Order = priority for the headline outcome.
# Every pattern names a SPECIFIC, well-established independence/undecidability
# result. Generic words like "open" / "unknown" / "hard" deliberately do NOT
# appear here.
MARKERS: list[tuple[str, str, str]] = [
    # --- INDEPENDENT of ZFC ---
    (r"continuum hypothesis", "INDEPENDENT", "continuum hypothesis"),
    (r"\bgeneralized continuum hypothesis\b|\bGCH\b", "INDEPENDENT", "GCH"),
    (r"2\s*\^\s*\{?\\?aleph_?\s*0\}?\s*=\s*\\?aleph_?\s*1", "INDEPENDENT", "2^aleph0 = aleph1"),
    (r"cardinality of (the )?(reals|continuum)", "INDEPENDENT", "cardinality of the continuum"),
    (r"whitehead (problem|conjecture)", "INDEPENDENT", "Whitehead problem"),
    (r"suslin('?s)? (hypothesis|problem|line)", "INDEPENDENT", "Suslin hypothesis"),
    (r"kurepa('?s)? (hypothesis|tree)", "INDEPENDENT", "Kurepa hypothesis"),
    (r"borel conjecture", "INDEPENDENT", "Borel conjecture"),
    (r"diamond principle|◇", "INDEPENDENT", "diamond principle"),
    (r"martin'?s axiom", "INDEPENDENT", "Martin's axiom"),
    (r"independent of (ZF|ZFC)\b", "INDEPENDENT", "stated independent of ZFC"),
    (r"undecidable in (ZF|ZFC)\b", "INDEPENDENT", "stated undecidable in ZFC"),
    (r"neither provable nor disprovable", "INDEPENDENT", "neither provable nor disprovable"),
    # --- RELATIVE CONSISTENCY / consistency strength ---
    (r"con\(\s*(ZFC?|PA)\s*\)", "RELATIVE_CONSISTENCY", "Con(theory)"),
    (r"consistency of (ZF|ZFC|PA|Peano)", "RELATIVE_CONSISTENCY", "consistency of a theory"),
    (r"consistency strength", "RELATIVE_CONSISTENCY", "consistency strength"),
    (r"(inaccessible|measurable|weakly compact|strongly compact|supercompact|woodin|huge) cardinal",
     "RELATIVE_CONSISTENCY", "large cardinal"),
    (r"large cardinal", "RELATIVE_CONSISTENCY", "large cardinal"),
    (r"g[öo]del'?s? (second )?incompleteness", "RELATIVE_CONSISTENCY", "Gödel incompleteness"),
    # --- INFEASIBLE: undecidable / no-algorithm / resource-impossible ---
    (r"halting problem", "INFEASIBLE", "halting problem"),
    (r"hilbert'?s tenth", "INFEASIBLE", "Hilbert's tenth problem"),
    (r"word problem for (groups|semigroups|monoids)", "INFEASIBLE", "word problem (groups)"),
    (r"entscheidungsproblem", "INFEASIBLE", "Entscheidungsproblem"),
    (r"busy beaver|\bBB\(\s*\d", "INFEASIBLE", "busy beaver"),
    (r"g[öo]del sentence", "INFEASIBLE", "Gödel sentence"),
    (r"this (statement|sentence) is (not provable|unprovable)", "INFEASIBLE", "self-referential unprovable"),
    (r"no algorithm (exists|decides|can decide)", "INFEASIBLE", "no decision algorithm"),
    (r"\bundecidable problem\b", "INFEASIBLE", "undecidable problem"),
]

OUTCOME_PRIORITY = {"INDEPENDENT": 3, "RELATIVE_CONSISTENCY": 2, "INFEASIBLE": 1}


def classify(statement: str) -> dict:
    text = statement or ""
    hits: list[dict] = []
    for pattern, outcome, label in MARKERS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append({"outcome": outcome, "marker": label})
    if not hits:
        return {"flagged": False, "candidate_outcome": None, "markers": []}
    headline = max(hits, key=lambda h: OUTCOME_PRIORITY.get(h["outcome"], 0))["outcome"]
    return {"flagged": True, "candidate_outcome": headline, "markers": hits}


def triage(statement: str, *, human_gate: bool = False, independence_argument: str | None = None,
           route_difficulty: str | None = None) -> dict:
    cls = classify(statement)
    soft = (route_difficulty == "likely_undecidable")
    flagged = cls["flagged"] or soft

    result = {
        "schema": "witsoc.foundation_triage.v1",
        "statement": statement,
        "is_solve": False,  # structural: this tool can never solve
        "flagged": flagged,
        "candidate_outcome": cls["candidate_outcome"],
        "markers": cls["markers"],
        "soft_signal_only": (soft and not cls["flagged"]),
        "human_gate": bool(human_gate),
        "independence_argument": independence_argument,
        "terminal_status": None,
        "recommended_action": None,
    }

    if not flagged:
        result["recommended_action"] = "proceed_to_campaign"  # not a foundation wall
        return result

    arg_ok = bool(independence_argument) and len(independence_argument.strip()) >= MIN_ARGUMENT_LEN
    if cls["candidate_outcome"] is None:
        # soft signal only — never enough to terminate; route to human review.
        result["recommended_action"] = "human_review_difficulty"
        return result
    if human_gate and arg_ok:
        # The ONLY path to a terminal foundation outcome. Terminal, never upgrades.
        result["terminal_status"] = cls["candidate_outcome"]
        result["recommended_action"] = "terminal_foundation_outcome"
    else:
        result["recommended_action"] = "human_gate_required"
        result["gate_reason"] = (
            "needs human_gate=true and a written independence_argument "
            f"(>= {MIN_ARGUMENT_LEN} chars) before a terminal foundation outcome")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("statement", nargs="*", help="target statement (or stdin)")
    ap.add_argument("--human-gate", action="store_true")
    ap.add_argument("--independence-argument", default=None)
    ap.add_argument("--route-spec", type=Path, default=None, help="route_spec.json to read difficulty")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    statement = " ".join(args.statement).strip() or sys.stdin.read().strip()
    route_difficulty = None
    if args.route_spec and args.route_spec.exists():
        spec = witcore.load_json(args.route_spec, {})
        route_difficulty = (spec.get("route_spec") or spec).get("difficulty")

    result = triage(statement, human_gate=args.human_gate,
                    independence_argument=args.independence_argument,
                    route_difficulty=route_difficulty)

    # Structural safety net: a terminal status must be a real foundation outcome.
    if result["terminal_status"] and result["terminal_status"] not in witcore.FOUNDATION_OUTCOMES:
        result["terminal_status"] = None
        result["recommended_action"] = "error_invalid_outcome"

    if args.out:
        witcore.save_json(args.out, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # exit 0 always: triage is advisory, not a pass/fail gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
