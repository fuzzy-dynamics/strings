#!/usr/bin/env python3
"""Layer 3.3: premise resolution validator — no hallucinated citations.

Every premise the prover/atlas wants to cite must either RESOLVE to a real Lean
declaration (checked with the toolchain) or be explicitly marked a SEARCH_TARGET.
A name that does not resolve is never silently used as if it existed.

Degrades gracefully: with no Lean toolchain, everything is UNCHECKED (never a
silent pass). This only ever classifies; it cannot upgrade trust.

Usage:
  validate_premises.py --names "Nat.mul_comm,Nat.foo" [--imports "import Mathlib"]
  validate_premises.py --atlas core_lemma_atlas.json [--lake-dir DIR] [--out J]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import witcore  # noqa: E402


def names_from_atlas(path: Path) -> list[str]:
    data = witcore.load_json(path, {})
    out: list[str] = []
    for node in data.get("nodes", []) or []:
        for sym in node.get("symbols", []) or []:
            if sym not in out:
                out.append(str(sym))
    return out


def resolve(name: str, imports: str, lake_dir: Path | None) -> dict:
    """Return {state: KNOWN|SEARCH_TARGET|UNCHECKED}. Uses `#check @name`."""
    src = (f"{imports}\n" if imports else "") + f"#check @{name}\n"
    verdict = witcore.lean_verify_cached(src, lake_dir)
    if not verdict.get("checked"):
        return {"name": name, "state": "UNCHECKED"}
    return {"name": name, "state": "KNOWN" if verdict.get("build_ok") else "SEARCH_TARGET"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--names", default=None, help="comma-separated lemma names")
    ap.add_argument("--atlas", type=Path, default=None, help="atlas JSON to validate all node symbols")
    ap.add_argument("--imports", default="", help="Lean imports/preamble providing the declarations")
    ap.add_argument("--lake-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    names: list[str] = []
    if args.names:
        names += [n.strip() for n in args.names.split(",") if n.strip()]
    if args.atlas:
        names += names_from_atlas(args.atlas)
    names = list(dict.fromkeys(names))

    results = [resolve(n, args.imports, args.lake_dir) for n in names]
    by_state: dict[str, list[str]] = {}
    for r in results:
        by_state.setdefault(r["state"], []).append(r["name"])

    out = {
        "schema": "witsoc.premise_validation.v1",
        "total": len(names),
        "known": by_state.get("KNOWN", []),
        "search_targets": by_state.get("SEARCH_TARGET", []),
        "unchecked": by_state.get("UNCHECKED", []),
        "toolchain": "absent" if by_state.get("UNCHECKED") and not (by_state.get("KNOWN") or by_state.get("SEARCH_TARGET")) else "present",
        "note": "SEARCH_TARGET names do not resolve in the given imports; treat as goals to find/prove, never as established citations.",
    }
    if args.out:
        witcore.save_json(args.out, out)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
