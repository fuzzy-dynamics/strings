#!/usr/bin/env python3
"""Single-ply parallel tactic scan for Lean proof repair.

Runs each candidate tactic once against the frozen target, scores the resulting
state by goal count and diagnostic reduction, prunes dead ends, and returns the
top branches. This is a one-step breadth scan, not a multi-step tree search.

This script is intentionally conservative. It drives an external Lean REPL or
checker command provided by --repl-cmd or WITSOC_LEAN_REPL_CMD. If no command is
available, it returns structured unavailable status rather than pretending to
search.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TACTICS = ["intro", "intros", "cases", "simp", "ring", "linarith", "omega", "induction"]


@dataclass
class Branch:
    tactic: str
    stdout: str
    stderr: str
    returncode: int
    score: float
    goal_count: int | None
    dead_end: bool


def read_target(args: argparse.Namespace) -> str:
    if args.target:
        return args.target
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    raise SystemExit("--target or --file required")


def estimate_goal_count(text: str) -> int | None:
    matches = re.findall(r"(\d+)\s+goals?", text, flags=re.IGNORECASE)
    if matches:
        return min(int(m) for m in matches)
    if "no goals" in text.lower() or "goals accomplished" in text.lower():
        return 0
    return None


def score_output(tactic: str, returncode: int, stdout: str, stderr: str) -> Branch:
    combined = f"{stdout}\n{stderr}"
    lower = combined.lower()
    dead = returncode != 0 or any(term in lower for term in ("error:", "unknown identifier", "unsolved goals", "failed"))
    goals = estimate_goal_count(combined)
    score = 100.0
    if dead:
        score -= 80.0
    if goals is not None:
        score -= 10.0 * goals
    score += max(0.0, 20.0 - len(combined) / 200.0)
    if "no goals" in lower:
        score += 50.0
    return Branch(tactic, stdout, stderr, returncode, score, goals, dead)


def run_tactic(repl_cmd: str, target: str, tactic: str, timeout: int) -> Branch:
    payload = f"{target}\nby\n  {tactic}\n"
    try:
        completed = subprocess.run(
            shlex.split(repl_cmd),
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return score_output(tactic, completed.returncode, completed.stdout, completed.stderr)
    except subprocess.TimeoutExpired as exc:
        return Branch(tactic, exc.stdout or "", exc.stderr or "timeout", 124, -100.0, None, True)
    except Exception as exc:
        return Branch(tactic, "", str(exc), 125, -100.0, None, True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", help="Frozen Lean theorem target without proof body.")
    parser.add_argument("--file", help="File containing frozen Lean theorem target.")
    parser.add_argument("--repl-cmd", default=os.environ.get("WITSOC_LEAN_REPL_CMD"))
    parser.add_argument("--tactic", action="append", dest="tactics")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    target = read_target(args)
    tactics = args.tactics or DEFAULT_TACTICS
    if not args.repl_cmd:
        print(json.dumps({
            "status": "unavailable",
            "reason": "No Lean REPL/checker command configured. Set WITSOC_LEAN_REPL_CMD or pass --repl-cmd.",
            "top_branches": [],
        }, indent=2))
        return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(run_tactic, args.repl_cmd, target, tactic, args.timeout) for tactic in tactics]
        branches = [future.result() for future in concurrent.futures.as_completed(futures)]

    branches.sort(key=lambda branch: branch.score, reverse=True)
    print(json.dumps({
        "status": "searched",
        "top_branches": [
            {
                "tactic": b.tactic,
                "score": b.score,
                "goal_count": b.goal_count,
                "dead_end": b.dead_end,
                "returncode": b.returncode,
                "stdout": b.stdout[-2000:],
                "stderr": b.stderr[-2000:],
            }
            for b in branches[:3]
        ],
        "explored": len(branches),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
