#!/usr/bin/env python3
"""Ω6 proof hygiene + the prompt bank — `witsoc bank`.

ProofOptimizer's lesson: search/RL proofs are bloated, and bloat poisons
everything downstream — technique mining, few-shot prompts, library search.
Goedel-Prover's lesson: verified (goal, proof) pairs are the expert-iteration
fuel. This module is both:

  SIMPLIFY  kernel-gated proof compression before anything is archived:
            try the one-tactic portfolio, then tactic-sequence prefixes and
            tail-drops — every candidate is kernel-verified, the shortest
            verified survivor wins (the original is always a valid fallback);
  BANK      simplified (goal, proof) pairs land in the knowledge substrate
            (`~/.witsoc/knowledge.sqlite3`, table proof_bank) keyed by goal
            signature;
  EXAMPLES  `examples_for(goal)` returns signature-similar verified pairs —
            the few-shot surface the Nexus loop embeds in every prove prompt.

Consumers: lemma_pool (banks on PROVED), nexus_loop (banks on success, embeds
examples), proof_autopsy-style mining benefits from the shorter forms.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

_ONE_TACTIC = ["by rfl", "by decide", "by omega", "by simp", "by simp_all", "by norm_num", "by trivial"]


def _connect():
    import knowledge_store as ks
    con = ks.connect()
    con.execute("CREATE TABLE IF NOT EXISTS proof_bank ("
                " goal TEXT PRIMARY KEY, proof TEXT, signature TEXT,"
                " original_len INTEGER, banked_len INTEGER, created INTEGER)")
    return con


def simplify(goal: str, proof: str, imports: str = "", lake_dir: Path | None = None) -> dict:
    """Kernel-gated compression. Sound by construction: only verified
    candidates replace the original."""
    import close_obligation as co

    def verifies(p: str) -> bool:
        return bool(witcore.lean_verify_cached(co.lean_source("bank_simplify", goal, imports, p),
                                               lake_dir).get("verified"))

    original = proof.strip()
    best = original
    # 1) a single cheap tactic often suffices for a search-built compound proof
    for cand in _ONE_TACTIC:
        if len(cand) < len(best) and verifies(cand):
            best = cand
            break
    # 2) prefixes of the tactic sequence (drop trailing steps)
    if best == original and original.startswith("by"):
        steps = [s.strip() for s in re.split(r";|\n<;>|\n", original[2:].strip()) if s.strip()]
        for k in range(1, len(steps)):
            cand = "by " + "; ".join(steps[:k])
            if len(cand) < len(best) and verifies(cand):
                best = cand
                break
    return {"goal": goal, "proof": best, "original_len": len(original),
            "banked_len": len(best), "compressed": best != original}


def bank(goal: str, proof: str, imports: str = "", lake_dir: Path | None = None,
         pre_simplify: bool = True) -> dict:
    record = simplify(goal, proof, imports, lake_dir) if pre_simplify else \
        {"goal": goal, "proof": proof, "original_len": len(proof), "banked_len": len(proof),
         "compressed": False}
    import knowledge_store as ks
    con = _connect()
    con.execute("INSERT OR REPLACE INTO proof_bank (goal, proof, signature, original_len,"
                " banked_len, created) VALUES (?,?,?,?,?,?)",
                (record["goal"], record["proof"], ks.goal_signature(goal),
                 record["original_len"], record["banked_len"], int(time.time())))
    con.commit()
    con.close()
    return {"banked": True, **{k: record[k] for k in ("proof", "compressed", "banked_len")}}


def examples_for(goal: str, k: int = 3) -> list[dict]:
    """Signature-similar verified pairs — the few-shot surface. Exact-signature
    matches first, then a token-overlap fallback."""
    import knowledge_store as ks
    con = _connect()
    sig = ks.goal_signature(goal)
    rows = con.execute("SELECT goal, proof FROM proof_bank WHERE signature = ?"
                       " ORDER BY banked_len LIMIT ?", (sig, k)).fetchall()
    if len(rows) < k:
        tokens = {t for t in re.findall(r"[a-zA-Z_]+", goal) if len(t) > 2}
        extra = con.execute("SELECT goal, proof FROM proof_bank ORDER BY created DESC"
                            " LIMIT 200").fetchall()
        scored = sorted(((len(tokens & set(re.findall(r"[a-zA-Z_]+", g))), g, p)
                         for g, p in extra if (g, p) not in rows), key=lambda x: -x[0])
        rows += [(g, p) for s, g, p in scored if s > 0][: k - len(rows)]
    con.close()
    return [{"goal": g, "proof": p} for g, p in rows[:k]]


def stats() -> dict:
    con = _connect()
    total, = con.execute("SELECT COUNT(*) FROM proof_bank").fetchone()
    compressed, = con.execute(
        "SELECT COUNT(*) FROM proof_bank WHERE banked_len < original_len").fetchone()
    con.close()
    return {"banked": total, "compressed": compressed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("bank")
    p_b.add_argument("--goal", required=True)
    p_b.add_argument("--proof", required=True)
    p_b.add_argument("--imports", default="")
    p_e = sub.add_parser("examples")
    p_e.add_argument("--goal", required=True)
    p_e.add_argument("-k", type=int, default=3)
    sub.add_parser("stats")
    args = ap.parse_args()
    if args.cmd == "bank":
        result = bank(args.goal, args.proof, args.imports)
    elif args.cmd == "examples":
        result = {"examples": examples_for(args.goal, args.k)}
    else:
        result = stats()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
