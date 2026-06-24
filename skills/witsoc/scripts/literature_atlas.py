#!/usr/bin/env python3
"""Persistent cross-problem literature atlas (P4).

The researcher bootstrap loop (literature_search -> ledger -> theorem_extract)
works, but it re-fetches from scratch for every target: findings the fleet
surfaced for one additive-combinatorics problem (Green–Tao, Szemerédi) are lost
to the next one, which dead-ends and re-emits a literature_search. This atlas is
a global, append-only cache of bus-supplied findings keyed by salient topic
tokens, so a target that overlaps a previously-researched one reuses the cached
sources instead of round-tripping through the orchestrator again.

Trust discipline is unchanged: cached findings are untrusted POINTERS, exactly
like a fresh literature_search reply. They become a per-problem source ledger
(re-usable by theorem-audit), never theorem evidence — extraction + kernel
gating still happen downstream.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402

SCHEMA = "witsoc.literature_atlas.v1"
_STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "has",
         "are", "all", "any", "every", "exists", "such", "then", "there",
         "conjecture", "problem", "theorem", "erdos", "erdős"}


def atlas_path() -> Path:
    return witcore.witsoc_home() / "literature_atlas.json"


def _tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9]{3,}", (text or "").lower())
    return {t for t in toks if t not in _STOP}


def _load() -> dict:
    data = witcore.load_json(atlas_path(), None)
    if isinstance(data, dict) and data.get("schema") == SCHEMA and isinstance(data.get("entries"), list):
        return data
    return {"schema": SCHEMA, "entries": []}


def record(topic: str, findings: list[dict], *, domain: str = "") -> dict:
    """Append (or merge into) the atlas the findings gathered for `topic`. Returns
    {recorded, total_entries}. De-dupes findings within a topic by (title,source)."""
    findings = [f for f in (findings or []) if isinstance(f, dict)]
    if not findings:
        return {"recorded": 0, "total_entries": len(_load()["entries"])}
    atlas = _load()
    toks = sorted(_tokens(topic) | _tokens(domain))
    # merge into an existing entry with the SAME topic string, else append
    entry = next((e for e in atlas["entries"] if e.get("topic") == topic), None)
    if entry is None:
        entry = {"topic": topic, "domain": domain, "tokens": toks,
                 "findings": [], "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        atlas["entries"].append(entry)
    seen = {(str(f.get("title")), str(f.get("source") or f.get("url")))
            for f in entry["findings"]}
    added = 0
    for f in findings:
        key = (str(f.get("title")), str(f.get("source") or f.get("url")))
        if key not in seen:
            entry["findings"].append(f)
            seen.add(key)
            added += 1
    entry["domain"] = entry.get("domain") or domain
    entry["tokens"] = sorted(set(entry.get("tokens") or []) | set(toks))
    entry["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    witcore.save_json(atlas_path(), atlas)
    return {"recorded": added, "total_entries": len(atlas["entries"])}


def lookup(target: str, *, domain: str = "", min_overlap: int = 2) -> dict | None:
    """Best cached entry whose topic tokens overlap the target (a domain match
    adds a point). Returns {topic, findings, overlap, score} or None. The
    overlap threshold avoids spurious one-word hits."""
    want = _tokens(target) | _tokens(domain)
    if not want:
        return None
    atlas = _load()
    best = None
    best_score = 0
    for e in atlas["entries"]:
        etoks = set(e.get("tokens") or [])
        overlap = len(want & etoks)
        score = overlap + (1 if domain and e.get("domain") == domain else 0)
        if overlap >= min_overlap and score > best_score and e.get("findings"):
            best, best_score = e, score
    if best is None:
        return None
    return {"topic": best["topic"], "domain": best.get("domain", ""),
            "findings": best["findings"], "overlap": len(want & set(best.get("tokens") or [])),
            "score": best_score}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lookup")
    p.add_argument("--target", required=True)
    p.add_argument("--domain", default="")
    p.add_argument("--min-overlap", type=int, default=2)
    p2 = sub.add_parser("list")
    args = ap.parse_args()
    if args.cmd == "lookup":
        print(json.dumps(lookup(args.target, domain=args.domain, min_overlap=args.min_overlap)
                         or {"hit": False}, indent=2, ensure_ascii=False))
    else:
        atlas = _load()
        print(json.dumps({"entries": [{"topic": e["topic"], "domain": e.get("domain"),
                                       "findings": len(e["findings"])} for e in atlas["entries"]]},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
