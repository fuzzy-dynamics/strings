#!/usr/bin/env python3
"""W3 tactic n-grams — `witsoc tactics`.

The last original-roadmap item: successful proofs are full of reusable tactic
SEQUENCES (`intro n; induction n <;> simp_all`), but the prover's candidate
pool only ever held single tactics and whole harvested proofs. This mines
n-grams (length 1–3) from every verified proof witsoc has produced — the
proof bank plus the live library's provenance — keyed by goal signature, and
feeds them back as prover candidates:

  mine            (re)build the n-gram table in the knowledge substrate
  candidates-for  signature-matched n-grams first, then the global
                  most-successful — returned as `by <sequence>` candidates

close_obligation consumes `candidates_for` automatically (guarded; empty
table = no cost). As always: candidates only — the kernel rejects wrong ones,
so mining can only extend reach.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

MAX_N = 3
_SPLIT_RE = re.compile(r";|<;>")


def _connect() -> sqlite3.Connection:
    import knowledge_store as ks
    con = ks.connect()
    con.execute("CREATE TABLE IF NOT EXISTS tactic_ngrams ("
                " signature TEXT, ngram TEXT, count INTEGER, updated INTEGER,"
                " PRIMARY KEY (signature, ngram))")
    return con


# A usable candidate step is SHORT: Mathlib's structured multi-line proofs
# collapse to one giant "step" under the ;-splitter, and each such monster
# would cost a doomed kernel build when raced as a candidate. Cap hard.
MAX_STEP_CHARS = 48


def steps_of(proof: str) -> list[str]:
    body = proof.strip()
    if body.startswith("by"):
        body = body[2:]
    return [s.strip() for s in _SPLIT_RE.split(body)
            if s.strip() and len(s.strip()) <= MAX_STEP_CHARS]


def ngrams_of(proof: str) -> list[str]:
    steps = steps_of(proof)
    out = []
    for n in range(1, min(MAX_N, len(steps)) + 1):
        for i in range(len(steps) - n + 1):
            out.append("; ".join(steps[i:i + n]))
    return out


def _proof_sources() -> list[tuple[str, str]]:
    """(goal, proof) pairs from the proof bank and the live library provenance."""
    pairs: list[tuple[str, str]] = []
    import knowledge_store as ks
    con = ks.connect()
    try:
        pairs += [(g, p) for g, p in con.execute("SELECT goal, proof FROM proof_bank")]
    except sqlite3.OperationalError:
        pass
    con.close()
    db = witcore.global_library() / "lemmas.db"
    if db.exists():
        try:
            lib = sqlite3.connect(db)
            for stmt, prov in lib.execute("SELECT statement, provenance FROM lemmas LIMIT 5000"):
                prov = str(prov or "")
                if ":by " in prov or prov.startswith("by "):
                    proof = prov.split(":", 1)[1] if ":" in prov and not prov.startswith("by ") else prov
                    if proof.strip().startswith("by"):
                        pairs.append((str(stmt), proof.strip()))
            lib.close()
        except Exception:
            pass
    return pairs


def mine() -> dict:
    import knowledge_store as ks
    pairs = _proof_sources()
    con = _connect()
    now = int(time.time())
    rows = 0
    for goal, proof in pairs:
        sig = ks.goal_signature(goal)
        for ng in ngrams_of(proof):
            con.execute("INSERT INTO tactic_ngrams (signature, ngram, count, updated)"
                        " VALUES (?,?,1,?) ON CONFLICT(signature, ngram)"
                        " DO UPDATE SET count = count + 1, updated = excluded.updated",
                        (sig, ng, now))
            rows += 1
    con.commit()
    total, = con.execute("SELECT COUNT(*) FROM tactic_ngrams").fetchone()
    con.close()
    return {"schema": "witsoc.tactic_ngrams.v1", "proofs_mined": len(pairs),
            "ngram_rows_touched": rows, "distinct_ngrams": total}


def mine_source(src: Path, limit: int = 200000) -> dict:
    """P-battery prep: mine tactic n-grams from an entire Lean source tree's
    kernel-verified proofs (e.g. ~/mathlib4/Mathlib) — the same upstream-trust
    contract as mathlib_autopsy (verified upstream, syntactically extracted,
    candidates only; the kernel rejects what doesn't fit). This is how the
    deterministic portfolio inherits thousands of real proof moves."""
    import knowledge_store as ks
    from mathlib_autopsy import extract_theorems
    con = _connect()
    now = int(time.time())
    proofs = rows = 0
    for path in sorted(Path(src).rglob("*.lean")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for decl in extract_theorems(text):
            sig = ks.goal_signature(decl["statement"])
            for ng in ngrams_of(decl["proof"]):
                con.execute("INSERT INTO tactic_ngrams (signature, ngram, count, updated)"
                            " VALUES (?,?,1,?) ON CONFLICT(signature, ngram)"
                            " DO UPDATE SET count = count + 1, updated = excluded.updated",
                            (sig, ng, now))
                rows += 1
            proofs += 1
            if proofs >= limit:
                break
        if proofs >= limit:
            break
    con.commit()
    total, = con.execute("SELECT COUNT(*) FROM tactic_ngrams").fetchone()
    con.close()
    return {"schema": "witsoc.tactic_ngrams.v1", "source": str(src),
            "proofs_mined": proofs, "ngram_rows_touched": rows, "distinct_ngrams": total}


def candidates_for(goal: str, k: int = 6) -> list[str]:
    """`by <sequence>` candidates: exact-signature matches first (the moves
    that closed structurally identical goals), then the global best."""
    import knowledge_store as ks
    con = _connect()
    sig = ks.goal_signature(goal)
    rows = [ng for ng, in con.execute(
        "SELECT ngram FROM tactic_ngrams WHERE signature = ? ORDER BY count DESC LIMIT ?",
        (sig, k))]
    if len(rows) < k:
        rows += [ng for ng, _c in con.execute(
            "SELECT ngram, SUM(count) AS c FROM tactic_ngrams GROUP BY ngram"
            " ORDER BY c DESC LIMIT ?", (k,)) if ng not in rows][: k - len(rows)]
    con.close()
    return [f"by {ng}" for ng in rows[:k]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mine")
    p_src = sub.add_parser("mine-source")
    p_src.add_argument("src", type=Path, help="Lean source tree (e.g. ~/mathlib4/Mathlib)")
    p_src.add_argument("--limit", type=int, default=200000)
    p_c = sub.add_parser("candidates-for")
    p_c.add_argument("--goal", required=True)
    p_c.add_argument("-k", type=int, default=6)
    args = ap.parse_args()
    if args.cmd == "mine":
        result = mine()
    elif args.cmd == "mine-source":
        result = mine_source(args.src, args.limit)
    else:
        result = {"candidates": candidates_for(args.goal, args.k)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
