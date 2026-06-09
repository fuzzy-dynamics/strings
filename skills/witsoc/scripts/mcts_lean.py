#!/usr/bin/env python3
"""Value-guided best-first tactic-state search over a Lean REPL (Phase 1).

This drives an external Lean REPL/checker (``--repl-cmd`` / ``WITSOC_LEAN_REPL_CMD``)
that, given a partial tactic script, reports how many goals remain. The search grows
a tactic sequence best-first, prioritising states by a learned VALUE (value_function)
minus the remaining-goal count, until a state has zero goals (proof found) or the
node budget is exhausted. Unlike the old 1-ply ranker it explores DEPTH, and the
oracle is pluggable so the search logic is unit-tested with a deterministic mock.

Trust: the REPL only reports goal counts to GUIDE the search; the discovered tactic
script is still handed back to be kernel-checked by the caller (close_obligation /
lean_verify). Search guidance never certifies a proof.

If no REPL is configured it returns a structured ``unavailable`` status (the
REPL-free compound search in proof_search.py is the fallback path).

CLI:
  mcts_lean.py --target "theorem t : P := " [--repl-cmd CMD] [--tactic simp ...]
      [--value-model M] [--max-nodes 64] [--max-depth 8]
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import value_function  # noqa: E402

# Atomic tactics that change the tactic state (good for state-space search).
DEFAULT_TACTICS = ["intro n", "intro a b", "intros", "constructor", "cases h",
                   "simp", "simp_all", "omega", "decide", "rfl", "norm_num",
                   "ring", "induction n", "assumption", "trivial"]

_DEAD_MARKERS = ("error:", "unknown identifier", "unknown constant", "unknown tactic",
                 "unsolved goals", "failed", "timeout")


def estimate_goal_count(text: str) -> int | None:
    matches = re.findall(r"(\d+)\s+goals?", text, flags=re.IGNORECASE)
    if matches:
        return min(int(m) for m in matches)
    low = text.lower()
    if "no goals" in low or "goals accomplished" in low:
        return 0
    return None


def is_dead(output: str, returncode: int) -> bool:
    low = output.lower()
    return returncode != 0 or any(mk in low for mk in _DEAD_MARKERS)


def repl_step(repl_cmd: str, target: str, timeout: int):
    """Build a `step(tactics) -> {goals, dead, output}` oracle backed by a real REPL.
    `goals` is the remaining-goal count (0 = proof complete), None if unknown."""
    def step(tactics: list[str]) -> dict:
        body = "; ".join(tactics) if tactics else "skip"
        payload = f"{target}\nby\n  {body}\n"
        try:
            r = subprocess.run(shlex.split(repl_cmd), input=payload, text=True,
                               capture_output=True, timeout=timeout, check=False)
            out = f"{r.stdout}\n{r.stderr}"
            dead = is_dead(out, r.returncode)
            goals = 0 if (not dead and "no goals" in out.lower()) else estimate_goal_count(out)
            return {"goals": goals, "dead": dead, "output": out[-2000:]}
        except subprocess.TimeoutExpired:
            return {"goals": None, "dead": True, "output": "timeout"}
        except Exception as exc:  # noqa: BLE001
            return {"goals": None, "dead": True, "output": str(exc)}
    return step


def best_first_search(target: str, tactics: list[str], step, value_model: dict,
                      max_nodes: int = 64, max_depth: int = 8) -> dict:
    """Value-guided best-first search over tactic sequences. Returns
    {found, proof, nodes, frontier_exhausted}. `step` is the (real or mock) oracle."""
    goal_feats = value_function.featurize_goal(target, "")

    def priority(tacs: list[str], goals: int | None) -> float:
        body = "by " + "; ".join(tacs) if tacs else "by skip"
        g = 99 if goals is None else goals
        # higher value, fewer remaining goals, shorter script => explored first.
        return value_function.score(goal_feats, body, value_model) - 2.0 * g - 0.25 * len(tacs)

    init = step([])
    if init.get("goals") == 0:
        return {"found": True, "proof": "by skip", "nodes": 1, "frontier_exhausted": False}

    counter = 0
    frontier: list = []
    heapq.heappush(frontier, (-priority([], init.get("goals")), counter, [], init.get("goals")))
    seen: set = {()}
    nodes = 0
    while frontier and nodes < max_nodes:
        _, _, tacs, _ = heapq.heappop(frontier)
        if len(tacs) >= max_depth:
            continue
        for t in tactics:
            new = tacs + [t]
            key = tuple(new)
            if key in seen:
                continue
            seen.add(key)
            nodes += 1
            r = step(new)
            if r.get("goals") == 0 and not r.get("dead"):
                return {"found": True, "proof": "by " + "; ".join(new),
                        "nodes": nodes, "frontier_exhausted": False}
            if r.get("dead") or r.get("goals") is None:
                continue
            counter += 1
            heapq.heappush(frontier, (-priority(new, r["goals"]), counter, new, r["goals"]))
            if nodes >= max_nodes:
                break
    return {"found": False, "proof": None, "nodes": nodes,
            "frontier_exhausted": not frontier}


def read_target(args: argparse.Namespace) -> str:
    if args.target:
        return args.target
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    raise SystemExit("--target or --file required")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", "--goal", dest="target",
                    help="Frozen Lean theorem target without proof body (ends at `:=`).")
    ap.add_argument("--file", help="File containing the frozen target.")
    ap.add_argument("--repl-cmd", default=os.environ.get("WITSOC_LEAN_REPL_CMD"))
    ap.add_argument("--tactic", action="append", dest="tactics")
    ap.add_argument("--value-model", type=Path, default=None)
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--max-nodes", type=int, default=64)
    ap.add_argument("--max-depth", type=int, default=8)
    args = ap.parse_args()

    target = read_target(args)
    tactics = args.tactics or DEFAULT_TACTICS
    if not args.repl_cmd:
        print(json.dumps({"status": "unavailable",
                          "reason": "No Lean REPL configured. Set WITSOC_LEAN_REPL_CMD or --repl-cmd. "
                                    "(proof_search.py is the REPL-free fallback.)",
                          "found": False, "proof": None}, indent=2))
        return 0

    model = {}
    if args.value_model and args.value_model.exists():
        model = json.loads(args.value_model.read_text(encoding="utf-8"))
    elif os.environ.get("WITSOC_VALUE_MODEL") and Path(os.environ["WITSOC_VALUE_MODEL"]).exists():
        model = json.loads(Path(os.environ["WITSOC_VALUE_MODEL"]).read_text(encoding="utf-8"))

    step = repl_step(args.repl_cmd, target, args.timeout)
    result = best_first_search(target, tactics, step, model, args.max_nodes, args.max_depth)
    result["status"] = "searched"
    result["value_model_trained_on"] = model.get("trained_on", 0)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("found") else 1


if __name__ == "__main__":
    raise SystemExit(main())
