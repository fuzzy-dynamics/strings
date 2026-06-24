#!/usr/bin/env python3
"""L3 campaign escalation gate — `witsoc budget-gate`.

The campaign block in lovasz_run.json is the single source of truth for a
Lovasz run's escalation state and per-barrier attempt counters. This gate owns
every mutation of that block:

  check            is dispatch allowed? Blocks at HONEST_STOP and reports
                   per-barrier overruns (the research_protocol.md "three loops
                   on the same barrier -> convert to obstruction" rule as a
                   counter) and the required action. Exit 1 when dispatch must
                   not proceed.
  record-attempt   increment the per-barrier attempt counters.
  escalate         move exactly one level down the ladder (or --to a named
                   level further down). The ladder is one-way:
                   DIRECT_ATTACK -> PRODUCT_LADDER -> OBSTRUCTION_CONVERSION
                   -> HONEST_STOP. Every escalation records a reason.
  record-progress  track best rung; stalled passes increment stall_count and
                   an escalation is RECOMMENDED (never auto-applied) after 3.

Deterministic ledger plumbing only — the gate never decides mathematics.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lovasz_run_manifest import ESCALATION_LADDER, default_campaign

STALL_ESCALATION_THRESHOLD = 3

RUNG_VALUE = {"L0": 0.0, "L1": 0.15, "L2": 0.3, "L3": 0.45, "L4": 0.6, "L5": 0.8, "L6": 1.0}


def manifest_path(run: Path) -> Path:
    return run / "lovasz_run.json"


def load_manifest(run: Path) -> dict:
    try:
        data = json.loads(manifest_path(run).read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def load_campaign(run: Path) -> dict:
    campaign = load_manifest(run).get("campaign")
    if isinstance(campaign, dict) and campaign.get("schema") == "witsoc.lovasz_campaign.v1":
        return campaign
    return default_campaign()


def save_campaign(run: Path, campaign: dict) -> None:
    data = load_manifest(run)
    data["campaign"] = campaign
    manifest_path(run).parent.mkdir(parents=True, exist_ok=True)
    manifest_path(run).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def exhausted_barriers(campaign: dict) -> list[str]:
    cap = int(campaign.get("max_attempts_per_barrier", 3))
    return sorted(b for b, n in campaign.get("barrier_attempts", {}).items() if int(n) >= cap)


def check(run: Path) -> dict:
    campaign = load_campaign(run)
    level = campaign.get("escalation_level", "DIRECT_ATTACK")
    over_barriers = exhausted_barriers(campaign)
    dispatch_allowed = level != "HONEST_STOP"
    if level == "HONEST_STOP":
        required = "no further dispatch; return to Explorer with failure memory (EXPLORER_RETURN_READY or NO_GO)"
    elif over_barriers:
        required = ("convert exhausted barriers to obstruction targets before further direct attacks: "
                    + ", ".join(over_barriers))
    else:
        required = "proceed"
    return {
        "schema": "witsoc.campaign_gate_check.v1",
        "run_dir": str(run),
        "escalation_level": level,
        "exhausted_barriers": over_barriers,
        "dispatch_allowed": dispatch_allowed,
        "required_action": required,
    }


def record_attempt(run: Path, barriers: list[str] | None = None) -> dict:
    campaign = load_campaign(run)
    counters = campaign.setdefault("barrier_attempts", {})
    for barrier in barriers or []:
        counters[barrier] = int(counters.get(barrier, 0)) + 1
    save_campaign(run, campaign)
    return {"barrier_attempts": counters}


def escalate(run: Path, reason: str, to: str | None = None) -> dict:
    campaign = load_campaign(run)
    current = campaign.get("escalation_level", "DIRECT_ATTACK")
    idx = ESCALATION_LADDER.index(current) if current in ESCALATION_LADDER else 0
    target = to or (ESCALATION_LADDER[min(idx + 1, len(ESCALATION_LADDER) - 1)])
    if target not in ESCALATION_LADDER or ESCALATION_LADDER.index(target) <= idx:
        return {"error": f"illegal escalation {current} -> {target}; the ladder is one-way: {ESCALATION_LADDER}"}
    campaign["escalation_level"] = target
    campaign["stall_count"] = 0
    campaign.setdefault("escalation_history", []).append({
        "from": current, "to": target, "reason": reason,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    save_campaign(run, campaign)
    return {"escalation_level": target, "from": current, "reason": reason}


def record_progress(run: Path, best_rung: str) -> dict:
    campaign = load_campaign(run)
    previous = campaign.get("last_best_rung", "L0")
    improved = RUNG_VALUE.get(best_rung, 0.0) > RUNG_VALUE.get(previous, 0.0)
    if improved:
        campaign["last_best_rung"] = best_rung
        campaign["stall_count"] = 0
    else:
        campaign["stall_count"] = int(campaign.get("stall_count", 0)) + 1
    save_campaign(run, campaign)
    return {
        "best_rung": campaign["last_best_rung"],
        "improved": improved,
        "stall_count": campaign["stall_count"],
        "escalation_recommended": campaign["stall_count"] >= STALL_ESCALATION_THRESHOLD
        and campaign.get("escalation_level") != "HONEST_STOP",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("run_dir", type=Path)

    p_attempt = sub.add_parser("record-attempt")
    p_attempt.add_argument("run_dir", type=Path)
    p_attempt.add_argument("--barrier", action="append", default=[])

    p_escalate = sub.add_parser("escalate")
    p_escalate.add_argument("run_dir", type=Path)
    p_escalate.add_argument("--reason", required=True)
    p_escalate.add_argument("--to", choices=ESCALATION_LADDER, default=None)

    p_progress = sub.add_parser("record-progress")
    p_progress.add_argument("run_dir", type=Path)
    p_progress.add_argument("--best-rung", required=True)

    args = parser.parse_args()
    if args.cmd == "check":
        result = check(args.run_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["dispatch_allowed"] else 1
    if args.cmd == "record-attempt":
        result = record_attempt(args.run_dir, args.barrier)
    elif args.cmd == "escalate":
        result = escalate(args.run_dir, args.reason, args.to)
        if "error" in result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1
    elif args.cmd == "record-progress":
        result = record_progress(args.run_dir, args.best_rung)
    else:
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
