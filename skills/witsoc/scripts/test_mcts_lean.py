#!/usr/bin/env python3
"""Phase 1: value-guided best-first tactic-state search (mcts_lean).

The host has no Lean REPL, so the search ORACLE is mocked deterministically — this
verifies the search LOGIC (it grows a tactic sequence to a zero-goal state, is
bounded, and consults the value model). The real REPL path is the same code with
`repl_step` as the oracle."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mcts_lean as mc

GOOD = ["intro n", "simp", "omega"]  # the (only) solution path in the mock tree


def mock_step(tactics: list[str]) -> dict:
    """A tiny proof tree: only the GOOD prefix stays alive; GOOD reaches 0 goals;
    everything off-path is a dead end."""
    if tactics == GOOD[: len(tactics)]:
        return {"goals": 0 if tactics == GOOD else 1, "dead": False, "output": ""}
    return {"goals": None, "dead": True, "output": "error: no progress"}


def main() -> int:
    failures: list[str] = []
    target = "theorem t : ∀ n : Nat, n + 0 = n :="

    # 1. The search finds the solution path and returns the assembled tactic script.
    res = mc.best_first_search(target, mc.DEFAULT_TACTICS, mock_step, {}, max_nodes=200, max_depth=6)
    if not res.get("found"):
        failures.append(f"search must find the proof in the mock tree, got {res}")
    elif res.get("proof") != "by intro n; simp; omega":
        failures.append(f"found proof should be the GOOD path, got {res.get('proof')!r}")

    # 2. It still finds it WITH a value model present (model only guides ordering).
    model = mc.value_function.train([
        {"statement": target, "proof": "by intro n; simp; omega", "discharged": True}] * 4)
    res2 = mc.best_first_search(target, mc.DEFAULT_TACTICS, mock_step, model, max_nodes=200, max_depth=6)
    if not res2.get("found"):
        failures.append("search with a value model must still find the proof")

    # 3. No solution in the tree => bounded, honest not-found (never hangs).
    dead_step = lambda tactics: ({"goals": 1, "dead": False, "output": ""} if not tactics
                                 else {"goals": None, "dead": True, "output": "err"})
    res3 = mc.best_first_search(target, mc.DEFAULT_TACTICS, dead_step, {}, max_nodes=30, max_depth=5)
    if res3.get("found"):
        failures.append("search must not report found when no zero-goal state exists")
    if res3.get("nodes", 0) > 30:
        failures.append(f"search must respect the node budget, used {res3.get('nodes')}")

    # 4. No REPL configured => structured 'unavailable', not a fake search.
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "mcts_lean.py"),
                        "--target", target], capture_output=True, text=True, timeout=30,
                       env={"PATH": "/usr/bin:/bin"})
    try:
        out = json.loads(r.stdout)
        if out.get("status") != "unavailable" or out.get("found") is not False:
            failures.append(f"no-REPL run must be 'unavailable'+found:false, got {out}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"no-REPL run must emit JSON, got {r.stdout!r} / {exc}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("MCTS_LEAN_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
