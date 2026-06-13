#!/usr/bin/env python3
"""Witsoc verified lemma library: persistent, semantically-searchable memory.

This turns one-shot runs into compounding research memory. Every lemma a run
establishes is stored once, keyed by its WIT statement, and retrieved by future
runs via semantic (token-cosine) search. WIT stays the primary engine and the
canonical record of every lemma; Lean is layered on top as a stronger trust tier
that elevates a lemma's rank and can be machine-checked here with the real Lean
toolchain.

Trust tiers (ascending):
  WIT_STRUCTURE   wit check passed (structural only)        rank 1
  WIT_RECEIPT     wit receipt accepted (semantic review)    rank 2
  LEAN_VERIFIED   lake build green AND no sorry/admit/axiom  rank 3  <-- strongest

`verify-lean` upgrades to LEAN_VERIFIED only when the Lean toolchain builds the
artifact AND a soundness scan finds no `sorry`/`admit`/`sorryAx`/local `axiom`.
A green build that leans on `sorry` is a warning, not an error, in Lean, so the
scan (shared `lean_check.lean_verify`) is what makes the tier trustworthy.

Search ranks by cosine similarity, multiplied by a Lean-significance boost so
verified lemmas surface first; `--require-lean` filters to LEAN_VERIFIED only.

Subcommands:
  add          --statement S --wit PATH [--lean PATH] [--tier T] [--target-hash H] [--provenance P]
  search       --query Q [--limit N] [--require-lean] [--min-tier T]
  get          --id ID
  verify-lean  --id ID --lean PATH [--lake-dir DIR]   (runs the Lean toolchain; upgrades tier)
  stats
  export-training --out FILE.jsonl                     (reward-labelled records)

Storage: a single SQLite file (default: <library>/lemmas.db).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import witcore  # noqa: E402  -- global (live) library path resolution
from lean_check import lean_verify  # noqa: E402  -- shared kernel check + soundness scan

TIER_RANK = {"WIT_STRUCTURE": 1, "WIT_RECEIPT": 2, "LEAN_VERIFIED": 3}
LEAN_BOOST = 0.5  # how much each tier above the base lifts the search score


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) > 1]


from witcore import cosine  # noqa: E402  -- shared substrate, was a local copy

def connect(library: Path) -> sqlite3.Connection:
    library.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(library / "lemmas.db")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement TEXT NOT NULL,
            tokens TEXT NOT NULL,
            wit_path TEXT,
            lean_path TEXT,
            trust_tier TEXT NOT NULL,
            target_hash TEXT,
            provenance TEXT,
            created_at REAL
        )"""
    )
    conn.commit()
    return conn


def cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.library)
    tier = args.tier
    if tier not in TIER_RANK:
        raise SystemExit(f"unknown tier {tier}; choose from {sorted(TIER_RANK)}")
    cur = conn.execute(
        "INSERT INTO lemmas (statement, tokens, wit_path, lean_path, trust_tier, target_hash, provenance, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (args.statement, " ".join(tokens(args.statement)),
         str(args.wit) if args.wit else None,
         str(args.lean) if args.lean else None,
         tier, args.target_hash, args.provenance, time.time()),
    )
    conn.commit()
    return {"status": "added", "id": cur.lastrowid, "trust_tier": tier}


def _row_to_dict(row: sqlite3.Row | tuple, cols: list[str]) -> dict[str, Any]:
    return {c: row[i] for i, c in enumerate(cols)}


COLS = ["id", "statement", "tokens", "wit_path", "lean_path", "trust_tier", "target_hash", "provenance", "created_at"]


def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.library)
    rows = conn.execute(f"SELECT {','.join(COLS)} FROM lemmas").fetchall()
    qvec = Counter(tokens(args.query))
    min_rank = TIER_RANK.get(args.min_tier, 1)
    scored = []
    for row in rows:
        rec = _row_to_dict(row, COLS)
        rank = TIER_RANK.get(rec["trust_tier"], 1)
        if args.require_lean and rec["trust_tier"] != "LEAN_VERIFIED":
            continue
        if rank < min_rank:
            continue
        sim = cosine(qvec, Counter(rec["tokens"].split()))
        # Lean-significance boost: stronger tiers rank higher at equal similarity.
        score = sim * (1.0 + LEAN_BOOST * (rank - 1))
        scored.append((score, sim, rec))
    scored.sort(key=lambda x: (-x[0], -TIER_RANK.get(x[2]["trust_tier"], 1)))
    matches = [{
        "id": rec["id"], "score": round(s, 6), "similarity": round(sim, 6),
        "trust_tier": rec["trust_tier"], "statement": rec["statement"],
        "wit_path": rec["wit_path"], "lean_path": rec["lean_path"],
        "provenance": rec["provenance"],  # surfaced so callers needn't a second `get` round-trip
    } for s, sim, rec in scored[: args.limit]]
    return {"query": args.query, "require_lean": args.require_lean, "matches": matches}


