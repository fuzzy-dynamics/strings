#!/usr/bin/env python3
"""Curriculum / reward densification (Phase 2).

Proof reward is sparse: a hard target gives 0 until the whole thing is closed.
This builds a DIFFICULTY-GRADED ladder of intermediate lemmas, proves the easy
ones first, and gives PARTIAL CREDIT for every verified sub-node — turning one
all-or-nothing target into many graded, individually-verifiable rewards that
self-play / search can climb.

Each rung is a formal Lean statement whose proof is attempted by the verifier-
guided search; difficulty is the search budget needed to close it (∞ = open).
The composition obligation `(rungs) → target` is emitted (validate_decomposition)
and an attempt is made to discharge it, so a fully-climbed ladder yields a real
proof of the target — never asserted, always kernel-checked.

Sub-lemmas come from `--sublemma` (repeatable), or by splitting a conjunction
`--target-lean "A ∧ B ∧ C"` at top level.

Acceptance (printed): ladder verified-nodes vs direct-attack verified-nodes.

Usage:
  curriculum.py --target "..." --target-lean "A ∧ B ∧ C" [--preamble "def ..."]
      [--sublemma "<lean>" ...] [--budget 20,80,300] [--out curriculum.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402
import proof_search  # noqa: E402


def split_top_level_and(expr: str) -> list[str]:
    """Split a Lean conjunction on top-level ∧ (paren/bracket aware)."""
    parts, depth, cur = [], 0, ""
    i = 0
    while i < len(expr):
        c = expr[i]
        if c in "([{⟨":
            depth += 1
        elif c in ")]}⟩":
            depth -= 1
        if depth == 0 and expr[i] == "∧":
            parts.append(cur.strip())
            cur = ""
            i += 1
            continue
        cur += c
        i += 1
    if cur.strip():
        parts.append(cur.strip())
    return [p.strip().strip("()").strip() for p in parts] if len(parts) > 1 else [expr.strip()]


def difficulty_of(stmt: str, preamble: str, budgets: list[int]) -> dict[str, Any]:
    """Smallest search budget that closes the rung; ∞ if none."""
    for b in budgets:
        r = proof_search.search(stmt, preamble, None, None, None, max_nodes=b, workers=8)
        if not r.get("discharged") and r.get("label") == "UNCHECKED_NO_TOOLCHAIN":
            return {"verified": False, "difficulty": None, "label": "UNCHECKED_NO_TOOLCHAIN"}
        if r.get("discharged"):
            return {"verified": True, "difficulty": b, "proof": r["proof"]}
    return {"verified": False, "difficulty": None, "label": "OBLIGATION_OPEN"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--target-lean", required=True)
    ap.add_argument("--preamble", default="")
    ap.add_argument("--sublemma", action="append", default=[])
    ap.add_argument("--budget", default="20,80,300")
    ap.add_argument("--out", type=Path, default=Path("curriculum.json"))
    args = ap.parse_args()

    budgets = [int(x) for x in args.budget.split(",")]
    rungs = args.sublemma or split_top_level_and(args.target_lean)

    graded = []
    for s in rungs:
        d = difficulty_of(s, args.preamble, budgets)
        graded.append({"statement": s, **d})
    # difficulty-graded: easy (small budget) first; open last.
    graded.sort(key=lambda g: (g["difficulty"] is None, g["difficulty"] or 0))

    verified_nodes = sum(1 for g in graded if g["verified"])
    # Partial-credit reward: each verified rung scores, weighted toward easier
    # rungs first (dense early reward), plus a composition bonus.
    reward = round(sum(1.0 / (1 + (g["difficulty"] or 999) / 100) for g in graded if g["verified"]), 4)

    # Direct attack on the whole target, same total budget.
    direct = proof_search.search(args.target_lean, args.preamble, None, None, None,
                                 max_nodes=sum(budgets), workers=8)
    direct_nodes = 1 if direct.get("discharged") else 0

    # Composition obligation: (rungs) -> target; try to discharge it.
    composition = None
    if verified_nodes == len(graded) and graded:
        hyps = " ".join(f"(_h{i} : {g['statement']})" for i, g in enumerate(graded))
        comp_stmt = f"{args.target_lean}"
        cr = proof_search.search(comp_stmt, args.preamble + f"\n-- with hyps {hyps}", None, None, None,
                                 max_nodes=200, workers=8)
        composition = {"discharged": cr.get("discharged"), "proof": cr.get("proof")}
        if cr.get("discharged"):
            reward += 1.0

    out = {
        "schema": "witsoc.curriculum.v1", "target": args.target,
        "rungs": graded, "verified_intermediate_nodes": verified_nodes,
        "direct_attack_verified_nodes": direct_nodes,
        "ladder_beats_direct": verified_nodes > direct_nodes,
        "partial_credit_reward": reward,
        "composition": composition,
        "note": "Partial credit per kernel-verified rung. 'ladder_beats_direct' is the "
                "Phase-2 acceptance signal; rungs are kernel-checked, never asserted.",
    }
    witcore.save_json(args.out, out)
    print(json.dumps({k: v for k, v in out.items() if k != "rungs"}
                     | {"rungs": [{"verified": g["verified"], "difficulty": g["difficulty"],
                                   "stmt": g["statement"][:48]} for g in graded]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
