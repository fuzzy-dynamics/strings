#!/usr/bin/env python3
"""Learned tactic-ordering policy for the prover (Tier A).

The portfolio closer works, but trying tactics in a fixed order wastes builds.
This is a *data-trained* policy (not neural — honest about that): it learns, from
which tactics actually closed which kinds of goals, a ranked ordering conditioned
on cheap goal features (∀, =, ≤, ∧, ∃, Nat, arithmetic). Expert iteration: every
successful closure feeds back as training data, so the order improves over runs.

For a real neural policy, pass `--policy cmd:<command>`: the command receives
{"goal","premises","tactics"} on stdin and returns {"tactics":[...]} — the same
plug-point the discovery engine uses for an external sampler.

Subcommands:
  train  --from-closures F [--from-closures G ...] --out policy.json
  rank   --statement S [--policy policy.json | --policy cmd:CMD] [--premises a,b]

A "closure" record (from close_obligation.py) is {statement, discharged, proof}.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import witcore  # noqa: E402

# Default priors so the policy is useful with zero training. Core-Lean tactics
# first (cheap, no mathlib), then mathlib tactics.
DEFAULT_ORDER = ["by rfl", "by decide", "by omega", "by simp", "by trivial",
                 "by norm_num", "by linarith", "by ring", "by ring_nf",
                 "by aesop", "by constructor",
                 "by intros; ring_nf", "by intros; ring", "by intros; omega",
                 "by intros; norm_num", "by intros; nlinarith"]


def features(statement: str) -> list[str]:
    s = statement
    feats = []
    if "∀" in s or "forall" in s:
        feats.append("forall")
    if "∃" in s or "exists" in s:
        feats.append("exists")
    if "=" in s:
        feats.append("eq")
    if "≤" in s or "<" in s or "≥" in s or ">" in s:
        feats.append("order")
    if "∧" in s or "∨" in s or "→" in s:
        feats.append("logic")
    if "Nat" in s or "ℕ" in s:
        feats.append("nat")
    if "%" in s or "mod" in s or "∣" in s or "dvd" in s:
        feats.append("modular")
    if "*" in s or "^" in s:
        feats.append("multiplicative")
    if "List" in s or "Finset" in s or "Set" in s:
        feats.append("finite_combinatorics")
    if "Function" in s or "f " in s or "f(" in s:
        feats.append("functional")
    if any(c.isdigit() for c in s):
        feats.append("arith")
    return sorted(feats) or ["plain"]


def bucket(statement: str) -> str:
    return "+".join(features(statement))


def cmd_train(args: argparse.Namespace) -> int:
    by_bucket: dict[str, Counter] = defaultdict(Counter)
    global_counts: Counter = Counter()
    seen = 0
    for f in args.from_closures:
        for rec in witcore.records(Path(f)):
            if not rec.get("discharged") or not rec.get("proof"):
                continue
            stmt = str(rec.get("statement") or "")
            proof = str(rec["proof"])
            by_bucket[bucket(stmt)][proof] += 1
            global_counts[proof] += 1
            seen += 1
    policy = {
        "schema": "witsoc.proof_policy.v1",
        "trained_on": seen,
        "global": [p for p, _ in global_counts.most_common()],
        "by_bucket": {b: [p for p, _ in c.most_common()] for b, c in by_bucket.items()},
        "default_order": DEFAULT_ORDER,
    }
    witcore.save_json(args.out, policy)
    print(json.dumps({"status": "trained", "examples": seen, "buckets": len(by_bucket), "out": str(args.out)}, indent=2))
    return 0


def rank_tactics(statement: str, policy: dict | None, premises: list[str]) -> list[str]:
    order: list[str] = []
    if policy:
        b = bucket(statement)
        order += policy.get("by_bucket", {}).get(b, [])
        order += policy.get("global", [])
        order += policy.get("default_order", DEFAULT_ORDER)
    else:
        order += DEFAULT_ORDER
    # Premise-guided candidates: try to close by directly applying a known lemma.
    for prem in premises:
        order += [f"by exact {prem}", f"by apply {prem}", f"by simp [{prem}]"]
    # Dedup preserving order.
    seen: set[str] = set()
    return [t for t in order if not (t in seen or seen.add(t))]


def cmd_rank(args: argparse.Namespace) -> int:
    premises = [p.strip() for p in (args.premises or "").split(",") if p.strip()]
    if args.policy and args.policy.startswith("cmd:"):
        reply = witcore.run_sampler(args.policy, {"goal": args.statement, "premises": premises,
                                                  "tactics": DEFAULT_ORDER})
        tactics = reply.get("tactics") if isinstance(reply, dict) else None
        if not tactics:
            tactics = rank_tactics(args.statement, None, premises)
    else:
        policy = witcore.load_json(Path(args.policy), None) if args.policy else None
        tactics = rank_tactics(args.statement, policy, premises)
    print(json.dumps({"statement": args.statement, "bucket": bucket(args.statement),
                      "tactics": tactics}, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_tr = sub.add_parser("train")
    p_tr.add_argument("--from-closures", action="append", required=True)
    p_tr.add_argument("--out", type=Path, required=True)
    p_rk = sub.add_parser("rank")
    p_rk.add_argument("--statement", required=True)
    p_rk.add_argument("--policy", default=None)
    p_rk.add_argument("--premises", default=None)
    args = ap.parse_args()
    return {"train": cmd_train, "rank": cmd_rank}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