def cmd_get(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.library)
    row = conn.execute(f"SELECT {','.join(COLS)} FROM lemmas WHERE id=?", (args.id,)).fetchone()
    if not row:
        return {"status": "not_found", "id": args.id}
    rec = _row_to_dict(row, COLS)
    rec.pop("tokens", None)
    return rec


def cmd_verify_lean(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.library)
    row = conn.execute("SELECT id FROM lemmas WHERE id=?", (args.id,)).fetchone()
    if not row:
        return {"status": "not_found", "id": args.id}
    # lean_verify = real build AND soundness scan. A build that is green but uses
    # `sorry`/`admit`/`sorryAx`/a local `axiom` is NOT a verification and must not
    # earn the LEAN_VERIFIED tier — that was the soundness hole this closes.
    result = lean_verify(args.lean, args.lake_dir)
    if result.get("verified"):
        conn.execute("UPDATE lemmas SET trust_tier=?, lean_path=? WHERE id=?",
                     ("LEAN_VERIFIED", str(args.lean), args.id))
        conn.commit()
        return {"status": "upgraded", "id": args.id, "trust_tier": "LEAN_VERIFIED", "lean": result}
    return {"status": "not_upgraded", "id": args.id,
            "reason": result.get("reason"), "forbidden": result.get("forbidden", []),
            "lean": result}


def cmd_stats(args: argparse.Namespace) -> dict[str, Any]:
    conn = connect(args.library)
    total = conn.execute("SELECT COUNT(*) FROM lemmas").fetchone()[0]
    by_tier = dict(conn.execute("SELECT trust_tier, COUNT(*) FROM lemmas GROUP BY trust_tier").fetchall())
    return {"total": total, "by_tier": by_tier, "lean_fraction": round((by_tier.get("LEAN_VERIFIED", 0) / total) if total else 0.0, 3)}


def cmd_export_training(args: argparse.Namespace) -> dict[str, Any]:
    """Emit reward-labelled (problem -> proof) records for expert iteration."""
    conn = connect(args.library)
    rows = conn.execute(f"SELECT {','.join(COLS)} FROM lemmas").fetchall()
    out = []
    for row in rows:
        rec = _row_to_dict(row, COLS)
        rank = TIER_RANK.get(rec["trust_tier"], 1)
        out.append({
            "kind": "lemma",
            "problem": rec["statement"],
            "wit_path": rec["wit_path"],
            "lean_path": rec["lean_path"],
            "trust_tier": rec["trust_tier"],
            # Reward signal: Lean-verified proofs are worth the most.
            "reward": round(rank / max(TIER_RANK.values()), 3),
            "target_hash": rec["target_hash"],
            "provenance": rec["provenance"],
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + ("\n" if out else ""), encoding="utf-8")
    return {"status": "exported", "records": len(out), "out": str(args.out)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", type=Path, default=None,
                        help="Directory holding lemmas.db. Default: the GLOBAL live library "
                             "(witcore.global_library(), ~/.witsoc/global_library) so every "
                             "agent and deep run shares one DB regardless of cwd.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add")
    p_add.add_argument("--statement", required=True)
    p_add.add_argument("--wit", type=Path)
    p_add.add_argument("--lean", type=Path)
    p_add.add_argument("--tier", default="WIT_STRUCTURE")
    p_add.add_argument("--target-hash")
    p_add.add_argument("--provenance")

    p_search = sub.add_parser("search")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument("--require-lean", action="store_true")
    p_search.add_argument("--min-tier", default="WIT_STRUCTURE")

    p_get = sub.add_parser("get")
    p_get.add_argument("--id", type=int, required=True)

    p_vl = sub.add_parser("verify-lean")
    p_vl.add_argument("--id", type=int, required=True)
    p_vl.add_argument("--lean", type=Path, required=True)
    p_vl.add_argument("--lake-dir", type=Path)

    sub.add_parser("stats")

    p_exp = sub.add_parser("export-training")
    p_exp.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.library is None:
        args.library = witcore.global_library()
    handlers = {
        "add": cmd_add, "search": cmd_search, "get": cmd_get,
        "verify-lean": cmd_verify_lean, "stats": cmd_stats, "export-training": cmd_export_training,
    }
    out = handlers[args.cmd](args)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
