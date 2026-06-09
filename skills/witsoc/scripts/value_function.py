#!/usr/bin/env python3
"""Phase 1: a learned VALUE FUNCTION for proof-search candidate ordering.

The compound search builds 1000+ candidate proofs but only the first `max_nodes`
are tried, so a good candidate ranked late by the hand-coded cost is truncated away
— it never gets a kernel check. This scores each candidate by *predicted success on
this goal* so good candidates land within the node budget: more goals close (reach)
and the winning candidate is found at a shallower rank (efficiency).

It is LEARNED, not hand-tuned: `train` accumulates, from the closure ledger, how
often each (goal-feature, candidate-feature) pair appears in a KERNEL-VERIFIED
proof, and turns those frequencies into weights. The model is a transparent dict of
weights (no opaque net), is deterministic, and **only reorders** — it can never make
an unsound proof pass (the kernel is still the sole trust root, every candidate is
checked). With no model the score is 0 everywhere, so ordering falls back exactly to
the existing cost and there is zero behavior change until the flywheel trains one.

CLI:
  value_function.py train --from-closures closures.json --out value_model.json
  value_function.py score --statement S [--preamble P] --proof "by ..." [--model M]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

MODEL_FILE = "value_model.json"
_CAND_TACTICS = ("rfl", "simp_all", "simp", "omega", "decide", "norm_num", "ring",
                 "rw", "exact", "apply", "constructor", "intro", "cases", "congr",
                 "linarith", "trivial", "assumption", "unfold")


def featurize_goal(statement: str, preamble: str = "") -> list[str]:
    """Coarse structural features of the goal — what KIND of proof it likely needs."""
    s = statement or ""
    f: list[str] = []
    if "∀" in s:
        f.append("g:forall")
    if "∃" in s:
        f.append("g:exists")
    if "=" in s:
        f.append("g:eq")
    if any(o in s for o in ("≤", "<", "≥", ">")):
        f.append("g:ineq")
    if "+" in s:
        f.append("g:add")
    if "*" in s:
        f.append("g:mul")
    if "^" in s:
        f.append("g:pow")
    if "%" in s:
        f.append("g:mod")
    if re.search(r"\bNat\b|ℕ", s):
        f.append("g:nat")
    if re.search(r"\bList\b", s):
        f.append("g:list")
    # two or more leading binders => an accumulator/generalization smell
    if len(re.findall(r"∀", s)) >= 2:
        f.append("g:multiforall")
    if preamble and re.search(r"def\s+\w+[^\n]*\n\s*\|", preamble):
        f.append("g:recdef")
    if preamble and re.search(r"def\s+\w+\s*:\s*Nat\s*(?:→|->)\s*Nat\s*(?:→|->)", preamble):
        f.append("g:accumulator")
    return f or ["g:other"]


def featurize_candidate(proof: str) -> list[str]:
    """Features of a candidate proof body — its strategy, tactics, and length."""
    p = proof or ""
    f: list[str] = []
    if "hgen" in p:
        f.append("c:generalization")
    if "hlib" in p:
        f.append("c:library")
    if "| nil" in p:
        f.append("c:listinduction")
    elif "induction" in p:
        f.append("c:induction")
    if re.search(r"have\s+h\w*\s*:", p):
        f.append("c:have")
    for t in _CAND_TACTICS:
        if re.search(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])", p):
            f.append(f"c:{t}")
    steps = p.count(";") + p.count("<;>") + 1
    f.append("c:len_short" if steps <= 2 else "c:len_med" if steps <= 5 else "c:len_long")
    return f


def score(goal_feats: list[str], proof: str, model: dict) -> float:
    """Predicted value of trying `proof` on a goal with `goal_feats`. 0 with no model
    (so callers fall back to their own tie-break ordering — zero behavior change)."""
    if not model:
        return 0.0
    cf = featurize_candidate(proof)
    pairs = model.get("pairs", {})
    prior = model.get("cand_prior", {})
    s = 0.0
    for c in cf:
        s += prior.get(c, 0.0)
        for g in goal_feats:
            s += pairs.get(f"{g}|{c}", 0.0)
    return s


def train(closures: list[dict]) -> dict:
    """Learn weights from KERNEL-VERIFIED closures: features that co-occur in
    successful (goal, proof) pairs get higher weight (log-frequency)."""
    pairs: Counter = Counter()
    cand: Counter = Counter()
    used = 0
    for r in closures:
        if not isinstance(r, dict) or not r.get("discharged") or not r.get("proof"):
            continue
        gf = featurize_goal(str(r.get("statement", "")), str(r.get("preamble", "")))
        cf = featurize_candidate(str(r["proof"]))
        used += 1
        for c in cf:
            cand[c] += 1
            for g in gf:
                pairs[f"{g}|{c}"] += 1
    return {
        "schema": "witsoc.value_model.v1",
        "trained_on": used,
        "pairs": {k: round(math.log1p(v), 4) for k, v in pairs.items()},
        "cand_prior": {k: round(0.5 * math.log1p(v), 4) for k, v in cand.items()},
    }


def load_model(library: Path | None) -> dict:
    """Discover a trained model: WITSOC_VALUE_MODEL, then `<library>/value_model.json`.
    Returns {} (no model) if none — callers then keep their existing ordering."""
    import os
    env = os.environ.get("WITSOC_VALUE_MODEL")
    if env and Path(env).exists():
        return witcore.load_json(Path(env), {}) or {}
    if library is not None:
        p = Path(library) / MODEL_FILE
        if p.exists():
            return witcore.load_json(p, {}) or {}
    return {}


def _load_closures(path: Path) -> list[dict]:
    data = witcore.load_json(path, [])
    if isinstance(data, dict):
        data = data.get("closures") or data.get("records") or []
    out = []
    for r in data if isinstance(data, list) else []:
        if isinstance(r, dict):
            out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--from-closures", type=Path, required=True)
    t.add_argument("--out", type=Path, default=Path(MODEL_FILE))
    s = sub.add_parser("score")
    s.add_argument("--statement", required=True)
    s.add_argument("--preamble", default="")
    s.add_argument("--proof", required=True)
    s.add_argument("--model", type=Path, default=None)
    args = ap.parse_args()

    if args.cmd == "train":
        model = train(_load_closures(args.from_closures))
        witcore.save_json(args.out, model)
        print(json.dumps({"trained_on": model["trained_on"], "pairs": len(model["pairs"]),
                          "out": str(args.out)}, indent=2))
        return 0
    model = witcore.load_json(args.model, {}) if args.model else {}
    gf = featurize_goal(args.statement, args.preamble)
    print(json.dumps({"goal_features": gf, "candidate_features": featurize_candidate(args.proof),
                      "score": score(gf, args.proof, model)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
