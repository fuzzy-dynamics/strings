#!/usr/bin/env python3
"""Novelty triage — `witsoc novelty`: is a candidate result actually NEW?

A result is not a discovery until it is both VERIFIED (the trust lattice's
job) and NEW (this tool's job). Verification and novelty are independent axes:
a kernel-verified lemma can be a textbook fact, and a genuinely new conjecture
can be unverified. The discovery ledger records both.

Checks, in order:
  1. LIVE LIBRARY     identical statement hash already recorded -> KNOWN_INTERNAL
  2. REFERENCE ATLAS  strong match in the merged theorem atlas (Mathlib + core
                      + promoted) -> KNOWN with the matching module as evidence
  3. EXTERNAL         pluggable `cmd:` checker (env WITSOC_NOVELTY_CMD): gets
                      {statement, keywords, sequence?} on stdin, returns
                      {known: bool, source?: str}. Wire an OEIS/web/literature
                      agent here; absent -> the external axis is honestly
                      UNCHECKED, never silently assumed clean.

Verdicts (the only values this tool emits):
  KNOWN_INTERNAL        already in the live library (not new to the system)
  KNOWN                 matches reference atlas or external source
  NOVEL_CANDIDATE       local checks clean AND an external check ran clean
  LOCALLY_NEW_UNCHECKED local checks clean, no external checker available

This tool NEVER upgrades trust; novelty is metadata for the discovery ledger
and the human gate, not a verification verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import theorem_atlas as ta  # noqa: E402
import witcore  # noqa: E402

# A reference-atlas match this strong (cosine on statement-vs-module text, or
# full symbol provision) is treated as "this is already known mathematics".
ATLAS_KNOWN_SIMILARITY = 0.75
ATLAS_KNOWN_SYMBOL_OVERLAP = 1.0


def statement_key(statement: str) -> str:
    return hashlib.sha256(" ".join(statement.split()).encode("utf-8")).hexdigest()[:16]


def check_live_library(statement: str, library: Path | None = None) -> dict | None:
    db = Path(library or witcore.global_library()) / "lemmas.db"
    if not db.exists():
        return None
    conn = sqlite3.connect(db)
    norm = " ".join(statement.split())
    for (stmt,) in conn.execute("SELECT statement FROM lemmas"):
        if " ".join(str(stmt).split()) == norm:
            return {"check": "live_library", "match": stmt}
    return None


def check_reference_atlas(statement: str) -> dict | None:
    class _A:  # reuse the atlas search handler without re-implementing scoring
        query, signature, limit = statement, "", 3
    res = ta.cmd_search(_A)
    for m in res.get("matches", []):
        if (m.get("similarity", 0) >= ATLAS_KNOWN_SIMILARITY
                or m.get("symbol_overlap", 0) >= ATLAS_KNOWN_SYMBOL_OVERLAP):
            return {"check": "reference_atlas", "module": m["module"],
                    "similarity": m.get("similarity"), "symbol_overlap": m.get("symbol_overlap"),
                    "source": m.get("source")}
    return None


_NETWORK_DOWN = False  # set after the first failed literature probe (process-level memo)


def check_external(statement: str, keywords: list[str], sequence: list[int] | None) -> dict | None:
    """Returns {known, source?} from the external checker, or None when no
    checker is configured (honest UNCHECKED, never assumed clean).

    F4 default: with no WITSOC_NOVELTY_CMD, the literature engine's arXiv
    keyword probe runs instead. Asymmetric by design: a probe MATCH counts as
    known-candidate prior work (sources attached for reading), but an empty
    probe result is NOT clean — keyword search misses things, so no-match
    returns None and the verdict stays LOCALLY_NEW_UNCHECKED with the probe
    recorded nowhere above evidence level."""
    cmd = os.environ.get("WITSOC_NOVELTY_CMD")
    if not cmd:
        # Isolated runs (tests, air-gapped) never probe; one network failure
        # memoizes the process as offline so triage stays fast.
        if os.environ.get("WITSOC_CORE_ONLY") or os.environ.get("WITSOC_LITERATURE_OFFLINE"):
            return None
        global _NETWORK_DOWN
        if _NETWORK_DOWN:
            return None
        try:
            import literature_engine as le
            probe = le.novelty_probe(statement, keywords, timeout=6.0)
        except Exception:
            return None
        if probe.get("status") != "ok":
            _NETWORK_DOWN = True
            return None
        if probe.get("known"):
            return {"check": "external", "known": True, "source": probe.get("source"),
                    "checker": "literature_engine.arxiv_probe", "matches": probe.get("matches")}
        return None  # no keyword match -> still UNCHECKED, never assumed clean
    out = witcore.run_sampler(cmd, {"statement": statement, "keywords": keywords,
                                    "sequence": sequence or []})
    if not isinstance(out, dict) or "known" not in out:
        return None  # checker failed -> still UNCHECKED, not clean
    return {"check": "external", "known": bool(out["known"]), "source": out.get("source")}


def triage(statement: str, keywords: list[str] | None = None,
           sequence: list[int] | None = None, library: Path | None = None) -> dict:
    evidence = []
    lib = check_live_library(statement, library)
    if lib:
        return {"novelty": "KNOWN_INTERNAL", "evidence": [lib], "statement_key": statement_key(statement)}
    atlas = check_reference_atlas(statement)
    if atlas:
        evidence.append(atlas)
        return {"novelty": "KNOWN", "evidence": evidence, "statement_key": statement_key(statement)}
    ext = check_external(statement, keywords or [], sequence)
    if ext is None:
        return {"novelty": "LOCALLY_NEW_UNCHECKED", "evidence": evidence,
                "statement_key": statement_key(statement),
                "note": "no external checker (WITSOC_NOVELTY_CMD); novelty NOT established"}
    evidence.append(ext)
    if ext["known"]:
        return {"novelty": "KNOWN", "evidence": evidence, "statement_key": statement_key(statement)}
    return {"novelty": "NOVEL_CANDIDATE", "evidence": evidence, "statement_key": statement_key(statement)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statement", required=True)
    ap.add_argument("--keywords", default="", help="comma-separated")
    ap.add_argument("--sequence", default="", help="comma-separated integers (for OEIS-style checks)")
    ap.add_argument("--library", type=Path, default=None)
    args = ap.parse_args()
    seq = [int(x) for x in args.sequence.split(",") if x.strip().lstrip("-").isdigit()]
    kws = [k.strip() for k in args.keywords.split(",") if k.strip()]
    print(json.dumps(triage(args.statement, kws, seq, args.library), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
