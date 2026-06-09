#!/usr/bin/env python3
"""Phase 6: curriculum-fed portfolios for autonomous campaigns.

A difficulty-graded LADDER feeds the flywheel: attack the easy rungs first, harvest
their verified proofs into the shared library, and the hard target compounds on them.
This turns a target (or a conjunction / a list of sub-lemmas) into an ordered portfolio
that `autonomous_campaign.run` consumes — easy rungs first, the full target last.

Ordering: a cheap structural difficulty heuristic by default (no Lean needed); with
`--grade` it uses the REAL prover budgets (`curriculum.difficulty_of`) to rank rungs by
the search budget that closes them. Calibration is untouched — the campaign still only
reaches SOLVED at a kernel-verified L6, and rungs are proved, never asserted.

Usage:
  curriculum_portfolio.py --target-lean "A ∧ B ∧ C" [--preamble P] [--sublemma S ...]
      [--domain D] [--grade] [--out portfolio.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import curriculum  # noqa: E402  -- split_top_level_and + difficulty_of


def difficulty_heuristic(stmt: str) -> int:
    """Cheap proxy for hardness: token count + weighted logical/arithmetic operators."""
    toks = len(re.findall(r"\S+", stmt))
    ops = sum(stmt.count(o) for o in ("∀", "∃", "→", "↔", "∧", "∨", "*", "^", "%"))
    return toks + 3 * ops


def build_portfolio(target_lean: str, sublemmas: list[str] | None = None, preamble: str = "",
                    domain: str = "other", graded_budgets: list[int] | None = None) -> list[dict]:
    rungs = [r.strip() for r in (sublemmas or curriculum.split_top_level_and(target_lean)) if r.strip()]
    rungs = [r for r in rungs if r != target_lean.strip()]
    if graded_budgets:
        graded = [((curriculum.difficulty_of(r, preamble, graded_budgets).get("difficulty") or 10 ** 9), r)
                  for r in rungs]
    else:
        graded = [(difficulty_heuristic(r), r) for r in rungs]
    graded.sort(key=lambda x: x[0])

    portfolio = [{"id": f"rung{i + 1}", "lean_target": r, "preamble": preamble, "domain": domain,
                  "difficulty": d}
                 for i, (d, r) in enumerate(graded)]
    portfolio.append({"id": "target", "lean_target": target_lean, "preamble": preamble, "domain": domain})
    return portfolio


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target-lean", required=True)
    ap.add_argument("--preamble", default="")
    ap.add_argument("--sublemma", action="append", default=[])
    ap.add_argument("--domain", default="other")
    ap.add_argument("--grade", action="store_true", help="rank rungs by real prover budget (needs Lean)")
    ap.add_argument("--budget", default="20,80,300")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    budgets = [int(b) for b in args.budget.split(",")] if args.grade else None
    portfolio = build_portfolio(args.target_lean, args.sublemma or None, args.preamble, args.domain, budgets)
    out = {"schema": "witsoc.curriculum_portfolio.v1", "target": args.target_lean,
           "rungs": len(portfolio) - 1, "portfolio": portfolio,
           "note": "feed `portfolio` to autonomous_campaign; easy rungs harvest into the library so the "
                   "hard target compounds. Rungs are proved (kernel), never asserted."}
    if args.out:
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
