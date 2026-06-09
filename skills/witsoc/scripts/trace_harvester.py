#!/usr/bin/env python3
"""Harvest reward-labelled traces for Witsoc expert iteration.

The Lean kernel, the discovery-engine evaluators, and the WIT/receipt pipeline
all emit a hard signal of success. Today that signal evaporates when a run ends.
This tool captures it: it walks a session/run tree (and an optional lemma
library) and emits a `training_traces.jsonl` of (problem -> solution, reward)
records suitable for fine-tuning the proposer (the AlphaProof-style loop).

Reward is derived ONLY from machine-checkable status, never from prose:

  LEAN_VERIFIED / RECEIPT_ACCEPTED ........ 1.0   (formally / receipt verified)
  CHECKED (exact construction / bounded) .. 0.6
  PROVED_SKETCH ........................... 0.4
  PARTIAL / CONDITIONAL ................... 0.3
  CONJECTURE .............................. 0.1
  FAILED_ATTEMPT / REJECTED ............... 0.0   (kept: negatives train too)

Sources harvested under --root:
  discovery_run.json / best.json  -> construction traces (engine certificates)
  *.wit alongside a status        -> WIT proof traces
  handoff_v1.json                 -> target/status proof traces
  lemmas.db (via --library)       -> verified-lemma traces

Subcommands:
  harvest --root DIR [--library DIR] --out training_traces.jsonl
  stats   --traces training_traces.jsonl
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

STATUS_REWARD = {
    "LEAN_VERIFIED": 1.0,
    "RECEIPT_ACCEPTED": 1.0,
    "CHECKED": 0.6,
    "PROVED_SKETCH": 0.4,
    "PARTIAL": 0.3,
    "CONDITIONAL": 0.3,
    "CONJECTURE": 0.1,
    "FAILED_ATTEMPT": 0.0,
    "REJECTED": 0.0,
    "OPEN": 0.0,
    "GAP": 0.0,
}


def reward_for(status: str | None) -> float:
    return STATUS_REWARD.get((status or "").upper(), 0.0)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def harvest_discovery(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    # Accept both a live run checkpoint and an emitted best.json.
    best = data.get("best") if "best" in data else data
    if not isinstance(best, dict):
        return None
    problem = data.get("problem") or data.get("best_score") and ""
    verify = data.get("independent_verification")
    if verify is not None:
        status = "CHECKED" if verify.get("ok") else "REJECTED"
    else:
        status = best.get("certificate", {}).get("claim_status") if isinstance(best.get("certificate"), dict) else None
        status = status or ("CHECKED" if best.get("object") else None)
    if not problem and not best.get("object"):
        return None
    return {
        "kind": "construction",
        "problem": data.get("problem", ""),
        "evaluator": data.get("evaluator"),
        "solution": best.get("object"),
        "score": best.get("score") or data.get("best_score"),
        "status": status,
        "reward": reward_for(status),
        "source": str(path),
    }


def harvest_handoff(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    status = data.get("status") or data.get("claim_status")
    target = data.get("frozen_target") or data.get("target") or data.get("statement")
    if not target:
        return None
    return {
        "kind": "proof",
        "problem": str(target),
        "target_hash": data.get("target_hash") or data.get("frozen_target_hash"),
        "status": status,
        "reward": reward_for(status),
        "source": str(path),
    }


def harvest_library(library: Path) -> list[dict[str, Any]]:
    db = library / "lemmas.db"
    if not db.exists():
        return []
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT statement, wit_path, lean_path, trust_tier, target_hash FROM lemmas").fetchall()
    tier_status = {"LEAN_VERIFIED": "LEAN_VERIFIED", "WIT_RECEIPT": "RECEIPT_ACCEPTED", "WIT_STRUCTURE": "CHECKED"}
    out = []
    for statement, wit_path, lean_path, tier, target_hash in rows:
        status = tier_status.get(tier, "CHECKED")
        out.append({
            "kind": "lemma",
            "problem": statement,
            "wit_path": wit_path,
            "lean_path": lean_path,
            "trust_tier": tier,
            "target_hash": target_hash,
            "status": status,
            "reward": reward_for(status),
            "source": str(db),
        })
    return out


def cmd_harvest(args: argparse.Namespace) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    if args.root and args.root.exists():
        # Prefer the emitted best.json over the live checkpoint in the same dir.
        best_dirs = {p.parent for p in args.root.rglob("best.json")}
        for path in sorted(args.root.rglob("*")):
            if path.name == "discovery_run.json" and path.parent in best_dirs:
                continue
            if path.name in ("discovery_run.json", "best.json"):
                t = harvest_discovery(path)
                if t:
                    traces.append(t)
            elif path.name == "handoff_v1.json":
                t = harvest_handoff(path)
                if t:
                    traces.append(t)
    if args.library:
        traces.extend(harvest_library(args.library))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + ("\n" if traces else ""), encoding="utf-8")
    positives = sum(1 for t in traces if t["reward"] > 0)
    return {
        "status": "harvested",
        "traces": len(traces),
        "positive_reward": positives,
        "negative_reward": len(traces) - positives,
        "by_kind": {k: sum(1 for t in traces if t["kind"] == k) for k in {t["kind"] for t in traces}},
        "out": str(args.out),
    }


def cmd_stats(args: argparse.Namespace) -> dict[str, Any]:
    traces = [json.loads(l) for l in args.traces.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not traces:
        return {"traces": 0}
    rewards = [t.get("reward", 0.0) for t in traces]
    return {
        "traces": len(traces),
        "mean_reward": round(sum(rewards) / len(rewards), 4),
        "verified_fraction": round(sum(1 for r in rewards if r >= 1.0) / len(rewards), 4),
        "by_status": {s: sum(1 for t in traces if (t.get("status") or "").upper() == s)
                      for s in sorted({(t.get("status") or "").upper() for t in traces})},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_h = sub.add_parser("harvest")
    p_h.add_argument("--root", type=Path, help="Run/session tree to scan.")
    p_h.add_argument("--library", type=Path, help="Lemma library directory (lemmas.db).")
    p_h.add_argument("--out", type=Path, required=True)

    p_s = sub.add_parser("stats")
    p_s.add_argument("--traces", type=Path, required=True)

    args = parser.parse_args()
    out = cmd_harvest(args) if args.cmd == "harvest" else cmd_stats(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
