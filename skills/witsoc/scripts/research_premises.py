#!/usr/bin/env python3
"""Researcher → prover premise bridge (Phase 2).

The researcher loop (literature_search → theorem_extract → bus-apply) turns a
target into EXTRACTED rows in `theorem_precondition_audit.json`: real known
theorems with an exact statement, hypotheses, and conclusion. Until now those
extractions were a dead end — read but never USED. This module turns them into a
reusable premise store the prover/reduction can consult.

Honesty contract (non-negotiable): an extracted theorem is an untrusted CITATION,
never a kernel fact. A premise becomes part of a proof only by being `apply`-ed in
a goal the kernel then checks. So:
  * `formal_availability == "mathlib"` premises are offered to the prover as
    candidate lemmas to try (still kernel-gated downstream);
  * everything else is recorded as an informal citation the orchestrator may
    formalize, but it NEVER discharges an obligation on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

PREMISES_NAME = "research_premises.json"
SCHEMA = "witsoc.research_premises.v1"


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _rows(run: Path) -> list[dict]:
    data = _load(run / "theorem_precondition_audit.json", [])
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def build_premises(run: Path) -> dict:
    """Turn EXTRACTED audit rows into a premise store. Returns the store dict and
    writes it to `research_premises.json`."""
    premises = []
    for r in _rows(run):
        if str(r.get("extraction_status") or "").upper() != "EXTRACTED":
            continue
        stmt = str(r.get("exact_statement") or "").strip()
        if not stmt or stmt.upper().startswith("PENDING") or stmt.upper() == "NONE":
            continue
        availability = str(r.get("formal_availability") or "unknown").lower()
        premises.append({
            "name": str(r.get("candidate_theorem") or "extracted_theorem"),
            "exact_statement": stmt,
            "hypotheses": [str(h) for h in (r.get("required_preconditions") or [])],
            "conclusion": str(r.get("conclusion") or ""),
            "formal_availability": availability,
            "source": str(r.get("source") or ""),
            # only mathlib-available theorems are directly try-able by the prover;
            # the rest are citations the orchestrator may formalize first.
            "usable_as_prover_premise": availability == "mathlib",
            "trust": "UNTRUSTED_CITATION (kernel-gated only when applied in a checked proof)",
        })
    store = {
        "schema": SCHEMA,
        "count": len(premises),
        "prover_ready": sum(1 for p in premises if p["usable_as_prover_premise"]),
        "premises": premises,
        "note": "extracted theorems are citations, not facts; they discharge nothing on their own",
    }
    (run / PREMISES_NAME).write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    return store


def prover_premises(run: Path) -> list[str]:
    """The subset offered to the prover as candidate `apply` lemmas — the
    mathlib-available extracted theorems' names. Still kernel-gated downstream."""
    store = _load(run / PREMISES_NAME, None)
    if not (isinstance(store, dict) and store.get("schema") == SCHEMA):
        store = build_premises(run)
    return [p["name"] for p in store.get("premises", []) if p.get("usable_as_prover_premise")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    args = ap.parse_args()
    print(json.dumps(build_premises(args.run_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
