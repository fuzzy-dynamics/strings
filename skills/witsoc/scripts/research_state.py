#!/usr/bin/env python3
"""Phase 4: Lovász as a PERSISTENT research director.

A hard problem is not solved in one pass; it is solved by try -> learn -> pivot over
many sessions. This is the durable per-problem research state plus a bandit controller
that allocates effort across approaches by expected verified progress — so the
campaign compounds instead of restarting each session.

State (persisted JSON, keyed by target hash):
  attempt_ledger   every (approach, outcome, rung, session) — the audit trail
  approach_stats   per-approach {tries, reward} for the bandit
  barrier_map      barriers seen and their status
  partial_results  verified products (rung >= L2) that survive
  dead_ends        approaches that repeatedly failed with no progress (don't repeat)
  best_rung        highest rung reached so far

CALIBRATION: the controller only ALLOCATES EFFORT. It never upgrades a claim — rungs
come from the actual (kernel-gated) outcome of each approach. best_rung can only rise
on a genuinely better verified outcome; the campaign stops honestly (SOLVED only at a
kernel-verified L6; otherwise STALLED / HONEST_STOP), never "loops until a solve".

The approaches are the existing engines: direct_prover, generalize_invariant,
structural_induction, premise_retrieval, conjecture_mining, construction_search,
analogical_transfer, speculative_arena, counterexample_search, ontology_pivot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

APPROACHES = [
    "direct_prover", "generalize_invariant", "structural_induction", "premise_retrieval",
    "conjecture_mining", "construction_search", "analogical_transfer", "speculative_arena",
    "counterexample_search", "ontology_pivot", "invention", "finite_reduction",
]

# rung -> reward (verified progress). Kernel outcomes only; the controller never sets these.
RUNG_REWARD = {"L0": 0.0, "L1": 0.15, "L2": 0.3, "L3": 0.45, "L4": 0.6, "L5": 0.8, "L6": 1.0}
DEADEND_STREAK = 3   # consecutive no-progress tries before an approach is retired
STALL_LIMIT = 6      # consecutive no-progress steps before the campaign STALLS


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_state(target: str) -> dict:
    return {
        "schema": "witsoc.research_state.v1",
        "target": target,
        "target_hash": sha(target),
        "status": "ACTIVE",
        "best_rung": "L0",
        "attempt_ledger": [],
        "approach_stats": {a: {"tries": 0, "reward": 0.0, "fail_streak": 0} for a in APPROACHES},
        "barrier_map": [],
        "partial_results": [],
        "dead_ends": [],
        "no_progress_streak": 0,
        "sessions": 0,
    }


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rung_value(rung: str) -> float:
    return RUNG_REWARD.get(rung, 0.0)


def select_approach(state: dict, priors: dict | None = None) -> str | None:
    """UCB1 over approaches, excluding retired dead-ends. `priors` (e.g. from
    analogical_transfer) give a small optimistic bonus to suggested approaches so a
    relevant technique is tried sooner. Returns None when everything is retired."""
    priors = priors or {}
    live = [a for a in APPROACHES if a not in state["dead_ends"]]
    if not live:
        return None
    # setdefault: states saved before a new approach existed must stay loadable
    for a in live:
        state["approach_stats"].setdefault(a, {"tries": 0, "reward": 0.0, "fail_streak": 0})
    total = sum(state["approach_stats"][a]["tries"] for a in live) + 1
    best, best_score = None, -1e18
    for a in live:
        st = state["approach_stats"][a]
        if st["tries"] == 0:
            score = 1e9 + priors.get(a, 0.0)          # try each at least once; priors break ties
        else:
            mean = st["reward"] / st["tries"]
            score = mean + math.sqrt(2.0 * math.log(total) / st["tries"]) + 0.1 * priors.get(a, 0.0)
        if score > best_score:
            best, best_score = a, score
    return best


def record(state: dict, approach: str, outcome: dict) -> dict:
    """Record a kernel-gated outcome. `outcome` = {rung, status, evidence?, barrier?,
    partial?}. Updates stats, ledger, best_rung, dead-ends, and the stall counter."""
    rung = outcome.get("rung", "L0")
    reward = _rung_value(rung)
    st = state["approach_stats"].setdefault(approach, {"tries": 0, "reward": 0.0, "fail_streak": 0})
    st["tries"] += 1
    st["reward"] += reward

    prev_best = _rung_value(state["best_rung"])
    progressed = reward > prev_best
    if progressed:
        state["best_rung"] = rung
        state["no_progress_streak"] = 0
        st["fail_streak"] = 0
    else:
        state["no_progress_streak"] += 1
        st["fail_streak"] += 1
        if st["fail_streak"] >= DEADEND_STREAK and approach not in state["dead_ends"]:
            state["dead_ends"].append(approach)

    state["attempt_ledger"].append({
        "approach": approach, "rung": rung, "status": outcome.get("status", "OPEN"),
        "progressed": progressed, "evidence": outcome.get("evidence"),
        "session": state["sessions"],
    })
    if outcome.get("barrier"):
        state["barrier_map"].append(outcome["barrier"])
    if outcome.get("partial") and rung >= "L2":   # rung strings sort lexicographically L0<L2<L6
        state["partial_results"].append(outcome["partial"])

    # honest stop conditions — never "loop until solve".
    if state["best_rung"] == "L6":
        state["status"] = "SOLVED"
    elif all(a in state["dead_ends"] for a in APPROACHES):
        state["status"] = "HONEST_STOP"
    elif state["no_progress_streak"] >= STALL_LIMIT:
        state["status"] = "STALLED"
    return state


def run_campaign(target: str, execute, priors: dict | None = None, max_steps: int = 30,
                 state: dict | None = None) -> dict:
    """Drive a campaign: select_approach -> execute(approach, target) -> record, until a
    stop condition. `execute(approach, target) -> outcome` is the engine dispatcher
    (real or a mock). State persists across calls (pass it back in next session)."""
    state = state or new_state(target)
    state["sessions"] += 1
    for _ in range(max_steps):
        if state["status"] != "ACTIVE":
            break
        approach = select_approach(state, priors)
        if approach is None:
            state["status"] = "HONEST_STOP"
            break
        outcome = execute(approach, target)
        record(state, approach, outcome)
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, required=True, help="persistent state JSON (created if absent)")
    ap.add_argument("--target", default=None, help="frozen target (required when creating state)")
    ap.add_argument("--select", action="store_true", help="print the next approach the bandit recommends")
    ap.add_argument("--record", nargs=2, metavar=("APPROACH", "RUNG"), help="record an outcome and update state")
    ap.add_argument("--prior", action="append", default=[], help="APPROACH:WEIGHT prior bonus (repeatable)")
    args = ap.parse_args()

    state = load(args.state)
    if state is None:
        if not args.target:
            print("--target required to create new state", file=sys.stderr)
            return 2
        state = new_state(args.target)
    priors = {}
    for p in args.prior:
        k, _, v = p.partition(":")
        try:
            priors[k] = float(v)
        except ValueError:
            pass

    if args.record:
        record(state, args.record[0], {"rung": args.record[1], "status": "RECORDED"})
        save(args.state, state)
    nxt = select_approach(state, priors)
    save(args.state, state)
    print(json.dumps({"status": state["status"], "best_rung": state["best_rung"],
                      "next_approach": nxt, "dead_ends": state["dead_ends"],
                      "no_progress_streak": state["no_progress_streak"],
                      "partial_results": len(state["partial_results"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
